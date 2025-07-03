"""
Motor de scheduling para sincronización automática RMS → Shopify.

Este módulo maneja la programación y ejecución de tareas de sincronización
periódicas entre RMS y Shopify, incluyendo detección de cambios automática.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import pytz

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global scheduler state
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None
_change_detector = None
_last_full_sync_date: Optional[datetime] = None


async def start_scheduler():
    """
    Inicia el scheduler con detección automática de cambios.
    """
    global _scheduler_running, _scheduler_task, _change_detector

    try:
        if _scheduler_running:
            logger.warning("Scheduler ya está ejecutándose")
            return

        logger.info("🕒 Iniciando scheduler con detección automática de cambios")
        _scheduler_running = True

        # Inicializar detector de cambios
        from app.services.change_detector import get_change_detector
        _change_detector = await get_change_detector()

        # Iniciar loop principal del scheduler
        _scheduler_task = asyncio.create_task(_scheduler_loop())

        logger.info("✅ Scheduler iniciado correctamente")

    except Exception as e:
        logger.error(f"❌ Error iniciando scheduler: {e}")
        _scheduler_running = False
        raise


async def stop_scheduler():
    """
    Detiene el scheduler y la detección de cambios.
    """
    global _scheduler_running, _scheduler_task, _change_detector

    try:
        if not _scheduler_running:
            logger.info("Scheduler no está ejecutándose")
            return

        logger.info("🛑 Deteniendo scheduler")
        _scheduler_running = False

        # Detener detector de cambios
        if _change_detector:
            await _change_detector.stop_monitoring()

        # Cancelar tarea del scheduler
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass

        _scheduler_task = None
        logger.info("✅ Scheduler detenido correctamente")

    except Exception as e:
        logger.error(f"❌ Error deteniendo scheduler: {e}")


async def _scheduler_loop():
    """
    Loop principal del scheduler que ejecuta tareas programadas.
    """
    try:
        logger.info(f"🔄 Iniciando monitoreo automático cada {settings.SYNC_INTERVAL_MINUTES} minutos")
        
        # Iniciar detección de cambios
        if _change_detector:
            await _change_detector.start_monitoring(settings.SYNC_INTERVAL_MINUTES)
        
        # Loop de mantenimiento del scheduler
        while _scheduler_running:
            try:
                # Verificar estado del detector
                await _check_change_detector_health()
                
                # Verificar tareas programadas adicionales
                await _check_scheduled_syncs()
                
                # Sleep por 5 minutos entre verificaciones de salud
                await asyncio.sleep(300)  # 5 minutos
                
            except asyncio.CancelledError:
                logger.info("Loop del scheduler cancelado")
                break
            except Exception as e:
                logger.error(f"Error en loop del scheduler: {e}")
                # Continuar ejecutándose a pesar del error
                await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Error crítico en scheduler loop: {e}")
    finally:
        # Asegurar que el detector se detenga
        if _change_detector:
            await _change_detector.stop_monitoring()


async def _check_change_detector_health():
    """
    Verifica la salud del detector de cambios.
    """
    try:
        if not _change_detector:
            return
            
        if not _change_detector.is_running():
            logger.warning("⚠️ Detector de cambios no está ejecutándose, reiniciando...")
            await _change_detector.start_monitoring(settings.SYNC_INTERVAL_MINUTES)
            
    except Exception as e:
        logger.error(f"Error verificando salud del detector: {e}")


async def _check_scheduled_syncs():
    """
    Verifica y ejecuta sincronizaciones programadas adicionales.
    """
    global _last_full_sync_date
    
    try:
        if not settings.ENABLE_FULL_SYNC_SCHEDULE:
            return
            
        # Obtener tiempo actual en la zona horaria configurada
        tz = pytz.timezone(settings.FULL_SYNC_TIMEZONE)
        current_time = datetime.now(tz)
        current_date = current_time.date()
        
        # Verificar si es el día correcto (si está configurado)
        if settings.FULL_SYNC_DAYS is not None:
            current_weekday = current_time.weekday()  # 0=Lunes, 6=Domingo
            if current_weekday not in settings.FULL_SYNC_DAYS:
                return
        
        # Verificar si es la hora correcta
        if (current_time.hour == settings.FULL_SYNC_HOUR and 
            current_time.minute >= settings.FULL_SYNC_MINUTE and 
            current_time.minute < settings.FULL_SYNC_MINUTE + 10):  # Ventana de 10 minutos
            
            # Verificar si ya se ejecutó hoy
            if _last_full_sync_date == current_date:
                return
            
            logger.info(f"🌙 Ejecutando sincronización completa programada ({current_time.strftime('%Y-%m-%d %H:%M:%S %Z')})")
            
            if _change_detector:
                result = await _change_detector.force_full_sync()
                if result.get("success"):
                    _last_full_sync_date = current_date
                    logger.info("✅ Sincronización completa programada completada exitosamente")
                else:
                    logger.error(f"❌ Error en sincronización completa programada: {result.get('error')}")
                
    except Exception as e:
        logger.error(f"Error en sincronizaciones programadas: {e}")


def get_scheduler_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual del scheduler.

    Returns:
        Dict: Información del estado
    """
    global _change_detector, _last_full_sync_date
    
    status = {
        "running": _scheduler_running,
        "task_active": _scheduler_task is not None and not _scheduler_task.done(),
        "sync_interval_minutes": settings.SYNC_INTERVAL_MINUTES,
        "change_detection_enabled": _change_detector is not None,
        "full_sync_schedule": {
            "enabled": settings.ENABLE_FULL_SYNC_SCHEDULE,
            "hour": settings.FULL_SYNC_HOUR,
            "minute": settings.FULL_SYNC_MINUTE,
            "timezone": settings.FULL_SYNC_TIMEZONE,
            "days": settings.FULL_SYNC_DAYS,
            "last_sync_date": _last_full_sync_date.isoformat() if _last_full_sync_date else None,
            "next_sync_estimate": _get_next_full_sync_time()
        }
    }
    
    # Agregar estadísticas del detector si está disponible
    if _change_detector:
        detector_stats = _change_detector.get_stats()
        status.update({
            "change_detector": detector_stats,
            "monitoring_active": _change_detector.is_running()
        })
    
    return status


async def manual_sync_trigger() -> Dict[str, Any]:
    """
    Trigger manual de verificación y sincronización.
    
    Returns:
        Dict: Resultado de la sincronización manual
    """
    try:
        logger.info("🔄 Ejecutando sincronización manual")
        
        if not _change_detector:
            return {"success": False, "error": "Change detector not initialized"}
        
        result = await _change_detector.manual_check_and_sync()
        
        logger.info("✅ Sincronización manual completada")
        return {"success": True, "result": result}
        
    except Exception as e:
        logger.error(f"Error en sincronización manual: {e}")
        return {"success": False, "error": str(e)}


async def force_full_sync() -> Dict[str, Any]:
    """
    Fuerza una sincronización completa.
    
    Returns:
        Dict: Resultado de la sincronización completa
    """
    try:
        logger.info("🔄 Ejecutando sincronización completa forzada")
        
        if not _change_detector:
            return {"success": False, "error": "Change detector not initialized"}
        
        result = await _change_detector.force_full_sync()
        
        logger.info("✅ Sincronización completa forzada completada")
        return {"success": True, "result": result}
        
    except Exception as e:
        logger.error(f"Error en sincronización forzada: {e}")
        return {"success": False, "error": str(e)}


async def update_sync_interval(new_interval_minutes: int) -> bool:
    """
    Actualiza el intervalo de sincronización.
    
    Args:
        new_interval_minutes: Nuevo intervalo en minutos
        
    Returns:
        bool: True si se actualizó correctamente
    """
    try:
        if new_interval_minutes < 1 or new_interval_minutes > 1440:  # 1 min a 24 horas
            raise ValueError("Intervalo debe estar entre 1 y 1440 minutos")
        
        logger.info(f"🔧 Actualizando intervalo de sincronización a {new_interval_minutes} minutos")
        
        # Reiniciar el detector con el nuevo intervalo
        if _change_detector and _change_detector.is_running():
            await _change_detector.stop_monitoring()
            await _change_detector.start_monitoring(new_interval_minutes)
        
        return True
        
    except Exception as e:
        logger.error(f"Error actualizando intervalo: {e}")
        return False


def get_sync_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas detalladas de sincronización.
    
    Returns:
        Dict: Estadísticas de sincronización
    """
    global _change_detector
    
    if _change_detector:
        return _change_detector.get_stats()
    else:
        return {
            "status": "not_initialized",
            "message": "Change detector not available"
        }


def _get_next_full_sync_time() -> Optional[str]:
    """
    Calcula la próxima hora de sincronización completa programada.
    
    Returns:
        Optional[str]: Próxima sincronización en formato ISO o None si no está habilitada
    """
    if not settings.ENABLE_FULL_SYNC_SCHEDULE:
        return None
    
    try:
        tz = pytz.timezone(settings.FULL_SYNC_TIMEZONE)
        now = datetime.now(tz)
        
        # Hora objetivo de hoy
        next_sync = now.replace(
            hour=settings.FULL_SYNC_HOUR,
            minute=settings.FULL_SYNC_MINUTE,
            second=0,
            microsecond=0
        )
        
        # Si ya pasó la hora de hoy, buscar el próximo día válido
        if now >= next_sync:
            next_sync = next_sync + timedelta(days=1)
        
        # Si hay días específicos configurados, buscar el próximo día válido
        if settings.FULL_SYNC_DAYS is not None:
            days_ahead = 0
            while days_ahead < 7:
                if next_sync.weekday() in settings.FULL_SYNC_DAYS:
                    break
                next_sync = next_sync + timedelta(days=1)
                days_ahead += 1
            else:
                # No se encontró un día válido en la próxima semana
                return None
        
        return next_sync.isoformat()
        
    except Exception as e:
        logger.error(f"Error calculando próxima sincronización: {e}")
        return None
