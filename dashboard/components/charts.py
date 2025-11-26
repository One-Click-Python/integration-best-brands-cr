"""
Interactive charts components using Plotly.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ..utils.constants import CHART_COLORS


def remder_success_rate_gauge(success_rate: float, title: str = "Tasa de Éxito") -> None:
    """
    Render a gauge chart for success rate.

    Args:
        success_rate: Success rate percentage (0-100)
        title: Chart title
    """
    # Determine color based on thresholds
    if success_rate >= 95:
        color = CHART_COLORS["success"]
    elif success_rate >= 90:
        color = CHART_COLORS["warning"]
    else:
        color = CHART_COLORS["danger"]

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=success_rate,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title, "font": {"size": 20}},
            delta={"reference": 95, "increasing": {"color": "green"}, "decreasing": {"color": "red"}},
            gauge={
                "axis": {"range": [None, 100], "tickwidth": 1, "tickcolor": "darkblue"},
                "bar": {"color": color},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 90], "color": "#ffcccc"},
                    {"range": [90, 95], "color": "#ffffcc"},
                    {"range": [95, 100], "color": "#ccffcc"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 95,
                },
            },
            number={"suffix": "%"},
        )
    )

    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))

    st.plotly_chart(fig, use_container_width=True)


def remder_resource_usage_bars(cpu: float, memory: float, disk: float) -> None:
    """
    Render horizontal bar chart for resource usage.

    Args:
        cpu: CPU usage percentage
        memory: Memory usage percentage
        disk: Disk usage percentage
    """
    resources = ["CPU", "Memoria", "Disco"]
    values = [cpu, memory, disk]

    # Assign colors based on thresholds
    colors = []
    for value in values:
        if value >= 90:
            colors.append(CHART_COLORS["danger"])
        elif value >= 70:
            colors.append(CHART_COLORS["warning"])
        else:
            colors.append(CHART_COLORS["success"])

    fig = go.Figure(
        data=[
            go.Bar(
                y=resources,
                x=values,
                orientation="h",
                marker=dict(color=colors),
                text=[f"{v:.1f}%" for v in values],
                textposition="inside",
            )
        ]
    )

    fig.update_layout(
        title="Uso de Recursos del Sistema",
        xaxis_title="Percentual (%)",
        xaxis=dict(range=[0, 100]),
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)


def remder_sync_activity_timeline(activity_data: list[dict]) -> None:
    """
    Render timeline chart for sync activities.

    Args:
        activity_data: List of activity records with timestamp and status
    """
    if not activity_data:
        st.info("📊 Ningúna atividade recente para exibir")
        return

    # Extract data
    timestamps = [record.get("timestamp") for record in activity_data]
    items_synced = [record.get("items_synced", 0) for record in activity_data]
    success = [record.get("success", False) for record in activity_data]

    # Create colors based on success
    colors = [CHART_COLORS["success"] if s else CHART_COLORS["danger"] for s in success]

    fig = go.Figure(
        data=[
            go.Bar(
                x=timestamps,
                y=items_synced,
                marker=dict(color=colors),
                text=items_synced,
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Histórico de Sincronizaciones",
        xaxis_title="Timestamp",
        yaxis_title="Ítems Sincronizados",
        height=400,
        margin=dict(l=20, r=20, t=50, b=80),
        xaxis_tickangle=-45,
    )

    st.plotly_chart(fig, use_container_width=True)


def remder_error_distribution_pie(error_counts: dict[str, int]) -> None:
    """
    Render pie chart for error distribution by type.

    Args:
        error_counts: Dictionary of error type -> count
    """
    if not error_counts or sum(error_counts.values()) == 0:
        st.info("📊 Ningún erro registrado")
        return

    labels = list(error_counts.keys())
    values = list(error_counts.values())

    fig = px.pie(
        names=labels,
        values=values,
        title="Distribuição de Erros por Tipo",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))

    st.plotly_chart(fig, use_container_width=True)


def remder_sync_stats_comparison(
    total_polled: int, newly_synced: int, updated: int, already_synced: int, errors: int
) -> None:
    """
    Render comparison chart for sync statistics.

    Args:
        total_polled: Total items polled
        newly_synced: New items synced
        updated: Itens updated
        already_synced: Itens already in sync
        errors: Sync errors
    """
    categories = ["Total Consultado", "Nuevos", "Actualizados", "Ya Sincronizados", "Erros"]
    values = [total_polled, newly_synced, updated, already_synced, errors]

    colors = [
        CHART_COLORS["info"],
        CHART_COLORS["success"],
        CHART_COLORS["primary"],
        CHART_COLORS["purple"],
        CHART_COLORS["danger"],
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=categories,
                y=values,
                marker=dict(color=colors),
                text=values,
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Estadísticas de Sincronización",
        xaxis_title="Categoria",
        yaxis_title="Quantidade",
        height=400,
        margin=dict(l=20, r=20, t=50, b=80),
        xaxis_tickangle=-15,
    )

    st.plotly_chart(fig, use_container_width=True)


def remder_combined_resource_chart(cpu_history: list, memory_history: list, disk_history: list, timestamps: list) -> None:
    """
    Render combined line chart for resource usage over time.

    Args:
        cpu_history: List of CPU usage values
        memory_history: List of memory usage values
        disk_history: List of disk usage values
        timestamps: List of timestamps
    """
    if not cpu_history or not timestamps:
        st.info("📊 Histórico de recursos no disponible")
        return

    fig = go.Figure()

    # CPU line
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=cpu_history,
            mode="lines+markers",
            name="CPU",
            line=dict(color=CHART_COLORS["primary"], width=2),
            marker=dict(size=6),
        )
    )

    # Memory line
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=memory_history,
            mode="lines+markers",
            name="Memoria",
            line=dict(color=CHART_COLORS["success"], width=2),
            marker=dict(size=6),
        )
    )

    # Disk line
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=disk_history,
            mode="lines+markers",
            name="Disco",
            line=dict(color=CHART_COLORS["warning"], width=2),
            marker=dict(size=6),
        )
    )

    # Add threshold lines
    fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Crítico (90%)")
    fig.add_hline(y=70, line_dash="dash", line_color="orange", annotation_text="Alerta (70%)")

    fig.update_layout(
        title="Uso de Recursos a lo Largo del Tiempo",
        xaxis_title="Timestamp",
        yaxis_title="Uso (%)",
        yaxis=dict(range=[0, 100]),
        height=400,
        margin=dict(l=20, r=20, t=50, b=80),
        xaxis_tickangle=-45,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def remder_log_level_distribution(log_stats: dict[str, int]) -> None:
    """
    Render bar chart for log level distribution.

    Args:
        log_stats: Dictionary of log level -> count
    """
    if not log_stats:
        st.info("📊 Sin estadísticas de log disponibles")
        return

    levels = list(log_stats.keys())
    counts = list(log_stats.values())

    # Assign colors based on log level
    color_map = {"ERROR": CHART_COLORS["danger"], "WARNING": CHART_COLORS["warning"], "INFO": CHART_COLORS["info"]}

    colors = [color_map.get(level, CHART_COLORS["primary"]) for level in levels]

    fig = go.Figure(
        data=[
            go.Bar(
                x=levels,
                y=counts,
                marker=dict(color=colors),
                text=counts,
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Distribuição de Logs por Nível",
        xaxis_title="Nível",
        yaxis_title="Quantidade",
        height=350,
        margin=dict(l=20, r=20, t=50, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)
