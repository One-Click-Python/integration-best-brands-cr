"""
Endpoints para control y monitoreo del sistema de order polling.

Este módulo proporciona APIs para controlar y monitorear el servicio de polling
de órdenes de Shopify como alternativa/complemento a webhooks.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Crear router
router = APIRouter()


class OrderPollingTriggerRequest(BaseModel):
    """Modelo para trigger manual de order polling."""

    lookback_minutes: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="Minutos para buscar órdenes (default: config)",
    )
    batch_size: int | None = Field(
        None,
        ge=1,
        le=250,
        description="Órdenes por página (max 250, default: config)",
    )
    max_pages: int | None = Field(
        None,
        ge=1,
        le=50,
        description="Máximo de páginas a consultar (default: config)",
    )
    dry_run: bool = Field(
        False,
        description="Si True, solo simula sin sincronizar",
    )


class OrderPollingConfigUpdate(BaseModel):
    """Modelo para actualizar configuración de polling."""

    interval_minutes: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="Intervalo entre polls (1-1440 minutos)",
    )
    lookback_minutes: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="Ventana de búsqueda (1-1440 minutos)",
    )
    batch_size: int | None = Field(
        None,
        ge=1,
        le=250,
        description="Órdenes por página (1-250)",
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_order_polling_status() -> dict[str, Any]:
    """
    Obtiene el estado actual del sistema de order polling.

    Returns:
        Dict con estado completo del polling service

    Example:
        ```json
        {
            "status": "success",
            "data": {
                "enabled": true,
                "interval_minutes": 10,
                "lookback_minutes": 15,
                "batch_size": 50,
                "last_poll_time": "2025-01-23T15:30:00+00:00",
                "polling_service_initialized": true,
                "will_execute_next_cycle": false,
                "seconds_until_next_poll": 420,
                "webhooks_enabled": true,
                "status": "waiting_for_interval",
                "statistics": {
                    "total_polled": 1247,
                    "already_synced": 1100,
                    "newly_synced": 145,
                    "sync_errors": 2,
                    "last_poll_time": "2025-01-23T15:30:00+00:00"
                }
            }
        }
        ```
    """
    try:
        from app.core.scheduler import get_scheduler_status

        scheduler_status = get_scheduler_status()
        polling_info = scheduler_status.get("order_polling", {})

        return {
            "status": "success",
            "data": polling_info,
            "message": "Order polling status retrieved successfully",
        }

    except Exception as e:
        logger.error(f"Error obteniendo estado de order polling: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting order polling status: {str(e)}",
        ) from e


@router.post("/trigger", status_code=status.HTTP_200_OK)
async def trigger_order_polling(
    request: OrderPollingTriggerRequest | None = None,
) -> dict[str, Any]:
    """
    Trigger manual de order polling.

    Args:
        request: Parámetros opcionales para el polling

    Returns:
        Dict con resultado del polling

    Example Request:
        ```json
        {
            "lookback_minutes": 30,
            "batch_size": 50,
            "max_pages": 10,
            "dry_run": false
        }
        ```

    Example Response:
        ```json
        {
            "status": "success",
            "data": {
                "status": "success",
                "timestamp": "2025-01-23T15:35:00+00:00",
                "duration_seconds": 12.45,
                "message": "Polling complete: 25/28 orders synced",
                "statistics": {
                    "total_polled": 28,
                    "already_synced": 3,
                    "newly_synced": 25,
                    "sync_errors": 0,
                    "success_rate": 100.0
                }
            }
        }
        ```
    """
    try:
        from app.services.order_polling_service import get_polling_service

        # Obtener polling service
        polling_service = await get_polling_service()

        # Preparar parámetros
        params = request.dict() if request else {}

        # Ejecutar polling
        result = await polling_service.poll_and_sync(
            lookback_minutes=params.get("lookback_minutes"),
            batch_size=params.get("batch_size", settings.ORDER_POLLING_BATCH_SIZE),
            max_pages=params.get("max_pages", settings.ORDER_POLLING_MAX_PAGES),
            dry_run=params.get("dry_run", False),
        )

        return {
            "status": "success",
            "data": result,
            "message": "Order polling executed successfully",
        }

    except Exception as e:
        logger.error(f"Error ejecutando order polling: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing order polling: {str(e)}",
        ) from e


@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_order_polling_stats() -> dict[str, Any]:
    """
    Obtiene estadísticas detalladas del polling service.

    Returns:
        Dict con estadísticas acumuladas

    Example Response:
        ```json
        {
            "status": "success",
            "data": {
                "total_polled": 1247,
                "already_synced": 1100,
                "newly_synced": 145,
                "sync_errors": 2,
                "last_poll_time": "2025-01-23T15:30:00+00:00",
                "error_aggregator": {
                    "total_errors": 2,
                    "error_types": {
                        "NetworkError": 1,
                        "ValidationError": 1
                    }
                }
            }
        }
        ```
    """
    try:
        from app.services.order_polling_service import get_polling_service

        # Obtener polling service
        polling_service = await get_polling_service()

        # Obtener estadísticas
        stats = polling_service.get_statistics()

        return {
            "status": "success",
            "data": stats,
            "message": "Order polling statistics retrieved successfully",
        }

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de polling: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting polling statistics: {str(e)}",
        ) from e


@router.post("/reset-stats", status_code=status.HTTP_200_OK)
async def reset_order_polling_stats() -> dict[str, Any]:
    """
    Reinicia las estadísticas acumuladas del polling service.

    Returns:
        Dict con confirmación

    Example Response:
        ```json
        {
            "status": "success",
            "message": "Order polling statistics reset successfully"
        }
        ```
    """
    try:
        from app.services.order_polling_service import get_polling_service

        # Obtener polling service
        polling_service = await get_polling_service()

        # Reiniciar estadísticas
        polling_service.reset_statistics()

        return {
            "status": "success",
            "message": "Order polling statistics reset successfully",
        }

    except Exception as e:
        logger.error(f"Error reiniciando estadísticas de polling: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting polling statistics: {str(e)}",
        ) from e


@router.put("/config", status_code=status.HTTP_200_OK)
async def update_order_polling_config(
    config: OrderPollingConfigUpdate,
) -> dict[str, Any]:
    """
    Actualiza la configuración de order polling.

    Args:
        config: Nueva configuración

    Returns:
        Dict con configuración actualizada

    Example Request:
        ```json
        {
            "interval_minutes": 15,
            "lookback_minutes": 20,
            "batch_size": 75
        }
        ```

    Example Response:
        ```json
        {
            "status": "success",
            "data": {
                "interval_minutes": 15,
                "lookback_minutes": 20,
                "batch_size": 75
            },
            "message": "Order polling configuration updated successfully"
        }
        ```

    Note:
        Esta configuración se aplica en runtime pero NO persiste entre restarts.
        Para cambios permanentes, actualizar variables de entorno (.env).
    """
    try:
        updated_fields = {}

        # Actualizar interval_minutes (esto afecta el scheduler)
        if config.interval_minutes is not None:
            settings.ORDER_POLLING_INTERVAL_MINUTES = config.interval_minutes
            updated_fields["interval_minutes"] = config.interval_minutes

        # Actualizar lookback_minutes
        if config.lookback_minutes is not None:
            settings.ORDER_POLLING_LOOKBACK_MINUTES = config.lookback_minutes
            updated_fields["lookback_minutes"] = config.lookback_minutes

        # Actualizar batch_size
        if config.batch_size is not None:
            settings.ORDER_POLLING_BATCH_SIZE = config.batch_size
            updated_fields["batch_size"] = config.batch_size

        if not updated_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No configuration fields provided to update",
            )

        logger.info(f"Order polling config updated: {updated_fields}")

        return {
            "status": "success",
            "data": updated_fields,
            "message": "Order polling configuration updated successfully (runtime only)",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando configuración de polling: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating polling configuration: {str(e)}",
        ) from e


@router.get("/health", status_code=status.HTTP_200_OK)
async def get_order_polling_health() -> dict[str, Any]:
    """
    Health check específico para order polling.

    Returns:
        Dict con estado de salud

    Example Response:
        ```json
        {
            "status": "healthy",
            "enabled": true,
            "polling_service_initialized": true,
            "shopify_api_reachable": true,
            "rms_db_reachable": true,
            "redis_reachable": true,
            "last_poll_success": true,
            "last_poll_time": "2025-01-23T15:30:00+00:00"
        }
        ```
    """
    try:
        from app.core.scheduler import get_scheduler_status

        scheduler_status = get_scheduler_status()
        polling_info = scheduler_status.get("order_polling", {})

        # Determinar estado de salud
        is_healthy = settings.ENABLE_ORDER_POLLING and polling_info.get("polling_service_initialized", False)

        health_status = {
            "status": "healthy" if is_healthy else "unhealthy",
            "enabled": settings.ENABLE_ORDER_POLLING,
            "polling_service_initialized": polling_info.get("polling_service_initialized", False),
            "last_poll_time": polling_info.get("last_poll_time"),
            "webhooks_enabled": settings.ENABLE_WEBHOOKS,
            "configuration": {
                "interval_minutes": settings.ORDER_POLLING_INTERVAL_MINUTES,
                "lookback_minutes": settings.ORDER_POLLING_LOOKBACK_MINUTES,
                "batch_size": settings.ORDER_POLLING_BATCH_SIZE,
                "max_pages": settings.ORDER_POLLING_MAX_PAGES,
            },
        }

        return health_status

    except Exception as e:
        logger.error(f"Error en health check de polling: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "enabled": settings.ENABLE_ORDER_POLLING,
        }
