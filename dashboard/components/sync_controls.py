"""
Sync control buttons and forms for manual operations.
"""

import streamlit as st

from dashboard.utils.api_client import get_api_client
from dashboard.utils.constants import SYNC_TYPES


def remder_sync_trigger_buttons() -> None:
    """Render sync trigger buttons for manual sync operations."""
    st.markdown("#### Controles Manuales de Sincronización")

    col1, col2, col3 = st.columns(3)

    api_client = get_api_client()

    with col1:
        if st.button("🔄 Sincronización Incremental", help="Sincroniza solo ítems modificados", use_container_width=True):
            with st.spinner("Ejecutando sincronización incremental..."):
                result = api_client.trigger_sync(sync_type="incremental")

                if result and result.get("status") == "success":
                    st.success("✅ Sincronización incremental iniciada con éxito!")
                    st.json(result.get("data", {}))
                else:
                    st.error("❌ Error al iniciar sincronización")

    with col2:
        if st.button("🔄 Sincronización Completa", help="Sincroniza todos los ítems", use_container_width=True, type="primary"):
            # Add confirmation
            if "confirm_full_sync" not in st.session_state:
                st.session_state.confirm_full_sync = False

            if not st.session_state.confirm_full_sync:
                st.warning("⚠️ Esto va a sincronizar TODOS los ítems. Haga clic nuevamente para confirmar.")
                st.session_state.confirm_full_sync = True
            else:
                with st.spinner("Ejecutando sincronización completa..."):
                    result = api_client.trigger_sync(sync_type="full")

                    if result and result.get("status") == "success":
                        st.success("✅ Sincronización completa iniciada con éxito!")
                        st.json(result.get("data", {}))
                    else:
                        st.error("❌ Error al iniciar sincronización")

                    st.session_state.confirm_full_sync = False

    with col3:
        if st.button("🔁 Sincronización Reversa", help="Shopify → RMS (stock)", use_container_width=True):
            with st.spinner("Ejecutando sincronización reversa..."):
                result = api_client.trigger_reverse_stock_sync(dry_run=False)

                if result and result.get("status") == "success":
                    st.success("✅ Sincronización reversa iniciada!")
                    st.json(result.get("data", {}))
                else:
                    st.error("❌ Error al iniciar sincronización reversa")


def remder_order_polling_controls() -> None:
    """Render order polling control buttons."""
    st.markdown("#### Controles de Polling de Pedidos")

    col1, col2, col3 = st.columns(3)

    api_client = get_api_client()

    with col1:
        if st.button("📦 Polling Manual", help="Ejecutar polling de pedidos ahora", use_container_width=True):
            with st.spinner("Ejecutando polling de pedidos..."):
                result = api_client.trigger_order_polling()

                if result and result.get("status") == "success":
                    st.success("✅ Polling de pedidos ejecutado!")
                    data = result.get("data", {})
                    stats = data.get("statistics", {})

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Total Consultado", stats.get("total_polled", 0))
                    with col_b:
                        st.metric("Nuevos Sincronizados", stats.get("newly_synced", 0))
                    with col_c:
                        st.metric("Errores", stats.get("sync_errors", 0))
                else:
                    st.error("❌ Falla en el polling de pedidos")

    with col2:
        if st.button("🧪 Dry-Run Polling", help="Probar sin hacer cambios", use_container_width=True):
            with st.spinner("Ejecutando dry-run..."):
                result = api_client.trigger_order_polling(dry_run=True)

                if result and result.get("status") == "success":
                    st.info("ℹ️ Dry-run ejecutado (sin cambios)")
                    st.json(result.get("data", {}))
                else:
                    st.error("❌ Falla en el dry-run")

    with col3:
        if st.button("🔄 Reiniciar Estadísticas", help="Limpiar estadísticas de polling", use_container_width=True):
            if st.confirm("¿Desea realmente resetear las estadísticas de polling?"):
                result = api_client.reset_order_polling_stats()

                if result and result.get("status") == "success":
                    st.success("✅ Estadísticas resetadas!")
                else:
                    st.error("❌ Error al resetar estadísticas")


def remder_sync_interval_config() -> None:
    """Render sync interval configuration form."""
    st.markdown("#### Configurar Intervalo de Sincronización")

    api_client = get_api_client()

    # Get current config
    config = api_client.get_sync_config()
    current_interval = 15  # Default

    if config and "data" in config:
        current_interval = config["data"].get("sync_interval_minutes", 15)

    with st.form("sync_interval_form"):
        st.write(f"**Intervalo actual**: {current_interval} minutos")

        new_interval = st.slider(
            "Nuevo intervalo (minutos)",
            min_value=1,
            max_value=60,
            value=current_interval,
            step=1,
            help="Intervalo entre sincronizaciones automáticas",
        )

        submitted = st.form_submit_button("💾 Actualizar Intervalo", use_container_width=True)

        if submitted:
            if new_interval != current_interval:
                result = api_client.update_sync_interval(new_interval)

                if result and result.get("status") == "success":
                    st.success(f"✅ Intervalo actualizado para {new_interval} minutos!")
                    st.rerun()
                else:
                    st.error("❌ Error al actualizar intervalo")
            else:
                st.info("ℹ️ Intervalo no fue modificado")


def remder_checkpoint_manager(checkpoints: list[dict]) -> None:
    """
    Render checkpoint management interface.

    Args:
        checkpoints: List of checkpoint data
    """
    if not checkpoints:
        st.info("ℹ️ Ningún checkpoint activo en este momento")
        return

    st.markdown("#### Gestionar Checkpoints")

    api_client = get_api_client()

    for checkpoint in checkpoints:
        sync_id = checkpoint.get("sync_id", "unknown")
        status = checkpoint.get("status", "unknown")
        processed = checkpoint.get("processed_items", 0)
        total = checkpoint.get("total_items", 0)

        progress = (processed / total * 100) if total > 0 else 0

        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                st.markdown(f"**{sync_id}**")
                st.progress(progress / 100)

            with col2:
                st.metric("Estado", status)

            with col3:
                st.metric("Progreso", f"{processed}/{total}")

            with col4:
                sub_col1, sub_col2 = st.columns(2)

                with sub_col1:
                    if status == "in_progress" and st.button("▶️ Reanudar", key=f"resume_{sync_id}"):
                        result = api_client.resume_checkpoint(sync_id)
                        if result:
                            st.success("✅ Checkpoint retomado!")
                            st.rerun()

                with sub_col2:
                    if st.button("🗑️ Eliminar", key=f"delete_{sync_id}"):
                        result = api_client.delete_checkpoint(sync_id)
                        if result:
                            st.success("✅ Checkpoint eliminado!")
                            st.rerun()

            st.divider()


def remder_collection_sync_controls() -> None:
    """Render collection sync controls."""
    st.markdown("#### Sincronización de Colecciones")

    api_client = get_api_client()

    with st.form("collection_sync_form"):
        col1, col2 = st.columns(2)

        with col1:
            sync_main = st.checkbox("Sincronizar colecciones principales", value=True)
            dry_run = st.checkbox("Dry-run (probar sin hacer cambios)", value=False)

        with col2:
            sync_subcategories = st.checkbox("Sincronizar subcategorias", value=True)

        submitted = st.form_submit_button("🔄 Sincronizar Colecciones", use_container_width=True)

        if submitted:
            with st.spinner("Sincronizando colecciones..."):
                result = api_client.sync_collections(dry_run=dry_run, sync_main=sync_main, sync_subcategories=sync_subcategories)

                if result and result.get("status") == "success":
                    if dry_run:
                        st.info("ℹ️ Dry-run ejecutado (sin cambios)")
                    else:
                        st.success("✅ Colecciones sincronizadas con éxito!")

                    st.json(result.get("data", {}))
                else:
                    st.error("❌ Error al sincronizar colecciones")


def remder_quick_actions() -> None:
    """Render quick action buttons for common operations."""
    st.markdown("#### Acciones Rápidas")

    api_client = get_api_client()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Reiniciar Métricas", help="Limpiar todas las métricas", use_container_width=True):
            result = api_client.reset_metrics()
            if result and result.get("status") == "success":
                st.success("✅ Métricas resetadas!")
            else:
                st.error("❌ Error al resetar métricas")

    with col2:
        if st.button("🔧 Reiniciar Circuit Breakers", help="Reiniciar protecciones de circuit breaker", use_container_width=True):
            result = api_client.reset_circuit_breakers()
            if result and result.get("status") == "success":
                st.success("✅ Circuit breakers resetados!")
            else:
                st.error("❌ Error al resetar circuit breakers")

    with col3:
        if st.button("🔄 Recargar Página", help="Recargar datos de la página", use_container_width=True):
            st.rerun()
