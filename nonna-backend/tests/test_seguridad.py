"""Casos de validación del Módulo 7 y controles de los módulos 4-6, ejecutados contra el backend."""
import hashlib
import hmac
import json
import uuid

import httpx
import jwt
import pytest

from common.secrets import get_secret
from services.inventory_service.app import app as inventory_app
from services.orders_service.app import app as orders_app
from tests.conftest import RouterTransport, auth, login

pytestmark = pytest.mark.anyio


# 1. Acceso anónimo al catálogo -> permitido (verifica: API Gateway, ruta S07 ANON)
async def test_m7_1_catalogo_anonimo(api):
    assert (await api.get("/api/v1/products")).status_code == 200


# 2. Operación protegida sin sesión válida -> 401 (verifica: API Gateway)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer abc.def.ghi"}, {"Authorization": "Basic xyz"}])
async def test_m7_2_sin_sesion_valida(api, headers):
    r = await api.get("/api/v1/orders", headers=headers)
    assert r.status_code == 401


async def test_m7_2_token_firmado_con_otra_clave(api):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    forged = jwt.encode({"sub": "4", "role": "ADMIN", "email": "x@x.cl", "iss": "nonna-auth", "aud": "nonna-api",
                         "iat": 1, "exp": 9999999999}, other, algorithm="RS256")
    r = await api.get("/api/v1/admin/stock", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


async def test_m7_2_token_alg_none(api):
    forged = jwt.encode({"sub": "4", "role": "ADMIN", "email": "x@x.cl"}, key=None, algorithm="none")
    assert (await api.get("/api/v1/admin/stock", headers={"Authorization": f"Bearer {forged}"})).status_code == 401


# 3. Administración desde un rol sin permiso -> 403 (verifica: gateway y además inventory)
async def test_m7_3_cliente_no_administra(api):
    cliente = auth(await login(api, "javiera@example.cl"))
    r = await api.delete("/api/v1/products/1", headers=cliente)
    assert r.status_code == 403
    r = await api.post("/api/v1/products", headers=cliente, json={})
    assert r.status_code == 403
    cocina = auth(await login(api, "cocina@lanonna.test"))
    assert (await api.delete("/api/v1/products/1", headers=cocina)).status_code == 403
    assert (await api.get("/api/v1/admin/clients", headers=cocina)).status_code == 403


async def test_m7_3_cabeceras_de_identidad_falsificadas(api):
    """El navegador manda X-User-Role: ADMIN -> el gateway la descarta."""
    cliente = auth(await login(api, "javiera@example.cl"))
    spoof = {"X-User-Id": "4", "X-User-Role": "ADMIN", "X-User-Email": "admin@lanonna.test",
             "X-Service-Name": "api-gateway", "X-Service-Token": "inventado"}
    assert (await api.delete("/api/v1/products/1", headers=spoof)).status_code == 401
    assert (await api.delete("/api/v1/products/1", headers=cliente | spoof)).status_code == 403


# 4. Consulta de un pedido ajeno -> 404 sin datos (verifica: orders, propiedad)
async def test_m7_4_pedido_ajeno(api):
    matias = auth(await login(api, "matias@example.cl"))
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await api.get("/api/v1/orders/P-1042", headers=javiera)  # propio
    assert r.status_code == 200 and r.json()["order_code"] == "P-1042"
    r = await api.get("/api/v1/orders/P-1042", headers=matias)   # ajeno
    assert r.status_code == 404
    assert "P-1042" not in r.text and "Ficticia" not in r.text
    # el listado solo trae los propios
    codes = {o["order_code"] for o in (await api.get("/api/v1/orders", headers=matias)).json()["items"]}
    assert "P-1042" not in codes and "P-1093" in codes
    # tampoco puede anularlo ni pagarlo
    assert (await api.post("/api/v1/orders/P-1042/cancel", headers=matias)).status_code == 404
    r = await api.post("/api/v1/payments", headers=matias | {"Idempotency-Key": uuid.uuid4().hex},
                       json={"order_code": "P-1042", "method": "WEBPAY"})
    assert r.status_code == 404


# 5. Acceso directo al backend sin identidad autorizada -> 401/403 (verifica: cada servicio)
async def test_m7_5_acceso_directo_a_servicios_privados():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=inventory_app), base_url="http://inventory.internal") as c:
        assert (await c.get("/products")).status_code == 401
        # identidad de usuario sin credencial de servicio
        r = await c.post("/products", headers={"X-User-Id": "4", "X-User-Role": "ADMIN", "X-User-Email": "a@a.cl"}, json={})
        assert r.status_code == 401
        # credencial robada del gateway no sirve para operaciones internas de orders->inventory
        gw = {"X-Service-Name": "api-gateway", "X-Service-Token": get_secret("svc-api-gateway-to-inventory")}
        r = await c.post("/internal/reservations", headers=gw, json={"order_id": 1, "items": [{"product_id": 1, "quantity": 1}]})
        assert r.status_code == 403
        # credencial de otro tramo (payments->orders) usada contra inventory
        r = await c.get("/products", headers={"X-Service-Name": "payments", "X-Service-Token": get_secret("svc-payments-to-orders")})
        assert r.status_code == 401
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=orders_app), base_url="http://orders.internal") as c:
        r = await c.post("/internal/orders/1/mark-paid", json={"payment_id": 1, "amount_clp": 1})
        assert r.status_code == 401


async def test_m7_5_gateway_no_publica_rutas_internas(api):
    for path in ("/api/v1/internal/reservations", "/internal/orders", "/api/v1/../internal/clients"):
        r = await api.post(path, json={})
        assert r.status_code in (404, 405)
    assert (await api.get("/internal/clients?ids=1")).status_code == 404


# 6. Confirmar pago con datos alterados del frontend -> rechazado (verifica: payments y orders)
async def test_m7_6_pago_alterado(api):
    cliente = auth(await login(api, "javiera@example.cl"))
    code = (await api.post("/api/v1/orders", headers=cliente, json={
        "items": [{"product_id": 7, "quantity": 1}], "delivery_type": "RETIRO"})).json()["order_code"]
    pay = (await api.post("/api/v1/payments", headers=cliente | {"Idempotency-Key": uuid.uuid4().hex},
                          json={"order_code": code, "method": "WEBPAY", })).json()
    token = pay["redirect_url"].rsplit("/", 1)[1]

    # a) el navegador intenta fijar el monto -> campo no permitido
    r = await api.post("/api/v1/payments", headers=cliente | {"Idempotency-Key": uuid.uuid4().hex},
                       json={"order_code": code, "method": "WEBPAY", "amount_clp": 1})
    assert r.status_code == 422
    # b) el cliente intenta marcar su pedido como PAGADO
    r = await api.patch(f"/api/v1/orders/{code}/status", headers=cliente, json={"status": "PAGADO"})
    assert r.status_code == 403
    # c) aviso falso sin firma / con firma inventada
    event = json.dumps({"event_id": "evt_fake_1", "token": token, "result": "AUTHORIZED", "amount": pay["amount_clp"]}).encode()
    r = await api.post("/api/v1/payments/webhook", content=event, headers={"Content-Type": "application/json"})
    assert r.status_code == 401
    r = await api.post("/api/v1/payments/webhook", content=event, headers={
        "Content-Type": "application/json", "X-Provider-Signature": hmac.new(b"adivinada", event, hashlib.sha256).hexdigest()})
    assert r.status_code == 401
    # d) aviso firmado pero con monto alterado
    bad = json.dumps({"event_id": "evt_fake_2", "token": token, "result": "AUTHORIZED", "amount": 1}).encode()
    sig = hmac.new(get_secret("payments-webhook-secret").encode(), bad, hashlib.sha256).hexdigest()
    r = await api.post("/api/v1/payments/webhook", content=bad, headers={"Content-Type": "application/json", "X-Provider-Signature": sig})
    assert r.status_code == 400
    # el pedido sigue sin pagar
    assert (await api.get(f"/api/v1/orders/{code}", headers=cliente)).json()["status"] == "PENDIENTE_PAGO"


# Otros controles
async def test_bloqueo_por_intentos_fallidos(api):
    email = f"lock{uuid.uuid4().hex[:6]}@example.cl"
    await api.post("/api/v1/auth/register", json={"email": email, "password": "Segura123", "first_name": "L", "last_name": "K"})
    for _ in range(5):
        assert (await api.post("/api/v1/auth/login", json={"email": email, "password": "mala12345"})).status_code == 401
    r = await api.post("/api/v1/auth/login", json={"email": email, "password": "Segura123"})
    assert r.status_code == 423


async def test_login_no_revela_si_correo_existe(api):
    a = await api.post("/api/v1/auth/login", json={"email": "noexiste@example.cl", "password": "x1234567"})
    b = await api.post("/api/v1/auth/login", json={"email": "javiera@example.cl", "password": "x1234567"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


async def test_limite_de_solicitudes(api, monkeypatch):
    from services.api_gateway import app as gw
    monkeypatch.setitem(gw.RATE_LIMITS, "default", 3)
    codes = [(await api.get("/api/v1/categories")).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429


async def test_dependencia_caida_error_controlado(api, down):
    down.add("inventory.internal")
    r = await api.get("/api/v1/products")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "inventory.internal" not in r.text and "Traceback" not in r.text


async def test_respuestas_sin_secretos_ni_hashes(api):
    admin = auth(await login(api, "admin@lanonna.test"))
    r = await api.get("/api/v1/admin/clients", headers=admin)
    assert r.status_code == 200
    first = r.json()["items"][0]
    assert first["run"].startswith("****") and "*" in first["phone"]  # enmascarados
    cliente = auth(await login(api, "javiera@example.cl"))
    me = await api.get("/api/v1/auth/me", headers=cliente)
    assert "password" not in me.text and "hash" not in me.text
    pay = await api.get("/api/v1/payments/1", headers=cliente)
    assert pay.status_code == 200 and "tok_" not in pay.text and "idempotency" not in pay.text


async def test_cabeceras_de_seguridad(api):
    r = await api.get("/api/v1/categories")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-correlation-id"]
