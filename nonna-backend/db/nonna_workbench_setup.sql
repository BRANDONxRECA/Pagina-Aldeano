-- =====================================================================
-- La Nonna — instalación completa para MySQL Workbench (MySQL 8.0.16 o superior)
-- Ejecutar con: File > Open SQL Script > rayo (Execute) o Ctrl+Shift+Enter
--
-- ANTES DE EJECUTAR: reemplaza (Ctrl+H) las 5 contraseñas CAMBIAR_* por las tuyas.
-- ADVERTENCIA: este script BORRA y vuelve a crear las 5 bases nonna_*.
-- =====================================================================

DROP DATABASE IF EXISTS nonna_auth;
DROP DATABASE IF EXISTS nonna_clients;
DROP DATABASE IF EXISTS nonna_inventory;
DROP DATABASE IF EXISTS nonna_orders;
DROP DATABASE IF EXISTS nonna_payments;

CREATE DATABASE nonna_auth      CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE nonna_clients   CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE nonna_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE nonna_orders    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE nonna_payments  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Un usuario por servicio, con permisos solo sobre su base.
-- Sin DELETE en auth, clients, orders y payments: se conserva el historial.
DROP USER IF EXISTS 'svc_auth'@'localhost';
DROP USER IF EXISTS 'svc_clients'@'localhost';
DROP USER IF EXISTS 'svc_inventory'@'localhost';
DROP USER IF EXISTS 'svc_orders'@'localhost';
DROP USER IF EXISTS 'svc_payments'@'localhost';

CREATE USER 'svc_auth'@'localhost'      IDENTIFIED BY 'usuario';
CREATE USER 'svc_clients'@'localhost'   IDENTIFIED BY 'Clientes';
CREATE USER 'svc_inventory'@'localhost' IDENTIFIED BY 'Inventario';
CREATE USER 'svc_orders'@'localhost'    IDENTIFIED BY 'ordenes';
CREATE USER 'svc_payments'@'localhost'  IDENTIFIED BY 'Pagos';

GRANT SELECT, INSERT, UPDATE         ON nonna_auth.*      TO 'svc_auth'@'localhost';
GRANT SELECT, INSERT, UPDATE         ON nonna_clients.*   TO 'svc_clients'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON nonna_inventory.* TO 'svc_inventory'@'localhost';
GRANT SELECT, INSERT, UPDATE         ON nonna_orders.*    TO 'svc_orders'@'localhost';
GRANT SELECT, INSERT, UPDATE         ON nonna_payments.*  TO 'svc_payments'@'localhost';
FLUSH PRIVILEGES;


-- ---------- 01-auth.sql ----------
-- Autoridad: Auth Service. Credenciales y sesiones. Ningún otro servicio lee esta base.
USE nonna_auth;

CREATE TABLE users (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email            VARCHAR(190) NOT NULL,
  password_hash    VARCHAR(255) NOT NULL COMMENT 'bcrypt/argon2 con sal; nunca reversible',
  role             ENUM('CLIENTE','TRABAJADOR','ADMIN') NOT NULL DEFAULT 'CLIENTE',
  active           TINYINT(1) NOT NULL DEFAULT 1,
  failed_attempts  TINYINT UNSIGNED NOT NULL DEFAULT 0,
  locked_until     DATETIME NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

-- Se guarda solo el hash del refresh token; permite revocar sesiones.
CREATE TABLE refresh_tokens (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  token_hash  CHAR(64) NOT NULL COMMENT 'SHA-256 del token',
  expires_at  DATETIME NOT NULL,
  revoked_at  DATETIME NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_refresh_hash (token_hash),
  KEY idx_refresh_user (user_id),
  CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Perfil del personal (trabajadores y administradores). Cada perfil pertenece a un usuario con rol TRABAJADOR o ADMIN.
-- Los clientes NO van aquí: su perfil vive en nonna_clients.
CREATE TABLE staff_profiles (
  user_id     BIGINT UNSIGNED NOT NULL,
  first_name  VARCHAR(80) NOT NULL,
  last_name   VARCHAR(80) NOT NULL,
  position    VARCHAR(60) NOT NULL COMMENT 'cargo, ej. Cocina, Despacho, Administración',
  hired_at    DATE NOT NULL,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_staff_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------- 02-clients.sql ----------
-- Autoridad: clients. Perfil y direcciones (datos personales, clasificación: RESTRINGIDO).
USE nonna_clients;

CREATE TABLE clients (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  auth_user_id  BIGINT UNSIGNED NOT NULL COMMENT 'referencia lógica a nonna_auth.users (sin FK entre servicios)',
  run           VARCHAR(12) NULL,
  first_name    VARCHAR(80) NOT NULL,
  last_name     VARCHAR(80) NOT NULL,
  email         VARCHAR(190) NOT NULL,
  phone         VARCHAR(20) NULL,
  notify_email  TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at    DATETIME NULL COMMENT 'baja lógica',
  PRIMARY KEY (id),
  UNIQUE KEY uq_clients_auth_user (auth_user_id),
  UNIQUE KEY uq_clients_email (email),
  UNIQUE KEY uq_clients_run (run)
) ENGINE=InnoDB;

-- Un cliente tiene 0..* direcciones; cada dirección pertenece a un solo cliente.
CREATE TABLE addresses (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  client_id   BIGINT UNSIGNED NOT NULL,
  street      VARCHAR(160) NOT NULL,
  commune     VARCHAR(80) NOT NULL,
  reference   VARCHAR(160) NULL,
  is_default  TINYINT(1) NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_addresses_client (client_id),
  CONSTRAINT fk_addresses_client FOREIGN KEY (client_id) REFERENCES clients(id)
) ENGINE=InnoDB;

-- ---------- 03-inventory.sql ----------
-- Autoridad: inventory. Catálogo (público), stock y reservas.
USE nonna_inventory;

CREATE TABLE categories (
  id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(60) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB;

CREATE TABLE products (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id  SMALLINT UNSIGNED NOT NULL,
  sku          VARCHAR(30) NOT NULL,
  name         VARCHAR(120) NOT NULL,
  description  VARCHAR(255) NOT NULL,
  price_clp    INT UNSIGNED NOT NULL COMMENT 'el precio oficial vive solo aquí',
  active       TINYINT(1) NOT NULL DEFAULT 1,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_products_sku (sku),
  KEY idx_products_category (category_id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id),
  CONSTRAINT chk_products_price CHECK (price_clp > 0)
) ENGINE=InnoDB;

-- Un producto tiene exactamente un registro de stock.
CREATE TABLE stock (
  product_id          BIGINT UNSIGNED NOT NULL,
  quantity_available  INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'unidades libres (ya descontadas las reservas activas)',
  quantity_reserved   INT UNSIGNED NOT NULL DEFAULT 0,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id),
  CONSTRAINT fk_stock_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;

-- Reserva por pedido y producto; expira si el pago no llega (recuperación de stock).
CREATE TABLE stock_reservations (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id    BIGINT UNSIGNED NOT NULL COMMENT 'referencia lógica a nonna_orders.orders',
  product_id  BIGINT UNSIGNED NOT NULL,
  quantity    INT UNSIGNED NOT NULL,
  status      ENUM('ACTIVA','CONFIRMADA','LIBERADA','EXPIRADA') NOT NULL DEFAULT 'ACTIVA',
  expires_at  DATETIME NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_reservation_order_product (order_id, product_id),
  KEY idx_reservation_expiry (status, expires_at),
  CONSTRAINT fk_reservation_product FOREIGN KEY (product_id) REFERENCES products(id),
  CONSTRAINT chk_reservation_qty CHECK (quantity > 0)
) ENGINE=InnoDB;

-- Vista del catálogo: producto + categoría + precio + disponibilidad en una sola consulta.
CREATE VIEW v_catalog AS
SELECT p.id, p.sku, p.name, p.description, c.name AS category, p.price_clp,
       s.quantity_available,
       (s.quantity_available > 0) AS available
FROM products p
JOIN categories c ON c.id = p.category_id
JOIN stock s ON s.product_id = p.id
WHERE p.active = 1;

-- ---------- 04-orders.sql ----------
-- Autoridad: orders. Pedidos y ciclo de vida. Es el único que decide el estado oficial del pedido.
USE nonna_orders;

CREATE TABLE orders (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_code          VARCHAR(12) NOT NULL COMMENT 'código visible, ej. P-1042',
  client_id           BIGINT UNSIGNED NOT NULL COMMENT 'referencia lógica a nonna_clients.clients',
  status              ENUM('PENDIENTE_PAGO','PAGADO','PREPARANDO','LISTO','ENTREGADO','ANULADO') NOT NULL DEFAULT 'PENDIENTE_PAGO',
  delivery_type       ENUM('DESPACHO','RETIRO') NOT NULL,
  delivery_address    VARCHAR(255) NULL COMMENT 'copia de la dirección al momento de comprar; solo para DESPACHO',
  subtotal_clp        INT UNSIGNED NOT NULL,
  delivery_fee_clp    INT UNSIGNED NOT NULL DEFAULT 0,
  total_clp           INT UNSIGNED NOT NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_orders_code (order_code),
  KEY idx_orders_client (client_id, created_at),
  KEY idx_orders_status (status),
  CONSTRAINT chk_orders_total CHECK (total_clp = subtotal_clp + delivery_fee_clp)
) ENGINE=InnoDB;

-- Un pedido confirmado tiene 1..* ítems. Se guardan nombre y precio al momento de la compra,
-- así el historial no cambia si el producto se modifica o se desactiva.
CREATE TABLE order_items (
  id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id              BIGINT UNSIGNED NOT NULL,
  product_id            BIGINT UNSIGNED NOT NULL COMMENT 'referencia lógica a nonna_inventory.products',
  product_name          VARCHAR(120) NOT NULL,
  unit_price_clp        INT UNSIGNED NOT NULL,
  quantity              INT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  KEY idx_items_order (order_id),
  CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT chk_items_qty CHECK (quantity > 0)
) ENGINE=InnoDB;

-- Bitácora de transiciones: quién cambió qué y cuándo. Nada se borra.
CREATE TABLE order_status_history (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id     BIGINT UNSIGNED NOT NULL,
  from_status  VARCHAR(20) NULL,
  to_status    VARCHAR(20) NOT NULL,
  changed_by   VARCHAR(60) NOT NULL COMMENT 'identidad: usuario trabajador o servicio (ej. svc-payments)',
  changed_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_history_order (order_id),
  CONSTRAINT fk_history_order FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB;

-- Pedidos activos: lo que el panel de trabajadores necesita ver (no incluye entregados ni anulados).
CREATE VIEW v_active_orders AS
SELECT o.id, o.order_code, o.client_id, o.status, o.delivery_type, o.total_clp, o.created_at
FROM orders o
WHERE o.status IN ('PENDIENTE_PAGO','PAGADO','PREPARANDO','LISTO');

-- ---------- 05-payments.sql ----------
-- Autoridad: payments. Intentos de pago, avisos del proveedor y comprobantes.
USE nonna_payments;

CREATE TABLE payments (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL COMMENT 'referencia lógica a nonna_orders.orders',
  client_id         BIGINT UNSIGNED NOT NULL,
  amount_clp        INT UNSIGNED NOT NULL COMMENT 'monto confirmado por orders, nunca por el navegador',
  method            ENUM('WEBPAY','TRANSFERENCIA','EFECTIVO') NOT NULL,
  provider          VARCHAR(30) NOT NULL DEFAULT 'WEBPAY_TEST',
  provider_token    VARCHAR(120) NULL COMMENT 'token de transacción del proveedor (no es la clave del comercio)',
  status            ENUM('INICIADO','AUTORIZADO','RECHAZADO','EXPIRADO') NOT NULL DEFAULT 'INICIADO',
  idempotency_key   VARCHAR(64) NOT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_payments_idempotency (idempotency_key),
  KEY idx_payments_order (order_id),
  CONSTRAINT chk_payments_amount CHECK (amount_clp > 0)
) ENGINE=InnoDB;

-- Cada aviso del proveedor se registra una sola vez: evita procesar dos veces la misma notificación.
CREATE TABLE payment_events (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  payment_id         BIGINT UNSIGNED NOT NULL,
  provider_event_id  VARCHAR(120) NOT NULL,
  signature_valid    TINYINT(1) NOT NULL,
  payload_sha256     CHAR(64) NOT NULL COMMENT 'huella del aviso; no se guardan datos de tarjeta',
  received_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_event_provider (provider_event_id),
  KEY idx_events_payment (payment_id),
  CONSTRAINT fk_events_payment FOREIGN KEY (payment_id) REFERENCES payments(id)
) ENGINE=InnoDB;

-- Boleta: un pago autorizado genera como máximo una.
CREATE TABLE receipts (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  payment_id      BIGINT UNSIGNED NOT NULL,
  receipt_number  VARCHAR(20) NOT NULL,
  issued_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_receipts_payment (payment_id),
  UNIQUE KEY uq_receipts_number (receipt_number),
  CONSTRAINT fk_receipts_payment FOREIGN KEY (payment_id) REFERENCES payments(id)
) ENGINE=InnoDB;

-- ---------- 90-seed.sql ----------
-- Datos de prueba FICTICIOS. Contraseñas de prueba: ver README (no usar en producción).

-- ============ AUTH ============
USE nonna_auth;
INSERT INTO users (id, email, password_hash, role) VALUES
 (1, 'javiera@example.cl',   '$2b$12$fmtpUmIBVOePAT3PVCFJDuzr9sU4KnflEW46v4eKa3f.3nVIT0X4S', 'CLIENTE'),
 (2, 'matias@example.cl',    '$2b$12$fmtpUmIBVOePAT3PVCFJDuzr9sU4KnflEW46v4eKa3f.3nVIT0X4S', 'CLIENTE'),
 (3, 'cocina@lanonna.test',  '$2b$12$rHbdiQpquPbKfqVVVc4CyeDl1vwE3PS7J9vJIzrQat/K4D8cvMGV6', 'TRABAJADOR'),
 (4, 'admin@lanonna.test',   '$2b$12$mB4CRFYp1hvz3rpbAjLc..34mNI41pRvxNFCE8c.fsse.NgnuZ0zq', 'ADMIN');

INSERT INTO staff_profiles (user_id, first_name, last_name, position, hired_at) VALUES
 (3, 'Carla',  'Soto',   'Cocina',         '2024-03-01'),
 (4, 'Andrés', 'Muñoz',  'Administración', '2022-01-10');

-- ============ CLIENTS ============
USE nonna_clients;
INSERT INTO clients (id, auth_user_id, run, first_name, last_name, email, phone) VALUES
 (1, 1, '11111111-1', 'Javiera', 'Rojas',  'javiera@example.cl', '+56911111111'),
 (2, 2, '22222222-2', 'Matías',  'Pérez',  'matias@example.cl',  '+56922222222');
INSERT INTO addresses (client_id, street, commune, reference, is_default) VALUES
 (1, 'Calle Ficticia 123', 'Maipú', 'Casa azul', 1),
 (2, 'Pasaje Ejemplo 456', 'Maipú', NULL, 1);

-- ============ INVENTORY ============
USE nonna_inventory;
INSERT INTO categories (id, name) VALUES (1,'Ravioles'),(2,'Lasañas'),(3,'Tallarines');
INSERT INTO products (id, category_id, sku, name, description, price_clp) VALUES
 (1,1,'RAV-RICO','Ravioles de ricotta y espinaca','Mantequilla salvia y parmesano.',7900),
 (2,1,'RAV-OSOB','Ravioles de osobuco','Jugo reducido y gremolata.',9500),
 (3,1,'RAV-HONG','Ravioles de hongos silvestres','Crema y trufa negra.',8700),
 (4,2,'LAS-BOLO','Lasaña a la bolognesa','Ragú de vacuno y bechamel casera.',8900),
 (5,2,'LAS-VERD','Lasaña de verduras de estación','Zapallo italiano y berenjena.',7800),
 (6,2,'LAS-POLL','Lasaña de pollo al pesto','Pesto de albahaca y piñones.',8300),
 (7,3,'TAL-PEST','Tallarines al pesto genovés','Piñones tostados y parmesano.',6900),
 (8,3,'TAL-CARB','Tallarines a la carbonara','Panceta, yema y pecorino.',7400),
 (9,3,'TAL-POMO','Tallarines al pomodoro','Tomate fresco y albahaca.',6500);
INSERT INTO stock (product_id, quantity_available, quantity_reserved) VALUES
 (1,30,0),(2,20,0),(3,25,0),(4,20,0),(5,25,0),(6,20,0),(7,40,0),(8,35,0),(9,40,0);

-- ============ ORDERS ============
USE nonna_orders;
INSERT INTO orders (id, order_code, client_id, status, delivery_type, delivery_address, subtotal_clp, delivery_fee_clp, total_clp, created_at) VALUES
 (1,'P-1042',1,'ENTREGADO'  ,'DESPACHO','Calle Ficticia 123, Maipú',22700,0,22700,'2026-09-02 13:10:00'),
 (2,'P-1058',1,'ENTREGADO'  ,'RETIRO'  ,NULL,                       19000,0,19000,'2026-09-10 20:05:00'),
 (3,'P-1093',2,'PREPARANDO' ,'DESPACHO','Pasaje Ejemplo 456, Maipú',15200,0,15200,'2026-09-15 19:40:00'),
 (4,'P-1094',2,'LISTO'      ,'RETIRO'  ,NULL,                       16600,0,16600,'2026-09-14 12:30:00');
INSERT INTO order_items (order_id, product_id, product_name, unit_price_clp, quantity) VALUES
 (1,4,'Lasaña a la bolognesa',8900,1),
 (1,7,'Tallarines al pesto genovés',6900,2),
 (2,2,'Ravioles de osobuco',9500,2),
 (3,9,'Tallarines al pomodoro',6500,1),
 (3,3,'Ravioles de hongos silvestres',8700,1),
 (4,6,'Lasaña de pollo al pesto',8300,2);
INSERT INTO order_status_history (order_id, from_status, to_status, changed_by) VALUES
 (1,NULL,'PENDIENTE_PAGO','javiera@example.cl'),(1,'PENDIENTE_PAGO','PAGADO','svc-payments'),(1,'PAGADO','ENTREGADO','cocina@lanonna.test'),
 (2,NULL,'PENDIENTE_PAGO','javiera@example.cl'),(2,'PENDIENTE_PAGO','PAGADO','svc-payments'),(2,'PAGADO','ENTREGADO','cocina@lanonna.test'),
 (3,NULL,'PENDIENTE_PAGO','matias@example.cl'), (3,'PENDIENTE_PAGO','PAGADO','svc-payments'),(3,'PAGADO','PREPARANDO','cocina@lanonna.test'),
 (4,NULL,'PENDIENTE_PAGO','matias@example.cl'), (4,'PENDIENTE_PAGO','PAGADO','svc-payments'),(4,'PAGADO','LISTO','cocina@lanonna.test');

-- ============ PAYMENTS ============
USE nonna_payments;
INSERT INTO payments (id, order_id, client_id, amount_clp, method, provider_token, status, idempotency_key) VALUES
 (1,1,1,22700,'WEBPAY','tok_test_0001','AUTORIZADO','seed-pay-0001'),
 (2,2,1,19000,'WEBPAY','tok_test_0002','AUTORIZADO','seed-pay-0002'),
 (3,3,2,15200,'WEBPAY','tok_test_0003','AUTORIZADO','seed-pay-0003'),
 (4,4,2,16600,'WEBPAY','tok_test_0004','AUTORIZADO','seed-pay-0004');
INSERT INTO payment_events (payment_id, provider_event_id, signature_valid, payload_sha256) VALUES
 (1,'evt_test_0001',1,SHA2('seed-1',256)),(2,'evt_test_0002',1,SHA2('seed-2',256)),
 (3,'evt_test_0003',1,SHA2('seed-3',256)),(4,'evt_test_0004',1,SHA2('seed-4',256));
INSERT INTO receipts (payment_id, receipt_number) VALUES (1,'B-000001'),(2,'B-000002'),(3,'B-000003'),(4,'B-000004');
