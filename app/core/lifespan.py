"""
Gestión del ciclo de vida de la aplicación FastAPI.

Este módulo maneja los eventos de startup y shutdown de la aplicación,
incluyendo inicialización de servicios, verificación de conexiones y limpieza.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación.
    Maneja eventos de startup y shutdown de manera ordenada.

    Args:
        app: Instancia de FastAPI
    """
    # === STARTUP ===
    logger.info("🚀 Iniciando RMS-Shopify Integration...", app)

    try:
        # 1. Configurar logging
        await startup_configure_logging()

        # 2. Verificar configuración
        await startup_verify_configuration()

        # 3. Verificar conexiones críticas
        await startup_verify_connections()

        # 4. Inicializar servicios asíncronos
        await startup_initialize_services()

        # 5. Configurar tareas programadas
        await startup_configure_scheduled_tasks()

        # 6. Configurar monitoreo
        await startup_configure_monitoring()

        # 7. Ejecutar verificaciones finales
        await startup_final_checks()

        logger.info("🎉 Aplicación iniciada correctamente")

    except Exception as e:
        logger.error(f"❌ Error durante el startup: {e}")
        await cleanup_on_startup_failure()
        sys.exit(1)

    # === YIELD (aplicación corriendo) ===
    yield

    # === SHUTDOWN ===
    logger.info("🛑 Cerrando RMS-Shopify Integration...")

    try:
        # 1. Detener tareas programadas
        await shutdown_stop_scheduled_tasks()

        # 2. Finalizar servicios asíncronos
        await shutdown_cleanup_services()

        # 3. Cerrar conexiones
        await shutdown_close_connections()

        # 4. Limpiar recursos
        await shutdown_cleanup_resources()

        # 5. Finalizar logging
        await shutdown_finalize_logging()

        logger.info("👋 Aplicación cerrada correctamente")

    except Exception as e:
        logger.error(f"❌ Error durante el shutdown: {e}")


# === FUNCIONES DE STARTUP ===


async def startup_configure_logging():
    """Configura el sistema de logging."""
    try:
        setup_logging()
        logger.info("✅ Sistema de logging configurado")
    except Exception as e:
        print(f"Error configurando logging: {e}")
        raise


async def startup_verify_configuration():
    """Verifica que la configuración sea válida."""
    try:
        # Verificar variables críticas
        required_vars = [
            "RMS_DB_HOST",
            "RMS_DB_NAME",
            "SHOPIFY_SHOP_URL",
            "SHOPIFY_ACCESS_TOKEN",
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(settings, var, None):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Variables de configuración faltantes: {missing_vars}")

        # Validar configuración de Shopify
        if not settings.SHOPIFY_SHOP_URL.endswith(".myshopify.com"):
            raise ValueError("SHOPIFY_SHOP_URL debe terminar en .myshopify.com")

        logger.info("✅ Configuración verificada")

    except Exception as e:
        logger.error(f"Error en configuración: {e}")
        raise


async def startup_verify_connections():
    """Verifica conexiones a servicios externos."""
    try:
        connection_results = {}

        # Verificar conexión a RMS usando la nueva infraestructura
        try:
            from app.db.connection import get_db_connection
            
            conn_db = get_db_connection()
            if not conn_db.is_initialized():
                logger.info("Inicializando conexión a base de datos RMS...")
                await conn_db.initialize()
            
            rms_ok = await conn_db.test_connection()
            connection_results["rms"] = rms_ok
            if rms_ok:
                logger.info("✅ Conexión a RMS verificada")
                # Verificar acceso a View_Items
                health_info = await conn_db.health_check()
                logger.info(f"✅ Health check RMS: {health_info['response_time_ms']}ms")
            else:
                logger.error("❌ Conexión a RMS falló")
        except Exception as e:
            logger.error(f"❌ Error conectando a RMS: {e}")
            connection_results["rms"] = False

        # Verificar conexión a Shopify
        try:
            from app.db.shopify_client import test_shopify_connection

            shopify_ok = await test_shopify_connection()
            connection_results["shopify"] = shopify_ok
            if shopify_ok:
                logger.info("✅ Conexión a Shopify verificada")
            else:
                logger.error("❌ Conexión a Shopify falló")
        except Exception as e:
            logger.error(f"❌ Error conectando a Shopify: {e}")
            connection_results["shopify"] = False

        # Verificar Redis (opcional)
        if settings.REDIS_URL:
            try:
                from app.core.redis_client import test_redis_connection

                redis_ok = await test_redis_connection()
                connection_results["redis"] = redis_ok
                if redis_ok:
                    logger.info("✅ Conexión a Redis verificada")
                else:
                    logger.warning("⚠️ Conexión a Redis falló (no crítico)")
            except Exception as e:
                logger.warning(f"⚠️ Error conectando a Redis: {e} (no crítico)")
                connection_results["redis"] = False

        # Verificar que servicios críticos estén disponibles
        # Temporalmente hacer RMS opcional para desarrollo
        critical_services = ["shopify"]  # Solo Shopify es crítico por ahora
        failed_critical = [service for service in critical_services if not connection_results.get(service, False)]

        if failed_critical:
            raise ConnectionError(f"Servicios críticos no disponibles: {failed_critical}")
        
        # Advertir si RMS no está disponible
        if not connection_results.get("rms", False):
            logger.warning("⚠️ RMS no está disponible - Las funciones de sincronización con RMS estarán deshabilitadas")

        logger.info("✅ Todas las conexiones críticas verificadas")

    except Exception as e:
        logger.error(f"Error verificando conexiones: {e}")
        raise


async def startup_initialize_services():
    """Inicializa servicios asíncronos."""
    try:
        # Inicializar cliente Redis para caché
        if settings.REDIS_URL:
            try:
                from app.core import redis_client

                await redis_client.initialize_redis()
                logger.info("✅ Cliente Redis inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando Redis: {e} (no crítico)")

        # Inicializar conexión a base de datos RMS
        try:
            from app.db.connection import get_db_connection
            
            conn_db = get_db_connection()
            if not conn_db.is_initialized():
                await conn_db.initialize()
            logger.info("✅ Conexión RMS inicializada")
        except Exception as e:
            logger.error(f"❌ Error inicializando conexión RMS: {e}")
            logger.warning("⚠️ Continuando sin conexión RMS - Las funciones de sincronización con RMS estarán deshabilitadas")
            # No lanzar la excepción para permitir que la app arranque sin RMS

        # Inicializar cliente HTTP para Shopify
        try:
            from app.db import shopify_client

            await shopify_client.initialize_http_client()
            logger.info("✅ Cliente HTTP Shopify inicializado")
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente Shopify: {e}")
            raise

        logger.info("✅ Servicios asíncronos inicializados")

    except Exception as e:
        logger.error(f"Error inicializando servicios: {e}")
        raise


async def startup_configure_scheduled_tasks():
    """Configura tareas programadas."""
    try:
        if settings.ENABLE_SCHEDULED_SYNC:
            from app.core.scheduler import start_scheduler

            await start_scheduler()
            logger.info("✅ Scheduler de tareas iniciado")
        else:
            logger.info("ℹ️ Tareas programadas deshabilitadas")

    except Exception as e:
        logger.error(f"Error configurando tareas programadas: {e}")
        # No es crítico, continuar sin scheduler
        logger.warning("⚠️ Continuando sin scheduler automático")


async def startup_configure_monitoring():
    """Configura sistema de monitoreo."""
    try:
        # Inicializar métricas
        if settings.METRICS_ENABLED:
            from app.core.metrics import initialize_metrics

            await initialize_metrics()
            logger.info("✅ Sistema de métricas inicializado")

        # Configurar alertas
        if settings.ALERT_EMAIL_ENABLED:
            from app.utils.notifications import test_email_configuration

            await test_email_configuration()
            logger.info("✅ Sistema de alertas configurado")

    except Exception as e:
        logger.warning(f"⚠️ Error configurando monitoreo: {e} (no crítico)")


async def startup_final_checks():
    """Ejecuta verificaciones finales antes de completar el startup."""
    try:
        # Verificar que todos los endpoints estén accesibles
        from app.core.health import is_system_healthy

        if await is_system_healthy():
            logger.info("✅ Sistema completamente saludable")
        else:
            logger.warning("⚠️ Algunos servicios no están completamente saludables")

        # Log de configuración activa
        logger.info("🔧 Configuración activa:")
        logger.info(f"   - Entorno: {settings.ENVIRONMENT}")
        logger.info(f"   - Debug: {settings.DEBUG}")
        logger.info(f"   - Rate Limiting: {settings.ENABLE_RATE_LIMITING}")
        logger.info(f"   - Sync Programado: {settings.ENABLE_SCHEDULED_SYNC}")
        logger.info(f"   - Métricas: {settings.METRICS_ENABLED}")

    except Exception as e:
        logger.warning(f"⚠️ Error en verificaciones finales: {e}")


async def cleanup_on_startup_failure():
    """Limpia recursos en caso de fallo durante startup."""
    try:
        logger.info("🧹 Limpiando recursos tras fallo en startup...")

        # Cerrar conexiones parciales
        await shutdown_close_connections()

        # Limpiar servicios parcialmente inicializados
        await shutdown_cleanup_services()

    except Exception as e:
        logger.error(f"Error durante limpieza de startup: {e}")


# === FUNCIONES DE SHUTDOWN ===


async def shutdown_stop_scheduled_tasks():
    """Detiene tareas programadas."""
    try:
        if settings.ENABLE_SCHEDULED_SYNC:
            from app.core.scheduler import stop_scheduler

            await stop_scheduler()
            logger.info("✅ Scheduler detenido")

    except Exception as e:
        logger.error(f"Error deteniendo scheduler: {e}")


async def shutdown_cleanup_services():
    """Finaliza servicios asíncronos."""
    try:
        # Finalizar trabajos en progreso
        await finalize_pending_jobs()

        # Cerrar cliente HTTP
        try:
            from app.db import shopify_client

            await shopify_client.close_http_client()
            logger.info("✅ Cliente HTTP Shopify cerrado")
        except Exception as e:
            logger.error(f"Error cerrando cliente Shopify: {e}")

        # Finalizar métricas
        if settings.METRICS_ENABLED:
            try:
                from app.core.metrics import finalize_metrics

                await finalize_metrics()
                logger.info("✅ Sistema de métricas finalizado")
            except Exception as e:
                logger.error(f"Error finalizando métricas: {e}")

    except Exception as e:
        logger.error(f"Error finalizando servicios: {e}")


async def shutdown_close_connections():
    """Cierra conexiones de manera limpia."""
    try:
        # Cerrar conexión RMS
        try:
            from app.db.connection import get_db_connection

            conn_db = get_db_connection()
            await conn_db.close()
            logger.info("✅ Conexión RMS cerrada")
        except Exception as e:
            logger.error(f"Error cerrando conexión RMS: {e}")

        # Cerrar cliente Redis
        if settings.REDIS_URL:
            try:
                from app.core import redis_client

                await redis_client.close_redis()
                logger.info("✅ Cliente Redis cerrado")
            except Exception as e:
                logger.error(f"Error cerrando Redis: {e}")

    except Exception as e:
        logger.error(f"Error cerrando conexiones: {e}")


async def shutdown_cleanup_resources():
    """Limpia recursos y archivos temporales."""
    try:
        # Limpiar archivos temporales
        import os
        import tempfile

        temp_dir = tempfile.gettempdir()
        app_temp_files = [f for f in os.listdir(temp_dir) if f.startswith("rms_shopify_")]

        for temp_file in app_temp_files:
            try:
                os.remove(os.path.join(temp_dir, temp_file))
            except Exception:
                pass  # Ignorar errores de archivos temporales

        if app_temp_files:
            logger.info(f"✅ {len(app_temp_files)} archivos temporales limpiados")

        # Limpiar caché en memoria
        await cleanup_memory_cache()

    except Exception as e:
        logger.error(f"Error limpiando recursos: {e}")


async def shutdown_finalize_logging():
    """Finaliza el sistema de logging."""
    try:
        # Flush de todos los handlers
        for handler in logger.handlers:
            handler.flush()

        # Cerrar handlers de archivo
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "close"):
                handler.close()

        logger.info("✅ Sistema de logging finalizado")

    except Exception as e:
        print(f"Error finalizando logging: {e}")


# === FUNCIONES AUXILIARES ===


async def finalize_pending_jobs():
    """Finaliza trabajos pendientes de manera ordenada."""
    try:
        # Esperar a que terminen trabajos de sincronización activos
        from app.services.sync_manager import wait_for_active_syncs

        await asyncio.wait_for(wait_for_active_syncs(), timeout=30)
        logger.info("✅ Trabajos de sincronización finalizados")

    except asyncio.TimeoutError:
        logger.warning("⚠️ Timeout esperando finalización de trabajos")
    except ImportError:
        logger.debug("Sync manager no disponible")
    except Exception as e:
        logger.error(f"Error finalizando trabajos: {e}")


async def cleanup_memory_cache():
    """Limpia cachés en memoria."""
    try:
        # Limpiar caché de productos si existe
        from app.core.cache_manager import clear_all_cache

        await clear_all_cache()
        logger.info("✅ Caché en memoria limpiado")

    except ImportError:
        logger.debug("Cache manager no disponible")
    except Exception as e:
        logger.error(f"Error limpiando caché: {e}")


def get_startup_info() -> Dict[str, Any]:
    """
    Obtiene información sobre el estado del startup.

    Returns:
        Dict: Información del startup
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "features": {
            "scheduled_sync": settings.ENABLE_SCHEDULED_SYNC,
            "rate_limiting": settings.ENABLE_RATE_LIMITING,
            "metrics": settings.METRICS_ENABLED,
            "alerts": settings.ALERT_EMAIL_ENABLED,
        },
        "services": {
            "redis_enabled": bool(settings.REDIS_URL),
            "rms_configured": bool(settings.RMS_DB_HOST),
            "shopify_configured": bool(settings.SHOPIFY_SHOP_URL),
        },
    }
