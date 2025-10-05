#!/usr/bin/env python3
"""
Mapeador inteligente de variantes por color y talla.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import (
    ProductStatus,
    ShopifyOption,
    ShopifyProductInput,
    ShopifyVariantInput,
)

logger = logging.getLogger(__name__)


class VariantMapper:
    """
    Mapeador inteligente para crear productos con múltiples variantes basadas en color y talla.
    """

    @staticmethod
    def group_items_by_model(items: List[RMSViewItem]) -> Dict[str, List[RMSViewItem]]:
        """
        Agrupa items RMS por modelo usando CCOD.

        Args:
            items: Lista de items RMS

        Returns:
            Dict: Items agrupados por modelo
        """
        grouped = defaultdict(list)

        for item in items:
            # CCOD siempre viene con valor, usar los primeros 4 caracteres para agrupar
            if item.ccod and item.ccod.strip():
                normalized_ccod = item.ccod.strip().upper()
                ccod_prefix = normalized_ccod
                model_key = f"ccod_{ccod_prefix}".replace(" ", "_").lower()
            else:
                # Esto no debería ocurrir, pero mantener como fallback
                logger.warning(f"Item sin CCOD encontrado: {item.c_articulo} - usando C_ARTICULO como clave")
                model_key = f"fallback_{item.c_articulo}".replace(" ", "_").lower()

            grouped[model_key].append(item)

        # Filtrar grupos que solo tienen un item para evitar variantes innecesarias
        # pero mantener si tienen diferentes colores o tallas
        filtered_groups = {}
        for key, group_items in grouped.items():
            if len(group_items) > 1:
                # Verificar si realmente hay variaciones de color o talla - VALIDAR QUE NO SEA SOLO ESPACIOS
                colors = set(item.color.strip() for item in group_items if item.color and item.color.strip())
                sizes = set(item.talla.strip() for item in group_items if item.talla and item.talla.strip())

                if len(colors) > 1 or len(sizes) > 1:
                    filtered_groups[key] = group_items
                else:
                    # Si no hay variaciones reales, crear productos individuales
                    for i, item in enumerate(group_items):
                        individual_key = f"{key}_individual_{i}"
                        filtered_groups[individual_key] = [item]
            else:
                filtered_groups[key] = group_items

        return filtered_groups

    @staticmethod
    async def _get_existing_product_status(handle: str, shopify_client) -> Optional[ProductStatus]:
        """
        Obtiene el status actual de un producto existente en Shopify.

        Args:
            handle: Handle del producto a buscar
            shopify_client: Cliente de Shopify

        Returns:
            ProductStatus del producto existente o None si no existe
        """
        try:
            existing_product = await shopify_client.get_product_by_handle(handle)
            if existing_product and existing_product.get("status"):
                current_status = existing_product["status"]
                logger.info(f"Producto existente '{handle}' tiene status: {current_status}")
                return ProductStatus(current_status)
            return None
        except Exception as e:
            logger.warning(f"Error al verificar producto existente '{handle}': {e}")
            return None

    @staticmethod
    async def map_product_group_with_variants(
        items: List[RMSViewItem],
        shopify_client,
        location_id: Optional[str] = None,
        preserve_shopify_status: bool = True,
    ) -> ShopifyProductInput:
        """
        Mapea un grupo de items RMS a un producto Shopify con múltiples variantes.

        Args:
            items: Lista de items RMS del mismo modelo
            shopify_client: Cliente de Shopify para resolución de categorías
            location_id: ID de ubicación para inventario
            preserve_shopify_status: Si True, preserva el status existente del producto en Shopify

        Returns:
            ShopifyProductInput: Producto con variantes múltiples
        """
        if not items:
            raise ValueError("No items provided for variant mapping")

        # Usar el primer item como base para el producto
        base_item = items[0]

        # Generar título base del producto (sin color/talla específicos)
        base_title = VariantMapper._generate_base_title(items)

        # Generar handle único basado en CCOD
        from app.utils.shopify_utils import generate_shopify_handle

        handle = generate_shopify_handle(base_item.ccod, base_item.familia)

        # Determinar status del producto
        product_status = ProductStatus.DRAFT  # Default para productos nuevos
        if preserve_shopify_status:
            existing_status = await VariantMapper._get_existing_product_status(handle, shopify_client)
            if existing_status:
                product_status = existing_status
                logger.info(f"🔄 Preservando status existente '{existing_status}' para producto '{handle}'")
            else:
                logger.info(f"🆕 Producto nuevo '{handle}', usando status DRAFT")

        # Generar opciones del producto basadas en variaciones reales
        options = VariantMapper._generate_product_options(items)

        # Crear todas las variantes
        variants = []
        for item in items:
            variant = VariantMapper._map_item_to_variant(item, options, location_id)
            variants.append(variant)

        # NUEVA LÓGICA: Determinar precio del producto basado en el valor más alto del CCOD
        # Esto asegura consistencia sin importar el orden o múltiples sincronizaciones
        VariantMapper._calculate_product_base_price(items)

        # Resolver categoría de taxonomía
        from app.services.data_mapper import RMSToShopifyMapper

        category_id = await RMSToShopifyMapper.resolve_category_id(
            base_item.categoria, shopify_client, base_item.familia
        )

        # Generar metafields usando el item base
        metafields = RMSToShopifyMapper._generate_complete_metafields(base_item)

        # Generar tags
        tags = VariantMapper._generate_tags(base_item)

        return ShopifyProductInput(
            title=base_title,
            handle=handle,
            status=product_status,
            productType=RMSToShopifyMapper._get_product_type(base_item),
            vendor=base_item.familia or "",
            category=category_id,
            tags=tags,
            options=[opt.name for opt in options] if options else None,
            variants=variants,
            description=VariantMapper._generate_description(base_item),
            metafields=metafields,
        )

    @staticmethod
    def _generate_base_title(items: List[RMSViewItem]) -> str:
        """
        Genera título base del producto sin color/talla específicos.
        Usa el guion como separador principal para extraer el título base.
        """
        base_item = items[0]

        # Estrategia principal: Split por guion y tomar primera parte
        if base_item.description:
            description = base_item.description.strip()

            # Split por el primer guion para separar título de talla/color
            if "-" in description:
                # Tomar solo la primera parte antes del guion
                base_title = description.split("-")[0].strip()

                # Validar que el título base sea significativo
                if base_title and len(base_title) >= 3:
                    # Limpiar espacios múltiples
                    base_title = " ".join(base_title.split())

                    # Si el título es válido, usarlo con CCOD
                    if not base_title.replace(" ", "").isdigit():
                        ccod_suffix = base_item.ccod or base_item.c_articulo
                        title_with_code = f"{base_title} - {ccod_suffix}"
                        return title_with_code[:255]

            # Si no hay guion o el split no funcionó, intentar usar descripción completa
            # pero removiendo patrones conocidos de talla/color
            title = description

            # Remover tallas numéricas al final
            import re

            title = re.sub(r"\s+\d+(?:[½¼¾]|\.5)?$", "", title)
            title = re.sub(r"\s+\d+$", "", title)

            # Remover NA, N/A
            title = re.sub(r"\b(NA|N/A)\b", " ", title, flags=re.IGNORECASE)

            # Limpiar espacios
            title = " ".join(title.split())

            # Si después de limpiar tenemos un título válido
            if title and len(title) >= 3 and not title.replace(" ", "").isdigit():
                # Agregar CCOD al título
                ccod_suffix = base_item.ccod or base_item.c_articulo
                title_with_code = f"{title} - {ccod_suffix}"
                return title_with_code[:255]

        # Estrategia fallback: Usar categoría o familia
        if base_item.categoria:
            return base_item.categoria[:255]
        elif base_item.familia:
            return base_item.familia[:255]
        else:
            return "Producto"[:255]

    @staticmethod
    def _generate_product_options(items: List[RMSViewItem]) -> List[ShopifyOption]:
        """
        Genera opciones del producto basadas en las variaciones reales.
        """
        options = []

        # Analizar variaciones de color - VALIDAR QUE NO SEA SOLO ESPACIOS
        colors = sorted(
            set(item.color.strip() for item in items if item.color and item.color.strip())
        )
        if colors and len(colors) > 1:
            options.append(ShopifyOption(name="Color", values=colors))
        elif colors:
            # Solo un color, pero incluirlo como opción
            options.append(ShopifyOption(name="Color", values=colors))

        # Analizar variaciones de talla - VALIDAR QUE NO SEA SOLO ESPACIOS
        sizes = sorted(
            set(item.talla.strip() for item in items if item.talla and item.talla.strip()),
            key=VariantMapper._sort_size_key,
        )
        if sizes and len(sizes) > 1:
            options.append(ShopifyOption(name="Size", values=sizes))
        elif sizes:
            # Solo una talla, pero incluirla como opción
            options.append(ShopifyOption(name="Size", values=sizes))

        # Si no hay opciones, crear una por defecto
        if not options:
            options.append(ShopifyOption(name="Style", values=["Default"]))

        return options

    @staticmethod
    def _sort_size_key(size: str) -> tuple:
        """
        Clave para ordenar tallas correctamente.
        """
        if not size:
            return (0, "")

        # Intentar convertir a número
        try:
            if "." in size:
                return (1, float(size))
            else:
                return (1, int(size))
        except ValueError:
            # Para tallas de texto (S, M, L, XL, etc.)
            size_order = {"XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6}
            return (2, size_order.get(size.upper(), 999), size)

    @staticmethod
    def _map_item_to_variant(
        item: RMSViewItem, product_options: List[ShopifyOption], location_id: Optional[str] = None
    ) -> ShopifyVariantInput:
        """
        Mapea un item RMS individual a una variante de Shopify.

        NUEVA LÓGICA: Siempre toma el precio directamente del item RMS específico,
        asegurando que no sea acumulativo sin importar cuántas veces se ejecute.
        """

        # CORRECCIÓN DE FORMATO RMS: Los precios de RMS a veces vienen mal formateados
        # Ej: 221239000000 debería ser 22,123.90 (dividir por 10,000,000)
        def correct_rms_price(price: Decimal) -> Decimal:
            """Corrige precios mal formateados de RMS."""
            if price > 100000000:  # Si es mayor a 100 millones, probablemente está mal formateado
                corrected = price / Decimal("10000000")
                logger.warning(f"⚠️ Corrigiendo precio RMS mal formateado: ₡{price:,.0f} → ₡{corrected:,.2f}")
                return corrected
            return price

        # Aplicar corrección a los precios
        corrected_price = correct_rms_price(item.price)
        corrected_sale_price = correct_rms_price(item.sale_price) if item.sale_price else None

        # PRECIO DETERMINÍSTICO: Usar precios corregidos
        if item.is_on_sale and corrected_sale_price:
            effective_price = corrected_sale_price
            compare_at_price = str(corrected_price)
        else:
            effective_price = corrected_price
            compare_at_price = None

        # VALIDACIÓN DE PRECIO: Validar después de corrección
        max_reasonable_price = 1000000  # 1 millón de colones
        if effective_price > max_reasonable_price:
            logger.error(
                f"🚨 PRECIO AÚN IRRACIONAL después de corrección para SKU {item.c_articulo}: ₡{effective_price:,.2f}"
            )
            logger.error(f"   Precio original RMS: ₡{item.price:,.0f}")
            logger.error(f"   Precio corregido: ₡{corrected_price:,.2f}")
            # Usar precio mínimo seguro como último recurso
            effective_price = Decimal("1000.00")  # Precio mínimo de emergencia
            logger.warning(f"   🆘 Usando precio de emergencia: ₡{effective_price:,.2f}")

        # Generar opciones de la variante basadas en las opciones del producto
        variant_options = []
        for option in product_options:
            if option.name == "Color":
                # Validar que el color no sea solo espacios
                if item.color and item.color.strip():
                    variant_options.append(item.color.strip())
                else:
                    variant_options.append("Default")
            elif option.name == "Size":
                # Validar que la talla no sea solo espacios
                if item.talla and item.talla.strip():
                    variant_options.append(item.talla.strip())
                else:
                    variant_options.append("Default")
            elif option.name == "Style":
                variant_options.append("Default")
            else:
                variant_options.append("Default")

        # Preparar inventario
        inventory_quantities = None
        if location_id and item.quantity > 0:
            inventory_quantities = [{"availableQuantity": item.quantity, "locationId": location_id}]

        return ShopifyVariantInput(
            sku=item.c_articulo,
            price=str(effective_price),
            compareAtPrice=compare_at_price,
            options=variant_options,
            inventoryQuantities=inventory_quantities,
            inventoryManagement="SHOPIFY",
            inventoryPolicy="DENY",
        )

    @staticmethod
    def _calculate_product_base_price(items: List[RMSViewItem]) -> Decimal:
        """
        Calcula el precio base del producto basado en el valor más alto del CCOD.

        Esta lógica asegura que el precio del producto sea consistente y determinístico,
        sin importar el orden de los items o múltiples ejecuciones.

        Args:
            items: Lista de items RMS del mismo CCOD

        Returns:
            Decimal: Precio más alto encontrado entre todas las variantes
        """
        if not items:
            return Decimal("0.00")

        max_price = Decimal("0.00")

        for item in items:
            # Usar precio efectivo (considerando ofertas)
            item_price = item.effective_price

            # Validar que el precio sea razonable
            max_reasonable_price = Decimal("1000000")  # 1 millón de colones
            if item_price > max_reasonable_price:
                logger.warning(f"⚠️ Precio irracional ignorado para SKU {item.c_articulo}: ₡{item_price:,.2f}")

                # Verificar precio base también
                if item.price > max_reasonable_price:
                    logger.warning(
                        f"   Precio base también irracional: ₡{item.price:,.2f} - IGNORANDO ITEM COMPLETAMENTE"
                    )
                    continue  # Saltar este item completamente
                else:
                    item_price = item.price  # Usar precio base como fallback

            if item_price > max_price:
                max_price = item_price

        return max_price

    @staticmethod
    def _generate_tags(item: RMSViewItem) -> List[str]:
        """
        Genera tags para el producto.
        """
        tags = []

        # CCOD como tag principal (normalizado)
        if item.ccod:
            normalized_ccod = item.ccod.strip().upper()
            tags.append(f"ccod_{normalized_ccod}")

        if item.familia:
            tags.append(item.familia)
        if item.categoria:
            tags.append(item.categoria)
        if item.genero:
            tags.append(item.genero)
        if item.extended_category:
            tags.append(item.extended_category)

        # Tag de promoción
        if item.is_on_sale:
            tags.append("En-Oferta")

        tags.append("RMS-Sync")

        return tags

    @staticmethod
    def _generate_description(item: RMSViewItem) -> str:
        """
        Genera descripción del producto.
        """
        return item.description or f"Producto {item.familia} {item.categoria}"


# Función helper para integración con el sistema existente
async def create_products_with_variants(
    rms_items: List[RMSViewItem],
    shopify_client,
    location_id: Optional[str] = None,
    preserve_shopify_status: bool = True,
) -> List[ShopifyProductInput]:
    """
    Genera productos con variantes inteligentes a partir de items RMS.

    Args:
        rms_items: Lista de items RMS
        shopify_client: Cliente de Shopify
        location_id: ID de ubicación para inventario
        preserve_shopify_status: Si True, preserva el status existente del producto en Shopify

    Returns:
        List: Lista de productos Shopify con variantes
    """
    # Agrupar items por modelo
    grouped_items = VariantMapper.group_items_by_model(rms_items)

    products = []
    for _, items in grouped_items.items():
        # Crear producto con variantes
        product = await VariantMapper.map_product_group_with_variants(
            items, shopify_client, location_id, preserve_shopify_status
        )
        products.append(product)

    return products
