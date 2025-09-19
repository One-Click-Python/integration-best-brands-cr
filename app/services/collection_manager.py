"""
Servicio para gestionar colecciones basadas en categorías RMS.

Este módulo maneja la creación automática de colecciones en Shopify
basadas en las categorías de productos RMS y asigna productos a las colecciones
correspondientes durante la sincronización.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.utils.distributed_lock import collection_lock
from app.utils.id_utils import is_valid_graphql_id, normalize_collection_id

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Gestiona colecciones en Shopify basadas en categorías RMS.
    """

    def __init__(self, shopify_client: ShopifyGraphQLClient):
        """
        Inicializa el gestor de colecciones.

        Args:
            shopify_client: Cliente GraphQL de Shopify
        """
        self.shopify_client = shopify_client
        self._collections_cache: Dict[str, Dict[str, Any]] = {}
        self._category_to_collection: Dict[str, str] = {}  # Mapeo categoría -> collection_id
        self._familia_to_collection: Dict[str, str] = {}  # Mapeo familia -> collection_id
        self._initialized = False

    async def initialize(self):
        """
        Inicializa el gestor cargando las colecciones existentes.
        """
        if self._initialized:
            return

        try:
            logger.info("Inicializando gestor de colecciones...")
            await self._load_existing_collections()
            self._initialized = True
            logger.info(f"Gestor de colecciones inicializado - {len(self._collections_cache)} colecciones existentes")
        except Exception as e:
            logger.error(f"Error inicializando gestor de colecciones: {e}")
            raise

    async def _load_existing_collections(self):
        """
        Carga todas las colecciones existentes en Shopify.
        """
        try:
            logger.info("Cargando colecciones existentes de Shopify...")
            all_collections = await self.shopify_client.get_all_collections()

            for collection in all_collections:
                handle = collection.get("handle", "")
                title = collection.get("title", "")
                collection_id = collection.get("id", "")

                # Normalizar el ID al formato GraphQL
                normalized_id = normalize_collection_id(collection_id)

                # Almacenar en cache
                self._collections_cache[handle] = collection

                # Mapear por título normalizado usando ID normalizado
                normalized_title = self._normalize_name(title)
                self._category_to_collection[normalized_title] = normalized_id

                # También mapear el título original usando ID normalizado
                self._category_to_collection[title.lower()] = normalized_id

                logger.debug(
                    f"Colección cargada: '{title}' (handle: {handle}, "
                    f"normalized_title: {normalized_title}, ID: {normalized_id})"
                )

        except Exception as e:
            logger.error(f"Error cargando colecciones existentes: {e}")
            raise

    def _normalize_name(self, name: str) -> str:
        """
        Normaliza un nombre para comparación.

        Args:
            name: Nombre a normalizar

        Returns:
            Nombre normalizado
        """
        if not name:
            return ""

        # Convertir a minúsculas
        normalized = name.lower()

        # Remover acentos
        replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        # Remover caracteres especiales excepto espacios y guiones
        normalized = re.sub(r"[^a-z0-9\s\-]", "", normalized)

        # Reemplazar múltiples espacios por uno solo
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _generate_collection_handle(self, collection_name: str, collection_type: str) -> str:
        """
        Genera un handle único y consistente para una colección basado en su nombre y tipo.

        Args:
            collection_name: Nombre de la colección
            collection_type: Tipo de colección (categoria/familia/extended)

        Returns:
            Handle normalizado para la colección
        """
        if not collection_name:
            return f"rms-{collection_type}-unknown"

        # Normalizar el nombre
        normalized = self._normalize_name(collection_name)

        # Reemplazar espacios por guiones
        handle_base = normalized.replace(" ", "-").replace("_", "-")

        # Asegurar que no hay guiones dobles
        handle_base = re.sub(r"-+", "-", handle_base)

        # Remover guiones al inicio y final
        handle_base = handle_base.strip("-")

        # Generar handle simple (sin prefijo para compatibilidad con colecciones manuales existentes)
        handle = handle_base

        logger.debug(f"Generated handle for '{collection_name}' ({collection_type}): {handle}")
        return handle

    def _get_alternative_handles(self, collection_name: str, collection_type: str) -> List[str]:
        """
        Genera handles alternativos para buscar colecciones existentes.

        Args:
            collection_name: Nombre de la colección
            collection_type: Tipo de colección

        Returns:
            Lista de handles posibles
        """
        base_handle = self._generate_collection_handle(collection_name, collection_type)

        alternatives = [
            base_handle,  # Handle simple: "tenis"
            f"rms-{collection_type}-{base_handle}",  # Handle con prefijo: "rms-categoria-tenis"
            f"{collection_type}-{base_handle}",  # Handle con tipo: "categoria-tenis"
        ]

        # Remover duplicados manteniendo el orden
        seen = set()
        unique_alternatives = []
        for handle in alternatives:
            if handle not in seen:
                seen.add(handle)
                unique_alternatives.append(handle)

        return unique_alternatives

    async def ensure_collection_exists(
        self, categoria: Optional[str], familia: Optional[str], extended_category: Optional[str] = None
    ) -> Optional[str]:
        """
        Asegura que existe una colección para la categoría/familia dada.
        Si no existe, la crea.

        Args:
            categoria: Categoría del producto RMS
            familia: Familia del producto RMS
            extended_category: Categoría extendida (opcional)

        Returns:
            ID de la colección o None si no se pudo crear/encontrar
        """
        try:
            # Determinar el nombre de la colección basado en prioridad
            collection_name = None
            collection_type = None

            # Prioridad 1: Categoría específica
            if categoria and categoria.strip():
                collection_name = categoria.strip()
                collection_type = "categoria"

            # Prioridad 2: Familia si no hay categoría
            elif familia and familia.strip():
                collection_name = familia.strip()
                collection_type = "familia"

            # Prioridad 3: Categoría extendida si no hay categoría ni familia
            elif extended_category and extended_category.strip():
                # Tomar solo el último nivel de la categoría extendida
                parts = extended_category.split(">")
                collection_name = parts[-1].strip() if parts else extended_category.strip()
                collection_type = "extended"

            if not collection_name:
                logger.warning("No se pudo determinar nombre de colección - sin categoría/familia")
                return None

            # Generar handle consistente basado en el nombre de la colección
            handle = self._generate_collection_handle(collection_name, collection_type)

            # Usar lock distribuido para prevenir race conditions durante la creación
            async with collection_lock(handle, timeout_seconds=30) as lock_acquired:
                if not lock_acquired:
                    logger.info(f"⏳ Otra operación está procesando la colección '{collection_name}', esperando...")
                    # Si no pudimos obtener el lock, hacer una verificación final
                    await asyncio.sleep(1)  # Breve espera

                    # Verificar cache nuevamente por si se creó mientras esperábamos
                    normalized_name = self._normalize_name(collection_name)
                    if normalized_name in self._category_to_collection:
                        collection_id = self._category_to_collection[normalized_name]
                        logger.info(
                            f"✅ Colección encontrada después de espera: '{collection_name}' -> {collection_id}"
                        )
                        return collection_id

                    # Si aún no existe, hacer verificación API
                    try:
                        fresh_collection = await self.shopify_client.get_collection_by_handle(handle)
                        if fresh_collection:
                            collection_id = fresh_collection.get("id")
                            normalized_id = normalize_collection_id(collection_id)

                            # Actualizar caches
                            self._collections_cache[handle] = fresh_collection
                            self._category_to_collection[normalized_name] = normalized_id
                            self._category_to_collection[collection_name.lower()] = normalized_id

                            return normalized_id
                    except Exception as e:
                        logger.warning(f"Error verificando colección después de lock fallido: {e}")

                    return None  # No pudimos crear ni encontrar la colección

                # Lock adquirido, proceder con verificaciones y creación
                logger.debug(f"🔒 Lock adquirido para colección: {collection_name}")

                # Verificar si ya existe en cache
                normalized_name = self._normalize_name(collection_name)

                # Buscar por nombre normalizado
                if normalized_name in self._category_to_collection:
                    collection_id = self._category_to_collection[normalized_name]
                    logger.debug(f"Colección encontrada en cache por nombre: '{collection_name}' -> {collection_id}")
                    return collection_id

                # Obtener handles alternativos para buscar colecciones existentes
                possible_handles = self._get_alternative_handles(collection_name, collection_type)
                logger.debug(f"Buscando colección '{collection_name}' con handles: {possible_handles}")

                # Buscar por handles en cache
                for candidate_handle in possible_handles:
                    if candidate_handle in self._collections_cache:
                        collection = self._collections_cache[candidate_handle]
                        collection_id = collection.get("id")
                        normalized_id = normalize_collection_id(collection_id)

                        logger.info(
                            f"✅ Colección encontrada en cache por handle: '{candidate_handle}' -> {normalized_id}"
                        )

                        # Actualizar caches con el handle principal también
                        self._collections_cache[handle] = collection
                        self._category_to_collection[normalized_name] = normalized_id
                        self._category_to_collection[collection_name.lower()] = normalized_id

                        return normalized_id

                # Antes de crear, hacer una verificación fresca con la API de Shopify
                logger.info(f"Verificando existencia de colección '{collection_name}' con API de Shopify...")

                # Probar todos los handles posibles en Shopify
                for candidate_handle in possible_handles:
                    try:
                        fresh_collection = await self.shopify_client.get_collection_by_handle(candidate_handle)

                        if fresh_collection:
                            collection_id = fresh_collection.get("id")
                            normalized_id = normalize_collection_id(collection_id)
                            actual_handle = fresh_collection.get("handle", candidate_handle)

                            logger.info(
                                f"✅ Colección encontrada en Shopify con handle '{actual_handle}': '{collection_name}' "
                                f"(ID: {normalized_id})"
                            )

                            # Actualizar caches con la colección encontrada usando el handle real
                            self._collections_cache[actual_handle] = fresh_collection
                            self._collections_cache[handle] = fresh_collection  # También con el handle generado
                            self._category_to_collection[normalized_name] = normalized_id
                            self._category_to_collection[collection_name.lower()] = normalized_id

                            return normalized_id

                    except Exception as e:
                        logger.debug(f"Handle '{candidate_handle}' no encontrado: {e}")
                        continue

                logger.debug(f"Ninguno de los handles {possible_handles} encontrado en Shopify")

                # Si no existe, crearla
                logger.info(f"Creando nueva colección: '{collection_name}' (tipo: {collection_type})")

            # Preparar datos de la colección
            collection_data = {
                "title": collection_name,
                "handle": handle,
                "descriptionHtml": self._generate_collection_description(
                    collection_name, collection_type, categoria, familia
                ),
                "metafields": [
                    {
                        "namespace": "rms",
                        "key": "source_type",
                        "value": collection_type,
                        "type": "single_line_text_field",
                    }
                ],
            }

            # Agregar metafields adicionales según el tipo
            if collection_type == "categoria" and categoria:
                collection_data["metafields"].append(
                    {"namespace": "rms", "key": "categoria", "value": categoria, "type": "single_line_text_field"}
                )
            elif collection_type == "familia" and familia:
                collection_data["metafields"].append(
                    {"namespace": "rms", "key": "familia", "value": familia, "type": "single_line_text_field"}
                )

            # Crear la colección o obtener la existente si el handle ya está tomado
            created_collection = await self.shopify_client.create_or_get_collection(collection_data)

            if created_collection:
                collection_id = created_collection.get("id")
                normalized_id = normalize_collection_id(collection_id)

                # Actualizar caches inmediatamente con ID normalizado
                self._collections_cache[handle] = created_collection
                self._category_to_collection[normalized_name] = normalized_id
                self._category_to_collection[collection_name.lower()] = normalized_id

                # Verificar que el ID es válido
                if is_valid_graphql_id(normalized_id, "Collection"):
                    logger.info(
                        f"✅ Colección creada exitosamente: '{collection_name}' (ID: {normalized_id}, handle: {handle})"
                    )
                else:
                    logger.warning(
                        f"⚠️ Colección creada con ID inválido: '{collection_name}' "
                        f"(ID: {normalized_id}, handle: {handle})"
                    )

                return normalized_id
            else:
                logger.error(f"No se pudo crear la colección: '{collection_name}'")
                return None

        except Exception as e:
            logger.error(f"Error asegurando colección para '{categoria}/{familia}': {e}")
            return None

    def _generate_collection_description(
        self, name: str, collection_type: str, _: Optional[str], familia: Optional[str]
    ) -> str:
        """
        Genera una descripción HTML para la colección.

        Args:
            name: Nombre de la colección
            collection_type: Tipo de colección (categoria/familia/extended)
            categoria: Categoría RMS
            familia: Familia RMS

        Returns:
            Descripción HTML
        """
        descriptions = {
            "categoria": f"<p>Productos de la categoría <strong>{name}</strong></p>",
            "familia": f"<p>Todos los productos de la familia <strong>{name}</strong></p>",
            "extended": f"<p>Productos relacionados con <strong>{name}</strong></p>",
        }

        base_description = descriptions.get(collection_type, f"<p>Colección de productos <strong>{name}</strong></p>")

        # Agregar información adicional si está disponible
        if collection_type == "categoria" and familia:
            base_description += f"<p>Familia: {familia}</p>"

        base_description += "<p><em>Colección generada automáticamente desde RMS</em></p>"

        return base_description

    async def add_product_to_collections(
        self,
        product_id: str,
        product_handle: str,
        categoria: Optional[str],
        familia: Optional[str],
        extended_category: Optional[str] = None,
    ) -> List[str]:
        """
        Agrega un producto a las colecciones correspondientes basadas en su
        categoría y familia.

        Args:
            product_id: ID del producto en Shopify
            product_handle: Handle del producto
            categoria: Categoría del producto RMS
            familia: Familia del producto RMS
            extended_category: Categoría extendida (opcional)

        Returns:
            Lista de IDs de colecciones a las que se agregó el producto
        """
        if not self._initialized:
            await self.initialize()

        added_to_collections = []

        try:
            # Intentar agregar a colección de categoría
            if categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=categoria, familia=familia, extended_category=extended_category
                )

                if collection_id:
                    try:
                        await self.shopify_client.add_products_to_collection(
                            collection_id=collection_id, product_ids=[product_id]
                        )
                        added_to_collections.append(collection_id)
                        logger.info(f"✅ Producto {product_id} agregado a colección de categoría '{categoria}'")
                    except Exception as e:
                        logger.warning(f"No se pudo agregar producto a colección de categoría: {e}")

            # También agregar a colección de familia si es diferente
            if familia and familia != categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=None, familia=familia, extended_category=None
                )

                if collection_id and collection_id not in added_to_collections:
                    try:
                        await self.shopify_client.add_products_to_collection(
                            collection_id=collection_id, product_ids=[product_id]
                        )
                        added_to_collections.append(collection_id)
                        logger.info(f"✅ Producto {product_id} agregado a colección de familia '{familia}'")
                    except Exception as e:
                        logger.warning(f"No se pudo agregar producto a colección de familia: {e}")

            if not added_to_collections:
                logger.warning(
                    f"Producto {product_id} no se agregó a ninguna colección "
                    f"(categoria: {categoria}, familia: {familia})"
                )

        except Exception as e:
            logger.error(f"Error agregando producto {product_id} a colecciones: {e}. Product handle: {product_handle}")

        return added_to_collections

    async def sync_product_collections(
        self,
        product_id: str,
        product_handle: str,
        current_collections: List[str],
        categoria: Optional[str],
        familia: Optional[str],
        extended_category: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        Sincroniza las colecciones de un producto, agregándolo a las nuevas
        y removiéndolo de las que ya no corresponden.

        Args:
            product_id: ID del producto
            current_collections: IDs de colecciones actuales del producto
            categoria: Categoría del producto
            familia: Familia del producto
            extended_category: Categoría extendida

        Returns:
            Dict con las colecciones agregadas y removidas
        """
        if not self._initialized:
            await self.initialize()

        result = {"added": [], "removed": [], "kept": []}

        try:
            # Determinar colecciones objetivo
            target_collections = set()

            # Colección de categoría
            if categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=categoria, familia=familia, extended_category=extended_category
                )
                if collection_id:
                    target_collections.add(collection_id)

            # Colección de familia
            if familia and familia != categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=None, familia=familia, extended_category=None
                )
                if collection_id:
                    target_collections.add(collection_id)

            # Convertir colecciones actuales a set
            current_set = set(current_collections)

            # Determinar cambios
            to_add = target_collections - current_set
            to_remove = current_set - target_collections
            to_keep = target_collections & current_set

            # Agregar a nuevas colecciones
            for collection_id in to_add:
                try:
                    await self.shopify_client.add_products_to_collection(
                        collection_id=collection_id, product_ids=[product_id]
                    )
                    result["added"].append(collection_id)
                except Exception as e:
                    logger.warning(f"Error agregando a colección {collection_id}: {e}")

            # Remover de colecciones obsoletas
            for collection_id in to_remove:
                try:
                    # Solo remover si es una colección manejada por RMS
                    if collection_id in self._category_to_collection.values():
                        await self.shopify_client.remove_products_from_collection(
                            collection_id=collection_id, product_ids=[product_id]
                        )
                        result["removed"].append(collection_id)
                except Exception as e:
                    logger.warning(f"Error removiendo de colección {collection_id}: {e}")

            result["kept"] = list(to_keep)

            if result["added"] or result["removed"]:
                logger.info(
                    f"Sincronización de colecciones para producto {product_id}: "
                    f"+{len(result['added'])} -{len(result['removed'])} "
                    f"={len(result['kept'])}"
                )

        except Exception as e:
            logger.error(f"Error sincronizando colecciones del producto: {e}. Product handle: {product_handle}")

        return result

    def get_collection_stats(self):
        """
        Obtiene estadísticas sobre las colecciones gestionadas.

        Returns:
            Diccionario con estadísticas
        """
        return {
            "total_collections": len(self._collections_cache),
            "category_mappings": len(self._category_to_collection),
            "familia_mappings": len(self._familia_to_collection),
            "initialized": self._initialized,
        }
