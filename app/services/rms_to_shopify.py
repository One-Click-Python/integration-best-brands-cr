"""
Microservicio de sincronización RMS → Shopify.

Este módulo maneja la sincronización de productos, inventarios y precios
desde Microsoft Retail Management System hacia Shopify.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.rms_to_shopify.sync_orchestrator import RMSToShopifySyncOrchestrator

logger = logging.getLogger(__name__)


async def sync_rms_to_shopify(
    force_update: bool = False,
    batch_size: int = None,
    filter_categories: Optional[List[str]] = None,
    include_zero_stock: bool = False,
    ccod: Optional[str] = None,
    resume_from_checkpoint: bool = True,
    checkpoint_frequency: int = 100,
    force_fresh_start: bool = False,
    sync_id: Optional[str] = None,
    use_streaming: bool = True,
    page_size: int = 500,
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronización RMS → Shopify.

    Args:
        force_update: Forzar actualización
        batch_size: Tamaño del lote para procesamiento
        filter_categories: Categorías a filtrar
        include_zero_stock: Incluir productos sin stock
        ccod: CCOD específico a sincronizar (opcional)
        resume_from_checkpoint: Reanudar desde checkpoint si existe
        checkpoint_frequency: Frecuencia de guardado de checkpoint
        force_fresh_start: Forzar inicio desde cero ignorando checkpoints
        sync_id: ID único de la sincronización (se genera automáticamente si no se proporciona)
        use_streaming: Usar procesamiento por streaming (recomendado para grandes volúmenes)
        page_size: Tamaño de página para extracción de RMS

    Returns:
        Dict: Resultado de la sincronización con información de checkpoint
    """
    sync_service = RMSToShopifySyncOrchestrator(sync_id=sync_id)

    try:
        await sync_service.initialize()

        sync_service.checkpoint_manager.resume_from_checkpoint = resume_from_checkpoint
        sync_service.checkpoint_manager.checkpoint_frequency = checkpoint_frequency
        sync_service.checkpoint_manager.force_fresh_start = force_fresh_start

        result = await sync_service.sync_products(
            force_update=force_update,
            batch_size=batch_size,
            filter_categories=filter_categories,
            include_zero_stock=include_zero_stock,
            cod_product=ccod,
            use_streaming=use_streaming,
            page_size=page_size,
        )
        return result

    finally:
        await sync_service.close()


async def get_sync_status() -> Dict[str, Any]:
    """
    Obtiene estado actual de sincronización.

    Returns:
        Dict: Estado de sincronización
    """
    return {"status": "ready", "last_sync": None, "next_scheduled": None}
