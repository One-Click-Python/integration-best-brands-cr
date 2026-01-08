"""
Reverse Stock Synchronization API Endpoints.

Provides endpoints for executing and monitoring the complementary
Shopify → RMS stock synchronization.
"""

import logging
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.connection import ConnDB
from app.db.rms.product_repository import ProductRepository
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.reverse_stock_sync import ReverseStockSynchronizer

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/reverse-stock-sync", tags=["Reverse Stock Sync"])

# Global state for last sync result
_last_sync_result: Optional[dict[str, Any]] = None


class ReverseStockSyncRequest(BaseModel):
    """Request model for reverse stock sync."""

    dry_run: bool = Field(default=False, description="Si True, solo simula sin hacer cambios reales")
    delete_zero_stock: bool = Field(default=True, description="Si True, elimina variantes con stock 0")
    batch_size: int = Field(default=50, ge=1, le=250, description="Número de productos por batch")
    limit: Optional[int] = Field(default=None, ge=1, description="Límite total de productos a procesar (None = todos)")


class ReverseStockSyncResponse(BaseModel):
    """Response model for reverse stock sync."""

    success: bool
    message: str
    sync_id: str
    report: Optional[dict[str, Any]] = None


async def get_shopify_client() -> ShopifyGraphQLClient:
    """Dependency para obtener el cliente de Shopify."""
    return ShopifyGraphQLClient(
        shop_url=settings.SHOPIFY_SHOP_URL,
        access_token=settings.SHOPIFY_ACCESS_TOKEN,
        api_version=settings.SHOPIFY_API_VERSION,
    )


async def get_product_repository() -> AsyncGenerator[ProductRepository, None]:
    """Dependency para obtener el repositorio de productos RMS."""
    conn_db = ConnDB()
    await conn_db.initialize()
    repo = ProductRepository(conn_db)
    try:
        yield repo
    finally:
        await conn_db.close()


async def get_reverse_stock_synchronizer(
    shopify_client: ShopifyGraphQLClient = Depends(get_shopify_client),
    product_repository: ProductRepository = Depends(get_product_repository),
) -> ReverseStockSynchronizer:
    """Dependency para obtener el sincronizador de stock reverso."""
    primary_location_id = await shopify_client.get_primary_location_id()

    if not primary_location_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener la ubicación principal de Shopify",
        )

    return ReverseStockSynchronizer(
        shopify_client=shopify_client,
        product_repository=product_repository,
        primary_location_id=primary_location_id,
    )


@router.post("/", response_model=ReverseStockSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_reverse_stock_sync(
    request: ReverseStockSyncRequest,
    synchronizer: ReverseStockSynchronizer = Depends(get_reverse_stock_synchronizer),
):
    """
    Ejecuta la sincronización reversa de stock Shopify → RMS.

    Esta sincronización complementaria:
    1. Encuentra productos en Shopify sin tag de sincronización de hoy
    2. Consulta el stock actual en RMS
    3. Actualiza el inventario en Shopify
    4. Elimina variantes con stock 0 (opcional)

    Args:
        request: Parámetros de sincronización

    Returns:
        Reporte detallado de la sincronización
    """
    global _last_sync_result

    try:
        logger.info(
            f"🔄 Iniciando reverse stock sync - "
            f"Dry run: {request.dry_run}, "
            f"Delete zero stock: {request.delete_zero_stock}, "
            f"Batch size: {request.batch_size}, "
            f"Limit: {request.limit or 'None'}"
        )

        # Execute reverse sync
        report = await synchronizer.execute_reverse_sync(
            dry_run=request.dry_run,
            delete_zero_stock=request.delete_zero_stock,
            batch_size=request.batch_size,
            limit=request.limit,
        )

        # Store result globally
        _last_sync_result = report

        success_rate = (
            (report["statistics"]["variants_updated"] + report["statistics"]["variants_deleted"])
            / max(1, report["statistics"]["variants_checked"])
        ) * 100

        return ReverseStockSyncResponse(
            success=True,
            message=f"Reverse sync completed successfully - {success_rate:.1f}% success rate",
            sync_id=report["sync_id"],
            report=report,
        )

    except Exception as e:
        logger.error(f"❌ Error in reverse stock sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reverse stock sync failed: {str(e)}"
        ) from e


@router.get("/status", response_model=dict[str, Any])
async def get_reverse_sync_status():
    """
    Obtiene el estado de la última sincronización reversa ejecutada.

    Returns:
        Estado y reporte de la última sincronización
    """
    global _last_sync_result

    if not _last_sync_result:
        return {
            "status": "never_run",
            "message": "No se ha ejecutado ninguna sincronización reversa todavía",
            "enabled": settings.ENABLE_REVERSE_STOCK_SYNC,
        }

    return {
        "status": "completed",
        "enabled": settings.ENABLE_REVERSE_STOCK_SYNC,
        "last_sync": _last_sync_result,
    }


@router.get("/config", response_model=dict[str, Any])
async def get_reverse_sync_config():
    """
    Obtiene la configuración actual de sincronización reversa.

    Returns:
        Configuración actual del sistema
    """
    return {
        "enabled": settings.ENABLE_REVERSE_STOCK_SYNC,
        "delay_minutes": settings.REVERSE_SYNC_DELAY_MINUTES,
        "delete_zero_stock": settings.REVERSE_SYNC_DELETE_ZERO_STOCK,
        "batch_size": settings.REVERSE_SYNC_BATCH_SIZE,
        "preserve_single_variant": settings.REVERSE_SYNC_PRESERVE_SINGLE_VARIANT,
    }


@router.post("/dry-run", response_model=ReverseStockSyncResponse)
async def dry_run_reverse_sync(
    limit: int = Query(default=10, ge=1, le=100, description="Número de productos a analizar"),
    synchronizer: ReverseStockSynchronizer = Depends(get_reverse_stock_synchronizer),
):
    """
    Ejecuta una simulación de reverse sync sin hacer cambios.

    Args:
        limit: Número máximo de productos a analizar

    Returns:
        Reporte de simulación mostrando qué cambios se harían
    """
    try:
        logger.info(f"🔍 Ejecutando dry-run de reverse sync con límite de {limit} productos")

        report = await synchronizer.execute_reverse_sync(
            dry_run=True,
            delete_zero_stock=True,
            batch_size=50,
            limit=limit,
        )

        return ReverseStockSyncResponse(
            success=True,
            message=f"Dry-run completado - Analizados {report['statistics']['products_checked']} productos",
            sync_id=report["sync_id"],
            report=report,
        )

    except Exception as e:
        logger.error(f"❌ Error in reverse sync dry-run: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dry-run failed: {str(e)}"
        ) from e
