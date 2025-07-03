"""
Endpoints para monitoreo y control del sistema de sincronización automática.

Este módulo proporciona APIs para controlar y monitorear el motor de detección
de cambios y sincronización automática entre RMS y Shopify.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.scheduler import (
    force_full_sync,
    get_scheduler_status,
    get_sync_stats,
    manual_sync_trigger,
    update_sync_interval,
)

logger = logging.getLogger(__name__)

# Crear router
router = APIRouter()


class SyncIntervalUpdate(BaseModel):
    """Modelo para actualizar intervalo de sincronización."""
    interval_minutes: int = Field(
        ..., 
        ge=1, 
        le=1440, 
        description="Intervalo en minutos (1-1440)"
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_sync_monitoring_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual del sistema de monitoreo y sincronización.
    
    Returns:
        Dict: Estado completo del sistema
    """
    try:
        status_info = get_scheduler_status()
        
        return {
            "status": "success",
            "data": status_info,
            "message": "Estado del sistema obtenido correctamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del sistema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}"
        )


@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_sync_statistics() -> Dict[str, Any]:
    """
    Obtiene estadísticas detalladas de sincronización.
    
    Returns:
        Dict: Estadísticas completas del sistema
    """
    try:
        stats = get_sync_stats()
        
        return {
            "status": "success",
            "data": stats,
            "message": "Estadísticas obtenidas correctamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.post("/trigger", status_code=status.HTTP_200_OK)
async def trigger_manual_sync() -> Dict[str, Any]:
    """
    Ejecuta una verificación y sincronización manual inmediata.
    
    Returns:
        Dict: Resultado de la sincronización manual
    """
    try:
        logger.info("API: Iniciando sincronización manual")
        
        result = await manual_sync_trigger()
        
        if result.get("success"):
            return {
                "status": "success",
                "data": result,
                "message": "Sincronización manual ejecutada correctamente"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en sincronización manual: {result.get('error', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en sincronización manual: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando sincronización manual: {str(e)}"
        )


@router.post("/force-full-sync", status_code=status.HTTP_200_OK)
async def trigger_full_sync() -> Dict[str, Any]:
    """
    Fuerza una sincronización completa de todos los productos.
    
    Returns:
        Dict: Resultado de la sincronización completa
    """
    try:
        logger.info("API: Iniciando sincronización completa forzada")
        
        result = await force_full_sync()
        
        if result.get("success"):
            return {
                "status": "success",
                "data": result,
                "message": "Sincronización completa ejecutada correctamente"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en sincronización completa: {result.get('error', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en sincronización completa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando sincronización completa: {str(e)}"
        )


@router.put("/interval", status_code=status.HTTP_200_OK)
async def update_sync_monitoring_interval(
    interval_data: SyncIntervalUpdate
) -> Dict[str, Any]:
    """
    Actualiza el intervalo de verificación de cambios.
    
    Args:
        interval_data: Nuevo intervalo en minutos
        
    Returns:
        Dict: Confirmación de actualización
    """
    try:
        logger.info(f"API: Actualizando intervalo a {interval_data.interval_minutes} minutos")
        
        success = await update_sync_interval(interval_data.interval_minutes)
        
        if success:
            return {
                "status": "success",
                "data": {
                    "new_interval_minutes": interval_data.interval_minutes,
                    "updated_at": "2025-07-03T10:00:00Z"  # You might want to use actual timestamp
                },
                "message": f"Intervalo actualizado a {interval_data.interval_minutes} minutos"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo actualizar el intervalo"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando intervalo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando intervalo: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def get_sync_monitoring_health() -> Dict[str, Any]:
    """
    Verifica la salud del sistema de monitoreo.
    
    Returns:
        Dict: Estado de salud del sistema
    """
    try:
        status_info = get_scheduler_status()
        
        is_healthy = (
            status_info.get("running", False) and
            status_info.get("task_active", False) and
            status_info.get("change_detection_enabled", False)
        )
        
        health_status = "healthy" if is_healthy else "unhealthy"
        
        response = {
            "status": "success",
            "data": {
                "health": health_status,
                "running": status_info.get("running", False),
                "monitoring_active": status_info.get("monitoring_active", False),
                "change_detection_enabled": status_info.get("change_detection_enabled", False),
                "last_check": status_info.get("change_detector", {}).get("last_check_time"),
                "total_checks": status_info.get("change_detector", {}).get("total_checks", 0),
                "changes_detected": status_info.get("change_detector", {}).get("changes_detected", 0),
                "items_synced": status_info.get("change_detector", {}).get("items_synced", 0)
            },
            "message": f"Sistema de monitoreo está {health_status}"
        }
        
        # Si no está saludable, devolver código de error
        if not is_healthy:
            return response  # Aún devolver 200 pero con información de unhealthy
            
        return response
        
    except Exception as e:
        logger.error(f"Error verificando salud del sistema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando salud: {str(e)}"
        )


@router.get("/recent-activity", status_code=status.HTTP_200_OK)
async def get_recent_sync_activity() -> Dict[str, Any]:
    """
    Obtiene actividad reciente de sincronización.
    
    Returns:
        Dict: Actividad reciente del sistema
    """
    try:
        stats = get_sync_stats()
        
        # Extraer información relevante de actividad reciente
        activity = {
            "last_sync_time": stats.get("last_sync_time"),
            "last_check_time": stats.get("last_check_time"),
            "recent_stats": {
                "total_checks": stats.get("total_checks", 0),
                "changes_detected": stats.get("changes_detected", 0),
                "items_synced": stats.get("items_synced", 0),
                "errors": stats.get("errors", 0)
            },
            "system_status": {
                "running": stats.get("running", False),
                "monitoring_active": stats.get("monitoring_active", False)
            }
        }
        
        return {
            "status": "success",
            "data": activity,
            "message": "Actividad reciente obtenida correctamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo actividad reciente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo actividad: {str(e)}"
        )


@router.get("/config", status_code=status.HTTP_200_OK)
async def get_sync_configuration() -> Dict[str, Any]:
    """
    Obtiene la configuración actual del sistema de sincronización.
    
    Returns:
        Dict: Configuración actual
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        
        config = {
            "sync_interval_minutes": settings.SYNC_INTERVAL_MINUTES,
            "enable_scheduled_sync": settings.ENABLE_SCHEDULED_SYNC,
            "batch_size": settings.SYNC_BATCH_SIZE,
            "max_concurrent_jobs": settings.SYNC_MAX_CONCURRENT_JOBS,
            "timeout_minutes": settings.SYNC_TIMEOUT_MINUTES,
            "rms_sync_incremental_hours": settings.RMS_SYNC_INCREMENTAL_HOURS
        }
        
        return {
            "status": "success",
            "data": config,
            "message": "Configuración obtenida correctamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo configuración: {str(e)}"
        )