# Configuración de Webhooks para Sincronización Shopify → RMS

## Descripción General

Los webhooks permiten que Shopify notifique automáticamente a tu sistema RMS cuando ocurren eventos específicos (como creación de pedidos). Esto habilita la sincronización en tiempo real sin necesidad de consultar constantemente la API de Shopify.

## ¿Qué son los Webhooks?

Un webhook es una notificación HTTP que Shopify envía a tu servidor cuando ocurre un evento específico. En lugar de que tu aplicación consulte constantemente si hay nuevos pedidos, Shopify te notifica inmediatamente cuando se crea o actualiza un pedido.

### Flujo de Webhooks:
1. **Cliente realiza pedido** en Shopify
2. **Shopify detecta el evento** (orden creada/actualizada)
3. **Shopify envía POST** a tu endpoint configurado
4. **Tu sistema procesa** el pedido y lo sincroniza con RMS
5. **Respuesta rápida** (< 5 segundos) para confirmar recepción

## Configuración de Webhooks

### Método 1: Script Automático (Recomendado)

Utiliza el script `configure_webhooks.py` incluido en el proyecto:

```bash
# 1. Configurar la URL base de tu servicio
export API_BASE_URL="https://tu-servidor.com"

# 2. Ejecutar el script de configuración
poetry run python configure_webhooks.py
```

El script configurará automáticamente estos webhooks:
- **orders/create**: Pedidos nuevos
- **orders/updated**: Pedidos actualizados  
- **orders/paid**: Pedidos pagados

### Método 2: Configuración Manual en Admin Shopify

#### Paso 1: Acceder a Configuración de Webhooks
1. Inicia sesión en tu Admin de Shopify
2. Ve a **Settings** (Configuración)
3. Selecciona **Notifications** (Notificaciones)
4. Desplázate hasta la sección **Webhooks**
5. Haz clic en **Create webhook**

#### Paso 2: Configurar Webhook para Pedidos Creados
```
Event: Order creation
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/order/created
API version: 2025-04 (o la más reciente)
```

#### Paso 3: Configurar Webhook para Pedidos Actualizados
```
Event: Order updates  
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/order/updated
API version: 2025-04 (o la más reciente)
```

#### Paso 4: Configurar Webhook para Pedidos Pagados
```
Event: Order paid
Format: JSON
URL: https://tu-servidor.com/api/v1/webhooks/order/updated
API version: 2025-04 (o la más reciente)
```

### Método 3: Configuración via API REST

```bash
# Webhook para pedidos creados
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/create",
      "address": "https://tu-servidor.com/api/v1/webhooks/order/created",
      "format": "json"
    }
  }'

# Webhook para pedidos actualizados
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/updated", 
      "address": "https://tu-servidor.com/api/v1/webhooks/order/updated",
      "format": "json"
    }
  }'

# Webhook para pedidos pagados
curl -X POST "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/paid",
      "address": "https://tu-servidor.com/api/v1/webhooks/order/updated", 
      "format": "json"
    }
  }'
```

## Endpoints de Webhook en tu Sistema

Tu aplicación expone estos endpoints para recibir webhooks:

### Endpoints Principales
- `POST /api/v1/webhooks/order/created` - Procesa pedidos nuevos
- `POST /api/v1/webhooks/order/updated` - Procesa pedidos actualizados
- `POST /api/v1/webhooks/shopify` - Endpoint genérico para todos los webhooks

### Endpoints de Utilidad  
- `GET /api/v1/webhooks/metrics` - Métricas de procesamiento
- `POST /api/v1/webhooks/test` - Prueba el procesamiento
- `GET /api/v1/webhooks/test` - Verifica que el endpoint funciona

## Configuración de Seguridad

### Validación de Firma HMAC

Para asegurar que los webhooks vienen realmente de Shopify, configura la validación de firma:

```bash
# En tu archivo .env
SHOPIFY_WEBHOOK_SECRET=tu_secreto_webhook_aqui
```

### Cómo Configurar el Secreto:

1. **En Admin Shopify**: Al crear el webhook, anota el "Webhook secret"
2. **En tu .env**: Agrega `SHOPIFY_WEBHOOK_SECRET=el_secreto_copiado`
3. **Reinicia tu aplicación** para cargar la nueva configuración

El sistema automáticamente validará todas las firmas HMAC de webhooks entrantes.

## Configuración de Pedidos Sin Cliente

Para manejar pedidos de invitados (sin cliente registrado):

### Variables de Entorno

```bash
# === CONFIGURACIÓN DE PEDIDOS SIN CLIENTE ===

# Permitir pedidos sin cliente (recomendado: true)
ALLOW_ORDERS_WITHOUT_CUSTOMER=true

# ID de cliente predeterminado para invitados (opcional)
# Si se configura, todos los pedidos sin cliente usarán este ID
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=

# Requerir email del cliente (recomendado: false para flexibilidad)
REQUIRE_CUSTOMER_EMAIL=false

# Nombre para mostrar en clientes invitados
GUEST_CUSTOMER_NAME="Cliente Invitado"
```

### Opciones de Configuración:

#### Opción 1: Permitir NULL (Más Flexible)
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
REQUIRE_CUSTOMER_EMAIL=false
# No configurar DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
```
- Los pedidos sin cliente se crean con `customer_id=NULL`
- Máxima flexibilidad para checkout de invitados

#### Opción 2: Cliente Predeterminado (Para Reportes)
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=999
REQUIRE_CUSTOMER_EMAIL=false
```
- Todos los pedidos de invitados se asignan al cliente ID 999
- Facilita reportes y análisis de ventas de invitados

#### Opción 3: Requerir Cliente (Más Estricto)
```bash
ALLOW_ORDERS_WITHOUT_CUSTOMER=false
REQUIRE_CUSTOMER_EMAIL=true
```
- Rechaza pedidos que no tengan cliente con email
- Fuerza registro antes de compra

## Verificación de Configuración

### 1. Verificar Webhooks Existentes

```bash
# Listar webhooks configurados
curl -X GET "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}"
```

### 2. Probar Endpoint Local

```bash
# Verificar que el endpoint responde
curl -X GET http://localhost:8000/api/v1/webhooks/test

# Probar procesamiento de webhook
curl -X POST http://localhost:8000/api/v1/webhooks/test \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "orders/create",
    "payload": {
      "id": "12345",
      "name": "#1001",
      "email": "test@example.com"
    }
  }'
```

### 3. Verificar Logs de Aplicación

```bash
# Ver logs en tiempo real
tail -f logs/app.log

# Buscar logs de webhooks específicamente
grep "webhook" logs/app.log | tail -20
```

## Solución de Problemas

### Problema 1: Webhooks No Llegan

#### Posibles Causas:
- URL incorrecta o inaccesible desde internet
- Servidor no responde en menos de 5 segundos
- Firewall bloqueando conexiones de Shopify
- SSL/HTTPS no configurado correctamente

#### Soluciones:
```bash
# 1. Verificar que tu servidor es accesible
curl -I https://tu-servidor.com/api/v1/webhooks/test

# 2. Verificar que responde rápidamente
time curl https://tu-servidor.com/api/v1/webhooks/test

# 3. Probar endpoint con datos de ejemplo
curl -X POST https://tu-servidor.com/api/v1/webhooks/order/created \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Topic: orders/create" \
  -d '{"id":123, "name":"#1001"}'
```

### Problema 2: Error de Validación HMAC

#### Síntomas:
- Logs muestran "Invalid webhook signature"
- Webhooks se reciben pero no se procesan

#### Soluciones:
```bash
# 1. Verificar que el secreto esté configurado
echo $SHOPIFY_WEBHOOK_SECRET

# 2. Regenerar secreto en Shopify Admin
# 3. Actualizar variable de entorno y reiniciar

# 4. Temporalmente deshabilitar validación para pruebas
# En config.py, comentar la validación HMAC
```

### Problema 3: Pedidos Sin Cliente No Se Procesan

#### Verificar Configuración:
```bash
# Verificar variables de entorno
echo "ALLOW_ORDERS_WITHOUT_CUSTOMER: $ALLOW_ORDERS_WITHOUT_CUSTOMER"
echo "REQUIRE_CUSTOMER_EMAIL: $REQUIRE_CUSTOMER_EMAIL"
echo "DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS: $DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS"
```

#### Revisar Logs:
```bash
# Buscar errores relacionados con clientes
grep -i "customer" logs/app.log | grep -i "error"

# Ver procesamiento de pedidos específicos
grep "order.*customer" logs/app.log
```

### Problema 4: Timeout en Webhooks

#### Síntomas:
- Shopify reintenta webhooks múltiples veces
- Logs muestran procesamiento lento

#### Optimizaciones:
1. **Procesamiento en Background**: Los webhooks ya usan `BackgroundTasks`
2. **Respuesta Rápida**: Responder inmediatamente y procesar después
3. **Batch Processing**: Agrupar operaciones de base de datos
4. **Cache**: Usar Redis para datos frecuentes

```python
# Ejemplo de respuesta rápida
@router.post("/order/created")
async def order_created_webhook(request: Request, background_tasks: BackgroundTasks):
    # Respuesta inmediata (< 1 segundo)
    background_tasks.add_task(process_order, payload)
    return {"status": "received", "processing": "background"}
```

## Monitoreo y Métricas

### Ver Métricas de Webhooks

```bash
# Obtener métricas actuales
curl http://localhost:8000/api/v1/webhooks/metrics

# Ejemplo de respuesta:
{
  "total_received": 150,
  "successful": 142,
  "failed": 8,
  "average_processing_time": 2.3,
  "last_webhook": "2025-07-02T10:30:00Z"
}
```

### Configurar Alertas

```bash
# Variables para alertas por email
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_FROM=alerts@tu-empresa.com
ALERT_EMAIL_TO=admin@tu-empresa.com
ALERT_EMAIL_PASSWORD=tu_password_app
```

## Buenas Prácticas

### 1. Seguridad
- ✅ Siempre validar firmas HMAC
- ✅ Usar HTTPS para todos los endpoints
- ✅ No loguear datos sensibles (tokens, passwords)
- ✅ Implementar rate limiting

### 2. Rendimiento  
- ✅ Responder a webhooks en < 5 segundos
- ✅ Usar procesamiento en background
- ✅ Implementar retry logic para fallos
- ✅ Monitorear métricas de rendimiento

### 3. Mantenimiento
- ✅ Loguear todos los webhooks recibidos
- ✅ Implementar health checks
- ✅ Tener plan de rollback
- ✅ Documentar cambios en webhooks

### 4. Testing
- ✅ Probar con pedidos de diferentes tipos
- ✅ Probar escenarios de error
- ✅ Validar con pedidos de invitados
- ✅ Simular fallos de red

## Configuración de Desarrollo vs Producción

### Desarrollo
```bash
# Usar ngrok para túnel local
ngrok http 8000

# Configurar webhook con URL de ngrok
https://abc123.ngrok.io/api/v1/webhooks/order/created

# Deshabilitar validación HMAC si es necesario
SHOPIFY_WEBHOOK_SECRET=
```

### Producción
```bash
# URL real del servidor
API_BASE_URL=https://tu-servidor.com

# Secreto webhook configurado
SHOPIFY_WEBHOOK_SECRET=whsec_tu_secreto_real

# Logging habilitado
LOG_LEVEL=INFO
LOG_FILE_PATH=/var/log/rms-shopify/app.log

# Alertas habilitadas
ALERT_EMAIL_ENABLED=true
```

## Comandos Útiles

### Configuración Inicial
```bash
# Verificar configuración
poetry run python -c "from app.core.config import get_settings; print(get_settings().SHOPIFY_SHOP_URL)"

# Configurar webhooks automáticamente
poetry run python configure_webhooks.py

# Verificar estado de la aplicación
curl http://localhost:8000/health
```

### Diagnóstico
```bash
# Ver últimos webhooks procesados
curl http://localhost:8000/api/v1/webhooks/metrics

# Probar webhook manualmente
curl -X POST http://localhost:8000/api/v1/webhooks/test \
  -H "Content-Type: application/json" \
  -d '{"topic": "orders/create", "payload": {"test": true}}'

# Monitorear logs en tiempo real
tail -f logs/app.log | grep webhook
```

### Mantenimiento
```bash
# Listar webhooks configurados en Shopify
curl "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}"

# Eliminar webhook específico
curl -X DELETE "https://tu-tienda.myshopify.com/admin/api/2025-04/webhooks/{WEBHOOK_ID}.json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}"

# Reconfigurar todos los webhooks
poetry run python configure_webhooks.py --force
```

---

## Contacto y Soporte

Para problemas con la configuración de webhooks:

1. **Verificar logs**: Revisar `logs/app.log` para errores específicos
2. **Probar endpoints**: Usar los comandos de diagnóstico anteriores
3. **Verificar configuración**: Validar variables de entorno
4. **Consultar métricas**: Revisar `/api/v1/webhooks/metrics`

La configuración correcta de webhooks es crucial para la sincronización automática y en tiempo real entre Shopify y RMS.

---

*Documento actualizado: Julio 2025*  
*Compatible con: Shopify API 2025-04, FastAPI, Python 3.9+*