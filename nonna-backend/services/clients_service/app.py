"""clients (microservicio privado). Autoridad sobre perfil y direcciones (nonna_clients).

Datos RESTRINGIDOS (RUN, correo, teléfono, direcciones). Cada cliente solo accede a su
propio registro: el id se obtiene de la identidad verificada (X-User-Id puesto por el
gateway), nunca de un parámetro enviado por el navegador.
No hay DELETE: el usuario de BD svc_clients no tiene ese permiso (se conserva historial).
"""
from __future__ import annotations

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from common.db import get_engine
from common.service import ApiError, Caller, UserCtx, create_app, require_callers, require_user
from common.tables import addresses, clients
from common.validators import mask_phone, mask_run, normalize_email, validate_phone, validate_run

app = create_app("clients")


def db():
    return get_engine("clients")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClientCreateIn(Strict):
    auth_user_id: int = Field(gt=0)
    email: str
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    run: str | None = None

    _email = field_validator("email")(lambda cls, v: normalize_email(v))
    _phone = field_validator("phone")(lambda cls, v: v and validate_phone(v))
    _run = field_validator("run")(lambda cls, v: v and validate_run(v))


class ProfileIn(Strict):
    """PUT reemplaza la representación editable del perfil. RUN y correo no se editan aquí."""
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    notify_email: bool = True

    _phone = field_validator("phone")(lambda cls, v: v and validate_phone(v))


class AddressIn(Strict):
    street: str = Field(min_length=3, max_length=160)
    commune: str = Field(min_length=2, max_length=80)
    reference: str | None = Field(default=None, max_length=160)
    is_default: bool = False


def profile_dto(row) -> dict:
    return {
        "id": row.id, "first_name": row.first_name, "last_name": row.last_name,
        "email": row.email, "phone": row.phone, "run": row.run, "notify_email": bool(row.notify_email),
    }


def address_dto(row) -> dict:
    return {"id": row.id, "street": row.street, "commune": row.commune,
            "reference": row.reference, "is_default": bool(row.is_default)}


def client_for_user(conn, user_id: int):
    row = conn.execute(select(clients).where(clients.c.auth_user_id == user_id, clients.c.deleted_at.is_(None))).first()
    if row is None:
        raise ApiError(404, "CLIENT_NOT_FOUND", "Perfil de cliente no encontrado")
    return row


# ---------------------------------------------------- API (vía API Gateway)
@app.get("/me")
async def get_profile(user: UserCtx = Depends(require_user("CLIENTE"))):
    def q():
        with db().connect() as conn:
            return profile_dto(client_for_user(conn, user.user_id))
    return await run_in_threadpool(q)


@app.put("/me")
async def put_profile(body: ProfileIn, user: UserCtx = Depends(require_user("CLIENTE"))):
    def q():
        with db().begin() as conn:
            row = client_for_user(conn, user.user_id)
            conn.execute(update(clients).where(clients.c.id == row.id).values(**body.model_dump()))
            return profile_dto(conn.execute(select(clients).where(clients.c.id == row.id)).first())
    return await run_in_threadpool(q)


@app.get("/me/addresses")
async def list_addresses(user: UserCtx = Depends(require_user("CLIENTE"))):
    def q():
        with db().connect() as conn:
            c = client_for_user(conn, user.user_id)
            rows = conn.execute(select(addresses).where(addresses.c.client_id == c.id).order_by(addresses.c.id)).all()
            return [address_dto(r) for r in rows]
    return await run_in_threadpool(q)


@app.post("/me/addresses", status_code=201)
async def add_address(body: AddressIn, user: UserCtx = Depends(require_user("CLIENTE"))):
    def q():
        with db().begin() as conn:
            c = client_for_user(conn, user.user_id)
            count = conn.execute(select(func.count()).select_from(addresses).where(addresses.c.client_id == c.id)).scalar_one()
            if count >= 10:
                raise ApiError(409, "ADDRESS_LIMIT", "Máximo 10 direcciones por cliente")
            is_default = body.is_default or count == 0
            if is_default:
                conn.execute(update(addresses).where(addresses.c.client_id == c.id).values(is_default=False))
            new_id = conn.execute(insert(addresses).values(client_id=c.id, **{**body.model_dump(), "is_default": is_default})).inserted_primary_key[0]
            return address_dto(conn.execute(select(addresses).where(addresses.c.id == new_id)).first())
    return await run_in_threadpool(q)


@app.put("/me/addresses/{address_id}")
async def put_address(address_id: int, body: AddressIn, user: UserCtx = Depends(require_user("CLIENTE"))):
    def q():
        with db().begin() as conn:
            c = client_for_user(conn, user.user_id)
            row = conn.execute(select(addresses).where(addresses.c.id == address_id, addresses.c.client_id == c.id)).first()
            if row is None:  # ajena o inexistente: misma respuesta
                raise ApiError(404, "ADDRESS_NOT_FOUND", "Dirección no encontrada")
            if body.is_default:
                conn.execute(update(addresses).where(addresses.c.client_id == c.id).values(is_default=False))
            conn.execute(update(addresses).where(addresses.c.id == address_id).values(**body.model_dump()))
            return address_dto(conn.execute(select(addresses).where(addresses.c.id == address_id)).first())
    return await run_in_threadpool(q)


@app.get("/admin/clients")
async def admin_list(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _: UserCtx = Depends(require_user("ADMIN")),
):
    """Listado administrativo con RUN y teléfono enmascarados (mínimo necesario)."""
    def q():
        with db().connect() as conn:
            total = conn.execute(select(func.count()).select_from(clients).where(clients.c.deleted_at.is_(None))).scalar_one()
            rows = conn.execute(select(clients).where(clients.c.deleted_at.is_(None)).order_by(clients.c.id)
                                .limit(page_size).offset((page - 1) * page_size)).all()
            return {"page": page, "page_size": page_size, "total": total, "items": [{
                "id": r.id, "first_name": r.first_name, "last_name": r.last_name, "email": r.email,
                "run": mask_run(r.run), "phone": mask_phone(r.phone), "created_at": r.created_at.isoformat(),
            } for r in rows]}
    return await run_in_threadpool(q)


# --------------------------------------------- API interna (solo servicios)
@app.post("/internal/clients", status_code=201)
async def internal_create(body: ClientCreateIn, _: Caller = Depends(require_callers("auth"))):
    def q():
        with db().begin() as conn:
            try:
                cid = conn.execute(insert(clients).values(**body.model_dump())).inserted_primary_key[0]
            except IntegrityError:
                raise ApiError(409, "CLIENT_EXISTS", "Ya existe un cliente con ese correo o RUN")
            return {"id": cid}
    return await run_in_threadpool(q)


@app.get("/internal/clients/by-user/{auth_user_id}")
async def internal_by_user(auth_user_id: int, _: Caller = Depends(require_callers("orders", "payments", "graphql"))):
    def q():
        with db().connect() as conn:
            row = client_for_user(conn, auth_user_id)
            return {"id": row.id, "first_name": row.first_name}
    return await run_in_threadpool(q)


@app.get("/internal/clients/{client_id}/addresses/{address_id}")
async def internal_address(client_id: int, address_id: int, _: Caller = Depends(require_callers("orders"))):
    """orders copia la dirección al pedido; la consulta exige que pertenezca al cliente."""
    def q():
        with db().connect() as conn:
            row = conn.execute(select(addresses).where(addresses.c.id == address_id, addresses.c.client_id == client_id)).first()
            if row is None:
                raise ApiError(404, "ADDRESS_NOT_FOUND", "Dirección no encontrada")
            return address_dto(row)
    return await run_in_threadpool(q)


@app.get("/internal/clients")
async def internal_batch(ids: str = Query(..., max_length=600), _: Caller = Depends(require_callers("graphql"))):
    """Lote para el GraphQL Gateway (evita N+1). Solo nombre y teléfono, nada más."""
    try:
        id_list = sorted({int(x) for x in ids.split(",") if x})[:100]
    except ValueError:
        raise ApiError(400, "INVALID_IDS", "ids inválidos")

    def q():
        with db().connect() as conn:
            rows = conn.execute(select(clients.c.id, clients.c.first_name, clients.c.last_name, clients.c.phone)
                                .where(clients.c.id.in_(id_list))).all()
            return [{"id": r.id, "first_name": r.first_name, "last_name": r.last_name, "phone": r.phone} for r in rows]
    return await run_in_threadpool(q)
