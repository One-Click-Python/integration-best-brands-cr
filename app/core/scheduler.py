"""
Motor de scheduling para sincronización automática RMS → Shopify.

Este módulo maneja la programación y ejecución de tareas de sincronización
periódicas entre RMS y Shopify, incluyendo detección de cambios automática.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import pytz

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global scheduler state
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None
_change_detector = None
_last_full_sync_date: Optional[date] = None
_last_rms_sync_time: Optional[datetime] = None
_last_rms_sync_success: bool = False

# Order polling state
_polling_service = None
_last_order_poll_time: Optional[datetime] = None


async def _save_scheduler_state():
    """
    Persiste el estado del scheduler en Redis para sobrevivir restarts.

    Guarda:
    - last_rms_sync_time: Timestamp de última sync RMS→Shopify
    - last_rms_sync_success: Éxito de última sync
    - last_full_sync_date: Fecha de última full sync programada
    """
    try:
        import json

        from app.core.redis_client import get_redis_client

        if not settings.REDIS_URL:
            logger.debug("Redis no configurado, estado no persistido")
            return

        redis = get_redis_client()

        state = {
            "last_rms_sync_time": _last_rms_sync_time.isoformat() if _last_rms_sync_time else None,
            "last_rms_sync_success": _last_rms_sync_success,
            "last_full_sync_date": _last_full_sync_date.isoformat() if _last_full_sync_date else None,
            "last_order_poll_time": _last_order_poll_time.isoformat() if _last_order_poll_time else None,
        }

        # Guardar en Redis con TTL de 24 horas
        await redis.set("scheduler:state", json.dumps(state), ex=86400)
        logger.debug("✅ Scheduler state saved to Redis")

    except Exception as e:
        logger.error(f"Error saving scheduler state to Redis: {e}")


async def _load_scheduler_state():
    """
    Carga el estado del scheduler desde Redis al iniciar.

    Permite que el scheduler reanude correctamente después de un restart,
    manteniendo el conocimiento de la última sync RMS→Shopify.
    """
    global _last_rms_sync_time, _last_rms_sync_success, _last_full_sync_date, _last_order_poll_time

    try:
        import json

        from app.core.redis_client import get_redis_client

        if not settings.REDIS_URL:
            logger.debug("Redis no configurado, estado no cargado")
            return

        redis = get_redis_client()

        state_json = await redis.get("scheduler:state")
        if not state_json:
            logger.info("No hay estado previo del scheduler en Redis")
            return

        state = json.loads(state_json)

        if state.get("last_rms_sync_time"):
            _last_rms_sync_time = datetime.fromisoformat(state["last_rms_sync_time"])
        _last_rms_sync_success = state.get("last_rms_sync_success", False)
        if state.get("last_full_sync_date"):
            _last_full_sync_date = datetime.fromisoformat(state["last_full_sync_date"]).date()
        if state.get("last_order_poll_time"):
            _last_order_poll_time = datetime.fromisoformat(state["last_order_poll_time"])

        logger.info(
            f"✅ Scheduler state loaded from Redis - "
            f"Last RMS sync: {_last_rms_sync_time.isoformat() if _last_rms_sync_time else 'None'}, "
            f"Success: {_last_rms_sync_success}, "
            f"Last order poll: {_last_order_poll_time.isoformat() if _last_order_poll_time else 'None'}"
        )

    except Exception as e:
        logger.error(f"Error loading scheduler state from Redis: {e}")


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

        # Load previous scheduler state from Redis (if available)
        await _load_scheduler_state()

        # Log order synchronization method priority
        if settings.ENABLE_ORDER_POLLING and settings.ENABLE_WEBHOOKS:
            logger.warning(
                "⚠️ AMBOS métodos de sincronización de órdenes activos. "
                "Order Polling es el método PRIMARY, webhooks son BACKUP."
            )
        elif settings.ENABLE_ORDER_POLLING:
            logger.info(
                "✅ Order Polling ACTIVO (método PRIMARY para sincronización de órdenes). "
                f"Intervalo: {settings.ORDER_POLLING_INTERVAL_MINUTES} minutos"
            )
        elif settings.ENABLE_WEBHOOKS:
            logger.warning(
                "⚠️ Solo webhooks activo (no recomendado). " "Considere habilitar Order Polling (más confiable)."
            )
        else:
            logger.error(
                "❌ NINGÚN método de sincronización de órdenes activo. "
                "Habilite ENABLE_ORDER_POLLING o ENABLE_WEBHOOKS."
            )

        _scheduler_running = True

        # Iniciar loop principal del scheduler (inicializará el detector internamente)
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
    global _scheduler_running, _scheduler_task, _change_detector, _polling_service

    try:
        if not _scheduler_running:
            logger.info("Scheduler no está ejecutándose")
            return

        logger.info("🛑 Deteniendo scheduler")
        _scheduler_running = False

        # Detener detector de cambios
        if _change_detector:
            await _change_detector.stop_monitoring()

        # Detener polling service
        if _polling_service:
            try:
                from app.services.order_polling_service import close_polling_service

                await close_polling_service()
                logger.info("✅ Order polling service detenido")
            except Exception as e:
                logger.error(f"Error deteniendo polling service: {e}")

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
    global _change_detector

    try:
        logger.info(f"🔄 Iniciando monitoreo automático cada {settings.SYNC_INTERVAL_MINUTES} minutos")

        # Inicializar detector de cambios en background (no bloquear startup)
        try:
            from app.services.change_detector import get_change_detector

            _change_detector = await get_change_detector()

            # Iniciar detección de cambios
            await _change_detector.start_monitoring(settings.SYNC_INTERVAL_MINUTES)
            logger.info("✅ Change detector inicializado y en monitoreo")
        except Exception as e:
            logger.error(f"❌ Error inicializando change detector: {e}")
            logger.warning("⚠️ Continuando sin change detector automático")

        # Loop de mantenimiento del scheduler
        while _scheduler_running:
            try:
                # Verificar estado del detector
                await _check_change_detector_health()

                # Verificar tareas programadas adicionales
                await _check_scheduled_syncs()

                # Verificar si debe ejecutarse reverse stock sync
                await _check_reverse_stock_sync()

                # Verificar si debe ejecutarse order polling
                await _check_order_polling()

                # Sleep por 1 minuto entre verificaciones
                await asyncio.sleep(60)  # 1 minuto

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


async def _check_reverse_stock_sync():
    """
    Verifica y ejecuta reverse stock sync si es necesario.

    Condiciones para ejecutar:
    - ENABLE_REVERSE_STOCK_SYNC=true
    - Última sync RMS→Shopify fue exitosa
    - Ha pasado el delay configurado desde la última sync RMS→Shopify
    """
    global _last_rms_sync_time, _last_rms_sync_success

    try:
        if not settings.ENABLE_REVERSE_STOCK_SYNC:
            return

        # Verificar que haya habido una sync RMS→Shopify exitosa
        if not _last_rms_sync_success or not _last_rms_sync_time:
            return

        # Verificar delay mínimo
        time_since_last_sync = datetime.now(pytz.UTC) - _last_rms_sync_time
        required_delay = timedelta(minutes=settings.REVERSE_SYNC_DELAY_MINUTES)

        if time_since_last_sync < required_delay:
            return

        logger.info(
            f"🔄 Ejecutando reverse stock sync "
            f"({time_since_last_sync.total_seconds() / 60:.1f} min después de RMS→Shopify)"
        )

        # Importar y ejecutar reverse sync
        from app.db.connection import ConnDB
        from app.db.rms.product_repository import ProductRepository
        from app.db.shopify_graphql_client import ShopifyGraphQLClient
        from app.services.reverse_stock_sync import ReverseStockSynchronizer

        # Initialize clients
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        primary_location_id = await shopify_client.get_primary_location_id()

        conn_db = ConnDB()
        await conn_db.initialize()
        product_repository = ProductRepository(conn_db)

        try:
            # Create synchronizer
            synchronizer = ReverseStockSynchronizer(
                shopify_client=shopify_client,
                product_repository=product_repository,
                primary_location_id=primary_location_id,
            )

            # Execute reverse sync
            report = await synchronizer.execute_reverse_sync(
                dry_run=False,
                delete_zero_stock=settings.REVERSE_SYNC_DELETE_ZERO_STOCK,
                batch_size=settings.REVERSE_SYNC_BATCH_SIZE,
                limit=None,  # Process all unsynced products
            )

            success_rate = (
                (report["statistics"]["variants_updated"] + report["statistics"]["variants_deleted"])
                / max(1, report["statistics"]["variants_checked"])
            ) * 100

            logger.info(
                f"✅ Reverse stock sync completado - "
                f"Success rate: {success_rate:.1f}%, "
                f"Updated: {report['statistics']['variants_updated']}, "
                f"Deleted: {report['statistics']['variants_deleted']}"
            )

            # Reset sync time to prevent re-execution
            _last_rms_sync_time = None
            _last_rms_sync_success = False

            # Persist reset state to Redis
            await _save_scheduler_state()

        finally:
            await conn_db.close()
            await shopify_client.close()

    except Exception as e:
        logger.error(f"Error en reverse stock sync: {e}", exc_info=True)


async def _check_order_polling():
    """
    Verifica y ejecuta order polling si es necesario.

    Condiciones para ejecutar:
    - ENABLE_ORDER_POLLING=true
    - Ha pasado el intervalo configurado desde el último polling
    - Webhook y polling pueden correr en paralelo (no se excluyen mutuamente)
    """
    global _polling_service, _last_order_poll_time

    try:
        if not settings.ENABLE_ORDER_POLLING:
            return

        # Verificar intervalo mínimo entre polls
        now = datetime.now(pytz.UTC)

        if _last_order_poll_time:
            time_since_last_poll = now - _last_order_poll_time
            required_interval = timedelta(minutes=settings.ORDER_POLLING_INTERVAL_MINUTES)

            if time_since_last_poll < required_interval:
                return

        logger.info(f"🔄 Ejecutando order polling " f"(intervalo: {settings.ORDER_POLLING_INTERVAL_MINUTES} min)")

        # Inicializar polling service si es necesario
        if not _polling_service:
            from app.services.order_polling_service import get_polling_service

            _polling_service = await get_polling_service()
            logger.info("✅ Order polling service initialized")

        # Ejecutar polling
        result = await _polling_service.poll_and_sync(
            lookback_minutes=settings.ORDER_POLLING_LOOKBACK_MINUTES,
            batch_size=settings.ORDER_POLLING_BATCH_SIZE,
            max_pages=settings.ORDER_POLLING_MAX_PAGES,
            dry_run=False,
        )

        # Actualizar timestamp del último polling
        _last_order_poll_time = now

        # Persistir estado
        await _save_scheduler_state()

        # Logging de resultados
        stats = result.get("statistics", {})
        logger.info(
            f"✅ Order polling completado - "
            f"Total: {stats.get('total_polled', 0)}, "
            f"Already synced: {stats.get('already_synced', 0)}, "
            f"Newly synced: {stats.get('newly_synced', 0)}, "
            f"Errors: {stats.get('sync_errors', 0)}"
        )

    except Exception as e:
        logger.error(f"Error en order polling: {e}", exc_info=True)


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
        if (
            current_time.hour == settings.FULL_SYNC_HOUR
            and current_time.minute >= settings.FULL_SYNC_MINUTE
            and current_time.minute < settings.FULL_SYNC_MINUTE + 10
        ):  # Ventana de 10 minutos
            # Verificar si ya se ejecutó hoy
            if _last_full_sync_date == current_date:
                return

            logger.info(
                f"🌙 Ejecutando sincronización completa programada ({current_time.strftime('%Y-%m-%d %H:%M:%S %Z')})"
            )

            if _change_detector:
                result = await _change_detector.force_full_sync()
                if result.get("success"):
                    _last_full_sync_date = current_date  # type: ignore
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
    global _change_detector, _last_full_sync_date, _last_rms_sync_time, _last_rms_sync_success
    global _polling_service, _last_order_poll_time

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
            "next_sync_estimate": _get_next_full_sync_time(),
        },
    }

    # Agregar información sobre reverse stock sync
    reverse_sync_info = {
        "enabled": settings.ENABLE_REVERSE_STOCK_SYNC,
        "delay_minutes": settings.REVERSE_SYNC_DELAY_MINUTES,
        "last_rms_sync_time": _last_rms_sync_time.isoformat() if _last_rms_sync_time else None,
        "last_rms_sync_success": _last_rms_sync_success,
        "will_execute_next_cycle": False,
        "seconds_until_eligible": None,
        "status": "waiting_for_rms_sync",
    }

    # Calcular si reverse sync se ejecutará en el próximo ciclo
    if _last_rms_sync_time and _last_rms_sync_success:
        now = datetime.now(pytz.UTC)
        time_since_sync = (now - _last_rms_sync_time).total_seconds()
        delay_seconds = settings.REVERSE_SYNC_DELAY_MINUTES * 60

        if time_since_sync >= delay_seconds:
            reverse_sync_info["will_execute_next_cycle"] = True
            reverse_sync_info["seconds_until_eligible"] = 0
            reverse_sync_info["status"] = "ready_to_execute"
        else:
            reverse_sync_info["seconds_until_eligible"] = int(delay_seconds - time_since_sync)
            reverse_sync_info["status"] = "waiting_for_delay"
    elif _last_rms_sync_time and not _last_rms_sync_success:
        reverse_sync_info["status"] = "blocked_by_failed_rms_sync"

    status["reverse_stock_sync"] = reverse_sync_info

    # Agregar información sobre order polling
    order_polling_info = {
        "enabled": settings.ENABLE_ORDER_POLLING,
        "interval_minutes": settings.ORDER_POLLING_INTERVAL_MINUTES,
        "lookback_minutes": settings.ORDER_POLLING_LOOKBACK_MINUTES,
        "batch_size": settings.ORDER_POLLING_BATCH_SIZE,
        "last_poll_time": _last_order_poll_time.isoformat() if _last_order_poll_time else None,
        "polling_service_initialized": _polling_service is not None,
        "will_execute_next_cycle": False,
        "seconds_until_next_poll": None,
        "webhooks_enabled": settings.ENABLE_WEBHOOKS,
        "status": "waiting",
    }

    # Calcular si polling se ejecutará en el próximo ciclo
    if settings.ENABLE_ORDER_POLLING:
        if _last_order_poll_time:
            now = datetime.now(pytz.UTC)
            time_since_poll = (now - _last_order_poll_time).total_seconds()
            interval_seconds = settings.ORDER_POLLING_INTERVAL_MINUTES * 60

            if time_since_poll >= interval_seconds:
                order_polling_info["will_execute_next_cycle"] = True
                order_polling_info["seconds_until_next_poll"] = 0
                order_polling_info["status"] = "ready_to_poll"
            else:
                order_polling_info["seconds_until_next_poll"] = int(interval_seconds - time_since_poll)
                order_polling_info["status"] = "waiting_for_interval"
        else:
            order_polling_info["status"] = "ready_to_poll"
            order_polling_info["will_execute_next_cycle"] = True

    status["order_polling"] = order_polling_info

    # Agregar estadísticas del detector si está disponible
    if _change_detector:
        detector_stats = _change_detector.get_stats()
        status.update({"change_detector": detector_stats, "monitoring_active": _change_detector.is_running()})

    # Agregar estadísticas del polling service si está disponible
    if _polling_service:
        try:
            polling_stats = _polling_service.get_statistics()
            status["order_polling"]["statistics"] = polling_stats
        except Exception as e:
            logger.error(f"Error getting polling statistics: {e}")

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
        return {"status": "not_initialized", "message": "Change detector not available"}


def notify_rms_sync_completed(success: bool):
    """
    Notifica al scheduler que una sync RMS→Shopify ha completado.

    Args:
        success: True si la sync fue exitosa

    Esta función se llama desde el change detector o desde endpoints de sync manual
    para activar el reverse stock sync si es necesario.
    """
    global _last_rms_sync_time, _last_rms_sync_success

    _last_rms_sync_time = datetime.now(pytz.UTC)
    _last_rms_sync_success = success

    if success:
        delay = settings.REVERSE_SYNC_DELAY_MINUTES
        logger.info(f"📝 RMS sync completada exitosamente - Reverse sync en {delay} min")
    else:
        logger.warning("⚠️ RMS sync completada con errores - Reverse sync no se ejecutará")

    # Persist state to Redis (non-blocking)
    # Create background task to save state without blocking
    try:
        asyncio.create_task(_save_scheduler_state())
    except RuntimeError:
        # If no event loop is running, log a warning but continue
        logger.warning("No event loop running, scheduler state not persisted to Redis")


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
        next_sync = now.replace(hour=settings.FULL_SYNC_HOUR, minute=settings.FULL_SYNC_MINUTE, second=0, microsecond=0)

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
