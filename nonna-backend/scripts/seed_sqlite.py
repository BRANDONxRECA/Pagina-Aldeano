"""Crea las 5 bases en SQLite con el mismo esquema y datos ficticios del script MySQL.

Se usa para pruebas automatizadas y para levantar el sistema sin MySQL
(``python scripts/run_local.py --sqlite``). Las contraseñas de prueba son:
    javiera@example.cl / Cliente123   matias@example.cl / Cliente123
    cocina@lanonna.test / Trabajador123   admin@lanonna.test / Admin12345
(Solo datos de prueba; en MySQL se usan los hashes del script del equipo.)
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

import bcrypt
from sqlalchemy import create_engine, insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import tables as t  # noqa: E402

TEST_PASSWORDS = {
    "javiera@example.cl": "Cliente123", "matias@example.cl": "Cliente123",
    "cocina@lanonna.test": "Trabajador123", "admin@lanonna.test": "Admin12345",
}


def seed(data_dir: Path) -> dict[str, str]:
    data_dir.mkdir(parents=True, exist_ok=True)
    urls = {}
    rounds = int(os.environ.get("BCRYPT_ROUNDS", "12"))
    for svc, md in t.METADATA_BY_SERVICE.items():
        path = data_dir / f"nonna_{svc}.db"
        if path.exists():
            path.unlink()
        url = f"sqlite:///{path.as_posix()}"
        engine = create_engine(url)
        md.create_all(engine)
        with engine.begin() as c:
            if svc == "auth":
                h = {e: bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds)).decode() for e, p in TEST_PASSWORDS.items()}
                c.execute(insert(t.users), [
                    {"id": 1, "email": "javiera@example.cl", "password_hash": h["javiera@example.cl"], "role": "CLIENTE"},
                    {"id": 2, "email": "matias@example.cl", "password_hash": h["matias@example.cl"], "role": "CLIENTE"},
                    {"id": 3, "email": "cocina@lanonna.test", "password_hash": h["cocina@lanonna.test"], "role": "TRABAJADOR"},
                    {"id": 4, "email": "admin@lanonna.test", "password_hash": h["admin@lanonna.test"], "role": "ADMIN"},
                ])
                c.execute(insert(t.staff_profiles), [
                    {"user_id": 3, "first_name": "Carla", "last_name": "Soto", "position": "Cocina", "hired_at": date(2024, 3, 1)},
                    {"user_id": 4, "first_name": "Andrés", "last_name": "Muñoz", "position": "Administración", "hired_at": date(2022, 1, 10)},
                ])
            elif svc == "clients":
                c.execute(insert(t.clients), [
                    {"id": 1, "auth_user_id": 1, "run": "11111111-1", "first_name": "Javiera", "last_name": "Rojas", "email": "javiera@example.cl", "phone": "+56911111111"},
                    {"id": 2, "auth_user_id": 2, "run": "22222222-2", "first_name": "Matías", "last_name": "Pérez", "email": "matias@example.cl", "phone": "+56922222222"},
                ])
                c.execute(insert(t.addresses), [
                    {"client_id": 1, "street": "Calle Ficticia 123", "commune": "Maipú", "reference": "Casa azul", "is_default": True},
                    {"client_id": 2, "street": "Pasaje Ejemplo 456", "commune": "Maipú", "reference": None, "is_default": True},
                ])
            elif svc == "inventory":
                c.execute(insert(t.categories), [{"id": 1, "name": "Ravioles"}, {"id": 2, "name": "Lasañas"}, {"id": 3, "name": "Tallarines"}])
                prods = [
                    (1, 1, "RAV-RICO", "Ravioles de ricotta y espinaca", "Mantequilla salvia y parmesano.", 7900),
                    (2, 1, "RAV-OSOB", "Ravioles de osobuco", "Jugo reducido y gremolata.", 9500),
                    (3, 1, "RAV-HONG", "Ravioles de hongos silvestres", "Crema y trufa negra.", 8700),
                    (4, 2, "LAS-BOLO", "Lasaña a la bolognesa", "Ragú de vacuno y bechamel casera.", 8900),
                    (5, 2, "LAS-VERD", "Lasaña de verduras de estación", "Zapallo italiano y berenjena.", 7800),
                    (6, 2, "LAS-POLL", "Lasaña de pollo al pesto", "Pesto de albahaca y piñones.", 8300),
                    (7, 3, "TAL-PEST", "Tallarines al pesto genovés", "Piñones tostados y parmesano.", 6900),
                    (8, 3, "TAL-CARB", "Tallarines a la carbonara", "Panceta, yema y pecorino.", 7400),
                    (9, 3, "TAL-POMO", "Tallarines al pomodoro", "Tomate fresco y albahaca.", 6500),
                ]
                c.execute(insert(t.products), [dict(zip(("id", "category_id", "sku", "name", "description", "price_clp"), p)) for p in prods])
                stock = {1: 30, 2: 20, 3: 25, 4: 20, 5: 25, 6: 20, 7: 40, 8: 35, 9: 40}
                c.execute(insert(t.stock), [{"product_id": k, "quantity_available": v, "quantity_reserved": 0} for k, v in stock.items()])
            elif svc == "orders":
                c.execute(insert(t.orders), [
                    {"id": 1, "order_code": "P-1042", "client_id": 1, "status": "ENTREGADO", "delivery_type": "DESPACHO", "delivery_address": "Calle Ficticia 123, Maipú", "subtotal_clp": 22700, "delivery_fee_clp": 0, "total_clp": 22700, "created_at": datetime(2026, 9, 2, 13, 10)},
                    {"id": 2, "order_code": "P-1058", "client_id": 1, "status": "ENTREGADO", "delivery_type": "RETIRO", "delivery_address": None, "subtotal_clp": 19000, "delivery_fee_clp": 0, "total_clp": 19000, "created_at": datetime(2026, 9, 10, 20, 5)},
                    {"id": 3, "order_code": "P-1093", "client_id": 2, "status": "PREPARANDO", "delivery_type": "DESPACHO", "delivery_address": "Pasaje Ejemplo 456, Maipú", "subtotal_clp": 15200, "delivery_fee_clp": 0, "total_clp": 15200, "created_at": datetime(2026, 9, 15, 19, 40)},
                    {"id": 4, "order_code": "P-1094", "client_id": 2, "status": "LISTO", "delivery_type": "RETIRO", "delivery_address": None, "subtotal_clp": 16600, "delivery_fee_clp": 0, "total_clp": 16600, "created_at": datetime(2026, 9, 14, 12, 30)},
                ])
                c.execute(insert(t.order_items), [
                    {"order_id": 1, "product_id": 4, "product_name": "Lasaña a la bolognesa", "unit_price_clp": 8900, "quantity": 1},
                    {"order_id": 1, "product_id": 7, "product_name": "Tallarines al pesto genovés", "unit_price_clp": 6900, "quantity": 2},
                    {"order_id": 2, "product_id": 2, "product_name": "Ravioles de osobuco", "unit_price_clp": 9500, "quantity": 2},
                    {"order_id": 3, "product_id": 9, "product_name": "Tallarines al pomodoro", "unit_price_clp": 6500, "quantity": 1},
                    {"order_id": 3, "product_id": 3, "product_name": "Ravioles de hongos silvestres", "unit_price_clp": 8700, "quantity": 1},
                    {"order_id": 4, "product_id": 6, "product_name": "Lasaña de pollo al pesto", "unit_price_clp": 8300, "quantity": 2},
                ])
            elif svc == "payments":
                c.execute(insert(t.payments), [
                    {"id": i, "order_id": i, "client_id": cid, "amount_clp": amt, "method": "WEBPAY", "provider_token": f"tok_test_000{i}", "status": "AUTORIZADO", "idempotency_key": f"seed-pay-000{i}"}
                    for i, cid, amt in ((1, 1, 22700), (2, 1, 19000), (3, 2, 15200), (4, 2, 16600))])
                c.execute(insert(t.receipts), [{"payment_id": i, "receipt_number": f"B-00000{i}"} for i in range(1, 5)])
        engine.dispose()
        urls[svc] = url
    return urls


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data"
    for svc, url in seed(out).items():
        print(svc, url)
