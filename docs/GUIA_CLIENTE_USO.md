# 📘 Guía del Cliente - Sistema de Integración RMS-Shopify

> **Guía práctica para configurar, operar y monitorear la sincronización automática entre su sistema RMS y tienda Shopify**

---

## 📋 Tabla de Contenidos

1. [¿Qué hace este sistema?](#1--qué-hace-este-sistema)
2. [Requisitos Previos](#2--requisitos-previos)
3. [Configuración Inicial](#3--configuración-inicial)
4. [Instalación en Windows](#4--instalación-en-windows)
5. [Levantando el Servicio](#5--levantando-el-servicio)
6. [Monitoreo de la Sincronización](#6--monitoreo-de-la-sincronización)
7. [Operaciones Comunes](#7--operaciones-comunes)
8. [Solución de Problemas](#8--solución-de-problemas)
9. [Contacto y Soporte](#9--contacto-y-soporte)

---

## 1. 🎯 ¿Qué hace este sistema?

Este sistema mantiene **sincronizados automáticamente** sus productos, inventarios y precios entre su base de datos RMS (punto de venta físico) y su tienda en línea Shopify.

### Características Principales

✅ **Sincronización Automática Cada 5 Minutos**
- El sistema detecta automáticamente productos nuevos o modificados en RMS
- Los cambios se reflejan en Shopify sin intervención manual

✅ **Sincronización Completa Nocturna**
- Cada noche se realiza una verificación completa de todo el catálogo
- Asegura que no haya diferencias entre RMS y Shopify

✅ **Sincronización de Pedidos**
- Los pedidos de Shopify se envían automáticamente a RMS
- Actualiza el inventario en ambos sistemas

✅ **Monitoreo en Tiempo Real**
- Panel web para ver el estado de la sincronización
- Logs detallados de todas las operaciones
- Alertas automáticas en caso de errores

### ¿Qué se sincroniza?

| Desde RMS → Shopify | Desde Shopify → RMS |
|---------------------|---------------------|
| ✓ Productos nuevos  | ✓ Pedidos nuevos |
| ✓ Precios           | ✓ Datos de clientes |
| ✓ Inventario/Stock  | ✓ Métodos de pago |
| ✓ Descripciones     | |
| ✓ Imágenes          | |
| ✓ Categorías        | |

---

## 2. ✅ Requisitos Previos

### A. Requisitos Técnicos

#### Computadora/Servidor Windows
- **Sistema Operativo**: Windows 10/11 Professional o Windows Server 2016+
- **Procesador**: 2 núcleos (4 núcleos recomendado)
- **Memoria RAM**: Mínimo 4GB (8GB recomendado)
- **Disco Duro**: 20GB de espacio libre
- **Conexión a Internet**: Estable y permanente

#### Software Necesario
- ✅ **Docker Desktop for Windows** (lo instalaremos en esta guía)
- ✅ Acceso a la base de datos RMS (SQL Server)
- ✅ Navegador web moderno (Chrome, Edge, Firefox)

### B. Credenciales Requeridas

Antes de comenzar, asegúrese de tener esta información a mano:

#### 1. Datos de Conexión RMS
```
✓ Servidor RMS (IP o nombre): __________________
✓ Puerto (usualmente 1433): __________________
✓ Nombre de la base de datos: __________________
✓ Usuario de acceso: __________________
✓ Contraseña: __________________
```

#### 2. Credenciales Shopify
```
✓ URL de su tienda: __________________.myshopify.com
✓ Access Token de API: __________________
✓ Webhook Secret: __________________
```

**¿Cómo obtener las credenciales de Shopify?**
1. Ingrese a su panel de Shopify Admin
2. Vaya a **Configuración → Apps y canales de venta → Desarrollar aplicaciones**
3. Cree una nueva aplicación privada
4. Configure los permisos necesarios (productos, inventario, pedidos)
5. Copie el **Admin API access token**

---

## 3. ⚙️ Configuración Inicial

### Archivo de Configuración (`.env`)

El sistema se configura mediante un archivo llamado `.env`. Este archivo contiene todos los parámetros necesarios para operar.

#### 📝 Pasos para Configurar

1. **Localize el archivo `.env.example`** en la carpeta del proyecto
2. **Créelo una copia** y renómbrelo a `.env`
3. **Edite el archivo** con un editor de texto (Notepad, Notepad++)

#### 🔑 Parámetros Críticos para Buena Sincronización

```bash
# ===================================
# 1. CONEXIÓN A RMS
# ===================================
RMS_DB_HOST=192.168.1.100          # IP de su servidor RMS
RMS_DB_PORT=1433                    # Puerto SQL Server (no cambiar)
RMS_DB_NAME=RMS_Database            # Nombre de su base de datos RMS
RMS_DB_USER=usuario_rms             # Usuario con permisos de lectura
RMS_DB_PASSWORD=contraseña_segura   # Contraseña del usuario
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server  # Driver (no cambiar)

# ===================================
# 2. CONEXIÓN A SHOPIFY
# ===================================
SHOPIFY_SHOP_URL=su-tienda.myshopify.com     # URL de su tienda
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx     # Token de API
SHOPIFY_API_VERSION=2025-04                   # Versión API (no cambiar)
SHOPIFY_WEBHOOK_SECRET=secret_webhook_123     # Secret para webhooks

# ===================================
# 3. MOTOR DE SINCRONIZACIÓN AUTOMÁTICA
# ===================================

# Sincronización continua (cada X minutos)
ENABLE_SCHEDULED_SYNC=true          # ✅ SIEMPRE EN true
SYNC_INTERVAL_MINUTES=5             # ⏱️ Cada cuántos minutos sincronizar
                                    # Recomendado: 5 minutos
                                    # Mínimo: 2 minutos
                                    # Máximo: 60 minutos

# Tamaño de lotes para sincronización
SYNC_BATCH_SIZE=100                 # 📦 Cuántos productos por lote
                                    # Valores recomendados:
                                    # - Conexión rápida: 100-200
                                    # - Conexión normal: 50-100
                                    # - Conexión lenta: 25-50

# Trabajos concurrentes
SYNC_MAX_CONCURRENT_JOBS=3          # 🔄 Sincronizaciones en paralelo
                                    # Recomendado: 3
                                    # Rango válido: 1-5

# ===================================
# 4. SINCRONIZACIÓN COMPLETA NOCTURNA
# ===================================
ENABLE_FULL_SYNC_SCHEDULE=true      # ✅ SIEMPRE EN true
FULL_SYNC_HOUR=23                   # 🕐 Hora del día (formato 24h)
FULL_SYNC_MINUTE=0                  # Minuto (0-59)
FULL_SYNC_TIMEZONE=America/Argentina/Buenos_Aires

# Ejemplos de configuración horaria:
# - 11:00 PM: HOUR=23, MINUTE=0
# - 2:00 AM: HOUR=2, MINUTE=0
# - 6:30 PM: HOUR=18, MINUTE=30

# ===================================
# 5. FILTROS Y OPTIMIZACIONES
# ===================================

# Excluir productos sin stock (recomendado)
SYNC_INCLUDE_ZERO_STOCK=false       # false = no sincroniza productos sin stock

# Categorías y Collections (opcional)
SYNC_INCLUDE_CATEGORY_TAGS=false    # Tags de categoría
SYNC_ENABLE_COLLECTIONS=false       # Collections automáticas

# ===================================
# 6. REDIS (CACHE)
# ===================================
REDIS_URL=redis://localhost:6379/0  # No cambiar si usa Docker

# ===================================
# 7. LOGGING Y MONITOREO
# ===================================
LOG_LEVEL=INFO                      # INFO, DEBUG, WARNING, ERROR
DEBUG=false                         # true solo para diagnóstico
```

### 🎯 Configuración Recomendada por Tipo de Negocio

#### Para Tiendas Pequeñas (< 1,000 productos)
```bash
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_SIZE=100
SYNC_MAX_CONCURRENT_JOBS=2
FULL_SYNC_HOUR=2
```

#### Para Tiendas Medianas (1,000 - 5,000 productos)
```bash
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_SIZE=150
SYNC_MAX_CONCURRENT_JOBS=3
FULL_SYNC_HOUR=2
```

#### Para Tiendas Grandes (> 5,000 productos)
```bash
SYNC_INTERVAL_MINUTES=10
SYNC_BATCH_SIZE=200
SYNC_MAX_CONCURRENT_JOBS=5
FULL_SYNC_HOUR=1
```

### ⚠️ Parámetros Importantes a Considerar

#### 1. **Intervalo de Sincronización (`SYNC_INTERVAL_MINUTES`)**
- **Muy frecuente** (1-2 min): Actualización casi instantánea, pero más carga en RMS
- **Balanceado** (5 min): Recomendado para la mayoría
- **Conservador** (10-15 min): Para servidores con recursos limitados

#### 2. **Hora de Sincronización Completa (`FULL_SYNC_HOUR`)**
- Elija una hora con **poco tráfico** en su tienda
- Recomendado: Entre 1:00 AM y 4:00 AM
- Evite horarios pico de ventas

#### 3. **Productos sin Stock (`SYNC_INCLUDE_ZERO_STOCK`)**
- `false` (recomendado): Solo productos disponibles aparecen en Shopify
- `true`: Todos los productos se sincronizan, incluso sin stock

---

## 4. 🪟 Instalación en Windows

### Paso 1: Instalar Docker Desktop

#### A. Descargar Docker Desktop
1. Visite: https://www.docker.com/products/docker-desktop/
2. Haga clic en **"Download for Windows"**
3. Ejecute el instalador descargado (`Docker Desktop Installer.exe`)

#### B. Instalar Docker
1. Acepte los términos de licencia
2. Marque la opción **"Use WSL 2 instead of Hyper-V"** (recomendado)
3. Haga clic en **"Ok"** y espere a que termine la instalación
4. **Reinicie su computadora** cuando se lo solicite

#### C. Configurar Docker
1. Abra **Docker Desktop** desde el menú de inicio
2. En la primera ejecución, acepte los términos de servicio
3. **Opcional**: Cree una cuenta de Docker Hub (no es obligatorio)
4. Verifique que Docker esté corriendo (ícono de ballena en la bandeja del sistema)

### Paso 2: Preparar el Proyecto

#### A. Descargar el Proyecto
1. Copie la carpeta del proyecto a una ubicación en su servidor
   - Ejemplo: `C:\rms-shopify-integration\`

#### B. Configurar el Archivo `.env`
1. Navegue a la carpeta del proyecto
2. Copie el archivo `.env.example` y renómbrelo a `.env`
3. Edite `.env` con sus credenciales (ver sección anterior)

### Paso 3: Construir la Imagen Docker

#### A. Abrir PowerShell o CMD
1. Presione `Windows + X`
2. Seleccione **"Windows PowerShell (Administrador)"** o **"Símbolo del sistema (Administrador)"**

#### B. Navegar al Proyecto
```powershell
cd C:\rms-shopify-integration
```

#### C. Construir la Imagen
```powershell
docker build -t rms-shopify-integration:latest .
```

Este proceso puede tomar **5-10 minutos** la primera vez.

**Indicadores de progreso:**
```
Step 1/15 : FROM python:3.13-slim
Step 2/15 : WORKDIR /app
...
Successfully built abc123def456
Successfully tagged rms-shopify-integration:latest
```

---

## 5. 🚀 Levantando el Servicio

### Opción A: Usar Docker Compose (Recomendado)

#### 1. Iniciar los Servicios
```powershell
docker-compose up -d
```

**Qué hace este comando:**
- `-d`: Ejecuta en segundo plano (modo "detached")
- Inicia dos contenedores:
  - `rms-shopify-api`: El servicio de integración
  - `rms-shopify-redis`: Cache para mejor rendimiento

#### 2. Verificar que Están Corriendo
```powershell
docker-compose ps
```

**Salida esperada:**
```
NAME                    STATUS              PORTS
rms-shopify-api         Up 30 seconds       0.0.0.0:8080->8080/tcp
rms-shopify-redis       Up 30 seconds       0.0.0.0:6379->6379/tcp
```

#### 3. Ver los Logs en Tiempo Real
```powershell
docker-compose logs -f api
```

**Logs exitosos se verán así:**
```
rms-shopify-api  | INFO:     Started server process [1]
rms-shopify-api  | INFO:     Waiting for application startup.
rms-shopify-api  | ✅ Motor de sincronización automática iniciado
rms-shopify-api  | ⏰ Sincronización programada: cada 5 minutos
rms-shopify-api  | INFO:     Application startup complete.
rms-shopify-api  | INFO:     Uvicorn running on http://0.0.0.0:8080
```

Para salir de los logs, presione `Ctrl + C`

### 🎨 Acceso al Panel Web (Dashboard)

El sistema incluye un **panel web interactivo** desarrollado con Streamlit que se inicia automáticamente junto con los demás servicios.

#### Acceder al Dashboard

Una vez los servicios estén corriendo, abra su navegador web y visite:

**Si accede desde el mismo servidor:**
```
http://localhost:8501
```

**Si accede desde otra computadora en la red:**
```
http://[IP-DEL-SERVIDOR]:8501
```

Por ejemplo: `http://192.168.1.100:8501`

#### ¿Qué puede hacer en el Dashboard?

El dashboard le permite:

1. **🏠 Inicio** → Vista general del sistema
   - Estado de salud (RMS, Shopify, Redis)
   - Métricas clave de sincronización
   - Acciones rápidas

2. **🔄 Gestión de Sincronización** → Control del motor automático
   - Ejecutar sincronización manual
   - Configurar intervalos
   - Ver y gestionar checkpoints
   - Estadísticas de sincronización

3. **📦 Pedidos** → Monitoreo de sincronización de pedidos
   - Estado del polling de pedidos
   - Estadísticas de pedidos sincronizados
   - Control del motor de pedidos

4. **🖥️ Monitor del Sistema** → Recursos y rendimiento
   - Uso de CPU y memoria
   - Espacio en disco
   - Estado de los servicios

5. **📝 Logs** (solo en modo DEBUG) → Visualización de logs
   - Búsqueda y filtrado de logs
   - Errores recientes
   - Estadísticas de logs

#### Comandos del Dashboard

```powershell
# Ver estado del dashboard
docker-compose ps dashboard

# Ver logs del dashboard
docker-compose logs -f dashboard

# Reiniciar solo el dashboard
docker-compose restart dashboard

# Detener el dashboard
docker-compose stop dashboard

# Iniciar el dashboard
docker-compose start dashboard
```

#### Configuración del Dashboard

El dashboard se configura automáticamente, pero puede personalizar algunos aspectos:

**Variables de entorno** (en `.env`):
```bash
# URL de la API (no cambiar si usa Docker)
DASHBOARD_API_URL=http://api:8000

# Habilitar visualización de logs
DEBUG=true
```

**⚠️ Nota importante:**
- El dashboard se conecta automáticamente a la API usando la red interna de Docker
- No necesita configuración adicional si usa Docker Compose
- El puerto 8501 debe estar disponible (no usado por otra aplicación)

### Opción B: Comandos Individuales para Detener/Iniciar

#### Detener los Servicios
```powershell
docker-compose down
```

#### Reiniciar los Servicios
```powershell
docker-compose restart
```

#### Ver Estado de los Servicios
```powershell
docker-compose ps
```

### 🎯 Verificación Final

#### 1. Verificar Acceso al Dashboard Web 🎨
Abra su navegador y visite:
```
http://localhost:8501
```

**Debe ver:** El panel web interactivo del sistema con:
- Estado de salud de los servicios
- Métricas de sincronización en tiempo real
- Botones de acciones rápidas

**⭐ Recomendación:** Use el dashboard como interfaz principal para monitorear y controlar el sistema.

#### 2. Verificar API REST (Opcional)
Si prefiere usar la API directamente, visite:
```
http://localhost:8000/docs
```

**Debe ver:** La interfaz Swagger UI con todos los endpoints disponibles

#### 3. Verificar Salud del Sistema
En el navegador, visite:
```
http://localhost:8000/api/v1/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-17T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "rms_database": "connected",
    "shopify_api": "connected",
    "redis": "connected"
  }
}
```

**💡 Nota:** También puede ver esta información de forma visual en el dashboard (http://localhost:8501)

---

## 6. 📊 Monitoreo de la Sincronización

### Panel Web de Administración

Una vez el servicio esté corriendo, puede acceder al panel de administración desde cualquier navegador en su red:

```
http://[IP-DEL-SERVIDOR]:8080/docs
```

Si accede desde el mismo servidor:
```
http://localhost:8080/docs
```

### 🎯 Endpoints Importantes

#### 1. **Estado del Motor Automático**

**URL:** `GET /api/v1/sync/monitor/status`

**Cómo acceder:**
- Navegador: `http://localhost:8080/api/v1/sync/monitor/status`
- PowerShell: `curl http://localhost:8080/api/v1/sync/monitor/status`

**Qué muestra:**
```json
{
  "motor_activo": true,
  "ultimo_sync": "2025-01-17T10:25:00Z",
  "proximo_sync": "2025-01-17T10:30:00Z",
  "intervalo_minutos": 5,
  "productos_sincronizados_hoy": 245,
  "errores_hoy": 0
}
```

**Interpretación:**
- ✅ `motor_activo: true` → Sistema funcionando correctamente
- ❌ `motor_activo: false` → Sistema detenido, revisar logs
- `ultimo_sync` → Última vez que se ejecutó
- `proximo_sync` → Cuándo se ejecutará nuevamente

#### 2. **Estadísticas Detalladas**

**URL:** `GET /api/v1/sync/monitor/stats`

**Qué muestra:**
```json
{
  "estadisticas_24h": {
    "productos_sincronizados": 245,
    "productos_creados": 12,
    "productos_actualizados": 233,
    "errores": 2,
    "tasa_exito": 99.2
  },
  "tiempo_promedio_sync": "2.5 segundos",
  "proximo_sync_completo": "2025-01-18T02:00:00Z"
}
```

**Métricas Clave:**
- `tasa_exito` → Debe estar por encima de 95%
- `errores` → Idealmente 0, revisar si aumentan
- `tiempo_promedio_sync` → Normal: 1-5 segundos

#### 3. **Logs del Sistema**

**URL:** `GET /api/v1/logs?level=INFO&limit=100`

**Niveles de logs disponibles:**
- `INFO` → Operaciones normales
- `WARNING` → Advertencias (no crítico)
- `ERROR` → Errores que requieren atención

**Ejemplo de uso:**
```
http://localhost:8080/api/v1/logs?level=ERROR&limit=50
```

Muestra los últimos 50 errores.

#### 4. **Salud del Sistema**

**URL:** `GET /api/v1/health`

**Qué verifica:**
- ✅ Conexión a RMS (SQL Server)
- ✅ Conexión a Shopify (API)
- ✅ Conexión a Redis (Cache)
- ✅ Espacio en disco
- ✅ Uso de memoria

### 📈 Dashboard Visual (Swagger UI)

La interfaz web en `http://localhost:8080/docs` le permite:

1. **Ver todos los endpoints disponibles** organizados por categoría
2. **Probar endpoints** directamente desde el navegador
3. **Ver respuestas en tiempo real**

**Categorías principales:**
- 🤖 **Sync Monitor** → Estado y control del motor automático
- 📊 **Metrics** → Métricas y estadísticas
- 📝 **Logs** → Visualización de logs
- 🔧 **Admin** → Operaciones administrativas

### 🔍 Cómo Interpretar el Estado

#### Motor Funcionando Correctamente ✅
```
✅ motor_activo: true
⏰ ultimo_sync: hace 3 minutos
📊 tasa_exito: 98%
🔢 productos_sincronizados_hoy: 342
⚠️ errores_hoy: 5 (menores)
```

#### Motor con Problemas ⚠️
```
✅ motor_activo: true
⏰ ultimo_sync: hace 45 minutos  ← Demasiado tiempo
📊 tasa_exito: 75%  ← Debajo del 95%
🔢 productos_sincronizados_hoy: 89
❌ errores_hoy: 45  ← Muchos errores
```

#### Motor Detenido ❌
```
❌ motor_activo: false
⏰ ultimo_sync: hace 2 horas
📊 tasa_exito: 0%
```

**Acción requerida:** Ver sección de Solución de Problemas

---

## 7. 🛠️ Operaciones Comunes

### 1. Forzar Sincronización Manual

A veces necesita sincronizar inmediatamente sin esperar el intervalo automático.

#### Opción A: Desde el Navegador (Swagger UI)

1. Visite `http://localhost:8080/docs`
2. Busque la sección **"Sync Monitor"**
3. Expanda el endpoint `POST /api/v1/sync/monitor/trigger`
4. Haga clic en **"Try it out"**
5. Haga clic en **"Execute"**

**Respuesta esperada:**
```json
{
  "status": "sync_iniciada",
  "mensaje": "Sincronización manual iniciada correctamente",
  "timestamp": "2025-01-17T10:35:00Z"
}
```

#### Opción B: Desde PowerShell/CMD

```powershell
curl -X POST http://localhost:8080/api/v1/sync/monitor/trigger
```

### 2. Forzar Sincronización Completa

Sincroniza **todos** los productos, sin importar si fueron modificados o no.

**⚠️ Advertencia:** Esta operación puede tomar varios minutos dependiendo de su catálogo.

```powershell
curl -X POST http://localhost:8080/api/v1/sync/monitor/force-full-sync
```

**Cuándo usar:**
- Después de cambios masivos en RMS
- Si detecta inconsistencias entre RMS y Shopify
- Como verificación periódica manual

### 3. Cambiar Intervalo de Sincronización

Puede ajustar el intervalo sin reiniciar el servicio.

#### Desde Swagger UI:
1. Vaya a `http://localhost:8080/docs`
2. Busque `PUT /api/v1/sync/monitor/interval`
3. Haga clic en **"Try it out"**
4. En el cuerpo, escriba:
```json
{
  "interval_minutes": 10
}
```
5. Haga clic en **"Execute"**

#### Desde PowerShell:
```powershell
curl -X PUT http://localhost:8080/api/v1/sync/monitor/interval `
  -H "Content-Type: application/json" `
  -d '{"interval_minutes": 10}'
```

**Valores válidos:** 2 a 60 minutos

### 4. Ver Productos Sincronizados Recientemente

```powershell
curl http://localhost:8080/api/v1/sync/monitor/recent-activity
```

**Muestra:**
- Productos sincronizados en la última hora
- Estado de cada sincronización
- Errores si los hubo

### 5. Pausar Temporalmente el Motor

**⚠️ No recomendado** excepto para mantenimiento.

```powershell
# Detener el servicio completo
docker-compose stop api

# Reiniciar cuando esté listo
docker-compose start api
```

### 6. Reiniciar el Servicio

Si nota comportamiento extraño, reiniciar puede resolver problemas:

```powershell
docker-compose restart api
```

### 7. Ver Logs en Tiempo Real

Útil para diagnosticar problemas:

```powershell
# Logs del servicio principal
docker-compose logs -f api

# Logs de Redis (cache)
docker-compose logs -f redis

# Últimas 100 líneas
docker-compose logs --tail=100 api
```

Para salir: presione `Ctrl + C`

---

## 8. 🚨 Solución de Problemas

### Problema 1: El servicio no inicia

#### Síntomas:
```
ERROR: Cannot start service api: port is already allocated
```

#### Solución:
Otro servicio está usando el puerto 8080.

**Opción A:** Cambiar el puerto en `docker-compose.yml`:
```yaml
ports:
  - "8081:8080"  # Cambiar 8080 por 8081
```

**Opción B:** Detener el servicio que usa el puerto 8080:
```powershell
# Ver qué proceso usa el puerto 8080
netstat -ano | findstr :8080

# Detener el proceso (reemplazar PID con el número que apareció)
taskkill /PID [número] /F
```

### Problema 2: No se puede conectar a RMS

#### Síntomas:
- Log: `ERROR: Could not connect to RMS database`
- Health check: `rms_database: "disconnected"`

#### Posibles Causas y Soluciones:

**A. Credenciales incorrectas**
1. Verifique `.env`:
   - `RMS_DB_HOST` (IP correcta)
   - `RMS_DB_USER` y `RMS_DB_PASSWORD`
   - `RMS_DB_NAME` (nombre exacto)

2. Pruebe la conexión manualmente desde SQL Server Management Studio

**B. Firewall bloqueando la conexión**
1. En Windows Firewall, agregue una regla para el puerto 1433
2. En el servidor RMS, verifique que SQL Server acepta conexiones remotas

**C. SQL Server no acepta conexiones remotas**
1. Abra SQL Server Configuration Manager
2. Vaya a **SQL Server Network Configuration → Protocols**
3. Habilite **TCP/IP**
4. Reinicie el servicio SQL Server

### Problema 3: No se puede conectar a Shopify

#### Síntomas:
- Log: `ERROR: Shopify API authentication failed`
- Health check: `shopify_api: "disconnected"`

#### Soluciones:

**A. Verificar Access Token**
1. El token debe empezar con `shpat_`
2. Verifique que el token no haya expirado
3. Regenere el token si es necesario desde Shopify Admin

**B. Verificar URL de la tienda**
```
Correcto: mi-tienda.myshopify.com
Incorrecto: https://mi-tienda.myshopify.com
Incorrecto: mi-tienda.com
```

**C. Verificar permisos del token**
El token debe tener permisos para:
- ✅ `read_products`
- ✅ `write_products`
- ✅ `read_inventory`
- ✅ `write_inventory`
- ✅ `read_orders`
- ✅ `write_orders`

### Problema 4: Sincronización muy lenta

#### Síntomas:
- Sincronizaciones toman más de 10 minutos
- `tiempo_promedio_sync: "45 segundos"`

#### Soluciones:

**A. Reducir tamaño de lotes**
En `.env`:
```bash
SYNC_BATCH_SIZE=50  # Reducir de 100 a 50
```

**B. Aumentar concurrencia**
```bash
SYNC_MAX_CONCURRENT_JOBS=5  # Aumentar de 3 a 5
```

**C. Verificar conexión a Internet**
- Velocidad de subida debe ser al menos 5 Mbps
- Ping a Shopify debe ser < 200ms

**D. Verificar recursos del servidor**
```powershell
# Ver uso de CPU y RAM
docker stats
```

Si CPU o RAM están al 100%, considere:
- Aumentar recursos del servidor
- Reducir `SYNC_MAX_CONCURRENT_JOBS`

### Problema 5: Muchos errores de sincronización

#### Síntomas:
- `tasa_exito < 90%`
- Muchos productos con error

#### Diagnóstico:

**Paso 1:** Ver logs de errores
```powershell
curl http://localhost:8080/api/v1/logs?level=ERROR&limit=50
```

**Paso 2:** Identificar patrones comunes

**Error:** `Product variant SKU already exists`
- **Causa:** SKU duplicado en RMS
- **Solución:** Verificar y corregir SKUs duplicados en RMS

**Error:** `Rate limit exceeded`
- **Causa:** Muchas peticiones a Shopify
- **Solución:** Aumentar `SYNC_INTERVAL_MINUTES` a 10 o 15

**Error:** `Invalid product data`
- **Causa:** Datos faltantes o incorrectos en RMS
- **Solución:** Verificar que productos tengan:
  - Precio > 0
  - Nombre válido
  - CCOD único

### Problema 6: Productos no aparecen en Shopify

#### Verificaciones:

**1. ¿El producto tiene stock?**
Si `SYNC_INCLUDE_ZERO_STOCK=false`, productos sin stock no se sincronizan.

**Solución:** Actualizar inventario en RMS o cambiar configuración a `true`

**2. ¿El producto fue modificado recientemente?**
El motor solo detecta productos modificados desde el último sync.

**Solución:** Forzar sincronización completa:
```powershell
curl -X POST http://localhost:8080/api/v1/sync/monitor/force-full-sync
```

**3. ¿El producto tiene errores?**
Revise logs para ese producto específico.

### Problema 7: El servicio se reinicia constantemente

#### Síntomas:
```powershell
docker-compose ps
# Muestra: Restarting (1) 5 seconds ago
```

#### Solución:

**Ver causa del error:**
```powershell
docker-compose logs api --tail=50
```

**Causas comunes:**
- Configuración `.env` incorrecta
- Falta de memoria RAM
- Error en la base de datos RMS

### Problema 8: Sincronización completa nocturna no se ejecuta

#### Verificaciones:

**1. ¿Está habilitada?**
```bash
ENABLE_FULL_SYNC_SCHEDULE=true  # Debe ser true
```

**2. ¿La hora es correcta?**
```bash
FULL_SYNC_HOUR=23  # 23 = 11 PM en formato 24h
FULL_SYNC_TIMEZONE=America/Argentina/Buenos_Aires
```

**3. Ver próxima ejecución:**
```powershell
curl http://localhost:8080/api/v1/sync/monitor/stats
# Buscar: "proximo_sync_completo"
```

### Problema 9: El dashboard no carga o muestra errores

#### Síntomas:
- Navegador muestra "No se puede conectar" en `http://localhost:8501`
- Dashboard muestra "Error de conexión con la API"
- Página en blanco o error 500

#### Soluciones:

**A. Dashboard no inicia**
```powershell
# Verificar estado del contenedor
docker-compose ps dashboard

# Ver logs del dashboard
docker-compose logs dashboard --tail=50
```

**Problemas comunes:**

1. **Puerto 8501 ya está en uso**
   ```powershell
   # En Windows, verificar qué proceso usa el puerto
   netstat -ano | findstr :8501

   # Opción 1: Cerrar el proceso que usa el puerto
   taskkill /PID [número] /F

   # Opción 2: Cambiar el puerto del dashboard
   # En docker-compose.yml, cambiar:
   # ports:
   #   - "8502:8501"  # Usar puerto 8502 en lugar de 8501
   ```

2. **Error "Connection error" en el dashboard**
   - **Causa:** Dashboard no puede conectarse a la API
   - **Verificar:** API está corriendo
   ```powershell
   curl http://localhost:8000/health
   ```
   - **Solución:** Verificar que `DASHBOARD_API_URL=http://api:8000` en docker-compose.yml

3. **Datos vacíos / Sin métricas**
   - **Causa:** API no está retornando datos
   - **Verificar:** Motor de sincronización activo
   ```powershell
   curl http://localhost:8000/api/v1/sync/monitor/status
   ```
   - **Solución:** Verificar que `ENABLE_SCHEDULED_SYNC=true` en `.env`

4. **Página "Logs" muestra "DEBUG mode required"**
   - **Causa:** Modo DEBUG no está habilitado
   - **Solución:** En `.env`, cambiar `DEBUG=true` y reiniciar:
   ```powershell
   docker-compose restart api
   ```

**B. Dashboard lento o no responde**
```powershell
# Verificar recursos del contenedor
docker stats rms-shopify-dashboard

# Reiniciar el dashboard
docker-compose restart dashboard
```

**C. Acceso desde otra computadora no funciona**
```powershell
# Verificar firewall de Windows
# Abrir puerto 8501 en Windows Firewall

# Verificar IP del servidor
ipconfig
# Buscar "Dirección IPv4"

# Acceder desde otro dispositivo usando:
# http://[IP-del-servidor]:8501
```

### 🆘 Comandos de Diagnóstico Rápido

```powershell
# 1. Ver estado general (API + Dashboard + Redis)
docker-compose ps

# 2. Ver últimos logs
docker-compose logs --tail=100 api

# 3. Ver salud del sistema
curl http://localhost:8080/api/v1/health

# 4. Ver estado del motor
curl http://localhost:8080/api/v1/sync/monitor/status

# 5. Ver errores recientes
curl http://localhost:8080/api/v1/logs?level=ERROR&limit=20

# 6. Reiniciar servicio
docker-compose restart api
```

---

## 9. 📞 Contacto y Soporte

### 🆘 Antes de Contactar Soporte

Por favor, recopile esta información:

1. **Descripción del problema**
2. **Logs recientes** (últimas 100 líneas):
   ```powershell
   docker-compose logs --tail=100 api > logs.txt
   ```
3. **Estado del sistema**:
   ```powershell
   curl http://localhost:8080/api/v1/health > health.json
   curl http://localhost:8080/api/v1/sync/monitor/status > status.json
   ```
4. **Configuración** (sin contraseñas):
   - Versión de Windows
   - Versión de Docker Desktop
   - Configuración `.env` (oculte contraseñas)

### 📧 Información de Contacto

**Soporte Técnico:**
- **Email**: enzo@oneclick.cr
- **Horario**: Lunes a Viernes, 9:00 AM - 6:00 PM (hora local)
- **Tiempo de respuesta**: 24-48 horas hábiles

**Soporte de Emergencia** (solo problemas críticos):
- Servicio completamente detenido
- Pérdida de datos
- Seguridad comprometida

### 📚 Documentación Adicional

Para información más técnica o avanzada, consulte:

- **CLAUDE.md** → Guía para desarrolladores
- **README.md** → Información general del proyecto
- **AUTOMATIC_SYNC_ENGINE.md** → Detalles técnicos del motor
- **RMS_TO_SHOPIFY_SYNC.md** → Flujo detallado de sincronización

---

## ✅ Lista de Verificación de Configuración

Antes de considerar el sistema completamente configurado, verifique:

### Instalación
- [ ] Docker Desktop instalado y corriendo
- [ ] Imagen Docker construida correctamente
- [ ] Servicios iniciados con `docker-compose up -d`
- [ ] Panel web accesible en http://localhost:8080/docs

### Configuración
- [ ] Archivo `.env` creado con todas las credenciales
- [ ] Conexión a RMS verificada (health check)
- [ ] Conexión a Shopify verificada (health check)
- [ ] Motor de sincronización automática activo
- [ ] Sincronización completa nocturna programada

### Pruebas
- [ ] Primera sincronización manual completada exitosamente
- [ ] Al menos un producto sincronizado en Shopify
- [ ] Logs sin errores críticos
- [ ] Métricas mostrando datos

### Monitoreo
- [ ] Panel web funcionando correctamente
- [ ] Logs accesibles
- [ ] Alertas configuradas (si aplica)
- [ ] Documentación guardada para referencia

---

## 🎉 ¡Felicitaciones!

Si completó todos los pasos, su sistema de integración RMS-Shopify está:

✅ **Instalado** correctamente
✅ **Configurado** con sus credenciales
✅ **Funcionando** automáticamente cada 5 minutos
✅ **Monitoreado** en tiempo real
✅ **Respaldado** con sincronización nocturna completa

**Su catálogo de productos ahora se mantiene sincronizado automáticamente entre RMS y Shopify.**

---

**Versión del documento:** 1.0
**Fecha de actualización:** Enero 2025
**Autor:** OneClick - Enzo
**Email de soporte:** enzo@oneclick.cr
