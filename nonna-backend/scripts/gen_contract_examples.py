"""Genera docs/contratos-ejemplos.md ejecutando cada servicio S01..S31 contra el sistema
real (en proceso, con SQLite y datos ficticios). Así los ejemplos JSON del Módulo 1 son
evidencia de ejecución, no texto inventado.

    python scripts/gen_contract_examples.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from tests import conftest as env  # noqa: E402  (levanta todo con bases temporales)
from common.secrets import get_secret  # noqa: E402

OUT = ROOT / "docs" / "contratos-ejemplos.md"
examples: list[dict] = []


def trim(value, depth=0):
    if isinstance(value, list):
        return [trim(v, depth + 1) for v in value[:2]] + (["…"] if len(value) > 2 else [])
    if isinstance(value, dict):
        return {k: ("<jwt>" if k == "access_token" else "<token opaco>" if k == "refresh_token" else trim(v, depth + 1))
                for k, v in value.items()}
    return value


async def call(api, sid, title, method, path, *, role=None, headers=None, json_body=None, params=None, content=None):
    h = dict(headers or {})
    r = await api.request(method, path, headers=h, json=json_body, params=params, content=content)
    try:
        body = r.json() if r.content else None
    except ValueError:
        body = r.text
    shown_headers = {k: ("Bearer <jwt>" if k == "Authorization" else v) for k, v in h.items()}
    examples.append({"id": sid, "title": title, "method": method, "path": path + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""),
                     "role": role, "headers": shown_headers, "request": json_body if content is None else json.loads(content),
                     "status": r.status_code, "response": trim(body)})
    return r


async def main():
    env.limiter.hits.clear()
    transport = httpx.ASGITransport(app=env.gateway_app, client=("203.0.113.10", 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://api-gateway.internal") as api:
        def bearer(tok):
            return {"Authorization": f"Bearer {tok}"}

        await call(api, "S01", "Registrar cliente", "POST", "/api/v1/auth/register", role="Visitante", json_body={
            "email": "camila@example.cl", "password": "Pasta2026", "first_name": "Camila", "last_name": "Rojas",
            "phone": "+56944444444", "run": "12345678-5"})
        r = await call(api, "S02", "Iniciar sesión", "POST", "/api/v1/auth/login", role="Visitante",
                       json_body={"email": "javiera@example.cl", "password": "Cliente123"})
        jav = r.json()
        await call(api, "S02", "Iniciar sesión (error)", "POST", "/api/v1/auth/login", role="Visitante",
                   json_body={"email": "javiera@example.cl", "password": "incorrecta1"})
        r = await call(api, "S03", "Renovar sesión", "POST", "/api/v1/auth/refresh", role="Cliente", json_body={"refresh_token": "<refresh_token>"})
        examples.pop()
        r = await api.post("/api/v1/auth/refresh", json={"refresh_token": jav["refresh_token"]})
        examples.append({"id": "S03", "title": "Renovar sesión (rota el refresh token)", "method": "POST", "path": "/api/v1/auth/refresh",
                         "role": "Cliente", "headers": {}, "request": {"refresh_token": "<token opaco>"}, "status": r.status_code, "response": trim(r.json())})
        jav = r.json()
        J = bearer(jav["access_token"])
        await call(api, "S05", "Usuario actual", "GET", "/api/v1/auth/me", role="Cliente", headers=J)
        adm = (await api.post("/api/v1/auth/login", json={"email": "admin@lanonna.test", "password": "Admin12345"})).json()
        A = bearer(adm["access_token"])
        coc = (await api.post("/api/v1/auth/login", json={"email": "cocina@lanonna.test", "password": "Trabajador123"})).json()
        K = bearer(coc["access_token"])
        await call(api, "S06", "Crear trabajador", "POST", "/api/v1/admin/staff", role="Admin", headers=A, json_body={
            "email": "despacho@lanonna.test", "password": "Despacho2026", "first_name": "Luis", "last_name": "Vera",
            "position": "Despacho", "role": "TRABAJADOR"})

        await call(api, "S07", "Consultar catálogo", "GET", "/api/v1/products", role="Visitante", params={"available": "true", "category": "Lasañas"})
        await call(api, "S08", "Consultar producto", "GET", "/api/v1/products/4", role="Visitante")
        await call(api, "S09", "Listar categorías", "GET", "/api/v1/categories", role="Visitante")
        r = await call(api, "S10", "Crear producto", "POST", "/api/v1/products", role="Admin", headers=A, json_body={
            "category_id": 3, "sku": "TAL-ALFR", "name": "Fettuccine Alfredo", "description": "Crema y parmesano.", "price_clp": 7900, "initial_stock": 15})
        pid = r.json()["id"]
        await call(api, "S11", "Reemplazar producto", "PUT", f"/api/v1/products/{pid}", role="Admin", headers=A, json_body={
            "category_id": 3, "sku": "TAL-ALFR", "name": "Fettuccine Alfredo", "description": "Crema, mantequilla y parmesano.", "price_clp": 8200, "active": True})
        await call(api, "S12", "Desactivar producto", "DELETE", f"/api/v1/products/{pid}", role="Admin", headers=A)
        await call(api, "S12", "Desactivar producto (cliente: denegado)", "DELETE", "/api/v1/products/1", role="Cliente", headers=J)
        await call(api, "S13", "Fijar stock", "PUT", "/api/v1/products/7/stock", role="Trabajador", headers=K, json_body={"quantity_available": 45})
        await call(api, "S14", "Consultar stock", "GET", "/api/v1/admin/stock", role="Trabajador", headers=K)

        await call(api, "S15", "Ver perfil", "GET", "/api/v1/me", role="Cliente", headers=J)
        await call(api, "S16", "Reemplazar perfil", "PUT", "/api/v1/me", role="Cliente", headers=J, json_body={
            "first_name": "Javiera", "last_name": "Rojas", "phone": "+56911111111", "notify_email": False})
        await call(api, "S17", "Listar direcciones", "GET", "/api/v1/me/addresses", role="Cliente", headers=J)
        r = await call(api, "S18", "Agregar dirección", "POST", "/api/v1/me/addresses", role="Cliente", headers=J, json_body={
            "street": "Av. Pajaritos 1500", "commune": "Maipú", "reference": "Depto 302", "is_default": False})
        aid = r.json()["id"]
        await call(api, "S19", "Reemplazar dirección", "PUT", f"/api/v1/me/addresses/{aid}", role="Cliente", headers=J, json_body={
            "street": "Av. Pajaritos 1500", "commune": "Maipú", "reference": "Depto 303", "is_default": True})
        await call(api, "S20", "Listar clientes (admin)", "GET", "/api/v1/admin/clients", role="Admin", headers=A, params={"page": 1, "page_size": 2})

        r = await call(api, "S21", "Crear pedido", "POST", "/api/v1/orders", role="Cliente", headers=J, json_body={
            "items": [{"product_id": 4, "quantity": 1}, {"product_id": 7, "quantity": 2}], "delivery_type": "DESPACHO", "address_id": aid})
        code = r.json()["order_code"]
        await call(api, "S21", "Crear pedido (precio enviado por el navegador: rechazado)", "POST", "/api/v1/orders", role="Cliente", headers=J, json_body={
            "items": [{"product_id": 4, "quantity": 1, "unit_price_clp": 10}], "delivery_type": "RETIRO"})
        await call(api, "S22", "Listar pedidos", "GET", "/api/v1/orders", role="Cliente", headers=J, params={"page": 1, "page_size": 2})
        await call(api, "S23", "Ver pedido", "GET", f"/api/v1/orders/{code}", role="Cliente", headers=J)
        await call(api, "S23", "Ver pedido ajeno (denegado)", "GET", "/api/v1/orders/P-1093", role="Cliente", headers=J)

        r = await call(api, "S27", "Iniciar pago Webpay", "POST", "/api/v1/payments", role="Cliente",
                       headers=J | {"Idempotency-Key": "pago-ejemplo-0001"}, json_body={"order_code": code, "method": "WEBPAY"})
        pay = r.json()
        token = pay["redirect_url"].rsplit("/", 1)[1]
        event = json.dumps({"event_id": "evt_ejemplo_0001", "token": token, "result": "AUTHORIZED", "amount": pay["amount_clp"]}).encode()
        sig = hmac.new(get_secret("payments-webhook-secret").encode(), event, hashlib.sha256).hexdigest()
        await call(api, "S30", "Aviso del proveedor (firma válida)", "POST", "/api/v1/payments/webhook", role="Proveedor",
                   headers={"Content-Type": "application/json", "X-Provider-Signature": "<hmac-sha256 hex>"}, content=event)
        examples.pop()
        r = await api.post("/api/v1/payments/webhook", content=event, headers={"Content-Type": "application/json", "X-Provider-Signature": sig})
        examples.append({"id": "S30", "title": "Aviso del proveedor (firma válida)", "method": "POST", "path": "/api/v1/payments/webhook",
                         "role": "Proveedor", "headers": {"Content-Type": "application/json", "X-Provider-Signature": "<hmac-sha256 hex>"},
                         "request": json.loads(event) | {"token": "<token de transacción>"}, "status": r.status_code, "response": r.json()})
        await call(api, "S30", "Aviso falso (sin firma)", "POST", "/api/v1/payments/webhook", role="Atacante",
                   headers={"Content-Type": "application/json"}, content=event)
        examples[-1]["request"]["token"] = "<token de transacción>"
        await call(api, "S28", "Ver pago", "GET", f"/api/v1/payments/{pay['id']}", role="Cliente", headers=J)
        await call(api, "S24", "Cambiar estado (cocina)", "PATCH", f"/api/v1/orders/{code}/status", role="Trabajador", headers=K, json_body={"status": "PREPARANDO"})
        await call(api, "S24", "Cambiar estado (cliente marca PAGADO: denegado)", "PATCH", f"/api/v1/orders/{code}/status", role="Cliente", headers=J, json_body={"status": "PAGADO"})

        r = await api.post("/api/v1/orders", headers=J, json={"items": [{"product_id": 9, "quantity": 1}], "delivery_type": "RETIRO"})
        code2 = r.json()["order_code"]
        r = await api.post("/api/v1/payments", headers=J | {"Idempotency-Key": "pago-ejemplo-0002"}, json={"order_code": code2, "method": "EFECTIVO"})
        await call(api, "S29", "Confirmar pago en efectivo", "POST", f"/api/v1/payments/{r.json()['id']}/confirm-manual", role="Trabajador", headers=K)
        r = await api.post("/api/v1/orders", headers=J, json={"items": [{"product_id": 8, "quantity": 1}], "delivery_type": "RETIRO"})
        await call(api, "S25", "Anular pedido", "POST", f"/api/v1/orders/{r.json()['order_code']}/cancel", role="Cliente", headers=J)
        await call(api, "S26", "Vencer pedidos impagos", "POST", "/api/v1/admin/orders/expire-pending", role="Admin", headers=A)
        await call(api, "S31", "GraphQL misPedidos", "POST", "/api/v1/graphql", role="Cliente", headers=J, json_body={
            "query": "query($p:Int!,$t:Int!){ misPedidos(pagina:$p,tamano:$t){ total items { codigo estado total pago { estado numeroBoleta } items { nombre cantidad productoActual { precio disponible } } } } }",
            "variables": {"p": 1, "t": 2}})
        await call(api, "S04", "Cerrar sesión", "POST", "/api/v1/auth/logout", role="Cliente", json_body={"refresh_token": "<token opaco>"})
        examples.pop()
        r = await api.post("/api/v1/auth/logout", json={"refresh_token": jav["refresh_token"]})
        examples.append({"id": "S04", "title": "Cerrar sesión (revoca el refresh token)", "method": "POST", "path": "/api/v1/auth/logout",
                         "role": "Cliente", "headers": {}, "request": {"refresh_token": "<token opaco>"}, "status": r.status_code, "response": None})

    examples.sort(key=lambda e: e["id"])
    lines = ["# Módulo 1 — Ejemplos de contratos (generados por ejecución)", "",
             "Generado con `python scripts/gen_contract_examples.py` contra el sistema real con datos **ficticios**. "
             "Tokens y firmas reemplazados por `<...>`; listas largas recortadas con `…`.", ""]
    for e in examples:
        lines += [f"### {e['id']} · {e['title']}", "",
                  f"`{e['method']} {e['path']}` · actor: **{e['role']}** · respuesta **{e['status']}**", ""]
        if e["headers"]:
            lines += ["Cabeceras: " + ", ".join(f"`{k}: {v}`" for k, v in e["headers"].items()), ""]
        if e["request"] is not None:
            lines += ["Solicitud:", "```json", json.dumps(e["request"], ensure_ascii=False, indent=2), "```"]
        lines += ["Respuesta:", "```json", json.dumps(e["response"], ensure_ascii=False, indent=2) if e["response"] is not None else "(sin cuerpo)", "```", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(examples)} ejemplos -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
