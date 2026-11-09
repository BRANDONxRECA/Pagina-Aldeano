# Módulo 1 — Ejemplos de contratos (generados por ejecución)

Generado con `python scripts/gen_contract_examples.py` contra el sistema real con datos **ficticios**. Tokens y firmas reemplazados por `<...>`; listas largas recortadas con `…`.

### S01 · Registrar cliente

`POST /api/v1/auth/register` · actor: **Visitante** · respuesta **201**

Solicitud:
```json
{
  "email": "camila@example.cl",
  "password": "Pasta2026",
  "first_name": "Camila",
  "last_name": "Rojas",
  "phone": "+56944444444",
  "run": "12345678-5"
}
```
Respuesta:
```json
{
  "id": 5,
  "email": "camila@example.cl",
  "role": "CLIENTE"
}
```

### S02 · Iniciar sesión

`POST /api/v1/auth/login` · actor: **Visitante** · respuesta **200**

Solicitud:
```json
{
  "email": "javiera@example.cl",
  "password": "Cliente123"
}
```
Respuesta:
```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_token": "<token opaco>",
  "user": {
    "id": 1,
    "email": "javiera@example.cl",
    "role": "CLIENTE"
  }
}
```

### S02 · Iniciar sesión (error)

`POST /api/v1/auth/login` · actor: **Visitante** · respuesta **401**

Solicitud:
```json
{
  "email": "javiera@example.cl",
  "password": "incorrecta1"
}
```
Respuesta:
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Correo o contraseña incorrectos",
    "correlation_id": "ca6d5f6bfd0b49cd848632dcece5e613"
  }
}
```

### S03 · Renovar sesión (rota el refresh token)

`POST /api/v1/auth/refresh` · actor: **Cliente** · respuesta **200**

Solicitud:
```json
{
  "refresh_token": "<token opaco>"
}
```
Respuesta:
```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_token": "<token opaco>",
  "user": {
    "id": 1,
    "email": "javiera@example.cl",
    "role": "CLIENTE"
  }
}
```

### S04 · Cerrar sesión (revoca el refresh token)

`POST /api/v1/auth/logout` · actor: **Cliente** · respuesta **204**

Solicitud:
```json
{
  "refresh_token": "<token opaco>"
}
```
Respuesta:
```json
(sin cuerpo)
```

### S05 · Usuario actual

`GET /api/v1/auth/me` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "id": 1,
  "email": "javiera@example.cl",
  "role": "CLIENTE"
}
```

### S06 · Crear trabajador

`POST /api/v1/admin/staff` · actor: **Admin** · respuesta **201**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "email": "despacho@lanonna.test",
  "password": "Despacho2026",
  "first_name": "Luis",
  "last_name": "Vera",
  "position": "Despacho",
  "role": "TRABAJADOR"
}
```
Respuesta:
```json
{
  "id": 6,
  "email": "despacho@lanonna.test",
  "role": "TRABAJADOR"
}
```

### S07 · Consultar catálogo

`GET /api/v1/products?available=true&category=Lasañas` · actor: **Visitante** · respuesta **200**

Respuesta:
```json
[
  {
    "id": 4,
    "name": "Lasaña a la bolognesa",
    "description": "Ragú de vacuno y bechamel casera.",
    "category": "Lasañas",
    "price_clp": 8900,
    "available": true
  },
  {
    "id": 5,
    "name": "Lasaña de verduras de estación",
    "description": "Zapallo italiano y berenjena.",
    "category": "Lasañas",
    "price_clp": 7800,
    "available": true
  },
  "…"
]
```

### S08 · Consultar producto

`GET /api/v1/products/4` · actor: **Visitante** · respuesta **200**

Respuesta:
```json
{
  "id": 4,
  "name": "Lasaña a la bolognesa",
  "description": "Ragú de vacuno y bechamel casera.",
  "category": "Lasañas",
  "price_clp": 8900,
  "available": true
}
```

### S09 · Listar categorías

`GET /api/v1/categories` · actor: **Visitante** · respuesta **200**

Respuesta:
```json
[
  {
    "id": 1,
    "name": "Ravioles"
  },
  {
    "id": 2,
    "name": "Lasañas"
  },
  "…"
]
```

### S10 · Crear producto

`POST /api/v1/products` · actor: **Admin** · respuesta **201**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "category_id": 3,
  "sku": "TAL-ALFR",
  "name": "Fettuccine Alfredo",
  "description": "Crema y parmesano.",
  "price_clp": 7900,
  "initial_stock": 15
}
```
Respuesta:
```json
{
  "id": 10,
  "name": "Fettuccine Alfredo",
  "description": "Crema y parmesano.",
  "category": "Tallarines",
  "price_clp": 7900,
  "available": true
}
```

### S11 · Reemplazar producto

`PUT /api/v1/products/10` · actor: **Admin** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "category_id": 3,
  "sku": "TAL-ALFR",
  "name": "Fettuccine Alfredo",
  "description": "Crema, mantequilla y parmesano.",
  "price_clp": 8200,
  "active": true
}
```
Respuesta:
```json
{
  "id": 10,
  "name": "Fettuccine Alfredo",
  "description": "Crema, mantequilla y parmesano.",
  "category": "Tallarines",
  "price_clp": 8200,
  "available": true
}
```

### S12 · Desactivar producto

`DELETE /api/v1/products/10` · actor: **Admin** · respuesta **204**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
(sin cuerpo)
```

### S12 · Desactivar producto (cliente: denegado)

`DELETE /api/v1/products/1` · actor: **Cliente** · respuesta **403**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "No tiene permisos para esta operación",
    "correlation_id": "7f8db20dde8e4f859803ba138cca9e58"
  }
}
```

### S13 · Fijar stock

`PUT /api/v1/products/7/stock` · actor: **Trabajador** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "quantity_available": 45
}
```
Respuesta:
```json
{
  "product_id": 7,
  "quantity_available": 45,
  "quantity_reserved": 0
}
```

### S14 · Consultar stock

`GET /api/v1/admin/stock` · actor: **Trabajador** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
[
  {
    "id": 1,
    "sku": "RAV-RICO",
    "name": "Ravioles de ricotta y espinaca",
    "active": true,
    "quantity_available": 30,
    "quantity_reserved": 0
  },
  {
    "id": 2,
    "sku": "RAV-OSOB",
    "name": "Ravioles de osobuco",
    "active": true,
    "quantity_available": 20,
    "quantity_reserved": 0
  },
  "…"
]
```

### S15 · Ver perfil

`GET /api/v1/me` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "id": 1,
  "first_name": "Javiera",
  "last_name": "Rojas",
  "email": "javiera@example.cl",
  "phone": "+56911111111",
  "run": "11111111-1",
  "notify_email": true
}
```

### S16 · Reemplazar perfil

`PUT /api/v1/me` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "first_name": "Javiera",
  "last_name": "Rojas",
  "phone": "+56911111111",
  "notify_email": false
}
```
Respuesta:
```json
{
  "id": 1,
  "first_name": "Javiera",
  "last_name": "Rojas",
  "email": "javiera@example.cl",
  "phone": "+56911111111",
  "run": "11111111-1",
  "notify_email": false
}
```

### S17 · Listar direcciones

`GET /api/v1/me/addresses` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
[
  {
    "id": 1,
    "street": "Calle Ficticia 123",
    "commune": "Maipú",
    "reference": "Casa azul",
    "is_default": true
  }
]
```

### S18 · Agregar dirección

`POST /api/v1/me/addresses` · actor: **Cliente** · respuesta **201**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "street": "Av. Pajaritos 1500",
  "commune": "Maipú",
  "reference": "Depto 302",
  "is_default": false
}
```
Respuesta:
```json
{
  "id": 3,
  "street": "Av. Pajaritos 1500",
  "commune": "Maipú",
  "reference": "Depto 302",
  "is_default": false
}
```

### S19 · Reemplazar dirección

`PUT /api/v1/me/addresses/3` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "street": "Av. Pajaritos 1500",
  "commune": "Maipú",
  "reference": "Depto 303",
  "is_default": true
}
```
Respuesta:
```json
{
  "id": 3,
  "street": "Av. Pajaritos 1500",
  "commune": "Maipú",
  "reference": "Depto 303",
  "is_default": true
}
```

### S20 · Listar clientes (admin)

`GET /api/v1/admin/clients?page=1&page_size=2` · actor: **Admin** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "page": 1,
  "page_size": 2,
  "total": 3,
  "items": [
    {
      "id": 1,
      "first_name": "Javiera",
      "last_name": "Rojas",
      "email": "javiera@example.cl",
      "run": "****111-1",
      "phone": "+569*****11",
      "created_at": "2026-11-08T21:46:23"
    },
    {
      "id": 2,
      "first_name": "Matías",
      "last_name": "Pérez",
      "email": "matias@example.cl",
      "run": "****222-2",
      "phone": "+569*****22",
      "created_at": "2026-11-08T21:46:23"
    }
  ]
}
```

### S21 · Crear pedido

`POST /api/v1/orders` · actor: **Cliente** · respuesta **201**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "items": [
    {
      "product_id": 4,
      "quantity": 1
    },
    {
      "product_id": 7,
      "quantity": 2
    }
  ],
  "delivery_type": "DESPACHO",
  "address_id": 3
}
```
Respuesta:
```json
{
  "order_code": "P-933341",
  "status": "PENDIENTE_PAGO",
  "delivery_type": "DESPACHO",
  "delivery_address": "Av. Pajaritos 1500, Maipú",
  "subtotal_clp": 22700,
  "delivery_fee_clp": 0,
  "total_clp": 22700,
  "created_at": "2026-11-08T21:46:25",
  "items": [
    {
      "product_id": 4,
      "product_name": "Lasaña a la bolognesa",
      "unit_price_clp": 8900,
      "quantity": 1,
      "line_total_clp": 8900
    },
    {
      "product_id": 7,
      "product_name": "Tallarines al pesto genovés",
      "unit_price_clp": 6900,
      "quantity": 2,
      "line_total_clp": 13800
    }
  ],
  "payment_deadline": "2026-11-08T22:01:25.663613"
}
```

### S21 · Crear pedido (precio enviado por el navegador: rechazado)

`POST /api/v1/orders` · actor: **Cliente** · respuesta **422**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "items": [
    {
      "product_id": 4,
      "quantity": 1,
      "unit_price_clp": 10
    }
  ],
  "delivery_type": "RETIRO"
}
```
Respuesta:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos de entrada inválidos",
    "correlation_id": "ba6b767daa9d4c1ba8c8f714b5555df0",
    "fields": [
      {
        "field": "items.0.unit_price_clp",
        "issue": "Extra inputs are not permitted"
      }
    ]
  }
}
```

### S22 · Listar pedidos

`GET /api/v1/orders?page=1&page_size=2` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "page": 1,
  "page_size": 2,
  "total": 3,
  "items": [
    {
      "order_code": "P-933341",
      "status": "PENDIENTE_PAGO",
      "delivery_type": "DESPACHO",
      "delivery_address": "Av. Pajaritos 1500, Maipú",
      "subtotal_clp": 22700,
      "delivery_fee_clp": 0,
      "total_clp": 22700,
      "created_at": "2026-11-08T21:46:25",
      "items": [
        {
          "product_id": 4,
          "product_name": "Lasaña a la bolognesa",
          "unit_price_clp": 8900,
          "quantity": 1,
          "line_total_clp": 8900
        },
        {
          "product_id": 7,
          "product_name": "Tallarines al pesto genovés",
          "unit_price_clp": 6900,
          "quantity": 2,
          "line_total_clp": 13800
        }
      ]
    },
    {
      "order_code": "P-1058",
      "status": "ENTREGADO",
      "delivery_type": "RETIRO",
      "delivery_address": null,
      "subtotal_clp": 19000,
      "delivery_fee_clp": 0,
      "total_clp": 19000,
      "created_at": "2026-09-10T20:05:00",
      "items": [
        {
          "product_id": 2,
          "product_name": "Ravioles de osobuco",
          "unit_price_clp": 9500,
          "quantity": 2,
          "line_total_clp": 19000
        }
      ]
    }
  ]
}
```

### S23 · Ver pedido

`GET /api/v1/orders/P-933341` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "order_code": "P-933341",
  "status": "PENDIENTE_PAGO",
  "delivery_type": "DESPACHO",
  "delivery_address": "Av. Pajaritos 1500, Maipú",
  "subtotal_clp": 22700,
  "delivery_fee_clp": 0,
  "total_clp": 22700,
  "created_at": "2026-11-08T21:46:25",
  "items": [
    {
      "product_id": 4,
      "product_name": "Lasaña a la bolognesa",
      "unit_price_clp": 8900,
      "quantity": 1,
      "line_total_clp": 8900
    },
    {
      "product_id": 7,
      "product_name": "Tallarines al pesto genovés",
      "unit_price_clp": 6900,
      "quantity": 2,
      "line_total_clp": 13800
    }
  ]
}
```

### S23 · Ver pedido ajeno (denegado)

`GET /api/v1/orders/P-1093` · actor: **Cliente** · respuesta **404**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "error": {
    "code": "ORDER_NOT_FOUND",
    "message": "Pedido no encontrado",
    "correlation_id": "7e837a181fcc42ca83f27d452411eb7d"
  }
}
```

### S24 · Cambiar estado (cocina)

`PATCH /api/v1/orders/P-933341/status` · actor: **Trabajador** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "status": "PREPARANDO"
}
```
Respuesta:
```json
{
  "order_code": "P-933341",
  "status": "PREPARANDO"
}
```

### S24 · Cambiar estado (cliente marca PAGADO: denegado)

`PATCH /api/v1/orders/P-933341/status` · actor: **Cliente** · respuesta **403**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "status": "PAGADO"
}
```
Respuesta:
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "No tiene permisos para esta operación",
    "correlation_id": "13376244a51c49ad98c4f35b86804737"
  }
}
```

### S25 · Anular pedido

`POST /api/v1/orders/P-577954/cancel` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "order_code": "P-577954",
  "status": "ANULADO"
}
```

### S26 · Vencer pedidos impagos

`POST /api/v1/admin/orders/expire-pending` · actor: **Admin** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "expired_orders": 0
}
```

### S27 · Iniciar pago Webpay

`POST /api/v1/payments` · actor: **Cliente** · respuesta **201**

Cabeceras: `Authorization: Bearer <jwt>`, `Idempotency-Key: pago-ejemplo-0001`

Solicitud:
```json
{
  "order_code": "P-933341",
  "method": "WEBPAY"
}
```
Respuesta:
```json
{
  "id": 5,
  "order_id": 5,
  "amount_clp": 22700,
  "method": "WEBPAY",
  "status": "INICIADO",
  "receipt_number": null,
  "created_at": "2026-11-08T21:46:25",
  "redirect_url": "http://provider.internal/pay/tok_7c9712809d198fc970497ecc3988c881"
}
```

### S28 · Ver pago

`GET /api/v1/payments/5` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "id": 5,
  "order_id": 5,
  "amount_clp": 22700,
  "method": "WEBPAY",
  "status": "AUTORIZADO",
  "receipt_number": "B-000005",
  "created_at": "2026-11-08T21:46:25"
}
```

### S29 · Confirmar pago en efectivo

`POST /api/v1/payments/6/confirm-manual` · actor: **Trabajador** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Respuesta:
```json
{
  "id": 6,
  "order_id": 6,
  "amount_clp": 6500,
  "method": "EFECTIVO",
  "status": "AUTORIZADO",
  "receipt_number": "B-000006",
  "created_at": "2026-11-08T21:46:25",
  "order_synced": true
}
```

### S30 · Aviso del proveedor (firma válida)

`POST /api/v1/payments/webhook` · actor: **Proveedor** · respuesta **200**

Cabeceras: `Content-Type: application/json`, `X-Provider-Signature: <hmac-sha256 hex>`

Solicitud:
```json
{
  "event_id": "evt_ejemplo_0001",
  "token": "<token de transacción>",
  "result": "AUTHORIZED",
  "amount": 22700
}
```
Respuesta:
```json
{
  "payment_id": 5,
  "status": "AUTORIZADO",
  "duplicate": false,
  "order_synced": true,
  "receipt_number": "B-000005"
}
```

### S30 · Aviso falso (sin firma)

`POST /api/v1/payments/webhook` · actor: **Atacante** · respuesta **401**

Cabeceras: `Content-Type: application/json`

Solicitud:
```json
{
  "event_id": "evt_ejemplo_0001",
  "token": "<token de transacción>",
  "result": "AUTHORIZED",
  "amount": 22700
}
```
Respuesta:
```json
{
  "error": {
    "code": "INVALID_SIGNATURE",
    "message": "Firma del proveedor inválida",
    "correlation_id": "40cedff236db4a4b88b098b8f9f8b881"
  }
}
```

### S31 · GraphQL misPedidos

`POST /api/v1/graphql` · actor: **Cliente** · respuesta **200**

Cabeceras: `Authorization: Bearer <jwt>`

Solicitud:
```json
{
  "query": "query($p:Int!,$t:Int!){ misPedidos(pagina:$p,tamano:$t){ total items { codigo estado total pago { estado numeroBoleta } items { nombre cantidad productoActual { precio disponible } } } } }",
  "variables": {
    "p": 1,
    "t": 2
  }
}
```
Respuesta:
```json
{
  "data": {
    "misPedidos": {
      "total": 5,
      "items": [
        {
          "codigo": "P-577954",
          "estado": "ANULADO",
          "total": 7400,
          "pago": null,
          "items": [
            {
              "nombre": "Tallarines a la carbonara",
              "cantidad": 1,
              "productoActual": {
                "precio": 7400,
                "disponible": true
              }
            }
          ]
        },
        {
          "codigo": "P-826220",
          "estado": "PAGADO",
          "total": 6500,
          "pago": {
            "estado": "AUTORIZADO",
            "numeroBoleta": "B-000006"
          },
          "items": [
            {
              "nombre": "Tallarines al pomodoro",
              "cantidad": 1,
              "productoActual": {
                "precio": 6500,
                "disponible": true
              }
            }
          ]
        }
      ]
    }
  }
}
```
