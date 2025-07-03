#!/bin/bash

# RMS-Shopify Integration - Cron Monitor Script
# Verifica que el servicio esté funcionando y ejecuta checks de salud

# Configuración
SERVICE_NAME="rms-shopify-integration"
API_URL="http://localhost:8080"
LOG_FILE="/var/log/rms-shopify-integration/cron-monitor.log"
ALERT_EMAIL="admin@tu-empresa.com"
MAX_RETRIES=3

# Función de logging
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Función para enviar alertas
send_alert() {
    local subject="$1"
    local message="$2"
    echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    log_message "ALERT: $subject - $message"
}

# Verificar si el servicio systemd está activo
check_systemd_service() {
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        log_message "ERROR: Servicio systemd $SERVICE_NAME no está activo"
        
        # Intentar reiniciar el servicio
        log_message "INFO: Intentando reiniciar servicio $SERVICE_NAME"
        if systemctl restart "$SERVICE_NAME"; then
            log_message "SUCCESS: Servicio $SERVICE_NAME reiniciado exitosamente"
            sleep 30  # Esperar que el servicio se estabilice
        else
            send_alert "RMS-Shopify Service Down" "No se pudo reiniciar el servicio $SERVICE_NAME"
            return 1
        fi
    fi
    return 0
}

# Verificar health check de la API
check_api_health() {
    local retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            log_message "SUCCESS: API health check passed"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        log_message "WARNING: API health check failed (attempt $retry_count/$MAX_RETRIES)"
        sleep 10
    done
    
    send_alert "RMS-Shopify API Health Check Failed" "API no responde después de $MAX_RETRIES intentos"
    return 1
}

# Verificar estado del motor de sincronización
check_sync_engine() {
    local response
    response=$(curl -s "$API_URL/api/v1/sync/monitor/status" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Verificar si el motor está ejecutándose
        if echo "$response" | grep -q '"running": true'; then
            log_message "SUCCESS: Motor de sincronización está activo"
            return 0
        else
            log_message "WARNING: Motor de sincronización no está ejecutándose"
            
            # Intentar reiniciar el motor
            if curl -s -X POST "$API_URL/api/v1/sync/monitor/trigger" > /dev/null 2>&1; then
                log_message "INFO: Trigger de sincronización enviado"
            else
                send_alert "RMS-Shopify Sync Engine Down" "Motor de sincronización no responde"
                return 1
            fi
        fi
    else
        log_message "ERROR: No se pudo verificar estado del motor de sincronización"
        return 1
    fi
}

# Verificar métricas y enviar alertas si hay problemas
check_metrics() {
    local response
    response=$(curl -s "$API_URL/api/v1/sync/monitor/stats" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Extraer tasa de errores (si existe)
        local error_rate
        error_rate=$(echo "$response" | grep -o '"errors": [0-9]*' | grep -o '[0-9]*')
        
        if [ "$error_rate" -gt 10 ]; then
            send_alert "RMS-Shopify High Error Rate" "Tasa de errores alta: $error_rate errores detectados"
        fi
        
        log_message "INFO: Métricas verificadas - Errores: $error_rate"
    else
        log_message "WARNING: No se pudieron obtener métricas"
    fi
}

# Función principal
main() {
    log_message "INFO: Iniciando verificación de monitor RMS-Shopify"
    
    # Crear directorio de logs si no existe
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Verificaciones en orden
    if check_systemd_service; then
        sleep 5  # Dar tiempo para que la API se estabilice
        
        if check_api_health; then
            check_sync_engine
            check_metrics
        fi
    fi
    
    log_message "INFO: Verificación de monitor completada"
}

# Ejecutar verificaciones
main "$@"