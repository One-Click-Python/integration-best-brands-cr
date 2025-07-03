# Sincronización de Pedidos: Shopify → RMS

## Descripción General

Este documento detalla el proceso de sincronización de pedidos desde Shopify hacia Microsoft Retail Management System (RMS). La sincronización permite que los pedidos realizados en la tienda online de Shopify se registren automáticamente en el sistema RMS para su gestión y despacho.

## Arquitectura del Sistema

### Componentes Principales

1. **ShopifyToRMSSync Service** (`app/services/shopify_to_rms.py`)
   - Servicio principal que orquesta la sincronización
   - Maneja la conversión de datos y validaciones
   - Gestiona errores y reintentos

2. **ShopifyOrderClient** (`app/db/shopify_order_client.py`)
   - Cliente GraphQL para obtener pedidos de Shopify
   - Maneja paginación y rate limiting
   - Obtiene datos completos del pedido

3. **RMSHandler** (`app/db/rms_handler.py`)
   - Gestiona conexiones a SQL Server
   - Ejecuta inserciones en tablas RMS
   - Maneja transacciones y rollbacks

4. **Webhook Handler** (`app/services/webhook_handler.py`)
   - Procesa webhooks en tiempo real
   - Valida firmas de seguridad
   - Enruta eventos a procesadores

## Flujo de Sincronización

### 1. Obtención de Pedidos

Los pedidos se pueden sincronizar de dos formas:

**A. Sincronización Manual (API REST)**
```
GET /api/v1/sync/orders  # Obtiene todos los pedidos
POST /api/v1/sync/orders # Sincroniza pedidos específicos
```

**B. Sincronización Automática (Webhooks)**
```
POST /api/v1/webhooks/order/created
POST /api/v1/webhooks/order/updated
```

### 2. Validación de Pedidos

Antes de sincronizar, cada pedido debe cumplir:

- **Estado Financiero**: PAID, PARTIALLY_PAID o AUTHORIZED
- **Líneas de Pedido**: Al menos un producto con SKU válido
- **Monto Total**: Mayor a cero
- **Datos Requeridos**: ID, nombre, fecha de creación

### 3. Proceso de Conversión

#### Datos del Cliente
```python
# Búsqueda/Creación de Cliente
1. Buscar cliente existente por email
2. Si no existe, crear nuevo cliente con:
   - Email
   - Nombre y Apellido
   - Teléfono
   - Dirección de facturación/envío
```

#### Mapeo de SKU a ItemID
```python
# Para cada línea del pedido:
1. Obtener SKU del producto en Shopify
2. Buscar ItemID en RMS: SELECT ItemID FROM View_Items WHERE C_ARTICULO = :sku
3. Si no encuentra el SKU, registrar error y continuar
```

## Mapeo de Campos: Shopify → RMS

### Tabla ORDER (Cabecera del Pedido)

| Campo RMS | Origen Shopify | Descripción |
|-----------|----------------|-------------|
| StoreID | 40 (fijo) | ID de tienda virtual |
| Time | createdAt | Fecha/hora del pedido |
| Type | 1 (fijo) | Tipo: 1=Venta, 2=Devolución |
| CustomerID | customer.id | ID del cliente (o NULL) |
| Deposit | 0 | Depósito inicial |
| Tax | totalTaxSet.shopMoney.amount | Impuestos totales |
| Total | totalPriceSet.shopMoney.amount | Total del pedido |
| SalesRepID | NULL | ID del vendedor |
| ShippingServiceID | NULL | Servicio de envío |
| ShippingTrackingNumber | fulfillments[0].trackingNumber | Número de seguimiento |
| Comment | "Shopify Order #{name} - {status}" | Comentario con info de Shopify |
| ShippingNotes | shippingAddress (formateada) | Notas de envío |

### Tabla ORDERENTRY (Líneas del Pedido)

| Campo RMS | Origen Shopify | Descripción |
|-----------|----------------|-------------|
| OrderID | (generado) | ID del pedido padre |
| ItemID | Resuelto por SKU | ID del producto en RMS |
| Price | discountedUnitPriceSet.amount | Precio unitario con descuento |
| FullPrice | originalUnitPriceSet.amount | Precio original sin descuento |
| Cost | NULL | Costo del producto |
| QuantityOnOrder | quantity | Cantidad ordenada |
| QuantityRTD | 0 | Cantidad lista para despacho |
| SalesRepID | NULL | ID del vendedor |
| DiscountReasonCodeID | NULL | Código de descuento |
| ReturnReasonCodeID | NULL | Código de devolución |
| Description | title (max 255) | Descripción del producto |
| IsAddMoney | 0 | Cargo adicional |
| VoucherID | NULL | ID del cupón |

### Datos del Cliente

| Campo RMS | Origen Shopify | Descripción |
|-----------|----------------|-------------|
| Email | customer.email | Email del cliente |
| FirstName | customer.firstName | Nombre |
| LastName | customer.lastName | Apellido |
| Phone | customer.phone | Teléfono |
| Address1 | billingAddress.address1 | Dirección línea 1 |
| Address2 | billingAddress.address2 | Dirección línea 2 |
| City | billingAddress.city | Ciudad |
| Province | billingAddress.province | Estado/Provincia |
| Country | billingAddress.country | País |
| Zip | billingAddress.zip | Código postal |

## Configuración y Puesta en Marcha

### 1. Variables de Entorno Requeridas

```bash
# Base de datos RMS (SQL Server)
RMS_DB_SERVER=servidor.sql.com
RMS_DB_DATABASE=RMS_Database
RMS_DB_USERNAME=usuario
RMS_DB_PASSWORD=contraseña
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server

# API de Shopify
SHOPIFY_SHOP_URL=https://mi-tienda.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2025-04

# Webhooks (opcional)
SHOPIFY_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

### 2. Configuración de Webhooks en Shopify

Para sincronización en tiempo real, configurar webhooks:

```bash
# Crear webhook de pedidos creados
curl -X POST https://mi-tienda.myshopify.com/admin/api/2025-04/webhooks.json \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/create",
      "address": "https://mi-servidor.com/api/v1/webhooks/order/created",
      "format": "json"
    }
  }'

# Crear webhook de pedidos actualizados
curl -X POST https://mi-tienda.myshopify.com/admin/api/2025-04/webhooks.json \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/updated",
      "address": "https://mi-servidor.com/api/v1/webhooks/order/updated",
      "format": "json"
    }
  }'
```

### 3. Ejecutar Sincronización Manual

```bash
# Sincronizar todos los pedidos
curl -X POST http://localhost:8000/api/v1/sync/orders \
  -H "Content-Type: application/json" \
  -d '{
    "order_ids": [],
    "force_sync": false,
    "validate_before_insert": true,
    "run_async": true
  }'

# Sincronizar pedidos específicos
curl -X POST http://localhost:8000/api/v1/sync/orders \
  -H "Content-Type: application/json" \
  -d '{
    "order_ids": ["gid://shopify/Order/123456789"],
    "force_sync": true
  }'
```

### 4. Script de Prueba

Existe un script de prueba completo:

```bash
poetry run python test_all_orders_sync.py
```

Este script:
- Obtiene todos los pedidos de Shopify
- Los sincroniza con RMS
- Genera reportes detallados
- Guarda resultados en JSON

## Manejo de Errores

### Errores Comunes y Soluciones

1. **SKU No Encontrado**
   - Error: "Item not found for SKU: XXX"
   - Solución: Verificar que el SKU existe en RMS tabla View_Items

2. **Cliente Sin Email**
   - Error: "Order has no customer email"
   - Comportamiento: Se crea pedido con CustomerID = NULL

3. **Estado Financiero Inválido**
   - Error: "Invalid financial status: PENDING"
   - Solución: Solo se sincronizan pedidos pagados o autorizados

4. **Conexión a Base de Datos**
   - Error: "Cannot connect to RMS database"
   - Solución: Verificar credenciales y conectividad SQL Server

### Logs y Monitoreo

Los logs incluyen:
- Inicio/fin de sincronización
- Pedidos procesados exitosamente
- Errores detallados por pedido
- Métricas de rendimiento

Ejemplo de log exitoso:
```
INFO: Starting order sync for order #1001
INFO: Customer found/created with ID: 12345
INFO: Mapped SKU ABC123 to ItemID 67890
INFO: Order created successfully with ID: 98765
INFO: Updated inventory for item 67890
INFO: Order #1001 synced successfully
```

## Limitaciones y Consideraciones

### Limitaciones Actuales

1. **Métodos No Implementados**: Varios métodos en `rms_handler.py` están pendientes de implementación
2. **Gestión de Inventario**: La actualización de stock no está completamente implementada
3. **Historial de Pedidos**: La tabla ORDERHISTORY no se está poblando
4. **Actualizaciones**: No se pueden actualizar pedidos existentes

### Consideraciones de Rendimiento

- **Rate Limiting**: Shopify limita a 2 llamadas/segundo
- **Batch Size**: Se recomienda procesar máximo 50 pedidos por lote
- **Timeout**: Las operaciones tienen timeout de 30 segundos
- **Concurrencia**: Máximo 5 pedidos procesándose simultáneamente

### Seguridad

- **Validación de Webhooks**: Siempre validar firma HMAC
- **Credenciales**: Nunca exponer tokens en logs
- **SQL Injection**: Usar siempre parámetros preparados
- **HTTPS**: Requerido para endpoints de webhook

## Próximos Pasos

### Implementaciones Pendientes

1. Completar métodos faltantes en `rms_handler.py`:
   - `find_order_by_shopify_id`
   - `find_customer_by_email`
   - `create_customer`
   - `find_item_by_sku`
   - `update_order`
   - `update_item_stock`

2. Agregar funcionalidades:
   - Sincronización de devoluciones
   - Actualización de estados de envío
   - Sincronización de pagos parciales
   - Notificaciones por email

3. Mejorar monitoreo:
   - Dashboard de métricas
   - Alertas de errores
   - Reportes de sincronización

## Solución de Problemas

### Verificar Conexión a RMS

```python
# Test de conexión
poetry run python -c "
from app.db.rms_handler import RMSHandler
handler = RMSHandler()
print(handler.test_connection())
"
```

### Verificar Mapeo de SKU

```sql
-- En SQL Server Management Studio
SELECT TOP 10 
    C_ARTICULO as SKU,
    ItemID,
    Description,
    Quantity
FROM View_Items
WHERE C_ARTICULO IS NOT NULL
```

### Debug de Pedidos

```python
# Ver estructura del pedido de Shopify
curl -X GET http://localhost:8000/api/v1/sync/orders?limit=1 \
  | python -m json.tool
```

## Contacto y Soporte

Para problemas o preguntas sobre la sincronización:
1. Revisar logs de la aplicación
2. Verificar configuración de variables de entorno
3. Consultar documentación de API de Shopify
4. Revisar esquema de base de datos RMS