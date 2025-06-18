# app/services/rms_shopify_mapper.py
"""
Servicio de mapeo de datos RMS → Shopify específico para Les Antonio.
Implementa la lógica de transformación basada en la estructura View_Items.
"""

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.core.config import get_settings
from app.utils.error_handler import ValidationException

settings = get_settings()
logger = logging.getLogger(__name__)


class RMSShopifyMapper:
    """
    Mapea datos desde RMS View_Items al formato requerido por Shopify.
    """

    def __init__(self):
        """Inicializa el mapper con configuraciones específicas."""
        self.tax_rate = 13  # Tasa de impuesto base en Costa Rica

    def map_product_group(self, items: List[RMSViewItem]) -> Dict[str, Any]:
        """
        Mapea un grupo de variantes RMS a un producto Shopify.
        Los productos se agrupan por CCOD (modelo + color).

        Args:
            items: Lista de items RMS del mismo grupo (mismo CCOD)

        Returns:
            Dict: Producto Shopify con todas sus variantes

        Raises:
            ValidationException: Si no se puede crear el mapeo
        """
        if not items:
            raise ValidationException(message="No items provided for mapping", field="items", invalid_value=items)

        # Usar el primer item como base para datos del producto
        base_item = items[0]

        # Validar que todos los items tienen el mismo CCOD
        ccod = base_item.ccod
        if not all(item.ccod == ccod for item in items):
            raise ValidationException(
                message="All items must have the same CCOD for grouping", field="ccod", invalid_value=ccod
            )

        # Generar producto base
        shopify_product = {
            "title": self._generate_product_title(base_item),
            "handle": self._generate_handle(base_item),
            "product_type": base_item.categoria or "",
            "vendor": base_item.familia or "",
            "tags": self._generate_tags(base_item),
            "body_html": self._generate_description(base_item),
            "status": "active",
            "published": True,
            "variants": [],
            "options": self._generate_options(items),
            "metafields": self._generate_metafields(base_item),
        }

        # Generar variantes
        for item in items:
            variant = self._map_variant(item)
            shopify_product["variants"].append(variant)

        # Validar producto final
        self._validate_shopify_product(shopify_product)

        return shopify_product

    def map_single_product(self, item: RMSViewItem) -> Dict[str, Any]:
        """
        Mapea un solo item RMS a producto Shopify (sin variantes).

        Args:
            item: Item RMS

        Returns:
            Dict: Producto Shopify
        """
        return self.map_product_group([item])

    def _generate_product_title(self, item: RMSViewItem) -> str:
        """
        Genera el título del producto para Shopify.

        Args:
            item: Item base RMS

        Returns:
            str: Título del producto
        """
        # Usar description como base, limpiando información de talla/color específico
        title = item.description or f"{item.familia} {item.categoria}"

        # Limpiar códigos de talla específicos (ej: "7-09" en "FILA MEDIAS 7-09 NAVY")
        title = re.sub(r"\b\d+-\d+\b", "", title)
        title = re.sub(r"\b\d+\.\d+\b", "", title)  # Para tallas como "6.5"

        # Limpiar colores específicos del título para que sea genérico
        if item.color:
            color_words = item.color.split()
            for word in color_words:
                title = re.sub(r"\b" + re.escape(word) + r"\b", "", title, flags=re.IGNORECASE)

        # Limpiar espacios extra y normalizar
        title = " ".join(title.split())
        title = title.strip()

        # Fallback si el título queda muy corto
        if len(title) < 3:
            title = f"{item.familia} {item.categoria} {item.ccod}"

        return title[:255]  # Límite de Shopify

    def _generate_handle(self, item: RMSViewItem) -> str:
        """
        Genera un handle único para Shopify basado en CCOD.

        Args:
            item: Item RMS

        Returns:
            str: Handle único
        """
        # Usar CCOD como base para handle
        base = item.ccod or item.c_articulo

        # Normalizar handle
        handle = base.lower()
        handle = re.sub(r"[^\w\s-]", "", handle)
        handle = re.sub(r"\s+", "-", handle)
        handle = re.sub(r"-+", "-", handle)
        handle = handle.strip("-")

        # Agregar prefijo de familia para unicidad
        if item.familia:
            family_prefix = item.familia.lower().replace(" ", "-")[:10]
            handle = f"{family_prefix}-{handle}"

        return handle[:100]  # Límite de Shopify

    def _generate_tags(self, item: RMSViewItem) -> str:
        """
        Genera tags para el producto en Shopify.

        Args:
            item: Item RMS

        Returns:
            str: Tags separados por coma
        """
        tags = []

        # Tags de clasificación
        if item.familia:
            tags.append(f"Familia-{item.familia}")

        if item.categoria:
            tags.append(f"Categoría-{item.categoria}")

        if item.genero:
            tags.append(f"Género-{item.genero}")

        # Tags de categorización extendida
        if item.extended_category:
            extended_parts = item.extended_category.split("/")
            for part in extended_parts:
                if part.strip():
                    tags.append(f"Ext-{part.strip()}")

        # Tags de origen y control
        tags.append("RMS-Sync")
        tags.append(f"CCOD-{item.ccod}")

        # Tag de impuesto
        if item.tax and item.tax > 0:
            tags.append("Gravado")

        return ", ".join(tags)

    def _generate_description(self, item: RMSViewItem) -> str:
        """
        Genera descripción HTML para Shopify.

        Args:
            item: Item RMS

        Returns:
            str: Descripción en HTML
        """
        description_parts = []

        if item.description:
            description_parts.append(f"<h3>{item.description}</h3>")

        # Información de clasificación
        info_items = []
        if item.familia:
            info_items.append(f"<strong>Familia:</strong> {item.familia}")
        if item.categoria:
            info_items.append(f"<strong>Categoría:</strong> {item.categoria}")
        if item.genero:
            info_items.append(f"<strong>Género:</strong> {item.genero}")

        if info_items:
            description_parts.append("<ul>")
            for info in info_items:
                description_parts.append(f"<li>{info}</li>")
            description_parts.append("</ul>")

        # Información adicional
        if item.extended_category:
            description_parts.append(f"<p><em>Clasificación: {item.extended_category}</em></p>")

        # Código de modelo
        description_parts.append(f"<p><small>Modelo: {item.ccod}</small></p>")

        return "\n".join(description_parts) if description_parts else ""

    def _generate_options(self, items: List[RMSViewItem]) -> List[Dict[str, Any]]:
        """
        Genera opciones de variante para Shopify.

        Args:
            items: Lista de items del mismo producto

        Returns:
            List: Opciones de variante
        """
        options = []

        # Obtener valores únicos para cada opción
        colors = list(set(item.color for item in items if item.color))
        sizes = list(set(item.talla for item in items if item.talla))

        # Opción 1: Color (siempre presente)
        if colors:
            options.append({"name": "Color", "values": sorted(colors)})
        else:
            options.append({"name": "Color", "values": ["Default"]})

        # Opción 2: Talla (si existe)
        if sizes:
            options.append({"name": "Talla", "values": sorted(sizes, key=self._sort_size_key)})

        return options

    def _sort_size_key(self, size: str) -> tuple:
        """
        Genera clave para ordenar tallas.

        Args:
            size: Talla a ordenar

        Returns:
            tuple: Clave de ordenamiento
        """
        if not size:
            return (0, "")

        # Intentar convertir a número si es posible
        try:
            if "." in size:
                return (1, float(size))
            else:
                return (1, int(size))
        except ValueError:
            # Para tallas de texto (S, M, L, XL)
            size_order = {"XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6}
            return (2, size_order.get(size.upper(), 999), size)

    def _map_variant(self, item: RMSViewItem) -> Dict[str, Any]:
        """
        Mapea un item RMS a una variante Shopify.

        Args:
            item: Item RMS

        Returns:
            Dict: Variante Shopify
        """
        # Calcular precios
        price, compare_at_price = self._calculate_prices(item)

        variant = {
            "sku": item.c_articulo,
            "price": str(price),
            "compare_at_price": str(compare_at_price) if compare_at_price else None,
            "inventory_quantity": max(0, item.quantity),
            "inventory_management": "shopify",
            "inventory_policy": "deny",  # No permitir venta sin stock
            "fulfillment_service": "manual",
            "requires_shipping": True,
            "taxable": bool(item.tax and item.tax > 0),
            "weight": 0,
            "weight_unit": "kg",
            "option1": item.color or "Default",
            "option2": item.talla,
            "option3": None,
            "barcode": item.c_articulo,  # Usar SKU como código de barras
        }

        return variant

    def _calculate_prices(self, item: RMSViewItem) -> Tuple[Decimal, Optional[Decimal]]:
        """
        Calcula precios para Shopify basado en promociones RMS.

        Args:
            item: Item RMS

        Returns:
            Tuple: (precio_actual, precio_comparacion)
        """
        base_price = item.price

        # Verificar si está en promoción activa
        if item.is_on_sale and item.sale_price and item.sale_price < base_price:
            return item.sale_price, base_price

        return base_price, None

    def _generate_metafields(self, item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera metafields para información adicional de RMS.

        Args:
            item: Item RMS

        Returns:
            List: Metafields de Shopify
        """
        metafields = []

        # Información de RMS
        metafields.append({"namespace": "rms", "key": "ccod", "value": item.ccod, "type": "single_line_text_field"})

        metafields.append({"namespace": "rms", "key": "item_id", "value": str(item.item_id), "type": "number_integer"})

        if item.extended_category:
            metafields.append(
                {
                    "namespace": "rms",
                    "key": "extended_category",
                    "value": item.extended_category,
                    "type": "single_line_text_field",
                }
            )

        # Información de sincronización
        metafields.append(
            {
                "namespace": "sync",
                "key": "last_synced",
                "value": datetime.now(timezone.utc).isoformat(),
                "type": "date_time",
            }
        )

        return metafields

    def _validate_shopify_product(self, product: Dict[str, Any]) -> None:
        """
        Valida que el producto mapeado cumpla con requerimientos Shopify.

        Args:
            product: Producto mapeado

        Raises:
            ValidationException: Si la validación falla
        """
        # Validar campos requeridos
        required_fields = ["title", "variants"]
        for field in required_fields:
            if not product.get(field):
                raise ValidationException(
                    message=f"Required field missing: {field}", field=field, invalid_value=product.get(field)
                )

        # Validar título
        title = product["title"]
        if len(title) < 1 or len(title) > 255:
            raise ValidationException(
                message="Product title must be between 1 and 255 characters", field="title", invalid_value=title
            )

        # Validar variantes
        variants = product["variants"]
        if not variants:
            raise ValidationException(
                message="Product must have at least one variant", field="variants", invalid_value=variants
            )

        # Validar SKUs únicos
        skus = [v.get("sku") for v in variants]
        if len(skus) != len(set(skus)):
            raise ValidationException(
                message="All variant SKUs must be unique", field="variants.sku", invalid_value=skus
            )

        # Validar precios
        for i, variant in enumerate(variants):
            price = variant.get("price")
            if not price or float(price) <= 0:
                raise ValidationException(
                    message=f"Variant {i} must have a valid price > 0",
                    field=f"variants[{i}].price",
                    invalid_value=price,
                )


def group_items_by_model(items: List[RMSViewItem]) -> Dict[str, List[RMSViewItem]]:
    """
    Agrupa items RMS por modelo (CCOD) para crear productos con variantes.

    Args:
        items: Lista de items RMS

    Returns:
        Dict: Items agrupados por CCOD
    """
    grouped = {}

    for item in items:
        ccod = item.ccod or item.c_articulo  # Fallback si no hay CCOD

        if ccod not in grouped:
            grouped[ccod] = []

        grouped[ccod].append(item)

    return grouped


def validate_rms_item_for_sync(item: RMSViewItem) -> bool:
    """
    Valida si un item RMS puede sincronizarse a Shopify.

    Args:
        item: Item RMS a validar

    Returns:
        bool: True si puede sincronizarse
    """
    # Validaciones básicas
    if not item.c_articulo or not item.description:
        return False

    if item.price <= 0:
        return False

    # Solo productos con stock o en promoción
    if item.quantity <= 0 and not item.is_on_sale:
        return False

    return True
