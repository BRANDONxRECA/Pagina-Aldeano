"""Conexión a la base propia de cada servicio.

Cada microservicio usa SOLO su base (nonna_<servicio>) y su propio usuario MySQL
(svc_<servicio>), creado por db/nonna_workbench_setup.sql con permisos mínimos.
La contraseña se obtiene del SecretProvider con la referencia ``db-<servicio>-password``.

Para pruebas automatizadas se puede definir ``<SERVICIO>_DATABASE_URL`` (por ejemplo
una base SQLite temporal); en ese caso no se usa ninguna contraseña.
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from common.secrets import get_secret

_ENGINES: dict[str, Engine] = {}


def database_url(service: str) -> str:
    override = os.environ.get(f"{service.upper()}_DATABASE_URL")
    if override:
        return override
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "3306")
    user = f"svc_{service}"
    password = quote_plus(get_secret(f"db-{service}-password"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/nonna_{service}?charset=utf8mb4"


def get_engine(service: str) -> Engine:
    if service not in _ENGINES:
        url = database_url(service)
        kwargs: dict = {"future": True}
        if url.startswith("mysql"):
            kwargs.update(pool_pre_ping=True, pool_recycle=1800, pool_size=10, max_overflow=10)
        else:
            kwargs.update(connect_args={"check_same_thread": False, "timeout": 30})
        _ENGINES[service] = create_engine(url, **kwargs)
    return _ENGINES[service]


def reset_engines() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
