"""
Formatting utilities for dashboard display.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from dashboard.utils.constants import DATETIME_FORMATS, STATUS_ICONS, THRESHOLDS


def format_datetime(dt: str | datetime | None, format_type: str = "display") -> str:
    """
    Format datetime string or object for display.

    Args:
        dt: Datetime string (ISO format) or datetime object
        format_type: Format type from DATETIME_FORMATS

    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "N/A"

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return dt

    fmt = DATETIME_FORMATS.get(format_type, DATETIME_FORMATS["display"])
    return dt.strftime(fmt)


def format_timedelta(seconds: int | float | None) -> str:
    """
    Format seconds into human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2d 3h 45m")
    """
    if seconds is None or seconds < 0:
        return "N/A"

    delta = timedelta(seconds=int(seconds))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and not parts:  # Only show seconds if less than 1 minute
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s"


def format_percentage(value: float | None, decimals: int = 1) -> str:
    """
    Format float as percentage.

    Args:
        value: Value to format (0-100 or 0-1)
        decimals: Decimal places

    Returns:
        Formatted percentage string
    """
    if value is None:
        return "N/A"

    # Handle both 0-1 and 0-100 ranges
    if 0 <= value <= 1:
        value = value * 100

    return f"{value:.{decimals}f}%"


def format_number(value: int | float | None, decimals: int = 0) -> str:
    """
    Format number with thousand separators.

    Args:
        value: Number to format
        decimals: Decimal places

    Returns:
        Formatted number string
    """
    if value is None:
        return "N/A"

    if decimals > 0:
        return f"{value:,.{decimals}f}"
    else:
        return f"{int(value):,}"


def format_bytes(bytes_value: int | float | None, decimals: int = 2) -> str:
    """
    Format bytes into human-readable size.

    Args:
        bytes_value: Size in bytes
        decimals: Decimal places

    Returns:
        Formatted size string (e.g., "1.5 GB")
    """
    if bytes_value is None or bytes_value < 0:
        return "N/A"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(bytes_value)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.{decimals}f} {units[unit_index]}"


def get_status_icon(status: str | bool) -> str:
    """
    Get emoji icon for status.

    Args:
        status: Status string or boolean

    Returns:
        Status icon emoji
    """
    if isinstance(status, bool):
        return STATUS_ICONS["success"] if status else STATUS_ICONS["error"]

    status_lower = str(status).lower()
    return STATUS_ICONS.get(status_lower, STATUS_ICONS["unknown"])


def get_health_status(value: float, metric_type: str) -> tuple[str, str]:
    """
    Determine health status based on metric value.

    Args:
        value: Metric value
        metric_type: Type of metric (cpu, memory, disk, success_rate)

    Returns:
        Tuple of (status_text, status_icon)
    """
    warning_threshold = THRESHOLDS.get(f"{metric_type}_warning", 75.0)
    critical_threshold = THRESHOLDS.get(f"{metric_type}_critical", 90.0)

    # For success_rate, lower is worse (inverted logic)
    if metric_type == "success_rate":
        if value >= warning_threshold:
            return ("Saludable", STATUS_ICONS["healthy"])
        elif value >= critical_threshold:
            return ("Alerta", STATUS_ICONS["warning"])
        else:
            return ("Crítico", STATUS_ICONS["unhealthy"])

    # For resource metrics, higher is worse
    if value >= critical_threshold:
        return ("Crítico", STATUS_ICONS["unhealthy"])
    elif value >= warning_threshold:
        return ("Alerta", STATUS_ICONS["warning"])
    else:
        return ("Saludable", STATUS_ICONS["healthy"])


def format_success_rate(success_count: int, total_count: int) -> str:
    """
    Calculate and format success rate.

    Args:
        success_count: Number of successful operations
        total_count: Total number of operations

    Returns:
        Formatted success rate percentage
    """
    if total_count == 0:
        return "N/A"

    rate = (success_count / total_count) * 100
    return format_percentage(rate, decimals=1)


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def format_dict_for_display(data: dict[str, Any], max_depth: int = 2, indent: int = 0) -> str:
    """
    Format dictionary for readable display.

    Args:
        data: Dictionary to format
        max_depth: Maximum nesting depth
        indent: Curremt indentation level

    Returns:
        Formatted string representation
    """
    if indent >= max_depth:
        return str(data)

    lines = []
    for key, value in data.items():
        prefix = "  " * indent
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(format_dict_for_display(value, max_depth, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: {len(value)} items")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)


def time_ago(dt: str | datetime | None) -> str:
    """
    Format datetime as time ago (e.g., "2 hours ago").

    Args:
        dt: Datetime string or object

    Returns:
        Time ago string
    """
    if dt is None:
        return "N/A"

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return dt

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "ahora mismo"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"hace {minutes} min" if minutes > 1 else "hace 1 min"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"hace {hours} horas" if hours > 1 else "hace 1 hora"
    else:
        days = int(seconds / 86400)
        return f"hace {days} días" if days > 1 else "hace 1 día"
