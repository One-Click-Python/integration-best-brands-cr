#!/usr/bin/env python3
"""
API endpoints para gestión de Shopify Collections basadas en género + categoría.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.gender_category_service import GenderCategoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.post("/sync")
async def sync_collections(
    dry_run: bool = Query(False, description="Si True, no crea las collections, solo muestra qué se haría"),
    sync_main: bool = Query(True, description="Sincronizar collections principales (Mujer, Hombre, etc.)"),
    sync_subcategories: bool = Query(
        True, description="Sincronizar subcategorías (Mujer-Flats, Hombre-Tenis, etc.)"
    ),
) -> Dict[str, Any]:
    """
    Sincroniza las collections de Shopify basadas en la configuración de género + categoría.

    Crea o actualiza:
    - Collections principales por género (Mujer, Hombre, Infantil, Bolsos)
    - Subcategorías dentro de cada género (Flats, Tenis, Tacones, etc.)

    Las collections son "smart/automated", lo que significa que Shopify las mantiene
    automáticamente basándose en las reglas definidas (product_type + tags).

    Args:
        dry_run: Si True, solo muestra qué se haría sin crear nada
        sync_main: Si True, sincroniza collections principales
        sync_subcategories: Si True, sincroniza subcategorías

    Returns:
        Resultado de la sincronización con estadísticas
    """
    try:
        logger.info(f"🔄 Iniciando sincronización de collections (dry_run={dry_run})")

        # Inicializar cliente de Shopify
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        # Inicializar gender category service con cliente GraphQL
        collection_manager = GenderCategoryService(shopify_client=shopify_client)

        # Ejecutar sincronización
        if sync_main and sync_subcategories:
            result = await collection_manager.sync_all_gender_collections(dry_run=dry_run)
        elif sync_main:
            result = await collection_manager.sync_main_collections(dry_run=dry_run)
        elif sync_subcategories:
            result = await collection_manager.sync_subcategory_collections(dry_run=dry_run)
        else:
            raise HTTPException(
                status_code=400, detail="Debe habilitar al menos sync_main o sync_subcategories"
            )

        logger.info(f"✅ Sincronización completada: {result}")
        return result

    except Exception as e:
        logger.error(f"❌ Error en sincronización de collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al sincronizar collections: {str(e)}")


@router.get("/status")
async def get_collections_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual de las collections en Shopify.

    Retorna información sobre:
    - Collections principales creadas
    - Subcategorías creadas
    - Collections pendientes
    - Configuración actual

    Returns:
        Estado actual del sistema de collections
    """
    try:
        logger.info("📊 Obteniendo estado de collections")

        # Inicializar cliente de Shopify
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        # Inicializar collection manager
        collection_manager = GenderCategoryService(shopify_client=shopify_client)

        # Obtener estado actual
        status = await collection_manager.get_collections_status()

        return status

    except Exception as e:
        logger.error(f"❌ Error al obtener estado de collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener estado: {str(e)}")


@router.post("/validate")
async def validate_configuration() -> Dict[str, Any]:
    """
    Valida la configuración del sistema de collections.

    Verifica:
    - Archivos de configuración (gender_mapping.json, category_mapping.json, etc.)
    - Mapeos de género y categoría
    - Coherencia de la estructura de collections
    - Detección de configuraciones faltantes o inválidas

    Returns:
        Resultado de la validación con detalles de errores/advertencias
    """
    try:
        logger.info("🔍 Validando configuración de collections")

        # Inicializar collection manager para validación
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        collection_manager = GenderCategoryService(shopify_client=shopify_client)

        # Ejecutar validación
        validation_result = await collection_manager.validate_configuration()

        if validation_result["is_valid"]:
            logger.info("✅ Configuración válida")
        else:
            logger.warning(f"⚠️ Configuración tiene errores: {validation_result['errors']}")

        return validation_result

    except Exception as e:
        logger.error(f"❌ Error al validar configuración: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en validación: {str(e)}")


@router.get("/mapping")
async def get_mapping_configuration() -> Dict[str, Any]:
    """
    Obtiene la configuración actual de mapeos de género y categoría.

    Retorna:
    - Mapeo de género RMS → product_type Shopify
    - Mapeo de categoría RMS → tags Shopify
    - Estructura de collections configurada
    - Reglas especiales y notas

    Returns:
        Configuración completa de mapeos
    """
    try:
        logger.info("📋 Obteniendo configuración de mapeos")

        # Inicializar collection manager
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        collection_manager = GenderCategoryService(shopify_client=shopify_client)

        # Obtener configuración
        mapping_config = {
            "gender_mapping": collection_manager.gender_mapping,
            "category_mapping": collection_manager.category_mapping_config,
            "collections_structure": collection_manager.collections_structure,
        }

        return mapping_config

    except Exception as e:
        logger.error(f"❌ Error al obtener configuración de mapeos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener mapeos: {str(e)}")


@router.delete("/collection/{handle}")
async def delete_collection(handle: str) -> Dict[str, Any]:
    """
    Elimina una collection específica de Shopify por su handle.

    PRECAUCIÓN: Esta operación no se puede deshacer fácilmente.
    Use con cuidado.

    Args:
        handle: Handle único de la collection a eliminar (ej: "mujer-flats")

    Returns:
        Resultado de la eliminación
    """
    try:
        logger.info(f"🗑️ Eliminando collection: {handle}")

        # Inicializar cliente de Shopify
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()

        # Inicializar collection manager
        collection_manager = GenderCategoryService(shopify_client=shopify_client)

        # Eliminar collection
        result = await collection_manager.delete_collection_by_handle(handle)

        logger.info(f"✅ Collection eliminada: {handle}")
        return result

    except Exception as e:
        logger.error(f"❌ Error al eliminar collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al eliminar collection: {str(e)}")
