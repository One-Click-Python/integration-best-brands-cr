# 🔄 Flujo de Sincronización RMS → Shopify

Este documento describe el flujo completo del proceso de sincronización desde Microsoft Retail Management System (RMS) hacia Shopify, mostrando todos los archivos involucrados y las decisiones clave del sistema.

## 📊 Diagrama de Flujo Principal

```mermaid
flowchart TD
    %% Entry Points
    API[📡 API Endpoint<br/>"/api/v1/sync/rms-to-shopify"]
    SCHEDULER[⏰ Scheduled Sync<br/>Auto-sync cada 5 min]
    
    %% Initialization
    INIT[🚀 Initialize<br/>RMSToShopifySync]
    
    %% Step A - Data Extraction
    A[📂 STEP A: Extract RMS Data<br/>_extract_rms_products]
    A1[🔍 Query RMS Database<br/>View_Items + ItemDynamic]
    A2[🔄 Map RMS → Shopify<br/>DataMapper.map_product_to_shopify]
    A3[📦 Group by CCOD<br/>Multiple variants per product]
    
    %% Get existing products
    EXISTING[💎 Get Existing Shopify Products<br/>_get_existing_shopify_products]
    
    %% Decision: New or Update
    DECISION{🤔 Product Exists?}
    
    %% Force Update Decision
    FORCE{⚡ Force Update?}
    
    %% New Product Flow
    NEW_FLOW[🆕 NEW PRODUCT FLOW]
    
    %% Update Product Flow  
    UPDATE_FLOW[🔄 UPDATE PRODUCT FLOW]
    
    %% Skip Flow
    SKIP[⏭️ Skip Product<br/>No changes needed]
    
    %% Step B - Create/Update Product
    B_NEW[📝 STEP B: Create Base Product<br/>MultipleVariantsCreator.create_product_with_variants]
    B_UPDATE[📝 STEP B: Update Base Product<br/>MultipleVariantsCreator.update_product_with_variants]
    
    %% Step C - Variants
    C[⚙️ STEP C: Create/Update Variants<br/>VariantManager.sync_product_variants]
    C1[🔧 Prepare Variant Data<br/>DataPreparator.prepare_variant_data]
    C2[🆕 Create New Variants<br/>productVariantsBulkCreate]
    C3[🔄 Update Existing Variants<br/>productVariantsBulkUpdate]
    
    %% Step D - Inventory
    D[📦 STEP D: Update Inventory<br/>InventoryManager.force_inventory_update]
    D1[🎯 Activate Tracking<br/>activate_inventory_tracking_well]
    D2[📊 Set Quantities<br/>INVENTORY_SET_QUANTITIES_MUTATION]
    
    %% Step E - Metafields
    E[🏷️ STEP E: Create Metafields<br/>MetafieldsManager.create_metafields]
    E1[📋 RMS Categories<br/>familia, categoria, extended_category]
    E2[🔗 Product Attributes<br/>size, color, sku mapping]
    
    %% Step F-G - Sale Price Check
    F[💰 STEP F: Check Sale Price<br/>Verify comparative prices]
    G{💸 Has Sale Price?}
    
    %% Step H - Discounts (Optional)
    H[🎯 STEP H: Create Auto Discount<br/>If sale price exists]
    
    %% Step I - Collections
    I[📚 STEP I: Add to Collections<br/>CollectionManager.add_product_to_collections]
    
    %% Step J - Complete
    J[✅ STEP J: Product Complete<br/>Log success + stats]
    
    %% Batch Processing
    BATCH[📦 Process in Batches<br/>Rate limiting + Error handling]
    
    %% Final Report
    REPORT[📊 Generate Sync Report<br/>Success/Error statistics]
    
    %% Error Handling
    ERROR[❌ Error Handling<br/>ErrorAggregator + Logging]
    
    %% Flow connections
    API --> INIT
    SCHEDULER --> INIT
    INIT --> A
    
    A --> A1
    A1 --> A2
    A2 --> A3
    A3 --> EXISTING
    
    EXISTING --> BATCH
    BATCH --> DECISION
    
    DECISION -->|No| NEW_FLOW
    DECISION -->|Yes| FORCE
    
    FORCE -->|Yes| UPDATE_FLOW
    FORCE -->|No| SKIP
    
    NEW_FLOW --> B_NEW
    UPDATE_FLOW --> B_UPDATE
    
    B_NEW --> C
    B_UPDATE --> C
    
    C --> C1
    C1 --> C2
    C1 --> C3
    C2 --> D
    C3 --> D
    
    D --> D1
    D1 --> D2
    D2 --> E
    
    E --> E1
    E1 --> E2
    E2 --> F
    
    F --> G
    G -->|Yes| H
    G -->|No| I
    H --> I
    
    I --> J
    SKIP --> J
    J --> REPORT
    
    %% Error paths
    A1 -.->|Error| ERROR
    A2 -.->|Error| ERROR
    C2 -.->|Error| ERROR
    D1 -.->|Error| ERROR
    E1 -.->|Error| ERROR
    ERROR --> REPORT
    
    %% Styling
    classDef stepClass fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef decisionClass fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef errorClass fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef successClass fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A,B_NEW,B_UPDATE,C,D,E,F,H,I stepClass
    class DECISION,FORCE,G decisionClass
    class ERROR errorClass
    class J,REPORT successClass
```

## 📁 Mapeo de Archivos y Responsabilidades

| Paso | Responsabilidad | Archivo Principal | Módulos Secundarios |
|------|----------------|-------------------|-------------------|
| **Entry Point** | API Endpoints & Scheduling | `app/api/v1/endpoints/sync.py` | `app/services/sync_manager.py` |
| **A - Extract** | Extracción de datos RMS | `app/services/rms_to_shopify.py` | `app/db/rms_handler.py` |
| **A - Map** | Mapeo RMS → Shopify | `app/services/data_mapper.py` | `app/services/variant_mapper.py` |
| **B - Product** | Crear/Actualizar producto base | `app/services/multiple_variants_creator/main.py` | `app/services/multiple_variants_creator/data_preparator.py` |
| **C - Variants** | Gestión de variantes | `app/services/multiple_variants_creator/variant_manager.py` | `app/db/shopify_graphql_client.py` |
| **D - Inventory** | Gestión de inventario | `app/services/multiple_variants_creator/inventory_manager.py` | `app/db/shopify_clients/inventory_client.py` |
| **E - Metafields** | Gestión de metafields | `app/services/multiple_variants_creator/metafields_manager.py` | `app/db/queries/metafields.py` |
| **I - Collections** | Gestión de colecciones | `app/services/collection_manager.py` | `app/db/queries/collections.py` |
| **Error Handling** | Manejo de errores | `app/utils/error_handler.py` | `app/core/logging_config.py` |

## 🔀 Diferencias: Producto Nuevo vs Actualización

### 🆕 Flujo para Producto NUEVO
```
Entry → A → EXISTING → DECISION(No) → NEW_FLOW → B_NEW → C → D → E → F → G → H/I → J
```

**Características:**
- ✅ **Crear producto base** con datos mínimos (título, handle, descripción)
- ✅ **Crear todas las variantes** usando `productVariantsBulkCreate`
- ✅ **Activar tracking de inventario** para todas las variantes
- ✅ **Establecer cantidades iniciales** con `INVENTORY_SET_QUANTITIES_MUTATION`
- ✅ **Crear todos los metafields** con información de RMS
- ✅ **Agregar a colecciones** basadas en categorías
- ✅ **Log como 'create'** en estadísticas

### 🔄 Flujo para Producto EXISTENTE (Force Update)
```
Entry → A → EXISTING → DECISION(Yes) → FORCE(Yes) → UPDATE_FLOW → B_UPDATE → C → D → E → F → G → H/I → J
```

**Características:**
- 🔄 **Actualizar producto base** con nuevos datos
- 🔄 **Sincronizar variantes**: crear nuevas + actualizar existentes
- 🔄 **Actualizar inventario** solo para variantes con cambios
- 🔄 **Actualizar metafields** existentes o crear nuevos
- 🔄 **Sincronizar colecciones** (agregar/remover según categorías)
- 🔄 **Log como 'update'** en estadísticas

### ⏭️ Flujo para Producto EXISTENTE (Skip)
```
Entry → A → EXISTING → DECISION(Yes) → FORCE(No) → SKIP → J
```

**Características:**
- ⏭️ **No modificar** el producto existente
- ⏭️ **Comparación inteligente** (pendiente implementar)
- ⏭️ **Log como 'skipped'** en estadísticas

## 🎯 Puntos de Decisión Clave

### 1. **Product Exists Check** (`DECISION`)
**Archivo:** `app/services/rms_to_shopify.py:482`
```python
existing_product = shopify_products["by_handle"].get(shopify_input.handle)
if existing_product:
    # Update flow
else:
    # Create flow
```

### 2. **Force Update Check** (`FORCE`)
**Archivo:** `app/services/rms_to_shopify.py:486`
```python
if force_update:
    # Execute full update flow
else:
    # Skip (future: intelligent comparison)
```

### 3. **Sale Price Check** (`G`)
**Archivo:** `app/services/multiple_variants_creator/main.py` (STEPS F-G)
```python
# F. Verificar precio de oferta
# G. ¿Tiene Sale Price?
if has_sale_price:
    # H. Crear descuento automático
else:
    # Continue to collections
```

## 🛠️ Configuración y Parámetros

### Parámetros de Entrada
| Parámetro | Descripción | Default | Archivo Config |
|-----------|-------------|---------|----------------|
| `force_update` | Forzar actualización de productos existentes | `false` | N/A |
| `batch_size` | Tamaño del lote para procesamiento | `100` | `SYNC_BATCH_SIZE` |
| `filter_categories` | Filtrar por categorías específicas | `null` | N/A |
| `include_zero_stock` | Incluir productos sin stock | `false` | N/A |
| `cod_product` | CCOD específico a sincronizar | `null` | N/A |

### Rate Limiting
**Archivo:** `app/services/rms_to_shopify.py:400-411`
```python
if batch_size > 2:
    sleep_time = 5  # 5 segundos entre lotes grandes
else:
    sleep_time = 1  # 1 segundo entre lotes pequeños
```

## 📊 Estadísticas y Monitoreo

### Métricas Tracked
```python
{
    "total_processed": 0,    # Total productos procesados
    "created": 0,           # Productos creados
    "updated": 0,           # Productos actualizados  
    "skipped": 0,           # Productos omitidos
    "errors": 0,            # Errores ocurridos
    "inventory_updated": 0,  # Inventarios actualizados
    "inventory_failed": 0    # Fallas de inventario
}
```

### Logging Context
**Archivo:** `app/core/logging_config.py`
```python
with LogContext(sync_id=self.sync_id, operation="sync_products"):
    # Todas las operaciones incluyen contexto de sync
```

## 🔄 Integración con Sistema Automático

### Trigger Automático
**Archivo:** `app/core/scheduler.py`
- **Frecuencia:** Cada 5 minutos (configurable con `SYNC_INTERVAL_MINUTES`)
- **Detection:** Basado en `Item.LastUpdated` en RMS
- **Batch Size:** Automático basado en carga

### Trigger Manual
**Endpoint:** `POST /api/v1/sync/rms-to-shopify`
- **Parámetros:** Todos configurables vía API
- **Locks:** Previene múltiples sincronizaciones simultáneas
- **Background Tasks:** Ejecución no bloqueante

## 🚨 Manejo de Errores

### Error Aggregator
**Archivo:** `app/utils/error_handler.py`
```python
self.error_aggregator.add_error(
    e,
    {"ccod": ccod, "title": shopify_input.title}
)
```

### Recovery Strategies
1. **Individual Product Errors:** Continue with next product
2. **Batch Errors:** Retry individual products
3. **Connection Errors:** Exponential backoff
4. **Rate Limit Errors:** Automatic throttling

## 📈 Optimizaciones Implementadas

### 1. **Batch Processing**
- Procesa múltiples productos en paralelo
- Rate limiting inteligente basado en tamaño de lote

### 2. **Bulk Operations**
- `productVariantsBulkCreate` para múltiples variantes
- `INVENTORY_SET_QUANTITIES_MUTATION` para inventario
- `METAFIELDS_SET_MUTATION` para metafields

### 3. **Connection Pooling**
- Cliente HTTP reutilizable
- Pool de conexiones a base de datos

### 4. **Smart Querying**
- Índices por handle y SKU
- Queries optimizadas con joins

---

*Este diagrama representa el estado actual del sistema. Para contribuir o reportar inconsistencias, revisar los archivos mencionados en cada sección.*