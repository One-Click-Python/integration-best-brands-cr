"""
API Client for RMS-Shopify Integration Dashboard

Handles all communication with the FastAPI backend endpoints.
"""

import os
from typing import Any

import requests
import streamlit as st

# Timeout constants
DEFAULT_TIMEOUT = 10  # For quick operations (health, status, etc.)
SYNC_TIMEOUT = 120  # For sync operations (2 minutes - RMS + Shopify API calls)


class APIClient:
    """Client for interacting with the RMS-Shopify Integration API."""

    def __init__(self, base_url: str | None = None, timeout: int = 10):
        """
        Initialize the API client.

        Args:
            base_url: Base URL for the API (default: from env or localhost:8080)
            timeout: Request timeout in seconds (default: 10)
        """
        self.base_url = base_url or os.getenv("DASHBOARD_API_URL", "http://localhost:8080")
        self.timeout = timeout
        self.session = requests.Session()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/api/v1/health")
            params: Query parameters
            json: JSON body for POST/PUT requests
            timeout: Optional timeout override (default: self.timeout)

        Returns:
            Response JSON data or None if error

        Raises:
            requests.exceptions.RequestException: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        request_timeout = timeout if timeout is not None else self.timeout

        try:
            response = self.session.request(method=method, url=url, params=params, json=json, timeout=request_timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            st.error(f"⏱️ Timeout de solicitud: La API no respondió en {request_timeout}s")
            return None
        except requests.exceptions.ConnectionError:
            st.error(f"🔌 Error de conexión: No se pudo conectar a la API en {self.base_url}")
            return None
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ Error HTTP {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            return None

    # ==================== HEALTH & SYSTEM ====================

    @st.cache_data(ttl=5)
    def get_health(_self) -> dict[str, Any] | None:
        """Get system health status (cached for 5s)."""
        return _self._make_request("GET", "/health")

    @st.cache_data(ttl=10)
    def get_health_detailed(_self) -> dict[str, Any] | None:
        """Get detailed health check with component status (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/metrics/health-detailed")

    @st.cache_data(ttl=30)
    def get_system_metrics(_self) -> dict[str, Any] | None:
        """Get system performance metrics (CPU, memory, disk) - cached for 30s."""
        return _self._make_request("GET", "/api/v1/metrics/performance")

    @st.cache_data(ttl=30)
    def get_dashboard_metrics(_self) -> dict[str, Any] | None:
        """Get dashboard summary metrics (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/metrics/dashboard")

    # ==================== SYNC MONITORING ====================

    @st.cache_data(ttl=5)
    def get_sync_status(_self) -> dict[str, Any] | None:
        """Get sync monitor status (cached for 5s)."""
        return _self._make_request("GET", "/api/v1/sync/monitor/status")

    @st.cache_data(ttl=10)
    def get_sync_stats(_self) -> dict[str, Any] | None:
        """Get sync statistics (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/sync/monitor/stats")

    def get_sync_config(_self) -> dict[str, Any] | None:
        """Get sync configuration (no cache - realtime)."""
        return _self._make_request("GET", "/api/v1/sync/monitor/config")

    def trigger_sync(_self, sync_type: str = "incremental") -> dict[str, Any] | None:
        """
        Trigger a manual sync.

        Args:
            sync_type: "incremental" or "full"
        """
        if sync_type == "full":
            return _self._make_request("POST", "/api/v1/sync/monitor/force-full-sync", timeout=SYNC_TIMEOUT)
        else:
            return _self._make_request("POST", "/api/v1/sync/monitor/trigger", timeout=SYNC_TIMEOUT)

    def update_sync_interval(_self, interval_minutes: int) -> dict[str, Any] | None:
        """Update sync interval."""
        return _self._make_request("PUT", "/api/v1/sync/monitor/interval", json={"interval_minutes": interval_minutes})

    # ==================== CHECKPOINTS ====================

    @st.cache_data(ttl=10)
    def get_checkpoint_list(_self) -> dict[str, Any] | None:
        """Get list of active checkpoints (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/sync/monitor/checkpoint/list")

    def get_checkpoint_status(_self, sync_id: str) -> dict[str, Any] | None:
        """Get specific checkpoint status (no cache)."""
        return _self._make_request("GET", f"/api/v1/sync/monitor/checkpoint/{sync_id}")

    def resume_checkpoint(_self, sync_id: str) -> dict[str, Any] | None:
        """Resume sync from checkpoint."""
        return _self._make_request("POST", f"/api/v1/sync/monitor/checkpoint/resume/{sync_id}")

    def delete_checkpoint(_self, sync_id: str) -> dict[str, Any] | None:
        """Delete a checkpoint."""
        return _self._make_request("DELETE", f"/api/v1/sync/monitor/checkpoint/{sync_id}")

    # ==================== ORDER POLLING ====================

    @st.cache_data(ttl=5)
    def get_order_polling_status(_self) -> dict[str, Any] | None:
        """Get order polling status and statistics (cached for 5s)."""
        return _self._make_request("GET", "/api/v1/orders/polling/status")

    @st.cache_data(ttl=10)
    def get_order_polling_stats(_self) -> dict[str, Any] | None:
        """Get order polling cumulative statistics (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/orders/polling/stats")

    def trigger_order_polling(
        _self, lookback_minutes: int | None = None, batch_size: int | None = None, dry_run: bool = False
    ) -> dict[str, Any] | None:
        """
        Trigger manual order polling.

        Args:
            lookback_minutes: Time window to search (default: from config)
            batch_size: Orders per page (default: from config)
            dry_run: Test without making changes
        """
        payload = {}
        if lookback_minutes is not None:
            payload["lookback_minutes"] = lookback_minutes
        if batch_size is not None:
            payload["batch_size"] = batch_size
        if dry_run:
            payload["dry_run"] = dry_run

        return _self._make_request("POST", "/api/v1/orders/polling/trigger", json=payload, timeout=SYNC_TIMEOUT)

    def reset_order_polling_stats(_self) -> dict[str, Any] | None:
        """Reset order polling statistics."""
        return _self._make_request("POST", "/api/v1/orders/polling/reset-stats")

    def update_order_polling_config(
        _self, interval_minutes: int | None = None, lookback_minutes: int | None = None
    ) -> dict[str, Any] | None:
        """Update order polling configuration."""
        payload = {}
        if interval_minutes is not None:
            payload["interval_minutes"] = interval_minutes
        if lookback_minutes is not None:
            payload["lookback_minutes"] = lookback_minutes

        return _self._make_request("PUT", "/api/v1/orders/polling/config", json=payload)

    # ==================== REVERSE STOCK SYNC ====================

    def trigger_reverse_stock_sync(_self, dry_run: bool = False) -> dict[str, Any] | None:
        """
        Trigger reverse stock sync (Shopify → RMS).

        Args:
            dry_run: Test without making changes
        """
        params = {"dry_run": str(dry_run).lower()}
        return _self._make_request("POST", "/api/v1/sync/reverse-stock-sync", params=params, timeout=SYNC_TIMEOUT)

    @st.cache_data(ttl=10)
    def get_reverse_stock_sync_status(_self) -> dict[str, Any] | None:
        """Get reverse stock sync status (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/sync/reverse-stock-sync/status")

    # ==================== COLLECTIONS ====================

    def sync_collections(
        _self, dry_run: bool = False, sync_main: bool = True, sync_subcategories: bool = True
    ) -> dict[str, Any] | None:
        """Sync Shopify collections."""
        params = {
            "dry_run": str(dry_run).lower(),
            "sync_main": str(sync_main).lower(),
            "sync_subcategories": str(sync_subcategories).lower(),
        }
        return _self._make_request("POST", "/api/v1/collections/sync", params=params, timeout=SYNC_TIMEOUT)

    @st.cache_data(ttl=30)
    def get_collections_status(_self) -> dict[str, Any] | None:
        """Get collections sync status (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/collections/status")

    # ==================== METRICS ====================

    @st.cache_data(ttl=30)
    def get_retry_metrics(_self) -> dict[str, Any] | None:
        """Get retry handler metrics (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/metrics/retry")

    @st.cache_data(ttl=30)
    def get_webhook_metrics(_self) -> dict[str, Any] | None:
        """Get webhook processor metrics (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/metrics/webhooks")

    @st.cache_data(ttl=30)
    def get_inventory_metrics(_self) -> dict[str, Any] | None:
        """Get inventory manager metrics (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/metrics/inventory")

    def reset_metrics(_self) -> dict[str, Any] | None:
        """Reset all metrics."""
        return _self._make_request("POST", "/api/v1/metrics/reset")

    def reset_circuit_breakers(_self) -> dict[str, Any] | None:
        """Reset circuit breakers."""
        return _self._make_request("POST", "/api/v1/metrics/reset-circuit-breakers")

    # ==================== LOGS (DEBUG MODE) ====================

    def search_logs(
        _self, level: str | None = None, limit: int = 100, search: str | None = None
    ) -> dict[str, Any] | None:
        """
        Search log entries.

        Args:
            level: Log level filter (INFO, WARNING, ERROR)
            limit: Maximum entries to return
            search: Search term in message
        """
        params = {"limit": limit}
        if level:
            params["level"] = level
        if search:
            params["search"] = search

        return _self._make_request("GET", "/api/v1/logs/search", params=params)

    @st.cache_data(ttl=5)
    def get_recent_logs(_self, limit: int = 100) -> dict[str, Any] | None:
        """Get recent log entries (cached for 5s)."""
        return _self._make_request("GET", "/api/v1/logs/recent", params={"limit": limit})

    @st.cache_data(ttl=30)
    def get_log_stats(_self) -> dict[str, Any] | None:
        """Get log statistics (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/logs/stats")

    @st.cache_data(ttl=5)
    def get_recent_errors(_self, limit: int = 50) -> dict[str, Any] | None:
        """Get recent error logs (cached for 5s)."""
        return _self._make_request("GET", "/api/v1/logs/errors", params={"limit": limit})

    # ==================== ADMIN (DEBUG MODE) ====================

    @st.cache_data(ttl=60)
    def get_system_info(_self) -> dict[str, Any] | None:
        """Get system information (cached for 60s)."""
        return _self._make_request("GET", "/api/v1/admin/system-info")

    @st.cache_data(ttl=10)
    def get_cache_stats(_self) -> dict[str, Any] | None:
        """Get cache statistics (cached for 10s)."""
        return _self._make_request("GET", "/api/v1/admin/cache-stats")

    @st.cache_data(ttl=5)
    def get_active_syncs(_self) -> dict[str, Any] | None:
        """Get active sync operations (cached for 5s)."""
        return _self._make_request("GET", "/api/v1/admin/active-syncs")

    def cancel_sync(_self, sync_id: str) -> dict[str, Any] | None:
        """Cancel a running sync."""
        return _self._make_request("POST", f"/api/v1/admin/cancel-sync/{sync_id}")

    @st.cache_data(ttl=30)
    def get_database_health(_self) -> dict[str, Any] | None:
        """Get database health details (cached for 30s)."""
        return _self._make_request("GET", "/api/v1/admin/database-health")


# Singleton instance
_client_instance: APIClient | None = None


def get_api_client() -> APIClient:
    """Get or create the API client singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = APIClient()
    return _client_instance
