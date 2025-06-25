"""
Endpoints para control de sincronización manual y programada.

Este módulo define todos los endpoints relacionados con operaciones
de sincronización entre RMS y Shopify.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.core.logging_config import log_sync_operation
from app.services.rms_to_shopify import get_sync_status, sync_rms_to_shopify
from app.services.shopify_to_rms import sync_shopify_to_rms
from app.utils.error_handler import (
    SyncException,
    ValidationException,
    create_error_response,
    handle_exception,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# Crear router
router = APIRouter()

# Query parameter singletons para evitar B008
DEFAULT_QUERY_LIMIT = Query(default=50, ge=1, le=1000)
DEFAULT_QUERY_SKIP = Query(default=0, ge=0)
DEFAULT_QUERY_SYNC_TYPE = Query(default=None, regex="^(rms_to_shopify|shopify_to_rms|full_sync)$")
DEFAULT_QUERY_START_DATE = Query(default=None)
DEFAULT_QUERY_END_DATE = Query(default=None)


# === MODELOS PYDANTIC ===


class SyncRequest(BaseModel):
    """Modelo para solicitudes de sincronización."""

    force_update: bool = Field(default=False, description="Forzar actualización de productos existentes")
    batch_size: Optional[int] = Field(default=None, ge=1, le=1000, description="Tamaño del lote para procesamiento")
    filter_categories: Optional[List[str]] = Field(default=None, description="Filtrar por categorías específicas")
    include_zero_stock: bool = Field(default=False, description="Incluir productos sin stock (cantidad = 0)")
    dry_run: bool = Field(default=False, description="Ejecutar en modo simulación sin hacer cambios")

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v):
        """Valida el tamaño del batch."""
        if v is not None and v <= 0:
            raise ValueError("batch_size debe ser mayor que 0")
        return v or settings.SYNC_BATCH_SIZE


class SyncResponse(BaseModel):
    """Modelo para respuestas de sincronización."""

    success: bool
    sync_id: str
    message: str
    statistics: Dict[str, Any]
    errors: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    timestamp: datetime
    duration_seconds: Optional[float] = None


class SyncStatusResponse(BaseModel):
    """Modelo para estado de sincronización."""

    status: str = Field(description="Estado actual: idle, running, error")
    active_syncs: List[str] = Field(description="IDs de syncs activos")
    last_sync: Optional[Dict[str, Any]] = None
    next_scheduled: Optional[datetime] = None
    system_health: Dict[str, str]


class ShopifyOrderSyncRequest(BaseModel):
    """Modelo para sincronización de pedidos específicos."""

    order_ids: List[str] = Field(description="IDs de pedidos de Shopify a sincronizar")
    skip_validation: bool = Field(default=False, description="Omitir validaciones de negocio")

    @field_validator("order_ids")
    @classmethod
    def validate_order_ids(cls, v):
        """Valida los IDs de pedidos."""
        if not v:
            raise ValueError("Se requiere al menos un order_id")
        if len(v) > 100:
            raise ValueError("Máximo 100 pedidos por request")
        return v


# === DEPENDENCIAS ===


async def verify_sync_permissions():
    """
    Verifica permisos para operaciones de sincronización.
    En el futuro se puede extender con autenticación real.
    """
    # TODO: Implementar verificación de API key o JWT
    pass


async def check_system_health():
    """
    Verifica que el sistema esté saludable para sincronización.
    """
    from app.core.health import is_system_healthy

    if not await is_system_healthy():
        raise HTTPException(status_code=503, detail="System is not healthy for sync operations")


# === ENDPOINTS ===


@router.get(
    "/status",
    response_model=SyncStatusResponse,
    summary="Obtener estado de sincronización",
    description="Obtiene el estado actual de todas las operaciones de sincronización",
)
async def get_synchronization_status():
    """
    Obtiene el estado actual de sincronización.

    Returns:
        SyncStatusResponse: Estado completo del sistema de sync
    """
    try:
        # Obtener estado de sync
        sync_status = await get_sync_status()

        # Obtener salud del sistema
        from app.core.health import get_health_status

        health_status = await get_health_status()

        # Construir respuesta
        status_response = SyncStatusResponse(
            status=sync_status.get("status", "unknown"),
            active_syncs=sync_status.get("active_syncs", []),
            last_sync=sync_status.get("last_sync"),
            next_scheduled=sync_status.get("next_scheduled"),
            system_health={
                service: data.get("status", "unknown") for service, data in health_status.get("services", {}).items()
            },
        )

        return status_response

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get synchronization status") from e


@router.post(
    "/rms-to-shopify",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sincronizar RMS → Shopify",
    description="Sincroniza productos, inventarios y precios de RMS hacia Shopify",
)
async def sync_rms_to_shopify_endpoint(
    sync_request: SyncRequest,
    background_tasks: BackgroundTasks,
    run_async: bool = Query(default=True, description="Ejecutar sincronización en segundo plano"),
    _: None = Depends(verify_sync_permissions),
    health_check: None = Depends(check_system_health),
):
    """
    Ejecuta sincronización de RMS hacia Shopify.

    Args:
        sync_request: Parámetros de sincronización
        background_tasks: Tareas en segundo plano
        run_async: Si ejecutar en background o sincrónicamente

    Returns:
        SyncResponse: Resultado de la sincronización
    """
    logger.debug("health_check", health_check)
    try:
        log_sync_operation(
            operation="start",
            service="rms_to_shopify",
            force_update=sync_request.force_update,
            batch_size=sync_request.batch_size,
        )

        if run_async:
            # Ejecutar en segundo plano
            sync_id = f"rms_to_shopify_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

            background_tasks.add_task(_execute_rms_to_shopify_sync, sync_request, sync_id)

            return SyncResponse(
                success=True,
                sync_id=sync_id,
                message="Synchronization started in background",
                statistics={"status": "started"},
                timestamp=datetime.now(timezone.utc),
            )
        else:
            # Ejecutar sincrónicamente
            if sync_request.dry_run:
                # Modo simulación
                result = await _simulate_rms_to_shopify_sync(sync_request)
            else:
                # Ejecución real
                result = await sync_rms_to_shopify(
                    force_update=sync_request.force_update,
                    batch_size=sync_request.batch_size,
                    filter_categories=sync_request.filter_categories,
                    include_zero_stock=sync_request.include_zero_stock,
                )

            return SyncResponse(
                success=True,
                sync_id=result["sync_id"],
                message="Synchronization completed successfully",
                statistics=result["statistics"],
                errors=result.get("errors"),
                recommendations=result.get("recommendations"),
                timestamp=datetime.now(timezone.utc),
                duration_seconds=result.get("duration_seconds"),
            )

    except ValidationException as e:
        logger.warning(f"Validation error in RMS sync: {e}")
        raise HTTPException(status_code=422, detail=create_error_response(e)) from e

    except SyncException as e:
        logger.error(f"Sync error in RMS sync: {e}")
        raise HTTPException(status_code=500, detail=create_error_response(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error in RMS sync: {e}")
        app_exception = handle_exception(e, reraise=False)
        raise HTTPException(status_code=500, detail=create_error_response(app_exception)) from e


@router.post(
    "/shopify-to-rms",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sincronizar Shopify → RMS",
    description="Sincroniza pedidos específicos de Shopify hacia RMS",
)
async def sync_shopify_to_rms_endpoint(
    sync_request: ShopifyOrderSyncRequest,
    background_tasks: BackgroundTasks,
    run_async: bool = Query(default=True, description="Ejecutar sincronización en segundo plano"),
    _: None = Depends(verify_sync_permissions),
    health_check: None = Depends(check_system_health),
):
    """
    Ejecuta sincronización de pedidos de Shopify hacia RMS.

    Args:
        sync_request: IDs de pedidos a sincronizar
        background_tasks: Tareas en segundo plano
        run_async: Si ejecutar en background

    Returns:
        SyncResponse: Resultado de la sincronización
    """
    logger.debug("health_check", health_check)
    try:
        log_sync_operation(
            operation="start",
            service="shopify_to_rms",
            order_count=len(sync_request.order_ids),
        )

        if run_async:
            # Ejecutar en segundo plano
            sync_id = f"shopify_to_rms_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

            background_tasks.add_task(_execute_shopify_to_rms_sync, sync_request, sync_id)

            return SyncResponse(
                success=True,
                sync_id=sync_id,
                message=f"Order synchronization started for {len(sync_request.order_ids)} orders",
                statistics={
                    "status": "started",
                    "order_count": len(sync_request.order_ids),
                },
                timestamp=datetime.now(timezone.utc),
            )
        else:
            # Ejecutar sincrónicamente
            result = await sync_shopify_to_rms(
                order_ids=sync_request.order_ids,
                skip_validation=sync_request.skip_validation,
            )

            return SyncResponse(
                success=True,
                sync_id=result["sync_id"],
                message="Order synchronization completed successfully",
                statistics=result["statistics"],
                errors=result.get("errors"),
                recommendations=result.get("recommendations"),
                timestamp=datetime.now(timezone.utc),
                duration_seconds=result.get("duration_seconds"),
            )

    except Exception as e:
        logger.error(f"Error in Shopify sync: {e}")
        app_exception = handle_exception(e, reraise=False)
        raise HTTPException(status_code=500, detail=create_error_response(app_exception)) from e


@router.post(
    "/full-sync",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sincronización completa bidireccional",
    description="Ejecuta sincronización completa en ambas direcciones",
)
async def full_synchronization(
    background_tasks: BackgroundTasks,
    force_update: bool = Query(default=False, description="Forzar actualización de todos los productos"),
    _: None = Depends(verify_sync_permissions),
    health_check: None = Depends(check_system_health),
):
    """
    Ejecuta sincronización completa bidireccional.

    Args:
        background_tasks: Tareas en segundo plano
        force_update: Forzar actualización completa

    Returns:
        SyncResponse: Resultado de la sincronización
    """
    logger.debug("health_check", health_check)
    try:
        sync_id = f"full_sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Siempre ejecutar en background por la duración
        background_tasks.add_task(_execute_full_sync, force_update, sync_id)

        log_sync_operation(operation="start", service="full_sync", force_update=force_update)

        return SyncResponse(
            success=True,
            sync_id=sync_id,
            message="Full bidirectional synchronization started in background",
            statistics={"status": "started", "type": "bidirectional"},
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Error starting full sync: {e}")
        app_exception = handle_exception(e, reraise=False)
        raise HTTPException(status_code=500, detail=create_error_response(app_exception)) from e


@router.get(
    "/history",
    summary="Historial de sincronización",
    description="Obtiene el historial de operaciones de sincronización",
)
async def get_sync_history(
    limit: int = DEFAULT_QUERY_LIMIT,
    skip: int = DEFAULT_QUERY_SKIP,
    sync_type: Optional[str] = DEFAULT_QUERY_SYNC_TYPE,
    start_date: Optional[datetime] = DEFAULT_QUERY_START_DATE,
    end_date: Optional[datetime] = DEFAULT_QUERY_END_DATE,
):
    """
    Obtiene historial de sincronizaciones.

    Args:
        limit: Número máximo de resultados
        skip: Número de resultados a saltar
        sync_type: Tipo de sincronización a filtrar
        start_date: Fecha de inicio del filtro
        end_date: Fecha de fin del filtro

    Returns:
        Dict: Historial de sincronizaciones
    """
    try:
        # TODO: Implementar consulta a base de datos o sistema de logs
        # Por ahora retornar datos de ejemplo

        history = {
            "total": 0,
            "syncs": [],
            "pagination": {"limit": limit, "skip": skip, "has_more": False},
            "filters": {
                "sync_type": sync_type,
                "start_date": start_date,
                "end_date": end_date,
            },
        }

        return history

    except Exception as e:
        logger.error(f"Error getting sync history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get synchronization history") from e


@router.delete(
    "/cancel/{sync_id}",
    summary="Cancelar sincronización",
    description="Cancela una operación de sincronización en progreso",
)
async def cancel_synchronization(sync_id: str):
    """
    Cancela una sincronización en progreso.

    Args:
        sync_id: ID de la sincronización a cancelar

    Returns:
        Dict: Resultado de la cancelación
    """
    try:
        # TODO: Implementar lógica de cancelación
        # Esto requeriría un sistema de gestión de tareas más sofisticado

        logger.info(f"Cancellation requested for sync: {sync_id}")

        return {
            "success": True,
            "message": f"Cancellation requested for sync {sync_id}",
            "sync_id": sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error canceling sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel synchronization {sync_id}") from e


# === FUNCIONES AUXILIARES ===


async def _execute_rms_to_shopify_sync(sync_request: SyncRequest, sync_id: str):
    """
    Ejecuta sincronización RMS → Shopify en segundo plano.

    Args:
        sync_request: Parámetros de sincronización
        sync_id: ID de la sincronización
    """
    try:
        logger.info(f"Starting background RMS sync: {sync_id}")

        result = await sync_rms_to_shopify(
            force_update=sync_request.force_update,
            batch_size=sync_request.batch_size,
            filter_categories=sync_request.filter_categories,
            include_zero_stock=sync_request.include_zero_stock,
        )

        logger.info(f"Background RMS sync completed: {sync_id}")
        log_sync_operation(
            operation="complete",
            service="rms_to_shopify",
            sync_id=sync_id,
            success_rate=result.get("success_rate", 0),
        )

    except Exception as e:
        logger.error(f"Background RMS sync failed: {sync_id} - {e}")
        log_sync_operation(operation="error", service="rms_to_shopify", sync_id=sync_id, error=str(e))


async def _execute_shopify_to_rms_sync(sync_request: ShopifyOrderSyncRequest, sync_id: str):
    """
    Ejecuta sincronización Shopify → RMS en segundo plano.

    Args:
        sync_request: Parámetros de sincronización
        sync_id: ID de la sincronización
    """
    try:
        logger.info(f"Starting background Shopify sync: {sync_id}")

        await sync_shopify_to_rms(
            order_ids=sync_request.order_ids,
            skip_validation=sync_request.skip_validation,
        )

        logger.info(f"Background Shopify sync completed: {sync_id}")
        log_sync_operation(
            operation="complete",
            service="shopify_to_rms",
            sync_id=sync_id,
            orders_processed=len(sync_request.order_ids),
        )

    except Exception as e:
        logger.error(f"Background Shopify sync failed: {sync_id} - {e}")
        log_sync_operation(operation="error", service="shopify_to_rms", sync_id=sync_id, error=str(e))


async def _execute_full_sync(force_update: bool, sync_id: str):
    """
    Ejecuta sincronización completa bidireccional.

    Args:
        force_update: Forzar actualización
        sync_id: ID de la sincronización
    """
    try:
        logger.info(f"Starting full bidirectional sync: {sync_id}")

        # 1. Primero sincronizar RMS → Shopify
        await sync_rms_to_shopify(force_update=force_update)

        # 2. Luego procesar pedidos pendientes de Shopify
        # TODO: Implementar lógica para obtener pedidos pendientes

        logger.info(f"Full sync completed: {sync_id}")
        log_sync_operation(operation="complete", service="full_sync", sync_id=sync_id)

    except Exception as e:
        logger.error(f"Full sync failed: {sync_id} - {e}")
        log_sync_operation(operation="error", service="full_sync", sync_id=sync_id, error=str(e))


async def _simulate_rms_to_shopify_sync(sync_request: SyncRequest) -> Dict[str, Any]:
    """
    Simula sincronización RMS → Shopify sin hacer cambios.

    Args:
        sync_request: Parámetros de sincronización

    Returns:
        Dict: Resultado simulado
    """
    logger.info("Running RMS sync simulation", sync_request)

    # Simular estadísticas
    simulated_result = {
        "sync_id": f"simulation_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "statistics": {
            "total_processed": 100,
            "created": 25,
            "updated": 50,
            "skipped": 20,
            "errors": 5,
        },
        "errors": {"error_count": 5, "warning_count": 10},
        "recommendations": [
            "Consider force update for better synchronization",
            "Review data quality for better success rate",
        ],
        "duration_seconds": 15.5,
    }

    return simulated_result
