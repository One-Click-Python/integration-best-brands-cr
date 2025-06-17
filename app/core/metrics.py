"""
Metrics collection and reporting system.

This module handles collecting, storing, and reporting system metrics
for monitoring sync performance and system health.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global metrics storage (in production this would be a proper metrics backend)
_metrics_data: Dict[str, List[Dict[str, Any]]] = {
    "sync_operations": [],
    "api_requests": [],
    "system_health": [],
    "errors": [],
}

_metrics_initialized = False


async def initialize_metrics():
    """
    Initialize the metrics collection system.
    """
    global _metrics_initialized
    
    try:
        logger.info("Initializing metrics system (simulated)")
        
        # TODO: Initialize actual metrics backend (Prometheus, StatsD, etc.)
        # For now, just simulate initialization
        
        _metrics_initialized = True
        logger.info("Metrics system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}")
        raise


async def finalize_metrics():
    """
    Finalize and cleanup metrics system.
    """
    global _metrics_initialized
    
    try:
        if not _metrics_initialized:
            return
            
        logger.info("Finalizing metrics system")
        
        # TODO: Flush metrics to backend, close connections
        # For now, just simulate cleanup
        
        _metrics_initialized = False
        logger.info("Metrics system finalized successfully")
        
    except Exception as e:
        logger.error(f"Error finalizing metrics: {e}")


def record_sync_metric(
    sync_type: str,
    duration_seconds: float,
    success_count: int,
    error_count: int,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Record a sync operation metric.
    
    Args:
        sync_type: Type of sync operation
        duration_seconds: Duration of the operation
        success_count: Number of successful operations
        error_count: Number of failed operations
        metadata: Additional metadata
    """
    try:
        if not _metrics_initialized:
            return
            
        metric = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sync_type": sync_type,
            "duration_seconds": duration_seconds,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / max(success_count + error_count, 1) * 100,
            "metadata": metadata or {},
        }
        
        _metrics_data["sync_operations"].append(metric)
        
        # Keep only last 1000 entries to prevent memory growth
        if len(_metrics_data["sync_operations"]) > 1000:
            _metrics_data["sync_operations"] = _metrics_data["sync_operations"][-1000:]
            
        logger.debug(f"Recorded sync metric for {sync_type}")
        
    except Exception as e:
        logger.error(f"Error recording sync metric: {e}")


def record_api_request(
    service: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float
):
    """
    Record an API request metric.
    
    Args:
        service: Service name (e.g., 'shopify', 'rms')
        endpoint: API endpoint
        method: HTTP method
        status_code: Response status code
        duration_ms: Request duration in milliseconds
    """
    try:
        if not _metrics_initialized:
            return
            
        metric = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "success": 200 <= status_code < 400,
        }
        
        _metrics_data["api_requests"].append(metric)
        
        # Keep only last 5000 entries
        if len(_metrics_data["api_requests"]) > 5000:
            _metrics_data["api_requests"] = _metrics_data["api_requests"][-5000:]
            
        logger.debug(f"Recorded API request metric for {service}/{endpoint}")
        
    except Exception as e:
        logger.error(f"Error recording API request metric: {e}")


def record_error_metric(
    error_type: str,
    error_message: str,
    service: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Record an error metric.
    
    Args:
        error_type: Type of error
        error_message: Error message
        service: Service where error occurred
        metadata: Additional error context
    """
    try:
        if not _metrics_initialized:
            return
            
        metric = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "service": service,
            "metadata": metadata or {},
        }
        
        _metrics_data["errors"].append(metric)
        
        # Keep only last 1000 errors
        if len(_metrics_data["errors"]) > 1000:
            _metrics_data["errors"] = _metrics_data["errors"][-1000:]
            
        logger.debug(f"Recorded error metric: {error_type}")
        
    except Exception as e:
        logger.error(f"Error recording error metric: {e}")


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of collected metrics.
    
    Returns:
        Dict: Metrics summary
    """
    try:
        if not _metrics_initialized:
            return {"error": "Metrics not initialized"}
            
        # Calculate summary statistics
        sync_ops = _metrics_data["sync_operations"]
        api_requests = _metrics_data["api_requests"]
        errors = _metrics_data["errors"]
        
        summary = {
            "collection_status": "active" if _metrics_initialized else "inactive",
            "data_points": {
                "sync_operations": len(sync_ops),
                "api_requests": len(api_requests),
                "errors": len(errors),
            },
            "sync_metrics": {
                "total_operations": len(sync_ops),
                "avg_duration": sum(op["duration_seconds"] for op in sync_ops) / max(len(sync_ops), 1),
                "avg_success_rate": sum(op["success_rate"] for op in sync_ops) / max(len(sync_ops), 1),
            },
            "api_metrics": {
                "total_requests": len(api_requests),
                "avg_duration_ms": sum(req["duration_ms"] for req in api_requests) / max(len(api_requests), 1),
                "success_rate": len([req for req in api_requests if req["success"]]) / max(len(api_requests), 1) * 100,
            },
            "error_metrics": {
                "total_errors": len(errors),
                "error_types": list(set(err["error_type"] for err in errors)),
            },
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        return {"error": str(e)}


def clear_metrics():
    """
    Clear all collected metrics.
    """
    try:
        global _metrics_data
        
        _metrics_data = {
            "sync_operations": [],
            "api_requests": [],
            "system_health": [],
            "errors": [],
        }
        
        logger.info("Metrics data cleared")
        
    except Exception as e:
        logger.error(f"Error clearing metrics: {e}")