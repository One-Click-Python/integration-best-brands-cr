"""
Sync Management Page - Manual sync controls and checkpoint management.
"""

import streamlit as st

from dashboard.components.sync_controls import (
    remder_checkpoint_manager,
    remder_collection_sync_controls,
    remder_sync_interval_config,
    remder_sync_trigger_buttons,
)
from dashboard.utils.api_client import get_api_client

st.set_page_config(
    page_title="Sync Management - RMS-Shopify Dashboard",
    page_icon="🔄",
    layout="wide",
)

st.title("🔄 Gestión de Sincronización")
st.markdown("---")

api_client = get_api_client()

# Manual Sync Controls
st.markdown("## 🎮 Controles Manuales")
remder_sync_trigger_buttons()

st.markdown("---")

# Sync Interval Configuration
st.markdown("## ⏱️ Configuración de Intervalo")
remder_sync_interval_config()

st.markdown("---")

# Checkpoint Management
st.markdown("## 📍 Gestión de Checkpoints")

checkpoint_data = api_client.get_checkpoint_list()

if checkpoint_data and checkpoint_data.get("status") == "success":
    checkpoints = checkpoint_data.get("data", {}).get("checkpoints", [])
    remder_checkpoint_manager(checkpoints)
else:
    st.info("ℹ️ No se pudo cargar checkpoints")

st.markdown("---")

# Collection Sync Controls (if enabled)
st.markdown("## 📚 Sincronización de Colecciones")

with st.expander("ℹ️ Sobre Sincronización de Colecciones"):
    st.markdown(
        """
        Las colecciones de Shopify son creadas automáticamente basadas en las categorías de RMS.

        **Opções:**
        - **Coleções Principais**: Crea colecciones para familias principais (ex: Zapatos, Ropa)
        - **Subcategorias**: Crea colecciones para subcategorias (ex: Tenis, Botas, Sandalias)
        - **Dry-run**: Executa sin hacer cambios (apenas para teste)

        **Nota**: Asegúrese de que `SYNC_ENABLE_COLLECTIONS=true` no `.env`
        """
    )

remder_collection_sync_controls()

st.markdown("---")

# Curremt Sync Status
st.markdown("## 📊 Estado Actual de Sincronización")

sync_status = api_client.get_sync_status()

if sync_status and sync_status.get("status") == "success":
    data = sync_status["data"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Monitoreo",
            "Activo" if data.get("monitoring_active") else "Inactivo",
            delta="🟢" if data.get("monitoring_active") else "🔴",
        )

    with col2:
        st.metric(
            "Detección de Cambios",
            "Habilitado" if data.get("change_detection_enabled") else "Deshabilitado",
            delta="🟢" if data.get("change_detection_enabled") else "🔴",
        )

    with col3:
        interval = data.get("sync_interval_minutes", 0)
        st.metric("Intervalo", f"{interval} min", delta="⏱️")

    # Change Detector Stats
    change_detector = data.get("change_detector", {})

    if change_detector:
        st.markdown("### 🔍 Estadísticas del Detector de Cambios")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total de Verificaciones", change_detector.get("total_checks", 0))

        with col2:
            st.metric("Cambios Detectados", change_detector.get("changes_detected", 0))

        with col3:
            st.metric("Ítems Sincronizados", change_detector.get("items_synced", 0))

        with col4:
            last_check = change_detector.get("last_check_time")
            if last_check:
                from dashboard.utils.formatters import time_ago

                st.metric("Última Verificación", time_ago(last_check))
            else:
                st.metric("Última Verificación", "N/A")

else:
    st.warning("⚠️ No se pudo cargar status de sincronización")

# Refresh button
if st.button("🔄 Actualizar Página", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
