# Módulo 6 — Rutas y secretos de integración

Un solo **API Gateway** público (`services/api_gateway`). Las rutas permitidas están en una lista explícita
(`services/api_gateway/routes.py`): cualquier otra combinación de verbo y ruta responde 404/405, y las rutas
`/internal/*` de los servicios nunca se publican. El gateway también expone `GET /routes` con esta misma lista.

**Credencial del usuario y credencial entre sistemas.** El navegador manda un JWT RS256 de 15 min. El gateway
lo valida (firma, emisor, audiencia y expiración), **descarta** cualquier cabecera `X-User-*` o `X-Service-*` que
venga del navegador, y envía al servicio destino:
`X-Service-Name` + `X-Service-Token` (credencial de *ese* tramo) + `X-User-Id/Role/Email` (identidad verificada).
Cada servicio rechaza una identidad de usuario que no venga acompañada de una credencial de servicio válida, y con ella
comprueba la propiedad de los recursos (por ejemplo, que un pedido pertenezca al cliente).

## Matriz de rutas REST

| ID | Verbo | Ruta externa | Acceso y rol | Sistema y ruta destino | Controles | Credencial del tramo |
|---|---|---|---|---|---|---|
| S01 | POST | `/api/v1/auth/register` | anónimo | auth: `POST /auth/register` | rate auth 10/min/IP, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S02 | POST | `/api/v1/auth/login` | anónimo | auth: `POST /auth/login` | rate auth 10/min/IP, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S03 | POST | `/api/v1/auth/refresh` | anónimo | auth: `POST /auth/refresh` | rate auth 10/min/IP, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S04 | POST | `/api/v1/auth/logout` | anónimo | auth: `POST /auth/logout` | rate auth 10/min/IP, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S05 | GET | `/api/v1/auth/me` | autenticado (cualquier rol) | auth: `GET /auth/me` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S06 | POST | `/api/v1/admin/staff` | autenticado: ADMIN | auth: `POST /auth/staff` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-auth` |
| S07 | GET | `/api/v1/products` | anónimo | inventory: `GET /products` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S08 | GET | `/api/v1/products/{id}` | anónimo | inventory: `GET /products/{id}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S09 | GET | `/api/v1/categories` | anónimo | inventory: `GET /categories` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S10 | POST | `/api/v1/products` | autenticado: ADMIN | inventory: `POST /products` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S11 | PUT | `/api/v1/products/{id}` | autenticado: ADMIN | inventory: `PUT /products/{id}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S12 | DELETE | `/api/v1/products/{id}` | autenticado: ADMIN | inventory: `DELETE /products/{id}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S13 | PUT | `/api/v1/products/{id}/stock` | autenticado: ADMIN, TRABAJADOR | inventory: `PUT /products/{id}/stock` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S14 | GET | `/api/v1/admin/stock` | autenticado: ADMIN, TRABAJADOR | inventory: `GET /admin/stock` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-inventory` |
| S15 | GET | `/api/v1/me` | autenticado: CLIENTE | clients: `GET /me` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S16 | PUT | `/api/v1/me` | autenticado: CLIENTE | clients: `PUT /me` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S17 | GET | `/api/v1/me/addresses` | autenticado: CLIENTE | clients: `GET /me/addresses` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S18 | POST | `/api/v1/me/addresses` | autenticado: CLIENTE | clients: `POST /me/addresses` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S19 | PUT | `/api/v1/me/addresses/{id}` | autenticado: CLIENTE | clients: `PUT /me/addresses/{id}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S20 | GET | `/api/v1/admin/clients` | autenticado: ADMIN | clients: `GET /admin/clients` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-clients` |
| S21 | POST | `/api/v1/orders` | autenticado: CLIENTE | orders: `POST /orders` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S22 | GET | `/api/v1/orders` | autenticado (cualquier rol) | orders: `GET /orders` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S23 | GET | `/api/v1/orders/{code}` | autenticado (cualquier rol) | orders: `GET /orders/{code}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S24 | PATCH | `/api/v1/orders/{code}/status` | autenticado: TRABAJADOR, ADMIN | orders: `PATCH /orders/{code}/status` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S25 | POST | `/api/v1/orders/{code}/cancel` | autenticado: CLIENTE, ADMIN | orders: `POST /orders/{code}/cancel` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S26 | POST | `/api/v1/admin/orders/expire-pending` | autenticado: ADMIN | orders: `POST /admin/orders/expire-pending` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-orders` |
| S27 | POST | `/api/v1/payments` | autenticado: CLIENTE | payments: `POST /payments` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-payments` |
| S28 | GET | `/api/v1/payments/{id}` | autenticado (cualquier rol) | payments: `GET /payments/{id}` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-payments` |
| S29 | POST | `/api/v1/payments/{id}/confirm-manual` | autenticado: TRABAJADOR, ADMIN | payments: `POST /payments/{id}/confirm-manual` | rate 120/min, cuerpo ≤64 KB, JSON | `svc-api-gateway-to-payments` |
| S30 | POST | `/api/v1/payments/webhook` | anónimo | payments: `POST /payments/webhook` | firma HMAC verificada en payments, rate 300/min | `svc-api-gateway-to-payments` |
| S31 | POST | `/api/v1/graphql` | autenticado (cualquier rol) | graphql: `POST /graphql` | rate 60/min, profundidad/alias/tokens | `svc-api-gateway-to-graphql` |

Además de lo anterior, todas las rutas aplican: plazo máximo de 5 s hacia el servicio, cabeceras de seguridad,
`X-Correlation-Id` y errores con formato `{"error": {code, message, correlation_id}}` sin trazas internas.

## Operaciones GraphQL (S31, `POST /api/v1/graphql`)

`POST /graphql` **no** autoriza todas las operaciones: cada query verifica su rol y cada campo sensible tiene su propio permiso.

| Operación | Tipo | Rol | Campos autorizados | Resolver | Subsistemas consultados |
|---|---|---|---|---|---|
| `misPedidos(pagina, tamano≤50)` | Query | CLIENTE | pedidos propios; `cliente` → null | `Query.mis_pedidos` | clients (id del cliente), orders, inventory (lote), payments (lote) |
| `pedido(codigo)` | Query | CLIENTE dueño / TRABAJADOR / ADMIN | todo; `cliente{telefono}` solo personal | `Query.pedido` | orders, inventory, payments, clients (solo personal) |
| `pedidosActivos(pagina, tamano≤50)` | Query | TRABAJADOR, ADMIN | todo | `Query.pedidos_activos` | orders, inventory, payments, clients |
| `reporteVentas(desde, hasta)` | Query | ADMIN | agregados sin datos personales | `Query.reporte_ventas` | analytics → orders |

Mutations: no se exponen. Las escrituras (crear pedido, pagar, cambiar estado) siguen en REST, porque las reglas
transaccionales pertenecen a cada servicio de negocio.
Límites: profundidad 6, máximo 10 alias, máximo 800 tokens, sin introspección y sin consultas por GET.

## gRPC

No aplica (ver `docs/ADR-001-analitica-y-grpc.md`): no hay métodos gRPC que documentar.

## Inventario de secretos e identidades

Los valores **nunca** van en el código, el repositorio, los logs ni este informe. El código pide la *referencia* a
`common/secrets.py` (SecretProvider): primero la variable `SECRET_<REF>` y luego el archivo `$SECRETS_DIR/<ref>`,
compatible con Docker secrets. Si un secreto falta, el servicio responde 503 (*falla cerrado*).

| Referencia | Tipo | Emisor | Consumidor | Finalidad | Ubicación segura | Alcance | Rotación y revocación |
|---|---|---|---|---|---|---|---|
| `jwt-private-key` | Clave privada RSA 2048 | `gen_secrets.py` / equipo | auth | Firmar access tokens | gestor de secretos, solo contenedor auth | solo firma | Rotar generando un par nuevo (`kid`); los tokens viejos expiran en 15 min |
| `jwt-public-key` | Clave pública RSA | idem | api-gateway | Verificar JWT | idem | solo verificación | Se reemplaza junto con la privada |
| `svc-<llamador>-to-<destino>` (17 pares) | Token de servicio (256 bits) | `gen_secrets.py` | llamador y destino | Autenticar el tramo interno | gestor de secretos, montado solo en esos dos contenedores | un tramo y las rutas que el destino permite a ese llamador | `gen_secrets.py --overwrite` o reemplazar el archivo; caché de 60 s; si se filtra uno, solo afecta a ese tramo |
| `payments-webhook-secret` | HMAC compartido con el proveedor | proveedor de pagos | payments (y el proveedor) | Verificar avisos de pago | gestor de secretos | solo verificar firmas | Rotar en el portal del proveedor y reemplazar el archivo |
| `provider-api-key` | Clave de comercio | proveedor de pagos | payments | Crear transacciones | gestor de secretos | solo crear o consultar transacciones | Revocar en el portal del proveedor si se filtra |
| `db-<servicio>-password` (5) | Contraseña MySQL | DBA / script SQL | el servicio dueño de la base | Conectar a `nonna_<servicio>` | gestor de secretos | solo su base, sin DELETE (excepto inventory) | `ALTER USER ... IDENTIFIED BY` + reemplazar el archivo |
| `mysql-root-password` | Contraseña root | `gen_secrets.py` | solo el contenedor mysql | Inicialización | gestor de secretos | administración | No la usa ningún servicio |

**Si una clave se filtra:** se rota solo esa referencia. Como cada tramo tiene su propio token, el daño queda limitado
a ese tramo. **Si el gestor de secretos no responde:** el valor se mantiene en caché durante 60 s y después el servicio
responde 503, sin usar valores por defecto.
