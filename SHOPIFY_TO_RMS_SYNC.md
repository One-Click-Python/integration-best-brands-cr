# Sincronización de Pedidos: Shopify → RMS

## Descripción General

Este documento detalla el proceso completo de sincronización de pedidos desde Shopify hacia Microsoft Retail Management System (RMS). La sincronización permite que los pedidos realizados en la tienda online de Shopify se registren automáticamente en el sistema RMS para su gestión, despacho y control de inventario con soporte para pedidos de invitados y procesamiento en tiempo real.

## 🚀 Características Principales

- **Sincronización en Tiempo Real**: Webhooks automáticos para procesamiento inmediato
- **Soporte para Pedidos de Invitados**: Configuración flexible para pedidos sin cliente registrado
- **Mapeo Inteligente de SKUs**: Resolución automática de productos RMS por SKU
- **Validación Completa**: Verificación de estados, pagos y productos antes de insertar
- **Transacciones Seguras**: Rollback automático en caso de errores
- **Manejo de Descuentos**: Preservación de precios originales y con descuento
- **Logging Detallado**: Auditoría completa de todas las operaciones
- **Rate Limiting**: Respeto a límites de API de Shopify

## Arquitectura del Sistema

### Componentes Principales

1. **ShopifyToRMSSync Service** (`app/services/shopify_to_rms.py`)
   - Servicio principal que orquesta la sincronización
   - Maneja la conversión de datos y validaciones exhaustivas
   - Gestiona transacciones y rollbacks automáticos
   - Implementa soporte para pedidos de invitados

2. **ShopifyOrderClient** (`app/db/shopify_order_client.py`)
   - Cliente REST y GraphQL para obtener pedidos de Shopify
   - Maneja paginación automática y rate limiting
   - Obtiene datos completos incluyendo líneas de pedido y customer
   - Soporte para filtros por estado y fecha

3. **RMSHandler** (`app/db/rms_handler.py`)
   - Gestiona conexiones con connection pooling a SQL Server
   - Ejecuta operaciones CRUD en tablas ORDER/ORDERENTRY
   - Maneja transacciones complejas y validaciones
   - Implementa métodos de búsqueda por email y SKU

4. **WebhookHandler** (`app/services/webhook_handler.py`)
   - Procesa webhooks en tiempo real con validación HMAC
   - Enruta eventos a procesadores específicos
   - Manejo de errores con retry automático
   - Logging estructurado de eventos

5. **Order Queries** (`app/db/queries/order_queries.py`)
   - Consultas SQL optimizadas para operaciones de pedidos
   - Manejo de búsquedas por ID, email y SKU
   - Soporte para transacciones y rollbacks
   - Validaciones de integridad de datos

## Flujo de Sincronización Completo

### 1. Captura de Pedidos

Los pedidos se pueden sincronizar de múltiples formas:

**A. Sincronización Automática (Webhooks) - Recomendado**
```bash
# Configuración automática de webhooks
POST /api/v1/webhooks/shopify/orders/create
POST /api/v1/webhooks/shopify/orders/update
```

**B. Sincronización Manual (API REST)**
```bash
# Obtener todos los pedidos
GET /api/v1/sync/orders

# Sincronizar pedidos específicos
POST /api/v1/sync/shopify-to-rms
{
  "order_ids": ["123456789"],
  "force_sync": false
}
```

**C. Sincronización Programada**
```bash
# El motor automático puede incluir pedidos
ENABLE_ORDER_SYNC_IN_MAIN_ENGINE=true
```

### 2. Validación de Pedidos

Antes de sincronizar, cada pedido debe cumplir con criterios estrictos:

#### Estados Financieros Válidos
- `PAID`: Pedido completamente pagado ✅
- `PARTIALLY_PAID`: Pedido parcialmente pagado ✅
- `AUTHORIZED`: Pago autorizado pendiente de captura ✅
- `PENDING`: Pago pendiente ❌
- `VOIDED`: Pago anulado ❌
- `REFUNDED`: Pedido reembolsado ❌

#### Validaciones Requeridas
- **Líneas de Pedido**: Al menos un producto con SKU válido
- **Monto Total**: Mayor a cero después de descuentos
- **Datos Requeridos**: ID, nombre, fecha de creación válidos
- **SKUs Existentes**: Todos los SKUs deben existir en RMS

### 3. Proceso de Conversión Detallado

#### Paso 1: Gestión del Cliente

```python
# Algoritmo de gestión de clientes
1. Si el pedido tiene customer:
   a. Buscar cliente existente por email en RMS
   b. Si existe: usar CustomerID existente
   c. Si no existe: crear nuevo cliente con datos completos
   
2. Si el pedido NO tiene customer (guest checkout):
   a. Si ALLOW_ORDERS_WITHOUT_CUSTOMER=true:
      - Usar DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS si está configurado
      - O usar CustomerID=NULL
   b. Si ALLOW_ORDERS_WITHOUT_CUSTOMER=false:
      - Rechazar el pedido con error
      
3. Si REQUIRE_CUSTOMER_EMAIL=true y no hay email:
   - Rechazar el pedido
```

#### Paso 2: Resolución de SKUs

```python
# Para cada línea del pedido:
1. Extraer SKU de la variante de Shopify
2. Buscar en RMS: SELECT ItemID FROM View_Items WHERE C_ARTICULO = :sku
3. Validar que el producto esté activo y disponible
4. Si SKU no existe: registrar error y continuar con siguiente línea
5. Calcular precios (original vs con descuento)
```

#### Paso 3: Creación de Transacciones

```python
# Transacción completa RMS
BEGIN TRANSACTION
try:
    1. INSERT INTO [ORDER] (cabecera del pedido)
    2. Para cada línea válida:
       INSERT INTO ORDERENTRY (detalle del pedido)
    3. Opcional: UPDATE item quantities
    4. COMMIT TRANSACTION
except:
    ROLLBACK TRANSACTION
    raise error
```

## Mapeo de Campos: Shopify → RMS

### Tabla ORDER (Cabecera del Pedido)

| Campo RMS | Origen Shopify | Transformación | Descripción |
|-----------|----------------|----------------|-------------|
| StoreID | 40 (configurable) | STORE_ID env var | ID de tienda virtual |
| Time | createdAt | ISO 8601 → DateTime | Fecha/hora del pedido |
| Type | 1 (fijo) | Constante | Tipo: 1=Venta, 2=Devolución |
| CustomerID | customer.id → lookup | Búsqueda/creación | ID del cliente RMS o NULL |
| Deposit | 0 (fijo) | Constante | Depósito inicial |
| Tax | totalTaxSet.shopMoney.amount | Decimal | Impuestos totales |
| Total | totalPriceSet.shopMoney.amount | Decimal | Total del pedido |
| SalesRepID | NULL | Sin mapeo | ID del vendedor |
| ShippingServiceID | NULL | Sin mapeo | Servicio de envío |
| ShippingTrackingNumber | fulfillments[0].trackingNumber | String | Número de seguimiento |
| Comment | Template configurable | "Shopify Order #{name}" | Comentario descriptivo |
| ShippingNotes | shippingAddress | Formato completo | Dirección de envío |
| PaymentMethod | gateway | String | Método de pago usado |
| OrderStatus | fulfillmentStatus | Mapeo de estados | Estado del pedido |

### Tabla ORDERENTRY (Líneas del Pedido)

| Campo RMS | Origen Shopify | Transformación | Descripción |
|-----------|----------------|----------------|-------------|
| OrderID | (auto-generado) | Secuencial | ID del pedido padre |
| ItemID | SKU → lookup | Resolución por C_ARTICULO | ID del producto en RMS |
| Price | discountedUnitPriceSet.amount | Decimal | Precio unitario con descuento |
| FullPrice | originalUnitPriceSet.amount | Decimal | Precio original sin descuento |
| Cost | NULL | Sin datos | Costo del producto |
| QuantityOnOrder | quantity | Integer | Cantidad ordenada |
| QuantityRTD | 0 | Inicial | Cantidad lista para despacho |
| SalesRepID | NULL | Sin mapeo | ID del vendedor |
| DiscountReasonCodeID | discountCodes[0].code | Lookup opcional | Código de descuento |
| ReturnReasonCodeID | NULL | N/A | Código de devolución |
| Description | title | Truncar a 255 chars | Descripción del producto |
| IsAddMoney | 0 | Fijo | No es cargo adicional |
| VoucherID | NULL | Sin mapeo | ID del cupón |
| TaxAmount | taxLines[].priceSet.amount | Decimal | Impuesto por línea |
| DiscountAmount | totalDiscountSet.amount / quantity | Decimal | Descuento por unidad |

### Tabla CUSTOMER (Datos del Cliente)

| Campo RMS | Origen Shopify | Transformación | Descripción |
|-----------|----------------|----------------|-------------|
| Email | customer.email | Validación email | Email del cliente |
| FirstName | customer.firstName | String (50 chars) | Nombre |
| LastName | customer.lastName | String (50 chars) | Apellido |
| Phone | customer.phone | Limpiar formato | Teléfono |
| Company | billingAddress.company | String opcional | Empresa |
| Address1 | billingAddress.address1 | String (100 chars) | Dirección línea 1 |
| Address2 | billingAddress.address2 | String opcional | Dirección línea 2 |
| City | billingAddress.city | String (50 chars) | Ciudad |
| Province | billingAddress.province | String (50 chars) | Estado/Provincia |
| Country | billingAddress.country | String (50 chars) | País |
| Zip | billingAddress.zip | String (20 chars) | Código postal |
| DateCreated | NOW() | Timestamp | Fecha de creación |
| LastModified | NOW() | Timestamp | Última modificación |

## Configuración Avanzada

### 1. Variables de Entorno Completas

```bash
# Base de datos RMS (SQL Server)
RMS_DB_HOST=servidor.sql.com
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database  
RMS_DB_USER=usuario
RMS_DB_PASSWORD=contraseña
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server
RMS_CONNECTION_TIMEOUT=30
RMS_CONNECTION_POOL_SIZE=10

# API de Shopify
SHOPIFY_SHOP_URL=mi-tienda.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2025-04
SHOPIFY_RATE_LIMIT_PER_SECOND=2

# Configuración de Pedidos
STORE_ID=40                                    # ID de tienda en RMS
DEFAULT_SALES_REP_ID=NULL                      # Vendedor por defecto
ORDER_SYNC_BATCH_SIZE=50                       # Lote máximo de pedidos
ORDER_SYNC_TIMEOUT_SECONDS=300                 # Timeout por lote

# Soporte para Pedidos de Invitados
ALLOW_ORDERS_WITHOUT_CUSTOMER=true            # Permitir pedidos sin cliente
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=         # Cliente por defecto (opcional)
REQUIRE_CUSTOMER_EMAIL=false                  # Requerir email obligatorio
GUEST_ORDER_PREFIX="GUEST-"                   # Prefijo para pedidos de invitados

# Webhooks de Shopify
SHOPIFY_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx    # Secret para validación HMAC
WEBHOOK_RETRY_ATTEMPTS=3                      # Reintentos automáticos
WEBHOOK_TIMEOUT_SECONDS=30                    # Timeout por webhook

# Estados Válidos de Pedidos
VALID_FINANCIAL_STATUSES=PAID,PARTIALLY_PAID,AUTHORIZED
VALID_FULFILLMENT_STATUSES=FULFILLED,PARTIAL,UNFULFILLED
```

### 2. Configuración de Webhooks en Shopify

#### Webhook Automático (Recomendado)
```bash
# Usar el script incluido para configuración automática
poetry run python configure_webhooks.py

# O usar la API REST de la aplicación
curl -X POST http://localhost:8080/api/v1/webhooks/configure \
  -H "Content-Type: application/json" \
  -d '{
    "events": ["orders/create", "orders/updated", "orders/paid"],
    "endpoint": "https://mi-servidor.com/api/v1/webhooks/shopify"
  }'
```

#### Configuración Manual
```bash
# Webhook para pedidos creados
curl -X POST https://mi-tienda.myshopify.com/admin/api/2025-04/webhooks.json \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/create",
      "address": "https://mi-servidor.com/api/v1/webhooks/shopify/orders/create",
      "format": "json",
      "fields": ["id", "name", "email", "financial_status", "line_items", "customer", "billing_address", "shipping_address", "total_price", "subtotal_price", "total_tax", "currency", "created_at", "updated_at"]
    }
  }'

# Webhook para pedidos pagados
curl -X POST https://mi-tienda.myshopify.com/admin/api/2025-04/webhooks.json \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/paid",
      "address": "https://mi-servidor.com/api/v1/webhooks/shopify/orders/paid",
      "format": "json"
    }
  }'
```

### 3. Permisos Requeridos en Shopify

El token de acceso debe tener estos permisos (scopes):

- `read_orders` - Leer pedidos
- `read_customers` - Leer datos de clientes
- `read_products` - Leer productos para validar SKUs
- `read_fulfillments` - Leer información de envíos
- `read_price_rules` - Leer reglas de descuentos (opcional)

## Sincronización Manual y Programada

### 1. Sincronización Completa

```bash
# Sincronizar todos los pedidos nuevos
curl -X POST http://localhost:8080/api/v1/sync/shopify-to-rms \
  -H "Content-Type: application/json" \
  -d '{
    "force_sync": false,
    "batch_size": 50,
    "financial_status": ["paid", "authorized"],
    "created_at_min": "2025-01-01T00:00:00Z",
    "validate_skus": true
  }'
```

### 2. Sincronización por Pedidos Específicos

```bash
# Sincronizar pedidos específicos por ID de Shopify
curl -X POST http://localhost:8080/api/v1/sync/shopify-to-rms \
  -H "Content-Type: application/json" \
  -d '{
    "order_ids": ["5678901234", "5678901235"],
    "force_sync": true,
    "skip_validation": false
  }'
```

### 3. Sincronización por Rango de Fechas

```bash
# Sincronizar pedidos en rango específico
curl -X POST http://localhost:8080/api/v1/sync/shopify-to-rms \
  -H "Content-Type: application/json" \
  -d '{
    "created_at_min": "2025-01-15T00:00:00Z",
    "created_at_max": "2025-01-20T23:59:59Z",
    "financial_status": ["paid"],
    "fulfillment_status": ["fulfilled", "unfulfilled"]
  }'
```

### 4. Sincronización con Filtros Avanzados

```bash
# Sincronizar con múltiples filtros
curl -X POST http://localhost:8080/api/v1/sync/shopify-to-rms \
  -H "Content-Type: application/json" \
  -d '{
    "financial_status": ["paid", "partially_paid"],
    "min_total": 10.00,
    "exclude_test_orders": true,
    "only_new_customers": false,
    "dry_run": false
  }'
```

## APIs de Monitoreo y Control

### 1. Estado de Sincronización

```bash
# Ver estado general de sincronización de pedidos
GET /api/v1/sync/orders/status

# Respuesta ejemplo:
{
  "status": "active",
  "last_sync": "2025-01-30T10:30:00Z",
  "orders_synced_today": 45,
  "errors_today": 2,
  "success_rate": 95.6,
  "pending_webhooks": 3,
  "avg_processing_time": "1.2s"
}
```

### 2. Historial de Sincronización

```bash
# Ver historial de pedidos sincronizados
GET /api/v1/sync/orders/history?limit=50&offset=0

# Ver detalles de sincronización específica
GET /api/v1/sync/orders/history/{sync_id}
```

### 3. Métricas Detalladas

```bash
# Métricas de rendimiento
GET /api/v1/metrics/orders

# Respuesta ejemplo:
{
  "total_orders_synced": 1250,
  "orders_today": 45,
  "orders_this_week": 320,
  "average_order_value": 85.50,
  "top_errors": [
    {"error": "SKU not found", "count": 5},
    {"error": "Invalid customer email", "count": 2}
  ],
  "processing_times": {
    "avg": "1.2s",
    "min": "0.5s",
    "max": "5.8s"
  }
}
```

### 4. Gestión de Errores

```bash
# Ver pedidos con errores
GET /api/v1/sync/orders/errors?limit=20

# Reintentar pedidos fallidos
POST /api/v1/sync/orders/retry-failed
{
  "max_retries": 3,
  "retry_only_recent": true,
  "hours_back": 24
}

# Marcar error como resuelto
PUT /api/v1/sync/orders/errors/{error_id}/resolve
```

## Manejo Avanzado de Errores

### Tipos de Errores y Soluciones

#### 1. Errores de Datos

| Error | Descripción | Solución | Acción Automática |
|-------|-------------|----------|-------------------|
| `SKU_NOT_FOUND` | SKU no existe en RMS | Crear producto o corregir SKU | Saltar línea, continuar |
| `INVALID_CUSTOMER_EMAIL` | Email malformado | Validar formato email | Usar guest customer |
| `DUPLICATE_ORDER` | Pedido ya existe | Verificar ID único | Saltar pedido |
| `INVALID_PRICE` | Precio negativo o cero | Validar datos Shopify | Rechazar línea |
| `MISSING_REQUIRED_FIELD` | Campo obligatorio vacío | Completar datos | Usar valores por defecto |

#### 2. Errores de Conexión

```python
# Manejo de errores con retry automático
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
def sync_order_to_rms(order_data):
    # Lógica de sincronización
    pass
```

#### 3. Errores de Validación

```bash
# Validar pedido antes de sincronizar
POST /api/v1/sync/orders/validate
{
  "order_id": "5678901234",
  "strict_validation": true,
  "check_inventory": true
}

# Respuesta:
{
  "valid": false,
  "errors": [
    {
      "field": "line_items[0].sku",
      "error": "SKU 'ABC123' not found in RMS",
      "severity": "error"
    }
  ],
  "warnings": [
    {
      "field": "customer.email",
      "warning": "Email domain unusual",
      "severity": "warning"
    }
  ]
}
```

### Logs Estructurados

```json
{
  "timestamp": "2025-01-30T10:45:00Z",
  "level": "INFO",
  "service": "ShopifyToRMSSync",
  "order_id": "5678901234",
  "order_name": "#1001",
  "message": "Order sync completed successfully",
  "context": {
    "customer_id": 12345,
    "total_amount": 85.50,
    "line_items_count": 3,
    "processing_time_ms": 1200,
    "rms_order_id": 98765
  }
}
```

### Alertas Automáticas

El sistema genera alertas para:
- Tasa de error > 10% en 1 hora
- Pedidos bloqueados > 30 minutos
- SKUs faltantes recurrentes
- Problemas de conexión RMS
- Webhooks fallidos > 5 consecutivos

## Casos Especiales

### 1. Pedidos de Invitados (Guest Checkout)

```python
# Configuración para pedidos sin cliente
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=999  # Cliente "Invitado" en RMS
REQUIRE_CUSTOMER_EMAIL=false

# Comportamiento:
if order.customer is None:
    if ALLOW_ORDERS_WITHOUT_CUSTOMER:
        customer_id = DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS or None
        # Crear pedido con customer_id especial o NULL
    else:
        raise Exception("Guest orders not allowed")
```

### 2. Pedidos con Descuentos Complejos

```python
# Manejo de múltiples descuentos
for line_item in order.line_items:
    original_price = line_item.original_unit_price
    discounted_price = line_item.discounted_unit_price
    total_discount = original_price - discounted_price
    
    # Insertar en ORDERENTRY con ambos precios
    insert_order_entry(
        price=discounted_price,
        full_price=original_price,
        discount_amount=total_discount
    )
```

### 3. Pedidos Parcialmente Pagados

```python
# Estado: PARTIALLY_PAID
if order.financial_status == "PARTIALLY_PAID":
    # Crear pedido normal pero marcar estado especial
    order_comment = f"Shopify Order #{order.name} - PARTIALLY PAID"
    # Puede requerir seguimiento manual en RMS
```

### 4. Pedidos con Múltiples Métodos de Pago

```python
# Combinar información de transacciones
payment_methods = []
for transaction in order.transactions:
    if transaction.status == "success":
        payment_methods.append(f"{transaction.gateway}: {transaction.amount}")

payment_method_text = " + ".join(payment_methods)
```

## Testing y Validación

### 1. Tests Automatizados

```bash
# Ejecutar tests de sincronización de pedidos
poetry run pytest tests/test_shopify_to_rms.py -v

# Test específico de webhooks
poetry run pytest tests/test_webhook_handler.py -v

# Test de integración completa
poetry run pytest tests/test_full_order_sync.py -v
```

### 2. Scripts de Validación

```bash
# Validar configuración de webhooks
poetry run python scripts/validate_webhooks.py

# Test de conectividad completa
poetry run python scripts/test_order_sync_setup.py

# Validar mapeo de SKUs
poetry run python scripts/validate_sku_mapping.py
```

### 3. Herramientas de Debug

```bash
# Debug de pedido específico
curl -X POST http://localhost:8080/api/v1/sync/orders/debug \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "5678901234",
    "verbose": true,
    "dry_run": true
  }'

# Simular webhook
curl -X POST http://localhost:8080/api/v1/webhooks/shopify/test \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Topic: orders/create" \
  -d @test_order_payload.json
```

## Optimizaciones y Rendimiento

### 1. Procesamiento por Lotes

```python
# Configuración óptima
ORDER_SYNC_BATCH_SIZE=50          # Tamaño de lote
MAX_CONCURRENT_ORDERS=5           # Pedidos paralelos
ORDER_PROCESSING_TIMEOUT=300      # 5 minutos por lote
CONNECTION_POOL_SIZE=10           # Pool de conexiones
```

### 2. Cache de Datos

```python
# Cache de datos frecuentes
- Customer lookups (TTL: 1 hora)
- SKU to ItemID mapping (TTL: 30 minutos)  
- Store configuration (TTL: 24 horas)
- Discount codes (TTL: 6 horas)
```

### 3. Consultas Optimizadas

```sql
-- Índices recomendados para RMS
CREATE INDEX IX_Customer_Email ON Customer(Email);
CREATE INDEX IX_ViewItems_SKU ON View_Items(C_ARTICULO);
CREATE INDEX IX_Order_ShopifyID ON [Order](Comment);  -- Si almacenamos ID Shopify
CREATE INDEX IX_OrderEntry_OrderID ON OrderEntry(OrderID);
```

### 4. Monitoreo de Performance

```bash
# Métricas de rendimiento en tiempo real
GET /api/v1/metrics/orders/performance

# Respuesta:
{
  "avg_processing_time": "1.2s",
  "throughput_per_minute": 25,
  "database_connection_time": "0.1s",
  "shopify_api_response_time": "0.8s",
  "memory_usage_mb": 145,
  "active_connections": 8
}
```

## Limitaciones y Consideraciones

### Limitaciones Actuales

1. **Actualizaciones de Pedidos**: Solo inserción de nuevos pedidos, no updates de existentes
2. **Gestión de Devoluciones**: No implementada automáticamente
3. **Inventario**: No actualiza stock automáticamente tras pedido
4. **Estados de Envío**: No sync bidireccional de fulfillment status
5. **Pagos Parciales**: Manejo básico, puede requerir intervención manual

### Consideraciones de Rendimiento

- **Rate Limiting Shopify**: 2 llamadas/segundo máximo
- **Batch Size**: Recomendado 20-50 pedidos por lote
- **Timeout**: 5 minutos máximo por lote de sincronización
- **Memoria**: ~5MB por lote de 50 pedidos
- **Conexiones DB**: Pool de 5-20 conexiones según carga

### Consideraciones de Datos

- **Encoding**: UTF-8 completo para caracteres especiales
- **Longitud de Campos**: Respeto a límites RMS (255 chars descripción)
- **Decimales**: Máximo 2 decimales para precios
- **Fechas**: Conversión correcta UTC → local timezone
- **Validación**: Estricta antes de insertar en RMS

## Seguridad y Mejores Prácticas

### 1. Validación de Webhooks

```python
def validate_webhook_signature(request_body, signature, secret):
    """Validar firma HMAC de webhook Shopify"""
    computed_hmac = base64.b64encode(
        hmac.new(
            secret.encode('utf-8'),
            request_body,
            digestmod=hashlib.sha256
        ).digest()
    ).decode()
    
    return hmac.compare_digest(computed_hmac, signature)
```

### 2. Sanitización de Datos

```python
def sanitize_order_data(order_data):
    """Limpiar datos de pedido antes de insertar"""
    # Truncar campos largos
    if 'description' in order_data:
        order_data['description'] = order_data['description'][:255]
    
    # Validar emails
    if 'email' in order_data:
        if not is_valid_email(order_data['email']):
            order_data['email'] = None
    
    # Escapar caracteres especiales SQL
    return escape_sql_data(order_data)
```

### 3. Logging de Seguridad

```python
# No loggear información sensible
SENSITIVE_FIELDS = ['credit_card', 'ssn', 'password', 'token']

def safe_log(data):
    safe_data = {k: v for k, v in data.items() if k not in SENSITIVE_FIELDS}
    logger.info(safe_data)
```

## Roadmap y Próximas Mejoras

### Corto Plazo (1-3 meses)

1. **Sincronización de Devoluciones**: Manejo automático de refunds
2. **Actualización de Estados**: Sync bidireccional de fulfillment status
3. **Inventario Automático**: Reducción de stock tras pedido confirmado
4. **Dashboard Web**: Interface visual para monitoreo
5. **Alertas Email**: Notificaciones automáticas de errores

### Mediano Plazo (3-6 meses)

1. **Sincronización Incremental**: Solo cambios desde última sync
2. **Multi-tienda**: Soporte para múltiples tiendas Shopify
3. **API para Terceros**: Webhooks salientes para sistemas externos
4. **Reportes Avanzados**: Analytics de pedidos y ventas
5. **Machine Learning**: Detección automática de anomalías

### Largo Plazo (6+ meses)

1. **Sincronización en Tiempo Real**: WebSockets para updates instantáneos
2. **Blockchain Audit**: Registro inmutable de todas las transacciones
3. **IA Predictiva**: Predicción de problemas de sincronización
4. **Multi-región**: Soporte para deployment global
5. **API GraphQL**: Interface moderna para integraciones

## Recursos y Referencias

### Documentación Oficial
- [Shopify Orders API](https://shopify.dev/docs/api/admin-rest/2025-04/resources/order)
- [Shopify Webhooks](https://shopify.dev/docs/apps/webhooks)
- [RMS Database Schema](https://docs.microsoft.com/en-us/dynamics365/commerce/dev-itpro/retail-server-architecture)

### Herramientas de Testing
- [Shopify Webhook Tester](https://webhook.site/)
- [ngrok](https://ngrok.com/) para testing local
- [Postman Collection](./postman/shopify-rms-sync.json) incluida

### Scripts Útiles
- `scripts/test_webhook_locally.py` - Test local de webhooks
- `scripts/validate_order_data.py` - Validación de estructura de pedidos
- `scripts/cleanup_test_orders.py` - Limpieza de pedidos de prueba

### Soporte
- **Email**: enzo@oneclick.cr
- **Documentación**: http://localhost:8080/docs (cuando está corriendo)
- **Logs Detallados**: `logs/app.log` para debugging
- **Issues**: GitHub Issues para reportar problemas

---

*Documento actualizado: Enero 2025*
*Versión del sistema: 2.5*
*Compatible con: Shopify API 2025-04, RMS SQL Server 2019+*
*Última sincronización exitosa de documentación: 30/01/2025*