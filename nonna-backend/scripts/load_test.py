"""Prueba de carga reproducible contra el API Gateway en ejecución (Módulo 9).

    python scripts/load_test.py --concurrency 20 --duration 30

Escenario (mezcla aproximada de un almuerzo con alta demanda):
  60 %  GET /api/v1/products               (catálogo, anónimo)
  25 %  POST /api/v1/graphql misPedidos    (agregación orders+inventory+payments)
  15 %  POST /api/v1/orders + anulación    (escritura con reserva/liberación de stock)
Mide latencia p50/p95/p99, throughput, errores y CPU/memoria de los procesos (si
psutil está instalado). Escribe el resultado en docs/evidencias/carga-<fecha>.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
QUERY = "{ misPedidos(pagina: 1, tamano: 10) { total items { codigo estado items { productoActual { nombre } } pago { estado } } } }"


async def login(client, email, password):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


async def worker(client, headers, stop_at, results):
    while time.perf_counter() < stop_at:
        roll = random.random()
        t0 = time.perf_counter()
        try:
            if roll < 0.60:
                kind = "catalogo"
                r = await client.get("/api/v1/products", params={"available": "true"})
                ok = r.status_code == 200
            elif roll < 0.85:
                kind = "graphql"
                r = await client.post("/api/v1/graphql", headers=headers, json={"query": QUERY})
                ok = r.status_code == 200 and "errors" not in r.json()
            else:
                kind = "pedido"
                r = await client.post("/api/v1/orders", headers=headers, json={
                    "items": [{"product_id": random.randint(1, 9), "quantity": 1}], "delivery_type": "RETIRO"})
                ok = r.status_code == 201
                if ok:
                    r2 = await client.post(f"/api/v1/orders/{r.json()['order_code']}/cancel", headers=headers)
                    ok = r2.status_code == 200
        except httpx.HTTPError:
            kind, ok = "error_red", False
        results.append((kind, (time.perf_counter() - t0) * 1000, ok))


def pct(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, int(len(values) * p / 100))], 1)


def process_usage():
    try:
        import psutil
    except ImportError:
        return {"note": "instale psutil para medir CPU/memoria"}
    pids_file = ROOT / ".run" / "pids.json"
    if not pids_file.exists():
        return {}
    usage = {}
    for name, pid in json.loads(pids_file.read_text()).items():
        try:
            p = psutil.Process(pid)
            procs = [p] + p.children(recursive=True)
            usage[name] = {"cpu_percent": round(sum(x.cpu_percent(interval=0.2) for x in procs), 1),
                           "rss_mb": round(sum(x.memory_info().rss for x in procs) / 2**20, 1)}
        except psutil.Error:
            pass
    return usage


async def main(args):
    limits = httpx.Limits(max_connections=args.concurrency * 2)
    async with httpx.AsyncClient(base_url=args.url, limits=limits, timeout=10) as client:
        headers = await login(client, args.email, args.password)
        results: list = []
        stop_at = time.perf_counter() + args.duration
        t0 = time.perf_counter()
        usage_task = asyncio.create_task(asyncio.to_thread(lambda: (time.sleep(args.duration / 2), process_usage())[1]))
        await asyncio.gather(*(worker(client, headers, stop_at, results) for _ in range(args.concurrency)))
        elapsed = time.perf_counter() - t0
        usage = await usage_task

    report = {
        "tipo": "medición (no proyección)",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "entorno": {"url": args.url, "os": os.name, "nota": args.note},
        "concurrencia": args.concurrency, "duracion_s": args.duration,
        "solicitudes": len(results), "throughput_rps": round(len(results) / elapsed, 1),
        "errores": sum(1 for r in results if not r[2]),
        "latencia_ms": {"p50": pct([r[1] for r in results], 50), "p95": pct([r[1] for r in results], 95),
                        "p99": pct([r[1] for r in results], 99)},
        "por_tipo": {},
        "recursos_a_mitad_de_prueba": usage,
    }
    for kind in sorted({r[0] for r in results}):
        lat = [r[1] for r in results if r[0] == kind]
        report["por_tipo"][kind] = {"n": len(lat), "p95_ms": pct(lat, 95),
                                    "media_ms": round(statistics.mean(lat), 1),
                                    "errores": sum(1 for r in results if r[0] == kind and not r[2])}
    out_dir = ROOT / "docs" / "evidencias"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"carga-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Guardado en", out.relative_to(ROOT))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--email", default="javiera@example.cl")
    p.add_argument("--password", default="Cliente123")
    p.add_argument("--note", default="")
    asyncio.run(main(p.parse_args()))
