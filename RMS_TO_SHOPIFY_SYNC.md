# Sincronización de Productos: RMS → Shopify

## Descripción General

Este documento detalla el proceso de sincronización de productos, inventario y precios desde Microsoft Retail Management System (RMS) hacia Shopify. La sincronización permite que los productos del sistema RMS se publiquen automáticamente en la tienda online de Shopify con taxonomía avanzada, variantes múltiples y metadatos estructurados.

## 🚀 Características Principales

- **Motor de Sincronización Automática**: Detección de cambios cada 5 minutos usando `Item.LastUpdated`
- **Agrupación Inteligente por CCOD**: Creación automática de variantes por color/talla
- **Mapeo Avanzado de Taxonomías**: Conversión a Standard Product Taxonomy de Shopify
- **Normalización de Datos**: Tallas fraccionarias (`23½` → `23.5`) y caracteres especiales
- **Gestión de Inventario**: Actualización en tiempo real con soporte multi-ubicación
- **Metafields Estructurados**: Preservación completa de datos RMS
- **Descuentos Automáticos**: Creación de ofertas basadas en SalePrice
- **Mecanismo de Bloqueo**: Prevención de sincronizaciones concurrentes

## Arquitectura del Sistema

### Componentes Principales

1. **RMSToShopifySync Service** (`app/services/rms_to_shopify.py`)
   - Servicio principal que orquesta la sincronización
   - Maneja el flujo completo de pasos A-J
   - Gestiona errores y reintentos por lotes
   - Implementa mecanismo de bloqueo anti-concurrencia

2. **DataMapper** (`app/services/data_mapper.py`)
   - Mapea datos RMS a formato Shopify
   - Resuelve categorías usando algoritmo de búsqueda inteligente
   - Normaliza tallas y crea metafields estructurados
   - Maneja casos especiales y encoding

3. **MultipleVariantsCreator** (`app/services/multiple_variants_creator/`)
   - Sistema modular para creación de variantes complejas
   - **DataPreparator**: Prepara y valida datos de entrada
   - **VariantManager**: Gestiona creación/actualización de variantes
   - **MetafieldsManager**: Maneja metafields en bulk
   - **InventoryManager**: Actualiza inventario por ubicación

4. **VariantMapper** (`app/services/variant_mapper.py`)
   - Agrupa artículos por CCOD para crear variantes
   - Optimiza la estructura de productos
   - Maneja casos especiales y fallbacks
   - Detecta variaciones reales (color/talla)

5. **ChangeDetector** (`app/services/change_detector.py`)
   - Monitor automático de cambios en RMS
   - Consulta `Item.LastUpdated` cada 5 minutos
   - Vincula `Item` con `View_Items` para datos completos
   - Maneja zonas horarias y timestamps

6. **RMSHandler** (`app/db/rms_handler.py`)
   - Conecta con SQL Server RMS usando connection pooling
   - Ejecuta consultas optimizadas con índices
   - Maneja filtros, paginación y timeouts
   - Soporte para consultas asíncronas

7. **ShopifyGraphQLClient** (`app/db/shopify_graphql_client.py`)
   - Cliente GraphQL optimizado para Shopify
   - Maneja operaciones masivas (bulk operations)
   - Soporta taxonomía estándar de productos
   - Rate limiting automático

## Estructura de la Base de Datos RMS

### Tabla Principal: View_Items

La vista `View_Items` en RMS consolida toda la información de productos:

```sql
SELECT 
    Familia,                -- Clasificación principal (Zapatos, Ropa, Accesorios)
    Genero,                 -- Audiencia objetivo (Hombre, Mujer, Niño, Niña)
    Categoria,              -- Categoría específica (Tenis, Botas, Sandalias, etc.)
    CCOD,                   -- Código de modelo + color (clave de agrupación)
    C_ARTICULO,             -- SKU único final
    ItemID,                 -- ID secuencial interno RMS
    Description,            -- Nombre comercial del producto
    color,                  -- Color del producto
    talla,                  -- Código/texto de talla
    Quantity,               -- Cantidad disponible total
    Price,                  -- Precio lista antes de impuestos
    SaleStartDate,          -- Fecha inicio promoción
    SaleEndDate,            -- Fecha fin promoción
    SalePrice,              -- Precio promocional
    ExtendedCategory,       -- Categoría extendida para filtros
    Tax,                    -- Porcentaje de impuesto (default 13%)
    Exis00,                 -- Stock bodega principal
    Exis57,                 -- Stock tienda/alternativo
    LastUpdated             -- Timestamp de última modificación (desde Item table)
FROM View_Items
```

### Tabla de Cambios: Item

```sql
SELECT 
    ID as ItemID,
    LastUpdated,            -- Timestamp UTC de último cambio
    DateCreated,            -- Fecha de creación
    ItemLookupCode          -- Código de búsqueda
FROM Item
WHERE LastUpdated > @last_sync_time
```

### Clasificación de Productos RMS

#### Familias (5 principales)
- **Zapatos**: Calzado en general
- **Ropa**: Prendas de vestir
- **Accesorios**: Bolsos, carteras, cinturones
- **Miscelaneos**: Productos varios
- **n/d**: Sin definir

#### Categorías (30+ tipos)
- **Calzado**: Tenis, Botas, Sandalias, Flats, Tacones, Vestir, Oxford, Deportivos, Casuales, Alpargatas
- **Ropa**: Vestidos, Blusas, Pantalones, Faldas, Trajes, Camisetas, Jeans
- **Accesorios**: Bolsos, Carteras, Cinturones, Billeteras, Mochilas, Maletines

#### Géneros
- Hombre, Mujer, Niño, Niña, Bebé, Unisex

## Flujo de Sincronización (Pasos A-J)

### Paso A: Extracción de Datos RMS
1. **Detección de cambios** usando `Item.LastUpdated` (automático cada 5 min)
2. **Consulta optimizada** a `View_Items` con JOIN a `Item` para cambios
3. **Validación** de datos requeridos (SKU, descripción, precio)
4. **Filtrado** opcional por categorías, familias o stock
5. **Agrupación** por CCOD para identificar productos con variantes

### Paso B: Creación/Actualización del Producto Base
1. **Mapeo de taxonomía** usando sistema inteligente de búsqueda
2. **Normalización** del título (limpieza de caracteres especiales)
3. **Asignación** de vendor (familia) y product_type (categoría)
4. **Creación** del producto principal con GraphQL mutations
5. **Manejo** de errores con retry automático

### Paso C: Creación/Actualización de Variantes
1. **Agrupación** de artículos por CCOD (mismo modelo)
2. **Creación de opciones** (Color como option1, Talla como option2)
3. **Asignación** de precios, SKUs y códigos de barras
4. **Configuración** de tracking de inventario y políticas
5. **Bulk creation** para eficiencia (hasta 100 variantes)

### Paso D: Actualización de Inventario
1. **Obtención** de location_id principal de Shopify
2. **Activación** del tracking por cada variante
3. **Actualización** de cantidades disponibles
4. **Soporte** para múltiples ubicaciones (bodega/tienda)
5. **Sincronización** de políticas de inventario

### Paso E: Creación/Actualización de Metafields
1. **Core RMS Fields**:
   - `rms.familia`: Familia de producto
   - `rms.categoria`: Categoría específica
   - `rms.talla`: Talla normalizada
   - `rms.color`: Color del producto
   - `rms.ccod`: Código de modelo

2. **Extended Fields**:
   - `rms.talla_original`: Talla original si fue normalizada
   - `rms.extended_category`: Path completo de categoría
   - `rms.product_attributes`: JSON con todos los atributos
   - `rms.genero`: Género/audiencia objetivo
   - `rms.item_id`: ID interno de RMS

3. **Custom Fields**:
   - `custom.target_gender`: Género en inglés
   - `custom.age_group`: Grupo de edad
   - `custom.shoe_size`: Talla específica para calzado

### Paso F-G: Verificación de Precios de Oferta
1. **Detección** de precios promocionales (SalePrice < Price)
2. **Validación** de fechas de vigencia de ofertas
3. **Configuración** de compareAtPrice en variantes
4. **Cálculo** de porcentaje de descuento
5. **Preparación** para creación de descuentos automáticos

### Paso H: Creación de Descuentos Automáticos
1. **Evaluación** si el descuento es >= 5%
2. **Creación** de descuento básico en Shopify
3. **Configuración** de fechas de inicio/fin
4. **Asignación** a productos/variantes específicos
5. **Activación** automática del descuento

### Paso I: Procesamiento de Imágenes (Opcional)
1. **Detección** de URLs de imágenes en datos RMS
2. **Descarga** y validación de imágenes
3. **Upload** a Shopify CDN
4. **Asignación** a productos/variantes
5. **Optimización** automática por Shopify

### Paso J: Finalización y Logging
1. **Registro** de métricas detalladas de sincronización
2. **Logging** estructurado de operaciones realizadas
3. **Actualización** de timestamps de última sincronización
4. **Generación** de reporte de sincronización
5. **Liberación** del lock de sincronización

## Mapeo de Campos: RMS → Shopify

### Producto Principal

| Campo Shopify | Origen RMS | Transformación | Descripción |
|---------------|------------|----------------|-------------|
| title | Description | Limpieza y normalización | Título del producto |
| vendor | Familia | Mapeo directo | Marca/Proveedor |
| productType | Categoria | Mapeo a taxonomy | Tipo de producto |
| handle | C_ARTICULO + Description | Slugify único | URL amigable |
| status | Quantity | > 0 = ACTIVE, = 0 = DRAFT | Estado del producto |
| productCategory | Categoria + Familia | Resolución inteligente | Taxonomía estándar Shopify |
| tags | Genero, Categoria | Array de tags | Etiquetas para búsqueda |

### Variantes de Producto

| Campo Shopify | Origen RMS | Transformación | Descripción |
|---------------|------------|----------------|-------------|
| sku | C_ARTICULO | Directo | SKU único |
| barcode | C_ARTICULO | Opcional | Código de barras |
| price | Price | Formato decimal (2 decimales) | Precio base |
| compareAtPrice | Price (si hay SalePrice) | Si SalePrice < Price | Precio original |
| inventoryQuantity | Quantity | Directo | Stock disponible |
| option1 (Color) | color | Capitalización | Opción de color |
| option2 (Talla) | talla | Normalización | Opción de talla |
| weight | - | 0 | Peso del producto |
| weightUnit | - | GRAMS | Unidad de peso |
| requiresShipping | - | true | Requiere envío |
| inventoryManagement | - | SHOPIFY | Gestión de inventario |
| inventoryPolicy | - | DENY | No permitir sobreventa |
| taxable | Tax > 0 | true/false | Aplica impuestos |

## Sistema de Taxonomía Avanzada

### Mapeo Inteligente de Categorías

El sistema utiliza un algoritmo de búsqueda y puntuación para mapear categorías RMS a la taxonomía estándar de Shopify:

```python
# Proceso de resolución de taxonomía
1. Búsqueda exacta en mapeo predefinido
2. Búsqueda por términos con algoritmo de scoring
3. Análisis de familia + categoría combinadas
4. Fallback a categoría genérica por familia
5. Default a "Miscellaneous" si no hay match
```

### Ejemplos de Mapeo

| Familia RMS | Categoría RMS | Taxonomía Shopify | Product Type |
|-------------|---------------|-------------------|--------------|
| Zapatos | Tenis | Apparel & Accessories > Shoes > Athletic Shoes | Sneakers |
| Zapatos | Botas | Apparel & Accessories > Shoes > Boots | Boots |
| Zapatos | Sandalias | Apparel & Accessories > Shoes > Sandals | Sandals |
| Ropa | MUJER-VEST | Apparel & Accessories > Women's Clothing | Dresses |
| Accesorios | Bolsos | Apparel & Accessories > Bags & Luggage > Handbags | Handbags |

### Normalización de Tallas

Sistema avanzado para normalizar diferentes formatos de tallas:

```python
# Ejemplos de normalización
"23½" → "23.5"
"23 ½" → "23.5"
"¼" → ".25"
"¾" → ".75"
"23,5" → "23.5"
"XXL" → "XXL" (sin cambio)
"38/40" → "38-40"
```

## Agrupación de Variantes por CCOD

### Lógica de Agrupación

El sistema agrupa artículos por CCOD (Código de Color y Modelo) para crear productos con múltiples variantes:

```python
# Ejemplo de agrupación
CCOD: 24YM05051 = Modelo 24YM050 + Color 51

Artículos RMS:
- CCOD: 24YM05051, Color: Negro, Talla: 38, SKU: 24YM05051-NEG-38
- CCOD: 24YM05051, Color: Negro, Talla: 39, SKU: 24YM05051-NEG-39
- CCOD: 24YM05051, Color: Negro, Talla: 40, SKU: 24YM05051-NEG-40

Resultado en Shopify:
- Producto: "Zapato Deportivo Negro"
- Variantes: 3 (una por cada talla)
```

### Validación de Agrupación

El sistema valida que las variantes tengan sentido:
- Mismo CCOD = mismo modelo y color
- Diferentes tallas = variantes válidas
- Validación de descripción consistente
- Detección de anomalías en agrupación

## Motor de Sincronización Automática

### Configuración del Motor

```bash
# Variables de entorno
ENABLE_SCHEDULED_SYNC=true          # Activar motor automático
SYNC_INTERVAL_MINUTES=5             # Intervalo de verificación
SYNC_BATCH_SIZE=10                  # Tamaño de lote
SYNC_MAX_CONCURRENT_JOBS=3          # Jobs paralelos máximos
ENABLE_SYNC_LOCK=true               # Activar bloqueo anti-concurrencia
SYNC_LOCK_TIMEOUT_SECONDS=1800      # Timeout del lock (30 min)
```

### Flujo del Motor Automático

1. **Verificación periódica** cada 5 minutos
2. **Consulta de cambios** en tabla `Item` por `LastUpdated`
3. **Obtención de datos** completos desde `View_Items`
4. **Procesamiento por lotes** respetando límites
5. **Registro de métricas** y estadísticas

### APIs de Control del Motor

```bash
# Estado del motor
GET /api/v1/sync/monitor/status

# Estadísticas detalladas
GET /api/v1/sync/monitor/stats

# Forzar sincronización manual
POST /api/v1/sync/monitor/trigger

# Actualizar intervalo
PUT /api/v1/sync/monitor/interval
{
  "interval_minutes": 10
}

# Ver actividad reciente
GET /api/v1/sync/monitor/recent-activity
```

## Gestión de Descuentos y Promociones

### Detección Automática de Ofertas

El sistema detecta y crea descuentos automáticamente cuando:
- `SalePrice` < `Price`
- `SaleStartDate` y `SaleEndDate` son válidas
- El descuento es >= 5%

### Tipos de Descuentos Soportados

1. **Porcentaje de descuento**: Calculado automáticamente
2. **Precio fijo**: Usando SalePrice directo
3. **Por categoría**: Aplicado a familias/categorías
4. **Por tiempo limitado**: Con fechas de vigencia

## Configuración y Puesta en Marcha

### 1. Variables de Entorno Requeridas

```bash
# Base de datos RMS (SQL Server)
RMS_DB_HOST=servidor.sql.com
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database  
RMS_DB_USER=usuario
RMS_DB_PASSWORD=contraseña
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server
RMS_CONNECTION_TIMEOUT=30

# API de Shopify
SHOPIFY_SHOP_URL=mi-tienda.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2025-04
SHOPIFY_RATE_LIMIT_PER_SECOND=2

# Configuración de sincronización
SYNC_BATCH_SIZE=10
SYNC_INCLUDE_ZERO_STOCK=false
SYNC_FORCE_UPDATE=false
ENABLE_DRY_RUN_MODE=false

# Redis para cache y locks
REDIS_URL=redis://localhost:6379/0
```

### 2. Permisos Requeridos en Shopify

El token de acceso debe tener estos permisos (scopes):

- `read_products` - Leer productos
- `write_products` - Crear/actualizar productos
- `read_inventory` - Leer inventario
- `write_inventory` - Actualizar inventario
- `read_product_listings` - Leer listados
- `write_product_listings` - Publicar productos
- `write_discounts` - Crear descuentos automáticos
- `read_price_rules` - Leer reglas de precio
- `write_price_rules` - Crear reglas de precio

### 3. Ejecutar Sincronización

#### Motor Automático (Recomendado)
```bash
# El motor se inicia automáticamente con la aplicación
poetry run uvicorn app.main:app --reload

# Verificar estado
curl http://localhost:8080/api/v1/sync/monitor/status
```

#### Sincronización Manual Completa
```bash
curl -X POST http://localhost:8080/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "force_update": false,
    "batch_size": 10,
    "include_zero_stock": false,
    "dry_run": false
  }'
```

#### Sincronización por CCOD Específico
```bash
curl -X POST http://localhost:8080/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "ccod": "24YM05051",
    "force_update": true
  }'
```

#### Sincronización por Categorías
```bash
curl -X POST http://localhost:8080/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "filter_categories": ["Tenis", "Botas"],
    "include_zero_stock": true,
    "batch_size": 20
  }'
```

#### Sincronización por Familia
```bash
curl -X POST http://localhost:8080/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "filter_families": ["Zapatos"],
    "force_update": false,
    "batch_size": 15
  }'
```

## Monitoreo y Métricas

### Métricas de Sincronización en Tiempo Real

```bash
# Dashboard de métricas
GET /api/v1/metrics/dashboard

# Respuesta ejemplo:
{
  "sync_metrics": {
    "total_syncs_today": 288,
    "products_synced": 1250,
    "variants_created": 4500,
    "metafields_created": 8750,
    "errors_today": 5,
    "success_rate": 99.6,
    "average_sync_time": "2.3s",
    "last_sync": "2025-01-30T10:45:00Z"
  },
  "system_metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 35.4,
    "active_connections": 12
  }
}
```

### Logs Estructurados

```json
{
  "timestamp": "2025-01-30T10:45:00Z",
  "level": "INFO",
  "service": "RMSToShopifySync",
  "step": "A",
  "message": "Starting RMS data extraction",
  "context": {
    "batch_number": 1,
    "total_batches": 10,
    "items_found": 45,
    "filters": {
      "categories": ["Tenis"],
      "include_zero_stock": false
    }
  }
}
```

### Alertas y Notificaciones

El sistema genera alertas automáticas para:
- Errores de conexión a RMS/Shopify
- Tasa de error > 5%
- Sincronización bloqueada > 30 minutos
- Espacio en disco < 10%
- Motor automático detenido

## Optimizaciones y Rendimiento

### 1. Consultas SQL Optimizadas

```sql
-- Índices recomendados para View_Items
CREATE INDEX IX_ViewItems_LastUpdated ON View_Items(LastUpdated)
CREATE INDEX IX_ViewItems_CCOD ON View_Items(CCOD)
CREATE INDEX IX_ViewItems_Categoria ON View_Items(Categoria)
CREATE INDEX IX_ViewItems_C_ARTICULO ON View_Items(C_ARTICULO)

-- Consulta optimizada con hints
SELECT TOP (@batch_size) 
    vi.*,
    i.LastUpdated
FROM View_Items vi WITH (NOLOCK)
INNER JOIN Item i WITH (NOLOCK) ON vi.ItemID = i.ID
WHERE i.LastUpdated > @last_sync_time
  AND vi.C_ARTICULO IS NOT NULL 
  AND vi.Description IS NOT NULL
  AND vi.Price > 0
  AND (@include_zero_stock = 1 OR vi.Quantity > 0)
ORDER BY i.LastUpdated ASC
```

### 2. Procesamiento por Lotes

- **Tamaño óptimo**: 10-20 productos por lote
- **Paralelismo**: Hasta 3 lotes simultáneos
- **Rate limiting**: 2 llamadas/segundo a Shopify
- **Retry logic**: 3 reintentos con backoff exponencial
- **Circuit breaker**: Pausa tras 5 errores consecutivos

### 3. Cache y Optimizaciones

- **Redis Cache**:
  - Taxonomías resueltas (TTL: 1 hora)
  - Metafield definitions (TTL: 24 horas)
  - Location IDs (TTL: 1 hora)
  
- **Connection Pooling**:
  - SQL Server: 5-20 conexiones
  - Redis: 10 conexiones
  - HTTP: Keep-alive habilitado

- **Bulk Operations**:
  - Metafields: Hasta 25 por llamada
  - Variantes: Hasta 100 por producto
  - Inventario: Hasta 50 actualizaciones

## Limitaciones y Consideraciones

### Límites de Shopify

1. **Variantes por Producto**: Máximo 100
2. **Opciones por Producto**: Máximo 3 (usamos Color y Talla)
3. **Metafields por Producto**: Sin límite práctico
4. **Caracteres en título**: Máximo 255
5. **Rate Limiting**: 2 llamadas/segundo (ajustable)
6. **Tamaño de request**: Máximo 20MB
7. **Bulk operation**: Máximo 10,000 objetos

### Consideraciones de Rendimiento

- **Tiempo promedio**: 2-3 segundos por producto
- **Memoria**: ~2MB por producto en proceso
- **CPU**: Intensivo durante normalización
- **Red**: ~100KB por producto (sin imágenes)
- **Base de datos**: Requiere índices optimizados

### Consideraciones de Datos

- **Encoding**: UTF-8 completo (emojis soportados)
- **Decimales**: Máximo 2 para precios
- **SKUs**: Deben ser únicos globalmente
- **Handles**: Se generan automáticamente únicos
- **Validación**: Estricta antes de enviar a Shopify

## Solución de Problemas

### Problemas Comunes y Soluciones

#### 1. Error de Conexión a RMS
```bash
# Verificar conexión
curl http://localhost:8080/api/v1/admin/database-test

# Verificar driver ODBC
odbcinst -q -d

# Test manual de conexión
poetry run python -m app.db.test_connection
```

#### 2. Productos Sin Taxonomía
```bash
# Ver categorías sin mapeo
curl http://localhost:8080/api/v1/sync/unmapped-categories

# Actualizar mapeos
curl -X POST http://localhost:8080/api/v1/sync/refresh-taxonomy
```

#### 3. SKUs Duplicados
```sql
-- Encontrar SKUs duplicados
WITH DuplicateSKUs AS (
    SELECT C_ARTICULO, COUNT(*) as count
    FROM View_Items 
    GROUP BY C_ARTICULO 
    HAVING COUNT(*) > 1
)
SELECT v.* 
FROM View_Items v
INNER JOIN DuplicateSKUs d ON v.C_ARTICULO = d.C_ARTICULO
ORDER BY v.C_ARTICULO, v.ItemID
```

#### 4. Sincronización Bloqueada
```bash
# Ver estado del lock
curl http://localhost:8080/api/v1/admin/sync-lock-status

# Forzar liberación del lock (usar con cuidado)
curl -X DELETE http://localhost:8080/api/v1/admin/sync-lock
```

#### 5. Errores de Rate Limit
```bash
# Ajustar rate limit
curl -X PUT http://localhost:8080/api/v1/admin/rate-limit \
  -H "Content-Type: application/json" \
  -d '{"calls_per_second": 1}'
```

### Comandos de Diagnóstico

```bash
# Health check completo
curl http://localhost:8080/api/v1/health

# Ver últimos errores
curl http://localhost:8080/api/v1/logs?level=error&limit=50

# Estadísticas del día
curl http://localhost:8080/api/v1/metrics/daily-summary

# Test de mapeo de categoría
curl -X POST http://localhost:8080/api/v1/sync/test-mapping \
  -H "Content-Type: application/json" \
  -d '{"categoria": "Tenis", "familia": "Zapatos"}'
```

### Scripts de Mantenimiento

```bash
# Limpiar cache
curl -X POST http://localhost:8080/api/v1/admin/clear-cache

# Validar integridad de datos
curl -X POST http://localhost:8080/api/v1/admin/validate-data

# Reindexar productos
curl -X POST http://localhost:8080/api/v1/admin/reindex-products

# Backup de configuración
curl http://localhost:8080/api/v1/admin/export-config > config-backup.json
```

## Mejores Prácticas

### 1. Configuración Inicial
- Comenzar con lotes pequeños (5-10 productos)
- Activar modo dry-run para validar
- Sincronizar por categorías específicas primero
- Monitorear métricas durante las primeras sincronizaciones

### 2. Operación Diaria
- Dejar el motor automático activo 24/7
- Revisar dashboard de métricas diariamente
- Configurar alertas por email para errores críticos
- Realizar sincronización completa semanal (domingos)

### 3. Mantenimiento
- Limpiar logs antiguos mensualmente
- Actualizar mapeos de taxonomía según necesidad
- Revisar productos sin variantes periódicamente
- Monitorear crecimiento de base de datos

### 4. Performance
- Usar índices recomendados en SQL Server
- Mantener Redis activo para cache
- Ajustar batch_size según capacidad del servidor
- Programar sincronizaciones pesadas en horario nocturno

## Integración con Otros Sistemas

### Webhooks de Notificación
```bash
# Configurar webhook para notificar completación
POST /api/v1/admin/webhook-config
{
  "event": "sync.completed",
  "url": "https://tu-sistema.com/webhook",
  "headers": {
    "Authorization": "Bearer token"
  }
}
```

### API para Sistemas Externos
```bash
# Obtener estado para dashboard externo
GET /api/v1/sync/external-status

# Trigger desde sistema externo
POST /api/v1/sync/external-trigger
Headers: X-API-Key: your-api-key
```

## Próximas Mejoras Planificadas

1. **Sincronización de Imágenes**: Upload automático desde URLs RMS
2. **Multi-idioma**: Soporte para traducciones automáticas
3. **IA para Categorización**: Mejora automática de mapeos con ML
4. **Sincronización Incremental**: Solo campos modificados
5. **Webhooks RMS**: Sincronización instantánea por triggers
6. **Gestión de Colecciones**: Creación automática por categorías
7. **SEO Automático**: Generación de meta descriptions con IA
8. **Reportes Avanzados**: Dashboard Analytics integrado

## Recursos y Referencias

### Documentación Oficial
- [Shopify GraphQL API](https://shopify.dev/docs/api/admin-graphql)
- [Shopify Product Taxonomy](https://help.shopify.com/en/manual/products/details/product-category)
- [SQL Server Best Practices](https://docs.microsoft.com/en-us/sql/relational-databases/performance/performance-center-for-sql-server-database-engine-and-azure-sql-database)

### Herramientas Útiles
- [Shopify GraphiQL Explorer](https://shopify.dev/docs/apps/tools/graphiql-admin-api)
- [SQL Server Profiler](https://docs.microsoft.com/en-us/sql/tools/sql-server-profiler/sql-server-profiler)
- [Redis Commander](https://github.com/joeferner/redis-commander)

### Soporte
- Email: enzo@oneclick.cr
- Documentación: `/docs` cuando la app está corriendo
- Logs: `logs/app.log` para debugging detallado

---

*Documento actualizado: Enero 2025*
*Versión del sistema: 2.5*
*Compatible con: Shopify API 2025-04, RMS SQL Server 2019+*