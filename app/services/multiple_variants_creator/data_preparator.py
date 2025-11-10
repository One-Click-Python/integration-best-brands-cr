#!/usr/bin/env python3
"""
Preparación y formateo de datos para productos y variantes de Shopify.

Este módulo se encarga específicamente de:
- Preparar datos de productos base
- Preparar datos de variantes para bulk operations
- Detectar tipos de opciones
- Formatear datos según requerimientos de Shopify
"""

import logging
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput

logger = logging.getLogger(__name__)


class DataPreparator:
    """
    Maneja la preparación y formateo de datos para operaciones de Shopify.
    """

    def prepare_base_product_data(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Prepara los datos básicos del producto para creación inicial.

        Args:
            shopify_input: Input del producto

        Returns:
            Dict: Datos del producto base
        """
        # Extract vendor from title if not provided
        vendor = shopify_input.vendor
        if shopify_input.title and "-" in shopify_input.title:
            vendor = shopify_input.title.split("-")[0].strip()
            if vendor:
                logger.info(f"🏷️ Extracted vendor from title: '{vendor}'")

        # Crear producto base con opciones pero sin variantes específicas
        product_data = {
            "title": shopify_input.title,
            "handle": shopify_input.handle,
            "status": shopify_input.status.value if shopify_input.status else "DRAFT",
            "productType": shopify_input.productType or "",
            "vendor": vendor or "",
            "tags": shopify_input.tags or [],
        }

        # Agregar categoría si existe
        if shopify_input.category:
            product_data["category"] = shopify_input.category

        # Agregar descripción si existe
        if shopify_input.description:
            product_data["descriptionHtml"] = shopify_input.description

        # IMPORTANTE: Incluir opciones en la creación inicial para que las variantes las puedan referenciar
        if shopify_input.variants is not None and len(shopify_input.variants) > 0:
            # Detectar dinámicamente las opciones disponibles
            option_sets = {}  # {"Color": set(), "Size": set()}

            for variant in shopify_input.variants:
                if hasattr(variant, "options") and variant.options:
                    # Detectar tipo de cada opción basado en posición
                    for position, option_value in enumerate(variant.options):
                        option_str = str(option_value)
                        option_name = self.detect_option_type(option_str, position)

                        if option_name not in option_sets:
                            option_sets[option_name] = set()
                        option_sets[option_name].add(option_str)

            # Crear productOptions solo si hay opciones detectadas
            if option_sets:
                product_options = []
                for option_name, values in option_sets.items():
                    product_options.append(
                        {"name": option_name, "values": [{"name": value} for value in sorted(list(values))]}
                    )

                product_data["productOptions"] = product_options
                options_summary = {name: sorted(values) for name, values in option_sets.items()}
                logger.info(f"🎨 Including productOptions in product: {options_summary}")

        return product_data

    def prepare_variant_data(self, variant: Any) -> Dict[str, Any]:
        """
        Prepara los datos de una variante para ProductVariantsBulkInput.

        Args:
            variant: Datos de la variante

        Returns:
            Dict: Datos formateados para ProductVariantsBulkInput
        """
        variant_data = {
            "price": str(variant.price),
        }

        # NOTA: ProductVariantsBulkInput NO acepta el campo 'sku'
        # Los SKUs se actualizarán después de crear las variantes

        # Precio de comparación
        if variant.compareAtPrice:
            variant_data["compareAtPrice"] = str(variant.compareAtPrice)

        # Opciones de la variante usando optionValues
        if variant.options:
            option_values = []
            for position, option_value in enumerate(variant.options):
                option_str = str(option_value)
                option_name = self.detect_option_type(option_str, position)
                option_values.append({"optionName": option_name, "name": option_str})
            variant_data["optionValues"] = option_values
            logger.debug(f"🔗 Variant {variant.sku} optionValues: {option_values}")

        # Inventario usando inventoryQuantities
        if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
            variant_data["inventoryQuantities"] = variant.inventoryQuantities

        # NOTA: No se puede establecer inventoryItem.tracked en productVariantsBulkCreate
        # El tracking se debe activar después usando inventoryItemUpdate mutation

        # Política de inventario
        if variant.inventoryPolicy:
            variant_data["inventoryPolicy"] = (
                variant.inventoryPolicy.value if hasattr(variant.inventoryPolicy, "value") else variant.inventoryPolicy
            )
        else:
            # Establecer política por defecto para inventario trackeado
            variant_data["inventoryPolicy"] = "DENY"  # No permitir ventas cuando sin stock

        return variant_data

    def detect_option_type(self, option_value: str, position: int = 0) -> str:
        """
        Detecta el tipo de opción basado en su posición y valor.

        Por convención RMS:
        - Primera opción (posición 0): Color
        - Segunda opción (posición 1): Size/Talla

        Args:
            option_value: Valor de la opción
            position: Posición en el array de opciones (0-based)

        Returns:
            str: "Color" si posición 0, "Size" si posición 1
        """

        logger.debug(f"Detecting option type for value: {option_value} at position {position}")
        # Simple y directo: basado en la posición
        # Esto permite cualquier valor tanto para Color como para Size
        if position == 0:
            return "Color"
        elif position == 1:
            return "Size"
        else:
            # Si hay más de 2 opciones (raro), usar nombres genéricos
            return f"Option{position + 1}"

    def prepare_product_update_data(
        self,
        shopify_input: ShopifyProductInput,
        existing_tags: Optional[List[str]] = None,
        preserve_media: bool = True,
        preserve_publishing: bool = True,
        fields_to_update: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Prepara los datos básicos del producto para actualización selectiva.

        Args:
            shopify_input: Input del producto con nuevos datos
            existing_tags: Tags actuales del producto en Shopify (para limpieza de RMS-Sync)
            preserve_media: Si True, no sobrescribe imágenes/media existentes
            preserve_publishing: Si True, no sobrescribe configuración de publishing
            fields_to_update: Lista específica de campos a actualizar (None = usar defaults seguros)

        Returns:
            Dict: Datos del producto para actualización selectiva
        """
        update_data = {}

        # Campos seguros para actualizar siempre (datos que vienen de RMS)
        # NOTA: productType NO se incluye - se preserva el valor actual de Shopify
        safe_fields = [
            "title",  # Título del producto
            "status",  # Solo si preserve_shopify_status es False
            "vendor",  # Proveedor/marca
            "category",  # Categoría de taxonomía
        ]

        # Si se especifican campos específicos, usar solo esos
        if fields_to_update:
            fields_to_process = fields_to_update
        else:
            # Usar campos seguros por defecto
            fields_to_process = safe_fields

        # Procesar campos seguros
        for field in fields_to_process:
            if field == "title" and shopify_input.title:
                update_data["title"] = shopify_input.title

            elif field == "status" and shopify_input.status:
                update_data["status"] = (
                    shopify_input.status.value if hasattr(shopify_input.status, "value") else shopify_input.status
                )

            elif field == "vendor":
                # Split title by "-" and use first part as vendor if vendor not provided
                if shopify_input.vendor:
                    update_data["vendor"] = shopify_input.vendor
                elif shopify_input.title and "-" in shopify_input.title:
                    # Extract vendor from title (first part before "-")
                    vendor_from_title = shopify_input.title.split("-")[0].strip()
                    if vendor_from_title:
                        update_data["vendor"] = vendor_from_title
                        logger.info(f"🏷️ Extracted vendor from title: '{vendor_from_title}'")
                # If no vendor and no "-" in title, field won't be updated

            elif field == "category" and shopify_input.category:
                update_data["category"] = shopify_input.category

        # TAGS: Siempre actualizar con limpieza automática de RMS-Sync antiguos
        if shopify_input.tags and existing_tags is not None:
            from app.services.data_mapper import RMSToShopifyMapper

            # Encontrar el nuevo tag RMS-Sync en los tags del shopify_input
            new_sync_tag = None
            for tag in shopify_input.tags:
                if tag.startswith("RMS-SYNC-"):
                    new_sync_tag = tag
                    break

            if new_sync_tag:
                # Limpiar tags antiguos y mantener solo el nuevo
                logger.debug(f"🏷️ Tags BEFORE cleanup: {existing_tags}")
                cleaned_tags = RMSToShopifyMapper.clean_rms_sync_tags(existing_tags, new_sync_tag)
                logger.debug(f"🏷️ Tags AFTER cleanup: {cleaned_tags}")

                # Agregar tags no-RMS-Sync de shopify_input (como ccod_)
                for tag in shopify_input.tags:
                    if not tag.startswith("RMS-SYNC-") and tag not in cleaned_tags:
                        cleaned_tags.append(tag)

                update_data["tags"] = cleaned_tags
                logger.info(f"🏷️ Tags actualizados: {len(existing_tags)} → {len(cleaned_tags)} (RMS-Sync limpio)")
            else:
                # Si no hay tag RMS-Sync, usar tags del shopify_input tal cual
                update_data["tags"] = shopify_input.tags
                logger.warning("⚠️ No se encontró tag RMS-SYNC en shopify_input, usando tags tal cual")

        # Campos con lógica especial de preservación
        if "descriptionHtml" in fields_to_process:
            if shopify_input.description and not preserve_media:
                # Solo actualizar descripción si se permite sobrescribir contenido
                update_data["descriptionHtml"] = shopify_input.description

        # Alternativa: usar el método del ShopifyProductInput si no se especifican campos custom
        if not fields_to_update:
            # Check if tags were already cleaned manually
            if "tags" in update_data:
                # Tags were cleaned - preserve them while merging safe fields
                cleaned_tags = update_data["tags"]
                update_data = shopify_input.to_safe_update_input(preserve_media, preserve_publishing)
                update_data["tags"] = cleaned_tags  # ✅ Restore cleaned tags
                logger.info(
                    f"📝 Usando actualización segura con tags limpios: "
                    f"{list(update_data.keys())} | Tags: {len(cleaned_tags)}"
                )
            else:
                # No tag processing happened, use safe defaults
                update_data = shopify_input.to_safe_update_input(preserve_media, preserve_publishing)
                logger.info(f"📝 Usando actualización segura con campos: {list(update_data.keys())}")
        else:
            logger.info(f"📝 Actualizando campos específicos: {list(update_data.keys())}")

        # Log de campos preservados para transparencia
        if preserve_media:
            logger.info("🖼️ Preservando: imágenes, media y contenido personalizado")
        if preserve_publishing:
            logger.info("📢 Preservando: configuración de publishing, tags personalizados")

        return update_data

    def validate_product_data(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Valida los datos del producto antes de enviarlos a Shopify.

        Args:
            shopify_input: Input del producto a validar

        Returns:
            Dict: Resultado de la validación
        """
        try:
            validation_results = {"valid": [], "invalid": [], "warnings": []}

            # Validar título (requerido)
            if not shopify_input.title or not shopify_input.title.strip():
                validation_results["invalid"].append("Product title is required")
            elif len(shopify_input.title) > 255:
                validation_results["invalid"].append("Product title is too long (max 255 characters)")
            else:
                validation_results["valid"].append("Product title is valid")

            # Validar handle (si está presente)
            if shopify_input.handle:
                if len(shopify_input.handle) > 255:
                    validation_results["warnings"].append("Product handle is longer than 255 characters")
                if not shopify_input.handle.replace("-", "").replace("_", "").isalnum():
                    validation_results["warnings"].append("Product handle contains special characters")

            # Validar vendor
            if shopify_input.vendor and len(shopify_input.vendor) > 255:
                validation_results["warnings"].append("Vendor name is longer than 255 characters")

            # Validar productType
            if shopify_input.productType and len(shopify_input.productType) > 255:
                validation_results["warnings"].append("Product type is longer than 255 characters")

            # Validar descripción
            if shopify_input.description and len(shopify_input.description) > 65535:
                validation_results["invalid"].append("Product description is too long (max 65535 characters)")

            # Validar tags
            if shopify_input.tags:
                if len(shopify_input.tags) > 250:
                    validation_results["warnings"].append("Too many tags (recommended max 250)")

                for tag in shopify_input.tags:
                    if len(tag) > 255:
                        validation_results["warnings"].append(f"Tag '{tag}' is longer than 255 characters")

            # Validar variantes
            if shopify_input.variants:
                variant_validation = self.validate_variants_data(shopify_input.variants)
                if not variant_validation["is_valid"]:
                    validation_results["invalid"].extend(variant_validation["results"]["invalid"])
                validation_results["warnings"].extend(variant_validation["results"]["warnings"])
                validation_results["valid"].extend(variant_validation["results"]["valid"])
            else:
                validation_results["warnings"].append("No variants specified")

            logger.info(
                f"📋 Product data validation: {len(validation_results['valid'])} valid, "
                f"{len(validation_results['invalid'])} invalid, {len(validation_results['warnings'])} warnings"
            )

            return {"is_valid": len(validation_results["invalid"]) == 0, "results": validation_results}

        except Exception as e:
            logger.error(f"❌ Error validating product data: {e}")
            return {"is_valid": False, "error": str(e), "results": {"valid": [], "invalid": [], "warnings": []}}

    def validate_variants_data(self, variants: List[Any]) -> Dict[str, Any]:
        """
        Valida los datos de las variantes.

        Args:
            variants: Lista de variantes a validar

        Returns:
            Dict: Resultado de la validación
        """
        try:
            validation_results = {"valid": [], "invalid": [], "warnings": []}

            sku_set = set()

            for i, variant in enumerate(variants):
                variant_name = f"variant[{i}]"

                # Validar SKU (requerido y único)
                if not hasattr(variant, "sku") or not variant.sku:
                    validation_results["invalid"].append(f"{variant_name}: SKU is required")
                    continue

                if variant.sku in sku_set:
                    validation_results["invalid"].append(f"{variant_name}: Duplicate SKU '{variant.sku}'")
                    continue

                sku_set.add(variant.sku)

                # Validar precio (requerido)
                if not hasattr(variant, "price") or variant.price is None:
                    validation_results["invalid"].append(f"{variant_name}: Price is required")
                    continue

                try:
                    price_float = float(variant.price)
                    if price_float < 0:
                        validation_results["invalid"].append(f"{variant_name}: Price cannot be negative")
                        continue
                    if price_float > 1000000:
                        validation_results["warnings"].append(f"{variant_name}: Very high price {price_float}")
                except (ValueError, TypeError):
                    validation_results["invalid"].append(f"{variant_name}: Invalid price format")
                    continue

                # Validar precio de comparación (opcional)
                if hasattr(variant, "compareAtPrice") and variant.compareAtPrice is not None:
                    try:
                        compare_price_float = float(variant.compareAtPrice)
                        if compare_price_float < 0:
                            validation_results["warnings"].append(f"{variant_name}: Compare price cannot be negative")
                        elif compare_price_float <= price_float:
                            validation_results["warnings"].append(
                                f"{variant_name}: Compare price should be higher than regular price"
                            )
                    except (ValueError, TypeError):
                        validation_results["warnings"].append(f"{variant_name}: Invalid compare price format")

                # Validar opciones
                if hasattr(variant, "options") and variant.options:
                    if len(variant.options) > 3:
                        validation_results["warnings"].append(
                            f"{variant_name}: Too many options (Shopify supports max 3)"
                        )

                    for j, option in enumerate(variant.options):
                        if not option or str(option).strip() == "":
                            validation_results["warnings"].append(f"{variant_name}: Option {j + 1} is empty")

                validation_results["valid"].append(f"{variant_name}: Valid variant data")

            return {"is_valid": len(validation_results["invalid"]) == 0, "results": validation_results}

        except Exception as e:
            logger.error(f"❌ Error validating variants data: {e}")
            return {"is_valid": False, "error": str(e), "results": {"valid": [], "invalid": [], "warnings": []}}
