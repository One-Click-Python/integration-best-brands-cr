"""
Metrics display components for the dashboard.
"""

import streamlit as st

from dashboard.utils.formatters import (
    format_datetime,
    format_number,
    format_percentage,
    format_timedelta,
    get_health_status,
    time_ago,
)


def remder_sync_metrics_card(sync_data: dict | None) -> None:
    """
    Render sync engine metrics card.

    Args:
        sync_data: Sync monitor status data
    """
    if not sync_data or "data" not in sync_data:
        st.warning("⚠️ Datos de sincronización no disponibles")
        return

    data = sync_data["data"]
    change_detector = data.get("change_detector", {})

    st.markdown("### 🔄 Sincronización RMS → Shopify")

    # Main metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    # Last sync
    with col1:
        last_check = change_detector.get("last_check_time")
        last_check_display = time_ago(last_check) if last_check else "N/A"

        st.metric(
            label="Última Sincronización",
            value=last_check_display,
            help=f"Timestamp: {format_datetime(last_check)}" if last_check else "Ninguna sincronización registrada",
        )

    # Itens synced
    with col2:
        items_synced = change_detector.get("items_synced", 0)
        st.metric(
            label="Ítems Sincronizados",
            value=format_number(items_synced),
            help="Total de items sincronizados desde o inicio",
        )

    # Changes detected
    with col3:
        changes_detected = change_detector.get("changes_detected", 0)
        st.metric(
            label="Cambios Detectados",
            value=format_number(changes_detected),
            help="Total de cambios detectados no RMS",
        )

    # Next sync
    with col4:
        next_sync = data.get("next_sync")
        if next_sync:
            next_sync_display = time_ago(next_sync).replace("hace", "en")
        else:
            next_sync_display = "N/A"

        st.metric(
            label="Próxima Sincronización",
            value=next_sync_display,
            help=f"Timestamp: {format_datetime(next_sync)}" if next_sync else "Sincronización no programada",
        )

    # Status indicators
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        monitoring_active = data.get("monitoring_active", False)
        icon = "🟢" if monitoring_active else "🔴"
        status = "Activo" if monitoring_active else "Inactivo"
        st.markdown(f"**Monitoreo**: {icon} {status}")

    with col2:
        change_detection = data.get("change_detection_enabled", False)
        icon = "🟢" if change_detection else "🔴"
        status = "Habilitado" if change_detection else "Deshabilitado"
        st.markdown(f"**Detección de Cambios**: {icon} {status}")

    with col3:
        interval = data.get("sync_interval_minutes", 0)
        st.markdown(f"**Intervalo**: ⏱️ {interval} min")


def remder_order_polling_metrics_card(polling_data: dict | None) -> None:
    """
    Render order polling metrics card.

    Args:
        polling_data: Order polling status data
    """
    if not polling_data or "data" not in polling_data:
        st.warning("⚠️ Datos de polling de pedidos no disponibles")
        return

    data = polling_data["data"]
    stats = data.get("statistics", {})

    st.markdown("### 📦 Polling de Pedidos (Shopify → RMS)")

    # Main metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_polled = stats.get("total_polled", 0)
        st.metric(
            label="Total Consultado",
            value=format_number(total_polled),
            help="Total de pedidos consultados desde o inicio",
        )

    with col2:
        newly_synced = stats.get("newly_synced", 0)
        st.metric(
            label="Nuevos Sincronizados",
            value=format_number(newly_synced),
            help="Pedidos novos sincronizados con éxito",
        )

    with col3:
        updated = stats.get("updated", 0)
        st.metric(
            label="Actualizados",
            value=format_number(updated),
            help="Pedidos existentes que fueron actualizados",
        )

    with col4:
        success_rate = stats.get("success_rate", 0)
        rate_status, rate_icon = get_health_status(success_rate, "success_rate")

        st.metric(
            label=f"Tasa de Éxito {rate_icon}",
            value=format_percentage(success_rate),
            help=f"Estado: {rate_status}",
        )

    # Additional info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        enabled = data.get("enabled", False)
        icon = "🟢" if enabled else "🔴"
        status = "Habilitado" if enabled else "Deshabilitado"
        st.markdown(f"**Estado**: {icon} {status}")

    with col2:
        last_poll = stats.get("last_poll_time")
        if last_poll:
            st.markdown(f"**Última Consulta**: {time_ago(last_poll)}")
        else:
            st.markdown("**Última Consulta**: N/A")

    with col3:
        errors = stats.get("sync_errors", 0)
        icon = "⚠️" if errors > 0 else "✅"
        st.markdown(f"**Erros**: {icon} {format_number(errors)}")


def remder_system_resources_card(metrics_data: dict | None) -> None:
    """
    Render system resources metrics card.

    Args:
        metrics_data: System performance metrics data
    """
    if not metrics_data:
        st.warning("⚠️ Métricas de sistema no disponibles")
        return

    system = metrics_data.get("system", {})

    st.markdown("### 🖥️ Recursos del Sistema")

    col1, col2, col3 = st.columns(3)

    # CPU Usage
    with col1:
        cpu_percent = system.get("cpu_percent", 0)
        cpu_status, cpu_icon = get_health_status(cpu_percent, "cpu")

        st.metric(
            label=f"CPU {cpu_icon}",
            value=format_percentage(cpu_percent),
            help=f"Estado: {cpu_status}",
        )
        st.progress(min(cpu_percent / 100, 1.0))

    # Memory Usage
    with col2:
        memory = system.get("memory", {})
        memory_percent = memory.get("percent", 0)
        memory_status, memory_icon = get_health_status(memory_percent, "memory")

        st.metric(
            label=f"Memoria {memory_icon}",
            value=format_percentage(memory_percent),
            help=f"Estado: {memory_status}",
        )
        st.progress(min(memory_percent / 100, 1.0))

    # Disk Usage
    with col3:
        disk = system.get("disk", {})
        disk_percent = disk.get("percent", 0)
        disk_status, disk_icon = get_health_status(disk_percent, "disk")

        st.metric(
            label=f"Disco {disk_icon}",
            value=format_percentage(disk_percent),
            help=f"Estado: {disk_status}",
        )
        st.progress(min(disk_percent / 100, 1.0))


def remder_reverse_sync_status(sync_data: dict | None) -> None:
    """
    Render reverse stock sync status.

    Args:
        sync_data: Sync monitor status data
    """
    if not sync_data or "data" not in sync_data:
        return

    reverse_sync = sync_data["data"].get("reverse_stock_sync", {})

    if not reverse_sync:
        return

    st.markdown("### 🔁 Sincronización Reversa (Shopify → RMS)")

    col1, col2, col3 = st.columns(3)

    with col1:
        enabled = reverse_sync.get("enabled", False)
        icon = "🟢" if enabled else "🔴"
        status = "Habilitado" if enabled else "Deshabilitado"
        st.markdown(f"**Estado**: {icon} {status}")

    with col2:
        delay = reverse_sync.get("delay_minutes", 0)
        st.markdown(f"**Delay**: ⏱️ {delay} min")

    with col3:
        rms_success = reverse_sync.get("last_rms_sync_success", False)
        icon = "✅" if rms_success else "❌"
        status = "Éxito" if rms_success else "Falla"
        st.markdown(f"**Última Sync RMS**: {icon} {status}")

    # Time until next execution
    if enabled:
        seconds_until = reverse_sync.get("seconds_until_eligible", 0)
        # Fix: Handle None case to prevent comparison error
        if seconds_until is not None and seconds_until > 0:
            time_until = format_timedelta(seconds_until)
            st.info(f"⏳ Próxima ejecución en: **{time_until}**")
        else:
            sync_status = reverse_sync.get("status", "unknown")
            if sync_status == "ready_to_execute":
                st.success("✅ Listo para ejecutar")
            elif sync_status == "blocked_by_failed_rms_sync":
                st.error("❌ Bloqueado por falla en la sincronización RMS")


def remder_metric_card(
    label: str, value: str | int | float, delta: str | None = None, icon: str = "📊", help_text: str | None = None
) -> None:
    """
    Render a single metric card.

    Args:
        label: Metric label
        value: Metric value
        delta: Optional delta/change value
        icon: Optional icon
        help_text: Optional help tooltip text
    """
    st.metric(
        label=f"{icon} {label}",
        value=value,
        delta=delta,
        delta_color="off" if delta else "normal",
        help=help_text,
    )


def remder_stats_summary(title: str, stats: dict[str, int | float]) -> None:
    """
    Render a summary of statistics.

    Args:
        title: Section title
        stats: Dictionary of statistic name -> value
    """
    st.markdown(f"#### {title}")

    num_stats = len(stats)
    cols = st.columns(min(num_stats, 4))  # Max 4 columns

    for idx, (stat_name, stat_value) in enumerate(stats.items()):
        col_idx = idx % 4
        with cols[col_idx]:
            # Format value based on type
            if isinstance(stat_value, float):
                if stat_value < 1:
                    display_value = format_percentage(stat_value * 100)
                else:
                    display_value = format_number(stat_value, decimals=2)
            else:
                display_value = format_number(stat_value)

            st.metric(label=stat_name, value=display_value)
