"""
Health status cards for the dashboard.
"""

import streamlit as st

from dashboard.utils.formatters import format_number, get_status_icon, time_ago


def remder_system_health_card(health_data: dict | None) -> None:
    """
    Render overall system health card.

    Args:
        health_data: Health check response data
    """
    if not health_data:
        st.error("❌ No se pudo obtener información de salud del sistema")
        return

    # Check both "overall" (detailed endpoint) and "status" (fast endpoint)
    overall = health_data.get("overall", health_data.get("status") == "healthy")
    services = health_data.get("services", {})

    # Overall status
    status_icon = get_status_icon(overall)
    status_text = "Sistema Saludable" if overall else "Sistema con Problemas"
    status_color = "green" if overall else "red"

    st.markdown(
        f"### {status_icon} {status_text}",
        help="Estado general de todos los servicios del sistema",
    )

    # Services status in columns
    num_services = len(services)
    if num_services > 0:
        cols = st.columns(num_services)

        for idx, (service_name, service_data) in enumerate(services.items()):
            with cols[idx]:
                service_status = service_data.get("status", "unknown")
                service_healthy = service_status == "healthy"
                service_icon = get_status_icon(service_healthy)

                latency = service_data.get("latency_ms")
                latency_text = f"{latency:.0f}ms" if latency is not None else "N/A"

                # Service name mapping
                service_display_names = {
                    "rms": "RMS Database",
                    "shopify": "Shopify API",
                    "redis": "Redis Cache",
                }
                display_name = service_display_names.get(service_name, service_name.upper())

                st.metric(
                    label=f"{service_icon} {display_name}",
                    value=service_status.title(),
                    delta=latency_text,
                    delta_color="off",
                )


def remder_uptime_card(health_data: dict | None) -> None:
    """
    Render system uptime card.

    Args:
        health_data: Health check response data with uptime info
    """
    if not health_data or "uptime" not in health_data:
        return

    uptime = health_data["uptime"]
    uptime_human = uptime.get("uptime_human", "N/A")
    start_time = uptime.get("start_time")

    st.metric(
        label="⏱️ Uptime del Sistema",
        value=uptime_human,
        delta=f"Iniciado: {time_ago(start_time)}",
        delta_color="off",
        help="Tiempo desde la última reinicialização del sistema",
    )


def remder_service_status_grid(services: dict) -> None:
    """
    Render detailed service status grid.

    Args:
        services: Dictionary of service status data
    """
    if not services:
        st.info("ℹ️ Ninguna información de servicio disponible")
        return

    st.markdown("#### Estado Detallado de los Servicios")

    # Create a table-like display
    for service_name, service_data in services.items():
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 4])

            status = service_data.get("status", "unknown")
            healthy = status == "healthy"
            icon = get_status_icon(healthy)

            with col1:
                st.markdown(f"**{service_name.upper()}**")

            with col2:
                color = "green" if healthy else "red"
                st.markdown(f":{color}[{icon} {status.title()}]")

            with col3:
                latency = service_data.get("latency_ms")
                if latency is not None:
                    st.markdown(f"Latência: **{latency:.0f}ms**")
                else:
                    st.markdown("Latência: **N/A**")

            with col4:
                # Additional service info if available
                if "error" in service_data:
                    st.markdown(f":red[⚠️ {service_data['error']}]")
                elif "last_check" in service_data:
                    st.markdown(f"Última verificação: {time_ago(service_data['last_check'])}")

            st.divider()


def remder_health_indicators(health_data: dict | None) -> None:
    """
    Render conpact health indicators for all services.

    Args:
        health_data: Health check response data
    """
    if not health_data:
        return

    services = health_data.get("services", {})

    if not services:
        return

    # Create horizontal indicators
    cols = st.columns(len(services))

    for idx, (service_name, service_data) in enumerate(services.items()):
        with cols[idx]:
            status = service_data.get("status", "unknown")
            healthy = status == "healthy"
            icon = get_status_icon(healthy)

            # Service name mapping
            names = {"rms": "RMS", "shopify": "Shopify", "redis": "Redis"}
            display_name = names.get(service_name, service_name.upper())

            # Color-coded container
            color = "green" if healthy else "red"
            st.markdown(
                f"""
                <div style="
                    text-align: center;
                    padding: 10px;
                    border-radius: 5px;
                    border: 2px solid {'#28a745' if healthy else '#dc3545'};
                    background-color: {'#d4edda' if healthy else '#f8d7da'};
                ">
                    <h3 style="margin: 0; color: {'#155724' if healthy else '#721c24'};">
                        {icon}
                    </h3>
                    <p style="margin: 5px 0 0 0; font-weight: bold; color: {'#155724' if healthy else '#721c24'};">
                        {display_name}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def remder_connection_test_results(test_results: dict) -> None:
    """
    Render connection test results.

    Args:
        test_results: Dictionary with test results for each service
    """
    st.markdown("#### Resultados do Teste de Conexão")

    for service_name, result in test_results.items():
        success = result.get("success", False)
        icon = get_status_icon(success)
        color = "green" if success else "red"

        with st.container():
            col1, col2 = st.columns([3, 7])

            with col1:
                st.markdown(f":{color}[{icon} **{service_name.upper()}**]")

            with col2:
                if success:
                    latency = result.get("latency_ms", 0)
                    st.markdown(f"✅ Conexão exitosa ({latency:.0f}ms)")
                else:
                    error = result.get("error", "Erro desconhecido")
                    st.markdown(f":red[❌ Falla: {error}]")

            st.divider()
