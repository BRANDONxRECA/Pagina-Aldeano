"""Auth Service (privado). Autoridad sobre credenciales, roles y sesiones (nonna_auth).

- Contraseñas: bcrypt (hash adaptativo con sal). Nunca se devuelven.
- Access token: JWT RS256 de 15 min. La clave privada solo la tiene este servicio
  (referencia ``jwt-private-key``); el gateway valida con la pública.
- Refresh token: aleatorio, se guarda solo su SHA-256, se rota en cada uso y se
  puede revocar (logout).
- Bloqueo temporal tras 5 intentos fallidos.
"""
from __future__ import annotations

import hashlib
import os
import secrets as pysecrets
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from common.db import get_engine
from common.secrets import get_secret
from common.service import (
    ApiError, Caller, UserCtx, call_service, create_app, expect_ok, get_logger,
    require_callers, require_user,
)
from common.tables import refresh_tokens, staff_profiles, users
from common.validators import normalize_email, validate_phone, validate_run

app = create_app("auth")
log = get_logger("auth")

ACCESS_TTL = timedelta(minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", "15")))
REFRESH_TTL = timedelta(days=int(os.environ.get("REFRESH_TOKEN_DAYS", "7")))
MAX_FAILED = 5
LOCK_TIME = timedelta(minutes=15)
BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "12"))
ISSUER, AUDIENCE = "nonna-auth", "nonna-api"
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(4)).decode()


def db():
    return get_engine("auth")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------- modelos
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PasswordMixin(Strict):
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("la contraseña debe combinar letras y números")
        return v


class RegisterIn(PasswordMixin):
    email: str = Field(max_length=190)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    run: str | None = Field(default=None, max_length=12)

    _email = field_validator("email")(lambda cls, v: normalize_email(v))
    _phone = field_validator("phone")(lambda cls, v: v and validate_phone(v))
    _run = field_validator("run")(lambda cls, v: v and validate_run(v))


class StaffIn(PasswordMixin):
    email: str = Field(max_length=190)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    position: str = Field(min_length=2, max_length=60)
    role: str = Field(pattern="^(TRABAJADOR|ADMIN)$")

    _email = field_validator("email")(lambda cls, v: normalize_email(v))


class LoginIn(Strict):
    email: str = Field(max_length=190)
    password: str = Field(min_length=1, max_length=72)


class RefreshIn(Strict):
    refresh_token: str = Field(min_length=20, max_length=200)


# --------------------------------------------------------------- tokens
def issue_tokens(user_row) -> dict:
    issued = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_row.id), "role": user_row.role, "email": user_row.email,
        "iss": ISSUER, "aud": AUDIENCE, "iat": issued, "exp": issued + ACCESS_TTL,
        "jti": uuid.uuid4().hex,
    }
    access = jwt.encode(claims, get_secret("jwt-private-key"), algorithm="RS256", headers={"kid": "nonna-1"})
    refresh = pysecrets.token_urlsafe(48)
    with db().begin() as conn:
        conn.execute(insert(refresh_tokens).values(
            user_id=user_row.id, token_hash=sha256(refresh), expires_at=now() + REFRESH_TTL))
    return {
        "access_token": access, "token_type": "Bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()), "refresh_token": refresh,
        "user": {"id": user_row.id, "email": user_row.email, "role": user_row.role},
    }


# ---------------------------------------------------------------- rutas
@app.post("/auth/register", status_code=201)
async def register(body: RegisterIn, _: Caller = Depends(require_callers("api-gateway"))):
    hashed = await run_in_threadpool(hash_password, body.password)

    def create_user():
        with db().begin() as conn:
            try:
                return conn.execute(insert(users).values(email=body.email, password_hash=hashed, role="CLIENTE")).inserted_primary_key[0]
            except IntegrityError:
                raise ApiError(409, "EMAIL_TAKEN", "El correo ya está registrado")

    user_id = await run_in_threadpool(create_user)
    # El perfil (datos personales) vive en clients: auth no lo guarda.
    try:
        resp = await call_service("clients", "POST", "/internal/clients", json_body={
            "auth_user_id": user_id, "email": body.email, "first_name": body.first_name,
            "last_name": body.last_name, "phone": body.phone, "run": body.run,
        })
        expect_ok(resp, "clients")
    except ApiError as exc:
        # Compensación: la cuenta queda inactiva y se libera el correo para reintentar.
        def deactivate():
            with db().begin() as conn:
                conn.execute(update(users).where(users.c.id == user_id).values(
                    active=False, email=f"void-{user_id}-{pysecrets.token_hex(4)}@invalid.local"))
        await run_in_threadpool(deactivate)
        log.warning("register_compensated", extra={"fields": {"user_id": user_id, "reason": exc.code}})
        if exc.status in (409, 422):
            raise
        raise ApiError(503, "REGISTRATION_UNAVAILABLE", "No fue posible completar el registro, intente más tarde")
    return {"id": user_id, "email": body.email, "role": "CLIENTE"}


@app.post("/auth/login")
async def login(body: LoginIn, _: Caller = Depends(require_callers("api-gateway"))):
    email = body.email.strip().lower()

    def do_login():
        with db().begin() as conn:
            row = conn.execute(select(users).where(users.c.email == email).with_for_update()).first()
            if row is None:
                check_password(body.password, _DUMMY_HASH)  # tiempo similar: no revela si el correo existe
                raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")
            if not row.active:
                raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")
            if row.locked_until and row.locked_until > now():
                raise ApiError(423, "ACCOUNT_LOCKED", "Cuenta bloqueada temporalmente por intentos fallidos")
            if not check_password(body.password, row.password_hash):
                failed = row.failed_attempts + 1
                values = {"failed_attempts": failed}
                if failed >= MAX_FAILED:
                    values = {"failed_attempts": 0, "locked_until": now() + LOCK_TIME}
                conn.execute(update(users).where(users.c.id == row.id).values(**values))
                return None
            conn.execute(update(users).where(users.c.id == row.id).values(failed_attempts=0, locked_until=None))
            return row

    row = await run_in_threadpool(do_login)
    if row is None:
        raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")
    return await run_in_threadpool(issue_tokens, row)


@app.post("/auth/refresh")
async def refresh(body: RefreshIn, _: Caller = Depends(require_callers("api-gateway"))):
    def rotate():
        with db().begin() as conn:
            tok = conn.execute(select(refresh_tokens).where(
                refresh_tokens.c.token_hash == sha256(body.refresh_token)).with_for_update()).first()
            if tok is None or tok.revoked_at is not None or tok.expires_at < now():
                raise ApiError(401, "INVALID_REFRESH", "Sesión expirada, inicie sesión nuevamente")
            conn.execute(update(refresh_tokens).where(refresh_tokens.c.id == tok.id).values(revoked_at=now()))
            user = conn.execute(select(users).where(users.c.id == tok.user_id)).first()
            if user is None or not user.active:
                raise ApiError(401, "INVALID_REFRESH", "Sesión expirada, inicie sesión nuevamente")
            return user

    user = await run_in_threadpool(rotate)
    return await run_in_threadpool(issue_tokens, user)


@app.post("/auth/logout", status_code=204)
async def logout(body: RefreshIn, _: Caller = Depends(require_callers("api-gateway"))):
    def revoke():
        with db().begin() as conn:
            conn.execute(update(refresh_tokens).where(
                refresh_tokens.c.token_hash == sha256(body.refresh_token),
                refresh_tokens.c.revoked_at.is_(None)).values(revoked_at=now()))
    await run_in_threadpool(revoke)


@app.get("/auth/me")
async def me(user: UserCtx = Depends(require_user())):
    return {"id": user.user_id, "email": user.email, "role": user.role}


@app.post("/auth/staff", status_code=201)
async def create_staff(body: StaffIn, admin: UserCtx = Depends(require_user("ADMIN"))):
    hashed = await run_in_threadpool(hash_password, body.password)

    def create():
        with db().begin() as conn:
            try:
                uid = conn.execute(insert(users).values(email=body.email, password_hash=hashed, role=body.role)).inserted_primary_key[0]
            except IntegrityError:
                raise ApiError(409, "EMAIL_TAKEN", "El correo ya está registrado")
            conn.execute(insert(staff_profiles).values(
                user_id=uid, first_name=body.first_name, last_name=body.last_name,
                position=body.position, hired_at=date.today()))
            return uid

    uid = await run_in_threadpool(create)
    log.info("staff_created", extra={"fields": {"by": admin.user_id, "user_id": uid, "role_new": body.role}})
    return {"id": uid, "email": body.email, "role": body.role}
