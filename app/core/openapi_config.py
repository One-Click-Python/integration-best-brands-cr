"""
Configuración personalizada de OpenAPI/Swagger para la aplicación FastAPI.

Este módulo maneja la configuración de la documentación automática de la API,
incluyendo esquemas personalizados, ejemplos, seguridad y metadatos.
"""

import logging
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def get_custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """
    Genera esquema OpenAPI personalizado con información adicional.

    Args:
        app: Instancia de FastAPI

    Returns:
        Dict: Esquema OpenAPI personalizado
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generar esquema base
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.3",
    )

    # Información adicional del proyecto
    openapi_schema["info"].update(
        {
            "contact": {
                "name": "Leonardo Illañez",
                "email": "leonardo@live.com.ar",
                "url": "https://github.com/leoillanez777",
            },
            "license": {
                "name": "MIT License",
                "url": "https://opensource.org/licenses/MIT",
            },
            "termsOfService": "https://example.com/terms",
            "x-logo": {
                "url": "https://example.com/logo.png",
                "altText": "RMS-Shopify Integration",
            },
        }
    )

    # Configurar servidores
    openapi_schema["servers"] = get_server_configuration()

    # Agregar tags personalizados
    openapi_schema["tags"] = get_custom_tags()

    # Configurar componentes de seguridad
    openapi_schema["components"] = get_security_components()

    # Agregar ejemplos personalizados
    add_custom_examples(openapi_schema)

    # Información adicional
    openapi_schema["x-app-info"] = {
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "features": {
            "synchronization": True,
            "webhooks": True,
            "metrics": settings.METRICS_ENABLED,
            "rate_limiting": settings.ENABLE_RATE_LIMITING,
        },
    }

    return openapi_schema


def get_server_configuration() -> list:
    """
    Configura los servidores disponibles para la API.

    Returns:
        List: Lista de configuraciones de servidor
    """
    servers = []

    # Servidor de desarrollo
    if settings.DEBUG:
        servers.append(
            {
                "url": f"http://localhost:{settings.PORT}",
                "description": "Servidor de Desarrollo",
                "variables": {
                    "port": {
                        "default": str(settings.PORT),
                        "description": "Puerto del servidor",
                    }
                },
            }
        )

    # Servidor de producción
    if settings.API_BASE_URL:
        servers.append({"url": settings.API_BASE_URL, "description": "Servidor de Producción"})

    # Servidor de staging (si está configurado)
    if hasattr(settings, "STAGING_URL") and settings.STAGING_URL:
        servers.append({"url": settings.STAGING_URL, "description": "Servidor de Staging"})

    return servers


def get_custom_tags() -> list:
    """
    Define tags personalizados para organizar los endpoints.

    Returns:
        List: Lista de tags con descripciones
    """
    return [
        {"name": "Root", "description": "Endpoints básicos de información y estado"},
        {"name": "Health", "description": "Endpoints de salud y monitoreo del sistema"},
        {
            "name": "Synchronization",
            "description": "Operaciones de sincronización entre RMS y Shopify",
            "externalDocs": {
                "description": "Documentación de sincronización",
                "url": "https://docs.example.com/sync",
            },
        },
        {
            "name": "Webhooks",
            "description": "Endpoints para recibir notificaciones de Shopify",
            "externalDocs": {
                "description": "Documentación de Shopify Webhooks",
                "url": "https://shopify.dev/apps/webhooks",
            },
        },
        {"name": "Metrics", "description": "Métricas y estadísticas del sistema"},
        {
            "name": "Administration",
            "description": "Endpoints administrativos (solo desarrollo)",
        },
        {"name": "Logs", "description": "Acceso a logs del sistema (solo desarrollo)"},
        {"name": "Info", "description": "Información del sistema y configuración"},
    ]


def get_security_components() -> Dict[str, Any]:
    """
    Define esquemas de seguridad para la API.

    Returns:
        Dict: Componentes de seguridad OpenAPI
    """
    return {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API Key para autenticación",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token JWT para autenticación",
            },
            "ShopifyWebhook": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Shopify-Hmac-Sha256",
                "description": "HMAC para verificación de webhooks de Shopify",
            },
        },
        "schemas": get_custom_schemas(),
        "responses": get_common_responses(),
        "parameters": get_common_parameters(),
    }


def get_custom_schemas() -> Dict[str, Any]:
    """
    Define esquemas personalizados reutilizables.

    Returns:
        Dict: Esquemas personalizados
    """
    return {
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "error": {"type": "boolean", "example": True},
                "error_type": {"type": "string", "example": "validation_error"},
                "error_code": {"type": "string", "example": "INVALID_SKU"},
                "message": {"type": "string", "example": "SKU inválido"},
                "details": {"type": "object"},
                "path": {"type": "string", "example": "/api/v1/sync/rms-to-shopify"},
                "timestamp": {"type": "string", "format": "date-time"},
                "request_id": {"type": "string", "example": "abc12345"},
            },
            "required": ["error", "message", "timestamp"],
        },
        "SuccessResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string", "example": "Operación completada"},
                "data": {"type": "object"},
                "timestamp": {"type": "string", "format": "date-time"},
                "request_id": {"type": "string", "example": "abc12345"},
            },
            "required": ["success", "message", "timestamp"],
        },
        "SyncStats": {
            "type": "object",
            "properties": {
                "total_processed": {"type": "integer", "example": 150},
                "successful": {"type": "integer", "example": 145},
                "failed": {"type": "integer", "example": 5},
                "skipped": {"type": "integer", "example": 0},
                "duration_seconds": {"type": "number", "example": 12.5},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
            },
        },
        "HealthStatus": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["healthy", "unhealthy"],
                    "example": "healthy",
                },
                "services": {
                    "type": "object",
                    "properties": {
                        "rms": {"$ref": "#/components/schemas/ServiceHealth"},
                        "shopify": {"$ref": "#/components/schemas/ServiceHealth"},
                        "redis": {"$ref": "#/components/schemas/ServiceHealth"},
                    },
                },
                "timestamp": {"type": "string", "format": "date-time"},
            },
        },
        "ServiceHealth": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["healthy", "unhealthy"],
                    "example": "healthy",
                },
                "latency_ms": {"type": "number", "example": 25.5},
                "error": {"type": "string", "example": "Connection timeout"},
            },
        },
    }


def get_common_responses() -> Dict[str, Any]:
    """
    Define respuestas comunes reutilizables.

    Returns:
        Dict: Respuestas comunes
    """
    return {
        "BadRequest": {
            "description": "Solicitud inválida",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error": True,
                        "error_type": "validation_error",
                        "message": "Parámetros inválidos",
                        "timestamp": "2025-06-15T10:30:00Z",
                    },
                }
            },
        },
        "Unauthorized": {
            "description": "No autorizado",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error": True,
                        "error_type": "authentication_error",
                        "message": "API Key requerida",
                        "timestamp": "2025-06-15T10:30:00Z",
                    },
                }
            },
        },
        "RateLimited": {
            "description": "Límite de rate excedido",
            "headers": {
                "Retry-After": {
                    "description": "Segundos para retry",
                    "schema": {"type": "integer"},
                }
            },
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error": True,
                        "error_type": "rate_limit_error",
                        "message": "Límite de requests excedido",
                        "timestamp": "2025-06-15T10:30:00Z",
                    },
                }
            },
        },
        "InternalError": {
            "description": "Error interno del servidor",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error": True,
                        "error_type": "internal_server_error",
                        "message": "Error interno del servidor",
                        "timestamp": "2025-06-15T10:30:00Z",
                    },
                }
            },
        },
    }


def get_common_parameters() -> Dict[str, Any]:
    """
    Define parámetros comunes reutilizables.

    Returns:
        Dict: Parámetros comunes
    """
    return {
        "RequestId": {
            "name": "X-Request-ID",
            "in": "header",
            "description": "ID único para tracking de request",
            "required": False,
            "schema": {"type": "string"},
        },
        "ApiKey": {
            "name": "X-API-Key",
            "in": "header",
            "description": "API Key para autenticación",
            "required": True,
            "schema": {"type": "string"},
        },
        "PageSize": {
            "name": "page_size",
            "in": "query",
            "description": "Número de elementos por página",
            "required": False,
            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "PageNumber": {
            "name": "page",
            "in": "query",
            "description": "Número de página",
            "required": False,
            "schema": {"type": "integer", "minimum": 1, "default": 1},
        },
    }


def add_custom_examples(openapi_schema: Dict[str, Any]) -> None:
    """
    Agrega ejemplos personalizados a los esquemas.

    Args:
        openapi_schema: Esquema OpenAPI a modificar
    """
    # Agregar ejemplos a paths específicos
    paths = openapi_schema.get("paths", {})

    # Ejemplo para sync endpoint
    if "/api/v1/sync/rms-to-shopify" in paths:
        sync_path = paths["/api/v1/sync/rms-to-shopify"]
        if "post" in sync_path:
            sync_path["post"]["requestBody"] = {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "force_update": {"type": "boolean"},
                                "batch_size": {"type": "integer"},
                                "filter_categories": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                        "examples": {
                            "full_sync": {
                                "summary": "Sincronización completa",
                                "value": {"force_update": True, "batch_size": 100},
                            },
                            "category_sync": {
                                "summary": "Sincronización por categoría",
                                "value": {
                                    "force_update": False,
                                    "batch_size": 50,
                                    "filter_categories": ["Electronics", "Clothing"],
                                },
                            },
                        },
                    }
                }
            }


def configure_openapi(app: FastAPI) -> None:
    """
    Configura OpenAPI personalizado para la aplicación.

    Args:
        app: Instancia de FastAPI
    """
    logger.info("🔧 Configurando documentación OpenAPI...")

    def custom_openapi():
        return get_custom_openapi_schema(app)

    # Solo habilitar en desarrollo o si está explícitamente habilitado
    if settings.DEBUG or settings.ENABLE_DOCS:
        app.openapi = custom_openapi
        logger.info("✅ Documentación OpenAPI configurada y habilitada")
    else:
        # Deshabilitar documentación en producción
        app.docs_url = None
        app.redoc_url = None
        app.openapi_url = None
        logger.info("🔒 Documentación OpenAPI deshabilitada (producción)")


def get_api_info() -> Dict[str, Any]:
    """
    Obtiene información sobre la configuración de la API.

    Returns:
        Dict: Información de la API
    """
    return {
        "title": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_enabled": settings.DEBUG or settings.ENABLE_DOCS,
        "docs_url": "/docs" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
        "redoc_url": "/redoc" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
        "openapi_url": "/openapi.json" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
        "environment": settings.ENVIRONMENT,
    }
