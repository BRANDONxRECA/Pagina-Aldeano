"""Piezas compartidas por todos los servicios.

- Fábrica de apps FastAPI con health check, identificador de correlación, logs sin
  secretos y errores controlados.
- Autenticación entre servicios: cada par llamador -> destino tiene su propia
  credencial (referencia ``svc-<llamador>-to-<destino>``). El destino rechaza
  cualquier llamada sin credencial válida, aunque venga desde la red interna.
- Contexto de usuario: SOLO se acepta si la llamada viene autenticada desde el
  API Gateway (u otro servicio confiable). El gateway borra las cabeceras X-User-*
  que mande el navegador y escribe las suyas a partir del JWT verificado.
- Cliente HTTP interno con plazos máximos y propagación de identidad/correlación.
"""
from __future__ import annotations

import contextvars
import hmac
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.secrets import SecretNotFound, get_secret

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
# Nombre del servicio que atiende la solicitud actual (identidad del llamador en call_service).
current_service_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_service", default=None)

DEFAULT_PORTS = {
    "api-gateway": 8000, "auth": 8001, "clients": 8002, "inventory": 8003,
    "orders": 8004, "payments": 8005, "graphql": 8006, "analytics": 8007,
    "provider": 8009,
}

# ------------------------------------------------------------------ logging
_SENSITIVE_KEYS = ("password", "token", "secret", "authorization", "signature", "run", "phone")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "service": current_service_var.get() or os.environ.get("SERVICE_NAME", "-"),
            "correlation_id": correlation_id_var.get(),
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            data.update({k: ("***" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v) for k, v in extra.items()})
        return json.dumps(data, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"nonna.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
        logger.propagate = False
    return logger


# ------------------------------------------------------------------- errores
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


def error_body(code: str, message: str, extra: dict | None = None) -> dict:
    body = {"error": {"code": code, "message": message, "correlation_id": correlation_id_var.get()}}
    if extra:
        body["error"].update(extra)
    return body


def create_app(service_name: str, **kwargs: Any) -> FastAPI:
    os.environ.setdefault("SERVICE_NAME", service_name)
    expose_docs = os.environ.get("EXPOSE_DOCS", "0") == "1"
    app = FastAPI(
        title=f"La Nonna - {service_name}",
        docs_url="/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if expose_docs else None,
        **kwargs,
    )
    app.state.service_name = service_name
    log = get_logger(service_name)

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        incoming = request.headers.get("x-correlation-id", "")
        cid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        token = correlation_id_var.set(cid)
        svc_token = current_service_var.set(service_name)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            response.headers["X-Correlation-Id"] = cid
            # Se registra ruta y estado; nunca cuerpo, cabeceras de autorización ni query con datos.
            log.info("request", extra={"fields": {
                "method": request.method, "path": request.url.path,
                "status": response.status_code, "ms": elapsed,
                "caller": request.headers.get("x-service-name", "external"),
            }})
            return response
        finally:
            correlation_id_var.reset(token)
            current_service_var.reset(svc_token)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(error_body(exc.code, exc.message, exc.extra), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "issue": e.get("msg")} for e in exc.errors()]
        return JSONResponse(error_body("VALIDATION_ERROR", "Datos de entrada inválidos", {"fields": fields}), status_code=422)

    @app.exception_handler(SecretNotFound)
    async def _secret_missing(_: Request, exc: SecretNotFound):
        log.error("secret_missing", extra={"fields": {"ref": exc.ref}})
        return JSONResponse(error_body("CONFIG_ERROR", "Servicio no disponible"), status_code=503)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("unhandled_error")
        return JSONResponse(error_body("INTERNAL_ERROR", "Error interno"), status_code=500)

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok", "service": service_name}

    return app


# ------------------------------------------------- autenticación de servicios
@dataclass(frozen=True)
class Caller:
    name: str


def _verify_service(request: Request, callee: str) -> Caller:
    name = request.headers.get("x-service-name", "")
    token = request.headers.get("x-service-token", "")
    if not name or not token or not name.replace("-", "").isalnum():
        raise ApiError(401, "SERVICE_UNAUTHENTICATED", "Llamada interna sin identidad de servicio")
    try:
        expected = get_secret(f"svc-{name}-to-{callee}")
    except SecretNotFound:
        # Un llamador sin credencial registrada para este destino no está autorizado.
        raise ApiError(401, "SERVICE_UNAUTHENTICATED", "Identidad de servicio no reconocida")
    if not hmac.compare_digest(token.encode(), expected.encode()):
        raise ApiError(401, "SERVICE_UNAUTHENTICATED", "Identidad de servicio no reconocida")
    return Caller(name)


def require_callers(*allowed: str):
    """Dependencia: autentica al servicio llamador y autoriza por método/ruta."""

    def dependency(request: Request) -> Caller:
        callee = request.app.state.service_name
        caller = _verify_service(request, callee)
        if caller.name not in allowed:
            raise ApiError(403, "SERVICE_FORBIDDEN", "Este servicio no puede invocar esta operación")
        return caller

    return dependency


# ------------------------------------------------------- contexto de usuario
ROLES = ("CLIENTE", "TRABAJADOR", "ADMIN")
STAFF = ("TRABAJADOR", "ADMIN")


@dataclass(frozen=True)
class UserCtx:
    user_id: int
    role: str
    email: str

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF

    def as_headers(self) -> dict[str, str]:
        return {"X-User-Id": str(self.user_id), "X-User-Role": self.role, "X-User-Email": self.email}


def user_from_headers(request: Request) -> UserCtx | None:
    uid, role, email = (request.headers.get(h) for h in ("x-user-id", "x-user-role", "x-user-email"))
    if not uid:
        return None
    if not uid.isdigit() or role not in ROLES or not email:
        raise ApiError(401, "INVALID_IDENTITY", "Identidad de usuario inválida")
    return UserCtx(int(uid), role, email)


def require_user(*roles: str, callers: Iterable[str] = ("api-gateway",)):
    """Dependencia: exige servicio llamador confiable + usuario con uno de los roles."""
    callers = tuple(callers)
    check_caller = require_callers(*callers)

    def dependency(request: Request, _caller: Caller = Depends(check_caller)) -> UserCtx:
        user = user_from_headers(request)
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "Se requiere iniciar sesión")
        if roles and user.role not in roles:
            raise ApiError(403, "FORBIDDEN", "No tiene permisos para esta operación")
        return user

    return dependency


# ----------------------------------------------------------- cliente interno
_transport: httpx.AsyncBaseTransport | None = None  # se reemplaza en pruebas
_client: httpx.AsyncClient | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport, _client
    _transport, _client = transport, None


def service_url(name: str) -> str:
    env = name.upper().replace("-", "_") + "_URL"
    return os.environ.get(env, f"http://127.0.0.1:{DEFAULT_PORTS[name]}").rstrip("/")


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(transport=_transport, follow_redirects=False)
    return _client


class DependencyError(ApiError):
    def __init__(self, callee: str, status: int = 503):
        super().__init__(status, "DEPENDENCY_UNAVAILABLE", f"Servicio interno no disponible: {callee}")
        self.callee = callee


async def call_service(
    callee: str,
    method: str,
    path: str,
    *,
    user: UserCtx | None = None,
    json_body: Any = None,
    params: dict | None = None,
    timeout: float = 3.0,
    extra_headers: dict | None = None,
) -> httpx.Response:
    caller = current_service_var.get() or os.environ.get("SERVICE_NAME", "unknown")
    headers = {
        "X-Service-Name": caller,
        "X-Service-Token": get_secret(f"svc-{caller}-to-{callee}"),
        "X-Correlation-Id": correlation_id_var.get() if correlation_id_var.get() != "-" else uuid.uuid4().hex,
    }
    if user:
        headers.update(user.as_headers())
    if extra_headers:
        headers.update(extra_headers)
    try:
        return await _http().request(
            method, service_url(callee) + path, json=json_body, params=params,
            headers=headers, timeout=httpx.Timeout(timeout),
        )
    except httpx.TimeoutException:
        raise DependencyError(callee, 504)
    except httpx.HTTPError:
        raise DependencyError(callee, 503)


async def call_external(name: str, method: str, url: str, *, timeout: float = 5.0, **kwargs: Any) -> httpx.Response:
    """Llamada a un proveedor externo (sin credenciales internas)."""
    try:
        return await _http().request(method, url, timeout=httpx.Timeout(timeout), **kwargs)
    except httpx.TimeoutException:
        raise DependencyError(name, 504)
    except httpx.HTTPError:
        raise DependencyError(name, 503)


def expect_ok(response: httpx.Response, callee: str) -> Any:
    """Devuelve el JSON si la respuesta es 2xx; si el destino responde 5xx se trata como indisponible."""
    if response.status_code >= 500:
        raise DependencyError(callee)
    if response.status_code >= 400:
        try:
            err = response.json().get("error", {})
        except ValueError:
            err = {}
        raise ApiError(response.status_code, err.get("code", "UPSTREAM_ERROR"), err.get("message", "Operación rechazada"))
    return response.json() if response.content else None
