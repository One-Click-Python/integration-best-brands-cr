"""
Endpoints para webhooks de Shopify.

Este módulo define todos los endpoints para recibir y procesar webhooks
de Shopify para sincronización en tiempo real.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.webhook_handler import WEBHOOK_PROCESSOR, validate_webhook_request

settings = get_settings()
logger = logging.getLogger(__name__)

# Crear router
router = APIRouter()


@router.post("/shopify", status_code=status.HTTP_200_OK)
async def receive_shopify_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Endpoint principal para recibir webhooks de Shopify.

    Args:
        request: Request HTTP con el webhook
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Respuesta inmediata para Shopify
    """
    # Verificar si webhooks están habilitados
    if not settings.ENABLE_WEBHOOKS:
        logger.warning(
            "⚠️ Webhook received but ENABLE_WEBHOOKS=False. "
            "Order Polling is the active sync method. "
            "Set ENABLE_WEBHOOKS=True in .env to enable webhook processing."
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": "Webhooks disabled",
                "message": "Order Polling is the primary sync method. Enable ENABLE_WEBHOOKS to use webhooks.",
                "active_sync_method": "order_polling"
            }
        )

    try:
        # Validar request y extraer datos
        topic, payload = await validate_webhook_request(request)

        # Obtener ID único del webhook
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar webhook en background para respuesta rápida
        background_tasks.add_task(process_webhook_background, topic, payload, webhook_id)

        # Respuesta inmediata para Shopify (< 5 segundos)
        return JSONResponse(
            status_code=200,
            content={"received": True, "topic": topic, "webhook_id": webhook_id, "processing": "background"},
        )

    except Exception as e:
        logger.error(f"Error receiving webhook: {e}")
        # Shopify espera 200 incluso en errores para evitar reintentos
        return JSONResponse(status_code=200, content={"received": True, "error": str(e), "processing": "failed"})


@router.post("/product/created", status_code=status.HTTP_200_OK)
async def product_created_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para producto creado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "products/create", payload, webhook_id)

        logger.info(f"Received product created webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in product created webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.post("/product/updated", status_code=status.HTTP_200_OK)
async def product_updated_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para producto actualizado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "products/update", payload, webhook_id)

        logger.info(f"Received product updated webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in product updated webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.post("/product/deleted", status_code=status.HTTP_200_OK)
async def product_deleted_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para producto eliminado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "products/delete", payload, webhook_id)

        logger.info(f"Received product deleted webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in product deleted webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.post("/order/created", status_code=status.HTTP_200_OK)
async def order_created_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para pedido creado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "orders/create", payload, webhook_id)

        logger.info(f"Received order created webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in order created webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.post("/order/updated", status_code=status.HTTP_200_OK)
async def order_updated_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para pedido actualizado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "orders/updated", payload, webhook_id)

        logger.info(f"Received order updated webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in order updated webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.post("/inventory/update", status_code=status.HTTP_200_OK)
async def inventory_updated_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Webhook para inventario actualizado en Shopify.

    Args:
        request: Request de FastAPI
        background_tasks: Tareas en background

    Returns:
        JSONResponse: Confirmación de procesamiento
    """
    try:
        # Validar y extraer payload
        _, payload = await validate_webhook_request(request)
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")

        # Procesar en background
        background_tasks.add_task(process_webhook_background, "inventory_levels/update", payload, webhook_id)

        logger.info(f"Received inventory updated webhook: {webhook_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "webhook_id": webhook_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in inventory updated webhook: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "error": str(e)})


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_webhook_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas del procesamiento de webhooks.

    Returns:
        Dict: Métricas actuales
    """
    try:
        return WEBHOOK_PROCESSOR.get_metrics()
    except Exception as e:
        logger.error(f"Error getting webhook metrics: {e}")
        return {"error": str(e)}


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_webhook_processing(topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Endpoint para probar el procesamiento de webhooks.

    Args:
        topic: Topic del webhook a simular
        payload: Payload del webhook

    Returns:
        Dict: Resultado del procesamiento
    """
    try:
        result = await WEBHOOK_PROCESSOR.process_webhook(
            topic=topic, payload=payload, webhook_id=f"test_{topic}_{hash(str(payload))}"
        )
        return result
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return {"status": "error", "error": str(e), "topic": topic}


@router.get("/test", status_code=status.HTTP_200_OK)
async def test_webhook_endpoint():
    """
    Endpoint de prueba para verificar que los webhooks funcionan.

    Returns:
        Dict: Respuesta de prueba
    """
    return {
        "message": "Webhook endpoint is working",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "processor_metrics": WEBHOOK_PROCESSOR.get_metrics(),
    }


async def process_webhook_background(topic: str, payload: Dict[str, Any], webhook_id: str = None):
    """
    Procesa un webhook en background.

    Args:
        topic: Topic del webhook
        payload: Datos del webhook
        webhook_id: ID único del webhook
    """
    try:
        result = await WEBHOOK_PROCESSOR.process_webhook(topic=topic, payload=payload, webhook_id=webhook_id)

        logger.info(f"Background webhook processing completed: {result}")

    except Exception as e:
        logger.error(f"Background webhook processing failed: {e}")
        # En un sistema de producción, aquí podrías:
        # - Enviar a una cola de reintentos
        # - Notificar a sistemas de monitoreo
        # - Almacenar en base de datos para revisión manual
