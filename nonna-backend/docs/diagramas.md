# Diagramas

Fuentes editables en esta carpeta (`diagramas/*.mmd`, Mermaid). GitHub los dibuja directamente aquí.
Para editarlos en **draw.io**: *Organizar → Insertar → Avanzado → Mermaid* y pegar el contenido del `.mmd`. También se pueden abrir en https://mermaid.live para exportar PNG/SVG al informe.

Leyenda UML: `*--` composición · `o--` agregación · `--` asociación · `..` referencia lógica entre servicios (id sin FK, cada base pertenece a un servicio) · `..>` dependencia (uso de una clase o contrato) · `<<service>>` servicio público · `<<DTO>>` objeto que sale al frontend · números = multiplicidad en cada extremo.

## Módulo 2 — UML de clases del dominio y servicios públicos

Fuente: [`diagramas/01-uml-dominio.mmd`](diagramas/01-uml-dominio.mmd)

```mermaid
---
title: "Módulo 2 · UML de clases del dominio y servicios públicos (La Nonna)"
---
classDiagram
    direction TB

    %% ===================== auth (nonna_auth)
    class Usuario {
        -id: Long
        -email: String
        -passwordHash: String
        -rol: Rol
        -activo: Boolean
        -intentosFallidos: Int
        -bloqueadoHasta: DateTime
    }
    class RefreshToken {
        -id: Long
        -tokenHash: String
        -expiraEn: DateTime
        -revocadoEn: DateTime
    }
    class PerfilPersonal {
        -nombre: String
        -apellido: String
        -cargo: String
        -fechaIngreso: Date
    }
    class Rol {
        <<enumeration>>
        CLIENTE
        TRABAJADOR
        ADMIN
    }

    %% ===================== clients (nonna_clients)
    class Cliente {
        -id: Long
        -authUserId: Long
        -run: String
        -nombre: String
        -apellido: String
        -email: String
        -telefono: String
        -notificarEmail: Boolean
        -eliminadoEn: DateTime
    }
    class Direccion {
        -id: Long
        -calle: String
        -comuna: String
        -referencia: String
        -esPredeterminada: Boolean
    }

    %% ===================== inventory (nonna_inventory)
    class Categoria {
        -id: Int
        -nombre: String
    }
    class Producto {
        -id: Long
        -sku: String
        -nombre: String
        -descripcion: String
        -precioClp: Int
        -activo: Boolean
    }
    class Stock {
        -cantidadDisponible: Int
        -cantidadReservada: Int
    }
    class ReservaStock {
        -id: Long
        -pedidoId: Long
        -cantidad: Int
        -estado: EstadoReserva
        -expiraEn: DateTime
    }

    %% ===================== orders (nonna_orders)
    class Pedido {
        -id: Long
        -codigo: String
        -clienteId: Long
        -estado: EstadoPedido
        -tipoEntrega: TipoEntrega
        -direccionEntrega: String
        -subtotalClp: Int
        -costoDespachoClp: Int
        -totalClp: Int
        +transicionar(nuevo: EstadoPedido, por: String)
    }
    class ItemPedido {
        -productoId: Long
        -nombreProducto: String
        -precioUnitarioClp: Int
        -cantidad: Int
    }
    class HistorialEstado {
        -desde: EstadoPedido
        -hacia: EstadoPedido
        -cambiadoPor: String
        -cambiadoEn: DateTime
    }
    class EstadoPedido {
        <<enumeration>>
        PENDIENTE_PAGO
        PAGADO
        PREPARANDO
        LISTO
        ENTREGADO
        ANULADO
    }

    %% ===================== payments (nonna_payments)
    class Pago {
        -id: Long
        -pedidoId: Long
        -clienteId: Long
        -montoClp: Int
        -metodo: MetodoPago
        -tokenProveedor: String
        -estado: EstadoPago
        -claveIdempotencia: String
    }
    class EventoPago {
        -idEventoProveedor: String
        -firmaValida: Boolean
        -payloadSha256: String
    }
    class Boleta {
        -numero: String
        -emitidaEn: DateTime
    }

    %% ===================== Relaciones del dominio (multiplicidad en ambos extremos)
    Usuario "1" *-- "0..*" RefreshToken : sesiones
    Usuario "1" -- "0..1" PerfilPersonal : personal
    Usuario --> Rol
    Usuario "1" .. "0..1" Cliente : authUserId (ref. lógica)
    Cliente "1" *-- "0..*" Direccion : direcciones
    Categoria "1" o-- "0..*" Producto : agrupa
    Producto "1" *-- "1" Stock : existencias
    Producto "1" -- "0..*" ReservaStock : reservado en
    Pedido "1" .. "0..*" ReservaStock : pedidoId (ref. lógica)
    Cliente "1" .. "0..*" Pedido : clienteId (ref. lógica)
    Pedido "1" *-- "1..*" ItemPedido : contiene
    ItemPedido "0..*" .. "1" Producto : productoId (copia nombre/precio)
    Pedido "1" *-- "1..*" HistorialEstado : bitácora
    Pedido --> EstadoPedido
    Pedido "1" .. "0..*" Pago : pedidoId (ref. lógica)
    Pago "1" *-- "0..*" EventoPago : avisos
    Pago "1" *-- "0..1" Boleta : comprobante

    %% ===================== DTO (lo que sale al frontend)
    class ProductoDTO {
        <<DTO>>
        id, name, description, category, price_clp, available
    }
    class PedidoDTO {
        <<DTO>>
        order_code, status, delivery_type, delivery_address, totales, items
    }
    class PerfilDTO {
        <<DTO>>
        first_name, last_name, email, phone, run, notify_email
    }
    class PagoDTO {
        <<DTO>>
        id, amount_clp, method, status, receipt_number, redirect_url
    }
    class TokenDTO {
        <<DTO>>
        access_token, expires_in, refresh_token, user
    }

    %% ===================== Servicios públicos (operación -> ID de servicio)
    class AuthService {
        <<service>>
        +registrar(datos) S01
        +iniciarSesion(email, clave) S02
        +refrescar(refreshToken) S03
        +cerrarSesion(refreshToken) S04
        +yo() S05
        +crearPersonal(datos) S06
    }
    class CatalogService {
        <<service>>
        +consultarCatalogo(filtro) S07
        +consultarProducto(id) S08
        +listarCategorias() S09
        +crearProducto(datos) S10
        +reemplazarProducto(id, datos) S11
        +desactivarProducto(id) S12
        +fijarStock(id, cantidad) S13
        +consultarStock() S14
    }
    class ClientService {
        <<service>>
        +verPerfil() S15
        +reemplazarPerfil(datos) S16
        +listarDirecciones() S17
        +agregarDireccion(datos) S18
        +reemplazarDireccion(id, datos) S19
        +listarClientes(pagina) S20
    }
    class OrderService {
        <<service>>
        +crearPedido(items, entrega) S21
        +listarPedidos(filtro) S22
        +verPedido(codigo) S23
        +cambiarEstado(codigo, estado) S24
        +anularPedido(codigo) S25
        +vencerPendientes() S26
    }
    class PaymentService {
        <<service>>
        +iniciarPago(codigo, metodo, idemKey) S27
        +verPago(id) S28
        +confirmarManual(id) S29
        +recibirAviso(evento, firma) S30
    }
    class AggregationService {
        <<service>>
        +misPedidos(pagina, tamano) S31
        +pedido(codigo) S31
        +pedidosActivos(pagina, tamano) S31
        +reporteVentas(desde, hasta) S31
    }

    AuthService ..> TokenDTO
    AuthService ..> Usuario
    CatalogService ..> ProductoDTO
    CatalogService ..> Producto
    ClientService ..> PerfilDTO
    ClientService ..> Cliente
    OrderService ..> PedidoDTO
    OrderService ..> Pedido
    PaymentService ..> PagoDTO
    PaymentService ..> Pago
    AggregationService ..> PedidoDTO
    AggregationService ..> ProductoDTO
    AggregationService ..> PagoDTO
```

## Módulo 5 — UML del API Gateway, políticas y GraphQL Gateway

Fuente: [`diagramas/02-uml-gateway.mmd`](diagramas/02-uml-gateway.mmd)

```mermaid
---
title: "Módulo 5 · UML de clases del API Gateway, políticas y GraphQL Gateway"
---
classDiagram
    direction LR

    class ApiGateway {
        <<público>>
        -maxBodyBytes: Int = 65536
        -upstreamTimeout: Float = 5s
        +proxy(request) Response
        -descartarCabecerasIdentidad(request)
        -forward(route, user, body) Response
    }
    class RouteDefinition {
        -id: String  (S01..S31)
        -method: String
        -external: String
        -internal: String
        -access: ANON o AUTH
        -roles: Rol[]
        -forwardHeaders: String[]
        +match(method, path) Params
    }
    class AuthenticationPolicy {
        -algoritmo: RS256
        -issuer: nonna-auth
        -audience: nonna-api
        +authenticate(request) UserCtx
    }
    class AuthorizationPolicy {
        +permitir(route, user) Boolean
    }
    class RateLimitPolicy {
        -nombre: default, auth, graphql, webhook
        -limitePorMinuto: Int
        +allow(clave) Boolean
    }
    class ServiceTarget {
        -nombre: String
        -baseUrl: String
        -credentialRef: svc-api-gateway-to-X
    }
    class SecretProvider {
        <<interface>>
        +getSecret(ref) String
        -cacheTTL = 60s
    }
    class ServiceCredential {
        -ref: svc-llamador-to-destino
        -llamador: String
        -destino: String
    }
    class UserCtx {
        <<valor>>
        +userId: Long
        +role: Rol
        +email: String
        +asHeaders()
    }
    class InternalServiceGuard {
        <<en cada servicio>>
        +requireCallers(nombres) Caller
        +requireUser(roles) UserCtx
    }
    class AuthServiceApi {
        <<service>>
        +login() / refresh() / logout()
        -firma con jwt-private-key
    }

    class GraphQLGateway {
        <<privado>>
        -maxDepth = 6
        -maxAliases = 10
        -maxTokens = 800
        -introspeccion = false
        +execute(query, ctx)
    }
    class Schema
    class QueryResolver {
        +misPedidos()
        +pedido()
        +pedidosActivos()
        +reporteVentas()
    }
    class IsStaffPermission {
        +hasPermission(info) Boolean
    }
    class GraphQLContext {
        -user: UserCtx
        +products: DataLoader
        +payments: DataLoader
        +clients: DataLoader
    }
    class OrdersAdapter {
        <<adaptador REST>>
        GET /internal/orders
    }
    class InventoryAdapter {
        <<adaptador REST>>
        GET /internal/products?ids
    }
    class PaymentsAdapter {
        <<adaptador REST>>
        GET /internal/payments?order_ids
    }
    class ClientsAdapter {
        <<adaptador REST>>
        GET /internal/clients?ids
    }
    class AnalyticsService {
        <<privado · analítica>>
        +salesSummary(desde, hasta)
    }

    ApiGateway "1" *-- "1..*" RouteDefinition : rutas (31)
    ApiGateway "1" --> "1" AuthenticationPolicy
    ApiGateway "1" --> "1" AuthorizationPolicy
    RouteDefinition "0..*" --> "1" RateLimitPolicy : aplica
    RouteDefinition "1..*" --> "1" ServiceTarget : destino
    ServiceTarget "1" --> "1" ServiceCredential : usa
    ApiGateway ..> SecretProvider : obtiene credencial
    AuthenticationPolicy ..> SecretProvider : jwt-public-key
    AuthenticationPolicy ..> UserCtx : produce
    AuthorizationPolicy ..> UserCtx
    ServiceTarget ..> InternalServiceGuard : verificada por
    AuthServiceApi ..> SecretProvider : jwt-private-key
    ServiceTarget <|.. AuthServiceApi : auth
    ServiceTarget <|.. GraphQLGateway : graphql

    GraphQLGateway "1" *-- "1" Schema
    Schema "1" *-- "1" QueryResolver
    QueryResolver ..> IsStaffPermission : campo cliente/telefono
    QueryResolver ..> GraphQLContext
    GraphQLContext "1" *-- "1" InventoryAdapter : DataLoader productos
    GraphQLContext "1" *-- "1" PaymentsAdapter : DataLoader pagos
    GraphQLContext "1" *-- "1" ClientsAdapter : DataLoader clientes
    QueryResolver ..> OrdersAdapter
    QueryResolver ..> AnalyticsService
    GraphQLGateway ..> InternalServiceGuard : solo llamador api-gateway
    OrdersAdapter ..> SecretProvider : svc-graphql-to-orders
```

## Módulo 3 — Mapa de componentes y despliegue

Fuente: [`diagramas/03-mapa-componentes.mmd`](diagramas/03-mapa-componentes.mmd)

```mermaid
---
title: "Módulo 3 · Mapa de componentes, despliegue y fronteras de confianza"
---
flowchart LR
    subgraph EXT["Zona no confiable (Internet)"]
        NAV["Navegador<br/>frontend PHP responsivo"]
        PROV["Proveedor de pagos<br/>(externo; adaptador de prueba)"]
    end

    subgraph DMZ["Frontera pública · único puerto expuesto :8000"]
        GW["API Gateway<br/>JWT RS256 · rutas en lista blanca<br/>rol · rate limit · timeouts"]
    end

    subgraph PRIV["Red privada (sin acceso público directo)"]
        AUTH["Auth Service<br/>credenciales y sesiones"]
        GQL["GraphQL Gateway<br/>agregación"]
        subgraph TX["Servicios transaccionales"]
            CLI["clients<br/>perfil y direcciones"]
            INV["inventory<br/>catálogo · stock · reservas"]
            ORD["orders<br/>pedidos · ciclo de vida"]
            PAY["payments<br/>pagos · avisos · boletas"]
        end
        ANA["analytics<br/>reporte de ventas"]
        SEC[("Gestor de secretos<br/>SecretProvider")]
    end

    subgraph DATA["Bases de datos (un usuario MySQL por servicio)"]
        DBA[("nonna_auth")]
        DBC[("nonna_clients")]
        DBI[("nonna_inventory")]
        DBO[("nonna_orders")]
        DBP[("nonna_payments")]
    end

    NAV -- "HTTPS + Bearer JWT" --> GW
    PROV -- "webhook firmado HMAC" --> GW
    GW -- "svc token + identidad verificada" --> AUTH
    GW --> CLI
    GW --> INV
    GW --> ORD
    GW --> PAY
    GW -- "POST /graphql" --> GQL
    AUTH -- "crear perfil" --> CLI
    ORD -- "precios · reservar/confirmar/liberar" --> INV
    ORD -- "cliente y dirección" --> CLI
    PAY -- "monto oficial · marcar pagado" --> ORD
    PAY -- "cliente" --> CLI
    PAY -- "crear transacción (clave de comercio)" --> PROV
    GQL --> ORD
    GQL -- "lote productos" --> INV
    GQL -- "lote pagos" --> PAY
    GQL -- "lote clientes (solo personal)" --> CLI
    GQL -- "reporte (ADMIN)" --> ANA
    ANA -- "ventas sin datos personales" --> ORD
    AUTH --- DBA
    CLI --- DBC
    INV --- DBI
    ORD --- DBO
    PAY --- DBP
    SEC -. "referencias, nunca valores en código" .-> GW
    SEC -.-> AUTH
    SEC -.-> PAY
    SEC -.-> ORD

    classDef pub fill:#fde7c8,stroke:#b8732a
    classDef priv fill:#dcecfb,stroke:#2f6aa3
    classDef ext fill:#eeeeee,stroke:#777
    class GW pub
    class NAV,PROV ext
    class AUTH,GQL,CLI,INV,ORD,PAY,ANA priv
```

## Módulo 3 — Secuencia: pedido y pago Webpay

Fuente: [`diagramas/04-secuencia-compra.mmd`](diagramas/04-secuencia-compra.mmd)

```mermaid
---
title: "Módulo 3 · Secuencia: crear pedido y pagar con Webpay (camino feliz y fallas)"
---
sequenceDiagram
    autonumber
    actor C as Cliente (navegador)
    participant GW as API Gateway
    participant O as orders
    participant CL as clients
    participant I as inventory
    participant P as payments
    participant PR as Proveedor de pagos

    C->>GW: POST /api/v1/orders {items[product_id, quantity], delivery_type, address_id} + JWT
    GW->>GW: valida JWT, rol CLIENTE, rate limit, descarta X-User-*
    GW->>O: POST /orders (svc-api-gateway-to-orders + identidad)
    O->>CL: GET /internal/clients/by-user/{uid}
    CL-->>O: client_id
    O->>I: GET /internal/products?ids=… (precios oficiales)
    I-->>O: nombre, precio, activo
    O->>O: calcula subtotal y total, INSERT pedido PENDIENTE_PAGO + historial
    O->>I: POST /internal/reservations {order_id, items}
    alt stock suficiente
        I-->>O: 201 reserva ACTIVA (vence en 15 min)
        O-->>GW: 201 {order_code, total, payment_deadline}
    else sin stock / inventory no responde
        I-->>O: 409 OUT_OF_STOCK / timeout
        O->>O: pedido ANULADO (se conserva en historial)
        O-->>GW: 409 / 503 controlado
    end
    GW-->>C: respuesta

    C->>GW: POST /api/v1/payments {order_code, WEBPAY} + Idempotency-Key
    GW->>P: POST /payments
    P->>O: GET /internal/orders/by-code/{code}
    O-->>P: total oficial, client_id, estado
    P->>P: verifica dueño y estado · el monto NO viene del navegador
    P->>PR: POST /transactions (X-Api-Key = provider-api-key)
    PR-->>P: token, url
    P-->>GW: 201 {status INICIADO, redirect_url}
    GW-->>C: redirect_url

    C->>PR: paga en el sitio del proveedor
    PR->>GW: POST /api/v1/payments/webhook + X-Provider-Signature
    GW->>P: reenvía bytes exactos
    P->>P: verifica HMAC, monto y event_id único
    alt aviso válido y nuevo
        P->>P: pago AUTORIZADO
        P->>O: POST /internal/orders/{id}/mark-paid {payment_id, amount}
        O->>I: POST /internal/reservations/{id}/confirm
        I-->>O: CONFIRMADA
        O-->>P: PAGADO
        P->>P: emite boleta B-xxxxxx
        P-->>PR: 200
    else firma inválida o monto alterado
        P-->>PR: 401 / 400 (sin cambios)
    else aviso repetido
        P-->>PR: 200 duplicate=true (sin doble efecto)
    else orders no responde
        P-->>PR: 503 → el proveedor reintenta · el reintento solo resincroniza
    end

    Note over O,I: Si el pago no llega en 15 min: orders anula el pedido y inventory libera el stock.
```

## Módulo 5 — Solicitud autorizada y denegada

Fuente: [`diagramas/05-secuencia-autorizada-denegada.mmd`](diagramas/05-secuencia-autorizada-denegada.mmd)

```mermaid
---
title: "Módulo 5 · Recorrido de una solicitud autorizada y de una denegada"
---
sequenceDiagram
    autonumber
    actor J as Javiera (CLIENTE)
    actor M as Matías (CLIENTE)
    participant GW as API Gateway
    participant SP as SecretProvider
    participant O as orders
    participant CL as clients

    rect rgb(225, 245, 225)
    Note over J,CL: Autorizada: Javiera consulta SU pedido
    J->>GW: GET /api/v1/orders/P-1042 · Bearer JWT
    GW->>SP: jwt-public-key
    GW->>GW: firma, iss, aud y exp OK · ruta S23 AUTH · rate OK
    GW->>SP: svc-api-gateway-to-orders
    GW->>O: GET /orders/P-1042 · X-Service-* + X-User-Id=1
    O->>O: require_user: credencial de servicio válida
    O->>CL: by-user/1 → client_id=1
    O->>O: pedido.client_id == 1 ✔
    O-->>GW: 200 PedidoDTO
    GW-->>J: 200
    end

    rect rgb(250, 225, 225)
    Note over M,CL: Denegada: Matías intenta ver el pedido de Javiera
    M->>GW: GET /api/v1/orders/P-1042 · Bearer JWT · X-User-Id: 1 (falsificada)
    GW->>GW: JWT válido · descarta X-User-Id del navegador y usa sub=2
    GW->>O: GET /orders/P-1042 · X-User-Id=2
    O->>CL: by-user/2 → client_id=2
    O->>O: pedido.client_id (1) ≠ 2 ✘
    O-->>GW: 404 ORDER_NOT_FOUND (sin datos)
    GW-->>M: 404
    end

    rect rgb(250, 235, 210)
    Note over M,O: Denegada en el borde: sin token o llamada directa
    M->>GW: GET /api/v1/orders (sin token)
    GW-->>M: 401 UNAUTHENTICATED (no llega a orders)
    M-xO: GET http://orders:8004/orders (directo)
    O-->>M: 401 SERVICE_UNAUTHENTICATED (y en Docker ni siquiera hay ruta de red)
    end
```
