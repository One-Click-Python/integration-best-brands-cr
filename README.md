# RMS-Shopify Integration

Sistema de integración bidireccional entre Microsoft Retail Management System (RMS) y Shopify para automatizar la sincronización de productos, inventarios, precios y pedidos entre venta física y e-commerce con **detección automática de cambios en tiempo real**.

## 🎯 Características Principales

- **🤖 Motor de Sincronización Automática**: Detección de cambios usando `Item.LastUpdated` cada 5 minutos
- **🔄 Sincronización Bidireccional**: RMS ↔ Shopify con taxonomías estándar y inicio automático
- **📊 Sistema de Taxonomías Avanzado**: Mapeo inteligente a Standard Product Taxonomy de Shopify
- **🏷️ Metafields Estructurados**: Talla, color y atributos RMS preservados como metafields
- **⚡ Normalización Automática**: Tallas (`23½` → `23.5`) y datos RMS optimizados
- **🏗️ Arquitectura de Microservicios**: Modular y escalable con auto-recovery
- **📡 API REST**: Control manual y programado con filtros avanzados
- **🔗 Webhooks**: Captura en tiempo real de eventos Shopify con soporte para pedidos sin cliente
- **📈 Sistema de Alertas**: Notificaciones de errores y estado con métricas en tiempo real
- **📝 Logging Estructurado**: Auditoría completa de operaciones con estadísticas detalladas
- **🔒 Mecanismo de Bloqueo**: Prevención de operaciones concurrentes para garantizar consistencia
- **🛒 Soporte para Pedidos de Invitados**: Procesamiento flexible de pedidos sin registro de cliente
- **📊 Dashboard de Métricas**: Visualización en tiempo real del rendimiento del sistema
- **🐳 Docker Ready**: Despliegue simplificado con Docker y Docker Compose

## 🏗️ Arquitectura

### Diagrama de Arquitectura SOLID

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      API Layer (REST)                             │  │
│  │  /sync  /webhooks  /collections  /health  /metrics  /admin       │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                              │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │                   Service Layer (Orquestación)                    │  │
│  │  ┌─────────────────────┐         ┌──────────────────────────┐    │  │
│  │  │ RMS → Shopify       │         │ Shopify → RMS            │    │  │
│  │  │ • DataExtractor     │         │ • OrderValidator         │    │  │
│  │  │ • ProductProcessor  │         │ • OrderConverter         │    │  │
│  │  │ • ShopifyUpdater    │         │ • CustomerResolver       │    │  │
│  │  │ • SyncOrchestrator  │         │ • OrderOrchestrator      │    │  │
│  │  └─────────────────────┘         └──────────────────────────┘    │  │
│  │                                                                    │  │
│  │  ┌─────────────────────┐         ┌──────────────────────────┐    │  │
│  │  │ Change Detection    │         │ Checkpoint System        │    │  │
│  │  │ • ChangeDetector    │         │ • UpdateCheckpoint       │    │  │
│  │  │ • APScheduler       │         │ • ProgressCheckpoint     │    │  │
│  │  └─────────────────────┘         └──────────────────────────┘    │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                              │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │              Domain Layer (DDD - Domain Models)                   │  │
│  │  • OrderDomain  • OrderEntryDomain  • Money (Value Object)        │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                              │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │              Repository Layer (SOLID - Data Access)               │  │
│  │  ┌──────────────────┐              ┌──────────────────────────┐  │  │
│  │  │ RMS Repositories │              │ Shopify Clients          │  │  │
│  │  │ • BaseRepository │              │ • ProductClient          │  │  │
│  │  │ • ProductRepo    │              │ • InventoryClient        │  │  │
│  │  │ • OrderRepo      │              │ • CollectionClient       │  │  │
│  │  │ • CustomerRepo   │              │ • UnifiedClient (Facade) │  │  │
│  │  │ • MetadataRepo   │              │ • BaseClient (Shared)    │  │  │
│  │  └────────┬─────────┘              └───────────┬──────────────┘  │  │
│  └───────────┼────────────────────────────────────┼─────────────────┘  │
└──────────────┼────────────────────────────────────┼────────────────────┘
               │                                     │
    ┌──────────▼──────────┐              ┌─────────▼──────────┐
    │   RMS (SQL Server)  │              │   Shopify API      │
    │                     │              │                    │
    │ • Item (LastUpdated)│              │ • GraphQL          │
    │ • View_Items        │              │ • REST API         │
    │ • ItemDynamic       │              │ • Webhooks         │
    │ • Order/OrderEntry  │              │ • Metafields       │
    │ • Customer          │              │ • Collections      │
    └─────────────────────┘              └────────────────────┘
```

### Características de la Arquitectura

- **🏗️ SOLID Principles**: Repositorios especializados con responsabilidad única
- **🎨 Domain-Driven Design**: Modelos de dominio con lógica de negocio encapsulada
- **⚡ Async/Await**: Operaciones asíncronas para máxima performance
- **🔄 Checkpoint System**: Doble sistema para sync incremental y recuperación
- **🔧 Modular Clients**: Clientes Shopify especializados por responsabilidad
- **📊 Dependency Injection**: Servicios reciben dependencias (inversión de control)

## 🛠️ Stack Tecnológico

- **Python 3.13** - Lenguaje principal con soporte async/await
- **FastAPI** - Framework web asíncrono de alto rendimiento
- **SQLAlchemy 2.0** - ORM con soporte asíncrono para SQL Server
- **Pydantic v2** - Validación y serialización de datos con rendimiento mejorado
- **Redis** - Cache y gestión de bloqueos para operaciones concurrentes
- **APScheduler** - Programación de tareas con soporte de zonas horarias
- **httpx/aiohttp** - Clientes HTTP asíncronos para APIs externas
- **SQL Server** - Base de datos RMS con soporte para triggers
- **Docker** - Containerización para desarrollo y producción
- **Poetry** - Gestión moderna de dependencias
- **GraphQL** - Cliente para operaciones avanzadas en Shopify

## 🚀 Instalación

### Prerrequisitos

- Python 3.13+
- SQL Server (con acceso a RMS)
- Redis (para Celery)
- Cuenta y API de Shopify

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd rms-shopify-integration
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows
```

### 3. Instalar dependencias

```bash
poetry install
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# === CONFIGURACIÓN DE LA APLICACIÓN ===
APP_NAME=RMS-Shopify Integration
APP_VERSION=0.1.0
DEBUG=False                                  # Producción: False, Desarrollo: True
LOG_LEVEL=INFO                               # DEBUG, INFO, WARNING, ERROR, CRITICAL

# === BASE DE DATOS RMS (SQL SERVER) ===
RMS_DB_HOST=localhost
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database
RMS_DB_USER=your_user
RMS_DB_PASSWORD=your_password
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server

# Configuración de Pool de Conexiones
RMS_CONNECTION_TIMEOUT=30                    # Timeout de conexión (segundos)
RMS_MAX_POOL_SIZE=10                         # Tamaño máximo del pool
RMS_POOL_RECYCLE=3600                        # Reciclar conexiones cada hora
RMS_POOL_PRE_PING=true                       # Verificar conexión antes de usar

# === SHOPIFY API ===
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token
SHOPIFY_API_VERSION=2025-04                  # Versión con soporte taxonomías
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret
SHOPIFY_RATE_LIMIT_PER_SECOND=2              # Límite de llamadas/segundo
SHOPIFY_LOCATION_ID=                         # ID de ubicación para inventario

# === 🤖 MOTOR DE SINCRONIZACIÓN AUTOMÁTICA ===
ENABLE_SCHEDULED_SYNC=true                   # Habilitar detección automática
SYNC_INTERVAL_MINUTES=5                      # Verificar cambios cada N minutos
SYNC_BATCH_SIZE=25                           # Productos por batch (25-100)
SYNC_MAX_CONCURRENT_JOBS=3                   # Jobs concurrentes (1-5)

# === 🕐 SINCRONIZACIÓN COMPLETA PROGRAMADA ===
ENABLE_FULL_SYNC_SCHEDULE=true               # Habilitar full sync programada
FULL_SYNC_HOUR=23                            # Hora del día (0-23)
FULL_SYNC_MINUTE=0                           # Minuto (0-59)
FULL_SYNC_TIMEZONE=America/Argentina/Buenos_Aires
# FULL_SYNC_DAYS=0,1,2,3,4                   # Opcional: Días específicos (0=Lun)

# === 🔄 SISTEMA DE CHECKPOINTS ===
# Update Checkpoint (Sincronización Incremental)
USE_UPDATE_CHECKPOINT=false                  # Habilitar sync incremental
CHECKPOINT_SUCCESS_THRESHOLD=0.95            # Mínimo 95% éxito para actualizar
CHECKPOINT_DEFAULT_DAYS=30                   # Días atrás si no hay checkpoint
CHECKPOINT_FILE_PATH=./checkpoint            # Directorio de checkpoints

# Progress Checkpoint (Recuperación de Fallos)
ENABLE_PROGRESS_CHECKPOINT=true              # Habilitar recuperación
CHECKPOINT_SAVE_INTERVAL=100                 # Guardar progreso cada N items
CHECKPOINT_AUTO_CLEANUP=true                 # Auto-limpiar al completar

# === 🛒 SOPORTE PARA PEDIDOS SIN CLIENTE ===
ALLOW_ORDERS_WITHOUT_CUSTOMER=true           # Permitir guest checkout
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=        # ID cliente por defecto (opcional)
REQUIRE_CUSTOMER_EMAIL=false                 # Requerir email
GUEST_CUSTOMER_NAME=Cliente Invitado         # Nombre para invitados

# === 🏷️ CATEGORÍAS Y COLLECTIONS ===
SYNC_INCLUDE_CATEGORY_TAGS=false             # Agregar tags de categoría
SYNC_ENABLE_COLLECTIONS=false                # Habilitar collections automáticas

# === 🔒 CONTROL DE CONCURRENCIA ===
ENABLE_SYNC_LOCK=true                        # Bloqueo distribuido (Redis)
SYNC_LOCK_TIMEOUT_SECONDS=1800               # 30 minutos timeout
SYNC_LOCK_RETRY_ATTEMPTS=3                   # Intentos de adquirir lock

# === 📊 MÉTRICAS Y MONITOREO ===
METRICS_COLLECTION_ENABLED=true              # Recolectar métricas
METRICS_RETENTION_DAYS=30                    # Retener métricas N días
HEALTH_CHECK_CACHE_TTL=60                    # Cache health checks (segundos)

# === 🗄️ REDIS ===
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50                     # Pool de conexiones
REDIS_SOCKET_TIMEOUT=5                       # Timeout de socket
REDIS_SOCKET_CONNECT_TIMEOUT=5               # Timeout de conexión

# === ⚡ CONFIGURACIÓN DE RENDIMIENTO ===
MAX_RETRIES=3                                # Reintentos en fallos
RETRY_BACKOFF_FACTOR=2                       # Factor de backoff exponencial
RATE_LIMIT_PER_SECOND=2                      # Límite global de llamadas
ENABLE_REQUEST_COMPRESSION=true              # Comprimir requests HTTP

# === 📧 ALERTAS Y NOTIFICACIONES ===
ALERT_EMAIL_ENABLED=False                    # Habilitar alertas por email
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_USE_TLS=true
ALERT_EMAIL_FROM=alerts@yourcompany.com
ALERT_EMAIL_TO=admin@yourcompany.com
ALERT_EMAIL_PASSWORD=your_email_password

# === 🧪 DESARROLLO Y DEBUG ===
# DEBUG_MODE=true                            # Solo en desarrollo
# ENABLE_SQL_ECHO=true                       # Mostrar queries SQL
# ENABLE_PROFILE=true                        # Profiling de performance
```

## 🎮 Uso

### Iniciar la aplicación

```bash
# Desarrollo (inicia motor de sincronización automática)
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Producción (inicia motor de sincronización automática)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

**🤖 Motor Automático**: El sistema de detección de cambios se inicia automáticamente al ejecutar uvicorn si `ENABLE_SCHEDULED_SYNC=true`

### Iniciar Celery (tareas asíncronas)

```bash
# Worker
celery -A app.core.celery_app worker --loglevel=info

# Scheduler (tareas programadas)
celery -A app.core.celery_app beat --loglevel=info
```

### API Endpoints

#### 🤖 Motor de Sincronización Automática

```bash
# Estado del motor automático
GET /api/v1/sync/monitor/status

# Estadísticas en tiempo real
GET /api/v1/sync/monitor/stats

# Trigger manual de sincronización
POST /api/v1/sync/monitor/trigger

# Sincronización completa forzada
POST /api/v1/sync/monitor/force-full-sync

# Actualizar intervalo (en minutos)
PUT /api/v1/sync/monitor/interval
{
  "interval_minutes": 10
}

# Health check del motor
GET /api/v1/sync/monitor/health

# Actividad reciente del motor
GET /api/v1/sync/monitor/recent-activity

# Configuración actual
GET /api/v1/sync/monitor/config
```

#### Sincronización Manual

```bash
# Sincronizar productos RMS → Shopify
POST /api/v1/sync/rms-to-shopify
{
  "force_update": false,
  "batch_size": 100,
  "include_zero_stock": false,
  "filter_categories": ["Zapatos", "Ropa"]
}

# Sincronizar pedidos Shopify → RMS  
POST /api/v1/sync/shopify-to-rms
{
  "order_ids": ["123456789", "987654321"]
}

# Estado de sincronización
GET /api/v1/sync/status
```

#### Webhooks Shopify

```bash
# Configurar webhook para pedidos
POST /api/v1/webhooks/shopify/orders/create

# Webhook para actualización de productos
POST /api/v1/webhooks/shopify/products/update
```

#### Monitoreo y Administración

```bash
# Salud del sistema
GET /api/v1/health
GET /api/v1/metrics/health-detailed

# Métricas de sincronización
GET /api/v1/metrics/system
GET /api/v1/metrics/performance
GET /api/v1/metrics/dashboard

# Logs y auditoría
GET /api/v1/logs?level=error&limit=50
GET /api/v1/logs/stream  # Stream en tiempo real

# Administración
GET /api/v1/admin/system-info
GET /api/v1/admin/cache-stats
GET /api/v1/admin/active-syncs
GET /api/v1/admin/database-health
POST /api/v1/admin/maintenance
```

## 📁 Estructura del Proyecto

```
rms-shopify-integration/
├── app/
│   ├── __init__.py
│   ├── main.py                            # Punto de entrada FastAPI con factory pattern
│   │
│   ├── api/v1/endpoints/                  # ⭐ API REST Endpoints
│   │   ├── sync.py                        # Sincronización manual (RMS↔Shopify)
│   │   ├── sync_monitor.py                # Monitor del motor automático
│   │   ├── webhooks.py                    # Webhooks de Shopify
│   │   ├── collections.py                 # Gestión de collections
│   │   ├── metrics.py                     # Métricas y estadísticas
│   │   ├── logs.py                        # Visualización de logs (DEBUG)
│   │   └── admin.py                       # Operaciones administrativas (DEBUG)
│   │
│   ├── core/                              # ⭐ Configuración y Utilidades Core
│   │   ├── config.py                      # Configuración centralizada (Pydantic Settings)
│   │   ├── lifespan.py                    # Eventos de inicio/cierre de app
│   │   ├── scheduler.py                   # APScheduler para sync automático
│   │   ├── logging_config.py              # Sistema de logging estructurado
│   │   ├── health.py                      # Health checks multi-capa
│   │   ├── middleware.py                  # Request logging, error handling, CORS
│   │   ├── routers.py                     # Registro de routers
│   │   ├── redis_client.py                # Cliente Redis con singleton
│   │   ├── cache_manager.py               # Sistema de caché con TTL
│   │   ├── metrics.py                     # Recolección de métricas
│   │   ├── taxonomy_mapping.py            # Mapeo RMS → Shopify taxonomy
│   │   └── exception_handlers.py          # Manejo global de excepciones
│   │
│   ├── db/                                # ⭐ Capa de Acceso a Datos (SOLID)
│   │   ├── connection.py                  # Pool de conexiones SQL Server (Singleton)
│   │   │
│   │   ├── repositories/                  # Repositorios RMS (Patrón Repository)
│   │   │   ├── base.py                    # BaseRepository con retry y session
│   │   │   ├── product.py                 # ProductRepository - consultas productos
│   │   │   ├── order.py                   # OrderRepository - creación pedidos
│   │   │   ├── customer.py                # CustomerRepository - gestión clientes
│   │   │   ├── metadata.py                # MetadataRepository - operaciones metadata
│   │   │   └── query_executor.py          # QueryExecutor - queries complejas
│   │   │
│   │   ├── shopify/                       # Clientes Shopify Modulares
│   │   │   ├── base_client.py             # BaseClient - HTTP/auth compartido
│   │   │   ├── product_client.py          # ProductClient - operaciones GraphQL
│   │   │   ├── inventory_client.py        # InventoryClient - gestión inventario
│   │   │   ├── collection_client.py       # CollectionClient - collections
│   │   │   └── unified_client.py          # UnifiedClient - facade coordinador
│   │   │
│   │   └── queries/                       # Queries SQL organizadas por dominio
│   │       ├── product_queries.py         # Consultas de productos
│   │       ├── order_queries.py           # Consultas de órdenes
│   │       └── customer_queries.py        # Consultas de clientes
│   │
│   ├── domain/                            # ⭐ Capa de Dominio (DDD)
│   │   ├── models/                        # Modelos de dominio con lógica de negocio
│   │   │   ├── order.py                   # OrderDomain - aggregate root
│   │   │   ├── order_entry.py             # OrderEntryDomain - line items
│   │   │   └── customer.py                # CustomerDomain - customer aggregate
│   │   │
│   │   └── value_objects/                 # Value Objects inmutables
│   │       └── money.py                   # Money - objeto de valor monetario
│   │
│   ├── services/                          # ⭐ Capa de Servicios (Lógica de Negocio)
│   │   │
│   │   ├── rms_to_shopify/                # RMS → Shopify (Componentes Modulares)
│   │   │   ├── data_extractor.py          # Extracción desde RMS con filtros
│   │   │   ├── product_processor.py       # Transformación y preparación
│   │   │   ├── shopify_updater.py         # Actualización en Shopify
│   │   │   ├── report_generator.py        # Generación de reportes sync
│   │   │   └── sync_orchestrator.py       # Orquestador principal
│   │   │
│   │   ├── shopify_to_rms/                # Shopify → RMS (Diseño SOLID)
│   │   │   ├── order_validator.py         # Validación de pedidos Shopify
│   │   │   ├── order_converter.py         # Conversión a formato dominio
│   │   │   ├── customer_resolver.py       # Resolución/creación clientes
│   │   │   ├── order_creator.py           # Creación en RMS
│   │   │   └── order_orchestrator.py      # Orquestador de pedidos
│   │   │
│   │   ├── change_detector.py             # Detección de cambios (LastUpdated)
│   │   ├── checkpoint/                    # Sistema de Checkpoints
│   │   │   ├── update_checkpoint.py       # UpdateCheckpointManager
│   │   │   └── sync_checkpoint.py         # SyncCheckpointManager
│   │   │
│   │   ├── inventory_manager.py           # Sincronización de inventario
│   │   ├── collection_manager.py          # Gestión de collections
│   │   ├── variant_mapper.py              # Mapeo RMS variants → Shopify
│   │   └── bulk_operations.py             # Operaciones masivas
│   │
│   └── utils/                             # ⭐ Utilidades y Helpers
│       ├── error_handler.py               # Manejo centralizado de errores
│       ├── error_aggregator.py            # Agregación de errores en batch
│       ├── retry_handler.py               # Lógica de retry con backoff
│       └── notifications.py               # Sistema de alertas
│
├── scripts/                               # ⭐ Scripts de Utilidad
│   ├── analyze_critical_stock.py          # Análisis de stock crítico
│   ├── sync_critical_products.py          # Sync selectivo de críticos
│   ├── cleanup_product_tags.py            # Limpieza de tags
│   ├── monitor_sync.py                    # Monitor de sync en tiempo real
│   └── fix_all_variant_colors.py          # Corrección de variantes incorrectas
│
├── checkpoint/                            # Directorio de Checkpoints
│   └── checkpoint.json                    # Update checkpoint (último sync exitoso)
│
├── checkpoints/                           # Directorio de Progress Checkpoints
│   └── [sync_id].json                     # Checkpoints de progreso por sync
│
├── logs/                                  # Directorio de Logs
│   ├── app.log                            # Log principal
│   ├── app_errors.log                     # Solo errores
│   └── app.json                           # Logs en formato JSON
│
├── tests/                                 # ⭐ Suite de Pruebas
│   ├── unit/                              # Tests unitarios
│   ├── integration/                       # Tests de integración
│   └── e2e/                               # Tests end-to-end
│
├── .env                                   # Variables de entorno (no en repo)
├── .env.example                           # Ejemplo de configuración
├── pyproject.toml                         # Configuración Poetry y proyecto
├── docker-compose.yml                     # Orquestación Docker producción
├── docker-compose.dev.yml                 # Orquestación Docker desarrollo
├── Dockerfile                             # Imagen Docker optimizada
└── README.md                              # Este archivo
```

### Convenciones de Organización

- **`repositories/`**: Un archivo por entidad (Product, Order, Customer)
- **`shopify/`**: Un cliente por responsabilidad (Product, Inventory, Collection)
- **`domain/`**: Modelos con lógica de negocio, value objects inmutables
- **`services/`**: Orquestadores que coordinan repositorios y domain models
- **`checkpoint/`**: Checkpoints de última sincronización exitosa
- **`checkpoints/`**: Checkpoints de progreso para sincronizaciones en curso

## 🏗️ Arquitectura SOLID y Domain-Driven Design

El proyecto ha evolucionado hacia una arquitectura moderna siguiendo principios SOLID y Domain-Driven Design (DDD).

### Migración de Arquitectura Monolítica a SOLID

**Antes (Monolítico)**:
```python
# ❌ Problema: Clase RMSHandler con múltiples responsabilidades
class RMSHandler:
    def get_products(self): ...
    def create_order(self): ...
    def get_customer(self): ...
    def get_inventory(self): ...
    # ... 20+ métodos más
```

**Ahora (SOLID - Repository Pattern)**:
```python
# ✅ Solución: Repositorios especializados con responsabilidad única
class ProductRepository(BaseRepository):
    """Responsabilidad única: Operaciones de productos"""
    async def get_by_ccod(self, ccod: str): ...
    async def get_modified_since(self, timestamp: datetime): ...

class OrderRepository(BaseRepository):
    """Responsabilidad única: Gestión de pedidos"""
    async def create_order(self, order_domain: OrderDomain): ...
    async def get_by_id(self, order_id: int): ...

class CustomerRepository(BaseRepository):
    """Responsabilidad única: Gestión de clientes"""
    async def find_by_email(self, email: str): ...
    async def create_customer(self, customer: CustomerDomain): ...
```

### Principios SOLID Aplicados

#### 1. **S**ingle Responsibility (Responsabilidad Única)
- ✅ Cada repositorio maneja una sola entidad
- ✅ Cada cliente de Shopify tiene una responsabilidad específica
- ✅ Servicios orquestan, no implementan lógica de datos

```python
# Ejemplo: ProductRepository solo maneja productos
class ProductRepository:
    async def get_by_ccod(self, ccod: str): ...
    async def get_all(self, filters: dict): ...
    # NO tiene métodos de orders, customers, etc.
```

#### 2. **O**pen/Closed (Abierto/Cerrado)
- ✅ BaseRepository permite extensión sin modificación
- ✅ Nuevos repositorios heredan funcionalidad común
- ✅ Fácil agregar nuevos tipos de sync sin modificar existentes

```python
# Extensión sin modificar BaseRepository
class NewEntityRepository(BaseRepository):
    """Nuevo repositorio sin modificar código existente"""
    async def custom_query(self): ...
```

#### 3. **L**iskov Substitution (Sustitución de Liskov)
- ✅ Todos los repositorios son intercambiables donde se espera BaseRepository
- ✅ Clientes Shopify son intercambiables vía interfaces

#### 4. **I**nterface Segregation (Segregación de Interfaces)
- ✅ Clientes especializados (Product, Inventory, Collection) vs un cliente gigante
- ✅ Servicios solo dependen de los repositorios que necesitan

#### 5. **D**ependency Inversion (Inversión de Dependencias)
- ✅ Servicios dependen de abstracciones (BaseRepository)
- ✅ No dependen de implementaciones concretas

```python
# Servicios reciben dependencias (inyección)
class SyncOrchestrator:
    def __init__(
        self,
        product_repo: ProductRepository,      # Dependencia inyectada
        shopify_client: UnifiedClient,        # Dependencia inyectada
        checkpoint_manager: UpdateCheckpoint  # Dependencia inyectada
    ): ...
```

### Domain-Driven Design (DDD)

#### Value Objects
```python
# Money - Objeto de valor inmutable para cantidades monetarias
from app.domain.value_objects.money import Money

price = Money(amount=Decimal("99.99"), currency="USD")
# Inmutable, auto-validación, comportamiento encapsulado
```

#### Domain Models (Aggregates)
```python
# OrderDomain - Aggregate Root con lógica de negocio
from app.domain.models.order import OrderDomain

order = OrderDomain(
    customer_id=123,
    store_id=1,
    total_amount=Money(Decimal("199.99"), "USD")
)
order.add_line_item(product_id=456, quantity=2, price=Money(...))
order.validate()  # Validación de reglas de negocio
```

#### Ventajas del Domain Layer
- **Lógica de negocio centralizada**: No dispersa en servicios o controllers
- **Validación en el modelo**: Imposible crear objetos inválidos
- **Testeable**: Domain models son puros (sin dependencias externas)
- **Reutilizable**: Misma lógica en diferentes contextos

### Clientes Shopify Modulares

**Antes**: Cliente monolítico con todos los métodos
**Ahora**: Clientes especializados por responsabilidad

```python
# UnifiedClient - Facade que coordina clientes especializados
class UnifiedClient:
    def __init__(self):
        self.products = ProductClient()      # Solo productos
        self.inventory = InventoryClient()   # Solo inventario
        self.collections = CollectionClient() # Solo collections
```

**Beneficios**:
- 🎯 Responsabilidad clara y única
- 🧪 Testeo más sencillo (mock individual)
- 🔧 Mantenimiento aislado por dominio
- 📦 Reutilización en diferentes contextos

### Patrón de Orquestación

Los **servicios** actúan como **orquestadores** que coordinan repositorios y domain models:

```python
# SyncOrchestrator coordina múltiples componentes
class SyncOrchestrator:
    async def sync_products(self):
        # 1. Extraer datos (usa ProductRepository)
        products = await self.extractor.extract()

        # 2. Procesar (usa domain models)
        processed = await self.processor.process(products)

        # 3. Actualizar Shopify (usa ShopifyClient)
        await self.updater.update(processed)

        # 4. Generar reporte
        return await self.reporter.generate(results)
```

### Beneficios de la Nueva Arquitectura

| Aspecto | Antes (Monolítico) | Ahora (SOLID + DDD) |
|---------|-------------------|---------------------|
| **Testabilidad** | ❌ Difícil (todo acoplado) | ✅ Fácil (componentes aislados) |
| **Mantenibilidad** | ❌ Cambios impactan todo | ✅ Cambios aislados |
| **Extensibilidad** | ❌ Agregar features modifica todo | ✅ Agregar sin modificar existente |
| **Claridad** | ❌ Responsabilidades mezcladas | ✅ Responsabilidad única clara |
| **Reutilización** | ❌ Difícil reutilizar partes | ✅ Componentes reutilizables |
| **Bugs** | ❌ Cambios rompen cosas no relacionadas | ✅ Impacto predecible y contenido |

## 🤖 Motor de Sincronización Automática

### Detección de Cambios en Tiempo Real

El sistema incluye un **motor de sincronización automática** que:

- 🔍 **Detecta cambios** en RMS usando `Item.LastUpdated` cada 5 minutos
- 🔗 **Vincula datos** entre tabla `Item` y vista `View_Items` 
- ⚡ **Sincroniza automáticamente** productos modificados por CCOD
- 🛡️ **Auto-recovery** con health checks cada 5 minutos
- 📊 **Métricas en tiempo real** accesibles via API

### Sincronización Completa Programada

Además del motor de cambios, puedes configurar una **sincronización completa diaria/semanal**:

- 🕐 **Horario configurable** con soporte de zonas horarias
- 📅 **Días específicos** de la semana (opcional)
- 🔄 **Independiente del motor de cambios** para asegurar consistencia
- 📊 **Reconciliación nocturna** de todo el catálogo

### Configuración Rápida

```bash
# En tu archivo .env

# Motor de detección de cambios (cada 5 minutos)
ENABLE_SCHEDULED_SYNC=true
SYNC_INTERVAL_MINUTES=5

# Sincronización completa programada (opcional)
ENABLE_FULL_SYNC_SCHEDULE=true              # Activar sync programada
FULL_SYNC_HOUR=23                           # 11 PM
FULL_SYNC_MINUTE=0                          # En punto
FULL_SYNC_TIMEZONE=America/Argentina/Buenos_Aires

# Ejemplos de configuración:
# Diaria a las 2 AM UTC
# FULL_SYNC_TIMEZONE=UTC
# FULL_SYNC_HOUR=2

# Solo días laborables (Lun-Vie) a las 3 AM
# FULL_SYNC_DAYS=0,1,2,3,4
# FULL_SYNC_HOUR=3

# Solo fines de semana
# FULL_SYNC_DAYS=5,6

# Iniciar aplicación (ambos motores se activan automáticamente)
poetry run uvicorn app.main:app --reload
```

### APIs de Control

```bash
# Ver estado del motor
curl http://localhost:8080/api/v1/sync/monitor/status

# Ejecutar sincronización manual
curl -X POST http://localhost:8080/api/v1/sync/monitor/trigger

# Ver estadísticas detalladas  
curl http://localhost:8080/api/v1/sync/monitor/stats
```

### Logs del Motor

```
🔍 Verificando cambios desde 2025-07-03T10:15:00Z
🔔 Detectados 3 items modificados en RMS
🔄 Iniciando sincronización automática para 3 items
✅ Sincronización automática completada: 3 productos procesados
```

## 🔄 Sistema de Checkpoints Dual

El sistema implementa **dos tipos de checkpoints** para máxima eficiencia y recuperación ante fallos.

### 1. Update Checkpoint (Sincronización Incremental)

Almacena la marca temporal del **último sync exitoso** para sincronizar solo cambios.

**Ubicación**: `./checkpoint/checkpoint.json`

**Estructura**:
```json
{
  "last_sync_timestamp": "2025-01-23T15:30:00Z",
  "total_synced": 1247,
  "success_rate": 0.98,
  "created_at": "2025-01-23T15:32:15Z"
}
```

**Funcionamiento**:
```python
# 1. Lee última sincronización exitosa
last_sync = checkpoint_manager.get_last_sync_time()
# → "2025-01-23T15:30:00Z"

# 2. Solo consulta productos modificados después
products = await repo.get_modified_since(last_sync)
# → Solo 15 productos modificados (no los 50,000 del catálogo)

# 3. Si sync exitoso (>95%), actualiza checkpoint
if success_rate > 0.95:
    checkpoint_manager.save(now)
```

**Configuración**:
```bash
# Habilitar modo incremental
USE_UPDATE_CHECKPOINT=true

# Umbral de éxito para actualizar (95% por defecto)
CHECKPOINT_SUCCESS_THRESHOLD=0.95

# Si no existe checkpoint, usar últimos N días
CHECKPOINT_DEFAULT_DAYS=30
```

**Ventajas**:
- ⚡ **100x más rápido**: Solo procesa cambios (15 items vs 50,000)
- 💰 **Menor costo**: Menos llamadas a API Shopify
- 🎯 **Precisión**: Usa `Item.LastUpdated` de RMS (fiable)

### 2. Progress Checkpoint (Recuperación de Fallos)

Almacena el **progreso** de sincronización en curso para reanudar si se interrumpe.

**Ubicación**: `./checkpoints/sync_[id].json`

**Estructura**:
```json
{
  "sync_id": "sync_20250123_153000",
  "total_items": 250,
  "processed_items": 150,
  "current_batch": 6,
  "start_time": "2025-01-23T15:30:00Z",
  "status": "in_progress"
}
```

**Funcionamiento**:
```python
# Guarda progreso cada 100 items
for batch in batches:
    await sync_batch(batch)
    checkpoint.save_progress(
        processed=len(batched_items),
        batch_number=current_batch
    )

# Si falla, reanuda desde último checkpoint
if interrupted:
    progress = checkpoint.load_progress(sync_id)
    resume_from_item = progress['processed_items']
```

**Auto-limpieza**:
- ✅ Se elimina automáticamente al completar sync
- ⏳ Permite reanudar si falla a mitad (evita re-procesar todo)

### Comparación de Checkpoints

| Tipo | Propósito | Ubicación | Duración | Limpieza |
|------|-----------|-----------|----------|----------|
| **Update** | Sync incremental | `./checkpoint/checkpoint.json` | Permanente | Manual |
| **Progress** | Recuperación | `./checkpoints/[sync_id].json` | Temporal | Auto (al completar) |

### Ejemplo de Uso Combinado

```bash
# Escenario: Tienes 50,000 productos, 15 fueron modificados hoy

# 1. Update Checkpoint → Solo extrae 15 modificados
[15:30] 🔍 Última sync: 2025-01-23T00:00:00Z
[15:30] 📦 Encontrados 15 productos modificados

# 2. Progress Checkpoint → Guarda progreso cada batch
[15:31] ✅ Batch 1/1 completado (15 items)
[15:31] 💾 Progress checkpoint guardado

# 3. Si falla en batch medio
[15:32] ❌ Error en batch 2/4 (procesados: 100/250)
[15:32] 💾 Progress checkpoint: { processed: 100, batch: 2 }

# 4. Al reiniciar, reanuda desde item 100
[15:35] 🔄 Reanudando desde item 100 (quedan 150)
[15:36] ✅ Completado (250/250)

# 5. Update checkpoint se actualiza solo si >95% éxito
[15:36] ✅ Success rate: 98% → Update checkpoint actualizado
[15:36] 🗑️  Progress checkpoint eliminado
```

### Configuración Completa

```bash
# === UPDATE CHECKPOINT (Incremental Sync) ===
USE_UPDATE_CHECKPOINT=true                   # Habilitar sync incremental
CHECKPOINT_SUCCESS_THRESHOLD=0.95            # Mínimo 95% éxito para actualizar
CHECKPOINT_DEFAULT_DAYS=30                   # Días atrás si no hay checkpoint
CHECKPOINT_FILE_PATH=./checkpoint            # Directorio de checkpoints

# === PROGRESS CHECKPOINT (Resume) ===
ENABLE_PROGRESS_CHECKPOINT=true              # Habilitar recuperación
CHECKPOINT_SAVE_INTERVAL=100                 # Guardar cada N items
CHECKPOINT_AUTO_CLEANUP=true                 # Limpiar al completar
```

### Endpoints de Checkpoint

```bash
# Ver estado de update checkpoint
GET /api/v1/sync/checkpoint/status

# Ver progreso de sync en curso
GET /api/v1/sync/monitor/checkpoint/{sync_id}

# Resetear update checkpoint (forzar full sync)
DELETE /api/v1/sync/checkpoint

# Limpiar checkpoints huérfanos
POST /api/v1/sync/checkpoint/cleanup
```

### Ventajas del Sistema Dual

| Beneficio | Update Checkpoint | Progress Checkpoint |
|-----------|-------------------|---------------------|
| **Velocidad** | ✅ 100x más rápido (incremental) | ⚡ Resume sin re-procesar |
| **Confiabilidad** | ✅ Siempre sabe desde cuándo sync | ✅ No pierde progreso |
| **Costo** | 💰 Menor uso de API | 💾 Menor procesamiento |
| **Mantenimiento** | 📝 Manual (persiste) | 🗑️ Auto-limpieza |

## 🔄 Flujos de Sincronización

### RMS → Shopify (Productos) - Sistema Mejorado

1. **Extracción**: Lee vista `View_Items` de RMS con campos familia, categoria, talla, color
2. **Mapeo de Taxonomías**: Utiliza `RMSTaxonomyMapper` para mapear a Standard Product Taxonomy
4. **Resolución Inteligente**: Busca mejores coincidencias de taxonomía con algoritmo de puntuación
5. **Metafields Estructurados**: Crea hasta 7 metafields con datos RMS organizados
6. **Validación**: Verifica integridad de datos y mapeos
7. **Filtrado**: Excluye productos sin stock por defecto (`include_zero_stock: false`)
8. **Carga**: Crea productos con categoría y metafields usando GraphQL
9. **Confirmación**: Registra resultado y métricas detalladas

### Shopify → RMS (Pedidos)

1. **Webhook**: Recibe notificación de nuevo pedido
2. **Validación**: Verifica autenticidad y formato
3. **Mapeo**: Convierte a formato RMS
4. **Inserción**: Crea registro en tablas `ORDER`/`ORDERENTRY`
5. **Confirmación**: Actualiza estado en Shopify

## 🏷️ Sistema de Taxonomías y Metafields

### Mapeo Avanzado RMS → Shopify

El sistema incluye un mapeador comprehensivo que convierte datos RMS a taxonomías estándar de Shopify:

#### Familias RMS Soportadas
- **Zapatos** → Footwear (Tenis, Botas, Sandalias, Tacones, etc.)
- **Ropa** → Apparel (MUJER-VEST, NIÑO-CASU, etc.)
- **Accesorios** → Accessories (Bolsos, ACCESORIOS CALZADO, etc.)
- **Miscelaneos** → Miscellaneous

#### Metafields Creados Automáticamente
```json
{
  "rms.familia": "Zapatos",
  "rms.categoria": "Tenis", 
  "rms.talla": "23½",
  "rms.color": "Negro",
  "rms.extended_category": "Zapatos > Tenis",
  "rms.product_attributes": {
    "familia": "Zapatos",
    "categoria": "Tenis",
    "ccod": "TEN001",
    "price": 129.99
  }
}
```


### Uso del Sistema Mejorado

```python
from app.services.enhanced_data_mapper import EnhancedDataMapper

# Inicializar
mapper = EnhancedDataMapper(shopify_client)
await mapper.initialize()

# Validar mapeo
validation = await mapper.validate_product_mapping(rms_item)

# Mapear producto completo
product_data = await mapper.map_rms_item_to_shopify_product(rms_item)
```

## 🔧 Configuración Avanzada

### Configuración de Sincronización

```bash
# Variables de entorno adicionales
SHOPIFY_API_VERSION=2025-04           # Versión API con soporte taxonomías
SHOPIFY_RATE_LIMIT_PER_SECOND=2      # Límite de llamadas por segundo
SYNC_INCLUDE_ZERO_STOCK=false        # Excluir productos sin stock
SYNC_USE_ENHANCED_MAPPER=true        # Usar mapeador avanzado
TAXONOMY_CACHE_TTL=3600              # Cache de taxonomías (segundos)
BULK_OPERATION_TIMEOUT=600           # Timeout para operaciones masivas
ENABLE_DRY_RUN_MODE=false           # Modo simulación sin cambios
```

### Filtros de Sincronización

```python
# Configurar filtros en .env
SYNC_FILTER_CATEGORIES=Electronics,Clothing
SYNC_FILTER_MIN_PRICE=10.00
SYNC_FILTER_EXCLUDE_INACTIVE=True
```

## 🚨 Monitoreo y Alertas

### Tipos de Alertas

- **Errores de Conexión**: RMS/Shopify no disponible
- **Errores de Sincronización**: Fallos en mapeo de datos
- **Rate Limit**: Límite de API alcanzado
- **Datos Inconsistentes**: Discrepancias detectadas
- **Operaciones Bloqueadas**: Intentos de sincronización concurrente
- **Performance**: Degradación del rendimiento del sistema
- **Espacio en Disco**: Alertas de capacidad para logs
- **Motor Detenido**: Si el motor automático falla

### Configuración de Alertas

```python
# app/utils/alerts.py
ALERT_THRESHOLDS = {
    'error_rate_threshold': 0.05,  # 5% de errores
    'sync_delay_minutes': 30,      # Retraso máximo
    'api_response_time_ms': 5000   # Tiempo de respuesta
}
```

## 🧪 Testing

```bash
# Ejecutar todas las pruebas
pytest

# Pruebas con cobertura
pytest --cov=app tests/

# Pruebas específicas
pytest tests/test_sync_services.py -v
```

## 📊 Métricas y KPIs

### Métricas de Rendimiento
- **Productos sincronizados/hora**: Throughput del sistema
- **Tiempo promedio de sincronización**: Por producto y por lote
- **Tasa de errores por servicio**: RMS, Shopify, Redis
- **Disponibilidad del sistema**: Uptime y SLA
- **Latencia de webhooks**: Tiempo de procesamiento

### Métricas de Negocio
- **Productos activos sincronizados**: Total y por categoría
- **Órdenes procesadas**: Por día/hora con montos
- **Discrepancias de inventario**: Detección automática
- **Tiempo de actualización**: Desde cambio RMS hasta Shopify

### Métricas del Sistema
- **Uso de CPU/Memoria**: Por componente
- **Conexiones de base de datos**: Pool y activas
- **Cache hit rate**: Eficiencia del Redis
- **API calls**: Por endpoint y cliente

## 🐳 Docker

### Desarrollo
```bash
# Construir imagen de desarrollo
docker build -f Dockerfile.dev -t rms-shopify-integration:dev .

# Ejecutar con hot-reload
docker-compose -f docker-compose.dev.yml up

# Ver logs en tiempo real
docker-compose logs -f api
```

### Producción
```bash
# Construir imagen optimizada
docker build -t rms-shopify-integration:latest .

# Ejecutar con docker-compose
docker-compose up -d

# Escalar workers
docker-compose up -d --scale api=3

# Backup de volúmenes
docker run --rm -v rms-shopify-integration_redis-data:/data \
  -v $(pwd)/backup:/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .
```

## 🤝 Contribución

1. Fork del proyecto
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📚 Documentación Adicional

### 📖 Guías de Sincronización
- **[📄 RMS → Shopify](RMS_TO_SHOPIFY_SYNC.md)** - Guía completa de sincronización de productos, inventario y precios desde RMS hacia Shopify
- **[📄 Shopify → RMS](SHOPIFY_TO_RMS_SYNC.md)** - Guía completa de sincronización de pedidos desde Shopify hacia RMS
- **[📄 Configuración de Webhooks](WEBHOOK_CONFIGURATION.md)** - Guía detallada para configurar webhooks de Shopify y manejo de pedidos sin cliente
- **[🤖 Motor de Sincronización Automática](AUTOMATIC_SYNC_ENGINE.md)** - Guía completa del motor de detección de cambios automática
- **[💻 Instalación en Windows](WINDOWS_INSTALLATION.md)** - Guía paso a paso para instalar en Windows Server
- **[🔧 Guía para Desarrolladores](CLAUDE.md)** - Referencia rápida para desarrollo y mantenimiento

### 📊 APIs y Referencias
- **[API Docs](http://localhost:8080/docs)** - Documentación interactiva Swagger (cuando la app esté corriendo)
- **[Sistema de Taxonomías y Metafields](docs/enhanced_taxonomy_system.md)** - Guía completa del sistema avanzado
- **[CHANGELOG.md](CHANGELOG.md)** - Historial completo de cambios

### 🔧 Scripts de Utilidad
- **[configure_webhooks.py](configure_webhooks.py)** - Script para configurar webhooks automáticamente
- Script para monitorear motor automático:
  ```bash
  # Verificar estado del motor
  curl http://localhost:8080/api/v1/sync/monitor/status
  
  # Trigger sincronización manual
  curl -X POST http://localhost:8080/api/v1/sync/monitor/trigger
  ```

## 📧 Soporte

Para soporte técnico o consultas:
- **Email**: enzo@oneclick.cr
- **Issues**: [GitHub Issues](https://github.com/One-Click-Python/integration-best-brands-cr/issues)

## 📝 Historial de Cambios

Para ver el historial completo de cambios, consulte el archivo [CHANGELOG.md](CHANGELOG.md).
