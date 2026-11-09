# La Nonna — Backend seguro (Evaluación Unidad 2)

Backend en **Python (FastAPI)** para el caso "Restaurante La Nonna". La base de datos es la del equipo
(`db/nonna_workbench_setup.sql`): 5 bases MySQL, una por sistema, y un usuario con permisos mínimos para cada una.

> Según la indicación del profesor, este entregable **no conecta el frontend PHP**. Las pruebas se ejecutan
> contra el API Gateway, igual que lo haría el navegador.

## Arquitectura

```
                 Internet
                    │  HTTPS (TLS en el proxy o balanceador de borde)
             ┌──────▼──────┐
             │ API Gateway │  :8000  ← único componente público
             └──┬───┬───┬──┘  JWT RS256 · rutas en lista blanca · rol · rate limit · timeouts
   red privada  │   │   │     (cada tramo tiene su propio token de servicio)
   ┌────────────┘   │   └─────────────────────┐
┌──▼───┐  ┌─────────▼──────┐  ┌─────────────┐ │
│ auth │  │ GraphQL Gateway│──► analytics   │ │
└──┬───┘  └──┬───┬───┬───┬─┘  └──────┬──────┘ │
   │         │   │   │   │           │        │
┌──▼─────┐ ┌─▼───▼┐ ┌▼───▼─────┐ ┌───▼────┐ ┌─▼────────┐      ┌───────────────┐
│clients │ │orders│ │inventory │ │payments│◄┤ webhook  │◄─────┤ Proveedor de  │
└───┬────┘ └──┬───┘ └────┬─────┘ └───┬────┘ └──────────┘      │ pagos (mock)  │
    │         │          │           │                         └───────────────┘
nonna_clients nonna_orders nonna_inventory nonna_payments (+ nonna_auth)
```

| Servicio | Puerto | Carpeta | Base |
|---|---|---|---|
| API Gateway (público) | 8000 | `services/api_gateway` | — |
| Auth Service | 8001 | `services/auth_service` | nonna_auth |
| clients | 8002 | `services/clients_service` | nonna_clients |
| inventory | 8003 | `services/inventory_service` | nonna_inventory |
| orders | 8004 | `services/orders_service` | nonna_orders |
| payments | 8005 | `services/payments_service` | nonna_payments |
| GraphQL Gateway (privado) | 8006 | `services/graphql_gateway` | — |
| analytics (privado) | 8007 | `services/analytics_service` | — |
| Proveedor de pagos de prueba | 8009 | `services/mock_provider` | — (externo simulado) |

## Requisitos

- Python 3.12 o superior (probado con 3.14 en Windows 11)
- MySQL 8.0.16 o superior con el script del equipo ya ejecutado en Workbench (o usar `--sqlite` para probar sin MySQL)
- **Windows:** dejar el proyecto en una ruta corta (por ejemplo `C:\nonna-backend`). Las rutas muy largas impiden
  cargar la librería `cryptography`.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

## Iniciar y detener

**Opción A: sin MySQL (SQLite con los mismos datos ficticios)**

```bash
.venv\Scripts\python scripts/run_local.py start --sqlite
```

**Opción B: con MySQL (la base del compañero)**

1. Ejecutar `db/nonna_workbench_setup.sql` en MySQL Workbench.
2. Generar los secretos locales. Las contraseñas de los usuarios `svc_*` se toman del script SQL y se guardan en `secrets/`, que no se sube a git:
   ```bash
   .venv\Scripts\python scripts/gen_secrets.py --db-from-sql db/nonna_workbench_setup.sql
   ```
3. (Opcional) Fijar contraseñas de prueba conocidas para los usuarios del seed:
   ```bash
   .venv\Scripts\python scripts/set_test_passwords.py
   ```
4. Levantar todo:
   ```bash
   .venv\Scripts\python scripts/run_local.py start
   ```

Estado y detención:

```bash
.venv\Scripts\python scripts/run_local.py status
```

```bash
.venv\Scripts\python scripts/run_local.py stop
```

Cada servicio tiene `GET /health`. Los logs quedan en `.run/logs/<servicio>.log` en formato JSON, con `correlation_id`
y sin tokens, contraseñas ni datos personales.

**Docker (separación de red real):** `docker compose up --build` usa `docker-compose.yml`, con una red `privada`
interna y solo los puertos 8000 y 8009 publicados. El script SQL crea los usuarios `@'localhost'`; para contenedores
hay que cambiarlos a `@'%'`. *Este archivo no se probó en el equipo donde se desarrolló (no tenía Docker).*

## Usuarios de prueba (ficticios)

| Correo | Contraseña | Rol |
|---|---|---|
| javiera@example.cl | Cliente123 | CLIENTE |
| matias@example.cl | Cliente123 | CLIENTE |
| cocina@lanonna.test | Trabajador123 | TRABAJADOR |
| admin@lanonna.test | Admin12345 | ADMIN |

(En MySQL solo valen después de `set_test_passwords.py`. Si no, se usan las contraseñas del README del compañero.)

## Ejemplos

```bash
curl -s "http://127.0.0.1:8000/api/v1/products?available=true"
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"javiera@example.cl\",\"password\":\"Cliente123\"}"
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/orders -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d "{\"items\":[{\"product_id\":1,\"quantity\":2}],\"delivery_type\":\"RETIRO\"}"
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/payments -H "Authorization: Bearer TOKEN" -H "Idempotency-Key: pago-001-abc" -H "Content-Type: application/json" -d "{\"order_code\":\"P-123456\",\"method\":\"WEBPAY\"}"
```

Luego, para simular que el cliente paga en el proveedor, abrir la `redirect_url` que devuelve el pago
(`http://127.0.0.1:8009/pay/tok_...`). El proveedor firma el aviso y lo envía al webhook del gateway.

La lista de rutas publicadas está en `GET http://127.0.0.1:8000/routes` y en [docs/rutas-y-secretos.md](docs/rutas-y-secretos.md).

## Pruebas

```bash
.venv\Scripts\python -m pytest -v
```

Las pruebas levantan los 9 componentes en un mismo proceso, cada uno con su propia base SQLite y sus propios secretos.
Cubren los flujos del caso, los 6 casos de validación del Módulo 7 y los límites de GraphQL.
Último resultado: [docs/evidencias/pytest.txt](docs/evidencias/pytest.txt) (39/39).

Prueba de carga (con el sistema levantado; sube temporalmente los límites de solicitudes, porque usa un solo usuario):

```bash
set RATE_DEFAULT=1000000 && set RATE_GRAPHQL=1000000 && .venv\Scripts\python scripts/run_local.py start --sqlite
```

```bash
.venv\Scripts\python scripts/load_test.py --concurrency 5 --duration 30
```

## Documentación

- [docs/rutas-y-secretos.md](docs/rutas-y-secretos.md): matriz de rutas, operaciones GraphQL e inventario de secretos (Módulo 6)
- [docs/graphql-y-pruebas.md](docs/graphql-y-pruebas.md): separación privada, schema, autorización GraphQL, casos del Módulo 7 y matriz requisito → prueba (Módulos 7, 8 y 10)
- [docs/schema.graphql](docs/schema.graphql): schema completo
- [docs/ADR-001-analitica-y-grpc.md](docs/ADR-001-analitica-y-grpc.md): decisión de analítica y gRPC con mediciones (Módulo 9)
- [docs/evidencias/](docs/evidencias/): resultados de pruebas y de carga

## Reglas de negocio implementadas

- **Precios y totales:** los calcula orders con el precio oficial de inventory. Un campo extra del navegador (por ejemplo `unit_price_clp`) se rechaza con 422.
- **Stock:** se reserva al crear el pedido. Al pagar, la reserva se confirma; al anular o vencer (15 min sin pago), el stock vuelve.
- **Estados:** `PENDIENTE_PAGO → PAGADO` (solo payments) `→ PREPARANDO → LISTO → ENTREGADO` (personal).
  El cliente puede anular un pedido en `PENDIENTE_PAGO`; el admin, también en `PAGADO` o `PREPARANDO` (reembolso manual).
  Anular **no borra**: el cambio queda en `order_status_history`.
- **Pagos:** se crean con `Idempotency-Key`; el monto lo fija orders. Webpay se confirma con un aviso firmado (HMAC) y
  sin procesar dos veces el mismo evento; efectivo y transferencia los confirma el personal. Cada pago autorizado emite
  una sola boleta.
- **Datos personales:** viven solo en clients. Un cliente solo ve lo suyo; el admin ve el RUN y el teléfono enmascarados.
- **Contraseñas:** bcrypt con costo 12; bloqueo de 15 min tras 5 intentos; refresh tokens rotados y revocables.
