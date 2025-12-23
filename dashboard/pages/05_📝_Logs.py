"""
Logs Page - View and search application logs (DEBUG mode required).
"""

import sys
from pathlib import Path

# Ensure dashboard module is importable (required for Streamlit in Docker)
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import streamlit as st

from dashboard.components.charts import remder_log_level_distribution
from dashboard.utils.api_client import get_api_client
from dashboard.utils.constants import LOG_LEVEL_COLORS, LOG_LEVELS
from dashboard.utils.formatters import format_datetime, format_number

st.set_page_config(
    page_title="Logs - RMS-Shopify Dashboard",
    page_icon="📝",
    layout="wide",
)

st.title("📝 Logs del Sistema")
st.markdown("---")

# Warning about DEBUG mode
st.info(
    """
    ℹ️ **Nota**: Los endpoints de logs requieren que el sistema esté ejecutándose en modo DEBUG.

    Para habilitar, configure: `DEBUG=true` en el archivo `.env`
    """
)

api_client = get_api_client()

# Log Statistics
st.markdown("## 📊 Estadísticas de Logs")

log_stats = api_client.get_log_stats()

if log_stats and "data" in log_stats:
    stats = log_stats["data"]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total de Registros", format_number(stats.get("total_logs", 0)))

    with col2:
        st.metric("Errores", format_number(stats.get("error_count", 0)), delta="⚠️")

    with col3:
        st.metric("Avisos", format_number(stats.get("warning_count", 0)), delta="⚠️")

    with col4:
        st.metric("Info", format_number(stats.get("info_count", 0)), delta="ℹ️")

    # Log level distribution chart
    if stats:
        level_counts = {
            "ERROR": stats.get("error_count", 0),
            "WARNING": stats.get("warning_count", 0),
            "INFO": stats.get("info_count", 0),
        }
        remder_log_level_distribution(level_counts)

st.markdown("---")

# Recent Errors
st.markdown("## ❌ Errores Recientes")

recent_errors = api_client.get_recent_errors(limit=10)

if recent_errors and "data" in recent_errors:
    errors = recent_errors["data"]

    if errors:
        for error in errors:
            with st.expander(f"🔴 {error.get('timestamp', 'N/A')} - {error.get('message', 'No message')[:100]}..."):
                st.markdown(f"**Timestamp**: {format_datetime(error.get('timestamp'))}")
                st.markdown(f"**Level**: {error.get('level', 'N/A')}")
                st.markdown(f"**Source**: {error.get('source', 'N/A')}")
                st.markdown(f"**Message**:")
                st.code(error.get("message", "No message available"))

                if "stacktrace" in error:
                    st.markdown("**Stacktrace**:")
                    st.code(error.get("stacktrace"))
    else:
        st.success("✅ Ningún error reciente!")

else:
    st.info("ℹ️ No se pudo cargar errores recientes (verifique si DEBUG mode está habilitado)")

st.markdown("---")

# Log Search and Filter
st.markdown("## 🔍 Buscar y Filtrar Logs")

with st.form("log_search_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        log_level = st.selectbox(
            "Nivel",
            options=list(LOG_LEVELS.keys()),
            index=0,
            help="Filtrar por nivel de log",
        )

    with col2:
        search_term = st.text_input("Buscar en el mensaje", placeholder="Escriba un término de búsqueda...", help="Buscar texto en los mensajes de log")

    with col3:
        limit = st.number_input("Límite de resultados", min_value=10, max_value=500, value=100, step=10, help="Número máximo de logs a mostrar")

    search_submitted = st.form_submit_button("🔍 Buscar", use_container_width=True)

if search_submitted:
    level_filter = LOG_LEVELS[log_level]
    search_filter = search_term if search_term else None

    logs_result = api_client.search_logs(level=level_filter, limit=limit, search=search_filter)

    if logs_result and "data" in logs_result:
        logs = logs_result["data"]

        if logs:
            st.success(f"✅ Encontrados {len(logs)} logs")

            # Convert to DataFrame for better display
            df = pd.DataFrame(logs)

            # Color code by level
            def highlight_level(row):
                level = row.get("level", "INFO")
                color = LOG_LEVEL_COLORS.get(level, "#ffffff")
                return [f"background-color: {color}20"] * len(row)

            # Display as table
            st.dataframe(
                df[["timestamp", "level", "source", "message"]],
                use_container_width=True,
                height=600,
            )

            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar como CSV",
                data=csv,
                file_name=f"logs_{format_datetime(pd.Timestamp.now(), 'iso')}.csv",
                mime="text/csv",
            )

        else:
            st.info("ℹ️ Ningún log encontrado con los filtros especificados")

    else:
        st.warning("⚠️ No se pudo buscar logs (verifique si DEBUG mode está habilitado)")

st.markdown("---")

# Recent Logs (Auto-refresh)
st.markdown("## 📜 Logs Recientes (Últimos 50)")

recent_logs = api_client.get_recent_logs(limit=50)

if recent_logs and "data" in recent_logs:
    logs = recent_logs["data"]

    if logs:
        # Display in reverse chronological order
        for log in reversed(logs):
            level = log.get("level", "INFO")
            timestamp = log.get("timestamp", "N/A")
            message = log.get("message", "No message")
            source = log.get("source", "N/A")

            # Color code based on level
            if level == "ERROR":
                color = "red"
                icon = "🔴"
            elif level == "WARNING":
                color = "orange"
                icon = "🟡"
            else:
                color = "blue"
                icon = "🔵"

            with st.container():
                st.markdown(
                    f":{color}[{icon} **{level}**] `{format_datetime(timestamp, 'display')}` | **{source}**"
                )
                st.text(message[:200] + ("..." if len(message) > 200 else ""))
                st.divider()

    else:
        st.info("ℹ️ Ningún log reciente disponible")

else:
    st.info("ℹ️ Logs recientes no disponibles (DEBUG mode requerido)")

# Refresh button
if st.button("🔄 Actualizar Logs", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
