"""
Metrics and monitoring endpoints.

This module provides endpoints for collecting and viewing system metrics,
performance data, and monitoring information.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.config import get_settings

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


class SystemMetrics(BaseModel):
    """Model for system metrics response."""

    uptime_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    request_count: int
    error_count: int


async def verify_metrics_access():
    """
    Verify access to metrics endpoints.
    In production, this would check API keys or authentication.
    """
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=403, detail="Metrics collection is disabled")


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
        # Try to get metrics from the metrics module
        try:
            from app.core.metrics import get_metrics_summary

            metrics_data = get_metrics_summary()
        except ImportError:
            # Fallback if metrics module not available
            metrics_data = {
                "collection_status": "disabled",
                "data_points": {"sync_operations": 0, "api_requests": 0, "errors": 0},
                "sync_metrics": {"total_operations": 0, "avg_duration": 0, "avg_success_rate": 0},
                "api_metrics": {"total_requests": 0, "avg_duration_ms": 0, "success_rate": 0},
                "error_metrics": {"total_errors": 0, "error_types": []},
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


@router.get(
    "/system",
    response_model=SystemMetrics,
    summary="Get system metrics",
    description="Get current system performance metrics",
)
async def get_system_metrics(_: None = Depends(verify_metrics_access)):
    """
    Get current system metrics.

    Returns:
        SystemMetrics: Current system performance data
    """
    try:
        import time

        import psutil

        # Get system metrics
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)

        # Calculate uptime (simplified)
        uptime = time.time() - psutil.boot_time()

        return SystemMetrics(
            uptime_seconds=uptime,
            memory_usage_mb=memory.used / (1024 * 1024),
            cpu_usage_percent=cpu_percent,
            active_connections=len(psutil.net_connections()),
            request_count=0,  # TODO: Implement request counting
            error_count=0,  # TODO: Implement error counting
        )

    except ImportError:
        # Fallback if psutil not available
        return SystemMetrics(
            uptime_seconds=0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            active_connections=0,
            request_count=0,
            error_count=0,
        )
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics") from e


@router.get(
    "/sync-operations", summary="Get sync operation metrics", description="Get detailed metrics for sync operations"
)
async def get_sync_metrics(
    limit: int = Query(default=50, ge=1, le=1000),
    sync_type: str = Query(default=None),
    _: None = Depends(verify_metrics_access),
):
    """
    Get sync operation metrics.

    Args:
        limit: Maximum number of records to return
        sync_type: Filter by sync type

    Returns:
        Dict: Sync operation metrics
    """
    try:
        # TODO: Implement actual sync metrics retrieval
        # For now, return placeholder data

        return {
            "sync_operations": [],
            "summary": {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "average_duration": 0,
                "success_rate": 0,
            },
            "filters": {
                "limit": limit,
                "sync_type": sync_type,
            },
        }

    except Exception as e:
        logger.error(f"Error getting sync metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync metrics") from e


@router.get(
    "/api-requests", summary="Get API request metrics", description="Get metrics for API requests to external services"
)
async def get_api_metrics(
    service: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    _: None = Depends(verify_metrics_access),
):
    """
    Get API request metrics.

    Args:
        service: Filter by service (shopify, rms)
        limit: Maximum number of records to return

    Returns:
        Dict: API request metrics
    """
    try:
        # TODO: Implement actual API metrics retrieval
        # For now, return placeholder data

        return {
            "api_requests": [],
            "summary": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "average_response_time": 0,
                "success_rate": 0,
            },
            "filters": {
                "service": service,
                "limit": limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting API metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve API metrics") from e


@router.post("/clear", summary="Clear metrics data", description="Clear all collected metrics data (admin only)")
async def clear_metrics(_: None = Depends(verify_metrics_access)):
    """
    Clear all collected metrics data.

    Returns:
        Dict: Confirmation of cleared data
    """
    try:
        # Try to clear metrics if module available
        try:
            from app.core.metrics import clear_metrics

            clear_metrics()

            return {
                "success": True,
                "message": "Metrics data cleared successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except ImportError:
            return {
                "success": False,
                "message": "Metrics module not available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Error clearing metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear metrics data") from e


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
            "collection_active": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Check if metrics module is available
        try:
            from app.core.metrics import get_metrics_summary

            metrics_data = get_metrics_summary()
            health_status["collection_active"] = metrics_data.get("collection_status") == "active"
        except ImportError:
            health_status["collection_active"] = False

        return health_status

    except Exception as e:
        logger.error(f"Error checking metrics health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

