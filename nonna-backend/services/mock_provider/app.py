"""Adaptador de prueba del proveedor de pagos (estilo Webpay, ambiente de integración).

NO es parte del backend propio: simula al proveedor EXTERNO para poder probar el flujo
completo sin una cuenta real. Preserva el contrato:
  - POST /transactions  (exige la clave del comercio en X-Api-Key) -> token + url de pago
  - GET  /pay/{token}?result=AUTHORIZED|REJECTED  simula que el cliente paga y envía
    el aviso firmado (HMAC-SHA256) al webhook público del API Gateway.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as pysecrets

from fastapi import Header, Query
from pydantic import BaseModel

from common.secrets import get_secret
from common.service import ApiError, call_external, create_app

app = create_app("provider")
WEBHOOK_URL = os.environ.get("PROVIDER_WEBHOOK_URL", "http://127.0.0.1:8000/api/v1/payments/webhook")
PUBLIC_URL = os.environ.get("PROVIDER_PUBLIC_URL", "http://127.0.0.1:8009").rstrip("/")
_transactions: dict[str, dict] = {}


class TransactionIn(BaseModel):
    buy_order: str
    amount: int


def sign(raw: bytes) -> str:
    return hmac.new(get_secret("payments-webhook-secret").encode(), raw, hashlib.sha256).hexdigest()


@app.post("/transactions", status_code=201)
async def create_transaction(body: TransactionIn, api_key: str = Header("", alias="X-Api-Key")):
    if not hmac.compare_digest(api_key, get_secret("provider-api-key")):
        raise ApiError(401, "INVALID_COMMERCE_KEY", "Clave de comercio inválida")
    token = "tok_" + pysecrets.token_hex(16)
    _transactions[token] = {"buy_order": body.buy_order, "amount": body.amount, "events": 0}
    return {"token": token, "url": f"{PUBLIC_URL}/pay/{token}"}


@app.get("/pay/{token}")
async def pay(token: str, result: str = Query("AUTHORIZED", pattern="^(AUTHORIZED|REJECTED)$"), resend: bool = False):
    tx = _transactions.get(token)
    if tx is None:
        raise ApiError(404, "UNKNOWN_TOKEN", "Transacción desconocida")
    if not resend:
        tx["events"] += 1
    event = {"event_id": f"evt_{token[4:16]}_{tx['events']}", "token": token, "result": result, "amount": tx["amount"]}
    raw = json.dumps(event).encode()
    resp = await call_external("gateway", "POST", WEBHOOK_URL, content=raw,
                               headers={"Content-Type": "application/json", "X-Provider-Signature": sign(raw)})
    return {"sent": event, "webhook_status": resp.status_code, "webhook_response": resp.json()}
