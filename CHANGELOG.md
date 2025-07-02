# Changelog

Todas las modificaciones notables a este proyecto serán documentadas en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Sin versionar] - 2025-07-02

### 🚀 Conector de Captura de Pedidos Shopify → RMS

#### Agregado - Sistema de Inserción en Tablas ORDER y ORDERENTRY
- ✨ **Conector completo** para captura de pedidos formalizados en Shopify
- 🗄️ **Inserción directa en tablas RMS**: ORDER y ORDERENTRY
- 📦 **Procesamiento de datos de cabecera**: cliente, fecha, total, impuestos
- 📋 **Procesamiento de datos de detalle**: productos, cantidades, precios unitarios
- ✅ **Validación de existencias** antes de procesar pedidos
- 🔄 **Gestión de excepciones** con manejo robusto de errores
- 📊 **Manejo de estados del pedido** durante todo el ciclo de vida

#### Implementación del Conector RMS
- 🛒 **Clase ShopifyOrderClient** (`app/db/shopify_order_client.py`) para obtención de pedidos Shopify
- 🔄 **Servicio ShopifyToRMSSync** (`app/services/shopify_to_rms.py`) para procesamiento y mapeo
- 📝 **RMSHandler mejorado** con métodos `create_order()` y `create_order_entry()`
- 🗃️ **Schemas Pydantic** para validación estricta de datos ORDER/ORDERENTRY

#### Datos de Cabecera ORDER Implementados
- `StoreID` - ID de tienda RMS configurado
- `Time` - Fecha y hora del pedido Shopify
- `CustomerID` - Cliente mapeado o creado en RMS
- `Total` - Total del pedido incluyendo impuestos
- `Tax` - Impuestos calculados según configuración
- `Comment` - ID de Shopify para tracking
- `ShippingNotes` - Dirección de envío

#### Datos de Detalle ORDERENTRY Implementados  
- `OrderID` - Referencia a tabla ORDER
- `ItemID` - ID del producto en RMS (mapeado desde SKU)
- `Price` - Precio unitario del producto
- `QuantityOnOrder` - Cantidad ordenada
- `Description` - Descripción del producto
- `Cost` - Costo del producto (si disponible)

#### Validaciones Implementadas
- ✅ **Validación de existencias** en View_Items antes de procesar
- ✅ **Verificación de estado financiero** (solo pedidos pagados)
- ✅ **Mapeo SKU → ItemID** con validación de productos existentes
- ✅ **Control de duplicados** mediante verificación de comentarios
- ✅ **Gestión de excepciones** con rollback en caso de error

#### Endpoints API del Conector
- `POST /api/v1/sync/shopify-to-rms` - Sincronizar pedidos específicos a tablas RMS
- `GET /api/v1/webhooks/orders/paid` - Webhook para captura automática de pedidos pagados

### Técnico - Arquitectura del Conector
- 🏗️ **Transacciones SQL** para integridad ORDER/ORDERENTRY
- 📊 **Queries optimizadas** para inserción en tablas RMS
- 🔄 **Sistema de reintentos** para manejo de conexión SQL Server
- 📈 **Logging detallado** de inserciones en base de datos

### Verificado - Integración de Base de Datos
- ✅ **Conexión RMS establecida**: 556,649 productos en View_Items
- ✅ **Test de endpoints**: `/database-test` respondiendo en ~577ms
- ✅ **Pool de conexiones**: 10 conexiones configuradas correctamente
- ✅ **Consultas optimizadas**: Soporte para filtros y paginación
- ✅ **Handler RMS mejorado**: Parámetro `include_zero_stock` agregado

## [Sin versionar] - 2025-06-25

### 🚀 Sistema de Taxonomías y Metafields Mejorado

#### Agregado - Sistema Avanzado de Mapeo
- ✨ **Sistema completo de taxonomías** para mapeo RMS → Shopify Standard Product Taxonomy
- 🗺️ **Mapeo comprehensivo** de 5 familias RMS y 22 categorías a taxonomías Shopify
- 📊 **Metafields estructurados** para talla, color y atributos RMS con tipos específicos
- 🔍 **Búsqueda inteligente** de taxonomías con algoritmo de puntuación multi-término
- ⚡ **Operaciones bulk** de metafields (hasta 25 simultáneos) para eficiencia
- 🔧 **Sistema de validación** integrado para mapeos antes de sincronización

#### Normalización Avanzada de Datos
- 🔢 **Normalización automática de tallas**: `23½` → `23.5`, `24¼` → `24.25`
- 📝 **Preservación de datos originales** en metafields separados cuando hay cambios
- 🏷️ **Generación inteligente de tags** basados en datos RMS y taxonomías
- 📋 **Opciones de producto** automáticas para talla y color

#### Nuevos Componentes Implementados
- 🏗️ **RMSTaxonomyMapper** (`app/core/taxonomy_mapping.py`) - Sistema de mapeo centralizado
- 🔄 **EnhancedDataMapper** (`app/services/enhanced_data_mapper.py`) - Servicio avanzado de mapeo
- 📡 **Consultas GraphQL mejoradas** - Soporte completo para taxonomías y metafields 2024-04
- 🌐 **Cliente GraphQL extendido** - Funciones avanzadas de taxonomía

#### Metafields Estructurados Implementados
```
rms.familia          - Familia del producto (Zapatos, Ropa, Accesorios)
rms.categoria        - Categoría específica (Tenis, Botas, Vestir)
rms.talla           - Talla normalizada (23.5, M, L)
rms.talla_original  - Talla original RMS (23½, si difiere)
rms.color           - Color del producto
rms.extended_category - Categoría jerárquica (Zapatos > Tenis)
rms.product_attributes - JSON con todos los atributos RMS
```

#### Mapeos de Taxonomía Implementados
- **Zapatos** → Footwear (Tenis→Athletic Shoes, Botas→Boots, Sandalias→Sandals)
- **Ropa** → Apparel (MUJER-VEST→Women's Dresses, NIÑO-CASU→Boys Casual)
- **Accesorios** → Accessories (Bolsos→Handbags, ACCESORIOS CALZADO→Shoe Care)
- **Miscelaneos** → Miscellaneous con fallbacks inteligentes

### Cambiado - Sincronización Mejorada
- 🔄 Sincronización de productos ahora excluye productos sin stock por defecto (`include_zero_stock: false`)
- ✨ Mejorada lógica de selección de ubicación principal de Shopify con múltiples estrategias
- 📊 Agregado logging detallado para ubicaciones de inventario y taxonomías
- 🏷️ Productos ahora se categorizan usando Standard Product Taxonomy de Shopify
- 📝 **Campos title y description ahora son iguales** - solo contienen el título del producto sin HTML

### Arreglado
- 🐛 Corregido comportamiento de sincronización que actualizaba productos sin stock a Shopify
- 🔧 Mejorado `get_primary_location_id` con lógica más robusta para detectar ubicación principal
- 🌐 Corregidas consultas GraphQL de taxonomía para compatibilidad con API 2024-04
- 🔧 **Corregido error de GraphQL metafield definitions**: Campo `metafieldDefinition` → `createdDefinition`
- 🔧 **Corregido campo inexistente**: Removido `supportsVariants` de consultas GraphQL tipo MetafieldDefinition

### Técnico - Arquitectura Mejorada
- 🏗️ **Cache de taxonomías** para optimización de rendimiento
- 📋 Modelo `SyncRequest` extendido con campo `include_zero_stock`
- 🔄 Propagación de parámetros a través de toda la cadena de sincronización
- 📡 Nuevas mutaciones GraphQL: `METAFIELDS_SET_MUTATION`, `CREATE_METAFIELD_DEFINITION_MUTATION`
- 🔍 Funciones avanzadas: `find_best_taxonomy_match()`, `create_metafields_bulk()`

### Verificado - Pruebas Completas
- ✅ **Normalización de tallas**: 8 casos de prueba exitosos
- ✅ **Mapeo de taxonomías**: 22 categorías RMS mapeadas correctamente
- ✅ **Creación de metafields**: 7 metafields por producto generados
- ✅ **Conexión Shopify**: Establecida (Best Brands cr)
- ✅ **Validación de sistema**: 10 productos de prueba validados exitosamente
- ✅ **Type checking**: 0 errores en PyRight
- ✅ **Funcionalidad de filtrado**: Productos sin stock excluidos por defecto
- ✅ **GraphQL metafield definitions**: 7 definiciones creadas exitosamente en Shopify
- ✅ **Taxonomía resolutiva**: 9 taxonomías resueltas con algoritmo de puntuación
- ✅ **Mapeo completo**: 9/10 productos mapeados (1 excluido por stock=0)

### Documentación
- 📚 **Documentación completa** del sistema en `docs/enhanced_taxonomy_system.md`
- 📝 **CLAUDE.md actualizado** con información del sistema mejorado
- 🔧 **Ejemplos de uso** y guías de integración incluidas

## [0.1.0] - 2025-06-15

### Agregado - Implementación Inicial
- ✨ **Implementación inicial** del sistema de integración RMS-Shopify
- 🔄 **Sincronización bidireccional básica** entre RMS y Shopify
- 📡 **Sistema de webhooks** para captura de eventos Shopify
- 📊 **Logging estructurado** y sistema de monitoreo
- 🐛 **Manejo robusto de errores** con reintentos automáticos
- 🏗️ **Arquitectura modular** con servicios independientes
- ⚙️ **Configuración centralizada** con variables de entorno
- 🔐 **Sistema de autenticación** para APIs
- 📈 **Métricas y KPIs** de sincronización
- 🐳 **Soporte para Docker** y contenedores

### Configuración Inicial
- 🛠️ **FastAPI** como framework web principal
- 🗄️ **SQLAlchemy** para manejo de base de datos SQL Server
- 🔄 **Sistema de tareas asíncronas** con Celery + Redis
- 📋 **Validación de datos** con Pydantic
- 🧪 **Suite de testing** con pytest
- 📚 **Documentación automática** con Swagger/OpenAPI

## [Sin versionar] - 2025-06-24

### Arreglado
- 🐛 Mejorado el manejo de sesiones HTTP de aiohttp para evitar warnings de sesiones no cerradas
- 🔧 Agregado logging detallado para debugging de inicialización de sesiones Shopify  
- 🔄 Mejorado el método close() del cliente GraphQL para verificar estado de sesión antes de cerrar

## [Sin versionar] - 2025-06-23

### Agregado
- ✨ Sistema de pruebas completo para conexiones de base de datos y Shopify
- 📋 Scripts de testing automatizado (`test_connection_simple.py`, `test_db_sync.py`)
- 🔧 Archivo de configuración de proyecto CLAUDE.md con comandos de desarrollo
- 📊 Verificación de health check para todos los servicios
- 🔍 Validación de conectividad con 556,649 productos en RMS View_Items
- ✅ Confirmación de acceso a 113,330 órdenes en tabla RMS Order

### Cambiado
- 🔄 Puerto de aplicación cambiado de 8000 a 8080 en toda la configuración
- 🛠️ Driver ODBC actualizado de "Driver 18" a "Driver 17 for SQL Server"
- 📝 Documentación actualizada con nuevos puertos en README.md y CLAUDE.md
- ⚙️ Configuración por defecto de puerto en config.py actualizada

### Arreglado
- 🐛 Error de binding de parámetros en verificación de tabla Order de RMS
- 🔧 Problema de duplicación de query SQL en rms_handler.py líneas 82-88
- 📡 Configuración de driver ODBC compatible con sistema macOS
- 🔗 Enlaces de documentación API actualizados a puerto 8080

### Verificado
- ✅ Conexión exitosa a base de datos RMS (latencia: ~1.6s)
- ✅ Conexión exitosa a Shopify API (latencia: ~1.3s) 
- ✅ Autenticación con token de acceso Shopify funcional
- ✅ Endpoints de health check operativos
- ✅ Endpoints de sincronización RMS-to-Shopify respondiendo correctamente
- ✅ Sistema de logging y métricas funcionando

### Técnico
- 🏗️ Arquitectura de conexión singleton para base de datos implementada
- 📊 Pool de conexiones SQL Server configurado (max: 10 conexiones)
- 🔄 Sistema de retry handler para APIs externas operativo
- 🎯 Background tasks para sincronización asíncrona configurados
- 📈 Sistema de métricas y monitoreo inicializado

## [0.1.0] - 2025-06-15

### Agregado
- ✨ Implementación inicial del sistema de integración RMS-Shopify
- 🔄 Sincronización bidireccional básica entre RMS y Shopify
- 📡 Sistema de webhooks para captura de eventos Shopify
- 📊 Sistema completo de logging estructurado y monitoreo
- 🐛 Manejo robusto de errores con reintentos automáticos
- 🏗️ Arquitectura modular con servicios independientes
- ⚙️ Configuración centralizada con variables de entorno
- 🔐 Sistema de autenticación para APIs
- 📈 Métricas y KPIs de sincronización
- 🐳 Soporte para Docker y contenedores

### Configuración Inicial
- 🛠️ FastAPI como framework web principal
- 🗄️ SQLAlchemy para manejo de base de datos SQL Server
- 🔄 Sistema de tareas asíncronas con Celery + Redis
- 📋 Validación de datos con Pydantic
- 🧪 Suite de testing con pytest
- 📚 Documentación automática con Swagger/OpenAPI

---

**Leyenda de Símbolos:**
- ✨ Nuevas características
- 🔄 Cambios en funcionalidad existente  
- 🐛 Corrección de errores
- 🔧 Mejoras técnicas
- 📊 Métricas y monitoreo
- 🛠️ Herramientas y configuración
- 📝 Documentación
- 🔐 Seguridad
- 🧪 Testing
- 🐳 DevOps
- ✅ Verificaciones
- 🏗️ Arquitectura