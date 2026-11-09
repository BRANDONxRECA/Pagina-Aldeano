"""Genera los secretos LOCALES de desarrollo en ./secrets (ignorado por git).

Uso:
    python scripts/gen_secrets.py                      # genera claves y tokens
    python scripts/gen_secrets.py --db-from-sql mi_script.sql
        # solo si YA crearon los usuarios svc_* con contraseñas propias: las copia desde ese SQL

Cada par llamador->destino recibe un token distinto (mínimo privilegio): si se filtra
el de payments->orders no sirve para llamar a inventory. Rotar = volver a ejecutar
el script (o reemplazar un archivo) y reiniciar/esperar 60 s de caché.
"""
from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Quién puede llamar a quién (única fuente de verdad de la red interna).
SERVICE_PAIRS = [
    ("api-gateway", "auth"), ("api-gateway", "clients"), ("api-gateway", "inventory"),
    ("api-gateway", "orders"), ("api-gateway", "payments"), ("api-gateway", "graphql"),
    ("auth", "clients"),
    ("orders", "inventory"), ("orders", "clients"),
    ("payments", "orders"), ("payments", "clients"),
    ("graphql", "orders"), ("graphql", "inventory"), ("graphql", "payments"),
    ("graphql", "clients"), ("graphql", "analytics"),
    ("analytics", "orders"),
]


def generate(target: Path, db_sql: Path | None = None, overwrite: bool = False) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    written = []

    def put(name: str, value: str):
        path = target / name
        if path.exists() and not overwrite:
            return
        path.write_text(value, encoding="utf-8")
        written.append(name)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    if overwrite or not (target / "jwt-private-key").exists():
        put("jwt-private-key", private_pem)
        (target / "jwt-public-key").write_text(public_pem, encoding="utf-8")
        written.append("jwt-public-key")

    for caller, callee in SERVICE_PAIRS:
        put(f"svc-{caller}-to-{callee}", secrets.token_urlsafe(32))
    put("payments-webhook-secret", secrets.token_urlsafe(32))
    put("provider-api-key", secrets.token_urlsafe(24))
    put("mysql-root-password", secrets.token_urlsafe(24))
    for svc in ("auth", "clients", "inventory", "orders", "payments"):
        if not db_sql:  # contraseña fuerte para el usuario svc_<svc> (la usa scripts/prepare_db.py)
            put(f"db-{svc}-password", secrets.token_urlsafe(24))

    if db_sql:
        text = db_sql.read_text(encoding="utf-8")
        for svc, pwd in re.findall(r"CREATE USER 'svc_(\w+)'@'[^']+'\s+IDENTIFIED BY '([^']+)'", text):
            if not pwd.startswith("CAMBIAR_"):
                put(f"db-{svc}-password", pwd)
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent / "secrets"))
    parser.add_argument("--db-from-sql", type=Path)
    parser.add_argument("--overwrite", action="store_true", help="rota todos los secretos")
    args = parser.parse_args()
    names = generate(Path(args.dir), args.db_from_sql, args.overwrite)
    # Se imprimen solo nombres (referencias), nunca valores.
    print(f"{len(names)} secretos escritos en {args.dir}:", file=sys.stderr)
    for n in names:
        print("  -", n, file=sys.stderr)
