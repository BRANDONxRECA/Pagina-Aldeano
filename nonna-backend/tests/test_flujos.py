"""Flujos principales del caso (Módulo 10): registro, catálogo, pedido, pago, cocina."""
import uuid

import pytest

from tests.conftest import auth, login, provider_pay

pytestmark = pytest.mark.anyio


async def test_catalogo_publico_sin_sesion(api):
    r = await api.get("/api/v1/products", params={"available": "true"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 9
    # Solo campos públicos: sin stock exacto, sin SKU, sin fechas internas.
    assert set(items[0]) == {"id", "name", "description", "category", "price_clp", "available"}
    assert (await api.get("/api/v1/categories")).status_code == 200


async def test_filtros_invalidos_400_o_422(api):
    r = await api.get("/api/v1/products", params={"page_size": "5000"})
    assert r.status_code == 422


async def test_registro_login_refresh_logout(api):
    email = f"nuevo{uuid.uuid4().hex[:6]}@example.cl"
    r = await api.post("/api/v1/auth/register", json={
        "email": email, "password": "Segura123", "first_name": "Ana", "last_name": "Díaz",
        "phone": "+56933333333", "run": "12345678-5"})
    assert r.status_code == 201, r.text
    assert "password" not in r.text
    # correo repetido
    r2 = await api.post("/api/v1/auth/register", json={
        "email": email, "password": "Segura123", "first_name": "Ana", "last_name": "Díaz"})
    assert r2.status_code == 409

    h = await login(api, email, "Segura123")
    me = await api.get("/api/v1/me", headers=auth(h))
    assert me.status_code == 200 and me.json()["first_name"] == "Ana"

    r = await api.post("/api/v1/auth/refresh", json={"refresh_token": h["_refresh"]})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    # el refresh anterior quedó revocado (rotación)
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": h["_refresh"]})).status_code == 401
    assert (await api.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})).status_code == 204
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})).status_code == 401


async def test_run_invalido_rechazado(api):
    r = await api.post("/api/v1/auth/register", json={
        "email": "x@example.cl", "password": "Segura123", "first_name": "A", "last_name": "B", "run": "12345678-0"})
    assert r.status_code == 422


async def test_compra_completa_webpay(api):
    cliente = auth(await login(api, "javiera@example.cl"))
    stock_before = {p["id"]: p for p in (await api.get("/api/v1/admin/stock", headers=auth(await login(api, "admin@lanonna.test")))).json()}

    # 1. Pedido: el navegador intenta mandar un precio -> se rechaza el campo
    r = await api.post("/api/v1/orders", headers=cliente, json={
        "items": [{"product_id": 1, "quantity": 2, "unit_price_clp": 1}], "delivery_type": "RETIRO"})
    assert r.status_code == 422

    r = await api.post("/api/v1/orders", headers=cliente, json={
        "items": [{"product_id": 1, "quantity": 2}, {"product_id": 8, "quantity": 1}],
        "delivery_type": "DESPACHO", "address_id": 1})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "PENDIENTE_PAGO"
    assert order["total_clp"] == 2 * 7900 + 7400  # precio oficial de inventory
    assert order["delivery_address"] == "Calle Ficticia 123, Maipú"
    code = order["order_code"]

    # 2. Stock reservado
    admin = auth(await login(api, "admin@lanonna.test"))
    stock_mid = {p["id"]: p for p in (await api.get("/api/v1/admin/stock", headers=admin)).json()}
    assert stock_mid[1]["quantity_available"] == stock_before[1]["quantity_available"] - 2
    assert stock_mid[1]["quantity_reserved"] == stock_before[1]["quantity_reserved"] + 2

    # 3. Pago Webpay (idempotente)
    key = {"Idempotency-Key": uuid.uuid4().hex}
    r = await api.post("/api/v1/payments", headers=cliente | key, json={"order_code": code, "method": "WEBPAY"})
    assert r.status_code == 201, r.text
    pay = r.json()
    assert pay["amount_clp"] == order["total_clp"] and pay["status"] == "INICIADO"
    again = await api.post("/api/v1/payments", headers=cliente | key, json={"order_code": code, "method": "WEBPAY"})
    assert again.json()["id"] == pay["id"] and again.json()["idempotent"] is True

    # 4. El proveedor (adaptador de prueba) avisa con firma válida
    token = pay["redirect_url"].rsplit("/", 1)[1]
    r = await provider_pay(token)
    assert r["webhook_status"] == 200, r
    assert r["webhook_response"]["receipt_number"].startswith("B-")

    # 5. Aviso duplicado: no se vuelve a aplicar
    r = await provider_pay(token, resend="true")
    assert r["webhook_response"]["duplicate"] is True

    detail = (await api.get(f"/api/v1/orders/{code}", headers=cliente)).json()
    assert detail["status"] == "PAGADO"
    stock_after = {p["id"]: p for p in (await api.get("/api/v1/admin/stock", headers=admin)).json()}
    assert stock_after[1]["quantity_reserved"] == stock_before[1]["quantity_reserved"]  # reserva confirmada
    assert stock_after[1]["quantity_available"] == stock_before[1]["quantity_available"] - 2

    # 6. Cocina avanza estados; no puede saltarse pasos
    cocina = auth(await login(api, "cocina@lanonna.test"))
    assert (await api.patch(f"/api/v1/orders/{code}/status", headers=cocina, json={"status": "LISTO"})).status_code == 409
    for st in ("PREPARANDO", "LISTO", "ENTREGADO"):
        r = await api.patch(f"/api/v1/orders/{code}/status", headers=cocina, json={"status": st})
        assert r.status_code == 200, r.text


async def test_pago_efectivo_confirmado_por_personal(api):
    cliente = auth(await login(api, "matias@example.cl"))
    code = (await api.post("/api/v1/orders", headers=cliente, json={
        "items": [{"product_id": 9, "quantity": 1}], "delivery_type": "RETIRO"})).json()["order_code"]
    pay = (await api.post("/api/v1/payments", headers=cliente | {"Idempotency-Key": uuid.uuid4().hex},
                          json={"order_code": code, "method": "EFECTIVO"})).json()
    # el cliente no puede confirmarse su propio pago
    assert (await api.post(f"/api/v1/payments/{pay['id']}/confirm-manual", headers=cliente)).status_code == 403
    cocina = auth(await login(api, "cocina@lanonna.test"))
    r = await api.post(f"/api/v1/payments/{pay['id']}/confirm-manual", headers=cocina)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "AUTORIZADO" and r.json()["receipt_number"]
    assert (await api.get(f"/api/v1/orders/{code}", headers=cliente)).json()["status"] == "PAGADO"


async def test_stock_insuficiente_y_anulacion_libera_stock(api):
    cliente = auth(await login(api, "matias@example.cl"))
    admin = auth(await login(api, "admin@lanonna.test"))
    assert (await api.put("/api/v1/products/5/stock", headers=admin, json={"quantity_available": 3})).status_code == 200
    r = await api.post("/api/v1/orders", headers=cliente, json={"items": [{"product_id": 5, "quantity": 4}], "delivery_type": "RETIRO"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "OUT_OF_STOCK"

    r = await api.post("/api/v1/orders", headers=cliente, json={"items": [{"product_id": 5, "quantity": 3}], "delivery_type": "RETIRO"})
    code = r.json()["order_code"]
    products = (await api.get("/api/v1/products/5")).json()
    assert products["available"] is False
    r = await api.post(f"/api/v1/orders/{code}/cancel", headers=cliente)
    assert r.status_code == 200 and r.json()["status"] == "ANULADO"
    assert (await api.get("/api/v1/products/5")).json()["available"] is True  # stock recuperado
    # sigue en el historial (no se borró)
    assert (await api.get(f"/api/v1/orders/{code}", headers=cliente)).json()["status"] == "ANULADO"


async def test_reserva_vencida_recupera_stock(api):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import update
    from common.db import get_engine
    from common.tables import orders, stock_reservations

    cliente = auth(await login(api, "javiera@example.cl"))
    admin = auth(await login(api, "admin@lanonna.test"))
    before = {p["id"]: p for p in (await api.get("/api/v1/admin/stock", headers=admin)).json()}[2]
    code = (await api.post("/api/v1/orders", headers=cliente, json={"items": [{"product_id": 2, "quantity": 2}], "delivery_type": "RETIRO"})).json()["order_code"]
    # Simula el paso del tiempo (pago que nunca llegó)
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    with get_engine("orders").begin() as c:
        c.execute(update(orders).where(orders.c.order_code == code).values(created_at=past))
    with get_engine("inventory").begin() as c:
        c.execute(update(stock_reservations).where(stock_reservations.c.status == "ACTIVA").values(expires_at=past))
    r = await api.post("/api/v1/admin/orders/expire-pending", headers=admin)
    assert r.status_code == 200 and r.json()["expired_orders"] >= 1
    after = {p["id"]: p for p in (await api.get("/api/v1/admin/stock", headers=admin)).json()}[2]
    assert after["quantity_available"] == before["quantity_available"]
    assert after["quantity_reserved"] == before["quantity_reserved"]
    assert (await api.get(f"/api/v1/orders/{code}", headers=cliente)).json()["status"] == "ANULADO"


async def test_admin_crud_producto(api):
    admin = auth(await login(api, "admin@lanonna.test"))
    body = {"category_id": 3, "sku": "TAL-TEST", "name": "Tallarines de prueba", "description": "Solo prueba",
            "price_clp": 5000, "initial_stock": 5}
    r = await api.post("/api/v1/products", headers=admin, json=body)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    put = {k: v for k, v in body.items() if k != "initial_stock"} | {"price_clp": 5500, "active": True}
    assert (await api.put(f"/api/v1/products/{pid}", headers=admin, json=put)).json()["price_clp"] == 5500
    assert (await api.delete(f"/api/v1/products/{pid}", headers=admin)).status_code == 204
    assert (await api.get(f"/api/v1/products/{pid}")).status_code == 404  # desactivado, no visible
