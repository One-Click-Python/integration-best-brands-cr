# RMS-Shopify Integration - Instalación como Servicio de Windows
# PowerShell Script para configurar el servicio en Windows Server/Desktop

param(
    [string]$ServiceName = "RMSShopifyIntegration",
    [string]$AppPath = "C:\RMS-Shopify-Integration",
    [string]$PythonPath = "",
    [string]$LogPath = "C:\Logs\RMS-Shopify-Integration"
)

# Verificar si se ejecuta como Administrador
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "Este script debe ejecutarse como Administrador"
    Write-Host "Presiona cualquier tecla para salir..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "🚀 Instalando RMS-Shopify Integration como Servicio de Windows..." -ForegroundColor Green

# 1. Crear directorios
Write-Host "📁 Creando directorios..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $AppPath | Out-Null
New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
New-Item -ItemType Directory -Force -Path "$AppPath\temp" | Out-Null

# 2. Detectar Python si no se especificó
if ([string]::IsNullOrEmpty($PythonPath)) {
    Write-Host "🔍 Detectando instalación de Python..." -ForegroundColor Yellow
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrEmpty($PythonPath)) {
        $PythonPath = (Get-Command py -ErrorAction SilentlyContinue).Source
    }
    if ([string]::IsNullOrEmpty($PythonPath)) {
        Write-Error "No se encontró Python. Instala Python 3.9+ y vuelve a ejecutar."
        exit 1
    }
}

Write-Host "✅ Python encontrado en: $PythonPath" -ForegroundColor Green

# 3. Copiar archivos de la aplicación
Write-Host "📋 Copiando archivos de la aplicación..." -ForegroundColor Yellow
$SourcePath = Split-Path -Parent $PSScriptRoot
Copy-Item -Path "$SourcePath\app" -Destination $AppPath -Recurse -Force
Copy-Item -Path "$SourcePath\requirements.txt" -Destination $AppPath -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$SourcePath\pyproject.toml" -Destination $AppPath -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$SourcePath\.env.example" -Destination $AppPath -Force

# 4. Instalar dependencias
Write-Host "📦 Instalando dependencias de Python..." -ForegroundColor Yellow
Set-Location $AppPath

# Crear virtual environment
& $PythonPath -m venv venv
& "$AppPath\venv\Scripts\pip.exe" install --upgrade pip
if (Test-Path "requirements.txt") {
    & "$AppPath\venv\Scripts\pip.exe" install -r requirements.txt
} else {
    # Instalar dependencias básicas si no hay requirements.txt
    & "$AppPath\venv\Scripts\pip.exe" install fastapi uvicorn sqlalchemy psycopg2-binary redis celery pydantic aiohttp
}

# 5. Crear script de servicio
Write-Host "⚙️ Creando script de servicio..." -ForegroundColor Yellow
$ServiceScript = @"
import sys
import os
import time
import logging
import subprocess
from pathlib import Path
import win32serviceutil
import win32service
import win32event
import servicemanager

class RMSShopifyService(win32serviceutil.ServiceFramework):
    _svc_name_ = "$ServiceName"
    _svc_display_name_ = "RMS-Shopify Integration Service"
    _svc_description_ = "Servicio de integración bidireccional entre RMS y Shopify con detección automática de cambios"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
        self.app_path = r"$AppPath"
        self.python_exe = r"$AppPath\venv\Scripts\python.exe"
        self.log_path = r"$LogPath"
        
        # Configurar logging
        self.setup_logging()
        
    def setup_logging(self):
        log_file = os.path.join(self.log_path, "service.log")
        os.makedirs(self.log_path, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("🛑 Deteniendo servicio RMS-Shopify Integration...")
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=30)
                self.logger.info("✅ Aplicación detenida correctamente")
            except Exception as e:
                self.logger.error(f"Error deteniendo aplicación: {e}")
                if self.process:
                    self.process.kill()
                    
        win32event.SetEvent(self.hWaitStop)
        
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.logger.info("🚀 Iniciando servicio RMS-Shopify Integration...")
        self.main()
        
    def main(self):
        # Cambiar al directorio de la aplicación
        os.chdir(self.app_path)
        
        # Configurar variables de entorno
        env_file = os.path.join(self.app_path, ".env")
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        
        while True:
            try:
                # Verificar si se debe detener
                result = win32event.WaitForSingleObject(self.hWaitStop, 5000)
                if result == win32event.WAIT_OBJECT_0:
                    break
                    
                # Iniciar la aplicación
                self.logger.info("🔄 Iniciando aplicación FastAPI...")
                cmd = [
                    self.python_exe, "-m", "uvicorn", 
                    "app.main:app", 
                    "--host", "0.0.0.0", 
                    "--port", "8080",
                    "--workers", "1"
                ]
                
                self.process = subprocess.Popen(
                    cmd,
                    cwd=self.app_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                self.logger.info(f"✅ Aplicación iniciada con PID: {self.process.pid}")
                
                # Monitorear el proceso
                while True:
                    # Verificar si se debe detener el servicio
                    result = win32event.WaitForSingleObject(self.hWaitStop, 10000)
                    if result == win32event.WAIT_OBJECT_0:
                        break
                        
                    # Verificar si el proceso sigue ejecutándose
                    if self.process.poll() is not None:
                        self.logger.error(f"❌ Aplicación terminó inesperadamente con código: {self.process.returncode}")
                        
                        # Leer logs de error
                        stdout, stderr = self.process.communicate()
                        if stderr:
                            self.logger.error(f"Error stderr: {stderr}")
                            
                        # Esperar antes de reiniciar
                        self.logger.info("⏳ Esperando 30 segundos antes de reiniciar...")
                        time.sleep(30)
                        break
                        
            except Exception as e:
                self.logger.error(f"Error en servicio: {e}")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(RMSShopifyService)
"@

$ServiceScript | Out-File -FilePath "$AppPath\service.py" -Encoding UTF8

# 6. Instalar pywin32 para el servicio
Write-Host "🔧 Instalando pywin32 para soporte de servicios..." -ForegroundColor Yellow
& "$AppPath\venv\Scripts\pip.exe" install pywin32

# 7. Crear archivo de configuración .env si no existe
if (-not (Test-Path "$AppPath\.env")) {
    Write-Host "⚙️ Creando archivo .env..." -ForegroundColor Yellow
    Copy-Item "$AppPath\.env.example" "$AppPath\.env"
    Write-Host "⚠️ IMPORTANTE: Configura el archivo .env antes de iniciar el servicio" -ForegroundColor Red
}

# 8. Instalar el servicio
Write-Host "🔧 Instalando servicio de Windows..." -ForegroundColor Yellow
& "$AppPath\venv\Scripts\python.exe" "$AppPath\service.py" install

# 9. Crear tareas programadas de Windows
Write-Host "⏰ Configurando tareas programadas..." -ForegroundColor Yellow

# Crear tarea de monitoreo cada 5 minutos
$MonitorAction = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File `"$AppPath\deployment\windows\monitor-service.ps1`""
$MonitorTrigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -At (Get-Date) -Once
$MonitorSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "RMS-Shopify-Monitor" -Action $MonitorAction -Trigger $MonitorTrigger -Settings $MonitorSettings -User "SYSTEM" -Force

# Crear tarea de sincronización nocturna
$NightSyncAction = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-Command `"Invoke-RestMethod -Uri 'http://localhost:8080/api/v1/sync/monitor/force-full-sync' -Method POST`""
$NightSyncTrigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "RMS-Shopify-NightSync" -Action $NightSyncAction -Trigger $NightSyncTrigger -User "SYSTEM" -Force

# 10. Crear scripts de utilidad
Write-Host "🛠️ Creando scripts de utilidad..." -ForegroundColor Yellow

# Script de monitoreo
$MonitorScript = @'
# Monitor del Servicio RMS-Shopify Integration
param([switch]$Silent)

$ServiceName = "RMSShopifyIntegration"
$ApiUrl = "http://localhost:8080"
$LogFile = "C:\Logs\RMS-Shopify-Integration\monitor.log"

function Write-Log($Message) {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "$Timestamp - $Message"
    Add-Content -Path $LogFile -Value $LogMessage
    if (-not $Silent) { Write-Host $LogMessage }
}

# Verificar servicio
$Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($Service -eq $null) {
    Write-Log "ERROR: Servicio $ServiceName no existe"
    exit 1
}

if ($Service.Status -ne "Running") {
    Write-Log "WARNING: Servicio $ServiceName no está ejecutándose. Intentando iniciar..."
    try {
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 30
        Write-Log "SUCCESS: Servicio $ServiceName iniciado"
    } catch {
        Write-Log "ERROR: No se pudo iniciar servicio: $_"
        exit 1
    }
}

# Verificar API
try {
    $Response = Invoke-RestMethod -Uri "$ApiUrl/health" -TimeoutSec 10 -ErrorAction Stop
    Write-Log "SUCCESS: API health check passed"
} catch {
    Write-Log "ERROR: API health check failed: $_"
    # Intentar reiniciar servicio
    try {
        Restart-Service -Name $ServiceName -Force
        Write-Log "INFO: Servicio reiniciado debido a fallo de API"
    } catch {
        Write-Log "ERROR: No se pudo reiniciar servicio: $_"
    }
}

# Verificar motor de sincronización
try {
    $SyncStatus = Invoke-RestMethod -Uri "$ApiUrl/api/v1/sync/monitor/status" -TimeoutSec 10 -ErrorAction Stop
    if ($SyncStatus.data.running -eq $true) {
        Write-Log "SUCCESS: Motor de sincronización activo"
    } else {
        Write-Log "WARNING: Motor de sincronización inactivo"
        # Trigger manual
        try {
            Invoke-RestMethod -Uri "$ApiUrl/api/v1/sync/monitor/trigger" -Method POST -TimeoutSec 10
            Write-Log "INFO: Trigger de sincronización enviado"
        } catch {
            Write-Log "ERROR: No se pudo enviar trigger: $_"
        }
    }
} catch {
    Write-Log "WARNING: No se pudo verificar estado del motor: $_"
}
'@

$MonitorScript | Out-File -FilePath "$AppPath\deployment\windows\monitor-service.ps1" -Encoding UTF8

# Script de estado
$StatusScript = @"
# Estado del Servicio RMS-Shopify Integration
Write-Host "=== Estado del Servicio RMS-Shopify Integration ===" -ForegroundColor Green

# Estado del servicio
`$Service = Get-Service -Name "$ServiceName" -ErrorAction SilentlyContinue
if (`$Service) {
    Write-Host "Servicio: `$(`$Service.Status)" -ForegroundColor Yellow
} else {
    Write-Host "Servicio: NO INSTALADO" -ForegroundColor Red
}

# Estado de la API
try {
    `$ApiStatus = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sync/monitor/status" -TimeoutSec 5
    Write-Host "`nEstado de la API:" -ForegroundColor Green
    `$ApiStatus | ConvertTo-Json -Depth 3 | Write-Host
} catch {
    Write-Host "`nAPI: NO DISPONIBLE" -ForegroundColor Red
}

# Logs recientes
Write-Host "`n=== Logs Recientes ===" -ForegroundColor Green
Get-Content "$LogPath\service.log" -Tail 10 -ErrorAction SilentlyContinue | Write-Host
"@

$StatusScript | Out-File -FilePath "$AppPath\rms-status.ps1" -Encoding UTF8

# 11. Configurar firewall
Write-Host "🔥 Configurando reglas de firewall..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "RMS-Shopify Integration" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue

Write-Host "`n🎉 Instalación completada exitosamente!" -ForegroundColor Green
Write-Host "========================================================================================" -ForegroundColor Cyan
Write-Host "                           RESUMEN DE INSTALACIÓN WINDOWS" -ForegroundColor Cyan
Write-Host "========================================================================================" -ForegroundColor Cyan
Write-Host "Servicio de Windows:     $ServiceName" -ForegroundColor White
Write-Host "Directorio de aplicación: $AppPath" -ForegroundColor White
Write-Host "Logs del sistema:        $LogPath" -ForegroundColor White
Write-Host "Logs del servicio:       Visor de Eventos > Aplicaciones y servicios > $ServiceName" -ForegroundColor White
Write-Host ""
Write-Host "COMANDOS ÚTILES:" -ForegroundColor Yellow
Write-Host "  Estado del servicio:   Get-Service $ServiceName" -ForegroundColor White
Write-Host "  Iniciar servicio:      Start-Service $ServiceName" -ForegroundColor White
Write-Host "  Detener servicio:      Stop-Service $ServiceName" -ForegroundColor White
Write-Host "  Reiniciar servicio:    Restart-Service $ServiceName" -ForegroundColor White
Write-Host "  Ver estado API:        PowerShell -File `"$AppPath\rms-status.ps1`"" -ForegroundColor White
Write-Host ""
Write-Host "TAREAS PROGRAMADAS CREADAS:" -ForegroundColor Yellow
Write-Host "  RMS-Shopify-Monitor:   Cada 5 minutos - verifica salud del servicio" -ForegroundColor White
Write-Host "  RMS-Shopify-NightSync: Diario 3:00 AM - sincronización completa" -ForegroundColor White
Write-Host ""
Write-Host "PRÓXIMOS PASOS:" -ForegroundColor Red
Write-Host "1. Editar $AppPath\.env con tu configuración" -ForegroundColor White
Write-Host "2. Iniciar el servicio: Start-Service $ServiceName" -ForegroundColor White
Write-Host "3. Verificar estado: PowerShell -File `"$AppPath\rms-status.ps1`"" -ForegroundColor White
Write-Host "========================================================================================" -ForegroundColor Cyan

Write-Host "`nPresiona cualquier tecla para continuar..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")