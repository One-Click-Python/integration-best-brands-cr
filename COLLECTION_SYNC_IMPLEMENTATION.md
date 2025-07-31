# 🏷️ Implementación de Sincronización de Colecciones RMS → Shopify

## 📋 Resumen

Se ha implementado un sistema automatizado que crea colecciones en Shopify basadas en las categorías y familias de productos de RMS, y asigna automáticamente los productos a las colecciones correspondientes durante la sincronización.

## 🎯 Características Principales

### 1. **Creación Automática de Colecciones**
- Las colecciones se crean automáticamente basadas en:
  - **Categorías RMS** (ej: "Tenis", "Botas", "Sandalias")
  - **Familias RMS** (ej: "Zapatos", "Accesorios")
  - **Categorías Extendidas** (ej: "Calzado > Zapatos > Tenis")

### 2. **Asignación Inteligente de Productos**
- Los productos se asignan automáticamente a las colecciones durante:
  - Creación de nuevos productos
  - Actualización de productos existentes
- Un producto puede pertenecer a múltiples colecciones (categoría + familia)

### 3. **Normalización de Nombres**
- Los nombres se normalizan para evitar duplicados:
  - Conversión a minúsculas
  - Eliminación de acentos
  - Creación de handles válidos para Shopify

### 4. **Cache y Optimización**
- Las colecciones existentes se cargan en cache al inicio
- Búsqueda eficiente por nombre normalizado y handle
- Minimización de llamadas a la API de Shopify

## 🔧 Componentes Implementados

### 1. **CollectionManager** (`app/services/collection_manager.py`)
Servicio principal que gestiona las colecciones:

```python
class CollectionManager:
    async def ensure_collection_exists(categoria, familia, extended_category)
    async def add_product_to_collections(product_id, categoria, familia)
    async def sync_product_collections(product_id, current_collections, ...)
```

### 2. **Mutations GraphQL** (`app/db/queries/collection_queries.py`)
- `COLLECTION_ADD_PRODUCTS_MUTATION`: Agrega productos a colecciones
- `COLLECTION_REMOVE_PRODUCTS_MUTATION`: Remueve productos de colecciones

### 3. **Métodos en ShopifyGraphQLClient**
- `add_products_to_collection()`: Agrega productos a una colección
- `remove_products_from_collection()`: Remueve productos de una colección

### 4. **Integración en RMSToShopifySync**
El servicio de sincronización ahora:
- Inicializa el CollectionManager
- Extrae categorías de los metafields del producto
- Llama al CollectionManager después de crear/actualizar productos

## 📊 Flujo de Trabajo

1. **Durante la Inicialización:**
   ```
   RMSToShopifySync → CollectionManager → Carga colecciones existentes
   ```

2. **Durante la Sincronización de Productos:**
   ```
   Producto RMS → Extraer categoría/familia → Crear/Actualizar en Shopify
                                          ↓
                                   CollectionManager
                                          ↓
                          ¿Existe colección? → No → Crear colección
                                   ↓ Sí
                          Agregar producto a colección
   ```

3. **Prioridad de Nombres de Colección:**
   - 1° Categoría específica (ej: "Tenis")
   - 2° Familia si no hay categoría (ej: "Zapatos")
   - 3° Última parte de categoría extendida

## 🚀 Uso

### Sincronización Normal
```bash
# La sincronización normal ahora crea colecciones automáticamente
python -m app.main
```

### Script de Prueba
```bash
# Probar la funcionalidad de colecciones
python test_collection_sync.py
```

### Ejemplo de Código
```python
# El proceso es automático, pero se puede usar manualmente:
from app.services.collection_manager import CollectionManager

collection_manager = CollectionManager(shopify_client)
await collection_manager.initialize()

# Asegurar que existe una colección
collection_id = await collection_manager.ensure_collection_exists(
    categoria="Tenis",
    familia="Zapatos",
    extended_category="Calzado > Zapatos > Tenis"
)

# Agregar producto a colecciones
collections = await collection_manager.add_product_to_collections(
    product_id="gid://shopify/Product/123",
    categoria="Tenis",
    familia="Zapatos"
)
```

## 📝 Metafields de Colección

Las colecciones creadas incluyen metafields RMS:
```json
{
  "namespace": "rms",
  "key": "source_type",
  "value": "categoria",  // o "familia" o "extended"
  "type": "single_line_text_field"
}
```

## 🔍 Logs y Monitoreo

El sistema registra:
- ✅ Creación exitosa de colecciones
- ✅ Productos agregados a colecciones
- ⚠️ Advertencias cuando no se puede determinar categoría
- ❌ Errores en operaciones de colección

Ejemplo de logs:
```
INFO - Creando nueva colección: 'Tenis' (tipo: categoria)
INFO - ✅ Colección creada exitosamente: 'Tenis' (ID: gid://shopify/Collection/123, handle: tenis)
INFO - ✅ Producto gid://shopify/Product/456 agregado a colección de categoría 'Tenis'
INFO - ✅ Product added to 2 collections
```

## ⚙️ Configuración

No se requiere configuración adicional. El sistema usa:
- Las credenciales existentes de Shopify
- La configuración de sincronización actual
- Los metafields de productos para extraer categorías

## 🎯 Beneficios

1. **Organización Automática**: Los productos se organizan automáticamente en colecciones
2. **Navegación Mejorada**: Los clientes pueden navegar por categoría/familia
3. **SEO Mejorado**: URLs de colección para cada categoría
4. **Gestión Simplificada**: No es necesario crear colecciones manualmente
5. **Consistencia**: Nombres normalizados y estructura consistente

## 📌 Notas Importantes

1. Las colecciones se crean solo cuando hay productos con esa categoría
2. Un producto puede pertenecer a múltiples colecciones
3. Las colecciones manuales existentes no se modifican
4. El sistema respeta los límites de API de Shopify
5. Los nombres de colección se normalizan (sin acentos, minúsculas)

## 🔄 Próximos Pasos Sugeridos

1. **Imágenes de Colección**: Agregar imágenes representativas a cada colección
2. **Descripciones SEO**: Mejorar las descripciones para SEO
3. **Reglas Automáticas**: Crear smart collections con reglas automáticas
4. **Jerarquía**: Implementar colecciones padre/hijo
5. **Sincronización Inversa**: Sincronizar cambios de colección de Shopify a RMS