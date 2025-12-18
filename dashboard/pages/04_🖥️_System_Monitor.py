"""
System Monitor Page - Detailed system health and performance monitoring.
"""

import streamlit as st

from dashboard.components.charts import remder_resource_usage_bars
from dashboard.components.health_cards import remder_service_status_grid
from dashboard.utils.api_client import get_api_client
from dashboard.utils.formatters import format_bytes, format_number, format_percentage, time_ago

st.set_page_config(
    page_title="System Monitor - RMS-Shopify Dashboard",
    page_icon="🖥️",
    layout="wide",
)

st.title("🖥️ Monitor del Sistema")
st.markdown("---")

api_client = get_api_client()

# Detailed Health Check
st.markdown("## 🏥 Estado Detallado de Salud")

health_detailed = api_client.get_health_detailed()

if health_detailed:
    # Check for "overall_status" (detailed endpoint) or "status" (fast endpoint)
    overall_status = health_detailed.get("overall_status", health_detailed.get("status", "unhealthy"))
    overall = overall_status == "healthy"
    services = health_detailed.get("components", health_detailed.get("services", {}))
    uptime_info = health_detailed.get("uptime", {})

    # Overall Status
    col1, col2 = st.columns([1, 1])

    with col1:
        if overall:
            st.success("✅ Sistema Operando Normalmente")
        else:
            st.error("❌ Sistema con Problemas")

    with col2:
        uptime_human = uptime_info.get("uptime_human", "N/A")
        start_time = uptime_info.get("start_time")

        st.metric(
            "Uptime del Sistema",
            uptime_human,
            delta=f"Iniciado {time_ago(start_time)}" if start_time else None,
        )

    st.markdown("---")

    # Service Details
    remder_service_status_grid(services)

else:
    st.warning("⚠️ No se pudo cargar información detalhadas de salud")

st.markdown("---")

# System Performance Metrics
st.markdown("## 📊 Métricas de Performance")

performance = api_client.get_system_metrics()

if performance:
    system = performance.get("system", {})

    # CPU, Memory, Disk
    cpu_percent = system.get("cpu_percent", 0)
    memory = system.get("memory", {})
    disk = system.get("disk", {})

    memory_percent = memory.get("percent", 0)
    disk_percent = disk.get("percent", 0)

    # Resource usage bars
    remder_resource_usage_bars(cpu_percent, memory_percent, disk_percent)

    st.markdown("---")

    # Detailed Resource Information
    st.markdown("### 💾 Detalles de Recursos")

    col1, col2, col3 = st.columns(3)

    # CPU Details
    with col1:
        st.markdown("#### 🖥️ CPU")
        st.metric("Uso Atual", format_percentage(cpu_percent))

    # Memory Details
    with col2:
        st.markdown("#### 🧠 Memoria")
        total = memory.get("total", 0)
        used = memory.get("used", 0)
        available = memory.get("available", 0)

        st.metric("Uso", format_percentage(memory_percent))
        st.write(f"**Total**: {format_bytes(total)}")
        st.write(f"**Usado**: {format_bytes(used)}")
        st.write(f"**Disponível**: {format_bytes(available)}")

    # Disk Details
    with col3:
        st.markdown("#### 💿 Disco")
        total = disk.get("total", 0)
        used = disk.get("used", 0)
        free = disk.get("free", 0)

        st.metric("Uso", format_percentage(disk_percent))
        st.write(f"**Total**: {format_bytes(total)}")
        st.write(f"**Usado**: {format_bytes(used)}")
        st.write(f"**Livre**: {format_bytes(free)}")

else:
    st.warning("⚠️ No se pudo cargar métricas de performance")

st.markdown("---")

# Additional Metrics
st.markdown("## 📈 Métricas Adicionais")

tab1, tab2, tab3 = st.tabs(["🔄 Retry Handler", "📡 Webhooks", "📦 Inventory"])

with tab1:
    retry_metrics = api_client.get_retry_metrics()

    if retry_metrics and "data" in retry_metrics:
        data = retry_metrics["data"]

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total de Tentativas", format_number(data.get("total_retries", 0)))

        with col2:
            st.metric("Éxitos", format_number(data.get("successful_retries", 0)))

        with col3:
            st.metric("Fallas", format_number(data.get("failed_retries", 0)))

        with col4:
            success_rate = data.get("success_rate", 0)
            st.metric("Tasa de Éxito", format_percentage(success_rate))

    else:
        st.info("ℹ️ Métricas de retry no disponibles")

with tab2:
    webhook_metrics = api_client.get_webhook_metrics()

    if webhook_metrics and "data" in webhook_metrics:
        data = webhook_metrics["data"]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Webhooks Processados", format_number(data.get("total_processed", 0)))

        with col2:
            st.metric("Éxitos", format_number(data.get("successful", 0)))

        with col3:
            st.metric("Fallas", format_number(data.get("failed", 0)))

    else:
        st.info("ℹ️ Métricas de webhook no disponibles")

with tab3:
    inventory_metrics = api_client.get_inventory_metrics()

    if inventory_metrics and "data" in inventory_metrics:
        data = inventory_metrics["data"]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Atualizações Totais", format_number(data.get("total_updates", 0)))

        with col2:
            st.metric("Éxitos", format_number(data.get("successful_updates", 0)))

        with col3:
            st.metric("Fallas", format_number(data.get("failed_updates", 0)))

    else:
        st.info("ℹ️ Métricas de inventory no disponibles")

st.markdown("---")

# Database Health (if available)
with st.expander("🗄️ Salud de la Base de Datos"):
    db_health = api_client.get_database_health()

    if db_health and "data" in db_health:
        data = db_health["data"]

        st.markdown("### Conexões RMS Database")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Pool Size", data.get("pool_size", "N/A"))

        with col2:
            st.metric("Conexões Ativas", data.get("active_connections", "N/A"))

        with col3:
            st.metric("Conexões Ociosas", data.get("idle_connections", "N/A"))

    else:
        st.info("ℹ️ Información de banco de dados no disponibles (requer DEBUG mode)")

# Refresh button
if st.button("🔄 Actualizar Página", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
