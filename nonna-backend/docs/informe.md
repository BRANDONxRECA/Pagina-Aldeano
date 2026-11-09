# Informe de arquitectura — Backend seguro "Restaurante La Nonna"

**Evaluación de la Unidad 2 · Diseño e implementación de un backend seguro completo**

| | |
|---|---|
| Caso | N° **__** — Restaurante "La Nonna" (pastas frescas, Maipú) *(completar el número)* |
| Integrantes | *(completar)* |
| Versión del frontend | *(completar: commit o tag del frontend PHP)* — pantallas: `index.php`, `carta.php`, `carrito.php`, `historial.php`, `quienes_somos.php` |
| Versión del backend | este repositorio (Python 3.12+, FastAPI, MySQL 8) |
| Fecha | 09-11-2026 |

> Por indicación del profesor, la integración con el frontend no forma parte de esta entrega. Las pantallas se usan
> como fuente de requisitos y todos los servicios se prueban a través del API Gateway, igual que lo haría el navegador.

Documentos que complementan este informe:
[diagramas](diagramas.md) · [ejemplos de contratos](contratos-ejemplos.md) · [rutas y secretos (M6)](rutas-y-secretos.md) ·
[GraphQL y pruebas (M7, M8, M10)](graphql-y-pruebas.md) · [ADR analítica/gRPC (M9)](ADR-001-analitica-y-grpc.md) · [schema GraphQL](schema.graphql)

---

## 0. Requisitos del caso y brechas declaradas

| ID | Requisito | Pantalla | Estado |
|---|---|---|---|
| R01 | Ver la carta con precios y disponibilidad | P02 `carta.php` | Implementado |
| R02 | Crear cuenta de cliente | P01 `index.php` → modal *Crear cuenta* | Implementado |
| R03 | Iniciar y cerrar sesión (cliente y trabajador) | P01 → modales *Iniciar sesión* y *Trabajadores* | Implementado |
| R04 | Armar el carrito y confirmar el pedido (despacho o retiro) | P03 `carrito.php` | Implementado (el carrito vive en el navegador; el pedido se crea al confirmar) |
| R05 | Pagar con tarjeta, transferencia o efectivo | P03 → *Tarjeta / Transferencia / Efectivo* → *Pagar* | Implementado (tarjeta con un adaptador de prueba del proveedor) |
| R06 | Ver el historial de compras con estado (Entregado / Cancelado) | P04 `historial.php` | Implementado (GraphQL `misPedidos`) |
| R07 | Seguir el estado del pedido ("Pedido en preparación") | P03 / P04 | Implementado (estados del pedido) |
| R08 | Gestión de pedidos por la cocina | **Brecha:** no hay pantalla de trabajador | Backend listo (S24, S29, `pedidosActivos`). Se incorporará como una vista *Panel cocina* después del login de trabajador |
| R09 | Administración de la carta, el stock y el personal | **Brecha:** no hay pantalla de admin | Backend listo (S06, S10–S14, S20). Vista *Administración* propuesta |
| R10 | Reporte de ventas | **Brecha:** no hay pantalla | Backend listo (`reporteVentas`, solo ADMIN) |
| R11 | Perfil y direcciones del cliente | **Brecha:** el carrito no pide la dirección | Backend listo (S15–S19). El carrito deberá agregar un selector de dirección para despacho |
| — | Información institucional | P05 `quienes_somos.php` | Contenido estático: no requiere servicio |

**Requisitos y decisiones de arquitectura.** Los requisitos R01–R11 vienen del caso y de las pantallas. Las decisiones
de arquitectura del equipo son, entre otras: separar en microservicios, usar JWT RS256, tener un solo gateway, reservar
stock y no implementar gRPC. Esas decisiones se justifican en las secciones 3, 5 y en el ADR.

---

## 1. Módulo 1 — Servicios derivados del frontend

Escritorio y móvil comparten las mismas operaciones: la versión móvil solo cambia la disposición, así que no agrega servicios.
Las variaciones que solo cambian la presentación no generan servicios nuevos.
Los ejemplos JSON de **cada** contrato, obtenidos por ejecución, están en [contratos-ejemplos.md](contratos-ejemplos.md).

Clasificación de datos: **P** = público · **R** = restringido (dato personal) · **C** = credencial.

| ID | Req. | Pantalla y acción | Propósito | Verbo y ruta | Entrada | Salida | Reglas y errores | Datos | Acceso |
|---|---|---|---|---|---|---|---|---|---|
| S01 | R02 | P01 · Crear cuenta | Registrar cliente | `POST /api/v1/auth/register` | email*, password* (8–72, letras y números), first_name*, last_name*, phone (+569…), run (con DV) | 201 {id, email, role} | 409 correo repetido · 422 validación · 503 si clients falla (se compensa) | C, R | Anónimo |
| S02 | R03 | P01 · Iniciar sesión / Trabajadores | Autenticar | `POST /api/v1/auth/login` | email*, password* | 200 {access_token, expires_in, refresh_token, user} | 401 genérico · 423 bloqueo tras 5 intentos · 429 rate | C | Anónimo |
| S03 | R03 | (automático) | Renovar sesión | `POST /api/v1/auth/refresh` | refresh_token* | 200 tokens nuevos | 401 si está revocado o vencido; rota el token | C | Anónimo (con token) |
| S04 | R03 | Menú · Cerrar sesión | Revocar sesión | `POST /api/v1/auth/logout` | refresh_token* | 204 | idempotente | C | Anónimo (con token) |
| S05 | R03 | Navbar (nombre o rol) | Usuario actual | `GET /api/v1/auth/me` | — | 200 {id, email, role} | 401 | R | Autenticado |
| S06 | R09 | Brecha · Admin | Crear trabajador | `POST /api/v1/admin/staff` | email*, password*, first_name*, last_name*, position*, role* (TRABAJADOR o ADMIN) | 201 {id, email, role} | 403 si no es ADMIN · 409 | C, R | ADMIN |
| S07 | R01 | P02 · Cargar carta | Consultar catálogo | `GET /api/v1/products` | query: category, available (bool), q (2–60), page, page_size ≤100 | 200 [{id, name, description, category, price_clp, available}] · [] si no hay | 422 filtros inválidos · sin stock exacto ni SKU | P | Anónimo |
| S08 | R01 | P02 · Detalle | Consultar producto | `GET /api/v1/products/{id}` | id | 200 producto | 404 si no existe o está inactivo | P | Anónimo |
| S09 | R01 | P02 · Secciones | Listar categorías | `GET /api/v1/categories` | — | 200 [{id, name}] | — | P | Anónimo |
| S10 | R09 | Brecha · Admin | Crear producto | `POST /api/v1/products` | category_id*, sku* (A-Z0-9-), name*, description*, price_clp* (>0), initial_stock | 201 producto | 409 SKU repetido · 422 categoría | P | ADMIN |
| S11 | R09 | Brecha · Admin | Reemplazar producto | `PUT /api/v1/products/{id}` | representación completa + active | 200 producto | 404 · 409 | P | ADMIN |
| S12 | R09 | Brecha · Admin | Retirar de la carta | `DELETE /api/v1/products/{id}` | id | 204 | desactivación lógica (el historial lo referencia) · 404 | P | ADMIN |
| S13 | R09 | Brecha · Cocina/Admin | Fijar stock | `PUT /api/v1/products/{id}/stock` | quantity_available* (0–100000) | 200 {disponible, reservado} | 404 | interno | TRABAJADOR, ADMIN |
| S14 | R09 | Brecha · Cocina/Admin | Consultar stock | `GET /api/v1/admin/stock` | — | 200 [{id, sku, name, active, available, reserved}] | — | interno | TRABAJADOR, ADMIN |
| S15 | R11 | Brecha · Perfil | Ver perfil | `GET /api/v1/me` | — (id desde el token) | 200 perfil | 404 | R | CLIENTE |
| S16 | R11 | Brecha · Perfil | Reemplazar perfil | `PUT /api/v1/me` | first_name*, last_name*, phone, notify_email | 200 perfil | RUN y correo no editables | R | CLIENTE |
| S17 | R04, R11 | P03 · Elegir dirección | Listar direcciones | `GET /api/v1/me/addresses` | — | 200 [direcciones] | solo las propias | R | CLIENTE |
| S18 | R11 | P03 · Nueva dirección | Agregar dirección | `POST /api/v1/me/addresses` | street*, commune*, reference, is_default | 201 dirección | máximo 10 · 409 | R | CLIENTE |
| S19 | R11 | Brecha · Perfil | Reemplazar dirección | `PUT /api/v1/me/addresses/{id}` | igual que S18 | 200 | 404 si es ajena | R | CLIENTE |
| S20 | R09 | Brecha · Admin | Listar clientes | `GET /api/v1/admin/clients` | page, page_size ≤100 | 200 página con RUN y teléfono enmascarados | 403 | R (enmascarado) | ADMIN |
| S21 | R04 | P03 · Confirmar pedido | Crear pedido | `POST /api/v1/orders` | items*[{product_id, quantity 1–20}] (1–20 líneas), delivery_type* (DESPACHO o RETIRO), address_id (solo despacho) | 201 {order_code, status, items con precio oficial, totales, payment_deadline} | 422 si se envían precio u otros campos extra · 409 sin stock o producto inactivo (el pedido queda ANULADO) · 503 | R (dirección) | CLIENTE |
| S22 | R06 | P04 · Historial / panel | Listar pedidos | `GET /api/v1/orders` | status, page, page_size ≤50 | 200 página | cliente: solo los propios · personal: todos | R | Autenticado |
| S23 | R06, R07 | P04 · Detalle | Ver pedido | `GET /api/v1/orders/{code}` | code | 200 pedido | 404 si es ajeno (no revela que existe) | R | Autenticado (dueño o personal) |
| S24 | R08 | Brecha · Cocina | Cambiar estado | `PATCH /api/v1/orders/{code}/status` | status* (PREPARANDO, LISTO o ENTREGADO) | 200 | 409 transición inválida · PAGADO no se puede fijar aquí | interno | TRABAJADOR, ADMIN |
| S25 | R04, R06 | P04 · Anular | Anular pedido | `POST /api/v1/orders/{code}/cancel` | code | 200 {status ANULADO} | cliente: solo en PENDIENTE_PAGO · admin: hasta PREPARANDO · libera stock · no borra | R | CLIENTE dueño, ADMIN |
| S26 | R04 | (tarea programada) | Vencer impagos | `POST /api/v1/admin/orders/expire-pending` | — | 200 {expired_orders} | también corre cada 60 s en orders | — | ADMIN |
| S27 | R05 | P03 · Pagar | Iniciar pago | `POST /api/v1/payments` + `Idempotency-Key` | order_code*, method* (WEBPAY, TRANSFERENCIA o EFECTIVO) | 201 {id, amount_clp (lo calcula el servidor), status INICIADO, redirect_url o instrucciones} | 404 si el pedido es ajeno · 409 no pagable o pago en curso · 422 si se envía el monto | R | CLIENTE |
| S28 | R05 | P03 · Estado del pago | Ver pago | `GET /api/v1/payments/{id}` | id | 200 {status, receipt_number} | 404 si es ajeno | R | Autenticado (dueño o personal) |
| S29 | R05 | Brecha · Caja | Confirmar efectivo o transferencia | `POST /api/v1/payments/{id}/confirm-manual` | id | 200 {AUTORIZADO, receipt_number} | 409 si es Webpay | interno | TRABAJADOR, ADMIN |
| S30 | R05 | (servidor a servidor) | Aviso del proveedor | `POST /api/v1/payments/webhook` + `X-Provider-Signature` | event_id, token, result, amount | 200 {status, duplicate, receipt_number} | 401 firma inválida · 400 monto alterado · avisos repetidos sin efecto | — | Proveedor (firma HMAC) |
| S31 | R06–R10 | P04 · Historial / panel / reporte | Agregación GraphQL | `POST /api/v1/graphql` | {query, variables} | 200 {data, errors parciales} | rol por operación y por campo · límites de costo | R / P | Autenticado |

**Lo que envía el navegador y lo que calcula el servidor:** el navegador manda solo identificadores, cantidades, tipo
de entrega y método de pago. El servidor calcula nombre, precio, subtotal, despacho, total, código de pedido, estados,
monto del pago, número de boleta y fecha de vencimiento. Un campo de más (por ejemplo `unit_price_clp` o `amount_clp`)
se rechaza con 422 (`extra="forbid"`).

---

## 2. Módulo 2 — Clases y cardinalidades del dominio

Diagrama: [diagramas.md § Módulo 2](diagramas.md) (fuente `diagramas/01-uml-dominio.mmd`).

### Relaciones

| Clase origen | Clase destino | Multiplicidad | Tipo | Regla de negocio que la justifica |
|---|---|---|---|---|
| Usuario | RefreshToken | 1 — 0..* | composición | Un usuario puede tener varias sesiones abiertas (varios dispositivos). Un token pertenece a un solo usuario y no existe sin él |
| Usuario | PerfilPersonal | 1 — 0..1 | asociación | Solo los usuarios TRABAJADOR o ADMIN tienen perfil de personal |
| Usuario | Cliente | 1 — 0..1 | referencia lógica | Solo un usuario CLIENTE tiene perfil en clients. `auth_user_id` es UNIQUE. No hay FK porque son bases de servicios distintos |
| Cliente | Direccion | 1 — 0..* | composición | Un cliente que solo retira no necesita dirección. Cada dirección pertenece a un cliente (máximo 10) |
| Categoria | Producto | 1 — 0..* | agregación | Todo producto está en una categoría. Una categoría nueva puede estar vacía |
| Producto | Stock | 1 — 1 | composición | Cada producto tiene exactamente un registro de existencias, que se crea junto con él |
| Producto | ReservaStock | 1 — 0..* | asociación | Un producto puede estar reservado en varios pedidos en curso |
| Pedido | ReservaStock | 1 — 0..* | referencia lógica | Hay una reserva por producto del pedido. Son 0 si el pedido se anuló antes de reservar (sin stock) |
| Cliente | Pedido | 1 — 0..* | referencia lógica | Un cliente puede no haber comprado nunca. Un pedido es de un solo cliente |
| Pedido | ItemPedido | 1 — 1..* | composición | **Un pedido confirmado tiene al menos un ítem** (la validación exige 1–20 líneas). No se modelan borradores vacíos: el carrito vive en el navegador |
| ItemPedido | Producto | 0..* — 1 | referencia lógica + copia | El ítem guarda el nombre y el precio *al momento de comprar*. Si el producto cambia o se desactiva, el historial no cambia |
| Pedido | HistorialEstado | 1 — 1..* | composición | Toda creación o transición queda registrada. Nunca se borra |
| Pedido | Pago | 1 — 0..* | referencia lógica | Un pedido puede tener intentos rechazados o vencidos. Como máximo uno está INICIADO o AUTORIZADO a la vez |
| Pago | EventoPago | 1 — 0..* | composición | Un pago en efectivo no tiene avisos. Webpay puede tener varios (por ejemplo, reintentos), cada uno único por `provider_event_id` |
| Pago | Boleta | 1 — 0..1 | composición | Un pago autorizado genera como máximo una boleta (`payment_id` UNIQUE). Un pago no autorizado no genera ninguna |

### Correspondencia entre operaciones UML e IDs de servicio

Cada operación de las clases `<<service>>` del diagrama lleva su ID: AuthService S01–S06 · CatalogService S07–S14 ·
ClientService S15–S20 · OrderService S21–S26 · PaymentService S27–S30 · AggregationService S31.
Las dependencias `..>` indican que el servicio *usa* un contrato (DTO) o una entidad. No significan que exista un
registro por cada instancia del servicio.

### Modelo interno y DTO

| Entidad interna | Atributos que **no** salen | DTO / respuesta |
|---|---|---|
| Usuario | password_hash, failed_attempts, locked_until | TokenDTO {access_token, expires_in, refresh_token, user{id, email, role}} |
| Producto + Stock | sku (solo admin), cantidades exactas (solo personal), fechas | ProductoDTO {id, name, description, category, price_clp, available} |
| Cliente | auth_user_id, deleted_at, timestamps | PerfilDTO (solo al dueño). Al admin: RUN y teléfono enmascarados |
| Pedido | id interno, client_id (solo personal), historial | PedidoDTO {order_code, status, delivery_type, delivery_address, totales, items} |
| Pago | provider_token, idempotency_key, client_id | PagoDTO {id, amount_clp, method, status, receipt_number} |

### Decisiones del equipo

- **¿El carrito y el pedido son clases distintas?** Sí. El carrito es estado del navegador y no se persiste. El pedido
  nace al confirmar, con precios del servidor y stock reservado.
- **¿Qué pasa con el historial si un producto deja de estar disponible?** El producto se desactiva (no se borra) y el
  ítem conserva el nombre y el precio de la compra. En GraphQL, `productoActual.disponible` muestra el estado de hoy.
- **¿Qué atributos se conservan internamente?** Ver la tabla anterior.

---

## 3. Módulo 3 — Sistemas e integraciones

Diagramas: mapa de componentes y secuencia del flujo de compra en [diagramas.md](diagramas.md).

| Sistema | Responsabilidad | Datos que administra (autoridad) | Servicios | Dependencias | Contrato de integración | Credencial requerida | Respuesta ante fallos |
|---|---|---|---|---|---|---|---|
| **inventory** | Catálogo, precio oficial, stock y reservas | `nonna_inventory`: categorías, productos, **precio**, stock, reservas | S07–S14 | — | REST interno: `GET /internal/products?ids`, `POST /internal/reservations`, `…/{order}/confirm`, `…/release`, `…/expire` | Usuario MySQL `svc_inventory`. Acepta `svc-orders-to-inventory`, `svc-graphql-to-inventory` y `svc-api-gateway-to-inventory` | Reserva atómica (todo o nada) e idempotente por pedido. Las reservas vencen solas: el stock se recupera aunque orders no avise |
| **orders** | Creación y ciclo de vida del pedido | `nonna_orders`: pedidos, ítems, **estado oficial**, historial | S21–S26 | inventory (precios y reservas), clients (cliente y dirección) | REST interno: `GET /internal/orders*`, `POST /internal/orders/{id}/mark-paid` (solo payments), `GET /internal/sales-source` (solo analytics) | `svc_orders`. Llama con `svc-orders-to-inventory` y `svc-orders-to-clients` | Si la reserva falla, el pedido queda ANULADO y se devuelve 409/503. Si inventory no responde al liberar, la reserva vence sola |
| **clients** | Registro del perfil, direcciones y acceso a datos personales | `nonna_clients`: perfil, RUN, teléfono, direcciones | S15–S20 | — | REST interno: `POST /internal/clients` (solo auth), `GET …/by-user/{uid}`, `GET …/{id}/addresses/{aid}` (solo orders), `GET /internal/clients?ids` (solo graphql) | `svc_clients` (sin DELETE) | Si falla el alta, auth compensa (desactiva la cuenta) y responde 503 |
| **payments** | Inicio del pago, verificación del resultado, boleta y relación con el proveedor | `nonna_payments`: pagos, avisos, boletas | S27–S30 | orders (monto oficial, marcar pagado), clients, proveedor | REST: webhook firmado. Interno: `GET /internal/payments?order_ids` | `svc_payments`, `provider-api-key`, `payments-webhook-secret` | Si orders no responde: 503 al proveedor, que reintenta; el reintento solo resincroniza. Si la reserva venció: 409 y el pago se marca para reembolso |
| auth *(complementario)* | Credenciales, roles y sesiones | `nonna_auth` | S01–S06 | clients | — | `svc_auth`, `jwt-private-key` | — |
| analytics *(complementario)* | Reporte de ventas | ninguno (caché) | S31 `reporteVentas` | orders | `GET /internal/sales/summary` | `svc-analytics-to-orders` | Si orders falla: error en GraphQL. Caché de 60 s |
| graphql *(complementario)* | Agregación para pantallas | ninguno | S31 | orders, inventory, payments, clients, analytics | `docs/schema.graphql` | `svc-graphql-to-*` | Errores parciales por campo |
| **Proveedor de pagos** *(externo)* | Cobro con tarjeta | — | S30 | — | API de transacciones + webhook HMAC | clave de comercio | Para la entrega se usa un adaptador de prueba (`mock_provider`) que conserva el contrato |

**Boletas** se implementan dentro de payments (tabla `receipts`, una por pago autorizado). **Despacho** se modela como
`delivery_type` + `delivery_address` + estados del pedido; no requiere un sistema propio a esta escala.
**Mensajería:** existe el dato `notify_email` en clients, pero el envío de correos **no está implementado**. Es una
brecha declarada y su adaptador iría como suscriptor de las transiciones de `order_status_history`.

**Disponibilidad y doble venta (ejemplo de la guía):** orders consulta a inventory y **reserva** en una sola
transacción con bloqueo por fila (`SELECT … FOR UPDATE` + `UPDATE … WHERE quantity_available >= qty`), así que nunca
confirma unidades que ya no existen. Si inventory no responde, el pedido no se acepta (falla cerrado).
**Pagos:** el aviso se verifica con HMAC-SHA256, `provider_event_id` es UNIQUE (no se procesa dos veces) y solo
payments → orders `mark-paid` puede pasar el pedido a PAGADO. El frontend nunca decide que un pedido está pagado.

---

## 4. Módulo 4 — Stakeholders y permisos HTTP

### Registro de stakeholders

| Stakeholder | Interés | Rol / identidad técnica | Uso de la información |
|---|---|---|---|
| Visitante | Ver la carta y precios | anónimo | Catálogo público (S07–S09), registro (S01) |
| Cliente | Comprar, pagar y revisar su historial | `CLIENTE` | Sus propios datos, pedidos y pagos |
| Cocina / despacho | Preparar y entregar pedidos | `TRABAJADOR` | Pedidos activos, estados, stock, confirmar efectivo |
| Administrador del local | Carta, precios, personal y ventas | `ADMIN` | Gestión del catálogo y del personal, anulaciones, reporte |
| Proveedor de pagos | Notificar el resultado de los cobros | identidad técnica: firma HMAC | Solo S30 |
| Servicios internos | Colaborar entre sistemas | `svc-<llamador>-to-<destino>` | Solo las rutas `/internal/*` que el destino les permite |
| Dueña / socios del local | Rentabilidad | **sin permisos operativos** | Reciben el reporte de ventas que exporta el ADMIN |
| Contador / SII | Respaldo tributario | **sin permisos operativos** | Reciben las boletas y el reporte desde administración |
| Docente / evaluador | Revisar la solución | **sin permisos operativos** | Usa las cuentas de prueba ficticias del README |

### Matriz de permisos por servicio y verbo

"Denegado" significa que el gateway o el servicio responde 401/403. "N/A" significa que el verbo no existe para ese
recurso (responde 404/405). Un verbo permitido no autoriza todas las rutas: cada fila es una ruta concreta.

| Rol / identidad | ID | Ruta | Verbo | Decisión | Alcance y condición | Dónde se verifica |
|---|---|---|---|---|---|---|
| Visitante | S07–S09 | `/api/v1/products*`, `/categories` | GET | Permitido | Solo campos públicos | Gateway (ANON) |
| Visitante | S01–S04 | `/api/v1/auth/*` | POST | Permitido | Rate limit de 10/min por IP | Gateway + auth |
| Visitante | todas las demás | — | todos | **Denegado (401)** | — | Gateway |
| Cliente | S15–S19 | `/api/v1/me*` | GET, POST, PUT | Permitido | Solo su registro (el id sale del token) | Gateway (rol) + clients |
| Cliente | — | `/api/v1/me*` | DELETE | N/A | Sin borrado: se conserva el historial | — |
| Cliente | S21 | `/api/v1/orders` | POST | Permitido | Precios del servidor · stock reservado | Gateway + orders |
| Cliente | S22, S23 | `/api/v1/orders[/{code}]` | GET | Permitido | **Solo sus pedidos**; uno ajeno da 404 | orders (propiedad) |
| Cliente | S25 | `/api/v1/orders/{code}/cancel` | POST | Permitido | Solo si es suyo y está en PENDIENTE_PAGO | orders |
| Cliente | S24 | `/api/v1/orders/{code}/status` | PATCH | **Denegado (403)** | No puede marcar estados (ni PAGADO) | Gateway + orders |
| Cliente | S27, S28 | `/api/v1/payments[/{id}]` | POST, GET | Permitido | Solo pedidos y pagos propios · Idempotency-Key | payments |
| Cliente | S29 | `/payments/{id}/confirm-manual` | POST | **Denegado (403)** | — | Gateway + payments |
| Cliente | S10–S12 | `/api/v1/products[/{id}]` | POST, PUT, DELETE | **Denegado (403)** | Consultar la carta no da permisos de administración | Gateway + inventory |
| Cliente | S31 | `/api/v1/graphql` | POST | Permitido | `misPedidos` y `pedido` propio. `cliente`/`telefono`, `pedidosActivos` y `reporteVentas` denegados | graphql (operación y campo) |
| Trabajador | S22–S24 | `/api/v1/orders*` | GET, PATCH | Permitido | Todos los pedidos · solo transiciones válidas | orders |
| Trabajador | S13, S14 | `/products/{id}/stock`, `/admin/stock` | PUT, GET | Permitido | — | Gateway + inventory |
| Trabajador | S29 | `/payments/{id}/confirm-manual` | POST | Permitido | Solo EFECTIVO o TRANSFERENCIA | payments |
| Trabajador | S10–S12, S06, S20, S26 | administración | POST, PUT, DELETE, GET | **Denegado (403)** | — | Gateway + servicio |
| Trabajador | S31 | `/api/v1/graphql` | POST | Permitido | `pedidosActivos`, `pedido`, `cliente{telefono}` | graphql |
| Admin | S06, S10–S14, S20, S26 | administración | todos los definidos | Permitido | DELETE de producto = desactivación lógica | Gateway + servicio |
| Admin | S25 | `/orders/{code}/cancel` | POST | Permitido | Hasta PREPARANDO (reembolso manual si estaba pagado) | orders |
| Admin | S31 | `/api/v1/graphql` | POST | Permitido | Incluye `reporteVentas` | graphql |
| Admin | S21, S27, S15–S19 | compra y perfil de cliente | POST, GET, PUT | **Denegado (403)** | El admin no compra como cliente | Gateway |
| Proveedor | S30 | `/api/v1/payments/webhook` | POST | Permitido | Solo con firma HMAC válida y monto correcto | payments |
| Servicio X | — | `/internal/*` | — | Permitido solo para los llamadores listados | ej. `mark-paid` solo payments, `reservations` solo orders | servicio destino (`require_callers`) |
| Navegador | — | cualquier servicio interno directo | todos | **Denegado (401)** | Sin credencial de servicio | cada servicio |

**Identidad y autorización:** la identidad la prueba el JWT (usuarios) o el token de servicio (sistemas). La
autorización la decide el gateway (rol por ruta) y la **repite** cada servicio, que además verifica propiedad y estado.
Ocultar un botón en el frontend no reemplaza estos controles. La prueba `test_m7_4_pedido_ajeno` comprueba que un
usuario no puede consultar pedidos de otro.

---

## 5. Módulo 5 — API Gateway y fronteras de confianza

Diagramas: UML del gateway y recorrido autorizado/denegado en [diagramas.md](diagramas.md).

**¿Cuántos gateways?** **Uno solo**, con políticas por ruta (`access`, `roles`, `rate`). Las rutas anónimas,
autenticadas, administrativas y el webhook se distinguen por política, no por despliegue. Un segundo gateway (por
ejemplo, uno de administración) solo tendría sentido con redes o equipos distintos, y no es el caso de un local. El
**GraphQL Gateway** es un componente aparte y **privado**: solo se llega a él a través del API Gateway.

| Clase de ruta | Ejemplos | Política |
|---|---|---|
| Externa anónima | S01–S04, S07–S09 | Sin token. Rate limit por IP (auth: 10/min) |
| Externa autenticada | S05, S15–S19, S21–S23, S25, S27, S28, S31 | JWT + rol. Propiedad verificada en el servicio |
| Administrativa | S06, S10–S14, S20, S24, S26, S29 | JWT + rol TRABAJADOR o ADMIN |
| Integración externa | S30 | Sin JWT. Firma HMAC verificada en payments |
| Interna | `/internal/*` | **Nunca** se publica. Exige token de servicio por tramo |

**Qué valida el gateway:** existencia de la ruta y del verbo (lista blanca), JWT (firma RS256, `iss`, `aud`, `exp`,
claims), rol, rate limit, tamaño ≤ 64 KB, `Content-Type` JSON y plazo de 5 s. Además descarta las cabeceras de
identidad del navegador, agrega cabeceras de seguridad y el correlation id.
**Qué valida cada servicio:** la credencial del servicio llamador y si ese llamador puede usar esa ruta, otra vez el
rol, la **propiedad del recurso**, las reglas de negocio (estados, stock, montos) y los esquemas de entrada (`extra=forbid`).

**Fronteras de confianza:** (1) Internet → gateway: nada es confiable y se valida todo. (2) Gateway → servicios: solo se
confía en la identidad si viene con el token del tramo. (3) Servicio → base: cada servicio tiene su usuario MySQL con
permisos mínimos y solo sobre su base. (4) Proveedor → webhook: se confía solo en avisos firmados.

**Material de apoyo (apigateway.zip):** sirvió para reconocer el flujo auth → gateway → backend. En esta propuesta las
políticas, la separación en cuatro sistemas, los secretos por tramo y las pruebas son propios.

---

## 6. Módulo 6 — Rutas y secretos

Ver [rutas-y-secretos.md](rutas-y-secretos.md): matriz completa de las 31 rutas, operaciones GraphQL e inventario de
secretos con rotación y revocación.

---

## 7. Módulo 7 — Datos sensibles y secretos del cliente

### Inventario y protección

| Dato o credencial | Finalidad | Clasificación | Sistema custodio | Roles autorizados | Representación en el frontend | Protección | Retención |
|---|---|---|---|---|---|---|---|
| Nombre, descripción y precio de producto | Mostrar la carta | Público | inventory | todos | Carta | Integridad: solo ADMIN modifica | Mientras exista el producto (luego se desactiva) |
| Stock exacto | Operación | Interno | inventory | TRABAJADOR, ADMIN | El público solo ve "disponible" (bool) | No se publica | Vigente |
| Correo | Login y contacto | Restringido | auth + clients | dueño, ADMIN | Perfil | TLS · no aparece en logs (solo el id) | Mientras la cuenta esté activa |
| Contraseña | Autenticación | Credencial | auth | nadie la lee | Solo el formulario de login | **bcrypt costo 12 con sal** · nunca se devuelve · bloqueo tras 5 intentos | Hasta que se cambie |
| RUN | Boleta e identificación | Restringido | clients | dueño · ADMIN enmascarado `****111-1` | Perfil | UNIQUE · validación de DV · enmascarado | Mientras la cuenta esté activa |
| Teléfono | Coordinar el despacho | Restringido | clients | dueño, personal (GraphQL `telefono`) | Perfil / panel | Permiso por campo · enmascarado para el admin | Mientras la cuenta esté activa |
| Direcciones | Despacho | Restringido | clients (perfil), orders (copia en el pedido) | dueño, personal del pedido | Carrito / pedido | El cliente solo ve las suyas (404 si es ajena) · no está en el catálogo | Perfil: mientras exista · pedido: historial tributario |
| Historial de pedidos | Seguimiento | Restringido | orders | dueño, personal | Historial | Propiedad verificada en orders y GraphQL | 6 años (respaldo tributario) |
| Access token (JWT) | Sesión | Credencial | emisor: auth | portador | Memoria del navegador | RS256 · 15 min · `aud`/`iss` · sin datos sensibles en los claims | 15 min |
| Refresh token | Renovar la sesión | Credencial | auth (solo el SHA-256) | portador | Almacenamiento del cliente | Rotación en cada uso · revocable · 7 días | 7 días |
| Token de transacción del proveedor | Correlacionar el pago | Interno | payments | servicio | Va en la `redirect_url` | No es la clave del comercio · no se devuelve en `GET /payments` | Junto con el pago |
| Clave de comercio, secreto HMAC, claves JWT, tokens de servicio, contraseñas de BD | Integraciones | **Secreto** | gestor de secretos | solo el servicio consumidor | **Nunca** | Ver M6 | Hasta que se roten |
| Datos de tarjeta | Pago | Sensible | **el proveedor** (no se reciben) | — | Sitio del proveedor | Fuera del alcance del backend | — |

### Decisión sobre secretos del cliente: **NO** se custodian

El backend no guarda secretos que pertenezcan al cliente: no hay tarjetas, claves de terceros ni tokens de pago
reutilizables. La contraseña es una *credencial* y se guarda solo como hash irreversible. El RUN, la dirección y el
teléfono son *datos personales restringidos*, no secretos: se protegen con control de acceso, enmascarado y exclusión
de los logs. Los secretos de integración (clave de comercio, HMAC) son del comercio y viven solo en payments. El
navegador no recibe ninguna clave compartida, porque no podría mantenerla confidencial.

### Recorrido de un dato restringido: la dirección de despacho

1. **Captura:** el cliente la ingresa (S18) por HTTPS. El gateway no la registra (los logs solo guardan ruta, estado y correlation id).
2. **Almacenamiento:** clients la guarda en `nonna_clients.addresses`, asociada a su `client_id`.
3. **Uso:** al crear un pedido de DESPACHO (S21), orders la pide a clients **con el `client_id` del token**, así que una dirección ajena da 404. Luego **copia** el texto en `orders.delivery_address`.
4. **Exposición:** solo la ven el dueño (S23, `misPedidos`) y el personal que despacha. No aparece en el catálogo, en analytics (`sales-source` no la incluye) ni en el listado de admin.
5. **Conservación:** la copia del pedido se mantiene como respaldo de la venta. El perfil no tiene DELETE (el usuario `svc_clients` no tiene ese permiso). La baja es lógica (`deleted_at`) y queda propuesta la anonimización de las direcciones del perfil al darse de baja.

### Sesiones y tokens

Access token de 15 min, sin estado. Refresh de 7 días, rotado y revocable (`/logout`). Si un refresh token se filtra,
se revoca. Si se filtra la clave JWT, se rota el par de claves y todas las sesiones caducan en ≤ 15 min.

**Casos de validación ejecutados:** ver la tabla en [graphql-y-pruebas.md](graphql-y-pruebas.md#casos-de-validación-del-módulo-7-ejecutados).

---

## 8–10. Módulos 8, 9 y 10

- **M8 — Separación privada y GraphQL:** [graphql-y-pruebas.md](graphql-y-pruebas.md) y [schema.graphql](schema.graphql).
- **M9 — Analítica y gRPC:** [ADR-001](ADR-001-analitica-y-grpc.md). Se implementó analítica liviana; gRPC no aplica y está justificado con mediciones.
- **M10 — Backend completo:** [README](../README.md) (arranque, secretos, datos y pruebas), [evidencias](evidencias/) y la matriz requisito → prueba en [graphql-y-pruebas.md](graphql-y-pruebas.md).

## Limitaciones conocidas

- El frontend no está conectado (indicación del profesor).
- El pago con tarjeta usa un adaptador de prueba del proveedor, que conserva el contrato, la firma y las transiciones.
- `docker-compose.yml` no se probó en el equipo de desarrollo. La separación de red se demostró con procesos locales y credenciales por tramo.
- El envío de notificaciones por correo no está implementado (brecha declarada).
- Las mediciones de carga y las pruebas automatizadas se hicieron con SQLite. Con MySQL se repiten con `scripts/security_checks.py` y `scripts/load_test.py` (ver la sección de ejecución).
