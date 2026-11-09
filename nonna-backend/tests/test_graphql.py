"""Módulo 8: GraphQL Gateway privado, agregación y límites."""
import httpx
import pytest

from services.graphql_gateway.app import app as graphql_app
from tests.conftest import auth, login

pytestmark = pytest.mark.anyio

MIS_PEDIDOS = """
query($p: Int!, $t: Int!) {
  misPedidos(pagina: $p, tamano: $t) {
    total pagina
    items {
      codigo estado total
      items { nombre cantidad precioUnitario productoActual { nombre precio disponible } }
      pago { estado metodo numeroBoleta }
    }
  }
}"""


async def gql(api, headers, query, variables=None):
    r = await api.post("/api/v1/graphql", headers=headers, json={"query": query, "variables": variables or {}})
    return r


async def test_agregacion_mis_pedidos_combina_tres_subsistemas(api):
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await gql(api, javiera, MIS_PEDIDOS, {"p": 1, "t": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "errors" not in body, body
    pedidos = {p["codigo"]: p for p in body["data"]["misPedidos"]["items"]}
    p = pedidos["P-1042"]
    assert p["estado"] == "ENTREGADO"                                   # orders
    assert p["items"][0]["productoActual"]["nombre"]                    # inventory
    assert p["pago"] == {"estado": "AUTORIZADO", "metodo": "WEBPAY", "numeroBoleta": "B-000001"}  # payments
    assert all(c in pedidos for c in ("P-1042", "P-1058"))
    assert "P-1093" not in pedidos  # pedido de otro cliente


async def test_dataloader_un_llamado_por_subsistema(api, monkeypatch):
    """Evita N+1: con varios pedidos e ítems hay 1 llamada a inventory y 1 a payments."""
    from common import service
    calls = []
    original = service.call_service

    async def spy(callee, method, path, **kw):
        if service.current_service_var.get() == "graphql":
            calls.append(path)
        return await original(callee, method, path, **kw)

    monkeypatch.setattr("services.graphql_gateway.app.call_service", spy)
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await gql(api, javiera, MIS_PEDIDOS, {"p": 1, "t": 10})
    assert "errors" not in r.json()
    assert calls.count("/internal/products") == 1
    assert calls.count("/internal/payments") == 1


async def test_pedido_ajeno_por_graphql(api):
    matias = auth(await login(api, "matias@example.cl"))
    r = await gql(api, matias, '{ pedido(codigo: "P-1042") { codigo total direccionEntrega } }')
    body = r.json()
    assert body["data"]["pedido"] is None
    assert body["errors"][0]["extensions"]["code"] == "ORDER_NOT_FOUND"
    assert "Ficticia" not in r.text


async def test_autorizacion_por_campo(api):
    """El cliente no puede leer datos de cliente (teléfono) aunque los pida en la selección."""
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await gql(api, javiera, '{ pedido(codigo: "P-1042") { codigo cliente { nombre telefono } } }')
    body = r.json()
    assert body["data"]["pedido"]["codigo"] == "P-1042"
    assert body["data"]["pedido"]["cliente"] is None
    assert "+569" not in r.text
    # El personal sí lo ve
    cocina = auth(await login(api, "cocina@lanonna.test"))
    r = await gql(api, cocina, '{ pedido(codigo: "P-1042") { cliente { nombre telefono } } }')
    assert r.json()["data"]["pedido"]["cliente"]["telefono"] == "+56911111111"


async def test_autorizacion_por_operacion(api):
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await gql(api, javiera, '{ reporteVentas(desde: "2026-09-01", hasta: "2026-09-30") { ingresos } }')
    assert r.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    r = await gql(api, javiera, "{ pedidosActivos { total } }")
    assert r.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"


async def test_panel_cocina_y_reporte_admin(api):
    cocina = auth(await login(api, "cocina@lanonna.test"))
    r = await gql(api, cocina, "{ pedidosActivos(pagina: 1, tamano: 20) { total items { codigo estado cliente { nombre } } } }")
    data = r.json()["data"]["pedidosActivos"]
    assert {"P-1093", "P-1094"} <= {p["codigo"] for p in data["items"]}
    assert all(p["estado"] in ("PAGADO", "PREPARANDO", "LISTO") for p in data["items"])

    admin = auth(await login(api, "admin@lanonna.test"))
    r = await gql(api, admin, '{ reporteVentas(desde: "2026-09-01", hasta: "2026-09-30") '
                              '{ pedidosPagados ingresos ticketPromedio porDia { fecha ingresos } topProductos { nombre unidades } } }')
    rep = r.json()["data"]["reporteVentas"]
    assert rep["pedidosPagados"] == 4 and rep["ingresos"] == 22700 + 19000 + 15200 + 16600


async def test_sin_sesion_rechazado(api):
    r = await api.post("/api/v1/graphql", json={"query": "{ misPedidos { total } }"})
    assert r.status_code == 401


async def test_limite_de_profundidad_alias_y_paginacion(api):
    javiera = auth(await login(api, "javiera@example.cl"))
    deep = "{ misPedidos { items { items { productoActual { nombre } } } } }"
    assert "errors" not in (await gql(api, javiera, deep)).json()
    aliases = "{ " + " ".join(f"a{i}: misPedidos {{ total }}" for i in range(12)) + " }"
    r = await gql(api, javiera, aliases)
    assert r.json()["errors"] and r.json().get("data") is None
    r = await gql(api, javiera, MIS_PEDIDOS, {"p": 1, "t": 500})
    assert r.json()["errors"][0]["extensions"]["code"] == "BAD_PAGINATION"


async def test_limite_de_tokens(api):
    """Consulta enorme (costo) rechazada antes de ejecutarse."""
    javiera = auth(await login(api, "javiera@example.cl"))
    huge = "{ misPedidos { " + " ".join(["total pagina tamano"] * 300) + " } }"
    r = await gql(api, javiera, huge)
    assert r.json()["errors"] and r.json().get("data") is None


async def test_introspeccion_deshabilitada(api):
    javiera = auth(await login(api, "javiera@example.cl"))
    r = await gql(api, javiera, "{ __schema { types { name } } }")
    assert r.json()["errors"]


async def test_error_parcial_si_inventory_cae(api, down):
    javiera = auth(await login(api, "javiera@example.cl"))
    down.add("inventory.internal")
    r = await gql(api, javiera, MIS_PEDIDOS, {"p": 1, "t": 10})
    body = r.json()
    pedidos = body["data"]["misPedidos"]["items"]
    assert pedidos and pedidos[0]["pago"]["estado"]                     # el resto llega igual
    assert pedidos[0]["items"][0]["productoActual"] is None             # campo afectado en null
    assert any(e["extensions"]["code"] == "DEPENDENCY_UNAVAILABLE" for e in body["errors"])


async def test_graphql_privado_no_accesible_directo():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=graphql_app), base_url="http://graphql.internal") as c:
        r = await c.post("/graphql", json={"query": "{ misPedidos { total } }"},
                         headers={"X-User-Id": "1", "X-User-Role": "CLIENTE", "X-User-Email": "a@a.cl"})
        assert r.status_code == 401
