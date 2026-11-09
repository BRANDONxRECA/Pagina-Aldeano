"""SecretProvider: resuelve referencias simbólicas de secretos.

Orden de búsqueda para la referencia ``svc-orders-to-inventory``:
  1. Variable de entorno ``SECRET_SVC_ORDERS_TO_INVENTORY``.
  2. Archivo ``$SECRETS_DIR/svc-orders-to-inventory`` (compatible con Docker secrets).

El código solo conoce referencias, nunca valores. Si el secreto no existe el
servicio falla cerrado (no inventa un valor por defecto). Los valores se cachean
un tiempo corto para permitir rotación sin reiniciar.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

_CACHE: dict[str, tuple[float, str]] = {}
CACHE_TTL_SECONDS = 60


class SecretNotFound(RuntimeError):
    def __init__(self, ref: str):
        # El mensaje incluye la referencia, nunca un valor.
        super().__init__(f"secreto no disponible: {ref}")
        self.ref = ref


def _secrets_dir() -> Path:
    default = Path(__file__).resolve().parent.parent / "secrets"
    return Path(os.environ.get("SECRETS_DIR", default))


def get_secret(ref: str) -> str:
    now = time.monotonic()
    cached = _CACHE.get(ref)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    env_name = "SECRET_" + ref.upper().replace("-", "_")
    value = os.environ.get(env_name)
    if value is None:
        path = _secrets_dir() / ref
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SecretNotFound(ref)
    _CACHE[ref] = (now, value)
    return value


def clear_cache() -> None:
    _CACHE.clear()
