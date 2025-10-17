"""
Configuración centralizada de routers para la aplicación FastAPI.

Este módulo se encarga de registrar todos los routers de la API,
configurar endpoints base y organizar las rutas de manera estructurada.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Importar routers de la API
from app.api.v1.endpoints.collections import router as collections_router
from app.api.v1.endpoints.sync import router as sync_router
from app.api.v1.endpoints.sync_monitor import router as sync_monitor_router
from app.api.v1.endpoints.webhooks import router as webhooks_router
from app.core.config import get_settings
from app.core.health import get_health_status, get_health_status_fast

settings = get_settings()
logger = logging.getLogger(__name__)


def create_root_endpoints(app: FastAPI) -> None:
    """
    Crea endpoints raíz de la aplicación.

    Args:
        app: Instancia de FastAPI
    """

    @app.get("/", tags=["Root"], summary="API Info")
    async def root():
        """
        Endpoint raíz que proporciona información básica de la API.

        Returns:
            Dict con información de la API
        """
        return {
            "message": "RMS-Shopify Integration API",
            "description": "Sistema de integración bidireccional entre RMS y Shopify",
            "version": settings.APP_VERSION,
            "status": "running",
            "documentation": "/docs" if settings.DEBUG else "disabled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoints": {
                "health": "/health",
                "api_v1": "/api/v1",
                "sync": "/api/v1/sync",
                "sync_monitor": "/api/v1/sync/monitor",
                "webhooks": "/api/v1/webhooks",
                "collections": "/api/v1/collections",
            },
        }

    @app.get("/ping", tags=["Root"], summary="Simple Ping")
    async def ping():
        """
        Endpoint simple para verificar que la API responde.

        Returns:
            Dict con pong y timestamp
        """
        return {"message": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}


def create_health_endpoints(app: FastAPI) -> None:
    """
    Crea endpoints de health check y monitoreo.

    Args:
        app: Instancia de FastAPI
    """

    @app.get("/health", tags=["Health"], summary="Health Check (Fast)")
    async def health_check():
        """
        Endpoint de health check rápido para uso general.
        Usa cache y verifica solo servicios críticos básicos.

        Returns:
            Dict con estado de salud rápido
        """
        try:
            health_status = await get_health_status_fast()

            status_code = 200 if health_status["overall"] else 503

            return JSONResponse(
                status_code=status_code,
                content={
                    "status": "healthy" if health_status["overall"] else "unhealthy",
                    "version": settings.APP_VERSION,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "uptime": health_status.get("uptime"),
                    "services": health_status["services"],
                    "environment": settings.ENVIRONMENT,
                    "debug": settings.DEBUG,
                    "cache_info": health_status.get("cache_info", "unknown"),
                },
            )

        except Exception as e:
            logger.error(f"Error en health check: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": settings.APP_VERSION,
                },
            )

    @app.get("/health/complete", tags=["Health"], summary="Complete Health Check")
    async def complete_health_check():
        """
        Endpoint de health check completo para monitoreo profundo.
        Verifica el estado de TODOS los servicios (puede ser lento).

        Returns:
            Dict con estado de salud completo
        """
        try:
            health_status = await get_health_status()

            status_code = 200 if health_status["overall"] else 503

            return JSONResponse(
                status_code=status_code,
                content={
                    "status": "healthy" if health_status["overall"] else "unhealthy",
                    "version": settings.APP_VERSION,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "uptime": health_status.get("uptime"),
                    "services": health_status["services"],
                    "system": health_status.get("system"),
                    "environment": settings.ENVIRONMENT,
                    "debug": settings.DEBUG,
                    "check_type": "complete",
                },
            )

        except Exception as e:
            logger.error(f"Error en complete health check: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": settings.APP_VERSION,
                    "check_type": "complete",
                },
            )

    @app.get("/health/liveness", tags=["Health"], summary="Liveness Probe")
    async def liveness_probe():
        """
        Endpoint para liveness probe de Kubernetes.
        Verifica que la aplicación esté ejecutándose.

        Returns:
            Dict simple con estado
        """
        return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

    @app.get("/health/readiness", tags=["Health"], summary="Readiness Probe")
    async def readiness_probe():
        """
        Endpoint para readiness probe de Kubernetes.
        Verifica que la aplicación esté lista para recibir tráfico.

        Returns:
            Dict con estado de preparación
        """
        try:
            # Verificar dependencias críticas
            health_status = await get_health_status()

            # Servicios críticos para estar "ready"
            critical_services = ["rms", "shopify"]
            ready = all(
                health_status["services"].get(service, {}).get("status") == "healthy" for service in critical_services
            )

            status_code = 200 if ready else 503

            return JSONResponse(
                status_code=status_code,
                content={
                    "status": "ready" if ready else "not_ready",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "critical_services": {
                        service: health_status["services"].get(service, {}).get("status", "unknown")
                        for service in critical_services
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error en readiness probe: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )


def create_info_endpoints(app: FastAPI) -> None:
    """
    Crea endpoints informativos adicionales.

    Args:
        app: Instancia de FastAPI
    """

    @app.get("/version", tags=["Info"], summary="Version Info")
    async def version_info():
        """
        Endpoint que retorna información de versión.

        Returns:
            Dict con información de versión
        """
        return {
            "version": settings.APP_VERSION,
            "name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/config", tags=["Info"], summary="Configuration Info")
    async def config_info():
        """
        Endpoint que retorna configuración (solo en modo debug).

        Returns:
            Dict con configuración (sanitizada)
        """
        if not settings.DEBUG:
            return JSONResponse(
                status_code=404,
                content={"message": "Config endpoint only available in debug mode"},
            )

        # Configuración sanitizada (sin secretos)
        safe_config = {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "host": settings.HOST,
            "port": settings.PORT,
            "log_level": settings.LOG_LEVEL,
            "rate_limiting_enabled": settings.ENABLE_RATE_LIMITING,
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "scheduled_sync_enabled": settings.ENABLE_SCHEDULED_SYNC,
            "sync_interval_minutes": settings.SYNC_INTERVAL_MINUTES,
            "shopify_api_version": settings.SHOPIFY_API_VERSION,
            "max_retries": settings.MAX_RETRIES,
            "slow_request_threshold": settings.SLOW_REQUEST_THRESHOLD,
        }

        return {"config": safe_config, "timestamp": datetime.now(timezone.utc).isoformat()}


def configure_api_v1_routers(app: FastAPI) -> None:
    """
    Configura todos los routers de la API v1.

    Args:
        app: Instancia de FastAPI
    """
    logger.info("🔧 Configurando routers de API v1...")

    # Router principal de sincronización
    app.include_router(
        sync_router,
        prefix="/api/v1/sync",
        tags=["Synchronization"],
        responses={
            404: {"description": "Endpoint not found"},
            500: {"description": "Internal server error"},
        },
    )
    logger.info("✅ Router de sincronización configurado")

    # Router de monitoreo de sincronización automática
    app.include_router(
        sync_monitor_router,
        prefix="/api/v1/sync/monitor",
        tags=["Sync Monitoring"],
        responses={
            404: {"description": "Monitoring endpoint not found"},
            500: {"description": "Monitoring error"},
        },
    )
    logger.info("✅ Router de monitoreo de sincronización configurado")

    # Router de webhooks
    app.include_router(
        webhooks_router,
        prefix="/api/v1/webhooks",
        tags=["Webhooks"],
        responses={
            404: {"description": "Webhook endpoint not found"},
            422: {"description": "Invalid webhook payload"},
            500: {"description": "Webhook processing error"},
        },
    )
    logger.info("✅ Router de webhooks configurado")

    # Router de collections
    app.include_router(
        collections_router,
        prefix="/api/v1",
        tags=["Collections"],
        responses={
            404: {"description": "Collection endpoint not found"},
            500: {"description": "Collection operation error"},
        },
    )
    logger.info("✅ Router de collections configurado")


def configure_optional_routers(app: FastAPI) -> None:
    """
    Configura routers opcionales basados en la configuración.

    Args:
        app: Instancia de FastAPI
    """

    # Router de métricas (si está habilitado)
    if settings.METRICS_ENABLED:
        try:
            from app.api.v1.endpoints.metrics import router as metrics_router

            app.include_router(
                metrics_router,
                prefix="/api/v1/metrics",
                tags=["Metrics"],
                responses={403: {"description": "Metrics access forbidden"}},
            )
            logger.info("✅ Router de métricas configurado")
        except ImportError:
            logger.warning("⚠️ Router de métricas no disponible")

    # Router de administración (solo en debug)
    if settings.DEBUG:
        try:
            from app.api.v1.endpoints.admin import router as admin_router

            app.include_router(
                admin_router,
                prefix="/api/v1/admin",
                tags=["Administration"],
                responses={403: {"description": "Admin access forbidden"}},
            )
            logger.info("✅ Router de administración configurado")
        except ImportError:
            logger.warning("⚠️ Router de administración no disponible")

    # Router de logs (solo en debug)
    if settings.DEBUG:
        try:
            from app.api.v1.endpoints.logs import router as logs_router

            app.include_router(
                logs_router,
                prefix="/api/v1/logs",
                tags=["Logs"],
                responses={403: {"description": "Logs access forbidden"}},
            )
            logger.info("✅ Router de logs configurado")
        except ImportError:
            logger.warning("⚠️ Router de logs no disponible")

    # Router de migración administrativa
    if settings.DEBUG or settings.ENVIRONMENT == "production":
        try:
            from app.api.v1.endpoints.admin_migration import router as migration_router

            app.include_router(
                migration_router,
                prefix="/api/v1",
                tags=["Migration"],
                responses={403: {"description": "Migration access forbidden"}},
            )
            logger.info("✅ Router de migración administrativa configurado")
        except ImportError:
            logger.warning("⚠️ Router de migración administrativa no disponible")


def configure_all_routers(app: FastAPI) -> None:
    """
    Configura todos los routers de la aplicación.

    Args:
        app: Instancia de FastAPI
    """
    logger.info("🔧 Configurando todos los routers...")

    # Endpoints base
    create_root_endpoints(app)
    create_health_endpoints(app)
    create_info_endpoints(app)

    # Routers principales de API v1
    configure_api_v1_routers(app)

    # Routers opcionales
    configure_optional_routers(app)

    logger.info("✅ Todos los routers configurados correctamente")


def get_router_info() -> Dict[str, Any]:
    """
    Obtiene información sobre los routers configurados.

    Returns:
        Dict con información de routers
    """
    return {
        "api_version": "v1",
        "base_paths": {
            "root": "/",
            "health": "/health",
            "sync": "/api/v1/sync",
            "sync_monitor": "/api/v1/sync/monitor",
            "webhooks": "/api/v1/webhooks",
            "collections": "/api/v1/collections",
            "metrics": "/api/v1/metrics" if settings.METRICS_ENABLED else None,
            "admin": "/api/v1/admin" if settings.DEBUG else None,
            "logs": "/api/v1/logs" if settings.DEBUG else None,
        },
        "features": {
            "metrics_enabled": settings.METRICS_ENABLED,
            "admin_enabled": settings.DEBUG,
            "logs_enabled": settings.DEBUG,
            "debug_mode": settings.DEBUG,
        },
    }
