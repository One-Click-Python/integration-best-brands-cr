"""
Servicio para gestionar colecciones basadas en categorías RMS.

Este módulo maneja la creación automática de colecciones en Shopify
basadas en las categorías de productos RMS y asigna productos a las colecciones
correspondientes durante la sincronización.
"""

import logging
import re
from typing import Dict, List, Optional, Set

from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.utils.error_handler import ShopifyAPIException

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
        self._collections_cache: Dict[str, Dict[str, any]] = {}
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
            logger.info(
                f"Gestor de colecciones inicializado - "
                f"{len(self._collections_cache)} colecciones existentes"
            )
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
                
                # Almacenar en cache
                self._collections_cache[handle] = collection
                
                # Mapear por título normalizado
                normalized_title = self._normalize_name(title)
                self._category_to_collection[normalized_title] = collection_id
                
                # También mapear el título original
                self._category_to_collection[title.lower()] = collection_id
                
                logger.debug(
                    f"Colección cargada: '{title}' (handle: {handle}, "
                    f"normalized: {normalized_title})"
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
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u'
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
            
        # Remover caracteres especiales excepto espacios y guiones
        normalized = re.sub(r'[^a-z0-9\s\-]', '', normalized)
        
        # Reemplazar múltiples espacios por uno solo
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _create_handle(self, name: str) -> str:
        """
        Crea un handle válido para Shopify a partir de un nombre.
        
        Args:
            name: Nombre de la colección
            
        Returns:
            Handle válido para Shopify
        """
        # Normalizar primero
        handle = self._normalize_name(name)
        
        # Reemplazar espacios por guiones
        handle = handle.replace(' ', '-')
        
        # Remover guiones múltiples
        handle = re.sub(r'-+', '-', handle)
        
        # Remover guiones al inicio y final
        handle = handle.strip('-')
        
        return handle or "sin-categoria"

    async def ensure_collection_exists(
        self, 
        categoria: Optional[str], 
        familia: Optional[str],
        extended_category: Optional[str] = None
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
                parts = extended_category.split('>')
                collection_name = parts[-1].strip() if parts else extended_category.strip()
                collection_type = "extended"
            
            if not collection_name:
                logger.warning("No se pudo determinar nombre de colección - sin categoría/familia")
                return None
                
            # Verificar si ya existe en cache
            normalized_name = self._normalize_name(collection_name)
            
            # Buscar por nombre normalizado
            if normalized_name in self._category_to_collection:
                collection_id = self._category_to_collection[normalized_name]
                logger.debug(
                    f"Colección encontrada en cache: '{collection_name}' -> {collection_id}"
                )
                return collection_id
                
            # Buscar por handle
            handle = self._create_handle(collection_name)
            if handle in self._collections_cache:
                collection = self._collections_cache[handle]
                collection_id = collection.get("id")
                logger.debug(
                    f"Colección encontrada por handle: '{collection_name}' -> {collection_id}"
                )
                return collection_id
                
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
                        "type": "single_line_text_field"
                    }
                ]
            }
            
            # Agregar metafields adicionales según el tipo
            if collection_type == "categoria" and categoria:
                collection_data["metafields"].append({
                    "namespace": "rms",
                    "key": "categoria",
                    "value": categoria,
                    "type": "single_line_text_field"
                })
            elif collection_type == "familia" and familia:
                collection_data["metafields"].append({
                    "namespace": "rms",
                    "key": "familia",
                    "value": familia,
                    "type": "single_line_text_field"
                })
                
            # Crear la colección
            created_collection = await self.shopify_client.create_collection(collection_data)
            
            if created_collection:
                collection_id = created_collection.get("id")
                # Actualizar caches
                self._collections_cache[handle] = created_collection
                self._category_to_collection[normalized_name] = collection_id
                self._category_to_collection[collection_name.lower()] = collection_id
                
                logger.info(
                    f"✅ Colección creada exitosamente: '{collection_name}' "
                    f"(ID: {collection_id}, handle: {handle})"
                )
                return collection_id
            else:
                logger.error(f"No se pudo crear la colección: '{collection_name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error asegurando colección para '{categoria}/{familia}': {e}")
            return None

    def _generate_collection_description(
        self, 
        name: str, 
        collection_type: str,
        categoria: Optional[str],
        familia: Optional[str]
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
            "extended": f"<p>Productos relacionados con <strong>{name}</strong></p>"
        }
        
        base_description = descriptions.get(
            collection_type, 
            f"<p>Colección de productos <strong>{name}</strong></p>"
        )
        
        # Agregar información adicional si está disponible
        if collection_type == "categoria" and familia:
            base_description += f"<p>Familia: {familia}</p>"
            
        base_description += "<p><em>Colección generada automáticamente desde RMS</em></p>"
        
        return base_description

    async def add_product_to_collections(
        self,
        product_id: str,
        categoria: Optional[str],
        familia: Optional[str],
        extended_category: Optional[str] = None
    ) -> List[str]:
        """
        Agrega un producto a las colecciones correspondientes basadas en su
        categoría y familia.
        
        Args:
            product_id: ID del producto en Shopify
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
                    categoria=categoria,
                    familia=familia,
                    extended_category=extended_category
                )
                
                if collection_id:
                    try:
                        await self.shopify_client.add_products_to_collection(
                            collection_id=collection_id,
                            product_ids=[product_id]
                        )
                        added_to_collections.append(collection_id)
                        logger.info(
                            f"✅ Producto {product_id} agregado a colección "
                            f"de categoría '{categoria}'"
                        )
                    except Exception as e:
                        logger.warning(
                            f"No se pudo agregar producto a colección de categoría: {e}"
                        )
            
            # También agregar a colección de familia si es diferente
            if familia and familia != categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=None,
                    familia=familia,
                    extended_category=None
                )
                
                if collection_id and collection_id not in added_to_collections:
                    try:
                        await self.shopify_client.add_products_to_collection(
                            collection_id=collection_id,
                            product_ids=[product_id]
                        )
                        added_to_collections.append(collection_id)
                        logger.info(
                            f"✅ Producto {product_id} agregado a colección "
                            f"de familia '{familia}'"
                        )
                    except Exception as e:
                        logger.warning(
                            f"No se pudo agregar producto a colección de familia: {e}"
                        )
                        
            if not added_to_collections:
                logger.warning(
                    f"Producto {product_id} no se agregó a ninguna colección "
                    f"(categoria: {categoria}, familia: {familia})"
                )
                
        except Exception as e:
            logger.error(
                f"Error agregando producto {product_id} a colecciones: {e}"
            )
            
        return added_to_collections

    async def sync_product_collections(
        self,
        product_id: str,
        current_collections: List[str],
        categoria: Optional[str],
        familia: Optional[str],
        extended_category: Optional[str] = None
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
            
        result = {
            "added": [],
            "removed": [],
            "kept": []
        }
        
        try:
            # Determinar colecciones objetivo
            target_collections = set()
            
            # Colección de categoría
            if categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=categoria,
                    familia=familia,
                    extended_category=extended_category
                )
                if collection_id:
                    target_collections.add(collection_id)
                    
            # Colección de familia
            if familia and familia != categoria:
                collection_id = await self.ensure_collection_exists(
                    categoria=None,
                    familia=familia,
                    extended_category=None
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
                        collection_id=collection_id,
                        product_ids=[product_id]
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
                            collection_id=collection_id,
                            product_ids=[product_id]
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
            logger.error(f"Error sincronizando colecciones del producto: {e}")
            
        return result

    def get_collection_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas sobre las colecciones gestionadas.
        
        Returns:
            Diccionario con estadísticas
        """
        return {
            "total_collections": len(self._collections_cache),
            "category_mappings": len(self._category_to_collection),
            "familia_mappings": len(self._familia_to_collection),
            "initialized": self._initialized
        }