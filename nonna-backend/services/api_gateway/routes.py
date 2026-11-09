"""RouteDefinition: lista EXPLÍCITA de rutas y verbos permitidos.

Cualquier combinación (verbo, ruta) que no esté aquí responde 404 en el gateway.
Las rutas /internal/* de los servicios nunca se publican.

access:
  ANON  -> no exige token (catálogo público, login, registro, webhook del proveedor)
  AUTH  -> exige JWT válido y uno de ``roles`` (vacío = cualquier rol autenticado)
El gateway hace la autorización gruesa por rol; cada servicio repite la verificación
de rol y además controla propiedad del recurso y reglas de negocio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RouteDefinition:
    id: str
    method: str
    external: str            # plantilla externa, ej. /api/v1/orders/{code}
    target: str              # servicio destino
    internal: str            # plantilla interna, ej. /orders/{code}
    access: str = "AUTH"     # ANON | AUTH
    roles: tuple[str, ...] = ()
    rate: str = "default"    # política de límite de solicitudes
    forward_headers: tuple[str, ...] = ()
    regex: re.Pattern = field(init=False, compare=False, repr=False)

    def __post_init__(self):
        pattern = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[A-Za-z0-9-]{1,40})", self.external) + "$"
        object.__setattr__(self, "regex", re.compile(pattern))

    def match(self, method: str, path: str) -> dict | None:
        if method != self.method:
            return None
        m = self.regex.match(path)
        return m.groupdict() if m else None

    def internal_path(self, params: dict) -> str:
        return self.internal.format(**params)


C, T, A = "CLIENTE", "TRABAJADOR", "ADMIN"

ROUTES: list[RouteDefinition] = [
    # --- Auth (S01-S06)
    RouteDefinition("S01", "POST", "/api/v1/auth/register", "auth", "/auth/register", "ANON", rate="auth"),
    RouteDefinition("S02", "POST", "/api/v1/auth/login", "auth", "/auth/login", "ANON", rate="auth"),
    RouteDefinition("S03", "POST", "/api/v1/auth/refresh", "auth", "/auth/refresh", "ANON", rate="auth"),
    RouteDefinition("S04", "POST", "/api/v1/auth/logout", "auth", "/auth/logout", "ANON", rate="auth"),
    RouteDefinition("S05", "GET", "/api/v1/auth/me", "auth", "/auth/me"),
    RouteDefinition("S06", "POST", "/api/v1/admin/staff", "auth", "/auth/staff", roles=(A,)),
    # --- Catálogo / inventory (S07-S14)
    RouteDefinition("S07", "GET", "/api/v1/products", "inventory", "/products", "ANON"),
    RouteDefinition("S08", "GET", "/api/v1/products/{id}", "inventory", "/products/{id}", "ANON"),
    RouteDefinition("S09", "GET", "/api/v1/categories", "inventory", "/categories", "ANON"),
    RouteDefinition("S10", "POST", "/api/v1/products", "inventory", "/products", roles=(A,)),
    RouteDefinition("S11", "PUT", "/api/v1/products/{id}", "inventory", "/products/{id}", roles=(A,)),
    RouteDefinition("S12", "DELETE", "/api/v1/products/{id}", "inventory", "/products/{id}", roles=(A,)),
    RouteDefinition("S13", "PUT", "/api/v1/products/{id}/stock", "inventory", "/products/{id}/stock", roles=(A, T)),
    RouteDefinition("S14", "GET", "/api/v1/admin/stock", "inventory", "/admin/stock", roles=(A, T)),
    # --- Clientes (S15-S20)
    RouteDefinition("S15", "GET", "/api/v1/me", "clients", "/me", roles=(C,)),
    RouteDefinition("S16", "PUT", "/api/v1/me", "clients", "/me", roles=(C,)),
    RouteDefinition("S17", "GET", "/api/v1/me/addresses", "clients", "/me/addresses", roles=(C,)),
    RouteDefinition("S18", "POST", "/api/v1/me/addresses", "clients", "/me/addresses", roles=(C,)),
    RouteDefinition("S19", "PUT", "/api/v1/me/addresses/{id}", "clients", "/me/addresses/{id}", roles=(C,)),
    RouteDefinition("S20", "GET", "/api/v1/admin/clients", "clients", "/admin/clients", roles=(A,)),
    # --- Pedidos (S21-S26)
    RouteDefinition("S21", "POST", "/api/v1/orders", "orders", "/orders", roles=(C,)),
    RouteDefinition("S22", "GET", "/api/v1/orders", "orders", "/orders"),
    RouteDefinition("S23", "GET", "/api/v1/orders/{code}", "orders", "/orders/{code}"),
    RouteDefinition("S24", "PATCH", "/api/v1/orders/{code}/status", "orders", "/orders/{code}/status", roles=(T, A)),
    RouteDefinition("S25", "POST", "/api/v1/orders/{code}/cancel", "orders", "/orders/{code}/cancel", roles=(C, A)),
    RouteDefinition("S26", "POST", "/api/v1/admin/orders/expire-pending", "orders", "/admin/orders/expire-pending", roles=(A,)),
    # --- Pagos (S27-S30)
    RouteDefinition("S27", "POST", "/api/v1/payments", "payments", "/payments", roles=(C,), forward_headers=("idempotency-key",)),
    RouteDefinition("S28", "GET", "/api/v1/payments/{id}", "payments", "/payments/{id}"),
    RouteDefinition("S29", "POST", "/api/v1/payments/{id}/confirm-manual", "payments", "/payments/{id}/confirm-manual", roles=(T, A)),
    RouteDefinition("S30", "POST", "/api/v1/payments/webhook", "payments", "/payments/webhook", "ANON",
                    rate="webhook", forward_headers=("x-provider-signature",)),
    # --- Agregación GraphQL (S31)
    RouteDefinition("S31", "POST", "/api/v1/graphql", "graphql", "/graphql", rate="graphql"),
]


def find_route(method: str, path: str) -> tuple[RouteDefinition, dict] | tuple[None, None]:
    for route in ROUTES:
        params = route.match(method, path)
        if params is not None:
            return route, params
    return None, None


def path_exists(path: str) -> bool:
    return any(r.regex.match(path) for r in ROUTES)
