"""API Gateway (ÚNICO componente público).

Responsabilidades:
1. Enrutar solo las rutas/verbos de routes.ROUTES (lista explícita; el resto 404/405).
2. AuthenticationPolicy: validar el JWT RS256 (firma, emisor, audiencia, expiración)
   con la clave pública ``jwt-public-key``.
3. AuthorizationPolicy: rol permitido por ruta (los servicios repiten y añaden propiedad).
4. Descartar cabeceras de identidad que mande el navegador (X-User-*, X-Service-*) y
   enviar solo contexto verificado + la credencial de servicio del tramo.
5. Límite de solicitudes, tamaño máximo de cuerpo, plazo máximo, errores controlados,
   cabeceras de seguridad y logs con correlation id sin secretos.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

import httpx
import jwt
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.secrets import get_secret
from common.service import (
    ApiError, DependencyError, UserCtx, _http, correlation_id_var, create_app, error_body,
    get_logger, service_url,
)
from services.api_gateway.routes import ROUTES, find_route, path_exists

app = create_app("api-gateway")
log = get_logger("api-gateway")
MAX_BODY_BYTES = 64 * 1024
UPSTREAM_TIMEOUT = float(os.environ.get("GATEWAY_UPSTREAM_TIMEOUT", "5"))
# solicitudes por ventana de 60 s
RATE_LIMITS = {
    "default": int(os.environ.get("RATE_DEFAULT", "120")),
    "auth": int(os.environ.get("RATE_AUTH", "10")),
    "graphql": int(os.environ.get("RATE_GRAPHQL", "60")),
    "webhook": int(os.environ.get("RATE_WEBHOOK", "300")),
}
FORWARDED_RESPONSE_HEADERS = ("content-type", "retry-after")

if os.environ.get("FRONTEND_ORIGIN"):
    app.add_middleware(
        CORSMiddleware, allow_origins=[os.environ["FRONTEND_ORIGIN"]], allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )


# --------------------------------------------------------- rate limiting
class RateLimiter:
    """Ventana deslizante en memoria (una instancia de gateway). Con varias réplicas
    se reemplazaría por un almacén compartido (Redis)."""

    def __init__(self):
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)

    def allow(self, policy: str, key: str) -> tuple[bool, int]:
        limit, window, now = RATE_LIMITS[policy], 60.0, time.monotonic()
        q = self.hits[(policy, key)]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False, int(window - (now - q[0])) + 1
        q.append(now)
        return True, 0


limiter = RateLimiter()


# ------------------------------------------------------ authentication
def authenticate(request: Request) -> UserCtx | None:
    header = request.headers.get("authorization", "")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 4096:
        raise ApiError(401, "INVALID_TOKEN", "Token inválido")
    try:
        claims = jwt.decode(token, get_secret("jwt-public-key"), algorithms=["RS256"],
                            audience="nonna-api", issuer="nonna-auth",
                            options={"require": ["exp", "iat", "sub", "role", "email"]})
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "TOKEN_EXPIRED", "La sesión expiró")
    except jwt.PyJWTError:
        raise ApiError(401, "INVALID_TOKEN", "Token inválido")
    if not str(claims["sub"]).isdigit() or claims["role"] not in ("CLIENTE", "TRABAJADOR", "ADMIN"):
        raise ApiError(401, "INVALID_TOKEN", "Token inválido")
    return UserCtx(int(claims["sub"]), claims["role"], claims["email"])


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------------- proxy
@app.api_route("/api/v1/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(request: Request, rest: str):
    path = request.url.path
    route, params = find_route(request.method, path)
    if route is None:
        if path_exists(path):
            raise ApiError(405, "METHOD_NOT_ALLOWED", "Método no permitido para esta ruta")
        raise ApiError(404, "NOT_FOUND", "Ruta no encontrada")

    user = authenticate(request)  # un token inválido se rechaza incluso en rutas anónimas
    if route.access == "AUTH":
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "Se requiere iniciar sesión")
        if route.roles and user.role not in route.roles:
            raise ApiError(403, "FORBIDDEN", "No tiene permisos para esta operación")

    rate_key = f"user:{user.user_id}" if user else f"ip:{client_ip(request)}"
    ok, retry = limiter.allow(route.rate, rate_key)
    if not ok:
        return JSONResponse(error_body("RATE_LIMITED", "Demasiadas solicitudes"), status_code=429,
                            headers={"Retry-After": str(retry)})

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "Solicitud demasiado grande")
    if body and request.method in ("POST", "PUT", "PATCH"):
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Use application/json")

    # Solo se reenvían cabeceras de la lista blanca; X-User-* / X-Service-* del navegador se descartan.
    headers = {"Content-Type": "application/json"} if body else {}
    for h in route.forward_headers:
        if h in request.headers:
            headers[h] = request.headers[h]

    try:
        upstream = await forward(route, request, params, user, headers, body)
    except DependencyError as exc:
        log.warning("upstream_unavailable", extra={"fields": {"route": route.id, "target": route.target}})
        raise ApiError(exc.status, "SERVICE_UNAVAILABLE", "Servicio temporalmente no disponible")

    if upstream.status_code >= 500:
        log.warning("upstream_error", extra={"fields": {"route": route.id, "status": upstream.status_code}})
    response = Response(content=upstream.content, status_code=upstream.status_code)
    for h in FORWARDED_RESPONSE_HEADERS:
        if h in upstream.headers:
            response.headers[h] = upstream.headers[h]
    return response


async def forward(route, request: Request, params: dict, user: UserCtx | None, headers: dict, body: bytes):
    """Reenvía al servicio destino con la credencial de ESTE tramo (gateway -> destino).
    El cuerpo va tal cual: el webhook necesita los bytes exactos para verificar la firma."""
    svc_headers = {
        "X-Service-Name": "api-gateway",
        "X-Service-Token": get_secret(f"svc-api-gateway-to-{route.target}"),
        "X-Correlation-Id": correlation_id_var.get(),
        **headers,
    }
    if user:
        svc_headers.update(user.as_headers())
    query = dict(request.query_params) if request.method == "GET" else None
    try:
        return await _http().request(request.method, service_url(route.target) + route.internal_path(params),
                                     content=body or None, params=query, headers=svc_headers,
                                     timeout=httpx.Timeout(UPSTREAM_TIMEOUT))
    except httpx.TimeoutException:
        raise DependencyError(route.target, 504)
    except httpx.HTTPError:
        raise DependencyError(route.target, 503)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.get("/routes", include_in_schema=False)
async def list_routes():
    """Documentación de rutas publicadas (sin destinos internos sensibles)."""
    return [{"id": r.id, "method": r.method, "path": r.external, "access": r.access, "roles": list(r.roles)} for r in ROUTES]
