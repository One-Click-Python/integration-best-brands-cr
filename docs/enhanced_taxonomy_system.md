# Sistema Mejorado de Taxonomías y Metafields

## Resumen

Se ha implementado un sistema completamente mejorado para el mapeo de datos RMS a taxonomías estándar de Shopify y metafields estructurados. Este sistema reemplaza el mapeo básico anterior con una solución robusta que maneja correctamente todos los campos RMS (familia, categoria, talla, color).

## Componentes Principales

### 1. RMSTaxonomyMapper (`app/core/taxonomy_mapping.py`)

**Funcionalidades:**
- Mapeo comprehensivo de familias y categorías RMS a taxonomías Shopify
- Normalización automática de tallas (ej: `23½` → `23.5`)
- Creación estructurada de metafields
- Validación de tipos de metafields

**Mapeos Implementados:**

#### Familias RMS → Shopify
- **Zapatos** → Footwear (búsqueda: shoes, footwear)
- **Ropa** → Apparel (búsqueda: apparel, clothing, fashion)
- **Accesorios** → Accessories (búsqueda: accessories, fashion accessories)
- **Miscelaneos** → Miscellaneous (búsqueda: miscellaneous, other)

#### Categorías Específicas → Taxonomías Shopify
- **Tenis** → Athletic Footwear (búsqueda: Athletic Shoes, Sneakers, Sports Shoes)
- **Botas** → Boots (búsqueda: Boots, Ankle Boots)
- **Sandalias** → Sandals (búsqueda: Sandals, Summer Shoes)
- **Tacones** → High Heels (búsqueda: High Heels, Dress Shoes)
- **Bolsos** → Handbags (búsqueda: Handbags, Bags, Purses)
- **MUJER-VEST-CERR-TA16** → Women's Dresses (búsqueda: Women's Dresses, Women's Formal Wear)
- Y muchas más...

### 2. EnhancedDataMapper (`app/services/enhanced_data_mapper.py`)

**Funcionalidades:**
- Mapeo completo de items RMS a productos Shopify
- Resolución automática de taxonomías usando búsqueda inteligente
- Creación bulk de metafields (hasta 25 simultáneos)
- Validación de mapeos antes de sincronización
- Sistema de cache para taxonomías resueltas

### 3. Consultas GraphQL Mejoradas (`app/db/shopify_graphql_queries.py`)

**Nuevas Consultas:**
- `TAXONOMY_CATEGORIES_QUERY` - Búsqueda de categorías
- `TAXONOMY_CATEGORY_DETAILS_QUERY` - Detalles completos de categoría
- `METAFIELDS_SET_MUTATION` - Creación bulk de metafields
- `CREATE_METAFIELD_DEFINITION_MUTATION` - Definiciones de metafields
- `CREATE_PRODUCT_WITH_CATEGORY_MUTATION` - Productos con categoría y metafields

### 4. Cliente GraphQL Mejorado (`app/db/shopify_graphql_client.py`)

**Nuevos Métodos:**
- `find_best_taxonomy_match()` - Encuentra la mejor coincidencia de taxonomía
- `create_metafields_bulk()` - Crea múltiples metafields eficientemente
- `create_metafield_definition()` - Crea definiciones de metafields
- `get_taxonomy_category_details()` - Obtiene detalles de categoría

## Metafields Estructurados

### Definiciones Implementadas

| Namespace | Key | Tipo | Descripción |
|-----------|-----|------|-------------|
| `rms` | `familia` | single_line_text_field | Familia del producto (Zapatos, Ropa, etc.) |
| `rms` | `categoria` | single_line_text_field | Categoría específica del producto |
| `rms` | `talla` | single_line_text_field | Talla normalizada |
| `rms` | `talla_original` | single_line_text_field | Talla original sin normalizar |
| `rms` | `color` | single_line_text_field | Color del producto |
| `rms` | `extended_category` | single_line_text_field | Categoría extendida (Familia > Categoría) |
| `rms` | `product_attributes` | json | Todos los atributos RMS en JSON |

### Ejemplo de Metafields Generados

```json
[
  {
    "namespace": "rms",
    "key": "familia",
    "type": "single_line_text_field",
    "value": "Zapatos"
  },
  {
    "namespace": "rms", 
    "key": "categoria",
    "type": "single_line_text_field",
    "value": "Tenis"
  },
  {
    "namespace": "rms",
    "key": "talla",
    "type": "single_line_text_field", 
    "value": "23.5"
  },
  {
    "namespace": "rms",
    "key": "talla_original",
    "type": "single_line_text_field",
    "value": "23½"
  },
  {
    "namespace": "rms",
    "key": "product_attributes",
    "type": "json",
    "value": {
      "familia": "Zapatos",
      "categoria": "Tenis", 
      "talla": "23.5",
      "color": "Negro",
      "ccod": "TEN001",
      "price": 129.99
    }
  }
]
```

## Normalización de Tallas

### Conversiones Automáticas

- `23½` → `23.5`
- `24¼` → `24.25`
- `25¾` → `25.75`
- `26⅓` → `26.33`
- `27⅔` → `27.67`

### Casos Especiales
- Tallas alfanuméricas (M, L, XL) se mantienen sin cambios
- Tallas vacías o "n/d" se manejan apropiadamente
- Se preserva la talla original en metafield separado cuando hay cambios

## Búsqueda Inteligente de Taxonomías

### Sistema de Puntuación
1. **Prioridad de términos**: Términos anteriores en la lista tienen mayor peso
2. **Coincidencia exacta**: Bonificación por coincidencia exacta en nombre (50 puntos)
3. **Coincidencia parcial**: Bonificación por coincidencia parcial (25 puntos)
4. **Coincidencia en nombre completo**: Bonificación menor (15 puntos)

### Ejemplo de Búsqueda
Para "Tenis" se busca:
1. "Athletic Shoes" (prioridad alta)
2. "Sneakers" (prioridad media) 
3. "Sports Shoes" (prioridad baja)

## Integración con Sincronización Existente

### Uso en RMSToShopifySync

```python
# Reemplazar el mapper existente
from app.services.enhanced_data_mapper import EnhancedDataMapper

# En el servicio de sincronización
enhanced_mapper = EnhancedDataMapper(self.shopify_client)
await enhanced_mapper.initialize()

# Mapear producto
product_data = await enhanced_mapper.map_rms_item_to_shopify_product(rms_item)
```

### Validación Previa

```python
# Validar antes de sincronizar
validation = await enhanced_mapper.validate_product_mapping(rms_item)
if validation['valid']:
    # Proceder con sincronización
    pass
else:
    # Manejar errores
    logger.error(f"Validation errors: {validation['errors']}")
```

## Ventajas del Sistema Mejorado

### 1. **Mapeo Comprehensivo**
- Cubre todas las 22 categorías RMS identificadas
- Mapeo específico para cada familia de productos
- Fallbacks inteligentes cuando no hay mapeo específico

### 2. **Estructura de Datos Rica**
- Metafields estructurados para búsqueda avanzada
- Preservación de datos originales RMS
- JSON estructurado para consultas complejas

### 3. **Eficiencia**
- Operaciones bulk para metafields (hasta 25 simultáneos)
- Cache de taxonomías resueltas
- Búsqueda inteligente con puntuación

### 4. **Mantenibilidad**
- Configuración centralizada en `taxonomy_mapping.py`
- Sistema de validación integrado
- Logging detallado para debugging

### 5. **Flexibilidad**
- Fácil adición de nuevas categorías
- Sistema de búsqueda configurable
- Soporte para múltiples estrategias de mapeo

## Configuración y Uso

### 1. Inicialización

```python
from app.services.enhanced_data_mapper import EnhancedDataMapper
from app.db.shopify_graphql_client import ShopifyGraphQLClient

client = ShopifyGraphQLClient()
mapper = EnhancedDataMapper(client)
await mapper.initialize()  # Crea definiciones de metafields
```

### 2. Mapeo de Producto

```python
product_data = await mapper.map_rms_item_to_shopify_product(rms_item)
```

### 3. Validación

```python
validation = await mapper.validate_product_mapping(rms_item)
```

### 4. Estadísticas

```python
stats = mapper.get_mapping_statistics()
```

## Pruebas Realizadas

### Test del Sistema Completo ✅

- **Normalización de tallas**: Funciona correctamente
- **Mapeo de taxonomías**: Mapeos implementados para todas las categorías
- **Creación de metafields**: 7 metafields generados por producto
- **Conexión Shopify**: Establecida exitosamente
- **Validación**: Sistema de validación operativo
- **Type checking**: Sin errores de tipos

### Resultados de Prueba

```
✅ Size normalization: 23½ → 23.5
✅ Taxonomy mapping: Zapatos > Tenis → Athletic Footwear
✅ Metafields creation: 7 metafields per product
✅ Shopify connection: Established
✅ Validation system: Working
✅ Type checking: 0 errors
```

## Próximos Pasos

1. **Integración completa** con el servicio de sincronización existente
2. **Pruebas con datos reales** de RMS
3. **Optimización** del cache de taxonomías
4. **Monitoreo** de performance en producción
5. **Documentación** de APIs para el equipo

## Soporte y Mantenimiento

### Agregar Nueva Categoría

1. Editar `CATEGORIA_TO_TAXONOMY_MAPPING` en `taxonomy_mapping.py`
2. Agregar términos de búsqueda apropiados
3. Probar con el sistema de validación

### Modificar Metafields

1. Actualizar `METAFIELD_DEFINITIONS` en `taxonomy_mapping.py`
2. Ejecutar inicialización para crear nuevas definiciones
3. Actualizar lógica de generación en `create_metafields()`

Este sistema proporciona una base sólida y escalable para el mapeo de datos RMS a Shopify, respetando las taxonomías estándar y creando una estructura de metafields rica para búsqueda y filtrado avanzado.