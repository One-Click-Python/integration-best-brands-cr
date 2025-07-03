# Sincronización de Productos: RMS → Shopify

## Descripción General

Este documento detalla el proceso de sincronización de productos, inventario y precios desde Microsoft Retail Management System (RMS) hacia Shopify. La sincronización permite que los productos del sistema RMS se publiquen automáticamente en la tienda online de Shopify con taxonomía avanzada, variantes múltiples y metadatos estructurados.

## Arquitectura del Sistema

### Componentes Principales

1. **RMSToShopifySync Service** (`app/services/rms_to_shopify.py`)
   - Servicio principal que orquesta la sincronización
   - Maneja el flujo completo de pasos A-J
   - Gestiona errores y reintentos por lotes

2. **EnhancedDataMapper** (`app/services/enhanced_data_mapper.py`)
   - Mapea datos RMS a Shopify Standard Product Taxonomy
   - Resuelve categorías usando algoritmo de búsqueda inteligente
   - Normaliza tallas y crea metafields estructurados

3. **MultipleVariantsCreator** (`app/services/multiple_variants_creator.py`)
   - Crea productos con múltiples variantes (color/talla)
   - Maneja la lógica de agrupación por CCOD
   - Integra con gestión automática de descuentos

4. **VariantMapper** (`app/services/variant_mapper.py`)
   - Agrupa artículos por CCOD para crear variantes
   - Optimiza la estructura de productos
   - Maneja casos especiales y fallbacks

5. **DiscountManager** (`app/services/discount_manager.py`)
   - Crea descuentos automáticos basados en precios de oferta
   - Maneja fechas de promoción (SaleStartDate/SaleEndDate)
   - Soporta descuentos básicos y por aplicación

6. **InventoryManager** (`app/services/inventory_manager.py`)
   - Gestiona cantidades de inventario por ubicación
   - Maneja activación de seguimiento de inventario
   - Actualiza stock en tiempo real

7. **RMSHandler** (`app/db/rms_handler.py`)
   - Conecta con SQL Server RMS
   - Ejecuta consultas optimizadas a View_Items
   - Maneja filtros y paginación

8. **ShopifyGraphQLClient** (`app/db/shopify_graphql_client.py`)
   - Cliente GraphQL optimizado para Shopify
   - Maneja operaciones masivas de metafields
   - Soporta taxonomía estándar de productos

## Estructura de la Base de Datos RMS

### Tabla Principal: View_Items

La tabla `View_Items` en RMS consolida toda la información de productos:

```sql
SELECT 
    Familia,                -- Clasificación principal (Zapatos, Ropa, Accesorios)
    Genero,                 -- Audiencia objetivo (Hombre, Mujer, Niño, Niña)
    Categoria,              -- Categoría específica (Tenis, Botas, Sandalias, etc.)
    CCOD,                   -- Código de modelo + color
    C_ARTICULO,             -- SKU único final
    ItemID,                 -- ID secuencial interno RMS
    Description,            -- Nombre comercial del producto
    color,                  -- Color del producto
    talla,                  -- Código/texto de talla
    Quantity,               -- Cantidad disponible
    Price,                  -- Precio lista antes de impuestos
    SaleStartDate,          -- Fecha inicio promoción
    SaleEndDate,            -- Fecha fin promoción
    SalePrice,              -- Precio promocional
    ExtendedCategory,       -- Categoría extendida para filtros
    Tax,                    -- Porcentaje de impuesto (default 13%)
    Exis00,                 -- Stock bodega principal
    Exis57                  -- Stock alternativo
FROM View_Items
```

### Clasificación de Productos RMS

#### Familias (5 principales)
- **Zapatos**: Calzado en general
- **Ropa**: Prendas de vestir
- **Accesorios**: Bolsos, carteras, cinturones
- **Miscelaneos**: Productos varios
- **n/d**: Sin definir

#### Categorías (22 principales)
- **Calzado**: Tenis, Botas, Sandalias, Flats, Tacones, Vestir, Oxford, Deportivos
- **Ropa**: Vestidos, Blusas, Pantalones, Faldas, Trajes
- **Accesorios**: Bolsos, Carteras, Cinturones, Billeteras

#### Géneros
- Hombre, Mujer, Niño, Niña, Bebé, Unisex

## Flujo de Sincronización (Pasos A-J)

### Paso A: Extracción de Datos RMS
1. Consulta optimizada a `View_Items` con filtros aplicados
2. Agrupación por CCOD para identificar variantes
3. Validación de datos requeridos (SKU, descripción, precio)
4. Exclusión de productos sin stock (opcional)

### Paso B: Creación/Actualización del Producto Base
1. Mapeo de familia y categoría a taxonomy de Shopify
2. Normalización del título y descripción
3. Asignación de vendor y product_type
4. Creación del producto principal con GraphQL

### Paso C: Creación/Actualización de Variantes
1. Agrupación de artículos por CCOD
2. Creación de opciones (Color, Talla)
3. Asignación de precios y SKUs
4. Configuración de tracking de inventario

### Paso D: Actualización de Inventario
1. Activación del tracking por variante
2. Configuración de cantidades por ubicación
3. Actualización de stock disponible
4. Manejo de ubicaciones múltiples

### Paso E: Creación/Actualización de Metafields
1. Metafields RMS (familia, categoria, talla, color)
2. Metafields normalizados (talla_original, extended_category)
3. Metafields de atributos (JSON completo)
4. Metafields de audiencia (target_gender, age_group)

### Paso F-G: Verificación de Precios de Oferta
1. Detección de precios de oferta (SalePrice vs Price)
2. Configuración de compareAtPrice
3. Validación de fechas de promoción
4. Preparación para descuentos automáticos

### Paso H: Creación de Descuentos Automáticos
1. Cálculo de porcentaje de descuento
2. Creación de descuento básico en Shopify
3. Configuración de fechas de validez
4. Asignación a productos específicos

### Paso J: Finalización y Logging
1. Registro de métricas de sincronización
2. Logging de errores y advertencias
3. Actualización de timestamps
4. Generación de reportes

## Mapeo de Campos: RMS → Shopify

### Producto Principal

| Campo Shopify | Origen RMS | Transformación | Descripción |
|---------------|------------|----------------|-------------|
| title | Description | Limpieza y normalización | Título del producto |
| vendor | Familia | Mapeo directo | Marca/Proveedor |
| productType | Categoria | Mapeo a taxonomy | Tipo de producto |
| handle | C_ARTICULO + Description | Slugify único | URL amigable |
| status | Quantity | > 0 = ACTIVE, = 0 = DRAFT | Estado del producto |
| productCategory | Categoria | Resolución inteligente | Taxonomía estándar Shopify |

### Variantes de Producto

| Campo Shopify | Origen RMS | Transformación | Descripción |
|---------------|------------|----------------|-------------|
| sku | C_ARTICULO | Directo | SKU único |
| price | Price | Corrección de formato | Precio base |
| compareAtPrice | SalePrice | Si existe precio oferta | Precio original |
| inventoryQuantity | Quantity | Directo | Stock disponible |
| option1 (Color) | color | Capitalización | Opción de color |
| option2 (Talla) | talla | Normalización | Opción de talla |
| weight | - | 0 | Peso del producto |
| requiresShipping | - | true | Requiere envío |
| inventoryManagement | - | SHOPIFY | Gestión de inventario |
| inventoryPolicy | - | DENY | Política de inventario |

### Sistema de Metafields

#### Metafields RMS Core
```json
{
  "rms.familia": {
    "type": "single_line_text_field",
    "value": "Zapatos",
    "description": "Familia de producto RMS"
  },
  "rms.categoria": {
    "type": "single_line_text_field", 
    "value": "Tenis",
    "description": "Categoría específica RMS"
  },
  "rms.talla": {
    "type": "single_line_text_field",
    "value": "23.5", 
    "description": "Talla normalizada"
  },
  "rms.talla_original": {
    "type": "single_line_text_field",
    "value": "23½",
    "description": "Talla original RMS (si es diferente)"
  },
  "rms.color": {
    "type": "single_line_text_field",
    "value": "Negro",
    "description": "Color del producto"
  }
}
```

#### Metafields Extendidos
```json
{
  "rms.ccod": {
    "type": "single_line_text_field",
    "value": "24YM05051",
    "description": "Código de modelo RMS"
  },
  "rms.extended_category": {
    "type": "single_line_text_field",
    "value": "Zapatos > Tenis",
    "description": "Categoría jerárquica"
  },
  "rms.product_attributes": {
    "type": "json",
    "value": "{\"item_id\": 12345, \"genero\": \"Hombre\", \"tax\": 13}",
    "description": "Todos los atributos RMS en JSON"
  }
}
```

#### Metafields de Audiencia
```json
{
  "custom.target_gender": {
    "type": "single_line_text_field",
    "value": "Men",
    "description": "Género objetivo"
  },
  "custom.age_group": {
    "type": "single_line_text_field", 
    "value": "Adult",
    "description": "Grupo de edad"
  },
  "custom.shoe_size": {
    "type": "single_line_text_field",
    "value": "23.5",
    "description": "Talla de calzado específica"
  }
}
```

## Sistema de Taxonomía Avanzada

### Mapeo Familia → Taxonomía Shopify

| Familia RMS | Product Type | Taxonomía Principal | Búsqueda Inteligente |
|-------------|--------------|-------------------|-------------------|
| Zapatos | Footwear | Shoes | Athletic Shoes, Boots, Sandals |
| Ropa | Apparel & Accessories | Clothing | Dresses, Tops, Bottoms |
| Accesorios | Apparel & Accessories | Bags & Luggage | Handbags, Wallets |
| Miscelaneos | Home & Garden | Miscellaneous | Various categories |

### Resolución Inteligente de Categorías

El sistema usa un algoritmo de puntuación para resolver categorías:

```python
def resolve_taxonomy_category(categoria: str, familia: str) -> Optional[Dict]:
    # 1. Búsqueda exacta en mapeo predefinido
    if categoria in CATEGORIA_TO_TAXONOMY_MAPPING:
        return CATEGORIA_TO_TAXONOMY_MAPPING[categoria]
    
    # 2. Búsqueda por términos múltiples con scoring
    search_terms = get_search_terms(categoria, familia)
    best_match = find_best_taxonomy_match(search_terms)
    
    # 3. Fallback a categoría genérica por familia
    return get_fallback_taxonomy(familia)
```

### Normalización de Tallas

Sistema avanzado para normalizar diferentes formatos:

```python
def normalize_size(talla: str) -> Tuple[str, str]:
    """
    Normaliza tallas de diferentes formatos:
    - "23½" → "23.5" 
    - "¼" → ".25"
    - "¾" → ".75"
    - "M" → "M" (sin cambio)
    - "XL" → "XL" (sin cambio)
    """
    original = talla
    normalized = talla
    
    # Reemplazo de fracciones Unicode
    if "½" in talla:
        normalized = talla.replace("½", ".5")
    elif "¼" in talla:
        normalized = talla.replace("¼", ".25") 
    elif "¾" in talla:
        normalized = talla.replace("¾", ".75")
    
    return normalized, original if normalized != original else None
```

## Agrupación de Variantes por CCOD

### Lógica de Agrupación

El sistema agrupa artículos por CCOD para crear productos con múltiples variantes:

```python
def group_items_by_ccod(items: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Agrupa artículos por CCOD normalizado.
    Un CCOD representa un modelo específico en un color específico.
    """
    groups = {}
    
    for item in items:
        ccod = normalize_ccod(item['ccod'])
        if ccod not in groups:
            groups[ccod] = []
        groups[ccod].append(item)
    
    # Filtrar grupos que realmente tienen variaciones
    return {k: v for k, v in groups.items() if has_real_variations(v)}
```

### Ejemplo de Agrupación

**Datos RMS:**
```
CCOD: 24YM05051, Color: Negro, Talla: 23, SKU: 24YM05051-NEG-23
CCOD: 24YM05051, Color: Negro, Talla: 24, SKU: 24YM05051-NEG-24  
CCOD: 24YM05051, Color: Negro, Talla: 25, SKU: 24YM05051-NEG-25
```

**Resultado Shopify:**
- **Producto**: Tenis Deportivo Negro (basado en CCOD 24YM05051)
- **Variantes**: 
  - Color: Negro, Talla: 23, SKU: 24YM05051-NEG-23
  - Color: Negro, Talla: 24, SKU: 24YM05051-NEG-24
  - Color: Negro, Talla: 25, SKU: 24YM05051-NEG-25

## Gestión Automática de Descuentos

### Detección de Promociones

El sistema detecta automáticamente productos en promoción:

```python
def detect_sale_items(items: List[Dict]) -> List[Dict]:
    """
    Detecta artículos con precios de oferta válidos.
    """
    sale_items = []
    
    for item in items:
        if (item.get('sale_price') and 
            item.get('sale_price') < item.get('price') and
            item.get('sale_start_date') and 
            item.get('sale_end_date')):
            
            discount_percentage = calculate_discount_percentage(
                item['price'], item['sale_price']
            )
            
            if discount_percentage >= 5:  # Mínimo 5% descuento
                sale_items.append({
                    **item,
                    'discount_percentage': discount_percentage
                })
    
    return sale_items
```

### Creación de Descuentos en Shopify

```python
async def create_automatic_discount(item: Dict) -> Optional[str]:
    """
    Crea descuento automático en Shopify basado en datos RMS.
    """
    discount_data = {
        "title": f"Oferta {item['description']} - {item['discount_percentage']}%",
        "method": {
            "percentage": {
                "percentage": item['discount_percentage']
            }
        },
        "targets": [
            {
                "productVariants": {
                    "variants": {
                        "id": item['shopify_variant_id']
                    }
                }  
            }
        ],
        "startsAt": item['sale_start_date'],
        "endsAt": item['sale_end_date'],
        "status": "ACTIVE"
    }
    
    return await create_shopify_discount(discount_data)
```

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

# Configuración de sincronización
SYNC_BATCH_SIZE=10
SYNC_INCLUDE_ZERO_STOCK=false
SYNC_FORCE_UPDATE=false
```

### 2. Permisos Requeridos en Shopify

El token de acceso debe tener estos permisos:

- `read_products`
- `write_products` 
- `read_inventory`
- `write_inventory`
- `read_product_listings`
- `write_product_listings`
- `write_discounts` (para descuentos automáticos)

### 3. Ejecutar Sincronización

#### Sincronización Completa
```bash
# Sincronizar todos los productos
curl -X POST http://localhost:8000/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "force_update": false,
    "batch_size": 10,
    "include_zero_stock": false,
    "run_async": true
  }'
```

#### Sincronización por CCOD Específico
```bash
# Sincronizar un modelo específico
curl -X POST http://localhost:8000/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "ccod": "24YM05051",
    "force_update": true
  }'
```

#### Sincronización por Categorías
```bash
# Sincronizar categorías específicas
curl -X POST http://localhost:8000/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "filter_categories": ["Tenis", "Botas"],
    "include_zero_stock": true,
    "batch_size": 20
  }'
```

#### Sincronización por Familia
```bash
# Sincronizar familia específica
curl -X POST http://localhost:8000/api/v1/sync/rms-to-shopify \
  -H "Content-Type: application/json" \
  -d '{
    "filter_families": ["Zapatos"],
    "force_update": false,
    "batch_size": 15
  }'
```

### 4. Scripts de Sincronización

#### Script de Sincronización Rápida
```bash
# Ejecutar script de sincronización rápida
poetry run python quick_sync.py
```

#### Script de Sincronización Completa  
```bash
# Ejecutar script de sincronización completa
poetry run python sync_all_products.py
```

## Monitoreo y Logging

### Métricas de Sincronización

El sistema registra métricas detalladas:

```python
{
    "sync_start_time": "2025-07-02T10:00:00Z",
    "sync_end_time": "2025-07-02T10:30:00Z", 
    "total_items_processed": 450,
    "products_created": 120,
    "products_updated": 80,
    "variants_created": 450,
    "variants_updated": 200,
    "discounts_created": 25,
    "metafields_created": 1800,
    "errors_count": 5,
    "warnings_count": 12
}
```

### Logs Detallados

```
INFO: [Step A] Starting RMS data extraction for batch 1/10
INFO: [Step A] Found 45 items in RMS View_Items
INFO: [Step B] Grouped into 12 products by CCOD
INFO: [Step C] Creating product: Tenis Deportivo (CCOD: 24YM05051)
INFO: [Step D] Created 3 variants for product
INFO: [Step E] Activating inventory tracking for variants
INFO: [Step F] Creating 18 metafields for product
INFO: [Step G] Detected sale price for variant 24YM05051-NEG-23
INFO: [Step H] Created automatic discount: 20% off Tenis Deportivo
INFO: [Step J] Product sync completed successfully
```

### Manejo de Errores

```python
# Tipos de errores comunes
ERROR_TYPES = {
    "MISSING_SKU": "Artículo sin SKU (C_ARTICULO)",
    "INVALID_PRICE": "Precio inválido o negativo", 
    "TAXONOMY_NOT_FOUND": "No se pudo resolver taxonomía",
    "SHOPIFY_API_ERROR": "Error en API de Shopify",
    "RMS_CONNECTION_ERROR": "Error de conexión a RMS",
    "DUPLICATE_SKU": "SKU duplicado en lote",
    "VARIANT_LIMIT_EXCEEDED": "Más de 100 variantes por producto"
}
```

## Optimizaciones y Rendimiento

### 1. Consultas SQL Optimizadas

```sql
-- Consulta optimizada con índices
SELECT [campos necesarios]
FROM View_Items WITH (NOLOCK)
WHERE C_ARTICULO IS NOT NULL 
  AND Description IS NOT NULL
  AND Price > 0
  AND (@include_zero_stock = 1 OR Quantity > 0)
  AND (@filter_categories IS NULL OR Categoria IN (@filter_categories))
ORDER BY CCOD, color, talla
```

### 2. Procesamiento por Lotes

- **Tamaño de lote**: 10-50 productos (configurable)
- **Concurrencia**: Máximo 3 lotes simultáneos
- **Rate limiting**: Respeta límites de API Shopify
- **Retry logic**: 3 reintentos con backoff exponencial

### 3. Cache y Optimizaciones

- **Taxonomía**: Cache de resoluciones de categorías
- **Metafields**: Bulk operations (hasta 25 simultáneos)
- **GraphQL**: Queries optimizadas con fragmentos
- **Conexiones**: Pool de conexiones SQL Server

## Limitaciones y Consideraciones

### Limitaciones Actuales

1. **Variantes por Producto**: Máximo 100 variantes (límite Shopify)
2. **Opciones por Producto**: Máximo 3 opciones (Color, Talla, Material)
3. **Metafields por Producto**: Sin límite práctico
4. **Tamaño de Lote**: Recomendado máximo 50 productos
5. **Rate Limiting**: 2 llamadas/segundo a Shopify API

### Consideraciones de Rendimiento

- **Tiempo de Sincronización**: ~2-3 segundos por producto
- **Base de Datos**: Requiere índices en View_Items
- **Memoria**: ~100MB por lote de 50 productos
- **Red**: Bandwidth intensivo para imágenes

### Consideraciones de Datos

- **Integridad**: Validación exhaustiva antes de crear productos
- **Duplicados**: Prevención por SKU y handle único
- **Encoding**: Soporte completo UTF-8 para caracteres especiales
- **Precisión**: Precios con 2 decimales máximo

## Solución de Problemas

### Problemas Comunes

#### 1. Conexión a RMS Fallida
```bash
# Verificar conexión
poetry run python -c "
from app.db.rms_handler import RMSHandler
handler = RMSHandler()
print(handler.test_connection())
"
```

#### 2. Productos Sin Taxonomía
```sql
-- Verificar categorías sin mapeo
SELECT DISTINCT Categoria 
FROM View_Items 
WHERE Categoria NOT IN (
    SELECT categoria FROM taxonomy_mappings
)
```

#### 3. SKUs Duplicados
```sql
-- Encontrar SKUs duplicados en RMS
SELECT C_ARTICULO, COUNT(*) as count
FROM View_Items 
GROUP BY C_ARTICULO 
HAVING COUNT(*) > 1
```

#### 4. Errores de API Shopify
```python
# Debug de respuestas GraphQL
DEBUG_SHOPIFY_QUERIES=true poetry run python sync_all_products.py
```

### Comandos de Diagnóstico

```bash
# Verificar estado de sincronización
curl -X GET http://localhost:8000/api/v1/sync/status

# Ver últimos logs
curl -X GET http://localhost:8000/api/v1/sync/logs?limit=50

# Verificar salud del sistema
curl -X GET http://localhost:8000/health

# Métricas de rendimiento
curl -X GET http://localhost:8000/metrics
```

### Limpieza y Mantenimiento

```bash
# Limpiar productos de prueba
curl -X DELETE http://localhost:8000/api/v1/sync/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Reconstruir índices de taxonomía
curl -X POST http://localhost:8000/api/v1/sync/rebuild-taxonomy

# Validar integridad de datos
curl -X POST http://localhost:8000/api/v1/sync/validate-data
```

## Próximos Pasos y Mejoras

### Funcionalidades Pendientes

1. **Sincronización de Imágenes**: Upload automático desde RMS
2. **Gestión de Colecciones**: Agrupación automática por categorías
3. **SEO Optimization**: Generación automática de meta descriptions
4. **Traducción**: Soporte multiidioma para contenido
5. **Integración con CDN**: Optimización de imágenes

### Optimizaciones Futuras

1. **Cache Inteligente**: Redis para datos frecuentemente accedidos
2. **Sincronización Incremental**: Solo cambios desde última sync
3. **Webhooks RMS**: Sincronización en tiempo real
4. **Machine Learning**: Mejora automática de taxonomía
5. **Reportes Avanzados**: Dashboard de analytics

## Contacto y Soporte

Para problemas con la sincronización RMS → Shopify:

1. **Logs de Sistema**: Revisar logs detallados de sincronización
2. **Base de Datos**: Verificar conectividad y estructura View_Items
3. **API Shopify**: Confirmar permisos y límites de rate
4. **Configuración**: Validar variables de entorno
5. **Documentación**: Consultar documentación oficial de Shopify GraphQL API

---

*Documento actualizado: Julio 2025*
*Versión del sistema: 2.0*
*Compatible con: Shopify API 2025-04, RMS SQL Server*