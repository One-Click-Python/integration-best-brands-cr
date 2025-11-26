"""
Orders Management Page - Order polling status and controls.
"""

import streamlit as st

from ..components.charts import remder_success_rate_gauge, remder_sync_stats_comparison
from ..components.sync_controls import remder_order_polling_controls
from ..utils.api_client import get_api_client
from ..utils.formatters import format_number, format_percentage, time_ago

st.set_page_config(
    page_title="Orders - RMS-Shopify Dashboard",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Gestión de Pedidos")
st.markdown("---")

api_client = get_api_client()

# Order Polling Controls
st.markdown("## 🎮 Controles de Polling")
remder_order_polling_controls()

st.markdown("---")

# Order Polling Status
st.markdown("## 📊 Status de Polling de Pedidos")

polling_status = api_client.get_order_polling_status()

if polling_status and polling_status.get("status") == "success":
    data = polling_status["data"]
    stats = data.get("statistics", {})

    # Configuration info
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        enabled = data.get("enabled", False)
        st.metric(
            "Estado",
            "Habilitado" if enabled else "Deshabilitado",
            delta="🟢" if enabled else "🔴",
        )

    with col2:
        interval = data.get("interval_minutes", 0)
        st.metric("Intervalo", f"{interval} min", delta="⏱️")

    with col3:
        lookback = data.get("lookback_minutes", 0)
        st.metric("Ventana de Consulta", f"{lookback} min", delta="🔍")

    with col4:
        batch_size = data.get("batch_size", 0)
        st.metric("Tamaño del Lote", batch_size, delta="📦")

    st.markdown("---")

    # Statistics
    st.markdown("### 📈 Estadísticas de Sincronización")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total = stats.get("total_polled", 0)
        st.metric("Total Consultado", format_number(total))

    with col2:
        already_synced = stats.get("already_synced", 0)
        st.metric("Ya Sincronizados", format_number(already_synced))

    with col3:
        newly_synced = stats.get("newly_synced", 0)
        st.metric("Nuevos", format_number(newly_synced), delta="+")

    with col4:
        updated = stats.get("updated", 0)
        st.metric("Actualizados", format_number(updated), delta="↻")

    with col5:
        errors = stats.get("sync_errors", 0)
        st.metric("Erros", format_number(errors), delta="⚠️" if errors > 0 else "✓")

    # Success Rate Gauge
    success_rate = stats.get("success_rate", 0)

    col1, col2 = st.columns(2)

    with col1:
        remder_success_rate_gauge(success_rate, "Tasa de Éxito de Sincronización")

    with col2:
        # Stats comparison chart
        remder_sync_stats_comparison(
            total_polled=total,
            newly_synced=newly_synced,
            updated=updated,
            already_synced=already_synced,
            errors=errors,
        )

    st.markdown("---")

    # Timing Information
    st.markdown("### ⏱️ Información de Tiempo")

    col1, col2, col3 = st.columns(3)

    with col1:
        last_poll = stats.get("last_poll_time")
        if last_poll:
            st.metric("Última Consulta", time_ago(last_poll))
        else:
            st.metric("Última Consulta", "N/A")

    with col2:
        will_execute = data.get("will_execute_next_cycle", False)
        st.metric(
            "Próximo Ciclo",
            "Sí" if will_execute else "No",
            delta="🟢" if will_execute else "🔴",
        )

    with col3:
        seconds_until = data.get("seconds_until_next_poll", 0)
        if seconds_until is not None and seconds_until > 0:
            from ..utils.formatters import format_timedelta

            st.metric("Tiempo hasta el Próximo Poll", format_timedelta(seconds_until))
        else:
            st.metric("Tiempo hasta el Próximo Poll", "Esperando")

    # Advanced Configuration
    with st.expander("⚙️ Configuración Avanzada"):
        st.markdown("### Actualizar Configuración de Polling")

        with st.form("order_polling_config"):
            col1, col2 = st.columns(2)

            with col1:
                new_interval = st.number_input(
                    "Intervalo (minutos)",
                    min_value=1,
                    max_value=60,
                    value=interval,
                    help="Intervalo entre polling de pedidos",
                )

            with col2:
                new_lookback = st.number_input(
                    "Ventana de Consulta (minutos)",
                    min_value=5,
                    max_value=120,
                    value=lookback,
                    help="Tiempo retroativo para buscar pedidos",
                )

            submitted = st.form_submit_button("💾 Actualizar Configuración", use_container_width=True)

            if submitted:
                result = api_client.update_order_polling_config(
                    interval_minutes=new_interval, lookback_minutes=new_lookback
                )

                if result and result.get("status") == "success":
                    st.success(f"✅ Configuración atualizada!")
                    st.rerun()
                else:
                    st.error("❌ Error al actualizar configuração")

else:
    st.error("❌ No se pudo cargar estado de polling de pedidos")
    st.info("ℹ️ Verifique si el polling de pedidos está habilitado (`ENABLE_ORDER_POLLING=true`)")

# Refresh button
if st.button("🔄 Actualizar Página", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
