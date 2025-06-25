# RMS-Shopify Integration

Sistema de integración bidireccional entre Microsoft Retail Management System (RMS) y Shopify para automatizar la sincronización de productos, inventarios, precios y pedidos entre venta física y e-commerce.

## 🎯 Características Principales

- **Sincronización Bidireccional**: RMS ↔ Shopify con taxonomías estándar
- **Sistema de Taxonomías Avanzado**: Mapeo inteligente a Standard Product Taxonomy de Shopify
- **Metafields Estructurados**: Talla, color y atributos RMS preservados como metafields
- **Normalización Automática**: Tallas (`23½` → `23.5`) y datos RMS optimizados
- **Arquitectura de Microservicios**: Modular y escalable
- **API REST**: Control manual y programado con filtros avanzados
- **Webhooks**: Captura en tiempo real de eventos Shopify
- **Sistema de Alertas**: Notificaciones de errores y estado
- **Logging Estructurado**: Auditoría completa de operaciones

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   RMS (SQL)     │◄──►│  FastAPI App     │◄──►│    Shopify      │
│                 │    │                  │    │                 │
│ • Products      │    │ • Sync Services  │    │ • Products      │
│ • Inventory     │    │ • Webhooks       │    │ • Orders        │
│ • Orders        │    │ • APIs           │    │ • Inventory     │
└─────────────────┘    │ • Error Handler  │    └─────────────────┘
                       │ • Logging        │
                       └──────────────────┘
                              │
                       ┌──────────────────┐
                       │ Redis + Celery   │
                       │ (Async Tasks)    │
                       └──────────────────┘
```

## 🛠️ Stack Tecnológico

- **Python 3.13**
- **FastAPI** - Framework web asíncrono
- **SQLAlchemy** - ORM para SQL Server
- **Pydantic** - Validación y serialización de datos
- **Celery + Redis** - Tareas asíncronas
- **APScheduler** - Programación de tareas
- **Requests/httpx** - Cliente HTTP
- **SQL Server** - Base de datos RMS

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
# Configuración de la aplicación
APP_NAME=RMS-Shopify Integration
APP_VERSION=0.1.0
DEBUG=True
LOG_LEVEL=INFO

# Base de datos RMS (SQL Server)
RMS_DB_HOST=localhost
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database
RMS_DB_USER=your_user
RMS_DB_PASSWORD=your_password
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server

# Shopify API
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token
SHOPIFY_API_VERSION=2024-04
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret

# Redis (para Celery)
REDIS_URL=redis://localhost:6379/0

# Configuración de sincronización
SYNC_INTERVAL_MINUTES=15
MAX_RETRIES=3
RATE_LIMIT_PER_SECOND=2

# Alertas y notificaciones
ALERT_EMAIL_ENABLED=True
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@yourcompany.com
ALERT_EMAIL_TO=admin@yourcompany.com
ALERT_EMAIL_PASSWORD=your_email_password
```

## 🎮 Uso

### Iniciar la aplicación

```bash
# Desarrollo
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

### Iniciar Celery (tareas asíncronas)

```bash
# Worker
celery -A app.core.celery_app worker --loglevel=info

# Scheduler (tareas programadas)
celery -A app.core.celery_app beat --loglevel=info
```

### API Endpoints

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

#### Monitoreo

```bash
# Salud del sistema
GET /api/v1/health

# Métricas de sincronización
GET /api/v1/metrics

# Logs de errores
GET /api/v1/logs?level=error&limit=50
```

## 📁 Estructura del Proyecto

```
rms-shopify-integration/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Punto de entrada FastAPI
│   ├── api/                        # Endpoints de la API
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── sync.py         # Endpoints de sincronización
│   │       │   └── webhooks.py     # Webhooks de Shopify
│   │       └── schemas/
│   │           ├── __init__.py
│   │           ├── rms_schemas.py  # Modelos Pydantic RMS
│   │           └── shopify_schemas.py # Modelos Pydantic Shopify
│   ├── core/                       # Configuración central
│   │   ├── __init__.py
│   │   ├── config.py              # Configuración de la app
│   │   ├── taxonomy_mapping.py    # Sistema de mapeo de taxonomías
│   │   └── logging_config.py      # Configuración de logging
│   ├── db/                        # Acceso a bases de datos
│   │   ├── __init__.py
│   │   ├── rms_handler.py         # Conexión y operaciones RMS
│   │   ├── shopify_client.py      # Cliente API Shopify (legacy)
│   │   ├── shopify_graphql_client.py # Cliente GraphQL Shopify avanzado
│   │   └── shopify_graphql_queries.py # Consultas GraphQL
│   ├── services/                  # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── rms_to_shopify.py     # Servicio RMS → Shopify
│   │   ├── enhanced_data_mapper.py # Mapeador avanzado con taxonomías
│   │   └── shopify_to_rms.py     # Servicio Shopify → RMS
│   └── utils/                     # Utilidades
│       ├── __init__.py
│       └── error_handler.py      # Manejo de errores
├── tests/                         # Pruebas unitarias
├── requirements.txt              # Dependencias
├── pyproject.toml               # Configuración del proyecto
├── .env.example                 # Ejemplo de variables de entorno
├── docker-compose.yml           # Orquestación con Docker
└── README.md
```

## 🔄 Flujos de Sincronización

### RMS → Shopify (Productos) - Sistema Mejorado

1. **Extracción**: Lee vista `View_Items` de RMS con campos familia, categoria, talla, color
2. **Mapeo de Taxonomías**: Utiliza `RMSTaxonomyMapper` para mapear a Standard Product Taxonomy
3. **Normalización**: Convierte tallas (`23½` → `23.5`) y limpia datos
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
  "rms.talla": "23.5",
  "rms.talla_original": "23½",
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

#### Normalización de Tallas
- `23½` → `23.5`
- `24¼` → `24.25`
- `25¾` → `25.75`
- Preserva talla original cuando hay cambios

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
SHOPIFY_API_VERSION=2024-04           # Versión API con soporte taxonomías
SYNC_INCLUDE_ZERO_STOCK=false        # Excluir productos sin stock
SYNC_USE_ENHANCED_MAPPER=true        # Usar mapeador avanzado
TAXONOMY_CACHE_TTL=3600              # Cache de taxonomías (segundos)
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

- **Productos sincronizados/hora**
- **Tiempo promedio de sincronización**
- **Tasa de errores por servicio**
- **Disponibilidad del sistema**
- **Latencia de webhooks**

## 🐳 Docker

```bash
# Construir imagen
docker build -t rms-shopify-integration .

# Ejecutar con docker-compose
docker-compose up -d
```

## 🤝 Contribución

1. Fork del proyecto
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está licenciado bajo [MIT License](LICENSE).

## 📚 Documentación Adicional

- **[Sistema de Taxonomías y Metafields](docs/enhanced_taxonomy_system.md)** - Guía completa del sistema avanzado
- **[CLAUDE.md](CLAUDE.md)** - Instrucciones para Claude Code y arquitectura detallada
- **[API Docs](http://localhost:8080/docs)** - Documentación interactiva Swagger (cuando la app esté corriendo)
- **[CHANGELOG.md](CHANGELOG.md)** - Historial completo de cambios

## 📧 Soporte

Para soporte técnico o consultas:
- **Email**: leonardo@live.com.ar
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)

## 📝 Historial de Cambios

Para ver el historial completo de cambios, consulte el archivo [CHANGELOG.md](CHANGELOG.md).
