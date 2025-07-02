"""
Endpoints para control de sincronización manual y programada.

Este módulo define todos los endpoints relacionados con operaciones
de sincronización entre RMS y Shopify.
"""

import asyncio
import logging
import time
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

# Sistema simple de locks para evitar múltiples sincronizaciones simultáneas
# Esto previene la acumulación de precios por múltiples procesos concurrentes
_sync_locks = {
    "rms_to_shopify": asyncio.Lock(),
    "shopify_to_rms": asyncio.Lock(),
    "full_sync": asyncio.Lock(),
}

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
    ccod: Optional[str] = Field(default=None, max_length=20, description="Sincronizar solo un producto específico por CCOD")

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
    
    # NUEVO: Verificar si ya hay una sincronización en progreso
    if _sync_locks["rms_to_shopify"].locked():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "sync_in_progress",
                "message": "Una sincronización RMS → Shopify ya está en progreso. Por favor espere a que termine.",
                "recommendation": "Use GET /api/v1/sync/status para verificar el estado actual"
            }
        )
    
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
                    ccod=sync_request.ccod,
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


@router.get(
    "/orders",
    summary="Obtener todas las órdenes de Shopify",
    description="Obtiene todas las órdenes (regulares y draft orders) disponibles en Shopify",
)
async def get_all_orders(
    limit: int = Query(default=50, ge=1, le=250, description="Número máximo de órdenes por tipo"),
    include_draft_orders: bool = Query(default=True, description="Incluir draft orders"),
    _: None = Depends(verify_sync_permissions),
):
    """
    Obtiene todas las órdenes disponibles en Shopify.
    
    Args:
        limit: Límite de órdenes por tipo (regulares y draft)
        include_draft_orders: Si incluir draft orders
        
    Returns:
        Dict: Órdenes obtenidas de Shopify
    """
    try:
        from app.db.shopify_order_client import ShopifyOrderClient
        from app.db.shopify_graphql_client import ShopifyGraphQLClient
        
        logger.info(f"Obteniendo órdenes de Shopify (limit={limit}, include_draft={include_draft_orders})")
        
        # Inicializar cliente GraphQL base
        graphql_client = ShopifyGraphQLClient()
        await graphql_client.initialize()
        
        # Inicializar cliente de órdenes
        order_client = ShopifyOrderClient(graphql_client)
        
        try:
            # Obtener órdenes regulares
            orders_result = await order_client.get_orders(limit=limit)
            regular_orders = orders_result.get("orders", []) if isinstance(orders_result, dict) else orders_result
            
            all_orders_data = {
                "orders": regular_orders,
                "total_orders": len(regular_orders),
                "draft_orders": [],
                "total_draft_orders": 0,
                "summary": {
                    "regular_orders_count": len(regular_orders),
                    "draft_orders_count": 0,
                    "total_count": len(regular_orders)
                }
            }
            
            # Obtener draft orders si está habilitado
            if include_draft_orders:
                draft_orders = await order_client.get_draft_orders(limit=limit)
                all_orders_data["draft_orders"] = draft_orders
                all_orders_data["total_draft_orders"] = len(draft_orders)
                all_orders_data["summary"]["draft_orders_count"] = len(draft_orders)
                all_orders_data["summary"]["total_count"] += len(draft_orders)
            
            logger.info(f"✅ Órdenes obtenidas: {all_orders_data['summary']['regular_orders_count']} regulares, {all_orders_data['summary']['draft_orders_count']} draft orders")
            
            return all_orders_data
            
        finally:
            await graphql_client.close()
            
    except Exception as e:
        logger.error(f"Error obteniendo órdenes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving orders from Shopify: {str(e)}"
        ) from e


@router.post(
    "/orders",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sincronizar órdenes específicas",
    description="Sincroniza órdenes específicas de Shopify hacia RMS (usa order_id directamente)",
)
async def sync_orders_endpoint(
    order_id: str = Query(description="ID de la orden específica a sincronizar"),
    force_sync: bool = Query(default=False, description="Forzar sincronización aunque ya exista"),
    validate_before_insert: bool = Query(default=True, description="Validar datos antes de insertar"),
    background_tasks: BackgroundTasks = None,
    run_async: bool = Query(default=True, description="Ejecutar sincronización en segundo plano"),
    _: None = Depends(verify_sync_permissions),
    health_check: None = Depends(check_system_health),
):
    """
    Sincroniza una orden específica de Shopify hacia RMS.
    
    Este endpoint maneja automáticamente tanto órdenes regulares como draft orders.
    
    Args:
        order_id: ID de la orden a sincronizar
        force_sync: Forzar sincronización
        validate_before_insert: Validar antes de insertar
        run_async: Ejecutar en background
        
    Returns:
        SyncResponse: Resultado de la sincronización
    """
    logger.debug("health_check", health_check)
    try:
        log_sync_operation(
            operation="start",
            service="single_order_sync",
            order_id=order_id,
        )
        
        if run_async and background_tasks:
            # Ejecutar en segundo plano
            sync_id = f"order_sync_{order_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            background_tasks.add_task(
                _execute_single_order_sync, 
                order_id, 
                force_sync, 
                validate_before_insert, 
                sync_id
            )
            
            return SyncResponse(
                success=True,
                sync_id=sync_id,
                message=f"Order synchronization started for order {order_id}",
                statistics={"status": "started", "order_id": order_id},
                timestamp=datetime.now(timezone.utc),
            )
        else:
            # Ejecutar sincrónicamente
            result = await _sync_single_order(order_id, force_sync, validate_before_insert)
            
            return SyncResponse(
                success=result["success"],
                sync_id=result["sync_id"],
                message=result["message"],
                statistics=result["statistics"],
                errors=result.get("errors"),
                timestamp=datetime.now(timezone.utc),
                duration_seconds=result.get("duration_seconds"),
            )
            
    except Exception as e:
        logger.error(f"Error in single order sync: {e}")
        app_exception = handle_exception(e, reraise=False)
        raise HTTPException(status_code=500, detail=create_error_response(app_exception)) from e


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
    # NUEVO: Usar lock para prevenir múltiples sincronizaciones simultáneas
    async with _sync_locks["rms_to_shopify"]:
        try:
            logger.info(f"🔒 Starting background RMS sync with LOCK: {sync_id}")

            result = await sync_rms_to_shopify(
                force_update=sync_request.force_update,
                batch_size=sync_request.batch_size,
                filter_categories=sync_request.filter_categories,
                include_zero_stock=sync_request.include_zero_stock,
                ccod=sync_request.ccod,
            )

            logger.info(f"✅ Background RMS sync completed with LOCK: {sync_id}")
            log_sync_operation(
                operation="complete",
                service="rms_to_shopify",
                sync_id=sync_id,
                success_rate=result.get("success_rate", 0),
            )

        except Exception as e:
            logger.error(f"❌ Background RMS sync failed with LOCK: {sync_id} - {e}")
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


async def _execute_single_order_sync(
    order_id: str, 
    force_sync: bool, 
    validate_before_insert: bool, 
    sync_id: str
):
    """
    Ejecuta sincronización de una orden específica en segundo plano.
    
    Args:
        order_id: ID de la orden
        force_sync: Forzar sincronización
        validate_before_insert: Validar antes de insertar
        sync_id: ID de la sincronización
    """
    try:
        logger.info(f"Starting background single order sync: {sync_id} for order {order_id}")
        
        result = await _sync_single_order(order_id, force_sync, validate_before_insert)
        
        if result["success"]:
            logger.info(f"✅ Background single order sync completed: {sync_id}")
            log_sync_operation(
                operation="complete",
                service="single_order_sync",
                sync_id=sync_id,
                order_id=order_id,
            )
        else:
            logger.error(f"❌ Background single order sync failed: {sync_id} - {result.get('message', 'Unknown error')}")
            log_sync_operation(
                operation="error",
                service="single_order_sync", 
                sync_id=sync_id,
                error=result.get("message", "Unknown error")
            )

    except Exception as e:
        logger.error(f"❌ Background single order sync exception: {sync_id} - {e}")
        log_sync_operation(
            operation="error", 
            service="single_order_sync", 
            sync_id=sync_id, 
            error=str(e)
        )


async def _sync_single_order(
    order_id: str, 
    force_sync: bool, 
    validate_before_insert: bool
) -> Dict[str, Any]:
    """
    Sincroniza una orden específica de Shopify hacia RMS.
    
    Args:
        order_id: ID de la orden a sincronizar
        force_sync: Forzar sincronización
        validate_before_insert: Validar antes de insertar
        
    Returns:
        Dict: Resultado de la sincronización
    """
    start_time = time.time()
    sync_id = f"order_sync_{order_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    try:
        from app.services.shopify_to_rms import ShopifyToRMSSync
        
        logger.info(f"Sincronizando orden individual: {order_id}")
        
        # Inicializar servicio de sincronización
        sync_service = ShopifyToRMSSync()
        
        # Usar el método sync_orders existente con una sola orden
        result = await sync_service.sync_orders(
            order_ids=[order_id],
            skip_validation=not validate_before_insert
        )
        
        duration = time.time() - start_time
        
        # Verificar si fue exitoso
        success = result.get("statistics", {}).get("created", 0) > 0 or result.get("statistics", {}).get("updated", 0) > 0
        
        # Construir respuesta 
        return {
            "success": success,
            "sync_id": sync_id,
            "message": f"Order {order_id} {'synchronized successfully' if success else 'synchronization failed'}",
            "statistics": {
                "order_id": order_id,
                "processed": 1,
                "success": 1 if success else 0,
                "database_impact": "ORDER and ORDERENTRY tables updated" if success else "No database changes",
                "sync_details": result.get("statistics", {}),
                "errors": result.get("errors", [])
            },
            "duration_seconds": duration
        }
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error sincronizando orden {order_id}: {e}")
        
        return {
            "success": False,
            "sync_id": sync_id,
            "message": f"Failed to synchronize order {order_id}: {str(e)}",
            "statistics": {
                "order_id": order_id,
                "processed": 1,
                "success": 0,
                "errors": 1
            },
            "errors": {"error_message": str(e)},
            "duration_seconds": duration
        }


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
