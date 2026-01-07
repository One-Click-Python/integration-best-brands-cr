"""
RMS-Shopify Integration - FastAPI Application Entry Point

Sistema de integración bidireccional entre Microsoft Retail Management System (RMS)
y Shopify para automatizar la sincronización de productos, inventarios, precios y pedidos.

Este archivo actúa como el punto de entrada principal de la aplicación,
orquestando todos los componentes de manera modular y mantenible.

Autor: Enzo Leonardo Illanez (enzo@oneclick.cr)
Versión: Definida en pyproject.toml (ver app.version.VERSION)
"""

import logging

import uvicorn
from fastapi import FastAPI

# Importaciones de configuración
from app.core.config import get_settings
from app.core.exception_handlers import configure_exception_handlers
from app.core.lifespan import lifespan

# Importaciones de módulos de configuración
from app.core.middleware import configure_all_middleware
from app.core.openapi_config import configure_openapi
from app.core.routers import configure_all_routers

# Configuración
settings = get_settings()
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Factory para crear y configurar la aplicación FastAPI.

    Esta función sigue el patrón Factory para crear una instancia
    completamente configurada de FastAPI, aplicando todas las
    configuraciones de manera ordenada y modular.

    Returns:
        FastAPI: Instancia configurada de la aplicación
    """
    logger.info("🏗️ Creando aplicación FastAPI...")

    # Crear instancia base de FastAPI
    app = FastAPI(
        title=settings.APP_NAME,
        description="Sistema de integración bidireccional entre RMS y Shopify",
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
        # URLs de documentación configuradas dinámicamente
        docs_url="/docs" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
        redoc_url="/redoc" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
        openapi_url="/openapi.json" if (settings.DEBUG or settings.ENABLE_DOCS) else None,
    )

    # Configurar componentes en orden específico
    # El orden es importante para el correcto funcionamiento

    # 1. Middleware (orden inverso de ejecución)
    configure_all_middleware(app)

    # 2. Manejadores de excepciones
    configure_exception_handlers(app)

    # 3. Routers y endpoints
    configure_all_routers(app)

    # 4. Documentación OpenAPI
    configure_openapi(app)

    logger.info("✅ Aplicación FastAPI creada y configurada")
    return app


# Crear instancia de la aplicación
# Esta será la instancia principal que usa el servidor ASGI
app = create_application()


# Metadatos de la aplicación para introspección
app.state.app_info = {
    "name": settings.APP_NAME,
    "version": settings.APP_VERSION,
    "environment": settings.ENVIRONMENT,
    "debug": settings.DEBUG,
    "created_by": "create_application factory",
}


if __name__ == "__main__":
    """
    Ejecutar la aplicación directamente para desarrollo.

    Para producción se recomienda usar:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

    Para desarrollo con auto-reload:
    uvicorn app.main:app --reload
    """
    logger.info("🚀 Iniciando aplicación desde main.py...")

    # Configuración para desarrollo
    uvicorn_config = {
        "app": "app.main:app",
        "host": settings.HOST,
        "port": settings.PORT,
        "reload": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.lower(),
        "access_log": True,
        "workers": 1 if settings.DEBUG else settings.WORKERS,
    }

    # Configuraciones adicionales para desarrollo
    if settings.DEBUG:
        uvicorn_config.update(
            {
                "reload_dirs": ["app"],
                "reload_excludes": ["*.pyc", "__pycache__"],
            }
        )

    # Configuraciones adicionales para producción
    else:
        uvicorn_config.update(
            {
                "workers": settings.WORKERS,
                "loop": "uvloop",  # Mejor performance en Linux
                "http": "httptools",  # Parser HTTP más rápido
            }
        )

    logger.info(f"🔧 Configuración Uvicorn: {uvicorn_config}")

    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("🛑 Aplicación detenida por el usuario")
    except Exception as e:
        logger.error(f"❌ Error ejecutando aplicación: {e}")
        raise
