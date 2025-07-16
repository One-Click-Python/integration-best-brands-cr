"""
Sync operation manager for coordinating and tracking sync operations.

This module manages the lifecycle of sync operations, tracks active syncs,
and provides coordination between different sync services.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global sync tracking
_active_syncs: Dict[str, Dict[str, Any]] = {}
_sync_history: List[Dict[str, Any]] = []
_sync_lock = asyncio.Lock()


async def cancel_sync(sync_id: str, reason: str = "Manual cancellation"):
    """
    Cancel an active sync operation.

    Args:
        sync_id: Sync identifier
        reason: Cancellation reason
    """
    async with _sync_lock:
        try:
            if sync_id not in _active_syncs:
                logger.warning(f"Sync {sync_id} not found in active syncs")
                return False

            sync_info = _active_syncs[sync_id]
            sync_info.update(
                {
                    "status": "cancelled",
                    "end_time": datetime.now(timezone.utc),
                    "duration_seconds": (datetime.now(timezone.utc) - sync_info["start_time"]).total_seconds(),
                    "cancellation_reason": reason,
                }
            )

            # Move to history
            _sync_history.append(sync_info)
            del _active_syncs[sync_id]

            logger.info(f"Cancelled sync operation: {sync_id} (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Error cancelling sync {sync_id}: {e}")
            return False


def get_active_syncs() -> List[Dict[str, Any]]:
    """
    Get list of currently active sync operations.

    Returns:
        List: Active sync operations
    """
    try:
        return list(_active_syncs.values())

    except Exception as e:
        logger.error(f"Error getting active syncs: {e}")
        return []


def get_sync_status(sync_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of a specific sync operation.

    Args:
        sync_id: Sync identifier

    Returns:
        Dict: Sync status information or None if not found
    """
    try:
        # Check active syncs first
        if sync_id in _active_syncs:
            return _active_syncs[sync_id]

        # Check history
        for sync_info in reversed(_sync_history):
            if sync_info["sync_id"] == sync_id:
                return sync_info

        return None

    except Exception as e:
        logger.error(f"Error getting sync status for {sync_id}: {e}")
        return None


async def wait_for_active_syncs(timeout: float = 30.0):
    """
    Wait for all active sync operations to complete.

    Args:
        timeout: Maximum time to wait in seconds
    """
    try:
        start_time = asyncio.get_event_loop().time()

        while _active_syncs and (asyncio.get_event_loop().time() - start_time) < timeout:
            logger.info(f"Waiting for {len(_active_syncs)} active syncs to complete...")
            await asyncio.sleep(1)

        if _active_syncs:
            logger.warning(f"Timeout waiting for syncs to complete. {len(_active_syncs)} syncs still active.")
        else:
            logger.info("All sync operations completed successfully")

    except Exception as e:
        logger.error(f"Error waiting for active syncs: {e}")


def get_sync_statistics() -> Dict[str, Any]:
    """
    Get overall sync statistics.

    Returns:
        Dict: Sync statistics summary
    """
    try:
        total_syncs = len(_sync_history)
        if total_syncs == 0:
            return {
                "total_syncs": 0,
                "active_syncs": len(_active_syncs),
                "success_rate": 0,
                "avg_duration": 0,
            }

        successful_syncs = len([s for s in _sync_history if s.get("success", False)])
        total_duration = sum(s.get("duration_seconds", 0) for s in _sync_history)

        return {
            "total_syncs": total_syncs,
            "active_syncs": len(_active_syncs),
            "successful_syncs": successful_syncs,
            "failed_syncs": total_syncs - successful_syncs,
            "success_rate": (successful_syncs / total_syncs) * 100,
            "avg_duration": total_duration / total_syncs,
            "sync_types": list(set(s.get("sync_type") for s in _sync_history if s.get("sync_type"))),
        }

    except Exception as e:
        logger.error(f"Error getting sync statistics: {e}")
        return {"error": str(e)}
