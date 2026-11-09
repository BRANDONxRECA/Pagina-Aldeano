"""payments (microservicio privado). Autoridad sobre intentos de pago, avisos del
proveedor y boletas (nonna_payments).

Reglas de seguridad:
- El monto SIEMPRE viene de orders (total oficial), nunca del navegador.
- Creación idempotente: cabecera Idempotency-Key obligatoria (UNIQUE en BD).
- El cambio a AUTORIZADO solo ocurre por:
    a) aviso del proveedor con firma HMAC-SHA256 válida (secreto ``payments-webhook-secret``)
       y monto/tokens coincidentes, o
    b) confirmación manual de un TRABAJADOR/ADMIN para EFECTIVO o TRANSFERENCIA.
- Cada aviso se procesa una sola vez (provider_event_id UNIQUE). Un aviso repetido
  solo reintenta sincronizar el pedido, sin duplicar efectos.
- La clave del comercio (``provider-api-key``) vive solo en este servicio.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as pysecrets

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from common.db import get_engine
from common.secrets import get_secret
from common.service import (
    ApiError, Caller, DependencyError, UserCtx, call_external, call_service, create_app,
    expect_ok, get_logger, require_callers, require_user,
)
from common.tables import payment_events, payments, receipts

app = create_app("payments")
log = get_logger("payments")
PROVIDER_URL = os.environ.get("PROVIDER_URL", "http://127.0.0.1:8009").rstrip("/")


def db():
    return get_engine("payments")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaymentIn(Strict):
    order_code: str = Field(pattern=r"^P-\d{3,10}$")
    method: str = Field(pattern="^(WEBPAY|TRANSFERENCIA|EFECTIVO)$")


class ProviderEvent(Strict):
    event_id: str = Field(min_length=6, max_length=120)
    token: str = Field(min_length=6, max_length=120)
    result: str = Field(pattern="^(AUTHORIZED|REJECTED)$")
    amount: int = Field(gt=0)


def payment_dto(row, receipt_number: str | None = None) -> dict:
    return {"id": row.id, "order_id": row.order_id, "amount_clp": row.amount_clp, "method": row.method,
            "status": row.status, "receipt_number": receipt_number, "created_at": row.created_at.isoformat()}


def receipt_for(conn, payment_id: int) -> str | None:
    return conn.execute(select(receipts.c.receipt_number).where(receipts.c.payment_id == payment_id)).scalar_one_or_none()


def issue_receipt(conn, payment_id: int) -> str:
    number = receipt_for(conn, payment_id)
    if number:
        return number
    number = f"B-{payment_id:06d}"
    try:
        conn.execute(insert(receipts).values(payment_id=payment_id, receipt_number=number))
    except IntegrityError:
        pass  # otra ejecución concurrente ya la emitió
    return number


async def sync_order_paid(pay_row) -> dict:
    """Pide a orders el cambio a PAGADO (idempotente en orders)."""
    resp = await call_service("orders", "POST", f"/internal/orders/{pay_row.order_id}/mark-paid",
                              json_body={"payment_id": pay_row.id, "amount_clp": pay_row.amount_clp})
    if resp.status_code == 409:
        log.warning("payment_needs_refund", extra={"fields": {"payment_id": pay_row.id, "order_id": pay_row.order_id}})
        return {"order_synced": False, "requires_refund": True}
    expect_ok(resp, "orders")
    return {"order_synced": True}


# -------------------------------------------------- API (vía API Gateway)
@app.post("/payments", status_code=201)
async def create_payment(
    body: PaymentIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    user: UserCtx = Depends(require_user("CLIENTE")),
):
    client = expect_ok(await call_service("clients", "GET", f"/internal/clients/by-user/{user.user_id}"), "clients")
    key = f"{client['id']}:{idempotency_key}"[:64]

    def existing_by_key():
        with db().connect() as conn:
            row = conn.execute(select(payments).where(payments.c.idempotency_key == key)).first()
            return row and (row, receipt_for(conn, row.id))
    found = await run_in_threadpool(existing_by_key)
    if found:
        return payment_dto(*found) | {"idempotent": True}

    order = expect_ok(await call_service("orders", "GET", f"/internal/orders/by-code/{body.order_code}"), "orders")
    if order["client_id"] != client["id"]:
        raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
    if order["status"] != "PENDIENTE_PAGO":
        raise ApiError(409, "ORDER_NOT_PAYABLE", f"El pedido está {order['status']}")

    def open_payment():
        with db().connect() as conn:
            return conn.execute(select(payments).where(payments.c.order_id == order["id"],
                                                       payments.c.status.in_(("INICIADO", "AUTORIZADO")))).first()
    if await run_in_threadpool(open_payment):
        raise ApiError(409, "PAYMENT_IN_PROGRESS", "El pedido ya tiene un pago en curso")

    provider_token, redirect_url = None, None
    if body.method == "WEBPAY":
        resp = await call_external("provider", "POST", f"{PROVIDER_URL}/transactions",
                                   headers={"X-Api-Key": get_secret("provider-api-key")},
                                   json={"buy_order": body.order_code, "amount": order["total_clp"]})
        data = expect_ok(resp, "provider")
        provider_token, redirect_url = data["token"], data["url"]

    def insert_payment():
        with db().begin() as conn:
            try:
                pid = conn.execute(insert(payments).values(
                    order_id=order["id"], client_id=client["id"], amount_clp=order["total_clp"],
                    method=body.method, provider="WEBPAY_TEST" if body.method == "WEBPAY" else "MANUAL",
                    provider_token=provider_token, status="INICIADO", idempotency_key=key)).inserted_primary_key[0]
            except IntegrityError:
                raise ApiError(409, "DUPLICATE_REQUEST", "Solicitud de pago duplicada")
            return conn.execute(select(payments).where(payments.c.id == pid)).first()
    row = await run_in_threadpool(insert_payment)
    dto = payment_dto(row)
    if redirect_url:
        dto["redirect_url"] = redirect_url  # el token de transacción no es la clave del comercio
    else:
        dto["instructions"] = "Pago pendiente de confirmación por el personal del local"
    return dto


@app.get("/payments/{payment_id}")
async def get_payment(payment_id: int, user: UserCtx = Depends(require_user())):
    client_id = None
    if not user.is_staff:
        client_id = expect_ok(await call_service("clients", "GET", f"/internal/clients/by-user/{user.user_id}"), "clients")["id"]

    def run():
        with db().connect() as conn:
            row = conn.execute(select(payments).where(payments.c.id == payment_id)).first()
            if row is None or (client_id is not None and row.client_id != client_id):
                raise ApiError(404, "PAYMENT_NOT_FOUND", "Pago no encontrado")
            return payment_dto(row, receipt_for(conn, row.id))
    return await run_in_threadpool(run)


@app.post("/payments/{payment_id}/confirm-manual")
async def confirm_manual(payment_id: int, staff: UserCtx = Depends(require_user("TRABAJADOR", "ADMIN"))):
    def run():
        with db().begin() as conn:
            row = conn.execute(select(payments).where(payments.c.id == payment_id).with_for_update()).first()
            if row is None:
                raise ApiError(404, "PAYMENT_NOT_FOUND", "Pago no encontrado")
            if row.method == "WEBPAY":
                raise ApiError(409, "PROVIDER_PAYMENT", "Los pagos Webpay solo los confirma el proveedor")
            if row.status not in ("INICIADO", "AUTORIZADO"):
                raise ApiError(409, "PAYMENT_STATE", f"El pago está {row.status}")
            conn.execute(update(payments).where(payments.c.id == payment_id).values(status="AUTORIZADO"))
            return conn.execute(select(payments).where(payments.c.id == payment_id)).first()
    row = await run_in_threadpool(run)
    sync = await sync_order_paid(row)

    def finish():
        with db().begin() as conn:
            return issue_receipt(conn, row.id) if sync["order_synced"] else None
    number = await run_in_threadpool(finish)
    log.info("manual_payment_confirmed", extra={"fields": {"payment_id": payment_id, "by": staff.user_id}})
    return payment_dto(row, number) | sync


@app.post("/payments/webhook")
async def provider_webhook(
    request: Request,
    signature: str = Header("", alias="X-Provider-Signature", max_length=128),
    _: Caller = Depends(require_callers("api-gateway")),
):
    raw = await request.body()
    expected = hmac.new(get_secret("payments-webhook-secret").encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        log.warning("webhook_bad_signature")
        raise ApiError(401, "INVALID_SIGNATURE", "Firma del proveedor inválida")
    try:
        event = ProviderEvent.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        raise ApiError(400, "INVALID_EVENT", "Aviso del proveedor inválido")
    digest = hashlib.sha256(raw).hexdigest()

    def process():
        with db().begin() as conn:
            pay = conn.execute(select(payments).where(payments.c.provider_token == event.token).with_for_update()).first()
            if pay is None:
                raise ApiError(404, "PAYMENT_NOT_FOUND", "Pago no encontrado")
            if event.amount != pay.amount_clp:
                raise ApiError(400, "AMOUNT_MISMATCH", "El monto informado no coincide")
            try:
                with conn.begin_nested():
                    conn.execute(insert(payment_events).values(payment_id=pay.id, provider_event_id=event.event_id,
                                                               signature_valid=True, payload_sha256=digest))
            except IntegrityError:
                return pay, True  # aviso repetido: no se vuelve a aplicar
            if pay.status == "INICIADO":
                new_status = "AUTORIZADO" if event.result == "AUTHORIZED" else "RECHAZADO"
                conn.execute(update(payments).where(payments.c.id == pay.id).values(status=new_status))
            return conn.execute(select(payments).where(payments.c.id == pay.id)).first(), False

    pay, duplicate = await run_in_threadpool(process)
    result = {"payment_id": pay.id, "status": pay.status, "duplicate": duplicate}
    if pay.status == "AUTORIZADO":
        try:
            result |= await sync_order_paid(pay)
        except DependencyError:
            # El proveedor reintentará el aviso; el reintento solo vuelve a sincronizar.
            raise ApiError(503, "ORDER_SYNC_PENDING", "Pago registrado; sincronización pendiente")
        if result.get("order_synced"):
            def finish():
                with db().begin() as conn:
                    return issue_receipt(conn, pay.id)
            result["receipt_number"] = await run_in_threadpool(finish)
    return result


# ------------------------------------------------ API interna (servicios)
@app.get("/internal/payments")
async def internal_by_orders(order_ids: str = Query(..., max_length=800), _: Caller = Depends(require_callers("graphql"))):
    """Lote para GraphQL: último pago de cada pedido con su boleta."""
    try:
        ids = sorted({int(x) for x in order_ids.split(",") if x})[:100]
    except ValueError:
        raise ApiError(400, "INVALID_IDS", "ids inválidos")

    def run():
        with db().connect() as conn:
            rows = conn.execute(select(payments, receipts.c.receipt_number)
                                .outerjoin(receipts, receipts.c.payment_id == payments.c.id)
                                .where(payments.c.order_id.in_(ids)).order_by(payments.c.id)).all()
            latest = {}
            for r in rows:
                latest[r.order_id] = {"order_id": r.order_id, "status": r.status, "method": r.method,
                                      "amount_clp": r.amount_clp, "receipt_number": r.receipt_number}
            return list(latest.values())
    return await run_in_threadpool(run)
