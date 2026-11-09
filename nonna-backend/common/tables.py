"""Mapeo (SQLAlchemy Core) de las tablas creadas por db/nonna_workbench_setup.sql.

En MySQL las tablas las crea el script del equipo; este módulo solo las describe para
consultarlas. ``metadata.create_all`` se usa únicamente en las pruebas con SQLite.
Cada servicio tiene su propio MetaData: ningún servicio conoce las tablas de otro.
"""
from sqlalchemy import (
    BigInteger, Boolean, CHAR, Column, Date, DateTime, Enum, ForeignKey, Integer,
    MetaData, SmallInteger, String, Table, UniqueConstraint, func,
)

# SQLite solo hace autoincrement con INTEGER; en MySQL se usa BIGINT del script.
BigId = BigInteger().with_variant(Integer(), "sqlite")
SmallId = SmallInteger().with_variant(Integer(), "sqlite")

# ----------------------------------------------------------------- nonna_auth
auth_metadata = MetaData()
users = Table(
    "users", auth_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("email", String(190), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("role", Enum("CLIENTE", "TRABAJADOR", "ADMIN", native_enum=True), nullable=False, server_default="CLIENTE"),
    Column("active", Boolean, nullable=False, server_default="1"),
    Column("failed_attempts", Integer, nullable=False, server_default="0"),
    Column("locked_until", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)
refresh_tokens = Table(
    "refresh_tokens", auth_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("user_id", BigId, ForeignKey("users.id"), nullable=False),
    Column("token_hash", CHAR(64), nullable=False, unique=True),
    Column("expires_at", DateTime, nullable=False),
    Column("revoked_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)
staff_profiles = Table(
    "staff_profiles", auth_metadata,
    Column("user_id", BigId, ForeignKey("users.id"), primary_key=True),
    Column("first_name", String(80), nullable=False),
    Column("last_name", String(80), nullable=False),
    Column("position", String(60), nullable=False),
    Column("hired_at", Date, nullable=False),
)

# -------------------------------------------------------------- nonna_clients
clients_metadata = MetaData()
clients = Table(
    "clients", clients_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("auth_user_id", BigId, nullable=False, unique=True),
    Column("run", String(12), nullable=True, unique=True),
    Column("first_name", String(80), nullable=False),
    Column("last_name", String(80), nullable=False),
    Column("email", String(190), nullable=False, unique=True),
    Column("phone", String(20), nullable=True),
    Column("notify_email", Boolean, nullable=False, server_default="1"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("deleted_at", DateTime, nullable=True),
)
addresses = Table(
    "addresses", clients_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("client_id", BigId, ForeignKey("clients.id"), nullable=False),
    Column("street", String(160), nullable=False),
    Column("commune", String(80), nullable=False),
    Column("reference", String(160), nullable=True),
    Column("is_default", Boolean, nullable=False, server_default="0"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

# ------------------------------------------------------------ nonna_inventory
inventory_metadata = MetaData()
categories = Table(
    "categories", inventory_metadata,
    Column("id", SmallId, primary_key=True, autoincrement=True),
    Column("name", String(60), nullable=False, unique=True),
)
products = Table(
    "products", inventory_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("category_id", SmallId, ForeignKey("categories.id"), nullable=False),
    Column("sku", String(30), nullable=False, unique=True),
    Column("name", String(120), nullable=False),
    Column("description", String(255), nullable=False),
    Column("price_clp", Integer, nullable=False),
    Column("active", Boolean, nullable=False, server_default="1"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)
stock = Table(
    "stock", inventory_metadata,
    Column("product_id", BigId, ForeignKey("products.id"), primary_key=True),
    Column("quantity_available", Integer, nullable=False, server_default="0"),
    Column("quantity_reserved", Integer, nullable=False, server_default="0"),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)
stock_reservations = Table(
    "stock_reservations", inventory_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("order_id", BigId, nullable=False),
    Column("product_id", BigId, ForeignKey("products.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", Enum("ACTIVA", "CONFIRMADA", "LIBERADA", "EXPIRADA", native_enum=True), nullable=False, server_default="ACTIVA"),
    Column("expires_at", DateTime, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("order_id", "product_id", name="uq_reservation_order_product"),
)

# --------------------------------------------------------------- nonna_orders
ORDER_STATUSES = ("PENDIENTE_PAGO", "PAGADO", "PREPARANDO", "LISTO", "ENTREGADO", "ANULADO")
orders_metadata = MetaData()
orders = Table(
    "orders", orders_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("order_code", String(12), nullable=False, unique=True),
    Column("client_id", BigId, nullable=False),
    Column("status", Enum(*ORDER_STATUSES, native_enum=True), nullable=False, server_default="PENDIENTE_PAGO"),
    Column("delivery_type", Enum("DESPACHO", "RETIRO", native_enum=True), nullable=False),
    Column("delivery_address", String(255), nullable=True),
    Column("subtotal_clp", Integer, nullable=False),
    Column("delivery_fee_clp", Integer, nullable=False, server_default="0"),
    Column("total_clp", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)
order_items = Table(
    "order_items", orders_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("order_id", BigId, ForeignKey("orders.id"), nullable=False),
    Column("product_id", BigId, nullable=False),
    Column("product_name", String(120), nullable=False),
    Column("unit_price_clp", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
)
order_status_history = Table(
    "order_status_history", orders_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("order_id", BigId, ForeignKey("orders.id"), nullable=False),
    Column("from_status", String(20), nullable=True),
    Column("to_status", String(20), nullable=False),
    Column("changed_by", String(60), nullable=False),
    Column("changed_at", DateTime, nullable=False, server_default=func.now()),
)

# ------------------------------------------------------------- nonna_payments
payments_metadata = MetaData()
payments = Table(
    "payments", payments_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("order_id", BigId, nullable=False),
    Column("client_id", BigId, nullable=False),
    Column("amount_clp", Integer, nullable=False),
    Column("method", Enum("WEBPAY", "TRANSFERENCIA", "EFECTIVO", native_enum=True), nullable=False),
    Column("provider", String(30), nullable=False, server_default="WEBPAY_TEST"),
    Column("provider_token", String(120), nullable=True),
    Column("status", Enum("INICIADO", "AUTORIZADO", "RECHAZADO", "EXPIRADO", native_enum=True), nullable=False, server_default="INICIADO"),
    Column("idempotency_key", String(64), nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)
payment_events = Table(
    "payment_events", payments_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("payment_id", BigId, ForeignKey("payments.id"), nullable=False),
    Column("provider_event_id", String(120), nullable=False, unique=True),
    Column("signature_valid", Boolean, nullable=False),
    Column("payload_sha256", CHAR(64), nullable=False),
    Column("received_at", DateTime, nullable=False, server_default=func.now()),
)
receipts = Table(
    "receipts", payments_metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("payment_id", BigId, ForeignKey("payments.id"), nullable=False, unique=True),
    Column("receipt_number", String(20), nullable=False, unique=True),
    Column("issued_at", DateTime, nullable=False, server_default=func.now()),
)

METADATA_BY_SERVICE = {
    "auth": auth_metadata,
    "clients": clients_metadata,
    "inventory": inventory_metadata,
    "orders": orders_metadata,
    "payments": payments_metadata,
}
