"""Ejecuta los 6 casos de validación del Módulo 7 (y el flujo de compra) contra el sistema
EN EJECUCIÓN, con la base que esté usando (MySQL real o SQLite), y guarda la evidencia.

    python scripts/run_local.py start          # con MySQL (o --sqlite)
    python scripts/security_checks.py --db "MySQL 8.0.36 local"

Resultado: docs/evidencias/seguridad-<fecha>.md  (tabla caso | esperado | obtenido | OK)
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.secrets import get_secret  # noqa: E402

rows: list[tuple] = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows


def check(case: str, desc: str, expected, got, component: str):
    ok = got in expected if isinstance(expected, (tuple, list, set)) else got == expected
    rows.append((case, desc, expected, got, "✅" if ok else "❌", component))
    print(f"{'OK ' if ok else 'FALLA'} {case} {desc}: esperado {expected}, obtenido {got}")


def main(args) -> int:
    gw = httpx.Client(base_url=args.gateway, timeout=10)

    def login(email, pwd):
        r = gw.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        r.raise_for_status()
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    jav = login("javiera@example.cl", args.client_password)
    mat = login("matias@example.cl", args.client_password)

    # 1. Catálogo anónimo
    r = gw.get("/api/v1/products")
    check("M7-1", "GET catálogo sin sesión", 200, r.status_code, "api-gateway (S07 ANON) + inventory")
    check("M7-1", "catálogo sin stock exacto ni SKU", True,
          r.status_code == 200 and all(set(p) == {"id", "name", "description", "category", "price_clp", "available"} for p in r.json()), "inventory (DTO)")
    # 2. Protegida sin sesión válida
    check("M7-2", "GET /orders sin token", 401, gw.get("/api/v1/orders").status_code, "api-gateway")
    check("M7-2", "GET /orders con token falso", 401, gw.get("/api/v1/orders", headers={"Authorization": "Bearer x.y.z"}).status_code, "api-gateway")
    # 3. Administración con rol sin permiso
    check("M7-3", "CLIENTE DELETE /products/1", 403, gw.delete("/api/v1/products/1", headers=jav).status_code, "api-gateway + inventory")
    spoof = {"X-User-Id": "4", "X-User-Role": "ADMIN", "X-User-Email": "admin@lanonna.test"}
    check("M7-3", "CLIENTE + cabecera X-User-Role: ADMIN falsificada", 403,
          gw.delete("/api/v1/products/1", headers=jav | spoof).status_code, "api-gateway (descarta cabeceras)")
    # 4. Pedido ajeno
    r = gw.get("/api/v1/orders/P-1042", headers=mat)
    check("M7-4", "Matías GET pedido P-1042 de Javiera", 404, r.status_code, "orders (propiedad)")
    check("M7-4", "respuesta sin datos del pedido ajeno", True, "Ficticia" not in r.text and "22700" not in r.text, "orders")
    q = '{ pedido(codigo: "P-1042") { codigo direccionEntrega } }'
    r = gw.post("/api/v1/graphql", headers=mat, json={"query": q})
    check("M7-4", "Matías GraphQL pedido(P-1042)", None, r.json().get("data", {}).get("pedido"), "graphql (propiedad)")
    # 5. Acceso directo sin identidad autorizada
    for name, port in (("inventory", 8003), ("orders", 8004), ("payments", 8005), ("graphql", 8006)):
        try:
            code = httpx.get(f"http://127.0.0.1:{port}/health", timeout=3).status_code  # health es público
            path = {"inventory": "/products", "orders": "/orders", "payments": "/payments/1", "graphql": "/graphql"}[name]
            method = "POST" if name == "graphql" else "GET"
            code = httpx.request(method, f"http://127.0.0.1:{port}{path}", json={"query": "{__typename}"} if name == "graphql" else None,
                                 headers={"X-User-Id": "4", "X-User-Role": "ADMIN", "X-User-Email": "a@a.cl"}, timeout=3).status_code
        except httpx.HTTPError:
            code = "sin conexión (red privada)"
        check("M7-5", f"llamada directa a {name} sin credencial de servicio", (401, "sin conexión (red privada)"), code, name)
    r = httpx.post("http://127.0.0.1:8003/internal/reservations", timeout=3, headers={
        "X-Service-Name": "api-gateway", "X-Service-Token": get_secret("svc-api-gateway-to-inventory")},
        json={"order_id": 999999, "items": [{"product_id": 1, "quantity": 1}]})
    check("M7-5", "credencial del gateway usada contra ruta interna de orders→inventory", 403, r.status_code, "inventory (autorización por llamador)")
    # 6. Pago con datos alterados
    r = gw.post("/api/v1/orders", headers=jav, json={"items": [{"product_id": 7, "quantity": 1}], "delivery_type": "RETIRO"})
    code = r.json()["order_code"]
    r = gw.post("/api/v1/payments", headers=jav | {"Idempotency-Key": uuid.uuid4().hex[:20]}, json={"order_code": code, "method": "WEBPAY", "amount_clp": 1})
    check("M7-6", "pago con monto enviado por el navegador", 422, r.status_code, "payments (extra=forbid)")
    pay = gw.post("/api/v1/payments", headers=jav | {"Idempotency-Key": uuid.uuid4().hex[:20]}, json={"order_code": code, "method": "WEBPAY"}).json()
    token = pay["redirect_url"].rsplit("/", 1)[1]
    check("M7-6", "cliente PATCH estado=PAGADO", 403, gw.patch(f"/api/v1/orders/{code}/status", headers=jav, json={"status": "PAGADO"}).status_code, "api-gateway + orders")
    ev = json.dumps({"event_id": "evt_chk_" + uuid.uuid4().hex[:8], "token": token, "result": "AUTHORIZED", "amount": pay["amount_clp"]}).encode()
    check("M7-6", "aviso de pago sin firma", 401, gw.post("/api/v1/payments/webhook", content=ev, headers={"Content-Type": "application/json"}).status_code, "payments (HMAC)")
    bad = json.dumps({"event_id": "evt_chk_" + uuid.uuid4().hex[:8], "token": token, "result": "AUTHORIZED", "amount": 1}).encode()
    sig = hmac.new(get_secret("payments-webhook-secret").encode(), bad, hashlib.sha256).hexdigest()
    check("M7-6", "aviso firmado con monto alterado", 400, gw.post("/api/v1/payments/webhook", content=bad,
          headers={"Content-Type": "application/json", "X-Provider-Signature": sig}).status_code, "payments (monto oficial)")
    check("M7-6", "pedido sigue impago", "PENDIENTE_PAGO", gw.get(f"/api/v1/orders/{code}", headers=jav).json()["status"], "orders")
    # Flujo válido: el aviso correcto sí paga, y repetido no duplica
    sig = hmac.new(get_secret("payments-webhook-secret").encode(), ev, hashlib.sha256).hexdigest()
    h = {"Content-Type": "application/json", "X-Provider-Signature": sig}
    r1 = gw.post("/api/v1/payments/webhook", content=ev, headers=h).json()
    r2 = gw.post("/api/v1/payments/webhook", content=ev, headers=h).json()
    check("M10", "aviso válido marca PAGADO y emite boleta", True, bool(r1.get("receipt_number")), "payments + orders + inventory")
    check("M10", "aviso repetido no duplica", True, r2.get("duplicate") is True, "payments (event_id único)")
    check("M10", "estado final del pedido", "PAGADO", gw.get(f"/api/v1/orders/{code}", headers=jav).json()["status"], "orders")
    gw.post(f"/api/v1/orders/{code}/cancel", headers=login("admin@lanonna.test", args.admin_password))  # deja el stock como estaba

    ok = all(r[4] == "✅" for r in rows)
    out = ROOT / "docs" / "evidencias" / f"seguridad-{datetime.now():%Y%m%d-%H%M%S}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Evidencia de seguridad (ejecución real)", "",
             f"- Fecha: {datetime.now().isoformat(timespec='seconds')}",
             f"- Base de datos: **{args.db}**", f"- Gateway: {args.gateway}",
             f"- Resultado: **{sum(r[4] == '✅' for r in rows)}/{len(rows)}** verificaciones correctas", "",
             "| Caso | Verificación | Esperado | Obtenido | OK | Componente que verifica |", "|---|---|---|---|---|---|"]
    lines += [f"| {c} | {d} | {e} | {g} | {k} | {comp} |" for c, d, e, g, k, comp in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{'TODO OK' if ok else 'HAY FALLAS'} -> {out.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--gateway", default="http://127.0.0.1:8000")
    p.add_argument("--db", default="MySQL (indicar versión)")
    p.add_argument("--client-password", default="Cliente123")
    p.add_argument("--admin-password", default="Admin12345")
    sys.exit(main(p.parse_args()))
