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
            "productType": base_item.categoria or "",
            "vendor": base_item.familia or "",
            "category": self._generate_category(base_item),
            "tags": self._generate_tags_list(base_item),
            "description": self._generate_description(base_item),
            "status": "ACTIVE",
            "options": self._generate_options_list(items),
            "variants": [],
            "metafields": self._generate_metafields(base_item),
        }

        # Generar variantes
        for item in items:
            variant = self._map_variant_input(item)
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
        title = re.sub(r"\s+", " ", title)  # Reemplazar múltiples espacios con uno solo
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

        # Agregar timestamp para garantizar unicidad
        timestamp = datetime.now().strftime("%H%M%S")
        handle = f"{handle}-{timestamp}"

        return handle[:100]  # Límite de Shopify

    def _generate_tags_list(self, item: RMSViewItem) -> List[str]:
        """
        Genera tags para el producto en Shopify como lista.

        Args:
            item: Item RMS

        Returns:
            List[str]: Lista de tags
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

        # Tags de producto
        if item.ccod:
            tags.append(f"CCOD-{item.ccod}")

        # Tag de impuesto
        if item.tax and item.tax > 0:
            tags.append("Gravado")
        else:
            tags.append("Exento")

        return tags

    def _generate_tags(self, item: RMSViewItem) -> str:
        """
        Genera tags para el producto en Shopify (versión legacy string).

        Args:
            item: Item RMS

        Returns:
            str: Tags separados por coma
        """
        tags = self._generate_tags_list(item)
        return ", ".join(tags)

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
        Genera descripción simple para Shopify (solo el título, sin HTML).

        Args:
            item: Item RMS

        Returns:
            str: Descripción simple igual al título
        """
        # Solo retornar el título limpio, sin HTML
        if item.description:
            return item.description.strip()
        else:
            return f"Producto {item.ccod}"

    def _generate_options_list(self, items: List[RMSViewItem]) -> List[str]:
        """
        Genera opciones de variante para Shopify como lista de strings.

        Args:
            items: Lista de items del mismo producto

        Returns:
            List[str]: Lista de nombres de opciones
        """
        options = []

        # Obtener valores únicos para cada opción
        colors = list(set(item.color for item in items if item.color))
        sizes = list(set(item.talla for item in items if item.talla))

        # Opción 1: Color (siempre presente)
        if colors or len(items) > 1:
            options.append("Color")

        # Opción 2: Talla (si existe)
        if sizes:
            options.append("Talla")

        return options

    def _generate_options(self, items: List[RMSViewItem]) -> List[Dict[str, Any]]:
        """
        Genera opciones de variante para Shopify (versión legacy dict).

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

    def _map_variant_input(self, item: RMSViewItem, location_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Mapea un item RMS a una variante Shopify GraphQL Input.

        Args:
            item: Item RMS
            location_id: ID de ubicación para inventario (opcional)

        Returns:
            Dict: Variante Shopify GraphQL Input
        """
        # Calcular precios
        price, compare_at_price = self._calculate_prices(item)

        # Generar opciones de variante
        options = []
        if item.color:
            options.append(item.color)
        if item.talla:
            options.append(item.talla)

        variant = {
            "sku": item.c_articulo,
            "price": str(price),
            "compareAtPrice": str(compare_at_price) if compare_at_price else None,
            "options": options,
            "inventoryManagement": "SHOPIFY",  # Enable inventory tracking
            "inventoryPolicy": "DENY",  # Don't allow purchase when out of stock
        }

        # Solo agregar inventoryQuantities si tenemos location_id
        if location_id:
            variant["inventoryQuantities"] = [
                {
                    "availableQuantity": max(0, item.quantity),
                    "locationId": location_id
                }
            ]

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

    def _generate_category(self, item: RMSViewItem) -> Optional[str]:
        """
        Genera categoría de Shopify Standard Product Taxonomy.

        Args:
            item: Item RMS

        Returns:
            str: ID de categoría de Shopify o None
        """
        # Mapeo básico de taxonomías más comunes
        # Idealmente esto debería usar el Enhanced Data Mapper
        taxonomy_map = {
            ("Zapatos", "Tenis"): "gid://shopify/TaxonomyCategory/aa-8-1",  # Athletic Shoes
            ("Zapatos", "Botas"): "gid://shopify/TaxonomyCategory/aa-8-4",  # Boots
            ("Zapatos", "Sandalias"): "gid://shopify/TaxonomyCategory/aa-8-6",  # Sandals
            ("Zapatos", "Flats"): "gid://shopify/TaxonomyCategory/aa-8-9",  # Flats
            ("Zapatos", "Tacones"): "gid://shopify/TaxonomyCategory/aa-8",  # Shoes (general)
            ("Ropa", "MUJER-VEST-CERR-TA16"): "gid://shopify/TaxonomyCategory/aa-1-7",  # Dresses
            ("Accesorios", "Bolsos"): "gid://shopify/TaxonomyCategory/aa-5-4",  # Handbags
        }
        
        if item.familia and item.categoria:
            return taxonomy_map.get((item.familia, item.categoria))
        
        return None

    def _generate_metafields(self, item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera metafields para información adicional de RMS.

        Args:
            item: Item RMS

        Returns:
            List: Metafields de Shopify
        """
        metafields = []

        # Información básica de RMS
        if item.familia:
            metafields.append({
                "namespace": "rms",
                "key": "familia",
                "value": str(item.familia),
                "type": "single_line_text_field"
            })

        if item.categoria:
            metafields.append({
                "namespace": "rms",
                "key": "categoria",
                "value": str(item.categoria),
                "type": "single_line_text_field"
            })

        if item.color:
            metafields.append({
                "namespace": "rms",
                "key": "color",
                "value": str(item.color),
                "type": "single_line_text_field"
            })

        if item.talla:
            metafields.append({
                "namespace": "rms",
                "key": "talla",
                "value": str(item.talla),
                "type": "single_line_text_field"
            })

        if item.ccod:
            metafields.append({
                "namespace": "rms",
                "key": "ccod",
                "value": str(item.ccod),
                "type": "single_line_text_field"
            })

        if item.item_id:
            metafields.append({
                "namespace": "rms",
                "key": "item_id",
                "value": str(item.item_id),
                "type": "number_integer"
            })

        if item.extended_category:
            metafields.append({
                "namespace": "rms",
                "key": "extended_category",
                "value": str(item.extended_category),
                "type": "single_line_text_field"
            })

        # Agregar metafields de categoría basados en el tipo de producto
        category_metafields = self._generate_category_metafields(item)
        metafields.extend(category_metafields)

        # Información de sincronización
        metafields.append({
            "namespace": "sync",
            "key": "last_synced",
            "value": datetime.now(timezone.utc).isoformat(),
            "type": "date_time"
        })

        return metafields

    def _generate_category_metafields(self, item: RMSViewItem) -> List[Dict[str, Any]]:
        """
        Genera metafields específicos de la categoría (Athletic Shoes, etc.).

        Args:
            item: Item RMS

        Returns:
            List: Metafields de categoría
        """
        metafields = []
        
        # Metafields específicos de categoría basados en datos RMS reales
        # APLICAR PARA TODOS LOS TIPOS DE PRODUCTOS, no solo zapatos
        
        # Color - aplicar para cualquier producto que tenga color en RMS
        if item.color:
            metafields.append({
                "namespace": "custom",
                "key": "color",
                "value": str(item.color),
                "type": "single_line_text_field"
            })
        
        # Target gender - aplicar para cualquier producto que tenga género en RMS
        if item.genero:
            metafields.append({
                "namespace": "custom",
                "key": "target_gender",
                "value": str(item.genero),
                "type": "single_line_text_field"
            })
        
        # Age group - determinar para cualquier producto basado en género
        if item.genero:
            if "Niño" in item.genero or "Niña" in item.genero:
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
        if item.talla:
            # Mapear según el tipo de producto
            if item.familia == "Zapatos":
                # Para zapatos usar shoe_size
                metafields.append({
                    "namespace": "custom",
                    "key": "shoe_size",
                    "value": str(item.talla),
                    "type": "single_line_text_field"
                })
            elif item.familia == "Ropa":
                # Para ropa usar clothing_size
                metafields.append({
                    "namespace": "custom",
                    "key": "clothing_size",
                    "value": str(item.talla),
                    "type": "single_line_text_field"
                })
            else:
                # Para otros productos usar size genérico
                metafields.append({
                    "namespace": "custom",
                    "key": "size",
                    "value": str(item.talla),
                    "type": "single_line_text_field"
                })
        
        # Activity - solo para productos deportivos/tenis
        if item.categoria == "Tenis":
            metafields.append({
                "namespace": "custom",
                "key": "activity",
                "value": "Running",
                "type": "single_line_text_field"
            })
        
        # Track quantity - para cualquier producto con inventario
        if item.quantity > 0:
            metafields.append({
                "namespace": "custom",
                "key": "track_quantity",
                "value": "true",
                "type": "boolean"
            })
        
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
