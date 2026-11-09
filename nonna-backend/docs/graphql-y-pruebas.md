# Módulo 8 — GraphQL Gateway · Módulos 7 y 10 — Pruebas

## Separación privada (mapa de clasificación)

| Servicio | Naturaleza | Responsabilidad | Datos propios | Contrato | Dependencias | Justificación de la separación |
|---|---|---|---|---|---|---|
| api-gateway | Borde (público) | Enrutar, autenticar el JWT, autorizar por rol, limitar | — (sin BD) | `routes.py` | todos | Único punto expuesto |
| auth | Transaccional (privado) | Credenciales, roles, sesiones | `nonna_auth` | REST `/auth/*` | clients | Las credenciales se aíslan de los datos personales |
| clients | Transaccional (privado) | Perfil y direcciones | `nonna_clients` | REST `/me*`, `/internal/clients*` | — | Datos restringidos con un único custodio |
| inventory | Transaccional + alta demanda de lectura | Catálogo, precio oficial, stock, reservas | `nonna_inventory` | REST `/products*`, `/internal/reservations*` | — | El catálogo se lee mucho y cambia poco; el stock tiene su propia autoridad |
| orders | Transaccional (privado) | Pedido y ciclo de vida | `nonna_orders` | REST `/orders*`, `/internal/orders*` | inventory, clients | Estado oficial del pedido |
| payments | Transaccional (privado) | Pagos, avisos del proveedor, boletas | `nonna_payments` | REST `/payments*`, webhook | orders, clients, proveedor | Aísla la clave del comercio y la verificación de firmas |
| graphql | Agregación (privado) | Vistas combinadas para pantallas | — (sin BD) | `docs/schema.graphql` | orders, inventory, payments, clients, analytics | Compone sin tocar bases ajenas |
| analytics | Analítica (privado) | Reporte de ventas | — (caché) | REST `/internal/sales/summary` | orders | No carga las consultas transaccionales |

## Schema

Completo en [`schema.graphql`](schema.graphql). Pantallas que lo usan: **Historial** (`misPedidos`), detalle de un
pedido (`pedido`), panel de cocina (`pedidosActivos`) y administración (`reporteVentas`).

### Consulta de prueba (pantalla Historial)

```graphql
query Historial($p: Int!, $t: Int!) {
  misPedidos(pagina: $p, tamano: $t) {
    total
    items {
      codigo estado total creadoEn
      items { nombre cantidad precioUnitario productoActual { precio disponible } }
      pago { estado metodo numeroBoleta }
    }
  }
}
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/graphql -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"query":"query($p:Int!,$t:Int!){ misPedidos(pagina:$p,tamano:$t){ total items { codigo estado total pago { numeroBoleta } items { nombre productoActual { precio disponible } } } } }","variables":{"p":1,"t":2}}'
```

Respuesta obtenida en ejecución (datos ficticios del seed, usuario javiera@example.cl):

```json
{"data":{"misPedidos":{"total":2,"items":[
  {"codigo":"P-1058","estado":"ENTREGADO","total":19000,"pago":{"numeroBoleta":"B-000002"},
   "items":[{"nombre":"Ravioles de osobuco","productoActual":{"precio":9500,"disponible":true}}]},
  {"codigo":"P-1042","estado":"ENTREGADO","total":22700,"pago":{"numeroBoleta":"B-000001"},
   "items":[{"nombre":"Lasaña a la bolognesa","productoActual":{"precio":8900,"disponible":true}},
            {"nombre":"Tallarines al pesto genovés","productoActual":{"precio":6900,"disponible":true}}]}]}}}
```

Si **inventory** no responde, la respuesta llega igual: `productoActual` viene en `null` y `errors` incluye
`{"extensions":{"code":"DEPENDENCY_UNAVAILABLE"}}` (prueba `test_error_parcial_si_inventory_cae`).

### Matriz de autorización GraphQL

| Elemento | CLIENTE | TRABAJADOR | ADMIN | Dónde se verifica |
|---|---|---|---|---|
| `misPedidos` | propios | denegado | denegado | resolver (rol) + `client_id` sacado de la identidad verificada |
| `pedido(codigo)` | solo si es dueño (si no, `ORDER_NOT_FOUND`) | todos | todos | resolver + `client_id` |
| `Pedido.cliente`, `ClienteResumen.telefono` | null + error | permitido | permitido | `IsStaff` (permiso por campo) |
| `pedidosActivos` | denegado | permitido | permitido | resolver |
| `reporteVentas` | denegado | denegado | permitido | resolver; analytics solo acepta al llamador `graphql` |
| Acceso directo a `graphql:/graphql` | 401 | 401 | 401 | `require_callers("api-gateway")` |

Límites probados: paginación de 1 a 50 (`BAD_PAGINATION`), más de 10 alias rechazado, más de 800 tokens rechazado,
introspección deshabilitada. Batching: con varios pedidos e ítems hay **1** llamada a inventory y **1** a payments
(`test_dataloader_un_llamado_por_subsistema`).

## Casos de validación del Módulo 7 (ejecutados)

Resultado completo: [`evidencias/pytest.txt`](evidencias/pytest.txt) — **39 pruebas, 39 aprobadas**.

| # | Caso | Entrada | Identidad | Resultado esperado y obtenido | Componente que verifica | Prueba |
|---|---|---|---|---|---|---|
| 1 | Catálogo anónimo | `GET /api/v1/products` | ninguna | 200, solo campos públicos (sin stock exacto) | gateway (S07 ANON) + inventory | `test_m7_1_catalogo_anonimo`, `test_catalogo_publico_sin_sesion` |
| 2 | Operación protegida sin sesión válida | `GET /api/v1/orders` sin token, con token falso, firmado con otra clave o `alg=none` | ninguna / falsificada | 401 | api-gateway (AuthenticationPolicy) | `test_m7_2_*` |
| 3 | Administración desde un rol sin permiso | `DELETE /api/v1/products/1`, `POST /products`, `GET /admin/clients` | CLIENTE / TRABAJADOR | 403; las cabeceras `X-User-Role: ADMIN` falsificadas se descartan | gateway + inventory/clients (`require_user`) | `test_m7_3_*` |
| 4 | Pedido ajeno | `GET /api/v1/orders/P-1042`, cancelar o pagar | matias (dueño: javiera) | 404 sin datos; el listado solo trae los propios | orders y payments (propiedad) | `test_m7_4_pedido_ajeno`, `test_pedido_ajeno_por_graphql` |
| 5 | Acceso directo al backend | `GET inventory:/products` sin credencial; token de otro tramo; token del gateway contra `/internal/reservations` | sin identidad / identidad equivocada | 401 / 403 | cada servicio (`require_callers`) | `test_m7_5_*`, `test_graphql_privado_no_accesible_directo` |
| 6 | Pago con datos alterados | monto en el cuerpo; `PATCH status=PAGADO`; webhook sin firma, con firma inventada o con monto alterado | CLIENTE / atacante | 422 / 403 / 401 / 400; el pedido sigue en PENDIENTE_PAGO | payments (HMAC, monto oficial) + orders (solo payments marca PAGADO) | `test_m7_6_pago_alterado` |

Otras pruebas: bloqueo tras 5 intentos fallidos (423), login que no revela si el correo existe, rate limit (429),
dependencia caída (503 controlado, sin traza), RUN y teléfono enmascarados, respuestas sin hash ni token, aviso de
pago duplicado sin doble efecto, reserva vencida que devuelve el stock, idempotencia del pago y transiciones de
estado inválidas (409).

## Matriz requisito → pantalla → servicio → prueba (Módulo 10)

| Requisito | Pantalla | Servicio(s) | Prueba | Resultado |
|---|---|---|---|---|
| Registro de cliente | index → Crear cuenta | S01 | `test_registro_login_refresh_logout` | aprobado |
| Inicio de sesión cliente / trabajador | index → Iniciar sesión / Trabajadores | S02–S05 | ídem, `test_bloqueo_por_intentos_fallidos` | aprobado |
| Ver carta | carta.php | S07–S09 | `test_catalogo_publico_sin_sesion` | aprobado |
| Carrito → pedido (despacho o retiro) | carrito.php | S21, S17 | `test_compra_completa_webpay` | aprobado |
| Pago con tarjeta (Webpay) | carrito.php → Pagar | S27, S30 | `test_compra_completa_webpay` | aprobado |
| Pago con transferencia o efectivo | carrito.php → Pagar | S27, S29 | `test_pago_efectivo_confirmado_por_personal` | aprobado |
| Historial de compras | historial.php | S31 `misPedidos`, S22 | `test_agregacion_mis_pedidos_combina_tres_subsistemas` | aprobado |
| Anular pedido | historial.php | S25 | `test_stock_insuficiente_y_anulacion_libera_stock` | aprobado |
| Panel de cocina (estados) | (brecha: sin pantalla) | S24, S31 `pedidosActivos` | `test_compra_completa_webpay`, `test_panel_cocina_y_reporte_admin` | aprobado |
| Administración de carta y stock | (brecha: sin pantalla) | S10–S14 | `test_admin_crud_producto` | aprobado |
| Reporte de ventas | (brecha: sin pantalla) | S31 `reporteVentas` | `test_panel_cocina_y_reporte_admin` | aprobado |
