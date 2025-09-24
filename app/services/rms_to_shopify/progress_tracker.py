import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SyncProgressTracker:
    """Tracker para progreso de sincronización con ETA y métricas."""

    def __init__(self, total_items: int, operation_name: str = "Sync", sync_id: str = "unknown"):
        self.total_items = total_items
        self.operation_name = operation_name
        self.sync_id = sync_id
        self.processed_items = 0
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    def update(self, created: int = 0, updated: int = 0, skipped: int = 0, errors: int = 0):
        """Actualiza las estadísticas y el progreso."""
        self.processed_items += 1
        self.stats["created"] += created
        self.stats["updated"] += updated
        self.stats["skipped"] += skipped
        self.stats["errors"] += errors

    def get_progress_info(self) -> Dict[str, Any]:
        """Obtiene información completa del progreso."""
        current_time = time.time()
        elapsed = current_time - self.start_time

        if self.processed_items == 0:
            return {"percentage": 0.0, "eta_seconds": 0, "rate_per_minute": 0.0, "elapsed_str": "00:00:00"}

        percentage = (self.processed_items / self.total_items) * 100
        rate_per_minute = (self.processed_items / elapsed) * 60 if elapsed > 0 else 0

        remaining_items = self.total_items - self.processed_items
        eta_seconds = (remaining_items / rate_per_minute) * 60 if rate_per_minute > 0 else 0

        return {
            "percentage": percentage,
            "eta_seconds": eta_seconds,
            "rate_per_minute": rate_per_minute,
            "elapsed_str": self._format_duration(elapsed),
            "eta_str": self._format_duration(eta_seconds),
            "processed": self.processed_items,
            "total": self.total_items,
        }

    def should_log_progress(self, force: bool = False) -> bool:
        """Determina si debe hacer log del progreso (cada 10% o cada 30 segundos)."""
        current_time = time.time()
        progress_info = self.get_progress_info()

        # Log cada 10% de progreso o cada 30 segundos
        percentage_milestone = int(progress_info["percentage"]) % 10 == 0
        time_milestone = (current_time - self.last_log_time) >= 30

        if force or percentage_milestone or time_milestone:
            self.last_log_time = current_time
            return True
        return False

    def log_progress(self, prefix: str = ""):
        """Hace log del progreso actual."""
        info = self.get_progress_info()

        logger.info(
            f"{prefix}📊 {self.operation_name} [sync_id: {self.sync_id}]: "
            f"{info['processed']}/{info['total']} ({info['percentage']:.1f}%) | "
            f"⏱️ {info['elapsed_str']} elapsed, ETA: {info['eta_str']} | "
            f"⚡ {info['rate_per_minute']:.1f}/min | "
            f"✅ {self.stats['created']} created, "
            f"🔄 {self.stats['updated']} updated, "
            f"⏭️ {self.stats['skipped']} skipped, "
            f"❌ {self.stats['errors']} errors"
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Formatea duración en formato HH:MM:SS."""
        if seconds < 0:
            return "00:00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"