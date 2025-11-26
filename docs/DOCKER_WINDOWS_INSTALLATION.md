# 🐳 Guía de Instalación de Docker en Windows

> **Guía completa paso a paso para instalar Docker Desktop en Windows y configurar el sistema RMS-Shopify Integration con inicio automático al encender la computadora**

---

## 📋 Tabla de Contenidos

1. [¿Qué es Docker y por qué lo usamos?](#1--qué-es-docker-y-por-qué-lo-usamos)
2. [Requisitos del Sistema](#2--requisitos-del-sistema)
3. [Verificar Compatibilidad (Script Automático)](#3--verificar-compatibilidad-script-automático)
4. [Instalar WSL2 (Requerido)](#4--instalar-wsl2-requerido)
5. [Instalar Docker Desktop](#5--instalar-docker-desktop)
6. [Configurar Inicio Automático](#6--configurar-inicio-automático)
7. [Desplegar el Proyecto RMS-Shopify](#7--desplegar-el-proyecto-rms-shopify)
8. [Verificación Final](#8--verificación-final)
9. [Configuración del Firewall](#9--configuración-del-firewall)
10. [Solución de Problemas](#10--solución-de-problemas)
11. [Mantenimiento](#11--mantenimiento)
12. [Comandos de Referencia Rápida](#12--comandos-de-referencia-rápida)
13. [Checklist de Instalación](#13--checklist-de-instalación)

---

## 1. 🐳 ¿Qué es Docker y por qué lo usamos?

### Explicación Simple

Imagine que Docker es como una **"caja mágica"** que contiene todo lo necesario para que una aplicación funcione. En lugar de instalar muchos programas diferentes en su computadora (Python, Redis, drivers de base de datos, etc.), Docker empaqueta todo en una sola "caja" que funciona igual en cualquier computadora.

### Beneficios de usar Docker

| Sin Docker | Con Docker |
|------------|------------|
| ❌ Instalar Python manualmente | ✅ Ya viene incluido |
| ❌ Instalar Redis manualmente | ✅ Ya viene incluido |
| ❌ Configurar drivers SQL Server | ✅ Ya viene configurado |
| ❌ Conflictos con otras aplicaciones | ✅ Aislado del sistema |
| ❌ "En mi computadora funciona..." | ✅ Funciona igual en todas |
| ❌ Difícil de actualizar | ✅ Actualización con un comando |

### ¿Qué necesita saber?

**No necesita ser experto en Docker.** Esta guía le enseñará los comandos básicos necesarios para:
- Iniciar el sistema
- Detener el sistema
- Ver el estado
- Solucionar problemas comunes

---

## 2. ✅ Requisitos del Sistema

### Requisitos de Hardware

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| **Procesador** | 64-bit con virtualización | Intel Core i5 o AMD Ryzen 5 |
| **Memoria RAM** | 4 GB | 8 GB o más |
| **Espacio en Disco** | 20 GB libres | 50 GB libres |
| **Conexión a Internet** | Estable | Fibra óptica |

### Requisitos de Software

#### Para Windows 10/11 Pro, Enterprise o Education
- Windows 10 versión 2004 o superior (Build 19041+)
- Windows 11 cualquier versión
- Hyper-V habilitado (Docker lo habilita automáticamente)

#### Para Windows 10/11 Home
- Windows 10 versión 2004 o superior (Build 19041+)
- Windows 11 cualquier versión
- **WSL2 (Windows Subsystem for Linux 2)** - Lo instalaremos en esta guía

### ¿Cómo saber qué versión de Windows tengo?

1. Presione `Windows + R` (tecla Windows y la letra R al mismo tiempo)
2. Escriba `winver` y presione Enter
3. Aparecerá una ventana con la información de su Windows

**Ejemplo de lo que verá:**
```
Windows 10 Pro
Versión 22H2
Compilación del SO 19045.3803
```

### ¿Cómo saber si tengo Windows Home o Pro?

1. Presione `Windows + I` para abrir Configuración
2. Vaya a **Sistema** → **Acerca de**
3. Busque **"Edición"**

**Si dice "Windows 10 Home" o "Windows 11 Home"**: Necesita instalar WSL2 (lo explicamos en la sección 4)

**Si dice "Windows 10 Pro/Enterprise/Education"**: Puede usar Hyper-V (más fácil)

---

## 3. 🔍 Verificar Compatibilidad (Script Automático)

Antes de instalar Docker, ejecute este script para verificar que su computadora cumple todos los requisitos.

### Cómo ejecutar el script

1. **Abra PowerShell como Administrador:**
   - Haga clic en el botón de **Inicio** (ícono de Windows)
   - Escriba `PowerShell`
   - Haga clic derecho en **"Windows PowerShell"**
   - Seleccione **"Ejecutar como administrador"**
   - Haga clic en **"Sí"** cuando pregunte si desea permitir cambios

2. **Copie y pegue el siguiente script completo:**

```powershell
# ============================================================
# SCRIPT DE VERIFICACIÓN DE REQUISITOS PARA DOCKER
# RMS-Shopify Integration
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACIÓN DE REQUISITOS PARA DOCKER DESKTOP" -ForegroundColor Cyan
Write-Host "  RMS-Shopify Integration" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$todosLosRequisitos = $true

# 1. Verificar que estamos ejecutando como Administrador
Write-Host "1. Verificando permisos de Administrador..." -ForegroundColor Yellow
$esAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if ($esAdmin) {
    Write-Host "   ✅ Ejecutándose como Administrador" -ForegroundColor Green
} else {
    Write-Host "   ❌ NO está ejecutándose como Administrador" -ForegroundColor Red
    Write-Host "      Por favor, cierre esta ventana y abra PowerShell como Administrador" -ForegroundColor Red
    $todosLosRequisitos = $false
}

# 2. Verificar versión de Windows
Write-Host ""
Write-Host "2. Verificando versión de Windows..." -ForegroundColor Yellow
$osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
$buildNumber = [int]$osInfo.BuildNumber
$osCaption = $osInfo.Caption

Write-Host "   Sistema Operativo: $osCaption" -ForegroundColor White
Write-Host "   Número de Build: $buildNumber" -ForegroundColor White

if ($buildNumber -ge 19041) {
    Write-Host "   ✅ Versión de Windows compatible (Build $buildNumber >= 19041)" -ForegroundColor Green
} else {
    Write-Host "   ❌ Versión de Windows NO compatible" -ForegroundColor Red
    Write-Host "      Se requiere Windows 10 versión 2004 o superior (Build 19041+)" -ForegroundColor Red
    Write-Host "      Por favor, actualice Windows antes de continuar" -ForegroundColor Red
    $todosLosRequisitos = $false
}

# 3. Verificar edición de Windows (Home vs Pro)
Write-Host ""
Write-Host "3. Verificando edición de Windows..." -ForegroundColor Yellow
$esHome = $osCaption -like "*Home*"
if ($esHome) {
    Write-Host "   📋 Edición: Windows Home" -ForegroundColor Yellow
    Write-Host "   ℹ️  Necesitará instalar WSL2 (se explica en la guía)" -ForegroundColor Cyan
} else {
    Write-Host "   ✅ Edición: Windows Pro/Enterprise/Education" -ForegroundColor Green
    Write-Host "   ℹ️  Puede usar Hyper-V (configuración más simple)" -ForegroundColor Cyan
}

# 4. Verificar virtualización en BIOS
Write-Host ""
Write-Host "4. Verificando virtualización del procesador..." -ForegroundColor Yellow
try {
    $virtualizacion = Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty HypervisorPresent
    $vmInfo = Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty VirtualizationFirmwareEnabled -ErrorAction SilentlyContinue

    if ($virtualizacion -or $vmInfo) {
        Write-Host "   ✅ Virtualización habilitada" -ForegroundColor Green
    } else {
        # Verificar de otra manera
        $hyperV = (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction SilentlyContinue)
        if ($hyperV -and $hyperV.State -eq "Enabled") {
            Write-Host "   ✅ Hyper-V habilitado" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  No se pudo confirmar virtualización" -ForegroundColor Yellow
            Write-Host "      Docker Desktop verificará esto durante la instalación" -ForegroundColor Yellow
            Write-Host "      Si falla, deberá habilitar virtualización en BIOS" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "   ⚠️  No se pudo verificar virtualización" -ForegroundColor Yellow
    Write-Host "      Docker Desktop lo verificará durante la instalación" -ForegroundColor Yellow
}

# 5. Verificar memoria RAM
Write-Host ""
Write-Host "5. Verificando memoria RAM..." -ForegroundColor Yellow
$ramGB = [math]::Round((Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
Write-Host "   RAM Total: $ramGB GB" -ForegroundColor White

if ($ramGB -ge 8) {
    Write-Host "   ✅ RAM suficiente ($ramGB GB >= 8 GB recomendados)" -ForegroundColor Green
} elseif ($ramGB -ge 4) {
    Write-Host "   ⚠️  RAM mínima ($ramGB GB >= 4 GB mínimos)" -ForegroundColor Yellow
    Write-Host "      El sistema funcionará pero puede ser lento" -ForegroundColor Yellow
} else {
    Write-Host "   ❌ RAM insuficiente ($ramGB GB < 4 GB mínimos)" -ForegroundColor Red
    Write-Host "      Se requieren al menos 4 GB de RAM" -ForegroundColor Red
    $todosLosRequisitos = $false
}

# 6. Verificar espacio en disco
Write-Host ""
Write-Host "6. Verificando espacio en disco..." -ForegroundColor Yellow
$disco = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'"
$espacioLibreGB = [math]::Round($disco.FreeSpace / 1GB, 2)
$espacioTotalGB = [math]::Round($disco.Size / 1GB, 2)
Write-Host "   Disco C: $espacioLibreGB GB libres de $espacioTotalGB GB totales" -ForegroundColor White

if ($espacioLibreGB -ge 50) {
    Write-Host "   ✅ Espacio suficiente ($espacioLibreGB GB >= 50 GB recomendados)" -ForegroundColor Green
} elseif ($espacioLibreGB -ge 20) {
    Write-Host "   ⚠️  Espacio mínimo ($espacioLibreGB GB >= 20 GB mínimos)" -ForegroundColor Yellow
    Write-Host "      Considere liberar espacio para mejor rendimiento" -ForegroundColor Yellow
} else {
    Write-Host "   ❌ Espacio insuficiente ($espacioLibreGB GB < 20 GB mínimos)" -ForegroundColor Red
    Write-Host "      Libere espacio en disco antes de continuar" -ForegroundColor Red
    $todosLosRequisitos = $false
}

# 7. Verificar WSL2
Write-Host ""
Write-Host "7. Verificando WSL2..." -ForegroundColor Yellow
try {
    $wslStatus = wsl --status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ WSL2 instalado" -ForegroundColor Green
        $wslVersion = wsl --version 2>&1 | Select-Object -First 1
        Write-Host "   Versión: $wslVersion" -ForegroundColor White
    } else {
        if ($esHome) {
            Write-Host "   ⚠️  WSL2 no instalado (REQUERIDO para Windows Home)" -ForegroundColor Yellow
            Write-Host "      Siga las instrucciones de la guía para instalar WSL2" -ForegroundColor Yellow
        } else {
            Write-Host "   ℹ️  WSL2 no instalado (opcional para Windows Pro)" -ForegroundColor Cyan
            Write-Host "      Docker puede usar Hyper-V en su lugar" -ForegroundColor Cyan
        }
    }
} catch {
    if ($esHome) {
        Write-Host "   ⚠️  WSL2 no instalado (REQUERIDO para Windows Home)" -ForegroundColor Yellow
    } else {
        Write-Host "   ℹ️  WSL2 no instalado (opcional para Windows Pro)" -ForegroundColor Cyan
    }
}

# 8. Verificar si Docker ya está instalado
Write-Host ""
Write-Host "8. Verificando Docker existente..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker ya está instalado" -ForegroundColor Green
        Write-Host "   Versión: $dockerVersion" -ForegroundColor White

        # Verificar si Docker está corriendo
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Docker está ejecutándose" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Docker está instalado pero NO está ejecutándose" -ForegroundColor Yellow
            Write-Host "      Inicie Docker Desktop desde el menú de inicio" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ℹ️  Docker no está instalado" -ForegroundColor Cyan
        Write-Host "      Siga las instrucciones de la guía para instalarlo" -ForegroundColor Cyan
    }
} catch {
    Write-Host "   ℹ️  Docker no está instalado" -ForegroundColor Cyan
}

# 9. Verificar conectividad a Internet
Write-Host ""
Write-Host "9. Verificando conectividad a Internet..." -ForegroundColor Yellow
try {
    $conexion = Test-Connection -ComputerName "google.com" -Count 1 -Quiet
    if ($conexion) {
        Write-Host "   ✅ Conexión a Internet activa" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Sin conexión a Internet" -ForegroundColor Red
        Write-Host "      Se requiere Internet para descargar Docker" -ForegroundColor Red
        $todosLosRequisitos = $false
    }
} catch {
    Write-Host "   ⚠️  No se pudo verificar conexión a Internet" -ForegroundColor Yellow
}

# Resumen final
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN DE VERIFICACIÓN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($todosLosRequisitos) {
    Write-Host "  ✅ SU SISTEMA CUMPLE TODOS LOS REQUISITOS" -ForegroundColor Green
    Write-Host ""
    if ($esHome) {
        Write-Host "  📋 SIGUIENTE PASO: Instalar WSL2 (Sección 4 de la guía)" -ForegroundColor Yellow
    } else {
        Write-Host "  📋 SIGUIENTE PASO: Instalar Docker Desktop (Sección 5 de la guía)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ HAY REQUISITOS QUE NO SE CUMPLEN" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Por favor, revise los errores marcados con ❌ arriba" -ForegroundColor Red
    Write-Host "  y corríjalos antes de continuar con la instalación." -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
```

3. **Presione Enter** para ejecutar el script

### Interpretación de Resultados

| Símbolo | Significado |
|---------|-------------|
| ✅ | Requisito cumplido - Todo bien |
| ⚠️ | Advertencia - Funciona pero puede mejorar |
| ❌ | Error - Debe corregirse antes de continuar |
| ℹ️ | Información - Solo para su conocimiento |

---

## 4. 🪟 Instalar WSL2 (Requerido)

> **Nota:** WSL2 es **OBLIGATORIO** para Windows Home y **RECOMENDADO** para Windows Pro/Enterprise.

### ¿Qué es WSL2?

WSL2 (Windows Subsystem for Linux 2) permite ejecutar Linux dentro de Windows. Docker lo usa para funcionar de manera más eficiente.

### Instalación Automática (Recomendada)

**Abra PowerShell como Administrador** y ejecute este comando:

```powershell
wsl --install
```

Este comando hace todo automáticamente:
- Habilita las características necesarias de Windows
- Instala el kernel de Linux
- Instala Ubuntu como distribución predeterminada

**Después de ejecutar el comando:**
1. **Reinicie su computadora** cuando se lo solicite
2. Al reiniciar, se abrirá una ventana de Ubuntu
3. Cree un nombre de usuario y contraseña (puede ser cualquiera)
4. ¡Listo! WSL2 está instalado

### Instalación Manual (Si el método automático falla)

Si el comando `wsl --install` no funciona, siga estos pasos:

#### Paso 1: Habilitar características de Windows

Abra PowerShell como Administrador y ejecute:

```powershell
# Habilitar WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Habilitar máquina virtual
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

**Reinicie su computadora.**

#### Paso 2: Descargar actualización del kernel de Linux

1. Descargue el paquete de actualización:
   - Vaya a: https://aka.ms/wsl2kernel
   - Haga clic en el enlace de descarga

2. Ejecute el archivo descargado (`wsl_update_x64.msi`)
3. Siga las instrucciones del instalador

#### Paso 3: Establecer WSL2 como predeterminado

Abra PowerShell (normal, no como administrador) y ejecute:

```powershell
wsl --set-default-version 2
```

#### Paso 4: Verificar instalación

```powershell
wsl --status
```

Debe ver algo como:
```
Versión predeterminada: 2
```

### Script Automático de Instalación WSL2

Si prefiere un script que haga todo automáticamente:

```powershell
# ============================================================
# SCRIPT DE INSTALACIÓN AUTOMÁTICA DE WSL2
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALACIÓN AUTOMÁTICA DE WSL2" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar administrador
$esAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $esAdmin) {
    Write-Host "❌ Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host "   Cierre esta ventana y abra PowerShell como Administrador" -ForegroundColor Red
    exit 1
}

Write-Host "1. Habilitando característica WSL..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

Write-Host ""
Write-Host "2. Habilitando característica de Máquina Virtual..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

Write-Host ""
Write-Host "3. Estableciendo WSL2 como versión predeterminada..." -ForegroundColor Yellow
wsl --set-default-version 2 2>$null

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ INSTALACIÓN DE WSL2 COMPLETADA" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANTE: Debe REINICIAR su computadora ahora" -ForegroundColor Yellow
Write-Host ""
Write-Host "Después de reiniciar:" -ForegroundColor White
Write-Host "1. Si aparece una ventana de Ubuntu, cree usuario y contraseña" -ForegroundColor White
Write-Host "2. Si no aparece, está listo para instalar Docker Desktop" -ForegroundColor White
Write-Host ""

$reiniciar = Read-Host "¿Desea reiniciar ahora? (S/N)"
if ($reiniciar -eq "S" -or $reiniciar -eq "s") {
    Write-Host "Reiniciando en 10 segundos..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    Restart-Computer
}
```

---

## 5. 🐳 Instalar Docker Desktop

### Paso 1: Descargar Docker Desktop

1. Abra su navegador web (Chrome, Edge, Firefox)
2. Vaya a: **https://www.docker.com/products/docker-desktop/**
3. Haga clic en el botón azul **"Download for Windows"**
4. Espere a que se descargue el archivo (aproximadamente 500 MB)

El archivo descargado se llamará algo como: `Docker Desktop Installer.exe`

### Paso 2: Ejecutar el instalador

1. **Localice el archivo descargado** (generalmente en la carpeta "Descargas")
2. **Haga doble clic** en `Docker Desktop Installer.exe`
3. Si aparece "¿Desea permitir que esta aplicación haga cambios?", haga clic en **"Sí"**

### Paso 3: Opciones de instalación

En la pantalla de configuración, verá dos opciones con casillas de verificación:

#### Si tiene Windows Home:
- ✅ Marque: **"Use WSL 2 instead of Hyper-V"** (OBLIGATORIO)
- ✅ Marque: **"Add shortcut to desktop"** (recomendado)

#### Si tiene Windows Pro/Enterprise:
- ☐ Puede dejar desmarcado "Use WSL 2..." (usará Hyper-V)
- ✅ Marque: **"Add shortcut to desktop"** (recomendado)

> **Recomendación:** Incluso en Windows Pro, se recomienda usar WSL2 por mejor rendimiento.

4. Haga clic en **"Ok"** para comenzar la instalación

### Paso 4: Esperar la instalación

- La instalación toma entre **5-15 minutos**
- Verá una barra de progreso
- **NO cierre la ventana** mientras se instala

### Paso 5: Reiniciar (si se solicita)

Al terminar, Docker puede solicitar reiniciar Windows:
- Haga clic en **"Close and restart"**
- Su computadora se reiniciará automáticamente

### Paso 6: Primer inicio de Docker

Después de reiniciar:

1. **Docker Desktop se iniciará automáticamente**
   - Verá un ícono de ballena (🐳) en la bandeja del sistema (esquina inferior derecha)
   - El ícono puede estar animado mientras Docker se inicia

2. **Aceptar términos de servicio**
   - La primera vez, aparecerá una ventana con los términos
   - Haga clic en **"Accept"** para continuar

3. **Cuenta de Docker Hub (OPCIONAL)**
   - Docker le pedirá crear una cuenta
   - Puede hacer clic en **"Skip"** o **"Continue without signing in"**
   - NO es necesario crear cuenta para usar Docker

4. **Tutorial inicial (OPCIONAL)**
   - Puede hacer clic en **"Skip tutorial"** si desea
   - O seguir el tutorial rápido de 2 minutos

### Paso 7: Verificar instalación

1. **Abra PowerShell** (no necesita ser como Administrador)
2. Ejecute:

```powershell
docker --version
```

Debe ver algo como:
```
Docker version 24.0.7, build afdd53b
```

3. Pruebe que Docker funciona:

```powershell
docker run hello-world
```

Debe ver un mensaje largo que incluye:
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

### Script de Verificación Post-Instalación

```powershell
# ============================================================
# VERIFICACIÓN DE INSTALACIÓN DE DOCKER
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACIÓN DE DOCKER DESKTOP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar comando docker
Write-Host "1. Verificando comando docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "   ✅ Docker instalado: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Docker no está instalado o no está en el PATH" -ForegroundColor Red
    exit 1
}

# Verificar Docker daemon
Write-Host ""
Write-Host "2. Verificando Docker daemon..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker daemon está ejecutándose" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Docker daemon NO está ejecutándose" -ForegroundColor Red
        Write-Host "      Inicie Docker Desktop desde el menú de inicio" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ❌ Error al verificar Docker daemon" -ForegroundColor Red
    exit 1
}

# Verificar docker-compose
Write-Host ""
Write-Host "3. Verificando docker-compose..." -ForegroundColor Yellow
try {
    $composeVersion = docker compose version
    Write-Host "   ✅ Docker Compose disponible: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️  Docker Compose no disponible como plugin" -ForegroundColor Yellow
    # Intentar comando antiguo
    try {
        $composeVersionOld = docker-compose --version
        Write-Host "   ✅ Docker Compose (legacy): $composeVersionOld" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ Docker Compose no está instalado" -ForegroundColor Red
    }
}

# Prueba de ejecución
Write-Host ""
Write-Host "4. Ejecutando prueba hello-world..." -ForegroundColor Yellow
$testResult = docker run --rm hello-world 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Prueba hello-world exitosa" -ForegroundColor Green
} else {
    Write-Host "   ❌ Prueba hello-world falló" -ForegroundColor Red
    Write-Host "   Error: $testResult" -ForegroundColor Red
}

# Información del sistema Docker
Write-Host ""
Write-Host "5. Información del sistema Docker..." -ForegroundColor Yellow
$dockerSystem = docker system info --format "{{.OSType}} - {{.Architecture}} - {{.ServerVersion}}" 2>$null
Write-Host "   $dockerSystem" -ForegroundColor White

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ DOCKER ESTÁ LISTO PARA USAR" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
```

---

## 6. 🔄 Configurar Inicio Automático

Para que el sistema RMS-Shopify funcione siempre que encienda la computadora, necesitamos configurar:

1. **Docker Desktop** inicie automáticamente con Windows
2. **Los contenedores** se reinicien automáticamente

### Parte 1: Configurar Docker Desktop para inicio automático

#### Método A: Desde la interfaz de Docker Desktop

1. **Abra Docker Desktop** (haga clic en el ícono de la ballena 🐳)
2. Haga clic en el **ícono de engranaje ⚙️** (Configuración) en la esquina superior derecha
3. En el menú izquierdo, seleccione **"General"**
4. Asegúrese de que esté marcada: ✅ **"Start Docker Desktop when you sign in to your computer"**
5. Haga clic en **"Apply & restart"**

#### Método B: Desde el Registro de Windows (Script Automático)

```powershell
# ============================================================
# CONFIGURAR INICIO AUTOMÁTICO DE DOCKER DESKTOP
# ============================================================

Write-Host ""
Write-Host "Configurando inicio automático de Docker Desktop..." -ForegroundColor Yellow

# Ruta del ejecutable de Docker Desktop
$dockerPath = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"

if (Test-Path $dockerPath) {
    # Crear entrada en el registro para inicio automático
    $registryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

    Set-ItemProperty -Path $registryPath -Name "Docker Desktop" -Value "`"$dockerPath`""

    Write-Host "✅ Docker Desktop configurado para iniciar automáticamente" -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró Docker Desktop en la ruta esperada" -ForegroundColor Red
    Write-Host "   Ruta buscada: $dockerPath" -ForegroundColor Red
}
```

### Parte 2: Configurar contenedores para reinicio automático

Los contenedores deben tener la política de reinicio configurada. Esto ya está en el archivo `docker-compose.yml` del proyecto:

```yaml
services:
  api:
    restart: unless-stopped  # Se reinicia automáticamente
    # ...

  dashboard:
    restart: unless-stopped  # Se reinicia automáticamente
    # ...

  redis:
    restart: unless-stopped  # Se reinicia automáticamente
    # ...
```

**¿Qué significa `restart: unless-stopped`?**
- ✅ Se reinicia si falla
- ✅ Se reinicia cuando Docker se inicia
- ❌ NO se reinicia si usted lo detuvo manualmente

### Parte 3: Crear tarea programada de verificación (Opcional pero recomendado)

Esta tarea verifica cada 5 minutos que Docker y los contenedores estén funcionando:

```powershell
# ============================================================
# CREAR TAREA PROGRAMADA DE VERIFICACIÓN DE DOCKER
# ============================================================

# Este script debe ejecutarse como Administrador

$scriptVerificacion = @'
# Script de verificación de Docker y contenedores
$logPath = "C:\RMS-Shopify-Integration\logs\docker-monitor.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Crear directorio de logs si no existe
if (-not (Test-Path "C:\RMS-Shopify-Integration\logs")) {
    New-Item -ItemType Directory -Path "C:\RMS-Shopify-Integration\logs" -Force | Out-Null
}

# Verificar si Docker está corriendo
$dockerRunning = $false
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
    }
} catch {
    $dockerRunning = $false
}

if (-not $dockerRunning) {
    # Docker no está corriendo, intentar iniciarlo
    Add-Content -Path $logPath -Value "$timestamp - Docker no está corriendo. Intentando iniciar..."

    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 60  # Esperar 60 segundos para que Docker inicie

    # Verificar de nuevo
    try {
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Add-Content -Path $logPath -Value "$timestamp - Docker iniciado exitosamente"
        } else {
            Add-Content -Path $logPath -Value "$timestamp - ERROR: No se pudo iniciar Docker"
        }
    } catch {
        Add-Content -Path $logPath -Value "$timestamp - ERROR: $($_.Exception.Message)"
    }
} else {
    # Docker está corriendo, verificar contenedores
    $contenedores = docker ps --format "{{.Names}}" 2>&1

    $apiRunning = $contenedores -like "*rms-shopify-api*"
    $dashboardRunning = $contenedores -like "*rms-shopify-dashboard*"
    $redisRunning = $contenedores -like "*rms-shopify-redis*"

    if (-not $apiRunning -or -not $dashboardRunning -or -not $redisRunning) {
        Add-Content -Path $logPath -Value "$timestamp - Contenedores no corriendo. Reiniciando..."

        Set-Location "C:\RMS-Shopify-Integration"
        docker compose up -d

        Add-Content -Path $logPath -Value "$timestamp - Contenedores reiniciados"
    } else {
        # Todo OK - registrar solo cada hora para no llenar el log
        $hora = (Get-Date).Hour
        $minuto = (Get-Date).Minute
        if ($minuto -lt 5) {
            Add-Content -Path $logPath -Value "$timestamp - OK: Docker y contenedores funcionando"
        }
    }
}
'@

# Guardar script de verificación
$scriptPath = "C:\RMS-Shopify-Integration\scripts"
if (-not (Test-Path $scriptPath)) {
    New-Item -ItemType Directory -Path $scriptPath -Force | Out-Null
}

$scriptVerificacion | Out-File -FilePath "$scriptPath\verificar-docker.ps1" -Encoding UTF8

Write-Host "Script de verificación creado en: $scriptPath\verificar-docker.ps1" -ForegroundColor Green

# Crear tarea programada
$taskName = "RMS-Shopify Docker Monitor"
$taskExists = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($taskExists) {
    Write-Host "La tarea '$taskName' ya existe. Eliminando..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath\verificar-docker.ps1`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Verifica que Docker y los contenedores RMS-Shopify estén funcionando"

Write-Host ""
Write-Host "✅ Tarea programada '$taskName' creada exitosamente" -ForegroundColor Green
Write-Host "   - Se ejecuta cada 5 minutos" -ForegroundColor White
Write-Host "   - Inicia Docker si no está corriendo" -ForegroundColor White
Write-Host "   - Reinicia contenedores si están detenidos" -ForegroundColor White
```

---

## 7. 📦 Desplegar el Proyecto RMS-Shopify

### Paso 1: Crear directorio del proyecto

Abra PowerShell y ejecute:

```powershell
# Crear directorio principal
New-Item -ItemType Directory -Path "C:\RMS-Shopify-Integration" -Force

# Crear subdirectorios
New-Item -ItemType Directory -Path "C:\RMS-Shopify-Integration\logs" -Force
New-Item -ItemType Directory -Path "C:\RMS-Shopify-Integration\scripts" -Force

Write-Host "✅ Directorios creados" -ForegroundColor Green
```

### Paso 2: Copiar archivos del proyecto

**Opción A: Si tiene los archivos en USB o carpeta**

1. Copie toda la carpeta del proyecto a `C:\RMS-Shopify-Integration`
2. Asegúrese de que el archivo `docker-compose.yml` esté en la raíz

**Opción B: Si tiene acceso al repositorio Git**

```powershell
cd C:\RMS-Shopify-Integration
git clone [URL-del-repositorio] .
```

### Paso 3: Configurar archivo .env

1. En la carpeta `C:\RMS-Shopify-Integration`, busque el archivo `.env.example`
2. Cópielo y renómbrelo a `.env`
3. Edítelo con sus credenciales

**Para editar el archivo:**
```powershell
notepad "C:\RMS-Shopify-Integration\.env"
```

**Contenido que debe configurar:**

```bash
# ===================================
# CONEXIÓN A RMS (SQL SERVER)
# ===================================
RMS_DB_HOST=192.168.1.100          # Cambie por la IP de su servidor RMS
RMS_DB_PORT=1433                    # Puerto de SQL Server (normalmente 1433)
RMS_DB_NAME=bb57                    # Nombre de su base de datos RMS
RMS_DB_USER=su_usuario              # Usuario de SQL Server
RMS_DB_PASSWORD=su_contraseña       # Contraseña de SQL Server

# ===================================
# CONEXIÓN A SHOPIFY
# ===================================
SHOPIFY_SHOP_URL=su-tienda.myshopify.com  # URL de su tienda (sin https://)
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx          # Token de API de Shopify
SHOPIFY_API_VERSION=2025-04               # No cambiar
SHOPIFY_WEBHOOK_SECRET=whsec_xxxxx        # Secret de webhooks (opcional)

# ===================================
# CONFIGURACIÓN DE SINCRONIZACIÓN
# ===================================
ENABLE_SCHEDULED_SYNC=True          # Habilitar sincronización automática
SYNC_INTERVAL_MINUTES=5             # Cada cuántos minutos sincronizar
SYNC_BATCH_SIZE=100                 # Productos por lote
```

### Paso 4: Construir la imagen Docker

```powershell
cd C:\RMS-Shopify-Integration

# Construir la imagen (puede tomar 5-10 minutos la primera vez)
docker build -t rms-shopify-integration:latest .
```

**Mientras se construye, verá:**
```
Step 1/15 : FROM python:3.12-slim
 ---> Downloading...
Step 2/15 : WORKDIR /app
...
Successfully built abc123def
Successfully tagged rms-shopify-integration:latest
```

### Paso 5: Iniciar los servicios

```powershell
cd C:\RMS-Shopify-Integration

# Iniciar todos los servicios
docker compose up -d
```

**Verá:**
```
[+] Running 3/3
 ✔ Container rms-shopify-redis      Started
 ✔ Container rms-shopify-api        Started
 ✔ Container rms-shopify-dashboard  Started
```

### Paso 6: Verificar que todo funcione

```powershell
# Ver estado de los contenedores
docker compose ps
```

**Debe ver:**
```
NAME                    STATUS              PORTS
rms-shopify-api         Up 30 seconds       0.0.0.0:8000->8000/tcp
rms-shopify-dashboard   Up 30 seconds       0.0.0.0:8501->8501/tcp
rms-shopify-redis       Up 30 seconds       0.0.0.0:6379->6379/tcp
```

### Script Completo de Despliegue

Este script hace todos los pasos automáticamente:

```powershell
# ============================================================
# SCRIPT DE DESPLIEGUE COMPLETO RMS-SHOPIFY
# ============================================================

param(
    [string]$ProjectPath = "C:\RMS-Shopify-Integration"
)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DESPLIEGUE DE RMS-SHOPIFY INTEGRATION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Docker
Write-Host "1. Verificando Docker..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ❌ Docker no está ejecutándose" -ForegroundColor Red
        Write-Host "   Por favor, inicie Docker Desktop y vuelva a ejecutar este script" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Docker está funcionando" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Docker no está instalado" -ForegroundColor Red
    exit 1
}

# Verificar que existe el directorio del proyecto
Write-Host ""
Write-Host "2. Verificando directorio del proyecto..." -ForegroundColor Yellow
if (-not (Test-Path $ProjectPath)) {
    Write-Host "   ❌ No se encontró el directorio: $ProjectPath" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Directorio encontrado: $ProjectPath" -ForegroundColor Green

# Verificar archivos necesarios
Write-Host ""
Write-Host "3. Verificando archivos necesarios..." -ForegroundColor Yellow

$archivosRequeridos = @(
    "docker-compose.yml",
    "Dockerfile",
    ".env"
)

$archivosFaltantes = @()
foreach ($archivo in $archivosRequeridos) {
    $rutaArchivo = Join-Path $ProjectPath $archivo
    if (Test-Path $rutaArchivo) {
        Write-Host "   ✅ $archivo" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $archivo (FALTANTE)" -ForegroundColor Red
        $archivosFaltantes += $archivo
    }
}

if ($archivosFaltantes.Count -gt 0) {
    Write-Host ""
    Write-Host "   Por favor, asegúrese de tener todos los archivos necesarios" -ForegroundColor Red

    if ($archivosFaltantes -contains ".env") {
        Write-Host ""
        Write-Host "   Para crear el archivo .env:" -ForegroundColor Yellow
        Write-Host "   1. Copie .env.example a .env" -ForegroundColor White
        Write-Host "   2. Edite .env con sus credenciales" -ForegroundColor White
    }
    exit 1
}

# Ir al directorio del proyecto
Set-Location $ProjectPath

# Construir imagen
Write-Host ""
Write-Host "4. Construyendo imagen Docker..." -ForegroundColor Yellow
Write-Host "   (Esto puede tomar varios minutos la primera vez)" -ForegroundColor White
Write-Host ""

docker build -t rms-shopify-integration:latest .

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "   ❌ Error al construir la imagen Docker" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "   ✅ Imagen construida exitosamente" -ForegroundColor Green

# Iniciar servicios
Write-Host ""
Write-Host "5. Iniciando servicios..." -ForegroundColor Yellow

docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Error al iniciar servicios" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ Servicios iniciados" -ForegroundColor Green

# Esperar a que los servicios estén listos
Write-Host ""
Write-Host "6. Esperando que los servicios estén listos..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Verificar salud
Write-Host ""
Write-Host "7. Verificando salud del sistema..." -ForegroundColor Yellow

# Verificar API
try {
    $healthAPI = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    Write-Host "   ✅ API funcionando" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️  API aún iniciando (puede tomar más tiempo)" -ForegroundColor Yellow
}

# Verificar Dashboard
try {
    $healthDashboard = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -TimeoutSec 10
    Write-Host "   ✅ Dashboard funcionando" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️  Dashboard aún iniciando (puede tomar más tiempo)" -ForegroundColor Yellow
}

# Resumen
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ DESPLIEGUE COMPLETADO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Accesos disponibles:" -ForegroundColor White
Write-Host ""
Write-Host "  🎨 Dashboard:    http://localhost:8501" -ForegroundColor Cyan
Write-Host "  📡 API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  ❤️  Health:       http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Comandos útiles:" -ForegroundColor White
Write-Host "  - Ver logs:      docker compose logs -f" -ForegroundColor Gray
Write-Host "  - Detener:       docker compose down" -ForegroundColor Gray
Write-Host "  - Reiniciar:     docker compose restart" -ForegroundColor Gray
Write-Host ""
```

---

## 8. ✅ Verificación Final

### Acceder al Dashboard

1. Abra su navegador (Chrome, Edge, Firefox)
2. Vaya a: **http://localhost:8501**
3. Debe ver el panel de control con:
   - Estado de salud del sistema
   - Métricas de sincronización
   - Botones de acciones

### Acceder a la Documentación de API

1. En su navegador, vaya a: **http://localhost:8000/docs**
2. Verá la interfaz Swagger con todos los endpoints

### Verificar Salud del Sistema

1. Visite: **http://localhost:8000/health**
2. Debe ver una respuesta JSON como:

```json
{
  "status": "healthy",
  "services": {
    "rms_database": "connected",
    "shopify_api": "connected",
    "redis": "connected"
  }
}
```

### Script de Verificación Completa

```powershell
# ============================================================
# VERIFICACIÓN COMPLETA DEL SISTEMA
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACIÓN COMPLETA RMS-SHOPIFY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$errores = 0

# 1. Docker
Write-Host "1. Docker Desktop" -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "   ✅ Versión: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Docker no disponible" -ForegroundColor Red
    $errores++
}

# 2. Contenedores
Write-Host ""
Write-Host "2. Contenedores" -ForegroundColor Yellow
$contenedores = docker compose ps --format json 2>$null | ConvertFrom-Json

$servicios = @("rms-shopify-api", "rms-shopify-dashboard", "rms-shopify-redis")
foreach ($servicio in $servicios) {
    $container = $contenedores | Where-Object { $_.Name -like "*$servicio*" }
    if ($container -and $container.State -eq "running") {
        Write-Host "   ✅ $servicio - Running" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $servicio - NOT Running" -ForegroundColor Red
        $errores++
    }
}

# 3. API
Write-Host ""
Write-Host "3. API Health" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    Write-Host "   ✅ API Status: $($health.status)" -ForegroundColor Green

    if ($health.services) {
        foreach ($servicio in $health.services.PSObject.Properties) {
            $status = $servicio.Value
            if ($status -eq "connected" -or $status -eq "healthy") {
                Write-Host "   ✅ $($servicio.Name): $status" -ForegroundColor Green
            } else {
                Write-Host "   ⚠️  $($servicio.Name): $status" -ForegroundColor Yellow
            }
        }
    }
} catch {
    Write-Host "   ❌ API no responde" -ForegroundColor Red
    $errores++
}

# 4. Dashboard
Write-Host ""
Write-Host "4. Dashboard" -ForegroundColor Yellow
try {
    $dashboard = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -TimeoutSec 10
    if ($dashboard.StatusCode -eq 200) {
        Write-Host "   ✅ Dashboard funcionando" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ Dashboard no responde" -ForegroundColor Red
    $errores++
}

# 5. Motor de sincronización
Write-Host ""
Write-Host "5. Motor de Sincronización" -ForegroundColor Yellow
try {
    $syncStatus = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/sync/monitor/status" -TimeoutSec 10
    if ($syncStatus.monitoring_active) {
        Write-Host "   ✅ Motor activo" -ForegroundColor Green
        Write-Host "   📊 Intervalo: $($syncStatus.check_interval_minutes) minutos" -ForegroundColor White
    } else {
        Write-Host "   ⚠️  Motor inactivo" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️  No se pudo verificar estado del motor" -ForegroundColor Yellow
}

# Resumen
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($errores -eq 0) {
    Write-Host "  ✅ SISTEMA FUNCIONANDO CORRECTAMENTE" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Accesos:" -ForegroundColor White
    Write-Host "  - Dashboard: http://localhost:8501" -ForegroundColor Cyan
    Write-Host "  - API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
} else {
    Write-Host "  ⚠️  SE ENCONTRARON $errores PROBLEMAS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Revise los errores arriba y consulte la sección de" -ForegroundColor White
    Write-Host "  Solución de Problemas en esta guía." -ForegroundColor White
}

Write-Host ""
```

---

## 9. 🔒 Configuración del Firewall

Para acceder al sistema desde otras computadoras en la red, configure el firewall de Windows.

### Puertos Requeridos

| Puerto | Servicio | Descripción |
|--------|----------|-------------|
| 8000 | API | Endpoints REST |
| 8501 | Dashboard | Panel web Streamlit |
| 6379 | Redis | Cache (solo interno) |

### Script de Configuración de Firewall

```powershell
# ============================================================
# CONFIGURACIÓN DE FIREWALL PARA RMS-SHOPIFY
# Ejecutar como Administrador
# ============================================================

Write-Host ""
Write-Host "Configurando reglas de firewall..." -ForegroundColor Yellow
Write-Host ""

# Verificar si es administrador
$esAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $esAdmin) {
    Write-Host "❌ Este script debe ejecutarse como Administrador" -ForegroundColor Red
    exit 1
}

# Regla para API (puerto 8000)
Write-Host "Creando regla para API (puerto 8000)..." -ForegroundColor White
New-NetFirewallRule -DisplayName "RMS-Shopify API" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8000 `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Permite acceso a la API de RMS-Shopify Integration" `
    -ErrorAction SilentlyContinue

if ($?) {
    Write-Host "   ✅ Regla API creada" -ForegroundColor Green
} else {
    # La regla puede ya existir
    Write-Host "   ℹ️  La regla API ya existe o no se pudo crear" -ForegroundColor Cyan
}

# Regla para Dashboard (puerto 8501)
Write-Host "Creando regla para Dashboard (puerto 8501)..." -ForegroundColor White
New-NetFirewallRule -DisplayName "RMS-Shopify Dashboard" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8501 `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Permite acceso al Dashboard de RMS-Shopify Integration" `
    -ErrorAction SilentlyContinue

if ($?) {
    Write-Host "   ✅ Regla Dashboard creada" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  La regla Dashboard ya existe o no se pudo crear" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "✅ Configuración de firewall completada" -ForegroundColor Green
Write-Host ""
Write-Host "Ahora puede acceder desde otras computadoras usando:" -ForegroundColor White
Write-Host "   - Dashboard: http://[IP-DE-ESTE-SERVIDOR]:8501" -ForegroundColor Cyan
Write-Host "   - API:       http://[IP-DE-ESTE-SERVIDOR]:8000" -ForegroundColor Cyan
Write-Host ""

# Mostrar IP del servidor
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -eq "Dhcp" }).IPAddress
if ($ip) {
    Write-Host "La IP de este servidor es: $ip" -ForegroundColor Yellow
}
```

---

## 10. 🔧 Solución de Problemas

### Problema 1: Docker Desktop no inicia

**Síntomas:**
- El ícono de Docker no aparece
- Docker muestra "Docker Desktop is starting..." indefinidamente

**Soluciones:**

1. **Reiniciar Docker Desktop:**
   - Clic derecho en el ícono de Docker (si está visible)
   - Seleccione "Restart"

2. **Reiniciar el servicio Docker:**
   ```powershell
   # Abrir PowerShell como Administrador
   Restart-Service docker
   ```

3. **Verificar WSL2:**
   ```powershell
   wsl --status
   wsl --update
   ```

4. **Reinstalar Docker Desktop:**
   - Desinstale desde Panel de Control
   - Reinicie la computadora
   - Vuelva a instalar

### Problema 2: Error "Cannot connect to Docker daemon"

**Síntomas:**
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Soluciones:**

1. **Iniciar Docker Desktop:**
   - Abra Docker Desktop desde el menú Inicio
   - Espere a que el ícono deje de estar animado

2. **Verificar que Docker Desktop esté corriendo:**
   ```powershell
   Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
   ```

### Problema 3: Contenedores no se inician

**Síntomas:**
- `docker compose up` muestra errores
- Contenedores aparecen como "Exited"

**Diagnóstico:**
```powershell
# Ver logs de los contenedores
docker compose logs

# Ver logs de un contenedor específico
docker compose logs api
```

**Soluciones comunes:**

1. **Error de puerto en uso:**
   ```powershell
   # Ver qué usa el puerto 8000
   netstat -ano | findstr :8000

   # Cambiar el puerto en docker-compose.yml
   # ports:
   #   - "8001:8000"  # Usar 8001 en lugar de 8000
   ```

2. **Error de archivo .env:**
   - Verifique que `.env` exista
   - Verifique que las credenciales sean correctas
   - No use comillas en los valores

3. **Error de conexión a base de datos:**
   - Verifique la IP del servidor RMS
   - Verifique usuario y contraseña
   - Verifique que el puerto 1433 esté accesible

### Problema 4: El sistema estaba funcionando pero dejó de funcionar

**Diagnóstico:**
```powershell
# Ver estado de contenedores
docker compose ps

# Ver logs recientes
docker compose logs --tail=50

# Verificar uso de recursos
docker stats --no-stream
```

**Solución: Reiniciar todo:**
```powershell
cd C:\RMS-Shopify-Integration
docker compose down
docker compose up -d
```

### Problema 5: Lento o sin respuesta

**Posibles causas:**

1. **Poca memoria RAM:**
   - Docker usa mucha RAM por defecto
   - Configure límites en Docker Desktop → Settings → Resources

2. **Disco lleno:**
   ```powershell
   # Limpiar Docker
   docker system prune -a
   ```

3. **Muchos contenedores/imágenes:**
   ```powershell
   # Ver uso de espacio de Docker
   docker system df
   ```

### Script de Diagnóstico Automático

```powershell
# ============================================================
# DIAGNÓSTICO AUTOMÁTICO RMS-SHOPIFY
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DIAGNÓSTICO DEL SISTEMA RMS-SHOPIFY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Docker
Write-Host "1. Estado de Docker" -ForegroundColor Yellow
Write-Host "   Versión Docker:" -ForegroundColor White
docker --version 2>&1

Write-Host "   Docker daemon:" -ForegroundColor White
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Funcionando" -ForegroundColor Green
} else {
    Write-Host "   ❌ NO funcionando" -ForegroundColor Red
    Write-Host "   Inicie Docker Desktop e intente de nuevo" -ForegroundColor Red
    exit
}

# 2. Contenedores
Write-Host ""
Write-Host "2. Estado de Contenedores" -ForegroundColor Yellow
docker compose ps

# 3. Uso de recursos
Write-Host ""
Write-Host "3. Uso de Recursos" -ForegroundColor Yellow
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# 4. Logs recientes
Write-Host ""
Write-Host "4. Últimos Logs (errores)" -ForegroundColor Yellow
docker compose logs --tail=10 2>&1 | Select-String -Pattern "error|ERROR|Error|fail|FAIL|Fail" | Select-Object -First 10

# 5. Conectividad
Write-Host ""
Write-Host "5. Pruebas de Conectividad" -ForegroundColor Yellow

Write-Host "   API (puerto 8000):" -ForegroundColor White
try {
    $api = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "   ✅ Responde (código: $($api.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "   ❌ No responde" -ForegroundColor Red
}

Write-Host "   Dashboard (puerto 8501):" -ForegroundColor White
try {
    $dashboard = Invoke-WebRequest -Uri "http://localhost:8501" -TimeoutSec 5
    Write-Host "   ✅ Responde (código: $($dashboard.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "   ❌ No responde" -ForegroundColor Red
}

# 6. Espacio en disco Docker
Write-Host ""
Write-Host "6. Uso de Disco Docker" -ForegroundColor Yellow
docker system df

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
```

---

## 11. 🔄 Mantenimiento

### Actualizar el Sistema

Cuando haya una nueva versión disponible:

```powershell
cd C:\RMS-Shopify-Integration

# 1. Detener servicios actuales
docker compose down

# 2. Hacer backup de configuración
Copy-Item ".env" ".env.backup.$(Get-Date -Format 'yyyyMMdd')"

# 3. Actualizar código (si usa Git)
git pull origin main

# 4. Reconstruir imagen
docker build -t rms-shopify-integration:latest .

# 5. Iniciar servicios
docker compose up -d

# 6. Verificar
docker compose ps
```

### Actualizar Docker Desktop

1. Docker Desktop le notificará cuando haya actualizaciones
2. Haga clic en el ícono de Docker → "Check for updates"
3. Siga las instrucciones del instalador
4. Los contenedores se reiniciarán automáticamente

### Limpiar Espacio en Disco

Docker puede usar mucho espacio con el tiempo.

```powershell
# Ver uso de espacio
docker system df

# Limpiar imágenes no usadas
docker image prune -a

# Limpiar todo lo no usado (imágenes, contenedores, volúmenes, redes)
docker system prune -a

# Limpiar volúmenes no usados (¡CUIDADO! puede borrar datos)
docker volume prune
```

### Backup de Datos

```powershell
# Crear directorio de backup
$backupDir = "C:\Backups\RMS-Shopify-$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backupDir -Force

# Backup de configuración
Copy-Item "C:\RMS-Shopify-Integration\.env" "$backupDir\.env"

# Backup de logs
Copy-Item "C:\RMS-Shopify-Integration\logs\*" "$backupDir\logs\" -Recurse

# Backup de volúmenes Docker (Redis)
docker run --rm -v rms-shopify-integration_redis-data:/data -v ${backupDir}:/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .

Write-Host "Backup creado en: $backupDir" -ForegroundColor Green
```

---

## 12. 📋 Comandos de Referencia Rápida

### Comandos Docker Esenciales

| Acción | Comando |
|--------|---------|
| Ver contenedores corriendo | `docker ps` |
| Ver todos los contenedores | `docker ps -a` |
| Ver logs de un contenedor | `docker logs [nombre]` |
| Ver logs en tiempo real | `docker logs -f [nombre]` |
| Reiniciar un contenedor | `docker restart [nombre]` |
| Detener un contenedor | `docker stop [nombre]` |
| Iniciar un contenedor | `docker start [nombre]` |
| Ver uso de recursos | `docker stats` |
| Ver imágenes | `docker images` |
| Ver uso de disco | `docker system df` |
| Limpiar recursos | `docker system prune` |

### Comandos Docker Compose

| Acción | Comando |
|--------|---------|
| Iniciar servicios | `docker compose up -d` |
| Detener servicios | `docker compose down` |
| Ver estado | `docker compose ps` |
| Ver logs | `docker compose logs` |
| Ver logs en tiempo real | `docker compose logs -f` |
| Reiniciar servicios | `docker compose restart` |
| Reiniciar un servicio | `docker compose restart api` |
| Reconstruir y reiniciar | `docker compose up -d --build` |

### URLs del Sistema

| Recurso | URL |
|---------|-----|
| Dashboard | http://localhost:8501 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Estado Sync | http://localhost:8000/api/v1/sync/monitor/status |

### Archivos Importantes

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.yml` | Configuración de servicios |
| `.env` | Variables de entorno (credenciales) |
| `Dockerfile` | Definición de imagen |
| `logs/` | Archivos de log de la aplicación |

---

## 13. ✅ Checklist de Instalación

Use esta lista para verificar que completó todos los pasos:

### Preparación
- [ ] Verificar requisitos del sistema (Sección 2)
- [ ] Ejecutar script de verificación (Sección 3)
- [ ] Corregir cualquier problema encontrado

### Instalación WSL2
- [ ] Instalar WSL2 (Sección 4)
- [ ] Reiniciar computadora
- [ ] Verificar `wsl --status`

### Instalación Docker
- [ ] Descargar Docker Desktop
- [ ] Instalar Docker Desktop
- [ ] Aceptar términos de servicio
- [ ] Verificar `docker --version`
- [ ] Verificar `docker run hello-world`

### Configuración Inicio Automático
- [ ] Configurar Docker Desktop para inicio automático
- [ ] Crear tarea programada de verificación (opcional)

### Despliegue del Proyecto
- [ ] Crear directorio `C:\RMS-Shopify-Integration`
- [ ] Copiar archivos del proyecto
- [ ] Crear y configurar archivo `.env`
- [ ] Construir imagen Docker
- [ ] Iniciar servicios con `docker compose up -d`

### Verificación
- [ ] Acceder a Dashboard: http://localhost:8501
- [ ] Acceder a API Docs: http://localhost:8000/docs
- [ ] Verificar Health: http://localhost:8000/health
- [ ] Todos los servicios muestran "connected"

### Firewall (si accede desde otras computadoras)
- [ ] Configurar reglas de firewall para puertos 8000 y 8501

### Prueba Final
- [ ] Reiniciar la computadora
- [ ] Verificar que Docker inicie automáticamente
- [ ] Verificar que los contenedores se inicien automáticamente
- [ ] Acceder al Dashboard después del reinicio

---

## 🎉 ¡Felicitaciones!

Si completó todos los pasos, su sistema RMS-Shopify Integration está:

✅ **Instalado** con Docker Desktop
✅ **Configurado** para inicio automático
✅ **Funcionando** con todos los servicios
✅ **Accesible** desde el navegador
✅ **Monitoreado** con tareas programadas

**El sistema se iniciará automáticamente cada vez que encienda la computadora.**

---

## 📞 Soporte

Si tiene problemas que no puede resolver:

1. **Recopile información:**
   - Ejecute el script de diagnóstico (Sección 10)
   - Guarde los logs: `docker compose logs > logs.txt`

2. **Contacte soporte:**
   - **Email:** enzo@oneclick.cr
   - **Incluya:** Descripción del problema, logs, y salida del diagnóstico

---

**Versión del documento:** 1.0
**Última actualización:** Noviembre 2025
**Compatible con:** Docker Desktop 4.x, Windows 10/11
