# Motor de Sincronización Automática RMS → Shopify

## Descripción General

El motor de sincronización automática detecta cambios en la base de datos RMS usando la tabla `Item.LastUpdated` y sincroniza automáticamente los productos modificados hacia Shopify. El sistema funciona en background desde el arranque de la aplicación con uvicorn.

## ¿Cómo Funciona?

### 1. Detección de Cambios Basada en Timestamps

El sistema utiliza la tabla `Item` de RMS que tiene un campo `LastUpdated` que se actualiza automáticamente cuando hay modificaciones en los productos.

**Query Principal:**
```sql
SELECT TOP 500
    ID,
    LastUpdated
FROM Item 
WHERE LastUpdated > :last_check
    AND LastUpdated IS NOT NULL
ORDER BY LastUpdated DESC
```

### 2. Vinculación con View_Items

Una vez detectados los items modificados, el sistema obtiene los datos completos desde `View_Items`:

```sql
SELECT 
    ItemID, C_ARTICULO, Description, Price, Quantity,
    Familia, Categoria, color, talla, CCOD,
    SalePrice, SaleStartDate, SaleEndDate,
    ExtendedCategory, Tax, Exis00, Exis57
FROM View_Items 
WHERE ItemID IN (IDs_modificados)
    AND C_ARTICULO IS NOT NULL 
    AND Description IS NOT NULL
    AND Price > 0
```

### 3. Sincronización Automática

- Agrupa productos por **CCOD** para sincronizar productos completos con variantes
- Ejecuta sincronización en lotes pequeños para evitar sobrecarga
- Aplica rate limiting para respetar límites de API de Shopify
- Registra métricas y estadísticas detalladas

## Configuración

### Variables de Entorno

```bash
# === CONFIGURACIÓN DE SINCRONIZACIÓN AUTOMÁTICA ===

# Habilitar sincronización programada (requerido)
ENABLE_SCHEDULED_SYNC=true

# Intervalo de verificación de cambios (en minutos)
SYNC_INTERVAL_MINUTES=5

# Tamaño de lote para sincronización
SYNC_BATCH_SIZE=10

# Máximo trabajos concurrentes
SYNC_MAX_CONCURRENT_JOBS=3

# Timeout para operaciones de sync (minutos)
SYNC_TIMEOUT_MINUTES=30

# Horas para sincronización incremental
RMS_SYNC_INCREMENTAL_HOURS=24
```

### Configuración Recomendada por Entorno

#### Desarrollo
```bash
ENABLE_SCHEDULED_SYNC=true
SYNC_INTERVAL_MINUTES=10
SYNC_BATCH_SIZE=5
SYNC_MAX_CONCURRENT_JOBS=1
```

#### Producción
```bash
ENABLE_SCHEDULED_SYNC=true
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_SIZE=10
SYNC_MAX_CONCURRENT_JOBS=3
```

## Inicio Automático

### Al Arrancar con Uvicorn

El sistema se inicia automáticamente cuando arrancas la aplicación:

```bash
# Desarrollo
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Proceso de Startup

1. **Configuración**: Se cargan variables de entorno
2. **Verificación**: Se verifican conexiones a RMS y Shopify
3. **Inicialización**: Se inicializa el `ChangeDetector`
4. **Scheduler**: Se inicia el scheduler automático si `ENABLE_SCHEDULED_SYNC=true`
5. **Monitoreo**: Comienza la detección de cambios cada `SYNC_INTERVAL_MINUTES`

### Logs de Startup

```
🚀 Iniciando RMS-Shopify Integration...
✅ Sistema de logging configurado
✅ Configuración verificada
✅ Conexión a RMS verificada
✅ Conexión a Shopify verificada
✅ Servicios asíncronos inicializados
🔍 Change Detector inicializado correctamente
🕒 Iniciando scheduler con detección automática de cambios
✅ Scheduler iniciado correctamente
🔄 Iniciando monitoreo automático cada 5 minutos
🎉 Aplicación iniciada correctamente
```

## APIs de Control

### Monitoreo del Sistema

```bash
# Estado general del sistema
GET /api/v1/sync/monitor/status

# Estadísticas detalladas
GET /api/v1/sync/monitor/stats

# Salud del sistema de monitoreo
GET /api/v1/sync/monitor/health

# Actividad reciente
GET /api/v1/sync/monitor/recent-activity

# Configuración actual
GET /api/v1/sync/monitor/config
```

### Control Manual

```bash
# Trigger sincronización manual inmediata
POST /api/v1/sync/monitor/trigger

# Forzar sincronización completa
POST /api/v1/sync/monitor/force-full-sync

# Actualizar intervalo de verificación
PUT /api/v1/sync/monitor/interval
{
  "interval_minutes": 10
}
```

### Ejemplos de Uso

#### Verificar Estado
```bash
curl -X GET http://localhost:8000/api/v1/sync/monitor/status
```

**Respuesta:**
```json
{
  "status": "success",
  "data": {
    "running": true,
    "task_active": true,
    "sync_interval_minutes": 5,
    "change_detection_enabled": true,
    "monitoring_active": true,
    "change_detector": {
      "total_checks": 145,
      "changes_detected": 12,
      "items_synced": 45,
      "last_sync_time": "2025-07-03T10:15:00Z",
      "errors": 0,
      "running": true,
      "last_check_time": "2025-07-03T10:20:00Z"
    }
  },
  "message": "Estado del sistema obtenido correctamente"
}
```

#### Ejecutar Sincronización Manual
```bash
curl -X POST http://localhost:8000/api/v1/sync/monitor/trigger
```

#### Cambiar Intervalo de Verificación
```bash
curl -X PUT http://localhost:8000/api/v1/sync/monitor/interval \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 3}'
```

## Flujo Detallado del Motor

### 1. Ciclo de Verificación

```
┌─────────────────────────────────────┐
│ Cada SYNC_INTERVAL_MINUTES minutos │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ Query Item tabla por LastUpdated    │
│ WHERE LastUpdated > last_check_time │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ ¿Hay cambios detectados?            │
└─────────────────┬───────────────────┘
                  │ SI
                  ▼
┌─────────────────────────────────────┐
│ Query View_Items para IDs detectados│
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ Agrupar por CCOD                    │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ Sincronizar con Shopify (lotes)     │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ Actualizar last_check_time          │
│ Registrar métricas                  │
└─────────────────────────────────────┘
```

### 2. Tipos de Cambios Detectados

- **Productos Nuevos**: Items con ID que no han sido sincronizados antes
- **Productos Modificados**: Items existentes con LastUpdated reciente
- **Cambios de Precio**: Detección de SalePrice vs Price
- **Cambios de Inventario**: Cambios en Quantity o estado de stock
- **Cambios de Estado**: Productos activados/desactivados

### 3. Estrategia de Sincronización

#### Por CCOD (Preferido)
- Sincroniza productos completos con todas sus variantes
- Mantiene consistencia entre tallas y colores
- Más eficiente para productos con múltiples opciones

#### Por SKU Individual
- Para productos sin CCOD válido
- Sincronización directa de variante específica
- Fallback cuando no hay agrupación posible

### 4. Rate Limiting y Optimización

- **Lotes pequeños**: Máximo 5 CCODs por vez
- **Pausas**: 1-3 segundos entre sincronizaciones
- **Rate limiting**: Respeta límites de API Shopify (2 calls/segundo)
- **Reintentos**: 3 intentos con backoff exponencial
- **Timeouts**: 30 segundos por operación

## Monitoreo y Logs

### Métricas Importantes

```json
{
  "total_checks": 1250,
  "changes_detected": 85,
  "items_synced": 342,
  "last_sync_time": "2025-07-03T10:20:00Z",
  "errors": 2,
  "success_rate": 97.6,
  "average_sync_time": "2.3s",
  "items_per_check": 2.8
}
```

### Logs de Ejemplo

```
2025-07-03 10:20:00 - INFO - 🔍 Verificando cambios desde 2025-07-03T10:15:00Z
2025-07-03 10:20:01 - INFO - 🔔 Detectados 3 items modificados en RMS
2025-07-03 10:20:01 - DEBUG - Obtenidos 3 productos válidos de View_Items
2025-07-03 10:20:02 - INFO - 🔄 Iniciando sincronización automática para 3 items
2025-07-03 10:20:02 - INFO - Sincronizando 2 CCODs modificados
2025-07-03 10:20:05 - INFO - ✅ Sincronización automática completada: 3 productos procesados
```

### Alertas y Errores

#### Errores Comunes
- **Conexión RMS**: Verificar credenciales y conectividad
- **SKU no encontrado**: Item en RMS pero no en View_Items
- **Rate limit**: Shopify API temporalmente bloqueada
- **Timeout**: Sincronización tardó más de 30 segundos

#### Configuración de Alertas
```bash
# Variables para alertas automáticas
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@tu-empresa.com
```

## Características Avanzadas

### 1. Auto-recovery

Si el detector se detiene, el scheduler lo reinicia automáticamente:

```
⚠️ Detector de cambios no está ejecutándose, reiniciando...
🔄 Iniciando monitoreo automático cada 5 minutos
```

### 2. Sincronización Nocturna

Sincronización completa automática diaria a las 2 AM:

```
🌙 Ejecutando sincronización completa nocturna
```

### 3. Health Checks

Verificación cada 5 minutos del estado del detector:

```bash
GET /api/v1/sync/monitor/health
```

### 4. Estadísticas en Tiempo Real

Dashboard de métricas accesible via API:

```bash
GET /api/v1/sync/monitor/stats
```

## Solución de Problemas

### Problema: El motor no se inicia

**Síntomas:**
- No hay logs de "🕒 Iniciando scheduler"
- Estado muestra `"running": false`

**Soluciones:**
```bash
# Verificar configuración
curl http://localhost:8000/api/v1/sync/monitor/config

# Verificar variable de entorno
echo $ENABLE_SCHEDULED_SYNC

# Debe ser 'true'
export ENABLE_SCHEDULED_SYNC=true
```

### Problema: Cambios no se detectan

**Síntomas:**
- `"changes_detected": 0` siempre
- Items modificados en RMS no aparecen en Shopify

**Verificaciones:**
```sql
-- Verificar que LastUpdated se actualiza en Item
SELECT TOP 10 ID, LastUpdated 
FROM Item 
ORDER BY LastUpdated DESC

-- Verificar conexión Item → View_Items
SELECT COUNT(*) FROM Item i
JOIN View_Items v ON i.ID = v.ItemID
WHERE i.LastUpdated > DATEADD(hour, -1, GETDATE())
```

### Problema: Errores de sincronización

**Síntomas:**
- `"errors": > 0` en estadísticas
- Logs muestran errores repetidos

**Soluciones:**
```bash
# Verificar logs detallados
curl http://localhost:8000/api/v1/sync/monitor/stats

# Trigger manual para debugging
curl -X POST http://localhost:8000/api/v1/sync/monitor/trigger

# Verificar conexiones
curl http://localhost:8000/health
```

### Problema: Rendimiento lento

**Síntomas:**
- Sincronización tarda más de 30 segundos
- Rate limiting frecuente

**Optimizaciones:**
```bash
# Reducir batch size
PUT /api/v1/sync/monitor/interval
{"interval_minutes": 10}

# En .env
SYNC_BATCH_SIZE=5
SYNC_MAX_CONCURRENT_JOBS=1
```

## Scripts de Utilidad

### Verificar Estado del Motor
```bash
#!/bin/bash
# check_sync_engine.sh

echo "=== Estado del Motor de Sincronización ==="
curl -s http://localhost:8000/api/v1/sync/monitor/status | python -m json.tool

echo -e "\n=== Estadísticas ==="
curl -s http://localhost:8000/api/v1/sync/monitor/stats | python -m json.tool

echo -e "\n=== Salud ==="
curl -s http://localhost:8000/api/v1/sync/monitor/health | python -m json.tool
```

### Trigger Sincronización y Monitorear
```bash
#!/bin/bash
# manual_sync.sh

echo "Ejecutando sincronización manual..."
curl -X POST http://localhost:8000/api/v1/sync/monitor/trigger

echo "Esperando 10 segundos..."
sleep 10

echo "Estado actualizado:"
curl -s http://localhost:8000/api/v1/sync/monitor/recent-activity | python -m json.tool
```

## Conclusión

El motor de sincronización automática proporciona:

- ✅ **Detección de cambios en tiempo real** usando `Item.LastUpdated`
- ✅ **Inicio automático** con uvicorn
- ✅ **Configuración flexible** via variables de entorno
- ✅ **APIs de control** para monitoreo y gestión
- ✅ **Rate limiting** y optimización automática
- ✅ **Auto-recovery** en caso de fallos
- ✅ **Métricas detalladas** y logging completo
- ✅ **Sincronización inteligente** por CCOD

Con este sistema, cualquier cambio en RMS se reflejará automáticamente en Shopify dentro del intervalo configurado, manteniendo ambos sistemas sincronizados sin intervención manual.

---

*Documento actualizado: Julio 2025*  
*Compatible con: RMS SQL Server, Shopify API 2025-04, FastAPI, Python 3.9+*