"""
Servicio para gestionar colecciones de Shopify basadas en género y categoría.

Este módulo maneja la creación y sincronización de colecciones inteligentes
(smart collections) en Shopify utilizando el sistema de género + categoría,
con mapeo automático a tags y product_type.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db.shopify_graphql_client import ShopifyGraphQLClient

logger = logging.getLogger(__name__)

# Configuration file paths
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
GENDER_MAPPING_FILE = CONFIG_DIR / "gender_mapping.json"
CATEGORY_MAPPING_FILE = CONFIG_DIR / "category_mapping.json"
COLLECTIONS_STRUCTURE_FILE = CONFIG_DIR / "shopify_collections_structure.json"


class GenderCategoryService:
    """
    Servicio especializado para gestión de colecciones basadas en género y categoría.

    Responsabilidades:
    - Mapeo de género RMS a product_type de Shopify
    - Mapeo de categorías RMS a tags de Shopify
    - Creación de smart collections con reglas automáticas
    - Sincronización de colecciones principales y subcategorías
    - Validación de configuración
    """

    def __init__(self, shopify_client: ShopifyGraphQLClient):
        """
        Inicializa el servicio de colecciones de género/categoría.

        Args:
            shopify_client: Cliente GraphQL de Shopify
        """
        self.shopify_client = shopify_client
        self.gender_mapping = self._load_gender_mapping()
        self.category_mapping_config = self._load_category_mapping()
        self.collections_structure = self._load_collections_structure()
        self._collections_cache: Dict[str, Dict[str, Any]] = {}

    def _load_gender_mapping(self) -> Dict[str, str]:
        """Carga el mapeo de género desde configuración JSON."""
        try:
            with open(GENDER_MAPPING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mappings", {})
        except Exception as e:
            logger.error(f"Error loading gender mapping: {e}")
            return {}

    def _load_category_mapping(self) -> Dict[str, Any]:
        """Carga el mapeo de categorías desde configuración JSON."""
        try:
            with open(CATEGORY_MAPPING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mappings", {})
        except Exception as e:
            logger.error(f"Error loading category mapping: {e}")
            return {}

    def _load_collections_structure(self) -> Dict[str, Any]:
        """Carga la estructura de colecciones desde configuración JSON."""
        try:
            with open(COLLECTIONS_STRUCTURE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading collections structure: {e}")
            return {}

    def map_gender_to_product_type(self, rms_gender: Optional[str]) -> str:
        """
        Mapea género RMS a product_type de Shopify.

        Args:
            rms_gender: Género desde RMS (Mujer, Hombre, Niño, Niña, Unisex)

        Returns:
            Product_type de Shopify (Mujer, Hombre, Infantil, Bolsos)
        """
        if not rms_gender:
            logger.warning("No gender provided, defaulting to 'Mujer'")
            return "Mujer"

        product_type = self.gender_mapping.get(rms_gender, "Mujer")
        logger.debug(f"Mapped gender '{rms_gender}' to product_type '{product_type}'")
        return product_type

    def map_category_to_tags(
        self, rms_familia: Optional[str], rms_categoria: Optional[str], rms_gender: Optional[str] = None
    ) -> List[str]:
        """
        Mapea categoría RMS a tags de Shopify para colecciones automáticas.

        Args:
            rms_familia: Familia del producto RMS
            rms_categoria: Categoría del producto RMS
            rms_gender: Género del producto RMS (opcional)

        Returns:
            Lista de tags para aplicar al producto
        """
        tags = []

        # Caso especial: Bolsos
        if rms_familia == "Accesorios" and rms_categoria == "Bolsos":
            tags.append("Bolsos")
            return tags

        # Mapear categoría a tag
        if rms_categoria:
            category_config = self.category_mapping_config.get(rms_categoria)

            if category_config:
                if isinstance(category_config, dict):
                    tag = category_config.get("tag", rms_categoria)
                else:
                    tag = category_config

                tags.append(tag)
                logger.debug(f"Mapped category '{rms_categoria}' to tag '{tag}'")
            else:
                # Sin mapeo, usar categoría original
                logger.warning(f"No mapping for category '{rms_categoria}', using as-is")
                tags.append(rms_categoria)

        # Agregar tag de género
        if rms_gender:
            product_type = self.map_gender_to_product_type(rms_gender)
            tags.append(product_type)

        return tags

    async def create_smart_collection_with_rules(
        self,
        title: str,
        handle: str,
        rules: List[Dict[str, str]],
        description: Optional[str] = None,
        disjunctive: bool = False,
        sort_order: str = "best-selling",
        published: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una colección inteligente en Shopify con reglas automáticas.

        Args:
            title: Título de la colección
            handle: Handle de la colección (URL slug)
            rules: Lista de reglas automáticas
            description: Descripción de la colección
            disjunctive: Si True, usa lógica OR; si False, usa AND
            sort_order: Orden de clasificación de productos
            published: Si publicar la colección

        Returns:
            Diccionario con la colección creada o None si hubo error
        """
        try:
            # Verificar si la colección ya existe
            existing = await self.shopify_client.get_collection_by_handle(handle)

            if existing:
                logger.info(f"Collection '{title}' already exists (handle: {handle})")
                return existing

            # Crear la colección
            logger.info(f"Creating smart collection: {title} (handle: {handle})")

            collection_input = {
                "title": title,
                "handle": handle,
                "descriptionHtml": description or "",
                "ruleSet": {
                    "appliedDisjunctively": disjunctive,
                    "rules": [
                        {
                            "column": rule["column"].upper(),
                            "relation": rule["relation"].upper(),
                            "condition": rule["condition"],
                        }
                        for rule in rules
                    ],
                },
                "sortOrder": sort_order.upper().replace("-", "_"),
            }

            result = await self.shopify_client.create_collection(collection_input)

            if result:
                logger.info(f"✅ Created collection: {title}")
                return result
            else:
                logger.error(f"Failed to create collection: {title}")
                return None

        except Exception as e:
            logger.error(f"Error creating collection '{title}': {e}")
            return None

    async def sync_main_collections(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sincroniza colecciones principales (Mujer, Hombre, Infantil, Bolsos).

        Args:
            dry_run: Si True, no crea colecciones realmente

        Returns:
            Diccionario con resultados de sincronización
        """
        results = {"created": [], "existing": [], "errors": []}

        main_collections = self.collections_structure.get("main_collections", {})

        for key, config in main_collections.items():
            try:
                logger.info(f"Processing main collection: {config['title']}")

                if dry_run:
                    logger.info(f"[DRY RUN] Would create: {config['title']}")
                    results["created"].append(config["title"])
                    continue

                collection = await self.create_smart_collection_with_rules(
                    title=config["title"],
                    handle=config["handle"],
                    rules=config["rules"],
                    description=config.get("description"),
                    disjunctive=config.get("disjunctive", False),
                    sort_order=config.get("sort_order", "best-selling"),
                    published=config.get("published", True),
                )

                if collection:
                    results["existing"].append(config["title"])
                else:
                    results["errors"].append({"collection": config["title"], "error": "Failed to create"})

            except Exception as e:
                logger.error(f"Error syncing '{config['title']}': {e}")
                results["errors"].append({"collection": config.get("title", key), "error": str(e)})

        return results

    async def sync_subcategory_collections(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sincroniza colecciones de subcategorías.

        Args:
            dry_run: Si True, no crea colecciones realmente

        Returns:
            Diccionario con resultados de sincronización
        """
        results = {"created": [], "existing": [], "skipped": [], "errors": []}

        subcategory_collections = self.collections_structure.get("subcategory_collections", {})

        for gender_key, categories in subcategory_collections.items():
            for category_key, config in categories.items():
                try:
                    if config.get("status") == "pending_implementation":
                        logger.info(f"Skipping pending: {config['title']}")
                        results["skipped"].append(config["title"])
                        continue

                    logger.info(f"Processing: {config['title']}")

                    if dry_run:
                        logger.info(f"[DRY RUN] Would create: {config['title']}")
                        results["created"].append(config["title"])
                        continue

                    collection = await self.create_smart_collection_with_rules(
                        title=config["title"],
                        handle=config["handle"],
                        rules=config["rules"],
                        description=config.get("description"),
                        disjunctive=config.get("disjunctive", False),
                        sort_order=config.get("sort_order", "best-selling"),
                        published=config.get("published", True),
                    )

                    if collection:
                        results["existing"].append(config["title"])
                    else:
                        results["errors"].append({"collection": config["title"], "error": "Failed to create"})

                except Exception as e:
                    logger.error(f"Error syncing '{config['title']}': {e}")
                    results["errors"].append(
                        {"collection": config.get("title", f"{gender_key}-{category_key}"), "error": str(e)}
                    )

        return results

    async def sync_all_gender_collections(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sincroniza todas las colecciones basadas en género (principales + subcategorías).

        Args:
            dry_run: Si True, no crea colecciones realmente

        Returns:
            Diccionario combinado con todos los resultados de sincronización
        """
        logger.info(f"🚀 Starting gender collection sync (dry_run={dry_run})")

        # Sincronizar colecciones principales
        logger.info("📁 Syncing main collections...")
        main_results = await self.sync_main_collections(dry_run=dry_run)

        # Sincronizar subcategorías
        logger.info("📂 Syncing subcategories...")
        sub_results = await self.sync_subcategory_collections(dry_run=dry_run)

        # Combinar resultados
        combined = {
            "main_collections": main_results,
            "subcategory_collections": sub_results,
            "summary": {
                "total_created": len(main_results["created"]) + len(sub_results["created"]),
                "total_existing": len(main_results["existing"]) + len(sub_results["existing"]),
                "total_skipped": len(sub_results["skipped"]),
                "total_errors": len(main_results["errors"]) + len(sub_results["errors"]),
            },
            "dry_run": dry_run,
        }

        logger.info(f"✅ Gender collection sync complete: {combined['summary']}")
        return combined

    async def get_collections_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual de las colecciones en Shopify.

        Returns:
            Diccionario con información de estado de colecciones
        """
        try:
            logger.info("📊 Fetching collections status from Shopify...")

            # Cargar todas las colecciones desde Shopify
            all_collections = await self.shopify_client.get_all_collections()

            # Crear cache de handles
            self._collections_cache = {collection.get("handle", ""): collection for collection in all_collections}

            # Analizar colecciones principales
            main_collections_status = {}
            for main_key, main_config in self.collections_structure["main_collections"].items():
                handle = main_config["handle"]
                exists = handle in self._collections_cache
                main_collections_status[main_key] = {
                    "handle": handle,
                    "title": main_config["title"],
                    "exists": exists,
                    "published": main_config.get("published", True),
                }

            # Analizar subcategorías
            subcategories_status = {}
            for parent_key, subcats in self.collections_structure["subcategory_collections"].items():
                subcategories_status[parent_key] = {}
                for subcat_key, subcat_config in subcats.items():
                    handle = subcat_config["handle"]
                    exists = handle in self._collections_cache
                    subcategories_status[parent_key][subcat_key] = {
                        "handle": handle,
                        "title": subcat_config["title"],
                        "exists": exists,
                        "published": subcat_config.get("published", True),
                        "status": subcat_config.get("status", "active"),
                    }

            # Estadísticas resumen
            total_main = len(self.collections_structure["main_collections"])
            total_subcats = sum(
                len(subcats) for subcats in self.collections_structure["subcategory_collections"].values()
            )
            total_expected = total_main + total_subcats

            existing_count = len(self._collections_cache)

            return {
                "summary": {
                    "total_expected": total_expected,
                    "total_existing": existing_count,
                    "main_collections_expected": total_main,
                    "subcategories_expected": total_subcats,
                },
                "main_collections": main_collections_status,
                "subcategories": subcategories_status,
            }

        except Exception as e:
            logger.error(f"❌ Error getting collections status: {e}", exc_info=True)
            raise

    async def validate_configuration(self) -> Dict[str, Any]:
        """
        Valida la configuración de colecciones.

        Returns:
            Diccionario con resultados de validación
        """
        errors = []
        warnings = []

        try:
            # Validar mapeo de género
            if not self.gender_mapping:
                errors.append("gender_mapping is empty or not loaded")
            else:
                logger.info(f"✅ Gender mapping loaded: {len(self.gender_mapping)} entries")

            # Validar mapeo de categorías
            if not self.category_mapping_config:
                errors.append("category_mapping_config is empty or not loaded")
            else:
                logger.info(f"✅ Category mapping loaded: {len(self.category_mapping_config)} entries")

            # Validar estructura de colecciones
            if not self.collections_structure:
                errors.append("collections_structure is empty or not loaded")
            else:
                # Verificar colecciones principales
                main_collections = self.collections_structure.get("main_collections", {})
                if not main_collections:
                    errors.append("No main_collections defined in structure")
                else:
                    logger.info(f"✅ Main collections defined: {len(main_collections)}")

                # Verificar subcategorías
                subcategories = self.collections_structure.get("subcategory_collections", {})
                if not subcategories:
                    warnings.append("No subcategory_collections defined in structure")
                else:
                    total_subcats = sum(len(subcats) for subcats in subcategories.values())
                    logger.info(f"✅ Subcategories defined: {total_subcats}")

            # Verificar implementaciones pendientes
            for parent_key, subcats in self.collections_structure.get("subcategory_collections", {}).items():
                for subcat_key, subcat_config in subcats.items():
                    if subcat_config.get("status") == "pending_implementation":
                        warnings.append(f"Subcategory '{parent_key}.{subcat_key}' is pending implementation")

            # Validar reglas especiales
            special_rules = self.category_mapping_config.get("special_rules", {})
            for rule_key, rule_config in special_rules.items():
                if rule_config.get("status") == "pending_client_decision":
                    warnings.append(f"Special rule '{rule_key}' is pending client decision")

            is_valid = len(errors) == 0

            return {
                "is_valid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "summary": {
                    "total_errors": len(errors),
                    "total_warnings": len(warnings),
                    "gender_mappings": len(self.gender_mapping),
                    "category_mappings": len(self.category_mapping_config.get("mappings", {})),
                    "main_collections": len(self.collections_structure.get("main_collections", {})),
                    "subcategories": sum(
                        len(subcats)
                        for subcats in self.collections_structure.get("subcategory_collections", {}).values()
                    ),
                },
            }

        except Exception as e:
            logger.error(f"❌ Error validating configuration: {e}", exc_info=True)
            errors.append(f"Validation failed with exception: {str(e)}")
            return {"is_valid": False, "errors": errors, "warnings": warnings}

    async def delete_collection_by_handle(self, handle: str) -> Dict[str, Any]:
        """
        Elimina una colección por su handle.

        Args:
            handle: Handle de la colección a eliminar

        Returns:
            Diccionario con resultado de eliminación
        """
        try:
            logger.info(f"🗑️ Deleting collection with handle: {handle}")

            # Cargar colecciones si no están en cache
            if not self._collections_cache:
                all_collections = await self.shopify_client.get_all_collections()
                self._collections_cache = {collection.get("handle", ""): collection for collection in all_collections}

            # Verificar si existe
            if handle not in self._collections_cache:
                logger.warning(f"⚠️ Collection '{handle}' not found in Shopify")
                return {"success": False, "message": f"Collection '{handle}' not found", "handle": handle}

            # Obtener ID de la colección
            collection_data = self._collections_cache[handle]
            collection_id = collection_data.get("id")

            if not collection_id:
                logger.error(f"❌ Collection '{handle}' has no ID")
                return {"success": False, "message": f"Collection '{handle}' has no ID", "handle": handle}

            # Eliminar colección
            success = await self.shopify_client.delete_collection(collection_id)

            if not success:
                logger.error(f"❌ Failed to delete collection '{handle}'")
                return {
                    "success": False,
                    "message": f"Failed to delete collection '{handle}'",
                    "handle": handle,
                }

            # Remover del cache
            del self._collections_cache[handle]

            logger.info(f"✅ Collection '{handle}' deleted successfully")
            return {
                "success": True,
                "message": f"Collection '{handle}' deleted successfully",
                "handle": handle,
                "deleted_id": collection_id,
            }

        except Exception as e:
            logger.error(f"❌ Error deleting collection '{handle}': {e}", exc_info=True)
            return {"success": False, "message": f"Exception: {str(e)}", "handle": handle}
