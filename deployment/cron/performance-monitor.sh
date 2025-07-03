#!/bin/bash

# Monitor de Performance para RMS-Shopify Integration
# Verifica métricas del sistema y de la aplicación

# Configuración
API_URL="http://localhost:8080"
LOG_FILE="/var/log/rms-shopify-integration/performance.log"
ALERT_EMAIL="admin@tu-empresa.com"
SERVICE_NAME="rms-shopify-integration"

# Umbrales de alerta
CPU_THRESHOLD=80        # % CPU
MEMORY_THRESHOLD=80     # % Memoria
DISK_THRESHOLD=85       # % Disco
RESPONSE_TIME_THRESHOLD=5000  # ms

# Función de logging
log_metric() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Obtener PID del proceso principal
get_service_pid() {
    systemctl show -p MainPID --value "$SERVICE_NAME"
}

# Verificar uso de CPU
check_cpu_usage() {
    local pid=$(get_service_pid)
    if [ "$pid" != "0" ] && [ -n "$pid" ]; then
        local cpu_usage=$(ps -p "$pid" -o %cpu --no-headers | tr -d ' ')
        log_metric "CPU_USAGE: ${cpu_usage}%"
        
        if (( $(echo "$cpu_usage > $CPU_THRESHOLD" | bc -l) )); then
            echo "ALERT: Alto uso de CPU: ${cpu_usage}%" | mail -s "RMS-Shopify High CPU Usage" "$ALERT_EMAIL"
        fi
    fi
}

# Verificar uso de memoria
check_memory_usage() {
    local pid=$(get_service_pid)
    if [ "$pid" != "0" ] && [ -n "$pid" ]; then
        local mem_usage=$(ps -p "$pid" -o %mem --no-headers | tr -d ' ')
        log_metric "MEMORY_USAGE: ${mem_usage}%"
        
        if (( $(echo "$mem_usage > $MEMORY_THRESHOLD" | bc -l) )); then
            echo "ALERT: Alto uso de memoria: ${mem_usage}%" | mail -s "RMS-Shopify High Memory Usage" "$ALERT_EMAIL"
        fi
    fi
}

# Verificar espacio en disco
check_disk_usage() {
    local disk_usage=$(df /opt/rms-shopify-integration | awk 'NR==2 {print $5}' | sed 's/%//')
    log_metric "DISK_USAGE: ${disk_usage}%"
    
    if [ "$disk_usage" -gt "$DISK_THRESHOLD" ]; then
        echo "ALERT: Poco espacio en disco: ${disk_usage}%" | mail -s "RMS-Shopify Low Disk Space" "$ALERT_EMAIL"
    fi
}

# Verificar tiempo de respuesta de la API
check_api_response_time() {
    local start_time=$(date +%s%3N)
    local response=$(curl -s -w "%{http_code}" "$API_URL/health" -o /dev/null)
    local end_time=$(date +%s%3N)
    local response_time=$((end_time - start_time))
    
    log_metric "API_RESPONSE_TIME: ${response_time}ms"
    log_metric "API_HTTP_CODE: $response"
    
    if [ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]; then
        echo "ALERT: Tiempo de respuesta API alto: ${response_time}ms" | mail -s "RMS-Shopify Slow API Response" "$ALERT_EMAIL"
    fi
    
    if [ "$response" != "200" ]; then
        echo "ALERT: API no responde correctamente: HTTP $response" | mail -s "RMS-Shopify API Error" "$ALERT_EMAIL"
    fi
}

# Verificar métricas de sincronización
check_sync_metrics() {
    local response=$(curl -s "$API_URL/api/v1/sync/monitor/stats" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Extraer métricas usando jq si está disponible, o grep como fallback
        if command -v jq &> /dev/null; then
            local total_checks=$(echo "$response" | jq -r '.data.change_detector.total_checks // 0')
            local errors=$(echo "$response" | jq -r '.data.change_detector.errors // 0')
            local items_synced=$(echo "$response" | jq -r '.data.change_detector.items_synced // 0')
            local running=$(echo "$response" | jq -r '.data.running // false')
        else
            local total_checks=$(echo "$response" | grep -o '"total_checks": [0-9]*' | grep -o '[0-9]*' | head -1)
            local errors=$(echo "$response" | grep -o '"errors": [0-9]*' | grep -o '[0-9]*' | head -1)
            local items_synced=$(echo "$response" | grep -o '"items_synced": [0-9]*' | grep -o '[0-9]*' | head -1)
            local running=$(echo "$response" | grep -o '"running": [a-z]*' | grep -o '[a-z]*' | head -1)
        fi
        
        log_metric "SYNC_TOTAL_CHECKS: ${total_checks:-0}"
        log_metric "SYNC_ERRORS: ${errors:-0}"
        log_metric "SYNC_ITEMS_SYNCED: ${items_synced:-0}"
        log_metric "SYNC_ENGINE_RUNNING: ${running:-false}"
        
        # Alertas por errores excesivos
        if [ "${errors:-0}" -gt 20 ]; then
            echo "ALERT: Muchos errores de sincronización: $errors" | mail -s "RMS-Shopify Sync Errors" "$ALERT_EMAIL"
        fi
        
        # Alerta si el motor no está corriendo
        if [ "$running" != "true" ]; then
            echo "ALERT: Motor de sincronización no está ejecutándose" | mail -s "RMS-Shopify Sync Engine Down" "$ALERT_EMAIL"
        fi
    else
        log_metric "SYNC_METRICS: ERROR - No se pudieron obtener métricas"
    fi
}

# Verificar conexiones de red
check_network_connections() {
    local connections=$(netstat -tn | grep :8080 | wc -l)
    log_metric "NETWORK_CONNECTIONS: $connections"
    
    if [ "$connections" -gt 100 ]; then
        echo "ALERT: Muchas conexiones activas: $connections" | mail -s "RMS-Shopify High Network Load" "$ALERT_EMAIL"
    fi
}

# Función principal
main() {
    # Crear directorio de logs si no existe
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log_metric "=== PERFORMANCE CHECK START ==="
    
    check_cpu_usage
    check_memory_usage
    check_disk_usage
    check_api_response_time
    check_sync_metrics
    check_network_connections
    
    log_metric "=== PERFORMANCE CHECK END ==="
}

# Ejecutar monitoreo
main "$@"