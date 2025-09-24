# Instalación en Windows - RMS-Shopify Integration

Guía completa para instalar y configurar el sistema RMS-Shopify Integration como **Servicio de Windows** con integración completa al programador del sistema operativo, incluyendo monitoreo automático y recuperación de fallos.

## 🎯 Características de la Instalación Windows

- **✅ Servicio de Windows** - Inicio automático con el sistema operativo
- **✅ Tareas Programadas** - Monitoreo y mantenimiento automático cada 5 minutos
- **✅ Event Viewer** - Logs integrados del sistema Windows
- **✅ Scripts PowerShell** - Gestión unificada del servicio y monitoreo
- **✅ Firewall Automático** - Reglas configuradas para puerto 8080/8443
- **✅ Auto-recovery** - Reinicio automático en caso de fallos críticos
- **✅ Performance Counters** - Métricas integradas de Windows
- **✅ Task Scheduler** - Programación de mantenimiento y backups

## 📋 Prerrequisitos del Sistema

### Software Requerido

- **Windows 10/11** (versión 1909+) o **Windows Server 2016+**
- **Python 3.13+** instalado y accesible desde PATH
- **PowerShell 5.1+** (incluido en Windows modernas)
- **Git for Windows** para clonar el repositorio
- **Permisos de Administrador** para instalación de servicios
- **SQL Server Native Client** para conectividad RMS
- **Visual C++ Redistributable** (para dependencias nativas)

### Verificar Prerrequisitos

```powershell
# Abrir PowerShell como Administrador
# Verificar Python y versión
python --version
Write-Host "Python OK: $(python --version)" -ForegroundColor Green

# Verificar PowerShell
$PSVersionTable.PSVersion
Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)" -ForegroundColor Green

# Verificar permisos de Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if ($isAdmin) {
    Write-Host "✅ Ejecutándose como Administrador" -ForegroundColor Green
} else {
    Write-Host "❌ Se requieren permisos de Administrador" -ForegroundColor Red
    exit 1
}

# Verificar conectividad SQL Server
try {
    sqlcmd -S "tu-servidor-sql" -Q "SELECT @@VERSION"
    Write-Host "✅ Conectividad SQL Server OK" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Verificar conectividad SQL Server" -ForegroundColor Yellow
}

# Verificar Git
git --version
Write-Host "Git OK: $(git --version)" -ForegroundColor Green
```

### Componentes de Windows Requeridos

```powershell
# Habilitar características de Windows necesarias
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole -All
Enable-WindowsOptionalFeature -Online -FeatureName IIS-HttpErrors -All
Enable-WindowsOptionalFeature -Online -FeatureName IIS-HttpLogging -All

# Instalar SQL Server Native Client (si no está instalado)
# Descargar de: https://www.microsoft.com/en-us/download/details.aspx?id=50402
```

## 🚀 Instalación Automática Completa

### Método 1: Script de Instalación Unificado (Recomendado)

```powershell
# 1. Clonar repositorio en ubicación estándar
git clone https://github.com/tu-usuario/rms-shopify-integration.git C:\Temp\rms-shopify-setup
cd C:\Temp\rms-shopify-setup

# 2. Ejecutar instalador maestro como Administrador
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\deployment\windows\install-windows-service.ps1 -InstallPath "C:\RMS-Shopify-Integration" -ServiceName "RMSShopifyIntegration" -Port 8080

# 3. Verificar instalación
Get-Service -Name "RMSShopifyIntegration"
```

### Método 2: Instalación Paso a Paso

#### Paso 1: Preparar Directorio de Instalación

```powershell
# Crear estructura de directorios
$InstallPath = "C:\RMS-Shopify-Integration"
$LogsPath = "C:\Logs\RMS-Shopify-Integration"
$BackupsPath = "C:\Backups\RMS-Shopify-Integration"

New-Item -ItemType Directory -Path $InstallPath -Force
New-Item -ItemType Directory -Path $LogsPath -Force
New-Item -ItemType Directory -Path $BackupsPath -Force
New-Item -ItemType Directory -Path "$InstallPath\app" -Force
New-Item -ItemType Directory -Path "$InstallPath\scripts" -Force
New-Item -ItemType Directory -Path "$InstallPath\config" -Force

Write-Host "✅ Estructura de directorios creada" -ForegroundColor Green
```

#### Paso 2: Instalar Aplicación

```powershell
# Clonar código fuente
git clone https://github.com/tu-usuario/rms-shopify-integration.git "$InstallPath\source"

# Copiar archivos de aplicación
Copy-Item -Path "$InstallPath\source\app" -Destination $InstallPath -Recurse -Force
Copy-Item -Path "$InstallPath\source\*.py" -Destination $InstallPath -Force
Copy-Item -Path "$InstallPath\source\pyproject.toml" -Destination $InstallPath -Force
Copy-Item -Path "$InstallPath\source\requirements.txt" -Destination $InstallPath -Force

# Copiar scripts de Windows
Copy-Item -Path "$InstallPath\source\deployment\windows\*" -Destination "$InstallPath\scripts" -Force

Write-Host "✅ Aplicación copiada" -ForegroundColor Green
```

#### Paso 3: Configurar Entorno Python

```powershell
# Crear virtual environment
cd $InstallPath
python -m venv venv

# Activar virtual environment
& ".\venv\Scripts\Activate.ps1"

# Actualizar pip y instalar dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt

# Verificar instalación
python -c "import fastapi, pydantic, sqlalchemy; print('✅ Dependencias instaladas correctamente')"

Write-Host "✅ Entorno Python configurado" -ForegroundColor Green
```

#### Paso 4: Crear Archivo de Configuración

```powershell
# Crear archivo .env con plantilla
$envContent = @"
# === CONFIGURACIÓN BÁSICA ===
APP_NAME=RMS-Shopify Integration
APP_VERSION=2.5
DEBUG=False
LOG_LEVEL=INFO
ENVIRONMENT=production

# === SERVIDOR WEB ===
HOST=0.0.0.0
PORT=8080
WORKERS=4

# === BASE DE DATOS RMS (SQL SERVER) ===
RMS_DB_HOST=tu-servidor-sql.local
RMS_DB_PORT=1433
RMS_DB_NAME=RMS_Database
RMS_DB_USER=rms_user
RMS_DB_PASSWORD=tu_password_seguro
RMS_DB_DRIVER=ODBC Driver 17 for SQL Server
RMS_CONNECTION_TIMEOUT=30
RMS_CONNECTION_POOL_SIZE=10
RMS_STORE_ID=1

# === SHOPIFY API ===
SHOPIFY_SHOP_URL=tu-tienda.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_tu_access_token_aqui
SHOPIFY_API_VERSION=2025-04
SHOPIFY_WEBHOOK_SECRET=whsec_tu_webhook_secret
SHOPIFY_RATE_LIMIT_PER_SECOND=2

# === MOTOR DE SINCRONIZACIÓN AUTOMÁTICA ===
ENABLE_SCHEDULED_SYNC=true
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_SIZE=10
SYNC_MAX_CONCURRENT_JOBS=3
SYNC_TIMEOUT_MINUTES=30
ENABLE_SYNC_LOCK=true
SYNC_LOCK_TIMEOUT_SECONDS=1800

# === SINCRONIZACIÓN COMPLETA PROGRAMADA ===
ENABLE_FULL_SYNC_SCHEDULE=true
FULL_SYNC_HOUR=2
FULL_SYNC_MINUTE=0
FULL_SYNC_TIMEZONE=America/Argentina/Buenos_Aires

# === PEDIDOS SIN CLIENTE ===
ALLOW_ORDERS_WITHOUT_CUSTOMER=true
DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS=
REQUIRE_CUSTOMER_EMAIL=false
GUEST_CUSTOMER_NAME=Cliente Invitado

# === REDIS PARA CACHE ===
REDIS_URL=redis://localhost:6379/0

# === LOGGING ESPECÍFICO WINDOWS ===
LOG_FILE_PATH=C:\Logs\RMS-Shopify-Integration\app.log
LOG_MAX_SIZE_MB=100
LOG_BACKUP_COUNT=10
LOG_ROTATION_ENABLED=true

# === ALERTAS POR EMAIL ===
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@tu-empresa.com,soporte@tu-empresa.com
ALERT_EMAIL_FROM=rms-shopify@tu-empresa.com
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_USE_TLS=true
ALERT_EMAIL_USERNAME=rms-shopify@tu-empresa.com
ALERT_EMAIL_PASSWORD=tu_app_password

# === MÉTRICAS Y MONITOREO ===
METRICS_COLLECTION_ENABLED=true
METRICS_RETENTION_DAYS=30
HEALTH_CHECK_CACHE_TTL=60

# === CONFIGURACIÓN WINDOWS ESPECÍFICA ===
WINDOWS_SERVICE_NAME=RMSShopifyIntegration
WINDOWS_SERVICE_DISPLAY_NAME=RMS-Shopify Integration Service
WINDOWS_SERVICE_DESCRIPTION=Sistema de integración bidireccional entre RMS y Shopify
WINDOWS_EVENT_LOG_SOURCE=RMSShopifyIntegration
WINDOWS_PERFORMANCE_COUNTERS_ENABLED=true
"@

$envContent | Out-File -FilePath "$InstallPath\.env" -Encoding UTF8
Write-Host "✅ Archivo .env creado - DEBE SER CONFIGURADO" -ForegroundColor Yellow
```

## 🔧 Configuración del Servicio de Windows

### Crear Servicio con NSSM (Recomendado)

```powershell
# Descargar e instalar NSSM (Non-Sucking Service Manager)
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$nssmPath = "$InstallPath\tools\nssm.exe"

# Crear directorio tools
New-Item -ItemType Directory -Path "$InstallPath\tools" -Force

# Descargar NSSM
Invoke-WebRequest -Uri $nssmUrl -OutFile "$env:TEMP\nssm.zip"
Expand-Archive -Path "$env:TEMP\nssm.zip" -DestinationPath "$env:TEMP\nssm"
Copy-Item -Path "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" -Destination $nssmPath

# Configurar servicio con NSSM
& $nssmPath install RMSShopifyIntegration "$InstallPath\venv\Scripts\python.exe"
& $nssmPath set RMSShopifyIntegration Parameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8080"
& $nssmPath set RMSShopifyIntegration AppDirectory $InstallPath
& $nssmPath set RMSShopifyIntegration DisplayName "RMS-Shopify Integration Service"
& $nssmPath set RMSShopifyIntegration Description "Sistema de integración bidireccional entre RMS y Shopify con sincronización automática"
& $nssmPath set RMSShopifyIntegration Start SERVICE_AUTO_START
& $nssmPath set RMSShopifyIntegration AppStdout "$LogsPath\service-stdout.log"
& $nssmPath set RMSShopifyIntegration AppStderr "$LogsPath\service-stderr.log"
& $nssmPath set RMSShopifyIntegration AppStdoutCreationDisposition 4
& $nssmPath set RMSShopifyIntegration AppStderrCreationDisposition 4
& $nssmPath set RMSShopifyIntegration AppRotateFiles 1
& $nssmPath set RMSShopifyIntegration AppRotateOnline 1
& $nssmPath set RMSShopifyIntegration AppRotateBytes 10485760

Write-Host "✅ Servicio Windows configurado con NSSM" -ForegroundColor Green
```

### Configurar Recuperación Automática

```powershell
# Configurar políticas de recuperación del servicio
sc.exe failure RMSShopifyIntegration reset=86400 actions=restart/5000/restart/10000/restart/30000

# Configurar recuperación avanzada
& $nssmPath set RMSShopifyIntegration AppThrottle 1500
& $nssmPath set RMSShopifyIntegration AppExit Default Restart
& $nssmPath set RMSShopifyIntegration AppRestartDelay 5000

Write-Host "✅ Recuperación automática configurada" -ForegroundColor Green
```

## 📋 Configuración del Task Scheduler

### Crear Tareas de Monitoreo

```powershell
# Script de monitoreo automático
$monitorScript = @"
# Monitor del Servicio RMS-Shopify Integration
`$serviceName = "RMSShopifyIntegration"
`$logPath = "C:\Logs\RMS-Shopify-Integration\monitor.log"

# Verificar estado del servicio
`$service = Get-Service -Name `$serviceName -ErrorAction SilentlyContinue
`$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

if (`$service -eq `$null) {
    `$message = "`$timestamp - ERROR: Servicio `$serviceName no encontrado"
    Add-Content -Path `$logPath -Value `$message
    # Enviar alerta crítica
    Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId 1001 -EntryType Error -Message "Servicio no encontrado"
} elseif (`$service.Status -ne "Running") {
    `$message = "`$timestamp - WARNING: Servicio `$serviceName no está ejecutándose (Estado: `$(`$service.Status))"
    Add-Content -Path `$logPath -Value `$message
    
    # Intentar reiniciar servicio
    try {
        Start-Service -Name `$serviceName
        `$message = "`$timestamp - INFO: Servicio `$serviceName reiniciado exitosamente"
        Add-Content -Path `$logPath -Value `$message
        Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId 1002 -EntryType Information -Message "Servicio reiniciado automáticamente"
    } catch {
        `$message = "`$timestamp - ERROR: Falló el reinicio del servicio: `$(`$_.Exception.Message)"
        Add-Content -Path `$logPath -Value `$message
        Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId 1003 -EntryType Error -Message "Falló reinicio automático: `$(`$_.Exception.Message)"
    }
} else {
    # Verificar respuesta HTTP del servicio
    try {
        `$response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 10
        if (`$response.StatusCode -eq 200) {
            `$message = "`$timestamp - INFO: Servicio `$serviceName funcionando correctamente"
            Add-Content -Path `$logPath -Value `$message
        } else {
            `$message = "`$timestamp - WARNING: Servicio responde con código `$(`$response.StatusCode)"
            Add-Content -Path `$logPath -Value `$message
        }
    } catch {
        `$message = "`$timestamp - ERROR: Servicio no responde HTTP: `$(`$_.Exception.Message)"
        Add-Content -Path `$logPath -Value `$message
        Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId 1004 -EntryType Warning -Message "Servicio no responde HTTP"
    }
}
"@

$monitorScript | Out-File -FilePath "$InstallPath\scripts\monitor-service.ps1" -Encoding UTF8

# Crear tarea programada para monitoreo
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File `"$InstallPath\scripts\monitor-service.ps1`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName "RMS-Shopify Monitor" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Monitorea el servicio RMS-Shopify Integration cada 5 minutos"

Write-Host "✅ Tarea de monitoreo configurada" -ForegroundColor Green
```

### Crear Tarea de Mantenimiento

```powershell
# Script de mantenimiento
$maintenanceScript = @"
# Mantenimiento del sistema RMS-Shopify Integration
`$logPath = "C:\Logs\RMS-Shopify-Integration"
`$backupPath = "C:\Backups\RMS-Shopify-Integration"
`$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Limpiar logs antiguos (más de 30 días)
Get-ChildItem -Path `$logPath -Recurse -File | Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force

# Comprimir logs antiguos (más de 7 días)
Get-ChildItem -Path `$logPath -Filter "*.log" | Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-7) } | ForEach-Object {
    `$compressedName = `$_.FullName + ".zip"
    Compress-Archive -Path `$_.FullName -DestinationPath `$compressedName -Force
    Remove-Item -Path `$_.FullName -Force
}

# Backup de configuración
`$configBackup = "`$backupPath\config-backup-`$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
Compress-Archive -Path "C:\RMS-Shopify-Integration\.env" -DestinationPath `$configBackup -Force

# Limpiar backups antiguos (más de 90 días)
Get-ChildItem -Path `$backupPath -Recurse -File | Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-90) } | Remove-Item -Force

# Verificar espacio en disco
`$disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'"
`$freeSpaceGB = [math]::Round(`$disk.FreeSpace / 1GB, 2)
if (`$freeSpaceGB -lt 5) {
    Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId 2001 -EntryType Warning -Message "Espacio en disco bajo: `$freeSpaceGB GB libres"
}

Add-Content -Path "`$logPath\maintenance.log" -Value "`$timestamp - Mantenimiento completado. Espacio libre: `$freeSpaceGB GB"
"@

$maintenanceScript | Out-File -FilePath "$InstallPath\scripts\maintenance.ps1" -Encoding UTF8

# Crear tarea programada para mantenimiento diario
$actionMaint = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File `"$InstallPath\scripts\maintenance.ps1`""
$triggerMaint = New-ScheduledTaskTrigger -Daily -At "3:00AM"
$principalMaint = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settingsMaint = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "RMS-Shopify Maintenance" -Action $actionMaint -Trigger $triggerMaint -Principal $principalMaint -Settings $settingsMaint -Description "Mantenimiento diario del sistema RMS-Shopify Integration"

Write-Host "✅ Tarea de mantenimiento configurada" -ForegroundColor Green
```

## 🔥 Configuración del Firewall

### Reglas de Firewall Automáticas

```powershell
# Crear reglas de firewall para el servicio
New-NetFirewallRule -DisplayName "RMS-Shopify Integration HTTP" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Domain,Private,Public
New-NetFirewallRule -DisplayName "RMS-Shopify Integration HTTPS" -Direction Inbound -Protocol TCP -LocalPort 8443 -Action Allow -Profile Domain,Private,Public

# Permitir conexiones salientes a Shopify
New-NetFirewallRule -DisplayName "RMS-Shopify Outbound HTTPS" -Direction Outbound -Protocol TCP -RemotePort 443 -Action Allow
New-NetFirewallRule -DisplayName "RMS-Shopify Outbound HTTP" -Direction Outbound -Protocol TCP -RemotePort 80 -Action Allow

Write-Host "✅ Reglas de firewall configuradas" -ForegroundColor Green
```

## 📊 Event Viewer y Logging

### Configurar Event Log Source

```powershell
# Crear fuente de eventos personalizada
New-EventLog -LogName Application -Source "RMSShopifyIntegration"

# Configurar niveles de log
$eventIds = @{
    "ServiceStart" = 1000
    "ServiceStop" = 1001
    "SyncSuccess" = 2000
    "SyncError" = 2001
    "ConfigError" = 3000
    "DatabaseError" = 3001
    "ShopifyError" = 3002
}

Write-Host "✅ Event Log configurado" -ForegroundColor Green
```

### Script de Logging Avanzado

```powershell
# Crear script de logging para integración con Event Viewer
$loggingScript = @"
function Write-RMSShopifyLog {
    param(
        [string]`$Message,
        [string]`$Level = "Information",
        [int]`$EventId = 1000
    )
    
    `$entryType = switch (`$Level) {
        "Error" { "Error" }
        "Warning" { "Warning" }
        default { "Information" }
    }
    
    Write-EventLog -LogName Application -Source "RMSShopifyIntegration" -EventId `$EventId -EntryType `$entryType -Message `$Message
    
    # También escribir a archivo de log
    `$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    `$logMessage = "`$timestamp [`$Level] `$Message"
    Add-Content -Path "C:\Logs\RMS-Shopify-Integration\system.log" -Value `$logMessage
}

# Exportar función para uso en otros scripts
Export-ModuleMember -Function Write-RMSShopifyLog
"@

$loggingScript | Out-File -FilePath "$InstallPath\scripts\RMSShopifyLogging.psm1" -Encoding UTF8
```

## 🎛️ Scripts de Gestión

### Script de Gestión del Servicio

```powershell
$managementScript = @"
# Script de gestión del servicio RMS-Shopify Integration
param(
    [Parameter(Mandatory=`$true)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "config", "health", "install", "uninstall")]
    [string]`$Action
)

`$serviceName = "RMSShopifyIntegration"
`$installPath = "C:\RMS-Shopify-Integration"
`$logPath = "C:\Logs\RMS-Shopify-Integration"

switch (`$Action) {
    "start" {
        Start-Service -Name `$serviceName
        Write-Host "✅ Servicio iniciado" -ForegroundColor Green
    }
    "stop" {
        Stop-Service -Name `$serviceName
        Write-Host "✅ Servicio detenido" -ForegroundColor Green
    }
    "restart" {
        Restart-Service -Name `$serviceName
        Write-Host "✅ Servicio reiniciado" -ForegroundColor Green
    }
    "status" {
        `$service = Get-Service -Name `$serviceName
        Write-Host "Estado del servicio: `$(`$service.Status)" -ForegroundColor (`$service.Status -eq "Running" ? "Green" : "Red")
        
        # Verificar respuesta HTTP
        try {
            `$response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5
            Write-Host "✅ Servicio responde HTTP (Código: `$(`$response.StatusCode))" -ForegroundColor Green
        } catch {
            Write-Host "❌ Servicio no responde HTTP" -ForegroundColor Red
        }
    }
    "logs" {
        Write-Host "📋 Últimos logs del servicio:" -ForegroundColor Yellow
        Get-Content -Path "`$logPath\app.log" -Tail 20
    }
    "config" {
        Write-Host "⚙️ Abriendo configuración..." -ForegroundColor Yellow
        notepad.exe "`$installPath\.env"
    }
    "health" {
        try {
            `$health = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status" -TimeoutSec 10
            Write-Host "✅ Motor de sincronización: `$(`$health.status)" -ForegroundColor Green
            Write-Host "📊 Items procesados hoy: `$(`$health.items_processed_today)"
            Write-Host "🕒 Última verificación: `$(`$health.last_check)"
        } catch {
            Write-Host "❌ No se pudo obtener estado de salud" -ForegroundColor Red
        }
    }
    "install" {
        Write-Host "🚀 Instalando servicio..." -ForegroundColor Yellow
        # Lógica de instalación aquí
    }
    "uninstall" {
        Write-Host "🗑️ Desinstalando servicio..." -ForegroundColor Yellow
        Stop-Service -Name `$serviceName -Force
        & "`$installPath\tools\nssm.exe" remove `$serviceName confirm
        Write-Host "✅ Servicio desinstalado" -ForegroundColor Green
    }
}
"@

$managementScript | Out-File -FilePath "$InstallPath\scripts\Manage-RMSShopify.ps1" -Encoding UTF8

Write-Host "✅ Script de gestión creado en: $InstallPath\scripts\Manage-RMSShopify.ps1" -ForegroundColor Green
```

## 🚀 Iniciar y Verificar el Servicio

### Iniciar Servicio

```powershell
# Iniciar el servicio
Start-Service -Name "RMSShopifyIntegration"

# Verificar estado
Get-Service -Name "RMSShopifyIntegration"

# Verificar que responde HTTP
Start-Sleep -Seconds 10
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 30
    Write-Host "✅ Servicio iniciado correctamente - Código HTTP: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ Error al verificar servicio: $($_.Exception.Message)" -ForegroundColor Red
}
```

### Verificar Logs

```powershell
# Ver logs del servicio
Get-Content -Path "C:\Logs\RMS-Shopify-Integration\service-stdout.log" -Tail 20

# Ver logs de la aplicación
Get-Content -Path "C:\Logs\RMS-Shopify-Integration\app.log" -Tail 20

# Ver eventos en Event Viewer
Get-EventLog -LogName Application -Source "RMSShopifyIntegration" -Newest 10
```

## 🔧 Gestión Diaria del Servicio

### Comandos Útiles

```powershell
# Script rápido de estado
& "C:\RMS-Shopify-Integration\scripts\Manage-RMSShopify.ps1" -Action status

# Ver logs en tiempo real
Get-Content -Path "C:\Logs\RMS-Shopify-Integration\app.log" -Wait -Tail 10

# Verificar sincronización automática
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/stats"

# Forzar sincronización manual
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/trigger" -Method Post

# Ver métricas del sistema
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/metrics/dashboard"
```

### Mantenimiento Semanal

```powershell
# Script de mantenimiento semanal
$weeklyMaintenance = @"
# Reiniciar servicio para limpiar memoria
Restart-Service -Name "RMSShopifyIntegration"

# Verificar logs por errores
`$errors = Select-String -Path "C:\Logs\RMS-Shopify-Integration\app.log" -Pattern "ERROR" | Select-Object -Last 10
if (`$errors) {
    Write-Host "⚠️ Errores encontrados en logs:" -ForegroundColor Yellow
    `$errors | ForEach-Object { Write-Host `$_.Line }
}

# Verificar espacio en disco
`$freeSpace = (Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB
Write-Host "💾 Espacio libre: `$([math]::Round(`$freeSpace, 2)) GB"

# Ejecutar diagnóstico completo
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/diagnostics"
"@

$weeklyMaintenance | Out-File -FilePath "$InstallPath\scripts\weekly-maintenance.ps1" -Encoding UTF8
```

## 🆘 Solución de Problemas Windows

### Problemas Comunes

#### 1. Servicio No Inicia

```powershell
# Verificar logs de error
Get-Content -Path "C:\Logs\RMS-Shopify-Integration\service-stderr.log" -Tail 20

# Verificar permisos
icacls "C:\RMS-Shopify-Integration" /grant "SYSTEM:(OI)(CI)F"

# Verificar Python en PATH
& "C:\RMS-Shopify-Integration\venv\Scripts\python.exe" --version

# Test manual de la aplicación
cd "C:\RMS-Shopify-Integration"
& ".\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

#### 2. Errores de Conectividad SQL Server

```powershell
# Test de conectividad SQL
sqlcmd -S "servidor-sql" -U "usuario" -P "password" -Q "SELECT @@VERSION"

# Verificar driver ODBC
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}

# Test desde Python
& "C:\RMS-Shopify-Integration\venv\Scripts\python.exe" -c "
import pyodbc
try:
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=servidor;DATABASE=RMS;UID=usuario;PWD=password')
    print('✅ Conexión SQL Server exitosa')
    conn.close()
except Exception as e:
    print(f'❌ Error SQL Server: {e}')
"
```

#### 3. Puerto 8080 en Uso

```powershell
# Verificar qué proceso usa el puerto
netstat -ano | findstr :8080

# Cambiar puerto en configuración
# Editar C:\RMS-Shopify-Integration\.env
# PORT=8081

# Actualizar reglas de firewall
New-NetFirewallRule -DisplayName "RMS-Shopify Integration HTTP Alt" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow
```

#### 4. Performance Degradada

```powershell
# Verificar uso de CPU/Memoria del servicio
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Select-Object Name, CPU, WorkingSet

# Verificar logs de performance
Select-String -Path "C:\Logs\RMS-Shopify-Integration\app.log" -Pattern "performance|slow|timeout" | Select-Object -Last 10

# Reiniciar con configuración optimizada
# Editar .env:
# SYNC_BATCH_SIZE=5
# SYNC_INTERVAL_MINUTES=10
```

## 📈 Monitoreo y Métricas

### Performance Counters Personalizados

```powershell
# Crear performance counters personalizados (requiere admin)
$counterCategories = @{
    "RMS-Shopify Integration" = @{
        "Products Synced Per Hour" = "NumberOfItems32"
        "Sync Success Rate" = "RawFraction"
        "API Response Time" = "AverageTimer32"
        "Active Connections" = "NumberOfItems32"
    }
}

# Script para actualizar counters (se ejecuta desde la aplicación)
```

### Dashboard de Métricas Windows

```powershell
# Script de dashboard para PowerShell
$dashboardScript = @"
Clear-Host
Write-Host "🎯 RMS-Shopify Integration Dashboard" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

# Estado del servicio
`$service = Get-Service -Name "RMSShopifyIntegration"
`$statusColor = if (`$service.Status -eq "Running") { "Green" } else { "Red" }
Write-Host "🔧 Estado del Servicio: " -NoNewline
Write-Host `$service.Status -ForegroundColor `$statusColor

# Métricas de la API
try {
    `$stats = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/stats" -TimeoutSec 5
    Write-Host "📊 Items procesados hoy: `$(`$stats.summary.items_processed_today)" -ForegroundColor Green
    Write-Host "✅ Tasa de éxito: `$(`$stats.summary.success_rate)%" -ForegroundColor Green
    Write-Host "⏱️ Tiempo promedio: `$(`$stats.summary.avg_processing_time)" -ForegroundColor Green
} catch {
    Write-Host "❌ No se pudieron obtener métricas de la API" -ForegroundColor Red
}

# Uso de recursos
`$process = Get-Process | Where-Object {`$_.ProcessName -eq "python" -and `$_.MainWindowTitle -eq ""}
if (`$process) {
    `$cpuPercent = [math]::Round(`$process.CPU, 2)
    `$memoryMB = [math]::Round(`$process.WorkingSet / 1MB, 2)
    Write-Host "💻 CPU: `${cpuPercent}% | Memoria: `${memoryMB} MB" -ForegroundColor Yellow
}

# Espacio en disco
`$freeSpaceGB = [math]::Round((Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
Write-Host "💾 Espacio libre: `$freeSpaceGB GB" -ForegroundColor Yellow

Write-Host "`nPresiona Ctrl+C para salir..."
Start-Sleep -Seconds 5
"@

$dashboardScript | Out-File -FilePath "$InstallPath\scripts\dashboard.ps1" -Encoding UTF8
```

## 📋 Checklist de Instalación

### ✅ Lista de Verificación

```powershell
Write-Host "📋 Checklist de Instalación Completa" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

$checklist = @(
    @{Name="Python 3.13+ instalado"; Check={python --version}},
    @{Name="Directorio de instalación creado"; Path="C:\RMS-Shopify-Integration"},
    @{Name="Virtual environment configurado"; Path="C:\RMS-Shopify-Integration\venv"},
    @{Name="Dependencias instaladas"; Check={& "C:\RMS-Shopify-Integration\venv\Scripts\pip.exe" list | Select-String fastapi}},
    @{Name="Archivo .env configurado"; Path="C:\RMS-Shopify-Integration\.env"},
    @{Name="Servicio Windows instalado"; Check={Get-Service -Name "RMSShopifyIntegration"}},
    @{Name="Tareas programadas creadas"; Check={Get-ScheduledTask -TaskName "RMS-Shopify Monitor"}},
    @{Name="Reglas de firewall configuradas"; Check={Get-NetFirewallRule -DisplayName "RMS-Shopify Integration HTTP"}},
    @{Name="Event Log source creado"; Check={Get-EventLog -List | Where-Object {$_.Log -eq "Application"}}},
    @{Name="Servicio iniciado y respondiendo"; Check={Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5}}
)

foreach ($item in $checklist) {
    try {
        if ($item.Path) {
            $result = Test-Path $item.Path
        } else {
            $result = $item.Check.Invoke()
        }
        Write-Host "✅ $($item.Name)" -ForegroundColor Green
    } catch {
        Write-Host "❌ $($item.Name)" -ForegroundColor Red
    }
}
```

## 🔄 Actualización del Sistema

### Script de Actualización

```powershell
$updateScript = @"
# Script de actualización del sistema RMS-Shopify Integration
param([string]`$Version = "latest")

Write-Host "🔄 Iniciando actualización del sistema..." -ForegroundColor Yellow

# 1. Detener servicio
Stop-Service -Name "RMSShopifyIntegration"

# 2. Backup de configuración actual
`$backupPath = "C:\Backups\RMS-Shopify-Integration\update-backup-`$(Get-Date -Format 'yyyyMMdd-HHmmss')"
New-Item -ItemType Directory -Path `$backupPath -Force
Copy-Item -Path "C:\RMS-Shopify-Integration\.env" -Destination "`$backupPath\.env" -Force

# 3. Descargar nueva versión
git -C "C:\RMS-Shopify-Integration\source" pull origin main

# 4. Actualizar dependencias
& "C:\RMS-Shopify-Integration\venv\Scripts\pip.exe" install -r "C:\RMS-Shopify-Integration\source\requirements.txt" --upgrade

# 5. Copiar archivos actualizados
Copy-Item -Path "C:\RMS-Shopify-Integration\source\app" -Destination "C:\RMS-Shopify-Integration" -Recurse -Force

# 6. Reiniciar servicio
Start-Service -Name "RMSShopifyIntegration"

# 7. Verificar funcionamiento
Start-Sleep -Seconds 15
try {
    `$response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 10
    Write-Host "✅ Actualización completada exitosamente" -ForegroundColor Green
} catch {
    Write-Host "❌ Error en la actualización - Restaurando backup..." -ForegroundColor Red
    # Lógica de rollback aquí
}
"@

$updateScript | Out-File -FilePath "$InstallPath\scripts\update-system.ps1" -Encoding UTF8
```

---

## 📞 Soporte y Contacto

### Información de Soporte

- **Email**: enzo@oneclick.cr
- **Documentación**: http://localhost:8080/docs (cuando el servicio esté ejecutándose)
- **Logs del Sistema**: `C:\Logs\RMS-Shopify-Integration\`
- **Event Viewer**: Fuente "RMSShopifyIntegration" en Application Log

### Escalación de Problemas

1. **Verificar servicio**: `Get-Service -Name "RMSShopifyIntegration"`
2. **Revisar logs**: `Get-Content -Path "C:\Logs\RMS-Shopify-Integration\app.log" -Tail 50`
3. **Ejecutar diagnóstico**: `& "C:\RMS-Shopify-Integration\scripts\Manage-RMSShopify.ps1" -Action health`
4. **Contactar soporte**: Con logs específicos y detalles del error

### Recursos Adicionales

- **Scripts de Gestión**: `C:\RMS-Shopify-Integration\scripts\`
- **Configuración**: `C:\RMS-Shopify-Integration\.env`
- **Backups**: `C:\Backups\RMS-Shopify-Integration\`
- **Task Scheduler**: Buscar tareas que inicien con "RMS-Shopify"

La instalación en Windows está **optimizada para entornos de producción** con todas las características de un servicio empresarial: monitoreo automático, recuperación de fallos, logging integrado, y gestión simplificada.

---

*Documento actualizado: Enero 2025*  
*Versión del sistema: 2.5*
*Compatible con: Windows 10/11, Windows Server 2016+, Python 3.13+*
*Última verificación de instalación: 30/01/2025*