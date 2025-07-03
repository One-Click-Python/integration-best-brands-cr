# Script de Gestión del Servicio RMS-Shopify Integration para Windows
# Proporciona comandos unificados para administrar el servicio

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "uninstall", "start", "stop", "restart", "status", "logs", "monitor", "config")]
    [string]$Action,
    
    [string]$ServiceName = "RMSShopifyIntegration",
    [string]$AppPath = "C:\RMS-Shopify-Integration"
)

$LogFile = "C:\Logs\RMS-Shopify-Integration\management.log"
$ApiUrl = "http://localhost:8080"

function Write-Log($Message, $Color = "White") {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "$Timestamp - $Message"
    
    # Escribir a archivo
    $LogDir = Split-Path $LogFile -Parent
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    Add-Content -Path $LogFile -Value $LogMessage
    
    # Escribir a consola
    Write-Host $LogMessage -ForegroundColor $Color
}

function Test-AdminRights {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-Service {
    if (-not (Test-AdminRights)) {
        Write-Log "ERROR: Se requieren permisos de Administrador para instalar el servicio" "Red"
        return $false
    }
    
    Write-Log "Instalando servicio $ServiceName..." "Yellow"
    
    try {
        # Ejecutar script de instalación
        $InstallScript = Join-Path $AppPath "deployment\windows\install-windows-service.ps1"
        if (Test-Path $InstallScript) {
            & $InstallScript
            Write-Log "Servicio instalado exitosamente" "Green"
            return $true
        } else {
            Write-Log "ERROR: Script de instalación no encontrado: $InstallScript" "Red"
            return $false
        }
    } catch {
        Write-Log "ERROR: Fallo al instalar servicio: $_" "Red"
        return $false
    }
}

function Uninstall-Service {
    if (-not (Test-AdminRights)) {
        Write-Log "ERROR: Se requieren permisos de Administrador para desinstalar el servicio" "Red"
        return $false
    }
    
    Write-Log "Desinstalando servicio $ServiceName..." "Yellow"
    
    try {
        # Detener servicio si está ejecutándose
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($Service -and $Service.Status -eq "Running") {
            Stop-Service -Name $ServiceName -Force
            Write-Log "Servicio detenido" "Yellow"
        }
        
        # Desinstalar servicio
        & "$AppPath\venv\Scripts\python.exe" "$AppPath\service.py" remove
        
        # Eliminar tareas programadas
        Unregister-ScheduledTask -TaskName "RMS-Shopify-Monitor" -Confirm:$false -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName "RMS-Shopify-NightSync" -Confirm:$false -ErrorAction SilentlyContinue
        
        Write-Log "Servicio desinstalado exitosamente" "Green"
        return $true
    } catch {
        Write-Log "ERROR: Fallo al desinstalar servicio: $_" "Red"
        return $false
    }
}

function Start-ServiceSafe {
    Write-Log "Iniciando servicio $ServiceName..." "Yellow"
    
    try {
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $Service) {
            Write-Log "ERROR: Servicio $ServiceName no está instalado" "Red"
            return $false
        }
        
        if ($Service.Status -eq "Running") {
            Write-Log "Servicio ya está ejecutándose" "Green"
            return $true
        }
        
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 10
        
        $Service.Refresh()
        if ($Service.Status -eq "Running") {
            Write-Log "Servicio iniciado exitosamente" "Green"
            
            # Verificar API después de unos segundos
            Start-Sleep -Seconds 20
            Test-ApiHealth
            return $true
        } else {
            Write-Log "ERROR: Servicio no pudo iniciarse. Estado: $($Service.Status)" "Red"
            return $false
        }
    } catch {
        Write-Log "ERROR: Fallo al iniciar servicio: $_" "Red"
        return $false
    }
}

function Stop-ServiceSafe {
    Write-Log "Deteniendo servicio $ServiceName..." "Yellow"
    
    try {
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $Service) {
            Write-Log "ERROR: Servicio $ServiceName no está instalado" "Red"
            return $false
        }
        
        if ($Service.Status -eq "Stopped") {
            Write-Log "Servicio ya está detenido" "Green"
            return $true
        }
        
        Stop-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 5
        
        $Service.Refresh()
        if ($Service.Status -eq "Stopped") {
            Write-Log "Servicio detenido exitosamente" "Green"
            return $true
        } else {
            Write-Log "WARNING: Servicio no se detuvo completamente. Estado: $($Service.Status)" "Yellow"
            return $false
        }
    } catch {
        Write-Log "ERROR: Fallo al detener servicio: $_" "Red"
        return $false
    }
}

function Restart-ServiceSafe {
    Write-Log "Reiniciando servicio $ServiceName..." "Yellow"
    
    if (Stop-ServiceSafe) {
        Start-Sleep -Seconds 3
        return Start-ServiceSafe
    }
    return $false
}

function Get-ServiceStatus {
    Write-Host "=== Estado del Servicio RMS-Shopify Integration ===" -ForegroundColor Green
    
    # Estado del servicio
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($Service) {
        Write-Host "Servicio Windows: " -NoNewline
        switch ($Service.Status) {
            "Running" { Write-Host $Service.Status -ForegroundColor Green }
            "Stopped" { Write-Host $Service.Status -ForegroundColor Red }
            default { Write-Host $Service.Status -ForegroundColor Yellow }
        }
        Write-Host "Tipo de inicio: $($Service.StartType)" -ForegroundColor Cyan
    } else {
        Write-Host "Servicio: NO INSTALADO" -ForegroundColor Red
        return
    }
    
    # Estado de la API
    Write-Host "`nVerificando API..." -ForegroundColor Yellow
    Test-ApiHealth
    
    # Estado del motor de sincronización
    Write-Host "`nEstado del motor de sincronización:" -ForegroundColor Yellow
    try {
        $SyncStatus = Invoke-RestMethod -Uri "$ApiUrl/api/v1/sync/monitor/status" -TimeoutSec 10
        if ($SyncStatus.data.running) {
            Write-Host "Motor de sincronización: ACTIVO" -ForegroundColor Green
            Write-Host "Intervalo: $($SyncStatus.data.sync_interval_minutes) minutos" -ForegroundColor Cyan
            
            if ($SyncStatus.data.change_detector) {
                $detector = $SyncStatus.data.change_detector
                Write-Host "Total verificaciones: $($detector.total_checks)" -ForegroundColor Cyan
                Write-Host "Cambios detectados: $($detector.changes_detected)" -ForegroundColor Cyan
                Write-Host "Items sincronizados: $($detector.items_synced)" -ForegroundColor Cyan
                Write-Host "Errores: $($detector.errors)" -ForegroundColor $(if($detector.errors -gt 0) {"Red"} else {"Green"})
            }
        } else {
            Write-Host "Motor de sincronización: INACTIVO" -ForegroundColor Red
        }
    } catch {
        Write-Host "Motor de sincronización: NO DISPONIBLE" -ForegroundColor Red
    }
    
    # Tareas programadas
    Write-Host "`nTareas programadas:" -ForegroundColor Yellow
    $MonitorTask = Get-ScheduledTask -TaskName "RMS-Shopify-Monitor" -ErrorAction SilentlyContinue
    $NightSyncTask = Get-ScheduledTask -TaskName "RMS-Shopify-NightSync" -ErrorAction SilentlyContinue
    
    if ($MonitorTask) {
        Write-Host "Monitor (cada 5 min): $($MonitorTask.State)" -ForegroundColor Cyan
    } else {
        Write-Host "Monitor: NO CONFIGURADO" -ForegroundColor Red
    }
    
    if ($NightSyncTask) {
        Write-Host "Sync nocturno (3 AM): $($NightSyncTask.State)" -ForegroundColor Cyan
    } else {
        Write-Host "Sync nocturno: NO CONFIGURADO" -ForegroundColor Red
    }
}

function Test-ApiHealth {
    try {
        $Response = Invoke-RestMethod -Uri "$ApiUrl/health" -TimeoutSec 10
        Write-Host "API Health: DISPONIBLE" -ForegroundColor Green
        if ($Response.status -eq "healthy") {
            Write-Host "Estado: SALUDABLE" -ForegroundColor Green
        } else {
            Write-Host "Estado: $($Response.status)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "API Health: NO DISPONIBLE" -ForegroundColor Red
        Write-Host "Error: $_" -ForegroundColor Red
    }
}

function Show-ServiceLogs {
    Write-Host "=== Logs del Servicio RMS-Shopify Integration ===" -ForegroundColor Green
    
    # Logs del servicio
    $ServiceLogFile = "C:\Logs\RMS-Shopify-Integration\service.log"
    if (Test-Path $ServiceLogFile) {
        Write-Host "`nÚltimas 20 líneas del log del servicio:" -ForegroundColor Yellow
        Get-Content $ServiceLogFile -Tail 20 | ForEach-Object { 
            if ($_ -match "ERROR") {
                Write-Host $_ -ForegroundColor Red
            } elseif ($_ -match "WARNING") {
                Write-Host $_ -ForegroundColor Yellow
            } elseif ($_ -match "SUCCESS") {
                Write-Host $_ -ForegroundColor Green
            } else {
                Write-Host $_
            }
        }
    } else {
        Write-Host "No se encontró archivo de log del servicio" -ForegroundColor Red
    }
    
    # Event Viewer logs
    Write-Host "`nÚltimos eventos del sistema (últimas 24 horas):" -ForegroundColor Yellow
    try {
        $Events = Get-WinEvent -FilterHashtable @{LogName='System'; ID=7034,7035,7036; StartTime=(Get-Date).AddDays(-1)} | 
                  Where-Object { $_.Message -like "*$ServiceName*" } | 
                  Select-Object -First 10
        
        if ($Events) {
            $Events | ForEach-Object {
                $Color = switch ($_.Id) {
                    7034 { "Red" }    # Service crashed
                    7035 { "Green" }  # Service started successfully
                    7036 { "Yellow" } # Service state change
                    default { "White" }
                }
                Write-Host "$($_.TimeCreated) - ID $($_.Id): $($_.Message)" -ForegroundColor $Color
            }
        } else {
            Write-Host "No hay eventos recientes del servicio en Event Viewer" -ForegroundColor Gray
        }
    } catch {
        Write-Host "No se pudieron obtener eventos del sistema: $_" -ForegroundColor Red
    }
}

function Start-ServiceMonitor {
    Write-Log "Iniciando monitor continuo del servicio..." "Yellow"
    Write-Host "Presiona Ctrl+C para detener el monitor" -ForegroundColor Yellow
    
    try {
        while ($true) {
            Clear-Host
            Write-Host "=== Monitor RMS-Shopify Integration - $(Get-Date) ===" -ForegroundColor Cyan
            
            Get-ServiceStatus
            
            Write-Host "`n--- Esperando 30 segundos para próxima verificación ---" -ForegroundColor Gray
            Start-Sleep -Seconds 30
        }
    } catch [System.Management.Automation.PipelineStoppedException] {
        Write-Log "Monitor detenido por el usuario" "Yellow"
    }
}

function Show-Configuration {
    Write-Host "=== Configuración RMS-Shopify Integration ===" -ForegroundColor Green
    
    $EnvFile = Join-Path $AppPath ".env"
    if (Test-Path $EnvFile) {
        Write-Host "`nConfiguración actual (.env):" -ForegroundColor Yellow
        $EnvContent = Get-Content $EnvFile
        $EnvContent | ForEach-Object {
            if ($_ -match "^#" -or $_ -eq "") {
                # Comentarios en gris
                Write-Host $_ -ForegroundColor Gray
            } elseif ($_ -match "PASSWORD|TOKEN|SECRET") {
                # Ocultar valores sensibles
                $parts = $_ -split "=", 2
                Write-Host "$($parts[0])=***HIDDEN***" -ForegroundColor Yellow
            } else {
                Write-Host $_ -ForegroundColor White
            }
        }
    } else {
        Write-Host "Archivo .env no encontrado en: $EnvFile" -ForegroundColor Red
    }
    
    Write-Host "`nUbicaciones importantes:" -ForegroundColor Yellow
    Write-Host "Aplicación: $AppPath" -ForegroundColor Cyan
    Write-Host "Logs: C:\Logs\RMS-Shopify-Integration\" -ForegroundColor Cyan
    Write-Host "Configuración: $EnvFile" -ForegroundColor Cyan
    
    Write-Host "`nPuertos y URLs:" -ForegroundColor Yellow
    Write-Host "API Local: $ApiUrl" -ForegroundColor Cyan
    Write-Host "Health Check: $ApiUrl/health" -ForegroundColor Cyan
    Write-Host "Documentación: $ApiUrl/docs" -ForegroundColor Cyan
}

# Función principal
function Main {
    Write-Log "Ejecutando acción: $Action" "Cyan"
    
    switch ($Action.ToLower()) {
        "install" { 
            $result = Install-Service
            if (-not $result) { exit 1 }
        }
        "uninstall" { 
            $result = Uninstall-Service
            if (-not $result) { exit 1 }
        }
        "start" { 
            $result = Start-ServiceSafe
            if (-not $result) { exit 1 }
        }
        "stop" { 
            $result = Stop-ServiceSafe
            if (-not $result) { exit 1 }
        }
        "restart" { 
            $result = Restart-ServiceSafe
            if (-not $result) { exit 1 }
        }
        "status" { Get-ServiceStatus }
        "logs" { Show-ServiceLogs }
        "monitor" { Start-ServiceMonitor }
        "config" { Show-Configuration }
        default { 
            Write-Log "Acción no reconocida: $Action" "Red"
            exit 1
        }
    }
}

# Ejecutar función principal
Main