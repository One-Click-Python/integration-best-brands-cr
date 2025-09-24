import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.utils.error_handler import ErrorAggregator

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates sync reports and recommendations."""

    def __init__(self, sync_id: str, error_aggregator: ErrorAggregator):
        self.sync_id = sync_id
        self.error_aggregator = error_aggregator

    def generate_sync_report(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera reporte final de sincronización.

        Args:
            stats: Estadísticas de sincronización

        Returns:
            Dict: Reporte completo
        """
        error_summary = self.error_aggregator.get_summary()

        report = {
            "sync_id": self.sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": stats,
            "errors": error_summary,
            "success_rate": ((stats["total_processed"] - stats["errors"]) / max(stats["total_processed"], 1) * 100),
            "recommendations": self._generate_recommendations(stats, error_summary),
        }

        # Log reporte final mejorado
        logger.info(
            f"🎉 Sync completed - ID: {self.sync_id} | "
            f"✅ {stats['created']} created, 🔄 {stats['updated']} updated, "
            f"⏭️ {stats['skipped']} skipped, ❌ {stats['errors']} errors | "
            f"Success rate: {report['success_rate']:.1f}%"
        )

        return report

    def _generate_recommendations(self, stats: Dict[str, Any], error_summary: Dict[str, Any]) -> List[str]:
        """
        Genera recomendaciones basadas en resultados.

        Args:
            stats: Estadísticas de sync
            error_summary: Resumen de errores

        Returns:
            List: Lista de recomendaciones
        """
        recommendations = []

        if error_summary["error_count"] > 0:
            recommendations.append("Review error logs and fix data quality issues")

        if stats["skipped"] > stats["updated"]:
            recommendations.append("Consider force update if products seem outdated")

        if error_summary["error_count"] / max(stats["total_processed"], 1) > 0.1:
            recommendations.append("High error rate detected - review data mapping")

        return recommendations