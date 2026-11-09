"""Fija contraseñas de PRUEBA conocidas para los 4 usuarios ficticios del seed en MySQL.

El script SQL del equipo trae hashes bcrypt cuyas contraseñas están en su README. Si no
las tienen a mano, ejecuten esto (usa el usuario svc_auth y su secreto db-auth-password):

    python scripts/set_test_passwords.py
"""
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.db import get_engine  # noqa: E402
from common.tables import users  # noqa: E402
from scripts.seed_sqlite import TEST_PASSWORDS  # noqa: E402

with get_engine("auth").begin() as conn:
    for email, pwd in TEST_PASSWORDS.items():
        h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt(12)).decode()
        n = conn.execute(update(users).where(users.c.email == email).values(password_hash=h, failed_attempts=0, locked_until=None)).rowcount
        print(f"{email}: {'actualizado' if n else 'no existe'}")
