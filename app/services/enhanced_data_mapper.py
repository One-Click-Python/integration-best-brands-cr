"""
Servicio mejorado de mapeo de datos RMS a Shopify.

Este módulo reemplaza el mapeo básico con un sistema avanzado que maneja
taxonomías estándar de Shopify y metafields estructurados.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import asdict

from app.core.taxonomy_mapping import RMSTaxonomyMapper, TaxonomyMapping
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.api.v1.schemas.rms_schemas import RMSViewItem

logger = logging.getLogger(__name__)


class EnhancedDataMapper:
    """
    Servicio mejorado para mapear datos de RMS a productos de Shopify
    con taxonomías estándar y metafields estructurados.
    """
    
    def __init__(self, shopify_client: ShopifyGraphQLClient):
        """
        Inicializa el mapeador mejorado.
        
        Args:
            shopify_client: Cliente GraphQL de Shopify
        """
        self.shopify_client = shopify_client
        self.taxonomy_mapper = RMSTaxonomyMapper()
        self._taxonomy_cache: Dict[str, str] = {}
        self._metafield_definitions_created: Set[str] = set()
        
    async def initialize(self) -> None:
        """Inicializa el servicio y crea las definiciones de metafields."""
        logger.info("Initializing Enhanced Data Mapper")
        await self._ensure_metafield_definitions()
        
    async def _ensure_metafield_definitions(self) -> None:
        """
        Asegura que todas las definiciones de metafields estén creadas en Shopify.
        """
        try:
            for key, definition in self.taxonomy_mapper.METAFIELD_DEFINITIONS.items():
                definition_key = f"{definition.namespace}.{definition.key}"
                
                if definition_key not in self._metafield_definitions_created:
                    definition_data = {
                        "name": definition.name,
                        "namespace": definition.namespace,
                        "key": definition.key,
                        "description": definition.description,
                        "type": definition.type.value,
                        "ownerType": "PRODUCT"
                    }
                    
                    result = await self.shopify_client.create_metafield_definition(definition_data)
                    if result:
                        self._metafield_definitions_created.add(definition_key)
                        logger.info(f"Created metafield definition: {definition_key}")
                    else:
                        logger.warning(f"Failed to create metafield definition: {definition_key}")
                        
        except Exception as e:
            logger.error(f"Error ensuring metafield definitions: {e}")
            # No fallar la inicialización por esto
    
    async def map_rms_item_to_shopify_product(self, rms_item: RMSViewItem) -> Dict[str, Any]:
        """
        Mapea un item de RMS a un producto de Shopify con taxonomías y metafields mejorados.
        
        Args:
            rms_item: Item de RMS a mapear
            
        Returns:
            Dict con datos del producto para Shopify
        """
        try:
            # Obtener mapeo de taxonomía
            taxonomy_mapping = self.taxonomy_mapper.get_taxonomy_mapping(
                rms_item.familia or "",
                rms_item.categoria or ""
            )
            
            # Resolver taxonomía en Shopify
            taxonomy_id = await self._resolve_taxonomy_id(taxonomy_mapping)
            
            # Crear metafields
            metafields = self.taxonomy_mapper.create_metafields(
                familia=rms_item.familia or "",
                categoria=rms_item.categoria or "",
                talla=rms_item.talla or "",
                color=rms_item.color or "",
                additional_data={
                    "ccod": rms_item.ccod,
                    "item_id": rms_item.item_id,
                    "price": float(rms_item.price) if rms_item.price else 0.0,
                    "quantity": rms_item.quantity or 0
                }
            )
            
            # Construir producto base
            product_data = {
                "title": rms_item.description,
                "productType": taxonomy_mapping.shopify_product_type,
                "vendor": rms_item.familia or "RMS",
                "status": "ACTIVE" if rms_item.quantity and rms_item.quantity > 0 else "DRAFT",
                "tags": self._generate_tags(rms_item, taxonomy_mapping),
                "metafields": metafields
            }
            
            # Agregar categoría de taxonomía si se resolvió
            if taxonomy_id:
                product_data["category"] = {"id": taxonomy_id}
            
            # Generar variantes
            variants = self._generate_variants(rms_item)
            if variants:
                product_data["variants"] = variants
                
            # Generar opciones de producto (talla, color)
            options = self._generate_product_options(rms_item)
            if options:
                product_data["options"] = options
            
            logger.debug(f"Mapped RMS item {rms_item.ccod} to Shopify product with taxonomy: {taxonomy_mapping.shopify_product_type}")
            return product_data
            
        except Exception as e:
            logger.error(f"Error mapping RMS item {rms_item.ccod}: {e}")
            raise
    
    async def _resolve_taxonomy_id(self, taxonomy_mapping: TaxonomyMapping) -> Optional[str]:
        """
        Resuelve el ID de taxonomía de Shopify para un mapeo dado.
        
        Args:
            taxonomy_mapping: Mapeo de taxonomía
            
        Returns:
            ID de taxonomía de Shopify o None
        """
        try:
            # Usar caché si existe
            cache_key = f"{taxonomy_mapping.rms_familia}_{taxonomy_mapping.rms_categoria}"
            if cache_key in self._taxonomy_cache:
                return self._taxonomy_cache[cache_key]
            
            # Si ya tenemos un ID específico, usarlo
            if taxonomy_mapping.shopify_taxonomy_id:
                self._taxonomy_cache[cache_key] = taxonomy_mapping.shopify_taxonomy_id
                return taxonomy_mapping.shopify_taxonomy_id
            
            # Buscar la mejor coincidencia usando términos de búsqueda
            search_terms = self.taxonomy_mapper.get_search_terms_for_taxonomy_resolution(
                taxonomy_mapping.rms_familia,
                taxonomy_mapping.rms_categoria
            )
            
            best_match = await self.shopify_client.find_best_taxonomy_match(search_terms)
            
            if best_match:
                taxonomy_id = best_match["id"]
                self._taxonomy_cache[cache_key] = taxonomy_id
                logger.info(f"Resolved taxonomy for {cache_key}: {best_match['fullName']} ({taxonomy_id})")
                return taxonomy_id
            else:
                logger.warning(f"No taxonomy found for {cache_key}, using product type only")
                return None
                
        except Exception as e:
            logger.error(f"Error resolving taxonomy ID: {e}")
            return None
    
    def _generate_tags(self, rms_item: RMSViewItem, taxonomy_mapping: TaxonomyMapping) -> List[str]:
        """
        Genera tags para el producto basados en los datos RMS.
        
        Args:
            rms_item: Item de RMS
            taxonomy_mapping: Mapeo de taxonomía
            
        Returns:
            Lista de tags
        """
        tags = []
        
        # Tags basados en RMS
        if rms_item.familia:
            tags.append(f"RMS-{rms_item.familia}")
        if rms_item.categoria:
            tags.append(f"Cat-{rms_item.categoria}")
        if rms_item.talla:
            talla_normalizada, _ = self.taxonomy_mapper.normalize_size(rms_item.talla)
            if talla_normalizada:
                tags.append(f"Size-{talla_normalizada}")
        if rms_item.color:
            tags.append(f"Color-{rms_item.color}")
            
        # Tags de sincronización
        tags.extend([
            "RMS-Sync",
            f"RMS-CCOD-{rms_item.ccod}",
            taxonomy_mapping.shopify_product_type
        ])
        
        # Filtrar tags vacíos y duplicados
        tags = list(filter(None, set(tags)))
        
        return tags[:10]  # Shopify tiene límite de tags
    
    def _generate_variants(self, rms_item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera variantes del producto basadas en talla y color.
        
        Args:
            rms_item: Item de RMS
            
        Returns:
            Lista de variantes
        """
        variants = []
        
        # Por ahora, crear una sola variante principal
        talla_normalizada, talla_original = self.taxonomy_mapper.normalize_size(rms_item.talla or "")
        
        variant = {
            "sku": rms_item.ccod,
            "price": str(rms_item.price) if rms_item.price else "0.00",
            "inventoryQuantity": rms_item.quantity or 0,
            "inventoryManagement": "SHOPIFY",
            "inventoryPolicy": "DENY",
            "requiresShipping": True,
            "taxable": True
        }
        
        # Agregar opciones de variante
        option_values = []
        if talla_normalizada:
            option_values.append(talla_normalizada)
        if rms_item.color:
            option_values.append(rms_item.color)
            
        if option_values:
            variant["optionValues"] = option_values
        
        # Metafields de variante específicos
        variant_metafields = []
        if talla_original and talla_original != talla_normalizada:
            variant_metafields.append({
                "namespace": "rms",
                "key": "original_size",
                "type": "single_line_text_field",
                "value": talla_original
            })
        
        if variant_metafields:
            variant["metafields"] = variant_metafields
        
        variants.append(variant)
        return variants
    
    def _generate_product_options(self, rms_item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera opciones de producto (Size, Color) para variantes.
        
        Args:
            rms_item: Item de RMS
            
        Returns:
            Lista de opciones de producto
        """
        options = []
        
        # Opción de talla
        talla_normalizada, _ = self.taxonomy_mapper.normalize_size(rms_item.talla or "")
        if talla_normalizada:
            options.append({
                "name": "Size",
                "values": [talla_normalizada]
            })
        
        # Opción de color
        if rms_item.color:
            options.append({
                "name": "Color",
                "values": [rms_item.color]
            })
        
        return options
    
    def get_mapping_statistics(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del mapeo realizado.
        
        Returns:
            Dict con estadísticas
        """
        return {
            "taxonomy_cache_size": len(self._taxonomy_cache),
            "metafield_definitions_created": len(self._metafield_definitions_created),
            "cached_taxonomies": list(self._taxonomy_cache.keys())
        }
    
    async def validate_product_mapping(self, rms_item: RMSViewItem) -> Dict[str, Any]:
        """
        Valida el mapeo de un producto RMS sin crearlo.
        
        Args:
            rms_item: Item de RMS a validar
            
        Returns:
            Dict con resultado de validación
        """
        try:
            validation_result = {
                "valid": True,
                "warnings": [],
                "errors": [],
                "mapping_info": {}
            }
            
            # Validar campos obligatorios
            if not rms_item.description:
                validation_result["errors"].append("Missing product title/description")
                validation_result["valid"] = False
            
            if not rms_item.ccod:
                validation_result["errors"].append("Missing product SKU/CCOD")
                validation_result["valid"] = False
            
            # Validar mapeo de taxonomía
            taxonomy_mapping = self.taxonomy_mapper.get_taxonomy_mapping(
                rms_item.familia or "",
                rms_item.categoria or ""
            )
            
            validation_result["mapping_info"]["taxonomy"] = {
                "familia": rms_item.familia,
                "categoria": rms_item.categoria,
                "shopify_product_type": taxonomy_mapping.shopify_product_type,
                "search_terms": taxonomy_mapping.search_terms
            }
            
            # Validar talla
            if rms_item.talla:
                talla_normalizada, talla_original = self.taxonomy_mapper.normalize_size(rms_item.talla)
                validation_result["mapping_info"]["size"] = {
                    "original": talla_original,
                    "normalized": talla_normalizada,
                    "changed": talla_original != talla_normalizada
                }
                
                if talla_original != talla_normalizada:
                    validation_result["warnings"].append(f"Size normalized: '{talla_original}' -> '{talla_normalizada}'")
            
            # Validar metafields
            metafields = self.taxonomy_mapper.create_metafields(
                familia=rms_item.familia or "",
                categoria=rms_item.categoria or "",
                talla=rms_item.talla or "",
                color=rms_item.color or ""
            )
            
            validation_result["mapping_info"]["metafields_count"] = len(metafields)
            
            return validation_result
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "mapping_info": {}
            }