"""
Sistema de checkpoints para sincronización RMS-Shopify.

Gestiona el guardado y recuperación del progreso de sincronización,
permitiendo reanudar operaciones interrumpidas.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SyncCheckpointManager:
    """
    Gestor de checkpoints para sincronización.

    Guarda el progreso en Redis para recuperación rápida y
    en archivo local como respaldo.
    """

    def __init__(self, sync_id: str):
        """
        Inicializa el gestor de checkpoints.

        Args:
            sync_id: Identificador único de la sincronización
        """
        self.sync_id = sync_id
        self.redis_client = None
        self.checkpoint_dir = Path("checkpoints")
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / f"{sync_id}.json"
        self.redis_key = f"sync:checkpoint:{sync_id}"

        # Configuration attributes that can be set externally
        self.resume_from_checkpoint: bool = True
        self.checkpoint_frequency: int = 100
        self.force_fresh_start: bool = False

    async def initialize(self):
        """Inicializa la conexión con Redis si está disponible."""
        # Verificar que el directorio de checkpoints exista
        logger.info(f"🗂️ Ensuring checkpoint directory exists: {self.checkpoint_dir}")
        self.checkpoint_dir.mkdir(exist_ok=True)

        try:
            if settings.REDIS_URL:
                self.redis_client = await redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
                # Test the connection
                await self.redis_client.ping()
                logger.info(f"📡 Checkpoint manager initialized with Redis for sync {self.sync_id}")
            else:
                logger.info(f"📁 Checkpoint manager initialized with file backup only for sync {self.sync_id}")
                self.redis_client = None
        except Exception as e:
            logger.debug(f"Redis not available, using file-based checkpoints only: {e}")
            self.redis_client = None

    async def save_checkpoint(
        self,
        last_processed_ccod: str,
        processed_count: int,
        total_count: int,
        stats: Dict[str, int],
        batch_number: int = 0,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Guarda un checkpoint del progreso actual.

        Args:
            last_processed_ccod: Último CCOD procesado exitosamente
            processed_count: Cantidad de productos procesados
            total_count: Total de productos a procesar
            stats: Estadísticas de la sincronización
            batch_number: Número del lote actual
            additional_data: Datos adicionales opcionales

        Returns:
            True si se guardó exitosamente
        """
        checkpoint_data = {
            "sync_id": self.sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_processed_ccod": last_processed_ccod,
            "processed_count": processed_count,
            "total_count": total_count,
            "batch_number": batch_number,
            "progress_percentage": (processed_count / total_count * 100) if total_count > 0 else 0,
            "stats": stats,
            "additional_data": additional_data or {},
        }

        try:
            # Guardar en Redis si está disponible
            if self.redis_client:
                await self.redis_client.setex(
                    self.redis_key,
                    86400,  # TTL de 24 horas
                    json.dumps(checkpoint_data),
                )
                logger.debug(f"Checkpoint saved to Redis: {processed_count}/{total_count} products")

            # Siempre guardar en archivo como respaldo
            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.debug(f"💾 Checkpoint file saved: {self.checkpoint_file}")

            # Log de progreso cada 10% o cada 1000 productos
            if processed_count % 1000 == 0 or (processed_count % max(total_count // 10, 1) == 0):
                logger.info(
                    f"💾 [PROGRESS CHECKPOINT] Saved - Progress: {processed_count}/{total_count} "
                    f"({checkpoint_data['progress_percentage']:.1f}%) - "
                    f"Last CCOD: {last_processed_ccod} - File: {self.checkpoint_file}"
                )

            return True

        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return False

    async def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Carga el último checkpoint disponible.

        Returns:
            Datos del checkpoint o None si no existe
        """
        try:
            # Intentar cargar desde Redis primero (si está disponible)
            if self.redis_client:
                try:
                    data = await self.redis_client.get(self.redis_key)
                    if data:
                        checkpoint = json.loads(data)
                        logger.info(
                            f"📂 [PROGRESS CHECKPOINT] Loaded from Redis: {checkpoint['processed_count']}/{checkpoint['total_count']}"
                        )
                        return checkpoint
                except Exception as redis_error:
                    logger.debug(f"Could not load from Redis: {redis_error}")

            # Si no está en Redis, cargar desde archivo
            if self.checkpoint_file.exists():
                with open(self.checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                logger.info(f"📂 [PROGRESS CHECKPOINT] Loaded from file: {checkpoint['processed_count']}/{checkpoint['total_count']}")
                return checkpoint

            logger.debug(f"ℹ️ [PROGRESS CHECKPOINT] No checkpoint found for sync {self.sync_id} - Starting fresh")
            return None

        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None

    async def delete_checkpoint(self) -> bool:
        """
        Elimina el checkpoint al completar la sincronización.

        Returns:
            True si se eliminó exitosamente
        """
        try:
            # Eliminar de Redis
            if self.redis_client:
                await self.redis_client.delete(self.redis_key)

            # Eliminar archivo
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()

            logger.info(f"Checkpoint deleted for sync {self.sync_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting checkpoint: {e}")
            return False

    async def get_progress_info(self) -> Dict[str, Any]:
        """
        Obtiene información detallada del progreso actual.

        Returns:
            Diccionario con información del progreso
        """
        checkpoint = await self.load_checkpoint()

        if not checkpoint:
            return {"status": "not_started", "sync_id": self.sync_id, "message": "No sync in progress"}

        # Calcular tiempo estimado
        now = datetime.now(timezone.utc)
        start_time = datetime.fromisoformat(checkpoint["timestamp"].replace("Z", "+00:00"))
        elapsed = (now - start_time).total_seconds()
        processed = checkpoint["processed_count"]
        total = checkpoint["total_count"]

        if processed > 0:
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            eta_seconds = remaining / rate if rate > 0 else 0
        else:
            rate = 0
            eta_seconds = 0

        return {
            "status": "in_progress",
            "sync_id": self.sync_id,
            "processed": processed,
            "total": total,
            "progress_percentage": checkpoint["progress_percentage"],
            "last_ccod": checkpoint["last_processed_ccod"],
            "batch_number": checkpoint.get("batch_number", 0),
            "stats": checkpoint["stats"],
            "elapsed_seconds": elapsed,
            "eta_seconds": eta_seconds,
            "processing_rate": rate,
            "timestamp": checkpoint["timestamp"],
        }

    async def should_resume(self) -> bool:
        """
        Determina si existe un checkpoint válido para reanudar.

        Returns:
            True si se puede reanudar desde checkpoint
        """
        checkpoint = await self.load_checkpoint()

        if not checkpoint:
            return False

        # Verificar que el checkpoint no sea muy viejo (>24 horas)
        try:
            checkpoint_time = datetime.fromisoformat(checkpoint["timestamp"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - checkpoint_time).total_seconds() / 3600

            if age_hours > 24:
                logger.warning(f"Checkpoint is {age_hours:.1f} hours old, ignoring")
                return False

            return checkpoint["processed_count"] < checkpoint["total_count"]

        except Exception as e:
            logger.error(f"Error checking checkpoint validity: {e}")
            return False

    async def close(self):
        """Cierra las conexiones."""
        try:
            if self.redis_client:
                await self.redis_client.close()
        except Exception as e:
            logger.error(f"Error closing checkpoint manager: {e}")

