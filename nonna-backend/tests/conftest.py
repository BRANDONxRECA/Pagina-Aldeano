"""Levanta TODOS los servicios en el mismo proceso, cada uno con su propia base SQLite y
sus propios secretos, conectados por un transporte HTTP que enruta por nombre de host.
Las pruebas hablan solo con el API Gateway, como lo haría el navegador; las pruebas de
acceso directo llaman a un servicio interno sin pasar por el gateway."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="nonna-test-"))
SERVICES = ["api-gateway", "auth", "clients", "inventory", "orders", "payments", "graphql", "analytics", "provider"]

os.environ.update({
    "SECRETS_DIR": str(_TMP / "secrets"),
    "BCRYPT_ROUNDS": "4",
    "ORDER_EXPIRY_LOOP_SECONDS": "0",
    "LOG_LEVEL": "WARNING",
    "PROVIDER_URL": "http://provider.internal",
    "PROVIDER_PUBLIC_URL": "http://provider.internal",
    "PROVIDER_WEBHOOK_URL": "http://api-gateway.internal/api/v1/payments/webhook",
    "RATE_AUTH": "1000",
    "ANALYTICS_CACHE_SECONDS": "0",
})
for name in SERVICES:
    os.environ[name.upper().replace("-", "_") + "_URL"] = f"http://{name}.internal"

from scripts.gen_secrets import generate  # noqa: E402
from scripts.seed_sqlite import TEST_PASSWORDS, seed  # noqa: E402

generate(_TMP / "secrets")
for svc, url in seed(_TMP / "data").items():
    os.environ[f"{svc.upper()}_DATABASE_URL"] = url

from common import service  # noqa: E402
from services.analytics_service.app import app as analytics_app  # noqa: E402
from services.api_gateway.app import app as gateway_app  # noqa: E402
from services.api_gateway.app import limiter  # noqa: E402
from services.auth_service.app import app as auth_app  # noqa: E402
from services.clients_service.app import app as clients_app  # noqa: E402
from services.graphql_gateway.app import app as graphql_app  # noqa: E402
from services.inventory_service.app import app as inventory_app  # noqa: E402
from services.mock_provider.app import app as provider_app  # noqa: E402
from services.orders_service.app import app as orders_app  # noqa: E402
from services.payments_service.app import app as payments_app  # noqa: E402

APPS = {
    "api-gateway.internal": gateway_app, "auth.internal": auth_app, "clients.internal": clients_app,
    "inventory.internal": inventory_app, "orders.internal": orders_app, "payments.internal": payments_app,
    "graphql.internal": graphql_app, "analytics.internal": analytics_app, "provider.internal": provider_app,
}
DOWN: set[str] = set()  # hosts simulados como caídos


class RouterTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.transports = {h: httpx.ASGITransport(app=a, client=("10.0.0.2", 5000)) for h, a in APPS.items()}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host in DOWN or host not in self.transports:
            raise httpx.ConnectError(f"no route to {host}", request=request)
        return await self.transports[host].handle_async_request(request)


service.set_transport(RouterTransport())


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def api():
    """Cliente 'navegador': solo puede hablar con el API Gateway."""
    limiter.hits.clear()
    DOWN.clear()
    transport = httpx.ASGITransport(app=gateway_app, client=("203.0.113.10", 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://api-gateway.internal") as client:
        yield client
    DOWN.clear()


@pytest.fixture
def down():
    return DOWN


async def login(api: httpx.AsyncClient, email: str, password: str | None = None) -> dict:
    r = await api.post("/api/v1/auth/login", json={"email": email, "password": password or TEST_PASSWORDS[email]})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}", "_refresh": data["refresh_token"]}


async def provider_pay(token: str, **params) -> dict:
    """Simula al cliente pagando en el sitio del proveedor (fuera de nuestro backend)."""
    async with httpx.AsyncClient(transport=RouterTransport()) as c:
        r = await c.get(f"http://provider.internal/pay/{token}", params=params)
        return r.json()


def auth(h: dict) -> dict:
    return {k: v for k, v in h.items() if not k.startswith("_")}
