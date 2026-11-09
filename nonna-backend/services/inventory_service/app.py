"""inventory (microservicio privado). Autoridad sobre catálogo, precios, stock y reservas.

- El catálogo es dato PÚBLICO, pero el stock exacto no se publica: el público solo ve
  ``available`` (bool). El personal ve cantidades en /admin/stock.
- El precio oficial vive solo aquí. orders lo consulta; el navegador nunca lo dicta.
- Reservas: orders reserva al crear el pedido; payments->orders confirma al pagar;
  si el pago no llega antes de ``expires_at`` la reserva expira y el stock vuelve.
- DELETE de producto = desactivación lógica (active=0): los pedidos antiguos lo referencian.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from common.db import get_engine
from common.service import ApiError, Caller, UserCtx, create_app, get_logger, require_callers, require_user
from common.tables import categories, products, stock, stock_reservations

app = create_app("inventory")
log = get_logger("inventory")
RESERVATION_MINUTES = int(os.environ.get("RESERVATION_MINUTES", "15"))


def db():
    return get_engine("inventory")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductIn(Strict):
    category_id: int = Field(gt=0)
    sku: str = Field(pattern=r"^[A-Z0-9-]{3,30}$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=255)
    price_clp: int = Field(gt=0, le=1_000_000)


class ProductCreateIn(ProductIn):
    initial_stock: int = Field(default=0, ge=0, le=100_000)


class ProductPutIn(ProductIn):
    active: bool = True


class StockIn(Strict):
    quantity_available: int = Field(ge=0, le=100_000)


class ReservationItem(Strict):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=50)


class ReservationIn(Strict):
    order_id: int = Field(gt=0)
    items: list[ReservationItem] = Field(min_length=1, max_length=30)


def catalog_query():
    return (select(products.c.id, products.c.name, products.c.description, products.c.price_clp,
                   products.c.active, categories.c.name.label("category"),
                   stock.c.quantity_available)
            .join(categories, categories.c.id == products.c.category_id)
            .join(stock, stock.c.product_id == products.c.id))


def public_dto(r) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "category": r.category,
            "price_clp": r.price_clp, "available": bool(r.active) and r.quantity_available > 0}


def _expire_reservations(conn) -> int:
    """Recuperación de stock: libera reservas ACTIVAS vencidas."""
    expired = conn.execute(select(stock_reservations).where(
        stock_reservations.c.status == "ACTIVA", stock_reservations.c.expires_at < now()).with_for_update()).all()
    for r in expired:
        conn.execute(update(stock).where(stock.c.product_id == r.product_id).values(
            quantity_available=stock.c.quantity_available + r.quantity,
            quantity_reserved=stock.c.quantity_reserved - r.quantity))
        conn.execute(update(stock_reservations).where(stock_reservations.c.id == r.id).values(status="EXPIRADA"))
    return len(expired)


# ------------------------------------------------- API pública (catálogo)
@app.get("/products")
async def list_products(
    category: str | None = Query(None, max_length=60),
    available: bool | None = None,
    q: str | None = Query(None, min_length=2, max_length=60),
    page: int = Query(1, ge=1, le=1000), page_size: int = Query(50, ge=1, le=100),
    _: Caller = Depends(require_callers("api-gateway")),
):
    def run():
        stmt = catalog_query().where(products.c.active.is_(True))
        if category:
            stmt = stmt.where(categories.c.name == category)
        if available is True:
            stmt = stmt.where(stock.c.quantity_available > 0)
        elif available is False:
            stmt = stmt.where(stock.c.quantity_available == 0)
        if q:
            stmt = stmt.where(products.c.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(products.c.id).limit(page_size).offset((page - 1) * page_size)
        with db().connect() as conn:
            return [public_dto(r) for r in conn.execute(stmt).all()]
    return await run_in_threadpool(run)


@app.get("/products/{product_id}")
async def get_product(product_id: int, _: Caller = Depends(require_callers("api-gateway"))):
    def run():
        with db().connect() as conn:
            r = conn.execute(catalog_query().where(products.c.id == product_id, products.c.active.is_(True))).first()
            if r is None:
                raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
            return public_dto(r)
    return await run_in_threadpool(run)


@app.get("/categories")
async def list_categories(_: Caller = Depends(require_callers("api-gateway"))):
    def run():
        with db().connect() as conn:
            return [{"id": r.id, "name": r.name} for r in conn.execute(select(categories).order_by(categories.c.id)).all()]
    return await run_in_threadpool(run)


# ---------------------------------------------- administración del catálogo
@app.post("/products", status_code=201)
async def create_product(body: ProductCreateIn, admin: UserCtx = Depends(require_user("ADMIN"))):
    def run():
        with db().begin() as conn:
            if conn.execute(select(categories.c.id).where(categories.c.id == body.category_id)).first() is None:
                raise ApiError(422, "CATEGORY_NOT_FOUND", "La categoría no existe")
            try:
                pid = conn.execute(insert(products).values(**body.model_dump(exclude={"initial_stock"}))).inserted_primary_key[0]
            except IntegrityError:
                raise ApiError(409, "SKU_TAKEN", "Ya existe un producto con ese SKU")
            conn.execute(insert(stock).values(product_id=pid, quantity_available=body.initial_stock, quantity_reserved=0))
            return public_dto(conn.execute(catalog_query().where(products.c.id == pid)).first())
    result = await run_in_threadpool(run)
    log.info("product_created", extra={"fields": {"by": admin.user_id, "product_id": result["id"]}})
    return result


@app.put("/products/{product_id}")
async def put_product(product_id: int, body: ProductPutIn, admin: UserCtx = Depends(require_user("ADMIN"))):
    def run():
        with db().begin() as conn:
            if conn.execute(select(products.c.id).where(products.c.id == product_id)).first() is None:
                raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
            try:
                conn.execute(update(products).where(products.c.id == product_id).values(**body.model_dump()))
            except IntegrityError:
                raise ApiError(409, "SKU_TAKEN", "Ya existe un producto con ese SKU o la categoría no existe")
            return public_dto(conn.execute(catalog_query().where(products.c.id == product_id)).first())
    return await run_in_threadpool(run)


@app.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: int, admin: UserCtx = Depends(require_user("ADMIN"))):
    def run():
        with db().begin() as conn:
            res = conn.execute(update(products).where(products.c.id == product_id, products.c.active.is_(True)).values(active=False))
            if res.rowcount == 0:
                raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
    await run_in_threadpool(run)
    log.info("product_deactivated", extra={"fields": {"by": admin.user_id, "product_id": product_id}})


@app.put("/products/{product_id}/stock")
async def put_stock(product_id: int, body: StockIn, user: UserCtx = Depends(require_user("ADMIN", "TRABAJADOR"))):
    def run():
        with db().begin() as conn:
            res = conn.execute(update(stock).where(stock.c.product_id == product_id).values(quantity_available=body.quantity_available))
            if res.rowcount == 0:
                raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
            r = conn.execute(select(stock).where(stock.c.product_id == product_id)).first()
            return {"product_id": product_id, "quantity_available": r.quantity_available, "quantity_reserved": r.quantity_reserved}
    return await run_in_threadpool(run)


@app.get("/admin/stock")
async def admin_stock(_: UserCtx = Depends(require_user("ADMIN", "TRABAJADOR"))):
    def run():
        stmt = (select(products.c.id, products.c.sku, products.c.name, products.c.active,
                       stock.c.quantity_available, stock.c.quantity_reserved)
                .join(stock, stock.c.product_id == products.c.id).order_by(products.c.id))
        with db().connect() as conn:
            return [dict(r._mapping) | {"active": bool(r.active)} for r in conn.execute(stmt).all()]
    return await run_in_threadpool(run)


# ----------------------------------------------- API interna (servicios)
@app.get("/internal/products")
async def internal_products(ids: str = Query(..., max_length=800), _: Caller = Depends(require_callers("orders", "graphql"))):
    """Lote por ids. Incluye productos desactivados (historial) con su estado."""
    try:
        id_list = sorted({int(x) for x in ids.split(",") if x})[:100]
    except ValueError:
        raise ApiError(400, "INVALID_IDS", "ids inválidos")

    def run():
        with db().connect() as conn:
            rows = conn.execute(catalog_query().where(products.c.id.in_(id_list))).all()
            return [public_dto(r) | {"active": bool(r.active)} for r in rows]
    return await run_in_threadpool(run)


@app.post("/internal/reservations", status_code=201)
async def reserve(body: ReservationIn, _: Caller = Depends(require_callers("orders"))):
    """Reserva atómica: o se reservan todas las líneas o ninguna. Idempotente por order_id."""
    merged: dict[int, int] = {}
    for it in body.items:
        merged[it.product_id] = merged.get(it.product_id, 0) + it.quantity

    def run():
        with db().begin() as conn:
            _expire_reservations(conn)
            existing = conn.execute(select(stock_reservations).where(stock_reservations.c.order_id == body.order_id)).all()
            if existing:
                return {"order_id": body.order_id, "status": existing[0].status,
                        "expires_at": existing[0].expires_at.isoformat(), "idempotent": True}
            # Bloqueo en orden de product_id para evitar interbloqueos.
            rows = conn.execute(select(stock.c.product_id, stock.c.quantity_available, products.c.active)
                                .join(products, products.c.id == stock.c.product_id)
                                .where(stock.c.product_id.in_(sorted(merged)))
                                .order_by(stock.c.product_id).with_for_update()).all()
            found = {r.product_id: r for r in rows}
            problems = []
            for pid, qty in merged.items():
                r = found.get(pid)
                if r is None or not r.active:
                    problems.append({"product_id": pid, "reason": "NO_DISPONIBLE"})
                elif r.quantity_available < qty:
                    problems.append({"product_id": pid, "reason": "STOCK_INSUFICIENTE", "available": r.quantity_available})
            if problems:
                raise ApiError(409, "OUT_OF_STOCK", "No hay stock suficiente para el pedido", {"items": problems})
            expires = now() + timedelta(minutes=RESERVATION_MINUTES)
            for pid, qty in merged.items():
                res = conn.execute(update(stock).where(stock.c.product_id == pid, stock.c.quantity_available >= qty).values(
                    quantity_available=stock.c.quantity_available - qty,
                    quantity_reserved=stock.c.quantity_reserved + qty))
                if res.rowcount != 1:  # defensa ante carrera en motores sin FOR UPDATE
                    raise ApiError(409, "OUT_OF_STOCK", "No hay stock suficiente para el pedido")
                conn.execute(insert(stock_reservations).values(order_id=body.order_id, product_id=pid, quantity=qty, expires_at=expires))
            return {"order_id": body.order_id, "status": "ACTIVA", "expires_at": expires.isoformat(), "idempotent": False}
    return await run_in_threadpool(run)


def _transition(order_id: int, target: str) -> dict:
    with db().begin() as conn:
        rows = conn.execute(select(stock_reservations).where(stock_reservations.c.order_id == order_id).with_for_update()).all()
        if not rows:
            raise ApiError(404, "RESERVATION_NOT_FOUND", "No hay reserva para el pedido")
        changed = 0
        for r in rows:
            if r.status == target:
                continue  # idempotente
            if r.status != "ACTIVA":
                raise ApiError(409, "RESERVATION_STATE", f"La reserva está {r.status}")
            values = {"quantity_reserved": stock.c.quantity_reserved - r.quantity}
            if target == "LIBERADA":
                values["quantity_available"] = stock.c.quantity_available + r.quantity
            conn.execute(update(stock).where(stock.c.product_id == r.product_id).values(**values))
            conn.execute(update(stock_reservations).where(stock_reservations.c.id == r.id).values(status=target))
            changed += 1
        return {"order_id": order_id, "status": target, "changed": changed}


@app.post("/internal/reservations/{order_id}/confirm")
async def confirm(order_id: int, _: Caller = Depends(require_callers("orders"))):
    return await run_in_threadpool(_transition, order_id, "CONFIRMADA")


@app.post("/internal/reservations/{order_id}/release")
async def release(order_id: int, _: Caller = Depends(require_callers("orders"))):
    return await run_in_threadpool(_transition, order_id, "LIBERADA")


@app.post("/internal/reservations/expire")
async def expire(_: Caller = Depends(require_callers("orders"))):
    def run():
        with db().begin() as conn:
            return {"expired": _expire_reservations(conn)}
    return await run_in_threadpool(run)
