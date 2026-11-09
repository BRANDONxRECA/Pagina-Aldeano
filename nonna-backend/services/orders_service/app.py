"""orders (microservicio privado). Autoridad sobre pedidos y su ciclo de vida (nonna_orders).

Reglas:
- El navegador envía solo product_id, cantidad, tipo de entrega y address_id. Precios,
  nombres, totales y estado los calcula/decide el servidor.
- Estados: PENDIENTE_PAGO -> PAGADO (solo payments) -> PREPARANDO -> LISTO -> ENTREGADO
  (personal). ANULADO desde PENDIENTE_PAGO (cliente dueño o admin) o desde PAGADO/PREPARANDO
  (solo admin; reembolso manual). Nada se borra: toda transición queda en order_status_history.
- Un cliente solo ve sus pedidos; un pedido ajeno responde 404 (no revela que existe).
- Pedidos impagos vencen junto con la reserva de stock y se anulan (recuperación de stock).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import secrets as pysecrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from common.db import get_engine
from common.service import (
    ApiError, Caller, DependencyError, UserCtx, call_service, create_app, expect_ok,
    get_logger, require_callers, require_user,
)
from common.tables import order_items, order_status_history, orders

log = get_logger("orders")
DELIVERY_FEE_CLP = int(os.environ.get("DELIVERY_FEE_CLP", "0"))
RESERVATION_MINUTES = int(os.environ.get("RESERVATION_MINUTES", "15"))
EXPIRY_LOOP_SECONDS = int(os.environ.get("ORDER_EXPIRY_LOOP_SECONDS", "60"))
STAFF_TRANSITIONS = {"PAGADO": "PREPARANDO", "PREPARANDO": "LISTO", "LISTO": "ENTREGADO"}


@contextlib.asynccontextmanager
async def lifespan(_app):
    task = None
    if EXPIRY_LOOP_SECONDS > 0:
        async def loop():
            while True:
                await asyncio.sleep(EXPIRY_LOOP_SECONDS)
                try:
                    await expire_pending_orders()
                except Exception:  # el job nunca debe botar el servicio
                    log.exception("expiry_job_failed")
        task = asyncio.create_task(loop())
    yield
    if task:
        task.cancel()


app = create_app("orders", lifespan=lifespan)


def db():
    return get_engine("orders")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemIn(Strict):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=20)


class OrderIn(Strict):
    items: list[ItemIn] = Field(min_length=1, max_length=20)
    delivery_type: str = Field(pattern="^(DESPACHO|RETIRO)$")
    address_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _address_rule(self):
        if self.delivery_type == "DESPACHO" and self.address_id is None:
            raise ValueError("address_id es obligatorio para DESPACHO")
        if self.delivery_type == "RETIRO" and self.address_id is not None:
            raise ValueError("address_id no aplica para RETIRO")
        return self


class StatusIn(Strict):
    status: str = Field(pattern="^(PREPARANDO|LISTO|ENTREGADO)$")


class MarkPaidIn(Strict):
    payment_id: int = Field(gt=0)
    amount_clp: int = Field(gt=0)


# ---------------------------------------------------------------- helpers
_client_cache: dict[int, int] = {}


async def client_id_for(user: UserCtx) -> int:
    if user.user_id not in _client_cache:
        data = expect_ok(await call_service("clients", "GET", f"/internal/clients/by-user/{user.user_id}"), "clients")
        _client_cache[user.user_id] = data["id"]
    return _client_cache[user.user_id]


def order_dto(row, items, include_client: bool = False) -> dict:
    dto = {
        "order_code": row.order_code, "status": row.status, "delivery_type": row.delivery_type,
        "delivery_address": row.delivery_address, "subtotal_clp": row.subtotal_clp,
        "delivery_fee_clp": row.delivery_fee_clp, "total_clp": row.total_clp,
        "created_at": row.created_at.isoformat(),
        "items": [{"product_id": i.product_id, "product_name": i.product_name,
                   "unit_price_clp": i.unit_price_clp, "quantity": i.quantity,
                   "line_total_clp": i.unit_price_clp * i.quantity} for i in items],
    }
    if include_client:
        dto["client_id"] = row.client_id
    return dto


def load_items(conn, order_ids: list[int]) -> dict[int, list]:
    out: dict[int, list] = {oid: [] for oid in order_ids}
    if order_ids:
        for it in conn.execute(select(order_items).where(order_items.c.order_id.in_(order_ids)).order_by(order_items.c.id)).all():
            out[it.order_id].append(it)
    return out


def fetch_order(conn, code: str):
    return conn.execute(select(orders).where(orders.c.order_code == code)).first()


def set_status(conn, order_row, to_status: str, changed_by: str, expected_from: str | None = None) -> bool:
    from_status = expected_from or order_row.status
    res = conn.execute(update(orders).where(orders.c.id == order_row.id, orders.c.status == from_status).values(status=to_status))
    if res.rowcount != 1:
        return False
    conn.execute(insert(order_status_history).values(order_id=order_row.id, from_status=from_status, to_status=to_status, changed_by=changed_by[:60]))
    return True


async def release_reservation(order_id: int) -> None:
    try:
        resp = await call_service("inventory", "POST", f"/internal/reservations/{order_id}/release")
        if resp.status_code not in (200, 404, 409):  # 409: ya expirada/confirmada
            log.warning("release_failed", extra={"fields": {"order_id": order_id, "status": resp.status_code}})
    except DependencyError:
        # La reserva expira sola en inventory: el stock se recupera igual.
        log.warning("release_deferred", extra={"fields": {"order_id": order_id}})


def paginate(stmt, page: int, page_size: int):
    return stmt.limit(page_size).offset((page - 1) * page_size)


# -------------------------------------------------- API (vía API Gateway)
@app.post("/orders", status_code=201)
async def create_order(body: OrderIn, user: UserCtx = Depends(require_user("CLIENTE"))):
    client_id = await client_id_for(user)
    merged: dict[int, int] = {}
    for it in body.items:
        merged[it.product_id] = merged.get(it.product_id, 0) + it.quantity
    if any(q > 20 for q in merged.values()):
        raise ApiError(422, "QUANTITY_LIMIT", "Máximo 20 unidades por producto")

    # Precios y nombres oficiales desde inventory (nunca desde el navegador).
    catalog = expect_ok(await call_service("inventory", "GET", "/internal/products",
                                           params={"ids": ",".join(map(str, merged))}), "inventory")
    by_id = {p["id"]: p for p in catalog}
    missing = [pid for pid in merged if pid not in by_id or not by_id[pid]["active"]]
    if missing:
        raise ApiError(409, "PRODUCT_UNAVAILABLE", "Hay productos que no están disponibles", {"product_ids": missing})

    address_text = None
    fee = 0
    if body.delivery_type == "DESPACHO":
        addr = expect_ok(await call_service("clients", "GET", f"/internal/clients/{client_id}/addresses/{body.address_id}"), "clients")
        address_text = f"{addr['street']}, {addr['commune']}"[:255]
        fee = DELIVERY_FEE_CLP
    subtotal = sum(by_id[pid]["price_clp"] * q for pid, q in merged.items())

    def insert_order():
        with db().begin() as conn:
            for _ in range(5):
                code = f"P-{pysecrets.randbelow(900000) + 100000}"
                try:
                    oid = conn.execute(insert(orders).values(
                        order_code=code, client_id=client_id, status="PENDIENTE_PAGO",
                        delivery_type=body.delivery_type, delivery_address=address_text,
                        subtotal_clp=subtotal, delivery_fee_clp=fee, total_clp=subtotal + fee,
                    )).inserted_primary_key[0]
                    break
                except IntegrityError:
                    continue
            else:
                raise ApiError(503, "CODE_GENERATION", "Intente nuevamente")
            conn.execute(insert(order_items), [
                {"order_id": oid, "product_id": pid, "product_name": by_id[pid]["name"],
                 "unit_price_clp": by_id[pid]["price_clp"], "quantity": q} for pid, q in merged.items()])
            conn.execute(insert(order_status_history).values(order_id=oid, from_status=None, to_status="PENDIENTE_PAGO", changed_by=user.email[:60]))
            return oid, code

    oid, code = await run_in_threadpool(insert_order)

    # Reserva de stock. Si falla, el pedido queda ANULADO (se conserva el historial).
    try:
        reservation = expect_ok(await call_service("inventory", "POST", "/internal/reservations", json_body={
            "order_id": oid, "items": [{"product_id": p, "quantity": q} for p, q in merged.items()]}), "inventory")
    except ApiError as exc:
        def annul():
            with db().begin() as conn:
                set_status(conn, fetch_order(conn, code), "ANULADO", "svc-orders")
        await run_in_threadpool(annul)
        if isinstance(exc, DependencyError):
            await release_reservation(oid)  # por si la reserva alcanzó a crearse
        raise

    def read():
        with db().connect() as conn:
            row = fetch_order(conn, code)
            return order_dto(row, load_items(conn, [row.id])[row.id])
    dto = await run_in_threadpool(read)
    dto["payment_deadline"] = reservation["expires_at"]
    return dto


@app.get("/orders")
async def list_orders(
    status: str | None = Query(None, pattern="^(PENDIENTE_PAGO|PAGADO|PREPARANDO|LISTO|ENTREGADO|ANULADO)$"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    user: UserCtx = Depends(require_user()),
):
    client_id = None if user.is_staff else await client_id_for(user)

    def run():
        cond = []
        if client_id is not None:
            cond.append(orders.c.client_id == client_id)
        if status:
            cond.append(orders.c.status == status)
        with db().connect() as conn:
            total = conn.execute(select(func.count()).select_from(orders).where(*cond)).scalar_one()
            rows = conn.execute(paginate(select(orders).where(*cond).order_by(orders.c.created_at.desc(), orders.c.id.desc()), page, page_size)).all()
            items = load_items(conn, [r.id for r in rows])
            return {"page": page, "page_size": page_size, "total": total,
                    "items": [order_dto(r, items[r.id], include_client=user.is_staff) for r in rows]}
    return await run_in_threadpool(run)


@app.get("/orders/{code}")
async def get_order(code: str, user: UserCtx = Depends(require_user())):
    client_id = None if user.is_staff else await client_id_for(user)

    def run():
        with db().connect() as conn:
            row = fetch_order(conn, code)
            if row is None or (client_id is not None and row.client_id != client_id):
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
            return order_dto(row, load_items(conn, [row.id])[row.id], include_client=user.is_staff)
    return await run_in_threadpool(run)


@app.patch("/orders/{code}/status")
async def change_status(code: str, body: StatusIn, user: UserCtx = Depends(require_user("TRABAJADOR", "ADMIN"))):
    """PATCH: actualización parcial (solo el estado). PAGADO no se puede fijar aquí."""
    def run():
        with db().begin() as conn:
            row = fetch_order(conn, code)
            if row is None:
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
            if STAFF_TRANSITIONS.get(row.status) != body.status:
                raise ApiError(409, "INVALID_TRANSITION", f"No se puede pasar de {row.status} a {body.status}")
            if not set_status(conn, row, body.status, user.email):
                raise ApiError(409, "CONCURRENT_UPDATE", "El pedido cambió, recargue e intente nuevamente")
            return {"order_code": code, "status": body.status}
    return await run_in_threadpool(run)


@app.post("/orders/{code}/cancel")
async def cancel_order(code: str, user: UserCtx = Depends(require_user("CLIENTE", "ADMIN"))):
    """Anulación = cambio de estado, no borrado. El registro y su historial se conservan."""
    client_id = None if user.is_staff else await client_id_for(user)

    def run():
        with db().begin() as conn:
            row = fetch_order(conn, code)
            if row is None or (client_id is not None and row.client_id != client_id):
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
            allowed = ("PENDIENTE_PAGO",) if user.role == "CLIENTE" else ("PENDIENTE_PAGO", "PAGADO", "PREPARANDO")
            if row.status not in allowed:
                raise ApiError(409, "INVALID_TRANSITION", f"No se puede anular un pedido {row.status}")
            if not set_status(conn, row, "ANULADO", user.email):
                raise ApiError(409, "CONCURRENT_UPDATE", "El pedido cambió, recargue e intente nuevamente")
            return row
    row = await run_in_threadpool(run)
    if row.status == "PENDIENTE_PAGO":
        await release_reservation(row.id)
    result = {"order_code": code, "status": "ANULADO"}
    if row.status in ("PAGADO", "PREPARANDO"):
        result["note"] = "Pedido pagado: requiere reembolso manual"
    return result


@app.post("/admin/orders/expire-pending")
async def admin_expire(_: UserCtx = Depends(require_user("ADMIN"))):
    return await expire_pending_orders()


async def expire_pending_orders() -> dict:
    limit = now() - timedelta(minutes=RESERVATION_MINUTES)

    def annul():
        expired = []
        with db().begin() as conn:
            rows = conn.execute(select(orders).where(orders.c.status == "PENDIENTE_PAGO", orders.c.created_at < limit)).all()
            for r in rows:
                if set_status(conn, r, "ANULADO", "svc-orders"):
                    expired.append(r.id)
        return expired

    expired = await run_in_threadpool(annul)
    for oid in expired:
        await release_reservation(oid)
    try:
        await call_service("inventory", "POST", "/internal/reservations/expire")
    except DependencyError:
        pass
    return {"expired_orders": len(expired)}


# ------------------------------------------------ API interna (servicios)
@app.get("/internal/orders/by-code/{code}")
async def internal_by_code(code: str, _: Caller = Depends(require_callers("payments", "graphql"))):
    def run():
        with db().connect() as conn:
            row = fetch_order(conn, code)
            if row is None:
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
            return order_dto(row, load_items(conn, [row.id])[row.id], include_client=True) | {"id": row.id}
    return await run_in_threadpool(run)


@app.get("/internal/orders")
async def internal_list(
    client_id: int | None = Query(None, gt=0),
    statuses: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    _: Caller = Depends(require_callers("graphql")),
):
    status_list = [s for s in (statuses or "").split(",") if s]

    def run():
        cond = []
        if client_id is not None:
            cond.append(orders.c.client_id == client_id)
        if status_list:
            cond.append(orders.c.status.in_(status_list))
        with db().connect() as conn:
            total = conn.execute(select(func.count()).select_from(orders).where(*cond)).scalar_one()
            rows = conn.execute(paginate(select(orders).where(*cond).order_by(orders.c.created_at.desc(), orders.c.id.desc()), page, page_size)).all()
            items = load_items(conn, [r.id for r in rows])
            return {"page": page, "page_size": page_size, "total": total,
                    "items": [order_dto(r, items[r.id], include_client=True) | {"id": r.id} for r in rows]}
    return await run_in_threadpool(run)


@app.post("/internal/orders/{order_id}/mark-paid")
async def mark_paid(order_id: int, body: MarkPaidIn, _: Caller = Depends(require_callers("payments"))):
    """Solo payments puede marcar un pedido como pagado, y solo por el monto oficial."""
    def check():
        with db().connect() as conn:
            row = conn.execute(select(orders).where(orders.c.id == order_id)).first()
            if row is None:
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
            if row.total_clp != body.amount_clp:
                raise ApiError(409, "AMOUNT_MISMATCH", "El monto no coincide con el pedido")
            return row

    row = await run_in_threadpool(check)
    if row.status in ("PAGADO", "PREPARANDO", "LISTO", "ENTREGADO"):
        return {"order_id": order_id, "status": row.status, "idempotent": True}
    if row.status != "PENDIENTE_PAGO":
        raise ApiError(409, "ORDER_NOT_PAYABLE", f"El pedido está {row.status}; requiere reembolso")

    resp = await call_service("inventory", "POST", f"/internal/reservations/{order_id}/confirm")
    if resp.status_code == 409:
        # La reserva expiró antes del pago: no se puede garantizar el stock.
        def annul():
            with db().begin() as conn:
                set_status(conn, row, "ANULADO", "svc-orders", expected_from="PENDIENTE_PAGO")
        await run_in_threadpool(annul)
        raise ApiError(409, "RESERVATION_EXPIRED", "La reserva venció; el pago requiere reembolso")
    expect_ok(resp, "inventory")

    def pay():
        with db().begin() as conn:
            if not set_status(conn, row, "PAGADO", "svc-payments", expected_from="PENDIENTE_PAGO"):
                current = conn.execute(select(orders.c.status).where(orders.c.id == order_id)).scalar_one()
                if current != "PAGADO":
                    raise ApiError(409, "ORDER_NOT_PAYABLE", f"El pedido está {current}")
    await run_in_threadpool(pay)
    return {"order_id": order_id, "status": "PAGADO", "idempotent": False}


@app.get("/internal/sales-source")
async def sales_source(
    date_from: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=500),
    _: Caller = Depends(require_callers("analytics")),
):
    """Fuente para analítica: sin client_id, sin dirección, sin datos personales."""
    start = datetime.fromisoformat(date_from)
    end = datetime.fromisoformat(date_to) + timedelta(days=1)

    def run():
        with db().connect() as conn:
            cond = (orders.c.created_at >= start, orders.c.created_at < end)
            rows = conn.execute(paginate(select(orders.c.id, orders.c.status, orders.c.delivery_type,
                                                orders.c.total_clp, orders.c.created_at)
                                         .where(*cond).order_by(orders.c.id), page, page_size)).all()
            items = load_items(conn, [r.id for r in rows])
            return {"page": page, "has_more": len(rows) == page_size, "items": [{
                "status": r.status, "delivery_type": r.delivery_type, "total_clp": r.total_clp,
                "date": r.created_at.date().isoformat(),
                "lines": [{"product_id": i.product_id, "product_name": i.product_name,
                           "quantity": i.quantity, "line_total_clp": i.unit_price_clp * i.quantity} for i in items[r.id]],
            } for r in rows]}
    return await run_in_threadpool(run)
