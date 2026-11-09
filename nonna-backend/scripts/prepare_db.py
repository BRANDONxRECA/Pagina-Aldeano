"""Prepara el script MySQL con contraseñas FUERTES sin ponerlas en el repositorio.

    python scripts/prepare_db.py

1. Genera (si faltan) los secretos de secrets/, incluidas las contraseñas de svc_*.
2. Escribe en db/generated/ (ignorado por git):
     setup.sql         -> para MySQL Workbench (usuarios @'localhost')
     setup-docker.sql  -> para docker-compose (usuarios @'%', se conectan desde otros contenedores)
   reemplazando los marcadores CAMBIAR_* de db/nonna_workbench_setup.sql.
3. Reemplaza los hashes de los 4 usuarios ficticios del seed por los de las contraseñas
   de prueba documentadas en el README (Cliente123, Trabajador123, Admin12345).

No imprime ningún valor secreto.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.gen_secrets import generate  # noqa: E402
from scripts.seed_sqlite import TEST_PASSWORDS  # noqa: E402

SERVICES = ("auth", "clients", "inventory", "orders", "payments")


def main() -> int:
    secrets_dir = ROOT / "secrets"
    generate(secrets_dir)
    source = (ROOT / "db" / "nonna_workbench_setup.sql").read_text(encoding="utf-8")
    sql = source
    for svc in SERVICES:
        pwd = (secrets_dir / f"db-{svc}-password").read_text(encoding="utf-8").strip()
        if "'" in pwd or "\\" in pwd:
            print(f"La contraseña de {svc} tiene caracteres no válidos para SQL; regenérela.")
            return 1
        sql = sql.replace(f"'CAMBIAR_{svc.upper()}'", f"'{pwd}'")
    if "'CAMBIAR_" in sql:
        print("Quedaron marcadores CAMBIAR_ sin reemplazar.")
        return 1

    # Hashes de prueba conocidos para los usuarios ficticios del seed.
    for email, pwd in TEST_PASSWORDS.items():
        start = sql.find(f"'{email}',")
        if start == -1:
            continue
        hash_start = sql.find("'$2b$", start)
        hash_end = sql.find("'", hash_start + 1)
        new_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt(12)).decode()
        sql = sql[:hash_start + 1] + new_hash + sql[hash_end:]

    out = ROOT / "db" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    header = "-- GENERADO por scripts/prepare_db.py. Contiene contraseñas: NO subir a git.\n"
    (out / "setup.sql").write_text(header + sql, encoding="utf-8")
    (out / "setup-docker.sql").write_text(header + sql.replace("@'localhost'", "@'%'"), encoding="utf-8")
    print("Listo: db/generated/setup.sql (Workbench) y db/generated/setup-docker.sql (Docker).")
    print("Las contraseñas de svc_* quedaron en secrets/db-<servicio>-password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
