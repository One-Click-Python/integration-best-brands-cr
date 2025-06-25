# Guía de Sincronización RMS-Shopify

## 📅 **Cuándo se Ejecuta la Sincronización**

### 1. **Manualmente via API** (Método Principal Actual)
```bash
POST /api/v1/sync/rms-to-shopify
```

### 2. **Programada Automáticamente** (Framework Existe, Pendiente Implementación)
- **Configuración**: `ENABLE_SCHEDULED_SYNC=True` 
- **Intervalo**: `SYNC_INTERVAL_MINUTES=15` (cada 15 minutos)
- **Estado**: El framework existe pero la lógica está marcada como "TODO"

### 3. **Sincronización Completa Bidireccional**
```bash
POST /api/v1/sync/full-sync
```

## 🔄 **Flujo Completo de Sincronización**

### **Fase 1: Inicialización** (`app/services/rms_to_shopify.py:96-165`)
```python
# 1. Validar configuración y conexiones
# 2. Configurar parámetros (batch_size, force_update, etc.)
# 3. Iniciar logging y métricas
```

### **Fase 2: Extracción de RMS** (`rms_to_shopify.py:178-212`)
```sql
-- Consulta principal a RMS
SELECT 
    c_articulo, descripcion as title, categoria, familia, 
    genero, color, talla, precio, cantidad, impuesto,
    extended_category, ccod
FROM View_Items 
WHERE activo = 1 AND [filtros opcionales]
```

### **Fase 3: Obtener Productos Shopify Existentes** (`rms_to_shopify.py:214-239`)
```graphql
# GraphQL Query para productos existentes
query getProducts {
  products(first: 250) {
    edges {
      node {
        id, title, handle, status, variants { ... }
      }
    }
  }
}
```

### **Fase 4: Procesamiento por Lotes** (`rms_to_shopify.py:241-325`)

#### **4.1 Mapeo de Datos** (`app/services/data_mapper.py:140-170`)
```python
# Transformar RMS → Shopify format
- title: Limpiar espacios múltiples
- handle: Generar URL-friendly
- description: Crear HTML completo con familia, género, color, talla, tax
- variants: Configurar precios, inventario, SKU
- tags: Combinar categoria + familia + color
```

#### **4.2 Operaciones por Producto**
```python
for batch in productos_lotes:
    for producto in batch:
        if producto_existe_en_shopify:
            if force_update or datos_diferentes:
                # ACTUALIZAR producto existente
                await shopify_client.update_product(id, datos)
        else:
            # CREAR nuevo producto
            await shopify_client.create_product(datos)
            # Actualizar descripción HTML por separado
            await shopify_client.update_product(id, {"descriptionHtml": html})
```

### **Fase 5: Creación/Actualización en Shopify** (`app/db/shopify_graphql_client.py`)

#### **5.1 Crear Producto** (Líneas 392-425)
```graphql
mutation productCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product { id, title, handle }
    userErrors { field, message }
  }
}
```

#### **5.2 Actualizar Descripción HTML** (Líneas 484-491)
```graphql
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id, descriptionHtml }
    userErrors { field, message }
  }
}
```

### **Fase 6: Manejo de Errores y Agregación**
```python
# Agregar errores por tipo
sync_stats = {
    "processed": 150,
    "created": 45,
    "updated": 105,
    "errors": 2,
    "skipped": 3
}
```

### **Fase 7: Reporte Final** (`rms_to_shopify.py:455-480`)
```json
{
    "success": true,
    "total_processed": 150,
    "created": 45,
    "updated": 105,
    "errors": 2,
    "execution_time": "00:05:23",
    "details": {
        "rms_products_found": 150,
        "shopify_products_existing": 105,
        "batch_size": 25,
        "error_details": [...]
    }
}
```

## 🎛️ **Parámetros de Configuración**

```bash
# Intervalo automático
SYNC_INTERVAL_MINUTES=15

# Tamaño de lotes
SYNC_BATCH_SIZE=100

# Timeout
SYNC_TIMEOUT_MINUTES=30

# Base de datos RMS
RMS_VIEW_ITEMS_TABLE=View_Items
```

## 🔧 **Puntos de Entrada**

1. **API REST**: `app/api/v1/endpoints/sync.py:165-248`
2. **Scheduler**: `app/core/scheduler.py` (pendiente implementación)
3. **Background Tasks**: Para ejecución asíncrona
4. **Startup**: `app/core/lifespan.py:253-268`

## 📊 **Endpoints de Sincronización Disponibles**

### RMS → Shopify
```bash
# Sincronización básica
POST /api/v1/sync/rms-to-shopify
{
    "force_update": false,
    "batch_size": 100,
    "filter_categories": ["categoria1", "categoria2"],
    "dry_run": false,
    "run_async": true
}

# Sincronización completa bidireccional
POST /api/v1/sync/full-sync
{
    "force_update": false,
    "batch_size": 50
}
```

### Shopify → RMS
```bash
# Sincronización de órdenes
POST /api/v1/sync/shopify-to-rms
{
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "batch_size": 25
}
```

## 🔍 **Monitoreo y Estado**

### Health Check
```bash
GET /health
```

### Métricas
```bash
GET /metrics
```

### Estado de Sincronización
```bash
GET /api/v1/sync/status
```

## ⚙️ **Configuraciones Importantes**

### Variables de Entorno Críticas
```bash
# RMS Database
RMS_DB_HOST=190.106.75.222,1438
RMS_DB_NAME=BB57_TempSF
RMS_DB_USER=your_user
RMS_DB_PASSWORD=your_password

# Shopify API
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token
SHOPIFY_API_VERSION=2025-04

# Sincronización
ENABLE_SCHEDULED_SYNC=True
SYNC_INTERVAL_MINUTES=15
SYNC_BATCH_SIZE=100
SYNC_TIMEOUT_MINUTES=30
SYNC_MAX_CONCURRENT_JOBS=3
```

## 🚨 **Resolución de Problemas Comunes**

### Error de Conexión a RMS
```bash
# Verificar conectividad
telnet 190.106.75.222 1438

# Verificar credenciales en logs
docker logs rms-shopify-app
```

### Error de API Shopify
```bash
# Verificar token de acceso
curl -H "X-Shopify-Access-Token: YOUR_TOKEN" \
     "https://your-shop.myshopify.com/admin/api/2025-04/shop.json"
```

### Productos No Sincronizados
```bash
# Verificar en logs la razón específica
grep "ERROR\|WARN" logs/sync.log

# Ejecutar sincronización forzada
POST /api/v1/sync/rms-to-shopify
{"force_update": true}
```

La sincronización es robusta con manejo de errores, procesamiento por lotes, y logging detallado en cada paso.