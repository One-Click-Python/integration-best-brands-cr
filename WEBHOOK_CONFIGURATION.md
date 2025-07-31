# Configuración de Webhooks para Sincronización Shopify → RMS

## Descripción General

Los webhooks permiten que Shopify notifique automáticamente a tu sistema RMS cuando ocurren eventos específicos (como creación de pedidos, actualización de productos, etc.). Esto habilita la sincronización en tiempo real sin necesidad de consultar constantemente la API de Shopify, siendo un componente fundamental para el procesamiento eficiente y automático de eventos.

## 🚀 Características Principales

- **Procesamiento en Tiempo Real**: Respuesta inmediata a eventos de Shopify
- **Validación HMAC**: Seguridad completa con verificación de firmas
- **Soporte para Pedidos de Invitados**: Configuración flexible para checkout sin registro
- **Procesamiento en Background**: Respuestas rápidas con procesamiento asíncrono
- **Retry Automático**: Reintentos inteligentes en caso de fallos
- **Monitoreo Avanzado**: Métricas detalladas y alertas automáticas
- **Rate Limiting**: Protección contra sobrecarga de requests
- **Logging Estructurado**: Auditoría completa de todos los eventos

## ¿Qué son los Webhooks?

Un webhook es una notificación HTTP que Shopify envía a tu servidor cuando ocurre un evento específico. En lugar de que tu aplicación consulte constantemente si hay nuevos eventos, Shopify te notifica inmediatamente cuando algo cambia.

### Flujo de Webhooks Mejorado:
1. **Cliente realiza acción** en Shopify (compra, actualización, etc.)
2. **Shopify detecta el evento** y prepara el payload
3. **Shopify envía POST** a tu endpoint configurado con firma HMAC
4. **Tu sistema valida** la firma y autenticidad del request
5. **Procesamiento rápido** con respuesta < 5 segundos
6. **Background processing** para operaciones complejas
7. **Confirmación y logging** de la operación completada

## Tipos de Webhooks Soportados

### Webhooks de Pedidos (Orders)
- `orders/create` - Nuevo pedido creado
- `orders/updated` - Pedido actualizado
- `orders/paid` - Pedido pagado
- `orders/cancelled` - Pedido cancelado
- `orders/fulfilled` - Pedido enviado
- `orders/partially_fulfilled` - Pedido parcialmente enviado

### Webhooks de Productos (Products)
- `products/create` - Nuevo producto creado
- `products/update` - Producto actualizado
- `inventory_levels/update` - Inventario actualizado

### Webhooks de Clientes (Customers)
- `customers/create` - Nuevo cliente registrado
- `customers/update` - Cliente actualizado

## Configuración de Webhooks

### Método 1: Script Automático (Recomendado)

Utiliza el script `configure_webhooks.py` incluido en el proyecto:

```bash
# 1. Configurar variables de entorno
export SHOPIFY_SHOP_URL="tu-tienda.myshopify.com"
export SHOPIFY_ACCESS_TOKEN="shpat_xxxxxxxxxxxxx"
export API_BASE_URL="https://tu-servidor.com"

# 2. Ejecutar el script de configuración completa
poetry run python configure_webhooks.py

# 3. Verificar configuración
poetry run python configure_webhooks.py --verify
```

El script configurará automáticamente estos webhooks esenciales:
- **orders/create**: Pedidos nuevos → `/api/v1/webhooks/shopify/orders/create`
- **orders/updated**: Pedidos actualizados → `/api/v1/webhooks/shopify/orders/update`
- **orders/paid**: Pedidos pagados → `/api/v1/webhooks/shopify/orders/paid`
- **products/update**: Productos actualizados → `/api/v1/webhooks/shopify/products/update`

### Método 2: API REST de la Aplicación

```bash
# Configurar múltiples webhooks usando la API de la aplicación
curl -X POST http://localhost:8080/api/v1/webhooks/configure \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      "orders/create",
      "orders/updated", 
      "orders/paid",
      "products/update",
      "inventory_levels/update"
    ],
    "base_url": "https://tu-servidor.com",
    "validate_existing": true,
    "force_recreate": false
  }'

# Verificar configuración
curl http://localhost:8080/api/v1/webhooks/status
```

### Método 3: Configuración Manual via Admin Shopify

#### Paso 1: Acceder a Configuración de Webhooks
1. Inicia sesión en tu Admin de Shopify
2. Ve a **Settings** (Configuración)
3. Selecciona **Notifications** (Notificaciones)
4. Desplázate hasta la sección **Webhooks**
5. Haz clic en **Create webhook**

#### Paso 2: Configurar Webhooks Principales

**Webhook para Pedidos Creados:**
```
Event: Order creation
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/shopify/orders/create
API version: 2025-04
Fields: id, name, email, financial_status, line_items, customer, billing_address, shipping_address, total_price, total_tax, created_at, updated_at
```

**Webhook para Pedidos Actualizados:**
```
Event: Order updates  
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/shopify/orders/update
API version: 2025-04
```

**Webhook para Productos Actualizados:**
```
Event: Product updates
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/shopify/products/update
API version: 2025-04
```

### Método 4: Configuración via API REST de Shopify

```bash
# Webhook para pedidos creados con configuración completa
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/create",
      "address": "https://tu-servidor.com/api/v1/webhooks/shopify/orders/create",
      "format": "json",
      "fields": [
        "id", "name", "email", "financial_status", "fulfillment_status",
        "line_items", "customer", "billing_address", "shipping_address",
        "total_price", "subtotal_price", "total_tax", "currency",
        "created_at", "updated_at", "order_number", "gateway",
        "total_discounts", "discount_codes", "transactions"
      ]
    }
  }'

# Webhook para productos actualizados
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "products/update",
      "address": "https://tu-servidor.com/api/v1/webhooks/shopify/products/update",
      "format": "json"
    }
  }'

# Webhook para inventario actualizado
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "inventory_levels/update",
      "address": "https://tu-servidor.com/api/v1/webhooks/shopify/inventory/update",
      "format": "json"
    }
  }'
```

## Endpoints de Webhook en tu Sistema

### Endpoints Principales

**Pedidos:**
- `POST /api/v1/webhooks/shopify/orders/create` - Procesa pedidos nuevos
- `POST /api/v1/webhooks/shopify/orders/update` - Procesa pedidos actualizados
- `POST /api/v1/webhooks/shopify/orders/paid` - Procesa pedidos pagados
- `POST /api/v1/webhooks/shopify/orders/cancelled` - Procesa cancelaciones

**Productos:**
- `POST /api/v1/webhooks/shopify/products/create` - Productos nuevos
- `POST /api/v1/webhooks/shopify/products/update` - Productos actualizados
- `POST /api/v1/webhooks/shopify/inventory/update` - Inventario actualizado

**Clientes:**
- `POST /api/v1/webhooks/shopify/customers/create` - Clientes nuevos
- `POST /api/v1/webhooks/shopify/customers/update` - Clientes actualizados

**Genérico:**
- `POST /api/v1/webhooks/shopify` - Endpoint universal que enruta eventos

### Endpoints de Gestión y Monitoreo

```bash
# Estado y configuración
GET /api/v1/webhooks/status               # Estado general de webhooks
GET /api/v1/webhooks/config               # Configuración actual
POST /api/v1/webhooks/configure           # Configurar webhooks automáticamente

# Métricas y monitoreo
GET /api/v1/webhooks/metrics              # Métricas de procesamiento
GET /api/v1/webhooks/metrics/detailed     # Métricas detalladas por tipo
GET /api/v1/webhooks/recent-activity      # Actividad reciente

# Testing y diagnóstico
POST /api/v1/webhooks/test                # Probar procesamiento
GET /api/v1/webhooks/health               # Health check
POST /api/v1/webhooks/validate/{webhook_id} # Validar webhook específico

# Gestión de errores
GET /api/v1/webhooks/errors               # Ver errores recientes
POST /api/v1/webhooks/retry-failed        # Reintentar webhooks fallidos
DELETE /api/v1/webhooks/errors/{error_id} # Marcar error como resuelto
```

## Configuración de Seguridad Avanzada

### Validación de Firma HMAC

Para asegurar que los webhooks vienen realmente de Shopify:

```bash
# En tu archivo .env
SHOPIFY_WEBHOOK_SECRET=whsec_tu_secreto_webhook_aqui
WEBHOOK_SIGNATURE_VALIDATION=true
```

### Configuración del Secreto:

1. **En Admin Shopify**: Al crear el webhook, copia el "Webhook secret"
2. **En tu .env**: Agrega `SHOPIFY_WEBHOOK_SECRET=el_secreto_copiado`
3. **Reinicia tu aplicación** para cargar la nueva configuración

### Validación Personalizada

```python
# El sistema automáticamente valida todas las firmas HMAC
# Configuración adicional disponible:

WEBHOOK_SIGNATURE_VALIDATION=true        # Activar validación (recomendado)
WEBHOOK_ALLOW_UNSIGNED=false            # Rechazar webhooks sin firma
WEBHOOK_SIGNATURE_TOLERANCE=300         # Tolerancia de tiempo (5 min)
```

## Configuración de Pedidos Sin Cliente

### Variables de Entorno Completas

```bash
# === CONFIGURACIÓN DE PEDIDOS SIN CLIENTE ===

# Permitir pedidos sin cliente registrado (recomendado: true)
ALLOW_ORDERS_WITHOUT_CUSTOMER=true

# ID de cliente predeterminado para invitados (opcional)
# Si se configura, todos los pedidos sin cliente usarán este ID
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=

# Requerir email del cliente (recomendado: false para flexibilidad)
REQUIRE_CUSTOMER_EMAIL=false

# Configuración de clientes invitados
GUEST_CUSTOMER_NAME="Cliente Invitado"
GUEST_ORDER_PREFIX="GUEST-"
GUEST_CUSTOMER_EMAIL_SUFFIX="@guest.local"

# Configuración avanzada para pedidos de invitados
CREATE_GUEST_CUSTOMER_RECORD=false      # Crear registro de cliente para invitados
GUEST_CUSTOMER_GROUP_ID=               # Grupo específico para invitados
ALLOW_GUEST_ORDER_UPDATES=true         # Permitir updates de pedidos sin cliente
```

### Estrategias de Configuración:

#### Estrategia 1: Máxima Flexibilidad (Recomendado)
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
REQUIRE_CUSTOMER_EMAIL=false
CREATE_GUEST_CUSTOMER_RECORD=false
# No configurar DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
```
- Pedidos sin cliente se crean con `customer_id=NULL`
- Máxima flexibilidad para checkout de invitados
- Ideal para e-commerce con checkout rápido

#### Estrategia 2: Cliente Unificado para Reportes
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=999
GUEST_CUSTOMER_NAME="Ventas de Invitados"
CREATE_GUEST_CUSTOMER_RECORD=true
```
- Todos los pedidos de invitados se asignan al cliente ID 999
- Facilita reportes y análisis de ventas
- Cliente "Ventas de Invitados" debe existir en RMS

#### Estrategia 3: Registro Automático de Invitados
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
CREATE_GUEST_CUSTOMER_RECORD=true
GUEST_CUSTOMER_EMAIL_SUFFIX="@guest.local"
GUEST_CUSTOMER_GROUP_ID=5
```
- Crea automáticamente registro de cliente para cada invitado
- Usa email temporal si no se proporciona
- Asigna a grupo específico de invitados

#### Estrategia 4: Solo Clientes Registrados
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=false
REQUIRE_CUSTOMER_EMAIL=true
```
- Rechaza pedidos sin cliente registrado
- Fuerza registro antes de compra
- Mayor control pero menor conversión

## Procesamiento Avanzado de Webhooks

### Configuración de Performance

```bash
# === CONFIGURACIÓN DE RENDIMIENTO ===

# Timeouts y límites
WEBHOOK_PROCESSING_TIMEOUT=30           # Timeout por webhook (segundos)
WEBHOOK_MAX_RETRY_ATTEMPTS=3            # Reintentos automáticos
WEBHOOK_RETRY_DELAY=5                   # Delay entre reintentos (segundos)
WEBHOOK_BATCH_SIZE=10                   # Procesar webhooks en lotes

# Rate limiting
WEBHOOK_RATE_LIMIT_PER_MINUTE=60        # Límite de webhooks por minuto
WEBHOOK_BURST_LIMIT=10                  # Límite de ráfaga

# Background processing
WEBHOOK_USE_BACKGROUND_TASKS=true       # Procesar en background
WEBHOOK_BACKGROUND_QUEUE_SIZE=100       # Tamaño de cola
WEBHOOK_WORKER_THREADS=4                # Threads para procesamiento

# Cache y optimizaciones
WEBHOOK_CACHE_CUSTOMER_LOOKUPS=true     # Cache de búsquedas de clientes
WEBHOOK_CACHE_SKU_MAPPINGS=true         # Cache de mapeos SKU
WEBHOOK_CACHE_TTL_SECONDS=300           # TTL del cache (5 minutos)
```

### Filtros de Eventos

```bash
# === FILTROS DE EVENTOS ===

# Estados de pedidos a procesar
WEBHOOK_PROCESS_ORDER_STATUSES=paid,authorized,partially_paid
WEBHOOK_IGNORE_TEST_ORDERS=true
WEBHOOK_MIN_ORDER_AMOUNT=0.01

# Tipos de eventos a procesar
WEBHOOK_ENABLED_EVENTS=orders/create,orders/paid,orders/updated,products/update
WEBHOOK_IGNORED_EVENTS=orders/cancelled,orders/deleted

# Filtros de productos
WEBHOOK_PROCESS_PRODUCT_UPDATES=true
WEBHOOK_IGNORE_DRAFT_PRODUCTS=true
WEBHOOK_PRODUCT_TYPES_TO_SYNC=          # Vacío = todos los tipos
```

## Verificación y Diagnóstico

### 1. Verificar Webhooks Configurados

```bash
# Listar webhooks en Shopify
curl -X GET "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}"

# Verificar webhooks vía API de la aplicación
curl http://localhost:8080/api/v1/webhooks/status

# Ver configuración detallada
curl http://localhost:8080/api/v1/webhooks/config
```

### 2. Probar Endpoints

```bash
# Health check básico
curl -X GET http://localhost:8080/api/v1/webhooks/health

# Probar procesamiento con datos de ejemplo
curl -X POST http://localhost:8080/api/v1/webhooks/test \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Topic: orders/create" \
  -H "X-Shopify-Shop-Domain: tu-tienda.myshopify.com" \
  -d '{
    "id": 12345,
    "name": "#TEST001",
    "email": "test@example.com",
    "financial_status": "paid",
    "line_items": [
      {
        "id": 67890,
        "sku": "TEST-SKU-001",
        "quantity": 1,
        "price": "29.99"
      }
    ]
  }'

# Probar webhook específico de pedido
curl -X POST http://localhost:8080/api/v1/webhooks/shopify/orders/create \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Topic: orders/create" \
  -d @test_order_payload.json
```

### 3. Verificar Logs y Métricas

```bash
# Ver logs en tiempo real
tail -f logs/app.log | grep webhook

# Buscar logs específicos de webhooks
grep "webhook" logs/app.log | tail -20

# Ver métricas actuales
curl http://localhost:8080/api/v1/webhooks/metrics

# Ver actividad reciente
curl http://localhost:8080/api/v1/webhooks/recent-activity?limit=10
```

### 4. Diagnóstico de Problemas

```bash
# Ver errores recientes
curl http://localhost:8080/api/v1/webhooks/errors?limit=20

# Validar webhook específico
curl -X POST http://localhost:8080/api/v1/webhooks/validate/orders-create

# Probar conectividad con Shopify
curl -X GET http://localhost:8080/api/v1/admin/shopify-connection-test
```

## Solución de Problemas Avanzada

### Problema 1: Webhooks No Llegan

#### Diagnóstico Completo:
```bash
# 1. Verificar accesibilidad externa
curl -I https://tu-servidor.com/api/v1/webhooks/health

# 2. Verificar respuesta rápida
time curl https://tu-servidor.com/api/v1/webhooks/health

# 3. Verificar logs de firewall/proxy
tail -f /var/log/nginx/access.log | grep webhook

# 4. Probar desde múltiples ubicaciones
# Usar herramientas como webhookrelay.com o ngrok
```

#### Soluciones Sistemáticas:
1. **SSL/TLS**: Verificar certificado válido
2. **DNS**: Confirmar resolución correcta
3. **Firewall**: Permitir tráfico desde IPs de Shopify
4. **Load Balancer**: Verificar configuración de health checks
5. **Proxy**: Confirmar forwarding correcto de headers

### Problema 2: Validación HMAC Fallida

#### Diagnóstico Detallado:
```bash
# Verificar configuración del secreto
echo "SHOPIFY_WEBHOOK_SECRET: $SHOPIFY_WEBHOOK_SECRET"

# Probar validación manual
curl -X POST http://localhost:8080/api/v1/webhooks/validate-signature \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "test",
    "signature": "sha256=...",
    "secret": "your_secret"
  }'

# Ver logs de validación
grep "signature" logs/app.log | tail -10
```

#### Soluciones:
1. **Regenerar Secreto**: En Admin Shopify → Webhooks → Edit → Regenerate
2. **Verificar Headers**: Confirmar que `X-Shopify-Hmac-Sha256` llega
3. **Debug Temporal**: Desactivar validación solo para testing
4. **Encoding**: Verificar UTF-8 en payload y secreto

### Problema 3: Performance y Timeouts

#### Métricas de Diagnóstico:
```bash
# Ver métricas de performance
curl http://localhost:8080/api/v1/metrics/webhooks/performance

# Monitorear carga del sistema
curl http://localhost:8080/api/v1/metrics/system

# Ver cola de background tasks
curl http://localhost:8080/api/v1/admin/background-tasks-status
```

#### Optimizaciones:
```bash
# Configurar procesamiento optimizado
WEBHOOK_USE_BACKGROUND_TASKS=true
WEBHOOK_BACKGROUND_QUEUE_SIZE=200
WEBHOOK_WORKER_THREADS=8
WEBHOOK_BATCH_SIZE=20

# Habilitar cache agresivo
WEBHOOK_CACHE_CUSTOMER_LOOKUPS=true
WEBHOOK_CACHE_TTL_SECONDS=600

# Optimizar base de datos
WEBHOOK_USE_CONNECTION_POOLING=true
WEBHOOK_DB_POOL_SIZE=20
```

### Problema 4: Pedidos Duplicados

#### Detección:
```bash
# Buscar pedidos duplicados
curl "http://localhost:8080/api/v1/admin/duplicate-orders-check"

# Ver logs de duplicados
grep "duplicate.*order" logs/app.log
```

#### Prevención:
```python
# Configuración de idempotencia
WEBHOOK_ENABLE_IDEMPOTENCY=true
WEBHOOK_IDEMPOTENCY_KEY_TTL=3600
WEBHOOK_DUPLICATE_CHECK_WINDOW=300
```

## Monitoreo y Alertas Avanzadas

### Dashboard de Métricas

```bash
# Métricas principales
GET /api/v1/webhooks/metrics/dashboard

# Respuesta ejemplo:
{
  "summary": {
    "total_received_today": 234,
    "successful_today": 228,
    "failed_today": 6,
    "success_rate": 97.4,
    "avg_processing_time": "1.2s"
  },
  "by_event_type": {
    "orders/create": {"count": 145, "success_rate": 98.6},
    "orders/paid": {"count": 89, "success_rate": 96.6},
    "products/update": {"count": 12, "success_rate": 100.0}
  },
  "performance": {
    "p50_response_time": "0.8s",
    "p95_response_time": "2.1s",
    "p99_response_time": "4.5s"
  },
  "errors": {
    "top_errors": [
      {"error": "SKU not found", "count": 3},
      {"error": "Invalid customer email", "count": 2}
    ]
  }
}
```

### Configuración de Alertas

```bash
# === CONFIGURACIÓN DE ALERTAS ===

# Email alerts
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@tu-empresa.com
ALERT_EMAIL_TO=admin@tu-empresa.com,dev@tu-empresa.com
ALERT_EMAIL_PASSWORD=tu_app_password

# Umbrales de alerta
ALERT_ERROR_RATE_THRESHOLD=5.0          # % de errores
ALERT_RESPONSE_TIME_THRESHOLD=5000      # ms
ALERT_QUEUE_SIZE_THRESHOLD=50           # pending webhooks
ALERT_FAILED_CONSECUTIVE_THRESHOLD=5    # fallos consecutivos

# Slack notifications (opcional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_CHANNEL=#alerts
SLACK_USERNAME=RMS-Shopify-Bot

# Canales de alerta
ALERT_CHANNELS=email,slack,log          # Múltiples canales
```

### Health Checks Automatizados

```bash
# Configurar health checks
curl -X POST http://localhost:8080/api/v1/webhooks/health-check/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "interval_minutes": 5,
    "checks": [
      "endpoint_accessibility",
      "signature_validation",
      "database_connectivity",
      "queue_health",
      "shopify_connectivity"
    ],
    "alert_on_failure": true
  }'
```

## Configuración por Entorno

### Desarrollo Local

```bash
# .env.development
DEBUG=true
LOG_LEVEL=DEBUG

# Usar ngrok para tunneling
NGROK_ENABLED=true
API_BASE_URL=https://abc123.ngrok.io

# Webhooks de desarrollo
SHOPIFY_WEBHOOK_SECRET=dev_secret_123
WEBHOOK_SIGNATURE_VALIDATION=false     # Para testing local

# Cache y performance relajados
WEBHOOK_CACHE_TTL_SECONDS=60
WEBHOOK_PROCESSING_TIMEOUT=60
```

### Staging

```bash
# .env.staging
DEBUG=false
LOG_LEVEL=INFO

# URL de staging
API_BASE_URL=https://staging.tu-servidor.com

# Configuración similar a producción pero relajada
WEBHOOK_SIGNATURE_VALIDATION=true
WEBHOOK_MAX_RETRY_ATTEMPTS=2
WEBHOOK_PROCESSING_TIMEOUT=45

# Alertas solo por log
ALERT_EMAIL_ENABLED=false
ALERT_CHANNELS=log
```

### Producción

```bash
# .env.production
DEBUG=false
LOG_LEVEL=INFO

# URL de producción
API_BASE_URL=https://api.tu-servidor.com

# Máxima seguridad
WEBHOOK_SIGNATURE_VALIDATION=true
WEBHOOK_ALLOW_UNSIGNED=false
WEBHOOK_SIGNATURE_TOLERANCE=300

# Performance optimizada
WEBHOOK_USE_BACKGROUND_TASKS=true
WEBHOOK_WORKER_THREADS=8
WEBHOOK_BATCH_SIZE=25
WEBHOOK_CACHE_TTL_SECONDS=600

# Alertas completas
ALERT_EMAIL_ENABLED=true
ALERT_CHANNELS=email,slack,log
ALERT_ERROR_RATE_THRESHOLD=2.0
```

## Scripts y Automatización

### Scripts de Configuración

```bash
# script/setup-webhooks.sh
#!/bin/bash
set -e

echo "🔧 Configurando webhooks de Shopify..."

# Verificar variables requeridas
if [ -z "$SHOPIFY_SHOP_URL" ] || [ -z "$SHOPIFY_ACCESS_TOKEN" ]; then
    echo "❌ Error: Variables de entorno requeridas no configuradas"
    exit 1
fi

# Configurar webhooks automáticamente
poetry run python configure_webhooks.py --force

# Verificar configuración
echo "✅ Verificando configuración..."
poetry run python configure_webhooks.py --verify

# Test básico
echo "🧪 Ejecutando tests básicos..."
curl -f http://localhost:8080/api/v1/webhooks/health || {
    echo "❌ Health check falló"
    exit 1
}

echo "🎉 Configuración de webhooks completada!"
```

### Monitoreo Automático

```bash
# scripts/monitor-webhooks.sh
#!/bin/bash

# Verificar métricas cada 5 minutos
while true; do
    METRICS=$(curl -s http://localhost:8080/api/v1/webhooks/metrics)
    ERROR_RATE=$(echo $METRICS | jq -r '.error_rate')
    
    if (( $(echo "$ERROR_RATE > 5.0" | bc -l) )); then
        echo "⚠️  Alta tasa de errores: $ERROR_RATE%"
        # Enviar alerta
        curl -X POST http://localhost:8080/api/v1/admin/send-alert \
            -d "message=Alta tasa de errores en webhooks: $ERROR_RATE%"
    fi
    
    sleep 300
done
```

## Mejores Prácticas y Recomendaciones

### 1. Seguridad
- ✅ **Siempre validar firmas HMAC** en producción
- ✅ **Usar HTTPS** para todos los endpoints
- ✅ **No loguear datos sensibles** (tokens, passwords, etc.)
- ✅ **Implementar rate limiting** para prevenir ataques
- ✅ **Validar payloads** antes del procesamiento
- ✅ **Usar conexiones seguras** a base de datos

### 2. Rendimiento y Escalabilidad
- ✅ **Responder en < 5 segundos** siempre
- ✅ **Usar procesamiento en background** para operaciones pesadas
- ✅ **Implementar cache** para datos frecuentes
- ✅ **Configurar connection pooling** para base de datos
- ✅ **Monitorear métricas** de performance constantemente
- ✅ **Usar índices** apropiados en base de datos

### 3. Confiabilidad
- ✅ **Implementar retry logic** con backoff exponencial
- ✅ **Loguear todos los eventos** para auditoría
- ✅ **Configurar health checks** automatizados
- ✅ **Tener plan de rollback** documentado
- ✅ **Implementar circuit breakers** para APIs externas
- ✅ **Monitorear y alertar** proactivamente

### 4. Mantenimiento
- ✅ **Documentar cambios** en webhooks
- ✅ **Versionar configuraciones** de webhooks
- ✅ **Automatizar testing** de webhooks
- ✅ **Limpiar logs antiguos** regularmente
- ✅ **Actualizar documentación** con cambios
- ✅ **Capacitar al equipo** en troubleshooting

### 5. Testing y Quality Assurance
- ✅ **Probar con múltiples escenarios** de pedidos
- ✅ **Simular fallos** de red y recuperación
- ✅ **Validar con pedidos de invitados** y registrados
- ✅ **Probar rate limiting** y timeouts
- ✅ **Validar idempotencia** de operaciones
- ✅ **Automatizar tests** de regresión

## Recursos Adicionales

### Herramientas de Testing
- [Webhook.site](https://webhook.site/) - Capturar y inspeccionar webhooks
- [ngrok](https://ngrok.com/) - Túneles seguros para testing local  
- [Postman](https://postman.com/) - Testing de APIs y webhooks
- [Insomnia](https://insomnia.rest/) - Cliente REST alternativo

### Documentación Oficial
- [Shopify Webhooks Guide](https://shopify.dev/docs/apps/webhooks)
- [Shopify Orders API](https://shopify.dev/docs/api/admin-rest/2025-04/resources/order)
- [HMAC Validation](https://shopify.dev/docs/apps/webhooks/configuration/https#step-5-verify-the-webhook)

### Monitoreo y Observabilidad
- [Grafana Dashboard](./monitoring/grafana-webhook-dashboard.json) - Incluido
- [Prometheus Metrics](./monitoring/prometheus-config.yml) - Configuración incluida
- [ELK Stack Integration](./monitoring/elasticsearch-mappings.json) - Logs estructurados

### Scripts de Utilidad
- `scripts/test-webhook-locally.py` - Testing local completo
- `scripts/webhook-load-test.py` - Pruebas de carga
- `scripts/cleanup-failed-webhooks.py` - Limpieza de webhooks fallidos
- `scripts/webhook-replay.py` - Reproducir webhooks para debugging

---

## Contacto y Soporte

### Soporte Técnico
- **Email**: enzo@oneclick.cr
- **Documentación**: http://localhost:8080/docs (API docs cuando esté corriendo)
- **Logs Detallados**: `logs/app.log` para debugging completo
- **Issues**: GitHub Issues para reportar problemas

### Escalation Path
1. **Verificar logs**: `tail -f logs/app.log | grep webhook`
2. **Revisar métricas**: `curl http://localhost:8080/api/v1/webhooks/metrics`
3. **Probar endpoints**: Scripts de diagnóstico incluidos
4. **Contactar soporte**: Con logs y métricas específicas

La configuración correcta de webhooks es **crítica** para la sincronización automática y en tiempo real entre Shopify y RMS. Una implementación robusta asegura la integridad de datos y la experiencia del cliente.

---

*Documento actualizado: Enero 2025*  
*Versión del sistema: 2.5*
*Compatible con: Shopify API 2025-04, FastAPI, Python 3.13+*
*Última revisión de configuración: 30/01/2025*