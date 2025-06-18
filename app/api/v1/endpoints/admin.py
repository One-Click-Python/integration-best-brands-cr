"""
Administrative endpoints for system management.

This module provides admin-only endpoints for system configuration,
maintenance operations, and troubleshooting.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


class SystemInfo(BaseModel):
    """Model for system information response."""

    app_name: str
    app_version: str
    environment: str
    debug_mode: bool
    uptime: str
    configuration: Dict[str, Any]


class CacheStats(BaseModel):
    """Model for cache statistics response."""

    status: str
    backend: str
    total_keys: int
    expired_keys: int
    memory_usage: Dict[str, Any]


class MaintenanceOperation(BaseModel):
    """Model for maintenance operation request."""

    operation: str
    parameters: Optional[Dict[str, Any]] = None
    force: bool = False


async def verify_admin_access():
    """
    Verify admin access.
    In production, this would check admin authentication/authorization.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Admin endpoints only available in debug mode")


@router.get(
    "/system-info",
    response_model=SystemInfo,
    summary="Get system information",
    description="Get detailed system information and configuration",
)
async def get_system_info(_: None = Depends(verify_admin_access)):
    """
    Get comprehensive system information.

    Returns:
        SystemInfo: System configuration and status
    """
    try:
        # Get startup info
        from app.core.lifespan import get_startup_info

        startup_info = get_startup_info()

        # Calculate uptime (simplified)
        import time

        try:
            import psutil

            uptime_seconds = time.time() - psutil.boot_time()
            uptime = f"{uptime_seconds / 3600:.1f} hours"
        except ImportError:
            uptime = "Unknown"

        return SystemInfo(
            app_name=startup_info["app_name"],
            app_version=startup_info["version"],
            environment=startup_info["environment"],
            debug_mode=startup_info["debug"],
            uptime=uptime,
            configuration={
                "features": startup_info["features"],
                "services": startup_info["services"],
                "settings": {
                    "sync_batch_size": settings.SYNC_BATCH_SIZE,
                    "rate_limiting": settings.ENABLE_RATE_LIMITING,
                    "redis_enabled": bool(settings.REDIS_URL),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system information") from e


@router.get(
    "/cache-stats",
    response_model=CacheStats,
    summary="Get cache statistics",
    description="Get detailed cache usage and performance statistics",
)
async def get_cache_stats(_: None = Depends(verify_admin_access)):
    """
    Get cache system statistics.

    Returns:
        CacheStats: Cache performance and usage data
    """
    try:
        # Try to get cache stats
        try:
            from app.core.cache_manager import get_cache_stats

            cache_data = await get_cache_stats()

            return CacheStats(
                status=cache_data.get("status", "unknown"),
                backend=cache_data.get("backend", "unknown"),
                total_keys=cache_data.get("memory_cache", {}).get("total_keys", 0),
                expired_keys=cache_data.get("memory_cache", {}).get("expired_keys", 0),
                memory_usage=cache_data.get("memory_cache", {}),
            )
        except ImportError:
            return CacheStats(
                status="not_available",
                backend="none",
                total_keys=0,
                expired_keys=0,
                memory_usage={},
            )

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache statistics") from e


@router.post(
    "/maintenance",
    summary="Execute maintenance operation",
    description="Execute various maintenance operations on the system",
)
async def execute_maintenance(operation: MaintenanceOperation, _: None = Depends(verify_admin_access)):
    """
    Execute maintenance operations.

    Args:
        operation: Maintenance operation details

    Returns:
        Dict: Operation result
    """
    try:
        operation_type = operation.operation.lower()
        result = {"operation": operation_type, "success": False, "message": "Unknown operation"}

        if operation_type == "clear_cache":
            try:
                from app.core.cache_manager import clear_all_cache

                await clear_all_cache()
                result = {"operation": operation_type, "success": True, "message": "Cache cleared successfully"}
            except ImportError:
                result["message"] = "Cache manager not available"

        elif operation_type == "cleanup_logs":
            # TODO: Implement log cleanup
            result = {"operation": operation_type, "success": True, "message": "Log cleanup not implemented yet"}

        elif operation_type == "restart_scheduler":
            try:
                from app.core.scheduler import start_scheduler, stop_scheduler

                await stop_scheduler()
                await start_scheduler()
                result = {"operation": operation_type, "success": True, "message": "Scheduler restarted successfully"}
            except ImportError:
                result["message"] = "Scheduler not available"

        elif operation_type == "health_check":
            try:
                from app.core.health import get_health_status

                health = await get_health_status()
                result = {
                    "operation": operation_type,
                    "success": True,
                    "message": "Health check completed",
                    "data": health,
                }
            except ImportError:
                result["message"] = "Health module not available"

        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result

    except Exception as e:
        logger.error(f"Error executing maintenance operation {operation.operation}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute maintenance operation: {str(e)}") from e


@router.get(
    "/active-syncs", summary="Get active sync operations", description="Get list of currently running sync operations"
)
async def get_active_syncs(_: None = Depends(verify_admin_access)):
    """
    Get currently active sync operations.

    Returns:
        Dict: List of active sync operations
    """
    try:
        # Try to get active syncs
        try:
            from app.services.sync_manager import get_active_syncs, get_sync_statistics

            active_syncs = get_active_syncs()
            sync_stats = get_sync_statistics()

            return {
                "active_syncs": active_syncs,
                "statistics": sync_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except ImportError:
            return {
                "active_syncs": [],
                "statistics": {"error": "Sync manager not available"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Error getting active syncs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active sync operations") from e


@router.post("/cancel-sync/{sync_id}", summary="Cancel sync operation", description="Cancel a specific sync operation")
async def cancel_sync_operation(sync_id: str, _: None = Depends(verify_admin_access)):
    """
    Cancel a specific sync operation.

    Args:
        sync_id: ID of the sync operation to cancel

    Returns:
        Dict: Cancellation result
    """
    try:
        # Try to cancel sync
        try:
            from app.services.sync_manager import cancel_sync

            success = await cancel_sync(sync_id, "Admin cancellation")

            return {
                "sync_id": sync_id,
                "cancelled": success,
                "message": "Sync cancelled successfully" if success else "Sync not found or already completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except ImportError:
            return {
                "sync_id": sync_id,
                "cancelled": False,
                "message": "Sync manager not available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Error cancelling sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel sync operation: {str(e)}") from e


@router.get(
    "/configuration", summary="Get system configuration", description="Get current system configuration settings"
)
async def get_configuration(include_sensitive: bool = Query(default=False), _: None = Depends(verify_admin_access)):
    """
    Get system configuration.

    Args:
        include_sensitive: Whether to include sensitive settings (masked)

    Returns:
        Dict: System configuration
    """
    try:
        config = {
            "general": {
                "app_name": settings.APP_NAME,
                "app_version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "debug": settings.DEBUG,
            },
            "features": {
                "scheduled_sync": settings.ENABLE_SCHEDULED_SYNC,
                "rate_limiting": settings.ENABLE_RATE_LIMITING,
                "metrics": settings.METRICS_ENABLED,
                "alerts": settings.ALERT_EMAIL_ENABLED,
            },
            "sync": {
                "batch_size": settings.SYNC_BATCH_SIZE,
                "slow_request_threshold": settings.SLOW_REQUEST_THRESHOLD,
                "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            },
        }

        if include_sensitive:
            config["connections"] = {
                "redis_configured": bool(settings.REDIS_URL),
                "rms_configured": bool(settings.RMS_DB_HOST),
                "shopify_configured": bool(settings.SHOPIFY_SHOP_URL),
                "redis_url": settings.REDIS_URL[:20] + "..." if settings.REDIS_URL else None,
                "rms_host": settings.RMS_DB_HOST,
                "shopify_url": settings.SHOPIFY_SHOP_URL,
            }

        return {
            "configuration": config,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system configuration") from e


@router.get("/logs/recent", summary="Get recent log entries", description="Get recent application log entries")
async def get_recent_logs(
    level: str = Query(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    _: None = Depends(verify_admin_access),
):
    """
    Get recent log entries.

    Args:
        level: Minimum log level to include
        limit: Maximum number of entries to return

    Returns:
        Dict: Recent log entries
    """
    try:
        # TODO: Implement actual log retrieval
        # This would read from log files or log aggregation system

        return {
            "logs": [],
            "filters": {
                "level": level,
                "limit": limit,
            },
            "message": "Log retrieval not implemented yet",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent logs") from e


@router.get(
    "/database-health",
    summary="Get database health details",
    description="Get detailed health information about the RMS database connection"
)
async def get_database_health(
    _: None = Depends(verify_admin_access)
):
    """
    Get detailed database health information.
    
    Returns:
        Dict: Detailed database health data
    """
    try:
        from app.db.connection import get_db_connection
        
        conn_db = get_db_connection()
        
        # Obtener información completa de la base de datos
        health_info = await conn_db.health_check()
        engine_info = conn_db.get_engine_info()
        
        # Información adicional de configuración
        config_info = {
            "host": settings.RMS_DB_HOST,
            "port": settings.RMS_DB_PORT,
            "database": settings.RMS_DB_NAME,
            "driver": settings.RMS_DB_DRIVER,
            "max_pool_size": settings.RMS_MAX_POOL_SIZE,
            "connection_timeout": settings.RMS_CONNECTION_TIMEOUT,
        }
        
        return {
            "health_check": health_info,
            "engine_info": engine_info,
            "configuration": config_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database health: {str(e)}") from e


@router.post(
    "/database-test",
    summary="Test database connection",
    description="Perform a test of the database connection and return results"
)
async def test_database_connection(
    _: None = Depends(verify_admin_access)
):
    """
    Test the database connection.
    
    Returns:
        Dict: Connection test results
    """
    try:
        from app.db.connection import get_db_connection
        
        conn_db = get_db_connection()
        
        # Realizar test de conexión
        import time
        start_time = time.time()
        
        if not conn_db.is_initialized():
            await conn_db.initialize()
        
        test_result = await conn_db.test_connection()
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        return {
            "connection_test": test_result,
            "response_time_ms": response_time,
            "initialized": conn_db.is_initialized(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Database connection test completed successfully" if test_result else "Database connection test failed"
        }
        
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test database connection: {str(e)}") from e

