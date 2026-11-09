# ADR-001 — Analítica y gRPC (Módulo 9)

**Estado:** aceptado · **Fecha:** 2026-11-08

## Contexto

La Nonna es un local de pastas en Maipú con despacho y retiro. Los requisitos que tienen que ver con carga son:
el catálogo (lectura pública), el carrito y el pedido, el pago, el historial del cliente, el panel de cocina y
un reporte de ventas para administración.

### Matriz de necesidades

| Característica | Estimación (proyección) | Medición (`scripts/load_test.py`) |
|---|---|---|
| Volumen de datos | ~200 pedidos/día ≈ 73.000/año; ~3 ítems por pedido; catálogo < 50 productos | — |
| Concurrencia | punta de almuerzo/cena: ~5 usuarios activos simultáneos (≈ 1–2 req/s) | Se probó con 5 y 20 workers que envían solicitudes sin pausa |
| Tamaño de mensajes | < 5 KB (pedido con ≤ 20 líneas; página GraphQL de ≤ 50 pedidos ≈ 30 KB) | — |
| Frecuencia | catálogo y GraphQL en cada visita; pedido + pago 1–2 veces por visita | — |
| Latencia esperada | p95 < 500 ms con la concurrencia de punta | **p95 = 186 ms** con 5 de concurrencia, 59 req/s, 0 errores |
| Streaming | No: el estado del pedido se consulta (historial y panel); no hay telemetría continua | — |

Mediciones (entorno: Windows 11, un proceso uvicorn por servicio, SQLite, 30 s, mezcla 60 % catálogo /
25 % GraphQL / 15 % crear+anular pedido; resultados en `docs/evidencias/carga-*.json`):

| Concurrencia | Solicitudes | Throughput | p50 | p95 | p99 | Errores |
|---|---|---|---|---|---|---|
| 5 | 1.787 | 59,3 req/s | 50 ms | **186 ms** | 218 ms | 0 |
| 20 | 1.195 | 39,4 req/s | 333 ms | 1.455 ms | 2.158 ms | 0 |

Con 20 trabajadores sin pausa (≈ 25 veces la punta proyectada) no hay errores, pero la latencia sube por la
contención de escritura de SQLite y porque cada servicio corre un solo worker. Con MySQL (InnoDB, bloqueo por fila) y
`--workers` > 1 se espera una mejora, pero **no se afirma sin medirla**.

## Decisión

1. **Servicio de analítica: SÍ, liviano y separado** (`services/analytics_service`).
   - Motivo: el reporte de ventas recorre todos los pedidos de un rango. No debe cargar las consultas
     transaccionales de orders ni exponer datos personales.
   - Origen: API interna `orders /internal/sales-source` (sin `client_id`, sin dirección). No lee la base de orders.
   - Actualización: bajo demanda, con caché de 60 s (retraso aceptado: 60 s).
   - Agregaciones: ingresos, pedidos pagados y anulados, ticket promedio, % despacho, ventas por día y top 5 de productos.
   - Permisos: solo el GraphQL Gateway puede llamarlo (`svc-graphql-to-analytics`), y GraphQL solo lo expone a ADMIN
     (`reporteVentas`).
   - **Sin big data:** 73 mil pedidos al año caben de sobra en una agregación en memoria.

2. **gRPC: NO se implementa.**
   - No hay procesamiento intensivo ni streaming: los mensajes son pequeños, la frecuencia es baja y la medición
     cumple el objetivo de latencia con REST/JSON interno.
   - El único flujo "en vivo" (estado del pedido) se resuelve consultando el estado. El navegador tampoco podría
     consumir gRPC directamente: necesitaría un adaptador (SSE o WebSocket) que no se justifica con esta carga.
   - Alternativas consideradas:
     (a) gRPC unary entre orders e inventory para reservas: el contrato tipado es atractivo, pero REST ya tiene
     validación estricta (Pydantic, `extra=forbid`), plazo máximo y autenticación por tramo. Agregaría `.proto`,
     certificados mTLS y otro stack sin una ganancia medible.
     (b) Streaming de servidor para el panel de cocina: la cocina ve pocos pedidos y los consulta al refrescar.

## Consecuencias

- Menos componentes que operar y asegurar (sin mTLS adicional ni generación de stubs).
- Si la carga crece (varias sucursales, más de 10 veces el volumen) o aparece seguimiento de despacho en tiempo real,
  se revisa esta decisión: gRPC server-streaming entre un servicio de despacho y un adaptador SSE en el gateway.
- La evidencia reproducible de que la alternativa elegida aguanta la carga es `scripts/load_test.py` + `docs/evidencias/`.
