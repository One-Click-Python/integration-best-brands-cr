"""
Constants and configuration for the dashboard.
"""

# ==================== STATUS INDICATORS ====================

STATUS_ICONS = {
    "healthy": "🟢",
    "unhealthy": "🔴",
    "warning": "🟡",
    "unknown": "⚪",
    "running": "🟢",
    "stopped": "🔴",
    "success": "✅",
    "error": "❌",
    "pending": "⏳",
    "in_progress": "🔄",
}

# ==================== COLOR SCHEMES ====================

# Health status colors
COLORS = {
    "success": "#28a745",
    "error": "#dc3545",
    "warning": "#ffc107",
    "info": "#17a2b8",
    "primary": "#007bff",
    "secondary": "#6c757d",
    "light": "#f8f9fa",
    "dark": "#343a40",
}

# Chart colors (Plotly compatible)
CHART_COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "info": "#17becf",
    "purple": "#9467bd",
    "pink": "#e377c2",
    "olive": "#bcbd22",
    "cyan": "#17becf",
}

# ==================== AUTO-REFRESH INTERVALS ====================

REFRESH_INTERVALS = {
    "5s": 5,
    "10s": 10,
    "30s": 30,
    "1min": 60,
    "5min": 300,
    "Deshabilitado": 0,
}

# ==================== LOG LEVELS ====================

LOG_LEVELS = {
    "ALL": None,
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
}

LOG_LEVEL_COLORS = {
    "INFO": "#17a2b8",
    "WARNING": "#ffc107",
    "ERROR": "#dc3545",
    "DEBUG": "#6c757d",
}

# ==================== SYNC TYPES ====================

SYNC_TYPES = {
    "Incremental": "incremental",
    "Full Sync": "full",
}

# ==================== DEFAULT CONFIGURATION ====================

DEFAULT_CONFIG = {
    "api_url": "http://localhost:8080",
    "timeout": 10,
    "auto_refresh": 30,
    "page_title": "RMS-Shopify Dashboard",
    "page_icon": "🛍️",
}

# ==================== METRICS THRESHOLDS ====================

THRESHOLDS = {
    "cpu_warning": 70.0,
    "cpu_critical": 90.0,
    "memory_warning": 75.0,
    "memory_critical": 90.0,
    "disk_warning": 80.0,
    "disk_critical": 95.0,
    "success_rate_warning": 95.0,
    "success_rate_critical": 90.0,
}

# ==================== TABLE CONFIGS ====================

TABLE_PAGE_SIZES = [10, 25, 50, 100]

# ==================== DATETIME FORMATS ====================

DATETIME_FORMATS = {
    "display": "%Y-%m-%d %H:%M:%S",
    "display_short": "%H:%M:%S",
    "date_only": "%Y-%m-%d",
    "time_only": "%H:%M:%S",
    "iso": "%Y-%m-%dT%H:%M:%S",
}
