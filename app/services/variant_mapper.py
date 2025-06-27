#!/usr/bin/env python3
"""
Mapeador inteligente de variantes por color y talla.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from collections import defaultdict

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
        Agrupa items RMS por modelo usando CCOD como clave principal.
        
        Args:
            items: Lista de items RMS
            
        Returns:
            Dict: Items agrupados por modelo
        """
        grouped = defaultdict(list)
        
        for item in items:
            # Priorizar CCOD si existe (más confiable para agrupar variantes)
            if item.ccod and item.ccod.strip():
                # Usar solo CCOD como clave, aplicando strip() para eliminar espacios
                model_key = f"ccod_{item.ccod.strip()}".replace(" ", "_").lower()
            else:
                # Usar descripción base sin talla/color específicos
                base_description = item.description or ""
                
                # Limpiar descripción de manera más agresiva
                clean_description = base_description
                
                # Remover números (tallas) al final
                import re
                clean_description = re.sub(r'\s+\d+(\.\d+)?$', '', clean_description)
                clean_description = re.sub(r'\s+\d+$', '', clean_description)
                
                # Remover colores conocidos
                common_colors = ['Negro', 'Blanco', 'Rojo', 'Azul', 'Verde', 'Amarillo', 
                               'Rosa', 'Morado', 'Gris', 'Naranja', 'Black', 'White', 
                               'Red', 'Blue', 'Green', 'Yellow', 'Pink', 'Purple', 'Gray', 'Orange']
                
                for color in common_colors:
                    clean_description = re.sub(rf'\b{color}\b', '', clean_description, flags=re.IGNORECASE)
                
                # Remover el color específico del item
                if item.color:
                    for color_word in item.color.split():
                        clean_description = re.sub(rf'\b{color_word}\b', '', clean_description, flags=re.IGNORECASE)
                
                # Remover la talla específica del item
                if item.talla:
                    clean_description = re.sub(rf'\b{item.talla}\b', '', clean_description)
                
                # Limpiar espacios múltiples y normalizar
                clean_description = re.sub(r'\s+', ' ', clean_description).strip()
                
                # Crear clave usando descripción limpia + familia + categoría
                model_key = f"{clean_description}_{item.familia}_{item.categoria}".replace(" ", "_").lower()
            
            grouped[model_key].append(item)
        
        # Filtrar grupos que solo tienen un item para evitar variantes innecesarias
        # pero mantener si tienen diferentes colores o tallas
        filtered_groups = {}
        for key, group_items in grouped.items():
            if len(group_items) > 1:
                # Verificar si realmente hay variaciones de color o talla
                colors = set(item.color for item in group_items if item.color)
                sizes = set(item.talla for item in group_items if item.talla)
                
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
    async def map_product_group_with_variants(
        items: List[RMSViewItem], 
        shopify_client, 
        location_id: Optional[str] = None
    ) -> ShopifyProductInput:
        """
        Mapea un grupo de items RMS a un producto Shopify con múltiples variantes.
        
        Args:
            items: Lista de items RMS del mismo modelo
            shopify_client: Cliente de Shopify para resolución de categorías
            location_id: ID de ubicación para inventario
            
        Returns:
            ShopifyProductInput: Producto con variantes múltiples
        """
        if not items:
            raise ValueError("No items provided for variant mapping")
        
        # Usar el primer item como base para el producto
        base_item = items[0]
        
        # Generar título base del producto (sin color/talla específicos)
        base_title = VariantMapper._generate_base_title(items)
        
        # Generar handle único
        handle = VariantMapper._generate_handle(base_title, base_item.c_articulo)
        
        # Generar opciones del producto basadas en variaciones reales
        options = VariantMapper._generate_product_options(items)
        
        # Crear todas las variantes
        variants = []
        for item in items:
            variant = VariantMapper._map_item_to_variant(item, options, location_id)
            variants.append(variant)
        
        # NUEVA LÓGICA: Determinar precio del producto basado en el valor más alto del CCOD
        # Esto asegura consistencia sin importar el orden o múltiples sincronizaciones
        highest_price = VariantMapper._calculate_product_base_price(items)
        
        # Resolver categoría de taxonomía
        from app.services.data_mapper import RMSToShopifyMapper
        category_id = await RMSToShopifyMapper.resolve_category_id(base_item.categoria, shopify_client)
        
        # Generar metafields usando el item base
        metafields = RMSToShopifyMapper._generate_complete_metafields(base_item)
        
        # Generar tags
        tags = VariantMapper._generate_tags(base_item)
        
        # Log del precio más alto para referencia
        logger.info(f"🎯 Producto {base_item.ccod}: Precio más alto entre variantes = ₡{highest_price:,.2f}")
        
        return ShopifyProductInput(
            title=base_title,
            handle=handle,
            status=ProductStatus.DRAFT,
            productType=base_item.categoria or "",
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
        """
        base_item = items[0]
        
        # Estrategia 1: Intentar limpiar la descripción
        if base_item.description:
            title = base_item.description.strip()
            
            # Remover patrones comunes de talla y color más agresivamente
            import re
            
            # Remover tallas numéricas: -5-, -5½-, -12-, etc.
            title = re.sub(r'-\s*\d+(?:[½¼¾]|\.5)?\s*-', ' ', title)
            
            # Remover colores específicos
            colors = set(item.color for item in items if item.color)
            for color in colors:
                if color:
                    # Remover color completo
                    title = title.replace(color, " ").strip()
                    # Remover partes del color
                    for color_part in color.split():
                        if len(color_part) > 2:
                            title = title.replace(color_part, " ").strip()
            
            # Remover patrones comunes problemáticos
            title = re.sub(r'\b(NA|N/A)\b', ' ', title, flags=re.IGNORECASE)  # NA, N/A
            title = re.sub(r'-+', ' ', title)   # Guiones múltiples
            title = re.sub(r'\s+', ' ', title)  # Espacios múltiples
            title = title.strip()
            
            # Extraer solo la marca/nombre principal (primera palabra significativa)
            words = [w for w in title.split() if len(w) > 2 and not w.isdigit()]
            if words:
                title = words[0]  # Tomar solo la primera palabra significativa
            
            # Si el título limpio es válido, usarlo
            if len(title) >= 3 and not title.replace('-', '').replace(' ', '').isdigit():
                return title
        
        # Estrategia 2: Usar Familia como base (más confiable)
        title = base_item.familia or "Producto"
        
        # Si familia es genérica, agregar categoría
        generic_families = ['Zapatos', 'Ropa', 'Accesorios']
        if title in generic_families and base_item.categoria:
            title = f"{base_item.categoria}"
        
        return title[:255]  # Límite de Shopify

    @staticmethod
    def _generate_handle(title: str, base_sku: str) -> str:
        """
        Genera handle único para el producto.
        """
        import re
        
        # Limpiar título
        handle = title.lower().strip()
        handle = re.sub(r"[^\w\s-]", "", handle)
        handle = re.sub(r"\s+", "-", handle)
        handle = re.sub(r"-+", "-", handle)
        handle = handle.strip("-")
        
        # Si está vacío, usar SKU
        if not handle:
            handle = "producto"
        
        # Agregar timestamp para unicidad
        import time
        timestamp = str(int(time.time()))[-4:]
        handle = f"{handle}-{timestamp}"
        
        return handle[:100]

    @staticmethod
    def _generate_product_options(items: List[RMSViewItem]) -> List[ShopifyOption]:
        """
        Genera opciones del producto basadas en las variaciones reales.
        """
        options = []
        
        # Analizar variaciones de color
        colors = sorted(set(item.color for item in items if item.color))
        if colors and len(colors) > 1:
            options.append(ShopifyOption(name="Color", values=colors))
        elif colors:
            # Solo un color, pero incluirlo como opción
            options.append(ShopifyOption(name="Color", values=colors))
        
        # Analizar variaciones de talla (aplicar strip() para eliminar espacios)
        sizes = sorted(set(item.talla.strip() for item in items if item.talla), key=VariantMapper._sort_size_key)
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
        item: RMSViewItem, 
        product_options: List[ShopifyOption], 
        location_id: Optional[str] = None
    ) -> ShopifyVariantInput:
        """
        Mapea un item RMS individual a una variante de Shopify.
        
        NUEVA LÓGICA: Siempre toma el precio directamente del item RMS específico,
        asegurando que no sea acumulativo sin importar cuántas veces se ejecute.
        """
        # PRECIO DETERMINÍSTICO: Siempre calculado directamente del item RMS
        # Sin dependencia de valores previos o estados externos
        effective_price = item.effective_price
        compare_at_price = None
        if item.is_on_sale and item.sale_price:
            compare_at_price = str(item.price)
        
        # VALIDACIÓN DE PRECIO: Rechazar precios irracionales
        max_reasonable_price = 1000000  # 1 millón de colones
        if effective_price > max_reasonable_price:
            logger.error(f"🚨 PRECIO IRRACIONAL DETECTADO para SKU {item.c_articulo}: ₡{effective_price:,.2f}")
            
            # Verificar si el precio base también es irracional
            if item.price > max_reasonable_price:
                logger.error(f"🚨 PRECIO BASE TAMBIÉN ES IRRACIONAL: ₡{item.price:,.2f}")
                logger.error(f"   🛑 RECHAZANDO ESTA VARIANTE COMPLETAMENTE")
                # Usar un precio mínimo seguro como último recurso
                effective_price = Decimal("1000.00")  # Precio mínimo de emergencia
                logger.warning(f"   🆘 Usando precio de emergencia: ₡{effective_price:,.2f}")
            else:
                logger.warning(f"   ✅ Usando precio base válido: ₡{item.price:,.2f}")
                effective_price = item.price  # Usar precio base como fallback
        
        # Generar opciones de la variante basadas en las opciones del producto
        variant_options = []
        for option in product_options:
            if option.name == "Color":
                variant_options.append(item.color or "Default")
            elif option.name == "Size":
                variant_options.append(item.talla.strip() if item.talla else "Default")
            elif option.name == "Style":
                variant_options.append("Default")
            else:
                variant_options.append("Default")
        
        # Preparar inventario
        inventory_quantities = None
        if location_id and item.quantity > 0:
            inventory_quantities = [{
                "availableQuantity": item.quantity,
                "locationId": location_id
            }]
        
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
        max_price_item = None
        
        for item in items:
            # Usar precio efectivo (considerando ofertas)
            item_price = item.effective_price
            
            # Validar que el precio sea razonable
            max_reasonable_price = Decimal("1000000")  # 1 millón de colones
            if item_price > max_reasonable_price:
                logger.warning(f"⚠️ Precio irracional ignorado para SKU {item.c_articulo}: ₡{item_price:,.2f}")
                
                # Verificar precio base también
                if item.price > max_reasonable_price:
                    logger.warning(f"   Precio base también irracional: ₡{item.price:,.2f} - IGNORANDO ITEM COMPLETAMENTE")
                    continue  # Saltar este item completamente
                else:
                    item_price = item.price  # Usar precio base como fallback
            
            if item_price > max_price:
                max_price = item_price
                max_price_item = item
        
        if max_price_item:
            logger.info(f"💰 Precio base del producto: ₡{max_price:,.2f} (basado en SKU {max_price_item.c_articulo})")
        
        return max_price

    @staticmethod
    def _generate_tags(item: RMSViewItem) -> List[str]:
        """
        Genera tags para el producto.
        """
        tags = []
        
        # CCOD como tag principal
        if item.ccod:
            tags.append(f"ccod_{item.ccod}")
        
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
    location_id: Optional[str] = None
) -> List[ShopifyProductInput]:
    """
    Crea productos con variantes inteligentes a partir de items RMS.
    
    Args:
        rms_items: Lista de items RMS
        shopify_client: Cliente de Shopify
        location_id: ID de ubicación para inventario
        
    Returns:
        List: Lista de productos Shopify con variantes
    """
    # Agrupar items por modelo
    grouped_items = VariantMapper.group_items_by_model(rms_items)
    
    products = []
    for model_key, items in grouped_items.items():
        logger.info(f"Creating product for model '{model_key}' with {len(items)} variants")
        
        # Crear producto con variantes
        product = await VariantMapper.map_product_group_with_variants(
            items, shopify_client, location_id
        )
        products.append(product)
    
    return products