"""
Manejadores de excepciones centralizados para la aplicación FastAPI.

Este módulo define todos los manejadores de excepciones personalizados y globales,
proporcionando respuestas consistentes y logging apropiado para diferentes tipos de errores.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.utils.error_handler import (
    AppException,
    RateLimitException,
    RMSConnectionException,
    ShopifyAPIException,
    SyncException,
    ValidationException,
)

settings = get_settings()
logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Manejador para excepciones personalizadas de la aplicación.

    Args:
        request: Request de FastAPI
        exc: Excepción personalizada de la app

    Returns:
        JSONResponse: Respuesta JSON con error formateado
    """
    logger.error(
        f"App Exception: {exc.message} - "
        f"Code: {exc.error_code} - "
        f"URL: {request.url} - "
        f"Details: {exc.details}"
    )

    # Enviar alerta si es crítico
    if exc.is_critical:
        await send_critical_alert(exc, request)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "application_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details if settings.DEBUG else None,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def sync_exception_handler(request: Request, exc: SyncException) -> JSONResponse:
    """
    Manejador específico para errores de sincronización.

    Args:
        request: Request de FastAPI
        exc: Excepción de sincronización

    Returns:
        JSONResponse: Respuesta JSON con información de error de sync
    """
    logger.error(
        f"Sync Exception: {exc.message} - "
        f"Service: {exc.service} - "
        f"Operation: {exc.operation} - "
        f"Failed Records: {exc.failed_records} - "
        f"URL: {request.url}"
    )

    # Log adicional con estadísticas
    if exc.sync_stats:
        logger.info(f"Sync Stats: {exc.sync_stats}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "synchronization_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "service": exc.service,
            "operation": exc.operation,
            "failed_records": exc.failed_records,
            "sync_stats": exc.sync_stats,
            "retry_suggested": exc.retry_suggested,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def shopify_api_exception_handler(request: Request, exc: ShopifyAPIException) -> JSONResponse:
    """
    Manejador específico para errores de la API de Shopify.

    Args:
        request: Request de FastAPI
        exc: Excepción de Shopify API

    Returns:
        JSONResponse: Respuesta JSON con información del error de Shopify
    """
    logger.error(
        f"Shopify API Exception: {exc.message} - "
        f"API Code: {exc.api_response_code} - "
        f"Rate Limited: {exc.rate_limited} - "
        f"Retry After: {exc.retry_after} - "
        f"URL: {request.url}"
    )

    # Headers adicionales para rate limiting
    headers = {}
    if exc.rate_limited and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
        headers["X-Rate-Limit-Exceeded"] = "true"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "shopify_api_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "shopify_response_code": exc.api_response_code,
            "rate_limited": exc.rate_limited,
            "retry_after": exc.retry_after,
            "endpoint": exc.endpoint,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
        headers=headers,
    )


async def rms_connection_exception_handler(request: Request, exc: RMSConnectionException) -> JSONResponse:
    """
    Manejador específico para errores de conexión con RMS.

    Args:
        request: Request de FastAPI
        exc: Excepción de conexión RMS

    Returns:
        JSONResponse: Respuesta JSON con información del error de RMS
    """
    logger.error(
        f"RMS Connection Exception: {exc.message} - "
        f"DB Host: {exc.db_host} - "
        f"Connection Type: {exc.connection_type} - "
        f"URL: {request.url}"
    )

    # Alerta crítica para problemas de RMS
    await send_critical_alert(exc, request)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "rms_connection_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "db_host": exc.db_host if settings.DEBUG else "hidden",
            "connection_type": exc.connection_type,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """
    Manejador para errores de validación de datos.

    Args:
        request: Request de FastAPI
        exc: Excepción de validación

    Returns:
        JSONResponse: Respuesta JSON con detalles de validación
    """
    logger.warning(
        f"Validation Exception: {exc.message} - "
        f"Field: {exc.field} - "
        f"Value: {exc.invalid_value} - "
        f"URL: {request.url}"
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "error_type": "validation_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "field": exc.field,
            "invalid_value": exc.invalid_value if settings.DEBUG else None,
            "expected_format": exc.expected_format,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """
    Manejador para errores de rate limiting.

    Args:
        request: Request de FastAPI
        exc: Excepción de rate limiting

    Returns:
        JSONResponse: Respuesta JSON con información de rate limit
    """
    logger.warning(
        f"Rate Limit Exception: {exc.message} - "
        f"Limit: {exc.limit} - "
        f"Reset Time: {exc.reset_time} - "
        f"URL: {request.url}"
    )

    headers = {
        "Retry-After": str(exc.retry_after),
        "X-Rate-Limit-Limit": str(exc.limit),
        "X-Rate-Limit-Reset": str(exc.reset_time),
    }

    return JSONResponse(
        status_code=429,
        content={
            "error": True,
            "error_type": "rate_limit_error",
            "error_code": exc.error_code,
            "message": exc.message,
            "limit": exc.limit,
            "retry_after": exc.retry_after,
            "reset_time": exc.reset_time,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Manejador para HTTPException estándar de FastAPI.

    Args:
        request: Request de FastAPI
        exc: HTTPException

    Returns:
        JSONResponse: Respuesta JSON estandarizada
    """
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail} - URL: {request.url}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "http_error",
            "status_code": exc.status_code,
            "message": exc.detail,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Manejador para HTTPException de Starlette (nivel más bajo).

    Args:
        request: Request de FastAPI
        exc: StarletteHTTPException

    Returns:
        JSONResponse: Respuesta JSON estandarizada
    """
    logger.warning(f"Starlette HTTP Exception: {exc.status_code} - {exc.detail} - " f"URL: {request.url}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_type": "http_error",
            "status_code": exc.status_code,
            "message": exc.detail,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Manejador global para excepciones no capturadas.

    Args:
        request: Request de FastAPI
        exc: Excepción no manejada

    Returns:
        JSONResponse: Respuesta JSON de error interno
    """
    # Log completo del error con traceback
    logger.error(
        f"Unhandled Exception: {str(exc)} - "
        f"Type: {type(exc).__name__} - "
        f"URL: {request.url} - "
        f"Traceback: {traceback.format_exc()}"
    )

    # Enviar alerta crítica
    await send_critical_alert(exc, request)

    # Respuesta genérica (sin exponer detalles internos)
    error_message = "Internal server error occurred"
    if settings.DEBUG:
        error_message = f"{type(exc).__name__}: {str(exc)}"

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_type": "internal_server_error",
            "message": error_message,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
            "traceback": traceback.format_exc() if settings.DEBUG else None,
        },
    )


def configure_exception_handlers(app: FastAPI) -> None:
    """
    Configura todos los manejadores de excepciones de la aplicación.

    Args:
        app: Instancia de FastAPI
    """
    logger.info("🔧 Configurando manejadores de excepciones...")

    # Manejadores específicos (orden de especificidad)
    app.add_exception_handler(ValidationException, validation_exception_handler)
    app.add_exception_handler(RateLimitException, rate_limit_exception_handler)
    app.add_exception_handler(SyncException, sync_exception_handler)
    app.add_exception_handler(ShopifyAPIException, shopify_api_exception_handler)
    app.add_exception_handler(RMSConnectionException, rms_connection_exception_handler)
    app.add_exception_handler(AppException, app_exception_handler)

    # Manejadores HTTP estándar
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

    # Manejador global (debe ser el último)
    app.add_exception_handler(Exception, global_exception_handler)

    logger.info("✅ Manejadores de excepciones configurados correctamente")


# Funciones auxiliares


async def send_critical_alert(exc: Exception, request: Request) -> None:
    """
    Envía alerta crítica para errores importantes.

    Args:
        exc: Excepción que generó la alerta
        request: Request que causó el error
    """
    try:
        if not settings.ALERT_EMAIL_ENABLED:
            return

        from app.utils.notifications import send_error_alert

        alert_data = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "url": str(request.url),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.headers.get("X-Forwarded-For")
            or (request.client.host if request.client else "unknown"),
        }

        await send_error_alert(alert_data)

    except Exception as alert_error:
        logger.error(f"Error enviando alerta crítica: {alert_error}")


def get_error_context(request: Request) -> Dict[str, Any]:
    """
    Extrae contexto útil de la request para logging de errores.

    Args:
        request: Request de FastAPI

    Returns:
        Dict con contexto del error
    """
    return {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client": {
            "host": request.client.host if request.client else None,
            "port": request.client.port if request.client else None,
        },
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("X-Request-ID"),
        "timestamp": datetime.utcnow().isoformat(),
    }
