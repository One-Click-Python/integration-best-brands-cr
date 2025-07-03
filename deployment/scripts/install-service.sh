#!/bin/bash

# Script de instalación para integración completa con sistema operativo
# RMS-Shopify Integration Service Installation

set -e

# Configuración
SERVICE_NAME="rms-shopify-integration"
APP_DIR="/opt/rms-shopify-integration"
USER_NAME="rms-user"
LOG_DIR="/var/log/rms-shopify-integration"
SYSTEMD_DIR="/etc/systemd/system"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función de logging
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar si se ejecuta como root
if [[ $EUID -ne 0 ]]; then
   error "Este script debe ejecutarse como root (use sudo)"
   exit 1
fi

log "Iniciando instalación de RMS-Shopify Integration como servicio del sistema..."

# 1. Crear usuario del sistema
log "Creando usuario del sistema: $USER_NAME"
if ! id "$USER_NAME" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir $APP_DIR --create-home $USER_NAME
    log "Usuario $USER_NAME creado"
else
    warning "Usuario $USER_NAME ya existe"
fi

# 2. Crear directorios
log "Creando directorios del sistema..."
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p $APP_DIR/temp
mkdir -p $APP_DIR/logs

# 3. Copiar archivos de la aplicación
log "Copiando archivos de la aplicación..."
if [ -d "$(pwd)/app" ]; then
    cp -r app/ $APP_DIR/
    cp -r deployment/ $APP_DIR/
    cp requirements.txt $APP_DIR/ 2>/dev/null || true
    cp pyproject.toml $APP_DIR/ 2>/dev/null || true
    cp .env.example $APP_DIR/
else
    error "No se encontraron archivos de la aplicación en el directorio actual"
    exit 1
fi

# 4. Configurar permisos
log "Configurando permisos..."
chown -R $USER_NAME:$USER_NAME $APP_DIR
chown -R $USER_NAME:$USER_NAME $LOG_DIR
chmod +x $APP_DIR/deployment/cron/*.sh
chmod +x $APP_DIR/deployment/scripts/*.sh

# 5. Instalar dependencias de Python
log "Instalando dependencias de Python..."
cd $APP_DIR
if command -v poetry &> /dev/null; then
    sudo -u $USER_NAME poetry install --no-dev
else
    # Crear virtual environment
    sudo -u $USER_NAME python3 -m venv .venv
    sudo -u $USER_NAME .venv/bin/pip install -r requirements.txt
fi

# 6. Instalar servicio systemd
log "Instalando servicio systemd..."
cp deployment/systemd/$SERVICE_NAME.service $SYSTEMD_DIR/
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# 7. Configurar archivo de entorno
log "Configurando archivo de entorno..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp $APP_DIR/.env.example $APP_DIR/.env
    chown $USER_NAME:$USER_NAME $APP_DIR/.env
    chmod 600 $APP_DIR/.env
    warning "Archivo .env creado desde ejemplo. DEBES configurar las variables antes de iniciar el servicio."
fi

# 8. Configurar tareas cron
log "Configurando tareas cron..."
crontab_file="/tmp/rms-cron-$USER_NAME"
cp deployment/cron/crontab.example $crontab_file
crontab -u $USER_NAME $crontab_file
rm $crontab_file
log "Tareas cron instaladas para usuario $USER_NAME"

# 9. Configurar logrotate
log "Configurando rotación de logs..."
cat > /etc/logrotate.d/rms-shopify-integration << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER_NAME $USER_NAME
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF

# 10. Crear scripts de utilidad
log "Creando scripts de utilidad..."
cat > /usr/local/bin/rms-status << EOF
#!/bin/bash
systemctl status $SERVICE_NAME
curl -s http://localhost:8080/api/v1/sync/monitor/status | python3 -m json.tool
EOF

cat > /usr/local/bin/rms-logs << EOF
#!/bin/bash
journalctl -u $SERVICE_NAME -f
EOF

chmod +x /usr/local/bin/rms-status
chmod +x /usr/local/bin/rms-logs

# 11. Verificar instalación
log "Verificando instalación..."
if systemctl is-enabled $SERVICE_NAME >/dev/null 2>&1; then
    log "✅ Servicio $SERVICE_NAME habilitado correctamente"
else
    error "❌ Fallo al habilitar servicio $SERVICE_NAME"
    exit 1
fi

# Mostrar resumen
log "🎉 Instalación completada exitosamente!"
echo
echo "========================================================================================"
echo "                           RESUMEN DE INSTALACIÓN"
echo "========================================================================================"
echo "Servicio:                $SERVICE_NAME"
echo "Directorio de aplicación: $APP_DIR"
echo "Usuario del sistema:     $USER_NAME"
echo "Logs del sistema:        $LOG_DIR"
echo "Logs de systemd:         journalctl -u $SERVICE_NAME"
echo
echo "COMANDOS ÚTILES:"
echo "  Estado del servicio:   systemctl status $SERVICE_NAME"
echo "  Iniciar servicio:      systemctl start $SERVICE_NAME"
echo "  Detener servicio:      systemctl stop $SERVICE_NAME"
echo "  Reiniciar servicio:    systemctl restart $SERVICE_NAME"
echo "  Ver logs:              rms-logs"
echo "  Ver estado API:        rms-status"
echo
echo "PRÓXIMOS PASOS:"
echo "1. Editar $APP_DIR/.env con tu configuración"
echo "2. Iniciar el servicio: systemctl start $SERVICE_NAME"
echo "3. Verificar estado: rms-status"
echo "========================================================================================"