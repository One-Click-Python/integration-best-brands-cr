"""
Endpoints para métricas y monitoreo del sistema.

Este módulo proporciona endpoints para obtener métricas operacionales,
estadísticas de rendimiento y estado del sistema de integración RMS-Shopify.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.bulk_operations import ShopifyBulkOperations
from app.services.inventory_manager import InventoryManager
from app.services.webhook_handler import WEBHOOK_PROCESSOR
from app.utils.retry_handler import get_all_metrics

settings = get_settings()
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


class MetricsSummary(BaseModel):
    """Model for metrics summary response."""

    collection_status: str
    timestamp: datetime
    data_points: Dict[str, int]
    sync_metrics: Dict[str, float]
    api_metrics: Dict[str, float]
    error_metrics: Dict[str, Any]


async def verify_metrics_access():
    """
    Verify access to metrics endpoints.
    In production, this would check API keys or authentication.
    """
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=403, detail="Metrics collection is disabled")


@router.get("/system", status_code=status.HTTP_200_OK)
async def get_system_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas generales del sistema.

    Returns:
        Dict: Métricas del sistema
    """
    try:
        # Obtener métricas de todos los componentes
        retry_metrics = get_all_metrics()
        webhook_metrics = WEBHOOK_PROCESSOR.get_metrics()

        # Métricas del sistema
        system_metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "status": "operational",
                "uptime_seconds": 0,  # Implementar si es necesario
                "version": "1.0.0",  # Obtener de settings
            },
            "retry_handlers": retry_metrics,
            "webhook_processor": webhook_metrics,
            "components": {
                "shopify_client": "operational",
                "rms_handler": "operational",
                "inventory_manager": "operational",
                "bulk_operations": "operational",
            },
        }

        return system_metrics

    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system metrics: {str(e)}") from e


@router.get("/retry", status_code=status.HTTP_200_OK)
async def get_retry_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas detalladas de los sistemas de reintentos.

    Returns:
        Dict: Métricas de reintentos
    """
    try:
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "retry_handlers": get_all_metrics()}
    except Exception as e:
        logger.error(f"Error getting retry metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve retry metrics: {str(e)}") from e


@router.get("/webhooks", status_code=status.HTTP_200_OK)
async def get_webhook_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas del procesador de webhooks.

    Returns:
        Dict: Métricas de webhooks
    """
    try:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "webhook_processor": WEBHOOK_PROCESSOR.get_metrics(),
        }
    except Exception as e:
        logger.error(f"Error getting webhook metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve webhook metrics: {str(e)}") from e


@router.get("/inventory", status_code=status.HTTP_200_OK)
async def get_inventory_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas del gestor de inventario.

    Returns:
        Dict: Métricas de inventario
    """
    try:
        inventory_manager = InventoryManager()
        await inventory_manager.initialize()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inventory_manager": inventory_manager.get_metrics(),
        }
    except Exception as e:
        logger.error(f"Error getting inventory metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve inventory metrics: {str(e)}") from e


@router.get("/bulk-operations", status_code=status.HTTP_200_OK)
async def get_bulk_operations_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas de operaciones bulk.

    Returns:
        Dict: Métricas de operaciones bulk
    """
    try:
        bulk_ops = ShopifyBulkOperations()

        return {"timestamp": datetime.now(timezone.utc).isoformat(), "bulk_operations": bulk_ops.get_metrics()}
    except Exception as e:
        logger.error(f"Error getting bulk operations metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve bulk operations metrics: {str(e)}") from e


@router.get("/performance", status_code=status.HTTP_200_OK)
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas de rendimiento del sistema.

    Returns:
        Dict: Métricas de rendimiento
    """
    try:
        import psutil

        # Métricas del sistema
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        performance_metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100,
                },
            },
            "python": {"version": sys.version, "executable": sys.executable, "platform": sys.platform},
        }

        return performance_metrics

    except ImportError:
        # psutil no está disponible
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": "psutil not available for system metrics",
            "python": {"version": sys.version, "executable": sys.executable, "platform": sys.platform},
        }
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve performance metrics: {str(e)}") from e


@router.get("/health-detailed", status_code=status.HTTP_200_OK)
async def get_detailed_health() -> Dict[str, Any]:
    """
    Obtiene estado detallado de salud del sistema.

    Returns:
        Dict: Estado detallado de todos los componentes
    """
    try:
        from app.db.rms_handler import RMSHandler
        from app.db.shopify_graphql_client import ShopifyGraphQLClient

        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "components": {},
        }

        # Test Shopify connection
        try:
            shopify_client = ShopifyGraphQLClient()
            await shopify_client.initialize()
            shopify_healthy = await shopify_client.test_connection()
            await shopify_client.close()

            health_status["components"]["shopify"] = {
                "status": "healthy" if shopify_healthy else "unhealthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Connection test successful" if shopify_healthy else "Connection test failed",
            }
        except Exception as e:
            health_status["components"]["shopify"] = {
                "status": "unhealthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

        # Test RMS connection
        try:
            rms_handler = RMSHandler()
            await rms_handler.initialize()
            rms_healthy = await rms_handler.test_connection()  # type: ignore
            await rms_handler.close()

            health_status["components"]["rms"] = {
                "status": "healthy" if rms_healthy else "unhealthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Connection test successful" if rms_healthy else "Connection test failed",
            }
        except Exception as e:
            health_status["components"]["rms"] = {
                "status": "unhealthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

        # Test Inventory Manager
        try:
            inventory_manager = InventoryManager()
            await inventory_manager.initialize()
            locations = await inventory_manager.get_locations()

            health_status["components"]["inventory_manager"] = {
                "status": "healthy" if locations else "degraded",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": f"Loaded {len(locations)} locations",
            }
        except Exception as e:
            health_status["components"]["inventory_manager"] = {
                "status": "unhealthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

        # Determinar estado general
        component_statuses = [comp["status"] for comp in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["overall_status"] = "unhealthy"
        elif "degraded" in component_statuses:
            health_status["overall_status"] = "degraded"

        return health_status

    except Exception as e:
        logger.error(f"Error getting detailed health: {e}")
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "overall_status": "unhealthy", "error": str(e)}


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_metrics() -> Dict[str, Any]:
    """
    Reinicia todas las métricas del sistema.

    Returns:
        Dict: Confirmación de reset
    """
    try:
        # Reset retry metrics
        from app.utils.retry_handler import RMS_RETRY_HANDLER, SHOPIFY_RETRY_HANDLER, SYNC_RETRY_HANDLER

        SHOPIFY_RETRY_HANDLER.reset_metrics()
        RMS_RETRY_HANDLER.reset_metrics()
        SYNC_RETRY_HANDLER.reset_metrics()

        # Reset webhook metrics
        WEBHOOK_PROCESSOR.error_aggregator = type(WEBHOOK_PROCESSOR.error_aggregator)()
        WEBHOOK_PROCESSOR.processed_webhooks.clear()

        logger.info("All metrics have been reset")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "message": "All metrics have been reset",
            "reset_components": ["retry_handlers", "webhook_processor", "error_aggregators"],
        }

    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}") from e


@router.post("/reset-circuit-breakers", status_code=status.HTTP_200_OK)
async def reset_circuit_breakers() -> Dict[str, Any]:
    """
    Reinicia todos los circuit breakers del sistema.

    Returns:
        Dict: Estado de los circuit breakers después del reset
    """
    try:
        from app.utils.retry_handler import RMS_RETRY_HANDLER, SHOPIFY_RETRY_HANDLER, CircuitState

        # Reset Shopify circuit breaker
        if SHOPIFY_RETRY_HANDLER.circuit_breaker:
            SHOPIFY_RETRY_HANDLER.circuit_breaker.state = CircuitState.CLOSED
            SHOPIFY_RETRY_HANDLER.circuit_breaker.failure_count = 0
            SHOPIFY_RETRY_HANDLER.circuit_breaker.success_count = 0
            SHOPIFY_RETRY_HANDLER.circuit_breaker.last_failure_time = None
            SHOPIFY_RETRY_HANDLER.circuit_breaker.last_success_time = None

        # Reset RMS circuit breaker
        if RMS_RETRY_HANDLER.circuit_breaker:
            RMS_RETRY_HANDLER.circuit_breaker.state = CircuitState.CLOSED
            RMS_RETRY_HANDLER.circuit_breaker.failure_count = 0
            RMS_RETRY_HANDLER.circuit_breaker.success_count = 0
            RMS_RETRY_HANDLER.circuit_breaker.last_failure_time = None
            RMS_RETRY_HANDLER.circuit_breaker.last_success_time = None

        logger.info("All circuit breakers have been reset to CLOSED state")

        # Get current state after reset
        circuit_states = {}
        if SHOPIFY_RETRY_HANDLER.circuit_breaker:
            circuit_states["shopify"] = SHOPIFY_RETRY_HANDLER.circuit_breaker.get_state_info()
        if RMS_RETRY_HANDLER.circuit_breaker:
            circuit_states["rms"] = RMS_RETRY_HANDLER.circuit_breaker.get_state_info()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "message": "All circuit breakers have been reset to CLOSED state",
            "circuit_breaker_states": circuit_states,
        }

    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset circuit breakers: {str(e)}") from e


@router.get("/dashboard", status_code=status.HTTP_200_OK)
async def get_dashboard_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas resumidas para dashboard.

    Returns:
        Dict: Métricas para dashboard
    """
    try:
        # Obtener métricas básicas de forma eficiente
        retry_metrics = get_all_metrics()
        webhook_metrics = WEBHOOK_PROCESSOR.get_metrics()

        # Calcular resumen
        total_operations = sum(handler.get("total_attempts", 0) for handler in retry_metrics.values())

        total_successes = sum(handler.get("total_successes", 0) for handler in retry_metrics.values())

        overall_success_rate = (total_successes / total_operations * 100) if total_operations > 0 else 100

        dashboard = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "overall_success_rate": round(overall_success_rate, 2),
                "total_operations": total_operations,
                "total_successes": total_successes,
                "webhook_cache_size": webhook_metrics.get("processed_webhooks_cache_size", 0),
                "system_status": "operational",
            },
            "services": {
                "shopify": {
                    "success_rate": retry_metrics.get("shopify", {}).get("success_rate", 0),
                    "total_attempts": retry_metrics.get("shopify", {}).get("total_attempts", 0),
                    "circuit_breaker_state": retry_metrics.get("shopify", {})
                    .get("circuit_breaker", {})
                    .get("state", "unknown"),
                },
                "rms": {
                    "success_rate": retry_metrics.get("rms", {}).get("success_rate", 0),
                    "total_attempts": retry_metrics.get("rms", {}).get("total_attempts", 0),
                    "circuit_breaker_state": retry_metrics.get("rms", {})
                    .get("circuit_breaker", {})
                    .get("state", "unknown"),
                },
            },
            "recent_activity": {
                "webhook_errors": webhook_metrics.get("error_summary", {}).get("error_count", 0),
                "last_update": datetime.now(timezone.utc).isoformat(),
            },
        }

        return dashboard

    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard metrics: {str(e)}") from e


# Legacy endpoints for backward compatibility


@router.get(
    "/summary",
    response_model=MetricsSummary,
    summary="Get metrics summary",
    description="Get a summary of collected metrics and performance data",
)
async def get_metrics_summary(_: None = Depends(verify_metrics_access)):
    """
    Get a summary of all collected metrics.

    Returns:
        MetricsSummary: Summary of metrics data
    """
    try:
        # Get metrics from new system
        retry_metrics = get_all_metrics()
        webhook_metrics = WEBHOOK_PROCESSOR.get_metrics()

        # Calculate aggregated data
        total_operations = sum(handler.get("total_attempts", 0) for handler in retry_metrics.values())

        total_successes = sum(handler.get("total_successes", 0) for handler in retry_metrics.values())

        success_rate = (total_successes / total_operations * 100) if total_operations > 0 else 100

        metrics_data = {
            "collection_status": "active",
            "data_points": {
                "sync_operations": total_operations,
                "api_requests": total_operations,
                "errors": webhook_metrics.get("error_summary", {}).get("error_count", 0),
            },
            "sync_metrics": {
                "total_operations": total_operations,
                "avg_duration": retry_metrics.get("shopify", {}).get("avg_duration", 0),
                "avg_success_rate": success_rate,
            },
            "api_metrics": {
                "total_requests": total_operations,
                "avg_duration_ms": retry_metrics.get("shopify", {}).get("avg_duration", 0) * 1000,
                "success_rate": success_rate,
            },
            "error_metrics": {
                "total_errors": webhook_metrics.get("error_summary", {}).get("error_count", 0),
                "error_types": [],
            },
        }

        return MetricsSummary(
            collection_status=metrics_data.get("collection_status", "unknown"),
            timestamp=datetime.now(timezone.utc),
            data_points=metrics_data.get("data_points", {}),
            sync_metrics=metrics_data.get("sync_metrics", {}),
            api_metrics=metrics_data.get("api_metrics", {}),
            error_metrics=metrics_data.get("error_metrics", {}),
        )

    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics summary") from e


@router.get("/health", summary="Metrics system health", description="Check the health of the metrics collection system")
async def metrics_health():
    """
    Check metrics system health.

    Returns:
        Dict: Health status of metrics system
    """
    try:
        health_status = {
            "status": "healthy",
            "metrics_enabled": settings.METRICS_ENABLED,
            "collection_active": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return health_status

    except Exception as e:
        logger.error(f"Error checking metrics health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
