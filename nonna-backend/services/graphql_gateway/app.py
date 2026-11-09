"""GraphQL Gateway (PRIVADO). Solo lo invoca el API Gateway (POST /api/v1/graphql).

Agrega información de varios subsistemas SIN acceder a sus bases de datos:
  orders (pedidos e ítems) + inventory (producto actual) + payments (pago y boleta)
  + clients (nombre/teléfono, solo personal) + analytics (reporte, solo ADMIN).

Controles:
- Identidad verificada (cabeceras puestas por el gateway, con credencial de servicio).
- Autorización por operación (rol), por recurso (dueño del pedido) y por campo
  (``cliente`` y ``telefono`` solo personal).
- Paginación obligatoria (máx. 50), profundidad máx. 6, máx. 10 alias, máx. 800 tokens.
- Sin introspección salvo GRAPHQL_INTROSPECTION=1. Sin consultas por GET.
- DataLoader: un solo llamado por subsistema para todos los ítems (evita N+1).
- Errores parciales: si inventory o payments no responden, el pedido se entrega igual
  y esos campos vienen en null con un error en ``errors``.
"""
from __future__ import annotations

import os
from typing import Optional

import strawberry
from fastapi import Depends, Request
from graphql import GraphQLError
from graphql.validation import NoSchemaIntrospectionCustomRule
from strawberry.dataloader import DataLoader
from strawberry.extensions import AddValidationRules, MaskErrors, MaxAliasesLimiter, MaxTokensLimiter, QueryDepthLimiter
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.permission import BasePermission
from strawberry.types import Info

from common.service import (
    ApiError, Caller, UserCtx, call_service, create_app, expect_ok, require_callers, user_from_headers,
)

MAX_PAGE = 50
SUBSYSTEM_TIMEOUT = float(os.environ.get("GRAPHQL_SUBSYSTEM_TIMEOUT", "2.5"))


# ------------------------------------------------------------------ contexto
class Context(BaseContext):
    def __init__(self, user: UserCtx):
        super().__init__()
        self.user = user
        self.products = DataLoader(load_fn=self._load_products)
        self.payments = DataLoader(load_fn=self._load_payments)
        self.clients = DataLoader(load_fn=self._load_clients)
        self._client_id: int | None = None

    async def client_id(self) -> int:
        if self._client_id is None:
            data = expect_ok(await call_service("clients", "GET", f"/internal/clients/by-user/{self.user.user_id}",
                                                timeout=SUBSYSTEM_TIMEOUT), "clients")
            self._client_id = data["id"]
        return self._client_id

    async def _batch(self, callee: str, path: str, param: str, keys: list[int], key_field: str):
        try:
            rows = expect_ok(await call_service(callee, "GET", path, params={param: ",".join(map(str, keys))},
                                                timeout=SUBSYSTEM_TIMEOUT), callee)
        except ApiError as exc:
            # Un error por clave: GraphQL entrega el resto de la respuesta (error parcial).
            return [exc for _ in keys]
        by_key = {r[key_field]: r for r in rows}
        return [by_key.get(k) for k in keys]

    async def _load_products(self, keys: list[int]):
        return await self._batch("inventory", "/internal/products", "ids", keys, "id")

    async def _load_payments(self, keys: list[int]):
        return await self._batch("payments", "/internal/payments", "order_ids", keys, "order_id")

    async def _load_clients(self, keys: list[int]):
        return await self._batch("clients", "/internal/clients", "ids", keys, "id")


def gql_error(exc: ApiError) -> GraphQLError:
    return GraphQLError(exc.message, extensions={"code": exc.code})


async def load(loader: DataLoader, key: int):
    """Carga por lote; si el subsistema falla, solo este campo queda en null (error parcial)."""
    try:
        return await loader.load(key)
    except ApiError as exc:
        raise gql_error(exc)


class IsStaff(BasePermission):
    message = "No autorizado para este campo"

    def has_permission(self, source, info: Info, **kwargs) -> bool:
        return info.context.user.is_staff


def check_page(pagina: int, tamano: int) -> None:
    if pagina < 1 or not 1 <= tamano <= MAX_PAGE:
        raise GraphQLError(f"Paginación inválida (tamano entre 1 y {MAX_PAGE})", extensions={"code": "BAD_PAGINATION"})


# --------------------------------------------------------------------- tipos
@strawberry.type(description="Datos públicos del catálogo (inventory).")
class Producto:
    id: int
    nombre: str
    descripcion: str
    categoria: str
    precio: int
    disponible: bool


@strawberry.type
class ItemPedido:
    producto_id: int
    nombre: str = strawberry.field(description="Nombre al momento de la compra (orders)")
    precio_unitario: int
    cantidad: int
    subtotal: int

    @strawberry.field(description="Estado actual del producto en inventory (puede ser null si no responde)")
    async def producto_actual(self, info: Info) -> Optional[Producto]:
        p = await load(info.context.products, self.producto_id)
        if p is None:
            return None
        return Producto(id=p["id"], nombre=p["name"], descripcion=p["description"], categoria=p["category"],
                        precio=p["price_clp"], disponible=p["available"])


@strawberry.type(description="Pago del pedido (payments). Nunca incluye tokens ni claves.")
class Pago:
    estado: str
    metodo: str
    monto: int
    numero_boleta: Optional[str]


@strawberry.type(description="Datos del cliente (clients). Solo visible para el personal.")
class ClienteResumen:
    nombre: str
    _phone: strawberry.Private[Optional[str]]

    @strawberry.field(permission_classes=[IsStaff])
    def telefono(self) -> Optional[str]:
        return self._phone


@strawberry.type
class Pedido:
    codigo: str
    estado: str
    tipo_entrega: str
    direccion_entrega: Optional[str]
    subtotal: int
    costo_despacho: int
    total: int
    creado_en: str
    items: list[ItemPedido]
    _order_id: strawberry.Private[int]
    _client_id: strawberry.Private[int]

    @strawberry.field(description="Combina payments con el pedido")
    async def pago(self, info: Info) -> Optional[Pago]:
        p = await load(info.context.payments, self._order_id)
        if p is None:
            return None
        return Pago(estado=p["status"], metodo=p["method"], monto=p["amount_clp"], numero_boleta=p["receipt_number"])

    @strawberry.field(permission_classes=[IsStaff], description="Solo personal")
    async def cliente(self, info: Info) -> Optional[ClienteResumen]:
        c = await load(info.context.clients, self._client_id)
        if c is None:
            return None
        return ClienteResumen(nombre=f"{c['first_name']} {c['last_name']}", _phone=c["phone"])


@strawberry.type
class PaginaPedidos:
    pagina: int
    tamano: int
    total: int
    items: list[Pedido]


@strawberry.type
class VentaDia:
    fecha: str
    pedidos: int
    ingresos: int


@strawberry.type
class ProductoTop:
    producto_id: int
    nombre: str
    unidades: int
    ingresos: int


@strawberry.type
class ReporteVentas:
    desde: str
    hasta: str
    pedidos_pagados: int
    pedidos_anulados: int
    ingresos: int
    ticket_promedio: int
    proporcion_despacho: float
    por_dia: list[VentaDia]
    top_productos: list[ProductoTop]


def to_pedido(o: dict) -> Pedido:
    return Pedido(
        codigo=o["order_code"], estado=o["status"], tipo_entrega=o["delivery_type"],
        direccion_entrega=o["delivery_address"], subtotal=o["subtotal_clp"], costo_despacho=o["delivery_fee_clp"],
        total=o["total_clp"], creado_en=o["created_at"],
        items=[ItemPedido(producto_id=i["product_id"], nombre=i["product_name"], precio_unitario=i["unit_price_clp"],
                          cantidad=i["quantity"], subtotal=i["line_total_clp"]) for i in o["items"]],
        _order_id=o["id"], _client_id=o["client_id"],
    )


def require_role(info: Info, *roles: str) -> UserCtx:
    user = info.context.user
    if user.role not in roles:
        raise GraphQLError("No tiene permisos para esta consulta", extensions={"code": "FORBIDDEN"})
    return user


async def fetch(callee: str, path: str, params: dict | None = None):
    try:
        return expect_ok(await call_service(callee, "GET", path, params=params, timeout=SUBSYSTEM_TIMEOUT), callee)
    except ApiError as exc:
        raise gql_error(exc)


# ------------------------------------------------------------------- queries
@strawberry.type
class Query:
    @strawberry.field(description="Historial del cliente autenticado con producto actual y pago (orders+inventory+payments)")
    async def mis_pedidos(self, info: Info, pagina: int = 1, tamano: int = 10) -> PaginaPedidos:
        require_role(info, "CLIENTE")
        check_page(pagina, tamano)
        try:
            client_id = await info.context.client_id()
        except ApiError as exc:
            raise gql_error(exc)
        data = await fetch("orders", "/internal/orders", {"client_id": client_id, "page": pagina, "page_size": tamano})
        return PaginaPedidos(pagina=pagina, tamano=tamano, total=data["total"], items=[to_pedido(o) for o in data["items"]])

    @strawberry.field(description="Resumen de un pedido. Cliente: solo los propios. Personal: cualquiera.")
    async def pedido(self, info: Info, codigo: str) -> Optional[Pedido]:
        user = info.context.user
        if not codigo.startswith("P-") or len(codigo) > 12:
            raise GraphQLError("Código inválido", extensions={"code": "BAD_INPUT"})
        try:
            o = expect_ok(await call_service("orders", "GET", f"/internal/orders/by-code/{codigo}", timeout=SUBSYSTEM_TIMEOUT), "orders")
            if not user.is_staff and o["client_id"] != await info.context.client_id():
                raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")  # mismo mensaje: no revela existencia
        except ApiError as exc:
            raise gql_error(exc)
        return to_pedido(o)

    @strawberry.field(description="Panel del personal: pedidos en curso (PAGADO, PREPARANDO, LISTO)")
    async def pedidos_activos(self, info: Info, pagina: int = 1, tamano: int = 20) -> PaginaPedidos:
        require_role(info, "TRABAJADOR", "ADMIN")
        check_page(pagina, tamano)
        data = await fetch("orders", "/internal/orders", {"statuses": "PAGADO,PREPARANDO,LISTO", "page": pagina, "page_size": tamano})
        return PaginaPedidos(pagina=pagina, tamano=tamano, total=data["total"], items=[to_pedido(o) for o in data["items"]])

    @strawberry.field(description="Reporte de ventas desde el servicio de analítica (solo ADMIN)")
    async def reporte_ventas(self, info: Info, desde: str, hasta: str) -> ReporteVentas:
        require_role(info, "ADMIN")
        r = await fetch("analytics", "/internal/sales/summary", {"from": desde, "to": hasta})
        return ReporteVentas(
            desde=r["from"], hasta=r["to"], pedidos_pagados=r["paid_orders"], pedidos_anulados=r["cancelled_orders"],
            ingresos=r["revenue_clp"], ticket_promedio=r["average_ticket_clp"], proporcion_despacho=r["delivery_share"],
            por_dia=[VentaDia(fecha=d["date"], pedidos=d["orders"], ingresos=d["revenue_clp"]) for d in r["by_day"]],
            top_productos=[ProductoTop(producto_id=p["product_id"], nombre=p["name"], unidades=p["units"], ingresos=p["revenue_clp"])
                           for p in r["top_products"]],
        )


def should_mask(error: GraphQLError) -> bool:
    original = error.original_error
    return original is not None and not isinstance(original, (GraphQLError, ApiError, PermissionError))


extensions = [
    lambda: QueryDepthLimiter(max_depth=6),
    lambda: MaxAliasesLimiter(max_alias_count=10),
    lambda: MaxTokensLimiter(max_token_count=800),
    lambda: MaskErrors(should_mask_error=should_mask, error_message="Error interno"),
]
if os.environ.get("GRAPHQL_INTROSPECTION", "0") != "1":
    extensions.append(lambda: AddValidationRules([NoSchemaIntrospectionCustomRule]))

schema = strawberry.Schema(query=Query, extensions=extensions)


async def get_context(request: Request, _: Caller = Depends(require_callers("api-gateway"))) -> Context:
    user = user_from_headers(request)
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Se requiere iniciar sesión")
    return Context(user)


app = create_app("graphql")
app.include_router(
    GraphQLRouter(schema, context_getter=get_context, graphql_ide=None, allow_queries_via_get=False),
    prefix="/graphql",
)
