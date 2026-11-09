"""analytics (servicio privado, separado de las transacciones).

Origen de datos: API interna de orders (/internal/sales-source), que entrega ventas sin
datos personales. No lee la base de orders directamente.
Actualización: bajo demanda con caché de ANALYTICS_CACHE_SECONDS (retraso aceptado: 60 s).
Permisos: solo el GraphQL Gateway puede llamarlo; el GraphQL solo expone el reporte a ADMIN.
Ver docs/ADR-001-analitica-y-grpc.md para la decisión de alcance (sin big data ni gRPC).
"""
from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from datetime import date

from fastapi import Depends, Query

from common.service import ApiError, Caller, call_service, create_app, expect_ok, require_callers

app = create_app("analytics")
CACHE_SECONDS = int(os.environ.get("ANALYTICS_CACHE_SECONDS", "60"))
MAX_PAGES = 50
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


async def fetch_sales(date_from: str, date_to: str) -> list[dict]:
    rows, page = [], 1
    while page <= MAX_PAGES:
        data = expect_ok(await call_service("orders", "GET", "/internal/sales-source", timeout=5.0,
                                            params={"from": date_from, "to": date_to, "page": page, "page_size": 500}), "orders")
        rows.extend(data["items"])
        if not data["has_more"]:
            break
        page += 1
    return rows


def summarize(rows: list[dict], date_from: str, date_to: str) -> dict:
    valid = [r for r in rows if r["status"] not in ("PENDIENTE_PAGO", "ANULADO")]
    by_day: dict[str, dict] = defaultdict(lambda: {"orders": 0, "revenue_clp": 0})
    products: Counter = Counter()
    revenue_by_product: Counter = Counter()
    names: dict[int, str] = {}
    for r in valid:
        by_day[r["date"]]["orders"] += 1
        by_day[r["date"]]["revenue_clp"] += r["total_clp"]
        for line in r["lines"]:
            products[line["product_id"]] += line["quantity"]
            revenue_by_product[line["product_id"]] += line["line_total_clp"]
            names[line["product_id"]] = line["product_name"]
    revenue = sum(r["total_clp"] for r in valid)
    return {
        "from": date_from, "to": date_to,
        "paid_orders": len(valid),
        "cancelled_orders": sum(1 for r in rows if r["status"] == "ANULADO"),
        "revenue_clp": revenue,
        "average_ticket_clp": round(revenue / len(valid)) if valid else 0,
        "delivery_share": round(sum(1 for r in valid if r["delivery_type"] == "DESPACHO") / len(valid), 3) if valid else 0,
        "by_day": [{"date": d, **v} for d, v in sorted(by_day.items())],
        "top_products": [{"product_id": pid, "name": names[pid], "units": units, "revenue_clp": revenue_by_product[pid]}
                         for pid, units in products.most_common(5)],
        "generated_at": int(time.time()),
    }


@app.get("/internal/sales/summary")
async def sales_summary(
    date_from: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _: Caller = Depends(require_callers("graphql")),
):
    try:
        d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError:
        raise ApiError(400, "INVALID_RANGE", "Fechas inválidas")
    if d2 < d1 or (d2 - d1).days > 366:
        raise ApiError(400, "INVALID_RANGE", "Rango inválido (máximo 366 días)")
    key = (date_from, date_to)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1] | {"cached": True}
    result = summarize(await fetch_sales(date_from, date_to), date_from, date_to)
    _cache[key] = (time.monotonic(), result)
    return result | {"cached": False}
