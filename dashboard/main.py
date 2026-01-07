"""
RMS-Shopify Integration Dashboard - Main Entry Point

This is the home page of the dashboard showing an overview of the system.
"""

import sys
from pathlib import Path

# Ensure dashboard module is importable (required for Streamlit in Docker)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import time
from datetime import datetime

import streamlit as st

from app.version import VERSION, check_for_updates_sync, version_string
from dashboard.components.health_cards import remder_health_indicators, remder_system_health_card, remder_uptime_card
from dashboard.components.metrics_display import (
    remder_order_polling_metrics_card,
    remder_reverse_sync_status,
    remder_sync_metrics_card,
    remder_system_resources_card,
)
from dashboard.components.sync_controls import remder_quick_actions
from dashboard.utils.api_client import get_api_client
from dashboard.utils.constants import DEFAULT_CONFIG, REFRESH_INTERVALS
from dashboard.utils.formatters import format_datetime

# Page configuration
st.set_page_config(
    page_title=DEFAULT_CONFIG["page_title"],
    page_icon=DEFAULT_CONFIG["page_icon"],
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize API client
api_client = get_api_client()


def main():
    """Main dashboard function."""

    # Header
    st.markdown('<h1 class="main-header">🛍️ RMS-Shopify Integration Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuraciones")

        # Version badge in sidebar
        st.markdown("### 📦 Versión")
        st.info(f"**{version_string()}**")

        # Check for updates
        update_info = check_for_updates_sync()
        if update_info.get("update_available"):
            st.warning(
                f"🔄 **Actualización disponible**\n\n"
                f"Nueva versión: **v{update_info.get('latest_version')}**\n\n"
                f"[Ver release notes]({update_info.get('release_url')})"
            )
        elif update_info.get("error"):
            # Silently skip if error (GitHub not configured)
            pass
        else:
            st.success("✅ Versión actual")

        st.markdown("---")

        # Auto-refresh settings
        st.markdown("### 🔄 Auto-Refresh")
        refresh_option = st.selectbox(
            "Intervalo de actualización",
            options=list(REFRESH_INTERVALS.keys()),
            index=2,  # Default to 30s
            help="Intervalo automático de actualización de los datos",
        )

        refresh_interval = REFRESH_INTERVALS[refresh_option]

        if refresh_interval > 0:
            st.info(f"⏱️ Actualizando cada {refresh_option}")

        # Manual refresh button
        if st.button("🔄 Actualizar Ahora", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        # API connection status
        st.markdown("### 🔗 Conexión API")
        st.text(f"Base URL: {api_client.base_url}")
        st.text(f"Timeout: {api_client.timeout}s")

        # Last update timestamp
        st.markdown("### 🕐 Última Actualización")
        current_time = datetime.now()
        st.text(format_datetime(current_time))

    # Main content area
    try:
        # Get all required data
        health_data = api_client.get_health()
        sync_data = api_client.get_sync_status()
        order_polling_data = api_client.get_order_polling_status()
        system_metrics = api_client.get_system_metrics()

        # System Health Section
        st.markdown("## 🏥 Estado del Sistema")

        col1, col2 = st.columns([2, 1])

        with col1:
            remder_system_health_card(health_data)

        with col2:
            remder_uptime_card(health_data)

        # Health indicators
        remder_health_indicators(health_data)

        st.markdown("---")

        # Sync Metrics Section
        st.markdown("## 📊 Métricas de Sincronización")

        # RMS to Shopify sync
        remder_sync_metrics_card(sync_data)

        st.markdown("---")

        # Order Polling
        remder_order_polling_metrics_card(order_polling_data)

        st.markdown("---")

        # Reverse Stock Sync
        remder_reverse_sync_status(sync_data)

        st.markdown("---")

        # System Resources
        st.markdown("## 🖥️ Recursos del Sistema")
        remder_system_resources_card(system_metrics)

        st.markdown("---")

        # Quick Actions
        remder_quick_actions()

        # Auto-refresh logic
        if refresh_interval > 0:
            time.sleep(refresh_interval)
            st.rerun()

    except Exception as e:
        st.error(f"❌ Error al cargar dashboard: {str(e)}")
        st.info("ℹ️ Verifique si la API está ejecutando y accesible.")

        if st.button("🔄 Intentar Nuevamente"):
            st.rerun()


# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Desarrollado por**: OneClick")

with col2:
    st.markdown(f"**Versión**: {VERSION}")

with col3:
    st.markdown(f"**Actualizado**: {format_datetime(datetime.now(), 'display_short')}")


if __name__ == "__main__":
    main()
