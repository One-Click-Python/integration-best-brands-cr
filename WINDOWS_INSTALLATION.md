# Instalación en Windows - RMS-Shopify Integration

Guía completa para instalar y configurar el sistema RMS-Shopify Integration como **Servicio de Windows** con integración completa al programador del sistema operativo.

## 🎯 Características de la Instalación Windows

- **✅ Servicio de Windows** - Inicio automático con el sistema
- **✅ Tareas Programadas** - Monitoreo y mantenimiento automático
- **✅ Event Viewer** - Logs integrados del sistema
- **✅ Scripts PowerShell** - Gestión unificada del servicio
- **✅ Firewall** - Reglas automáticas para el puerto 8080
- **✅ Auto-recovery** - Reinicio automático en fallos

## 📋 Prerrequisitos

### Software Requerido
- **Windows 10/11** o **Windows Server 2016+**
- **Python 3.9+** instalado y accesible desde PATH
- **PowerShell 5.1+** (incluido en Windows)
- **Permisos de Administrador** para instalación

### Verificar Prerrequisitos
```powershell
# Verificar Python
python --version

# Verificar PowerShell
$PSVersionTable.PSVersion

# Verificar permisos de Administrador
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
```

## 🚀 Instalación Automática

### 1. Descargar e Instalar

```powershell
# Clonar repositorio
git clone <repository-url>
cd rms-shopify-integration

# Ejecutar instalación como Administrador
PowerShell -ExecutionPolicy Bypass -File "deployment\windows\install-windows-service.ps1"
```

### 2. Configuración Inicial

El instalador crea automáticamente:
- ✅ **Servicio de Windows**: `RMSShopifyIntegration`
- ✅ **Directorio de aplicación**: `C:\RMS-Shopify-Integration\`
- ✅ **Logs del sistema**: `C:\Logs\RMS-Shopify-Integration\`
- ✅ **Virtual environment**: Python con todas las dependencias
- ✅ **Archivo .env**: Plantilla de configuración
- ✅ **Tareas programadas**: Monitoreo cada 5 minutos
- ✅ **Reglas de firewall**: Puerto 8080 abierto

### 3. Configurar Variables de Entorno

Editar `C:\RMS-Shopify-Integration\.env`:

```bash
# === CONFIGURACIÓN BÁSICA ===
APP_NAME=RMS-Shopify Integration
DEBUG=False
LOG_LEVEL=INFO

# === BASE DE DATOS RMS (SQL SERVER) ===
RMS_DB_HOST=tu-servidor-sql
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database
RMS_DB_USER=tu_usuario
RMS_DB_PASSWORD=tu_contraseña
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server
RMS_STORE_ID=1

# === SHOPIFY API ===
SHOPIFY_SHOP_URL=https://tu-tienda.myshopify.com
SHOPIFY_ACCESS_TOKEN=tu_access_token
SHOPIFY_API_VERSION=2025-04
SHOPIFY_WEBHOOK_SECRET=tu_webhook_secret

# === MOTOR DE SINCRONIZACIÓN AUTOMÁTICA ===
ENABLE_SCHEDULED_SYNC=true
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_SIZE=10
SYNC_MAX_CONCURRENT_JOBS=3

# === PEDIDOS SIN CLIENTE ===
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=
REQUIRE_CUSTOMER_EMAIL=false

# === ALERTAS ===
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@tu-empresa.com
ALERT_EMAIL_FROM=rms-shopify@tu-empresa.com
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_PASSWORD=tu_password_email
```

## ⚙️ Gestión del Servicio

### Script de Gestión Unificada

```powershell
# Script principal de gestión
C:\RMS-Shopify-Integration\deployment\windows\manage-service.ps1

# Comandos disponibles:
PowerShell -File "manage-service.ps1" -Action install     # Instalar servicio
PowerShell -File "manage-service.ps1" -Action start      # Iniciar servicio
PowerShell -File "manage-service.ps1" -Action stop       # Detener servicio
PowerShell -File "manage-service.ps1" -Action restart    # Reiniciar servicio
PowerShell -File "manage-service.ps1" -Action status     # Ver estado completo
PowerShell -File "manage-service.ps1" -Action logs       # Ver logs
PowerShell -File "manage-service.ps1" -Action monitor    # Monitor en tiempo real
PowerShell -File "manage-service.ps1" -Action config     # Ver configuración
```

### Comandos Básicos de Windows

```powershell
# Gestión del servicio
Get-Service RMSShopifyIntegration           # Ver estado
Start-Service RMSShopifyIntegration         # Iniciar
Stop-Service RMSShopifyIntegration          # Detener
Restart-Service RMSShopifyIntegration       # Reiniciar

# Ver logs en Event Viewer
Get-WinEvent -LogName Application | Where-Object {$_.ProviderName -eq "RMSShopifyIntegration"}

# Estado rápido
PowerShell -File "C:\RMS-Shopify-Integration\rms-status.ps1"
```

## 📅 Tareas Programadas (Task Scheduler)

### Tareas Automáticas Creadas

| Tarea | Frecuencia | Descripción |
|-------|------------|-------------|
| **RMS-Shopify-Monitor** | Cada 5 minutos | Verifica salud del servicio y API |
| **RMS-Shopify-NightSync** | Diario 3:00 AM | Sincronización completa nocturna |
| **RMS-Shopify-WeeklyRestart** | Domingos 4:00 AM | Reinicio de mantenimiento |
| **RMS-Shopify-LogCleanup** | Lunes 2:00 AM | Limpieza de logs antiguos |

### Gestionar Tareas Programadas

```powershell
# Ver tareas programadas
Get-ScheduledTask -TaskName "*RMS-Shopify*"

# Ejecutar tarea manualmente
Start-ScheduledTask -TaskName "RMS-Shopify-Monitor"

# Deshabilitar/habilitar tarea
Disable-ScheduledTask -TaskName "RMS-Shopify-NightSync"
Enable-ScheduledTask -TaskName "RMS-Shopify-NightSync"

# Ver historial de ejecución
Get-ScheduledTaskInfo -TaskName "RMS-Shopify-Monitor"
```

## 🔍 Monitoreo y Logs

### Ubicaciones de Logs

```
C:\Logs\RMS-Shopify-Integration\
├── service.log          # Logs del servicio principal
├── monitor.log          # Logs del monitor automático  
├── performance.log      # Métricas de rendimiento
├── management.log       # Logs de gestión del servicio
└── sync\               # Logs específicos de sincronización
    ├── rms-to-shopify.log
    └── shopify-to-rms.log
```

### Monitoreo en Tiempo Real

```powershell
# Monitor continuo del servicio
PowerShell -File "manage-service.ps1" -Action monitor

# Ver logs en tiempo real
Get-Content "C:\Logs\RMS-Shopify-Integration\service.log" -Wait -Tail 20

# Estado de la API
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status"
```

### Event Viewer

1. Abrir **Event Viewer** (`eventvwr.msc`)
2. Navegar a **Windows Logs > Application**
3. Filtrar por **Source**: `RMSShopifyIntegration`

## 🛡️ Seguridad y Firewall

### Reglas de Firewall Automáticas

```powershell
# Verificar regla creada
Get-NetFirewallRule -DisplayName "*RMS-Shopify*"

# Crear regla manualmente si es necesario
New-NetFirewallRule -DisplayName "RMS-Shopify Integration" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow
```

### Permisos de Usuario

El servicio se ejecuta como:
- **Usuario**: `SYSTEM` (máximos privilegios)
- **Directorio de trabajo**: `C:\RMS-Shopify-Integration`
- **Acceso**: Lectura/escritura en logs y temp

## 🔧 Solución de Problemas

### Problema: Servicio no inicia

```powershell
# Verificar estado detallado
Get-Service RMSShopifyIntegration | Format-List *

# Ver últimos errores
Get-WinEvent -FilterHashtable @{LogName='System'; ID=7034} | Where-Object {$_.Message -like "*RMSShopifyIntegration*"}

# Verificar configuración
PowerShell -File "manage-service.ps1" -Action config

# Reiniciar con logs detallados
PowerShell -File "manage-service.ps1" -Action restart
```

### Problema: API no responde

```powershell
# Verificar puerto
netstat -an | findstr :8080

# Test de conectividad
Test-NetConnection -ComputerName localhost -Port 8080

# Verificar firewall
Get-NetFirewallRule -DisplayName "*RMS-Shopify*" | Get-NetFirewallPortFilter
```

### Problema: Motor de sincronización inactivo

```powershell
# Verificar estado del motor
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status"

# Trigger manual
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/trigger" -Method POST

# Forzar sincronización completa
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/force-full-sync" -Method POST
```

## 📊 APIs de Control

### Health Check
```powershell
# Estado general
Invoke-RestMethod -Uri "http://localhost:8080/health"

# Estado detallado del motor
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status"

# Estadísticas de sincronización
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/stats"
```

### Control Manual
```powershell
# Trigger sincronización inmediata
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/trigger" -Method POST

# Cambiar intervalo a 10 minutos
$Body = @{ interval_minutes = 10 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/interval" -Method PUT -Body $Body -ContentType "application/json"
```

## 🔄 Actualización del Servicio

```powershell
# 1. Detener servicio
Stop-Service RMSShopifyIntegration

# 2. Actualizar código
cd C:\RMS-Shopify-Integration
git pull origin main

# 3. Actualizar dependencias
.\venv\Scripts\pip.exe install -r requirements.txt

# 4. Reiniciar servicio
Start-Service RMSShopifyIntegration

# 5. Verificar estado
PowerShell -File "manage-service.ps1" -Action status
```

## 📋 Desinstalación

```powershell
# Desinstalar completamente
PowerShell -File "manage-service.ps1" -Action uninstall

# Limpieza manual adicional (opcional)
Remove-Item -Path "C:\RMS-Shopify-Integration" -Recurse -Force
Remove-Item -Path "C:\Logs\RMS-Shopify-Integration" -Recurse -Force
```

## 🎉 Verificación de Instalación

### Lista de Verificación Completa

```powershell
# 1. Servicio funcionando
Get-Service RMSShopifyIntegration

# 2. API disponible
Invoke-RestMethod -Uri "http://localhost:8080/health"

# 3. Motor de sincronización activo
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status"

# 4. Tareas programadas configuradas
Get-ScheduledTask -TaskName "*RMS-Shopify*"

# 5. Logs generándose
Get-ChildItem "C:\Logs\RMS-Shopify-Integration" -Recurse

# 6. Firewall configurado
Get-NetFirewallRule -DisplayName "*RMS-Shopify*"
```

### Resultado Esperado

Si todo está configurado correctamente, deberías ver:
- ✅ **Servicio**: `Running`
- ✅ **API Health**: `200 OK`
- ✅ **Motor Sync**: `running: true`
- ✅ **Tareas**: 4 tareas programadas activas
- ✅ **Logs**: Archivos de log actualizándose
- ✅ **Firewall**: Regla para puerto 8080 activa

---

## 📧 Soporte Windows

Para problemas específicos de Windows:
- **Event Viewer**: Revisar logs del sistema
- **Services.msc**: Gestión visual de servicios
- **Task Scheduler**: Gestión de tareas programadas
- **PowerShell**: Scripts de gestión incluidos

¡Tu sistema RMS-Shopify Integration ahora está completamente integrado con Windows!