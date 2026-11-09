"""Inicia / detiene todos los servicios como procesos separados (uvicorn).

    python scripts/run_local.py start            # MySQL (requiere db-*-password en secrets/)
    python scripts/run_local.py start --sqlite   # sin MySQL: crea bases SQLite con datos de prueba
    python scripts/run_local.py status
    python scripts/run_local.py stop

Separación de red en local: los servicios privados escuchan SOLO en 127.0.0.1; el único
componente que puede publicarse (--public) es el API Gateway. Además, cada servicio exige
su credencial de servicio, así que tampoco aceptan llamadas locales no autorizadas.
Para una separación de red real usar docker-compose.yml (red interna sin puertos publicados).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / ".run"
SERVICES = [
    ("auth", "services.auth_service.app:app", 8001),
    ("clients", "services.clients_service.app:app", 8002),
    ("inventory", "services.inventory_service.app:app", 8003),
    ("orders", "services.orders_service.app:app", 8004),
    ("payments", "services.payments_service.app:app", 8005),
    ("graphql", "services.graphql_gateway.app:app", 8006),
    ("analytics", "services.analytics_service.app:app", 8007),
    ("provider", "services.mock_provider.app:app", 8009),
    ("api-gateway", "services.api_gateway.app:app", 8000),
]


def start(args):
    RUN.mkdir(exist_ok=True)
    (RUN / "logs").mkdir(exist_ok=True)
    if (RUN / "pids.json").exists():
        print("Ya hay servicios corriendo; use 'stop' primero.")
        return 1
    sys.path.insert(0, str(ROOT))
    from scripts.gen_secrets import generate
    generate(ROOT / "secrets", ROOT / "db" / "nonna_workbench_setup.sql")
    env = os.environ.copy()
    env.setdefault("SECRETS_DIR", str(ROOT / "secrets"))
    env["PYTHONPATH"] = str(ROOT)
    if args.sqlite:
        from scripts.seed_sqlite import seed
        for svc, url in seed(ROOT / "data").items():
            env[f"{svc.upper()}_DATABASE_URL"] = url
    pids = {}
    for name, module, port in SERVICES:
        host = "0.0.0.0" if (name == "api-gateway" and args.public) else "127.0.0.1"
        log = open(RUN / "logs" / f"{name}.log", "ab")
        senv = env | {"SERVICE_NAME": name}
        cmd = [sys.executable, "-m", "uvicorn", module, "--host", host, "--port", str(port),
               "--no-access-log", "--workers", str(args.workers if name in ("api-gateway", "inventory", "graphql") else 1)]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(cmd, cwd=ROOT, env=senv, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        pids[name] = proc.pid
        print(f"  {name:12s} pid={proc.pid}  {host}:{port}")
    (RUN / "pids.json").write_text(json.dumps(pids))
    return wait_healthy()


def wait_healthy(timeout: float = 30) -> int:
    deadline = time.time() + timeout
    pending = {n: p for n, _, p in SERVICES}
    while pending and time.time() < deadline:
        for name, port in list(pending.items()):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                    if r.status == 200:
                        pending.pop(name)
            except OSError:
                pass
        time.sleep(0.5)
    if pending:
        print("No respondieron:", ", ".join(pending), "(revise .run/logs)")
        return 1
    print("Todos los servicios responden /health. Gateway: http://127.0.0.1:8000/api/v1/...")
    return 0


def stop(_args):
    path = RUN / "pids.json"
    if not path.exists():
        print("No hay servicios registrados.")
        return 0
    for name, pid in json.loads(path.read_text()).items():
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"  detenido {name}")
        except OSError:
            pass
    path.unlink()
    return 0


def status(_args):
    for name, _, port in SERVICES:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                state = "OK"
        except OSError:
            state = "caído"
        print(f"  {name:12s} :{port}  {state}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["start", "stop", "status"])
    p.add_argument("--sqlite", action="store_true", help="usar SQLite con datos de prueba en vez de MySQL")
    p.add_argument("--public", action="store_true", help="publicar el API Gateway en 0.0.0.0")
    p.add_argument("--workers", type=int, default=1)
    a = p.parse_args()
    sys.exit({"start": start, "stop": stop, "status": status}[a.command](a))
