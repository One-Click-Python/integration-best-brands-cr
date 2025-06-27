"""
Mapeador de datos entre RMS y Shopify.

Este módulo contiene las funciones de mapeo para convertir datos entre
los formatos de RMS y Shopify GraphQL API.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import (
    ProductStatus,
    ShopifyOption,
    ShopifyProductInput,
    ShopifyVariantInput,
)
from app.db.shopify_graphql_client import ShopifyGraphQLClient

logger = logging.getLogger(__name__)

# Mapeo de categorías RMS a términos de búsqueda de Shopify Taxonomy
RMS_TO_SHOPIFY_CATEGORY_MAPPING = {
    "Tenis": "Athletic Shoes",
    "Zapatos": "Shoes",
    "Botas": "Boots",
    "Sandalia": "Sandals",
    "Flats": "Flats",
    "Bolsos": "Handbags",
    "Carteras": "Handbags",
    "Mochilas": "Backpacks",
    "Accesorios": "Accessories",
    "Billeteras": "Wallets",
    "Correas": "Belts",
    "Sombreros": "Hats",
}

# Cache para categorías ya resueltas
_category_cache: Dict[str, Optional[str]] = {}


class RMSToShopifyMapper:
    """
    Mapeador de datos de RMS a Shopify usando GraphQL schemas.
    """

    @staticmethod
    async def resolve_category_id(rms_categoria: Optional[str], shopify_client: ShopifyGraphQLClient) -> Optional[str]:
        """
        Resuelve el ID de categoría de Shopify Standard Product Taxonomy para una categoría RMS.

        Args:
            rms_categoria: Categoría del producto RMS
            shopify_client: Cliente de Shopify para hacer la búsqueda

        Returns:
            ID de categoría de Shopify o None si no se encuentra
        """
        if not rms_categoria:
            return None

        # Verificar cache primero
        if rms_categoria in _category_cache:
            return _category_cache[rms_categoria]

        # Obtener término de búsqueda
        search_term = RMS_TO_SHOPIFY_CATEGORY_MAPPING.get(rms_categoria, rms_categoria)

        try:
            # Buscar categorías en Shopify
            categories = await shopify_client.search_taxonomy_categories(search_term)

            if categories:
                # Tomar la primera categoría encontrada
                category_id = categories[0]["id"]
                logger.info(
                    f"Mapped RMS category '{rms_categoria}' to Shopify category "
                    f"'{categories[0]['name']}' (ID: {category_id})"
                )

                # Guardar en cache
                _category_cache[rms_categoria] = category_id
                return category_id
            else:
                logger.warning(
                    f"No Shopify category found for RMS category '{rms_categoria}' (search: '{search_term}')"
                )
                _category_cache[rms_categoria] = None
                return None

        except Exception as e:
            logger.error(f"Error resolving category for '{rms_categoria}': {e}")
            _category_cache[rms_categoria] = None
            return None

    @staticmethod
    async def map_product_to_shopify_with_category(
        rms_item: RMSViewItem, shopify_client: ShopifyGraphQLClient, location_id: Optional[str] = None
    ) -> ShopifyProductInput:
        """
        Convierte un item RMS a formato de producto Shopify GraphQL con categoría de taxonomía.

        Args:
            rms_item: Item de RMS a convertir
            shopify_client: Cliente de Shopify para resolución de categorías
            location_id: ID de ubicación para inventario (opcional)

        Returns:
            ShopifyProductInput: Producto mapeado con categoría de taxonomía
        """
        # Obtener el mapeo básico
        shopify_input = RMSToShopifyMapper.map_product_to_shopify(rms_item, location_id)

        # Resolver categoría de taxonomía
        category_id = await RMSToShopifyMapper.resolve_category_id(rms_item.categoria, shopify_client)
        shopify_input.category = category_id

        return shopify_input

    @staticmethod
    def map_product_to_shopify(rms_item: RMSViewItem, location_id: Optional[str] = None) -> ShopifyProductInput:
        """
        Convierte un item RMS a formato de producto Shopify GraphQL.

        Args:
            rms_item: Item de RMS validado

        Returns:
            ShopifyProductInput: Producto en formato Shopify
        """
        try:
            # Generar handle único
            handle = RMSToShopifyMapper._generate_handle(rms_item.description or "", rms_item.c_articulo)

            # Generar tags
            tags = RMSToShopifyMapper._generate_tags(rms_item)

            # Crear opciones de producto
            options = RMSToShopifyMapper._generate_options(rms_item)

            # Crear variante
            variant = RMSToShopifyMapper._map_variant(rms_item, location_id)

            # Productos siempre como DRAFT hasta completar información visual
            status = ProductStatus.DRAFT

            # Generar descripción HTML completa
            description_html = RMSToShopifyMapper.create_product_description(rms_item)

            # Limpiar título - eliminar espacios múltiples
            clean_title = (rms_item.description or f"Producto {rms_item.c_articulo}").strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            # Generar metafields incluyendo los específicos de categoría
            metafields = RMSToShopifyMapper._generate_complete_metafields(rms_item)

            return ShopifyProductInput(
                title=clean_title,
                handle=handle,
                status=status,
                productType=rms_item.categoria or "",
                vendor=rms_item.familia or "",
                tags=tags,
                options=[opt.name for opt in options] if options else None,
                variants=[variant] if variant else None,
                description=description_html,
                metafields=metafields,
            )

        except Exception as e:
            logger.error(f"Error mapping RMS item {rms_item.c_articulo} to Shopify: {e}")
            raise

    @staticmethod
    def _map_variant(rms_item: RMSViewItem, location_id: Optional[str] = None) -> ShopifyVariantInput:
        """
        Mapea una variante de RMS a Shopify.

        Args:
            rms_item: Item RMS

        Returns:
            ShopifyVariantInput: Variante para Shopify
        """
        # Determinar precio efectivo y precio de comparación
        effective_price = rms_item.effective_price
        compare_at_price = None

        # Si está en oferta, el precio normal es el compare_at_price
        if rms_item.is_on_sale and rms_item.sale_price:
            compare_at_price = str(rms_item.price)

        # Generar opciones de la variante
        variant_options = []
        if rms_item.color:
            variant_options.append(rms_item.color)
        if rms_item.talla:
            variant_options.append(rms_item.talla)
        if rms_item.genero and len(variant_options) < 3:
            variant_options.append(rms_item.genero)

        # Asegurar al menos una opción
        if not variant_options:
            variant_options = ["Default"]

        # Preparar inventario si se proporciona location_id
        inventory_quantities = None
        if location_id and rms_item.quantity > 0:
            inventory_quantities = [{"availableQuantity": rms_item.quantity, "locationId": location_id}]

        return ShopifyVariantInput(
            sku=rms_item.c_articulo,
            price=str(effective_price),
            compareAtPrice=compare_at_price,
            options=variant_options,
            inventoryQuantities=inventory_quantities,
            inventoryManagement="SHOPIFY",  # Enable inventory tracking
            inventoryPolicy="DENY",  # Deny purchases when out of stock
        )

    @staticmethod
    def _generate_handle(title: str, sku: str) -> str:
        """
        Genera un handle único para Shopify.

        Args:
            title: Título del producto
            sku: SKU del producto

        Returns:
            str: Handle generado
        """
        # Limpiar título
        handle = title.lower().strip()
        handle = re.sub(r"[^\w\s-]", "", handle)
        handle = re.sub(r"\s+", "-", handle)
        handle = re.sub(r"-+", "-", handle)
        handle = handle.strip("-")

        # Si está vacío, usar solo SKU
        if not handle:
            handle = "producto"

        # Agregar SKU para unicidad
        handle = f"{handle}-{sku.lower()}"

        return handle[:100]  # Límite de Shopify

    @staticmethod
    def _generate_tags(rms_item: RMSViewItem) -> List[str]:
        """
        Genera tags para el producto.

        Args:
            rms_item: Item RMS

        Returns:
            List[str]: Lista de tags
        """
        tags = []

        # Tags de clasificación
        if rms_item.familia:
            tags.append(rms_item.familia)

        if rms_item.categoria:
            tags.append(rms_item.categoria)

        if rms_item.genero:
            tags.append(rms_item.genero)

        if rms_item.extended_category:
            tags.append(rms_item.extended_category)

        # Tags de atributos
        if rms_item.color:
            tags.append(f"Color-{rms_item.color}")

        if rms_item.talla:
            tags.append(f"Talla-{rms_item.talla}")

        # Tag de promoción
        if rms_item.is_on_sale:
            tags.append("En-Oferta")

        # Tag de origen
        tags.append("RMS-Sync")

        return tags

    @staticmethod
    def _generate_options(rms_item: RMSViewItem) -> List[ShopifyOption]:
        """
        Genera opciones de producto para Shopify.

        Args:
            rms_item: Item RMS

        Returns:
            List[ShopifyOption]: Opciones del producto
        """
        options = []

        # Opción 1: Color (siempre presente)
        color_values = [rms_item.color] if rms_item.color else ["Default"]
        options.append(ShopifyOption(name="Color", values=color_values))

        # Opción 2: Talla (si existe)
        if rms_item.talla:
            options.append(ShopifyOption(name="Talla", values=[rms_item.talla]))

        # Opción 3: Género (si existe y no hay talla)
        elif rms_item.genero:
            options.append(ShopifyOption(name="Género", values=[rms_item.genero]))

        return options

    @staticmethod
    def create_product_description(rms_item: RMSViewItem) -> str:
        """
        Crea una descripción simple para el producto (solo el título, sin HTML).

        Args:
            rms_item: Item RMS

        Returns:
            str: Descripción simple igual al título
        """
        # Solo retornar el título limpio, sin HTML
        clean_title = (rms_item.description or f"Producto {rms_item.c_articulo}").strip()
        clean_title = re.sub(r"\s+", " ", clean_title)  # Eliminar espacios múltiples
        return clean_title

    @staticmethod
    def _generate_complete_metafields(rms_item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera metafields completos incluyendo los específicos de categoría.

        Args:
            rms_item: Item RMS

        Returns:
            List: Metafields completos
        """
        from datetime import datetime, timezone
        
        metafields = []

        # Información básica de RMS
        if rms_item.familia:
            metafields.append({
                "namespace": "rms",
                "key": "familia",
                "value": str(rms_item.familia),
                "type": "single_line_text_field"
            })

        if rms_item.categoria:
            metafields.append({
                "namespace": "rms",
                "key": "categoria",
                "value": str(rms_item.categoria),
                "type": "single_line_text_field"
            })

        if rms_item.color:
            metafields.append({
                "namespace": "rms",
                "key": "color",
                "value": str(rms_item.color),
                "type": "single_line_text_field"
            })

        if rms_item.talla:
            metafields.append({
                "namespace": "rms",
                "key": "talla",
                "value": str(rms_item.talla),
                "type": "single_line_text_field"
            })

        if rms_item.ccod:
            metafields.append({
                "namespace": "rms",
                "key": "ccod",
                "value": str(rms_item.ccod),
                "type": "single_line_text_field"
            })

        if rms_item.item_id:
            metafields.append({
                "namespace": "rms",
                "key": "item_id",
                "value": str(rms_item.item_id),
                "type": "number_integer"
            })

        if rms_item.extended_category:
            metafields.append({
                "namespace": "rms",
                "key": "extended_category",
                "value": str(rms_item.extended_category),
                "type": "single_line_text_field"
            })

        # Metafields específicos de categoría basados en datos RMS reales
        # APLICAR PARA TODOS LOS TIPOS DE PRODUCTOS, no solo zapatos
        
        # Color - aplicar para cualquier producto que tenga color en RMS
        if rms_item.color:
            metafields.append({
                "namespace": "custom",
                "key": "color",
                "value": str(rms_item.color),
                "type": "single_line_text_field"
            })
        
        # Target gender - aplicar para cualquier producto que tenga género en RMS
        if rms_item.genero:
            metafields.append({
                "namespace": "custom",
                "key": "target_gender",
                "value": str(rms_item.genero),
                "type": "single_line_text_field"
            })
        
        # Age group - determinar para cualquier producto basado en género
        if rms_item.genero:
            if "Niño" in rms_item.genero or "Niña" in rms_item.genero:
                metafields.append({
                    "namespace": "custom",
                    "key": "age_group",
                    "value": "Kids",
                    "type": "single_line_text_field"
                })
            else:
                metafields.append({
                    "namespace": "custom",
                    "key": "age_group",
                    "value": "Adult", 
                    "type": "single_line_text_field"
                })
        
        # Size mapping - aplicar para CUALQUIER producto que tenga talla
        if rms_item.talla:
            # Mapear según el tipo de producto
            if rms_item.familia == "Zapatos":
                # Para zapatos usar shoe_size
                metafields.append({
                    "namespace": "custom",
                    "key": "shoe_size",
                    "value": str(rms_item.talla),
                    "type": "single_line_text_field"
                })
            elif rms_item.familia == "Ropa":
                # Para ropa usar clothing_size
                metafields.append({
                    "namespace": "custom", 
                    "key": "clothing_size",
                    "value": str(rms_item.talla),
                    "type": "single_line_text_field"
                })
            else:
                # Para otros productos usar size genérico
                metafields.append({
                    "namespace": "custom",
                    "key": "size",
                    "value": str(rms_item.talla),
                    "type": "single_line_text_field"
                })
        
        # Activity - solo para productos deportivos/tenis
        if rms_item.categoria == "Tenis":
            metafields.append({
                "namespace": "custom",
                "key": "activity",
                "value": "Running",
                "type": "single_line_text_field"
            })
        
        # Track quantity - para cualquier producto con inventario
        if rms_item.quantity > 0:
            metafields.append({
                "namespace": "custom",
                "key": "track_quantity",
                "value": "true",
                "type": "boolean"
            })

        # Información de sincronización
        metafields.append({
            "namespace": "sync",
            "key": "last_synced",
            "value": datetime.now(timezone.utc).isoformat(),
            "type": "date_time"
        })

        return metafields


class ShopifyToRMSMapper:
    """
    Mapeador de datos de Shopify a RMS.
    """

    @staticmethod
    def extract_sku_from_variant(variant: Dict[str, Any]) -> Optional[str]:
        """
        Extrae el SKU de una variante de Shopify.

        Args:
            variant: Datos de variante de Shopify

        Returns:
            Optional[str]: SKU si se encuentra
        """
        return variant.get("sku") or variant.get("node", {}).get("sku")

    @staticmethod
    def extract_inventory_item_id(variant: Dict[str, Any]) -> Optional[str]:
        """
        Extrae el ID del item de inventario de una variante.

        Args:
            variant: Datos de variante de Shopify

        Returns:
            Optional[str]: ID del item de inventario
        """
        inventory_item = variant.get("inventoryItem") or variant.get("node", {}).get("inventoryItem")
        if inventory_item:
            return inventory_item.get("id")
        return None

    @staticmethod
    def parse_product_for_updates(shopify_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsea un producto de Shopify para identificar actualizaciones necesarias.

        Args:
            shopify_product: Producto de Shopify

        Returns:
            Dict: Datos parseados para comparación
        """
        parsed = {
            "id": shopify_product.get("id"),
            "title": shopify_product.get("title"),
            "handle": shopify_product.get("handle"),
            "status": shopify_product.get("status"),
            "productType": shopify_product.get("productType"),
            "vendor": shopify_product.get("vendor"),
            "tags": shopify_product.get("tags", []),
            "variants": [],
        }

        # Parsear variantes
        variants = shopify_product.get("variants", {})
        if isinstance(variants, dict) and "edges" in variants:
            for edge in variants["edges"]:
                variant = edge.get("node", {})
                parsed["variants"].append(
                    {
                        "id": variant.get("id"),
                        "sku": variant.get("sku"),
                        "price": variant.get("price"),
                        "compareAtPrice": variant.get("compareAtPrice"),
                        "inventoryQuantity": variant.get("inventoryQuantity"),
                        "inventoryItemId": ShopifyToRMSMapper.extract_inventory_item_id(variant),
                    }
                )

        return parsed


class DataComparator:
    """
    Comparador para determinar diferencias entre productos RMS y Shopify.
    """

    @staticmethod
    def needs_update(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> bool:
        """
        Determina si un producto necesita actualización.

        Args:
            rms_item: Item RMS
            shopify_product: Producto Shopify existente

        Returns:
            bool: True si necesita actualización
        """
        try:
            # Comparar campos básicos
            if DataComparator._title_changed(rms_item, shopify_product):
                return True

            if DataComparator._price_changed(rms_item, shopify_product):
                return True

            if DataComparator._inventory_changed(rms_item, shopify_product):
                return True

            if DataComparator._status_changed(rms_item, shopify_product):
                return True

            return False

        except Exception as e:
            logger.error(f"Error comparing products: {e}")
            return True  # En caso de error, asumir que necesita actualización

    @staticmethod
    def _title_changed(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> bool:
        """Compara títulos."""
        rms_title = rms_item.description or f"Producto {rms_item.c_articulo}"
        shopify_title = shopify_product.get("title", "")
        return rms_title != shopify_title

    @staticmethod
    def _price_changed(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> bool:
        """Compara precios."""
        try:
            rms_price = str(rms_item.effective_price)

            # Obtener precio de la primera variante
            variants = shopify_product.get("variants", {})
            if isinstance(variants, dict) and "edges" in variants:
                edges = variants["edges"]
                if edges:
                    shopify_price = edges[0].get("node", {}).get("price", "0")
                    return rms_price != shopify_price

            return True  # Si no hay variantes, necesita actualización

        except Exception:
            return True

    @staticmethod
    def _inventory_changed(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> bool:
        """Compara inventario."""
        try:
            rms_quantity = rms_item.quantity

            # Obtener cantidad de la primera variante
            variants = shopify_product.get("variants", {})
            if isinstance(variants, dict) and "edges" in variants:
                edges = variants["edges"]
                if edges:
                    shopify_quantity = edges[0].get("node", {}).get("inventoryQuantity", 0)
                    return rms_quantity != shopify_quantity

            return True  # Si no hay variantes, necesita actualización

        except Exception:
            return True

    @staticmethod
    def _status_changed(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> bool:
        """Compara estado del producto."""
        try:
            # Determinar estado esperado basado en inventario
            expected_status = "ACTIVE" if rms_item.quantity > 0 else "DRAFT"
            current_status = shopify_product.get("status", "DRAFT")

            return expected_status != current_status

        except Exception:
            return True

    @staticmethod
    def get_update_summary(rms_item: RMSViewItem, shopify_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtiene resumen de cambios necesarios.

        Args:
            rms_item: Item RMS
            shopify_product: Producto Shopify

        Returns:
            Dict: Resumen de cambios
        """
        changes = {"sku": rms_item.c_articulo, "changes": [], "critical": False}

        if DataComparator._title_changed(rms_item, shopify_product):
            changes["changes"].append("title")

        if DataComparator._price_changed(rms_item, shopify_product):
            changes["changes"].append("price")
            changes["critical"] = True

        if DataComparator._inventory_changed(rms_item, shopify_product):
            changes["changes"].append("inventory")
            changes["critical"] = True

        if DataComparator._status_changed(rms_item, shopify_product):
            changes["changes"].append("status")

        return changes

