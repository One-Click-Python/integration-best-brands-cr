#!/usr/bin/env python3
"""
Creador de productos con múltiples variantes para Shopify.
"""

import logging
from typing import Any, Dict, List

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput

logger = logging.getLogger(__name__)


class MultipleVariantsCreator:
    """
    Clase especializada para crear productos con múltiples variantes en Shopify.
    """

    def __init__(self, shopify_client, primary_location_id: str):
        """
        Inicializa el creador de variantes múltiples.

        Args:
            shopify_client: Cliente de Shopify GraphQL
            primary_location_id: ID de la ubicación principal
        """
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id

    async def create_product_with_variants(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Crea un producto en Shopify con múltiples variantes de manera optimizada.

        Args:
            shopify_input: Input del producto con todas las variantes

        Returns:
            Dict: Producto creado con todas las variantes

        Raises:
            Exception: Si falla la creación del producto o variantes
        """
        try:
            # Paso 1: Crear producto básico sin variantes específicas
            product_data = self._prepare_base_product_data(shopify_input)
            created_product = await self.shopify_client.create_product(product_data)

            if not created_product or not created_product.get("id"):
                raise Exception("Product creation failed - no product ID returned")

            product_id = created_product["id"]
            logger.info(f"📦 Created base product: {product_id} - {created_product.get('title')}")

            # Paso 2: Crear todas las variantes usando productVariantsBulkCreate
            if shopify_input.variants and len(shopify_input.variants) > 1:
                # Primero obtener las variantes existentes para evitar conflictos
                existing_variants = await self._get_existing_variants(product_id)
                await self._create_multiple_variants(product_id, shopify_input.variants, existing_variants)
            elif shopify_input.variants and len(shopify_input.variants) == 1:
                await self._update_default_variant(product_id, shopify_input.variants[0])

            # Paso 3: Crear metafields
            if shopify_input.metafields:
                await self._create_metafields(product_id, shopify_input.metafields)

            # Paso 4: Activar inventory tracking para todas las variantes
            await self._activate_inventory_for_all_variants(product_id, shopify_input.variants)

            logger.info(f"✅ Successfully created product with {len(shopify_input.variants)} variants")
            return created_product

        except Exception as e:
            logger.error(f"❌ Error creating product with multiple variants: {e}")
            raise

    def _prepare_base_product_data(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Prepara los datos básicos del producto para creación inicial.

        Args:
            shopify_input: Input del producto

        Returns:
            Dict: Datos del producto base
        """
        # Crear producto base con opciones pero sin variantes específicas
        product_data = {
            "title": shopify_input.title,
            "handle": shopify_input.handle,
            "status": shopify_input.status.value if shopify_input.status else "DRAFT",
            "productType": shopify_input.productType or "",
            "vendor": shopify_input.vendor or "",
            "tags": shopify_input.tags or [],
        }

        # Agregar categoría si existe
        if shopify_input.category:
            product_data["category"] = shopify_input.category

        # Agregar descripción si existe
        if shopify_input.description:
            product_data["descriptionHtml"] = shopify_input.description

        # IMPORTANTE: Incluir opciones en la creación inicial para que las variantes las puedan referenciar
        if len(shopify_input.variants) > 1 and shopify_input.variants is not None:
            # Extraer todas las opciones únicas de las variantes
            colors = set()
            sizes = set()

            for variant in shopify_input.variants:
                if hasattr(variant, "options") and variant.options and len(variant.options) >= 2:
                    colors.add(str(variant.options[0]))
                    sizes.add(str(variant.options[1]))

            if colors and sizes:
                product_data["productOptions"] = [
                    {"name": "Color", "values": [{"name": color} for color in sorted(list(colors))]},
                    {"name": "Size", "values": [{"name": size} for size in sorted(list(sizes))]},
                ]
                logger.info(f"🎨 Including productOptions in product: Colors={sorted(colors)}, Sizes={sorted(sizes)}")

        return product_data

    async def _get_existing_variants(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene las variantes existentes de un producto.

        Args:
            product_id: ID del producto

        Returns:
            List: Lista de variantes existentes
        """
        try:
            query = """
            query GetProductVariants($id: ID!) {
              product(id: $id) {
                variants(first: 50) {
                  edges {
                    node {
                      id
                      sku
                      selectedOptions {
                        name
                        value
                      }
                    }
                  }
                }
              }
            }
            """

            result = await self.shopify_client._execute_query(query, {"id": product_id})

            if result and result.get("product"):
                variants = result["product"].get("variants", {}).get("edges", [])
                existing_variants = [variant["node"] for variant in variants]
                logger.info(f"🔍 Found {len(existing_variants)} existing variants in product")
                return existing_variants

            return []

        except Exception as e:
            logger.warning(f"❌ Error getting existing variants: {e}")
            return []

    async def _create_multiple_variants(
        self, product_id: str, variants: List[Any], existing_variants: List[Dict[str, Any]] = None
    ) -> None:
        """
        Crea múltiples variantes usando productVariantsBulkCreate.

        Args:
            product_id: ID del producto
            variants: Lista de variantes a crear
        """
        try:
            existing_variants = existing_variants or []

            # Determinar qué variantes necesitamos crear (evitar duplicados)
            variants_to_create = []
            variants_to_update = []
            variant_options = ""

            for variant in variants:
                # Verificar si esta variante ya existe
                existing_match = None
                if hasattr(variant, "options") and variant.options:
                    # Crear combinación de opciones flexible (puede ser 1 o 2 opciones)
                    variant_options = "-".join(variant.options)

                    for existing in existing_variants:
                        existing_options = existing.get("selectedOptions", [])
                        if len(existing_options) == len(variant.options):
                            existing_combo = "-".join([opt["value"] for opt in existing_options])
                            if variant_options == existing_combo:
                                existing_match = existing
                                break

                if existing_match:
                    # Variante existe - marcar para actualización
                    variants_to_update.append((existing_match, variant))
                    logger.info(f"🔄 Will update existing variant: {variant_options}")
                else:
                    # Variante nueva - marcar para creación
                    variants_to_create.append(variant)
                    logger.info(f"🆕 Will create new variant: {variant_options}")

            # Preparar datos de variantes para bulk creation (solo las nuevas)
            variants_data = []
            for variant in variants_to_create:
                variant_data = self._prepare_variant_data(variant)
                variants_data.append(variant_data)

            # Crear variantes nuevas si las hay
            if variants_data:
                logger.info(f"🚀 Creating {len(variants_data)} new variants using bulk creation...")
                bulk_result = await self.shopify_client.create_variants_bulk(product_id, variants_data)

                if bulk_result and bulk_result.get("productVariants"):
                    created_variants = bulk_result["productVariants"]
                    logger.info(f"✅ Successfully created {len(created_variants)} new variants")

                    # Actualizar SKUs después de la creación (ya que ProductVariantsBulkInput no acepta SKU)
                    await self._update_variant_skus(created_variants, variants_to_create, product_id)

                    # Log de cada variante creada
                    for variant in created_variants:
                        options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                        logger.info(
                            f"   ✅ New variant: {variant.get('sku', 'NO-SKU')} - {options_str} - ${variant['price']}"
                        )
                else:
                    logger.warning("❌ No variants returned from bulk creation")
            else:
                logger.info("ℹ️  No new variants to create")

            # Actualizar variantes existentes si las hay
            if variants_to_update:
                logger.info(f"🔄 Updating {len(variants_to_update)} existing variants...")
                await self._update_existing_variants(variants_to_update)

        except Exception as e:
            logger.error(f"❌ Error creating multiple variants: {e}")
            raise

    async def _update_existing_variants(self, variants_to_update: List[tuple]) -> None:
        """
        Actualiza variantes existentes.

        Args:
            variants_to_update: Lista de tuplas (existing_variant, new_variant_data)
        """
        try:
            update_data = []
            for existing_variant, new_variant in variants_to_update:
                # VALIDACIÓN CRÍTICA: Verificar si la variante existente ya tiene precio extremo
                existing_price_str = existing_variant.get("price", "0")
                try:
                    existing_price_float = float(existing_price_str)
                    if existing_price_float > 1000000:
                        logger.error("🚨 VARIANTE YA CORRUPTA - NO ACTUALIZAR:")
                        logger.error(f"   SKU: {new_variant.sku}")
                        logger.error(f"   Precio actual en Shopify: ₡{existing_price_float:,.2f}")
                        logger.error(f"   Precio correcto a aplicar: ₡{float(new_variant.price):,.2f}")
                        logger.error("   ⏸️ SALTANDO actualización para evitar tocar variantes ya corruptas")
                        logger.warning(f"   💡 RECOMENDACIÓN: Eliminar y recrear variante {new_variant.sku}")
                        continue
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ No se pudo verificar precio existente para {new_variant.sku}")

                # VALIDACIÓN DE PRECIO: Asegurar que el precio sea razonable
                new_price_float = float(new_variant.price)
                max_reasonable_price = 1000000.0  # 1 millón de colones

                if new_price_float > max_reasonable_price:
                    logger.error("🚨 PRECIO IRRACIONAL DETECTADO en actualización:")
                    logger.error(f"   SKU: {new_variant.sku}")
                    logger.error(f"   Precio nuevo: ₡{new_price_float:,.2f}")
                    logger.error(f"   Precio existente: ₡{existing_variant.get('price', 'unknown')}")
                    logger.error("   ⏸️ SALTANDO esta actualización para prevenir corrupción de datos")
                    continue

                # DEBUGGING: Log de datos antes de preparar actualización
                logger.info(f"🔍 DEBUG VARIANT PREP - SKU: {new_variant.sku}")
                logger.info(
                    f"🔍 DEBUG VARIANT PREP - Original price object: {new_variant.price} \
                        (type: {type(new_variant.price)})"
                )
                logger.info(f"🔍 DEBUG VARIANT PREP - Price as float: {new_price_float}")
                logger.info(f"🔍 DEBUG VARIANT PREP - Existing variant price: {existing_variant.get('price', 'N/A')}")

                # VALIDACIÓN ADICIONAL: Asegurar formato correcto del precio
                price_str = str(new_variant.price)

                # Verificar que no tenga caracteres extraños o formato incorrecto
                if not price_str.replace(".", "").replace("-", "").isdigit():
                    logger.error(f"🚨 PRECIO CON FORMATO INVÁLIDO: '{price_str}'")
                    logger.error(f"   SKU: {new_variant.sku}")
                    logger.error("   ⏸️ SALTANDO actualización con formato inválido")
                    continue

                variant_update = {
                    "id": existing_variant["id"],
                    "price": price_str,  # Usar string limpio
                }

                # Solo incluir SKU si es diferente
                if new_variant.sku and new_variant.sku != existing_variant.get("sku"):
                    variant_update["sku"] = new_variant.sku

                # Precio de comparación (también validarlo)
                if new_variant.compareAtPrice:
                    compare_price_float = float(new_variant.compareAtPrice)
                    if compare_price_float <= max_reasonable_price:
                        compare_price_str = str(new_variant.compareAtPrice)
                        # Validar formato también
                        if compare_price_str.replace(".", "").replace("-", "").isdigit():
                            variant_update["compareAtPrice"] = compare_price_str
                        else:
                            logger.warning(
                                f"⚠️ Precio de comparación con formato inválido ignorado: '{compare_price_str}'"
                            )
                    else:
                        logger.warning(f"⚠️ Precio de comparación irracional ignorado: ₡{compare_price_float:,.2f}")

                # Log de la actualización válida con datos detallados
                logger.info(f"📝 Preparando actualización válida para {new_variant.sku}:")
                logger.info(f"   💰 Precio: ₡{new_price_float:,.2f} (string: '{price_str}')")
                logger.info(f"   🆔 Variant ID: {existing_variant['id']}")
                logger.info(f"   📦 Update data: {variant_update}")

                update_data.append(variant_update)

            if update_data:
                # Usar productVariantsBulkUpdate para todas las actualizaciones
                # Solo necesitamos el product_id del contexto de esta función
                # Los update_data ya contienen los IDs de variantes
                logger.info(f"🔄 Using bulk update for {len(update_data)} variants")

                # Como no tenemos product_id aquí, vamos a actualizar una por una usando la API correcta
                for variant_update in update_data:
                    await self._update_single_variant(variant_update)

                logger.info(f"✅ Updated {len(update_data)} existing variants")

        except Exception as e:
            logger.warning(f"❌ Error updating existing variants: {e}")

    async def _update_single_variant(self, variant_data: Dict[str, Any]) -> None:
        """
        Actualiza una sola variante usando REST API (más confiable para API 2025-04).

        Args:
            variant_data: Datos de la variante a actualizar
        """
        try:
            # Usar REST API para actualizar la variante (más confiable)
            variant_id = variant_data["id"].split("/")[-1]  # Extract numeric ID

            update_payload = {}
            if "price" in variant_data:
                update_payload["price"] = variant_data["price"]
            if "sku" in variant_data:
                update_payload["sku"] = variant_data["sku"]
            if "compareAtPrice" in variant_data:
                update_payload["compare_at_price"] = variant_data["compareAtPrice"]

            if update_payload:
                await self._update_variant_via_rest(variant_id, update_payload)
                logger.info(f"   ✅ Updated variant via REST: {variant_data.get('sku')} - ${variant_data.get('price')}")
            else:
                logger.warning(f"   ⚠️ No fields to update for variant {variant_data.get('id')}")

        except Exception as e:
            logger.warning(f"❌ Error updating single variant: {e}")

    async def _update_variant_via_rest(self, variant_id: str, update_data: Dict[str, Any]) -> None:
        """
        Actualiza una variante usando la REST API de Shopify.

        Args:
            variant_id: ID numérico de la variante
            update_data: Datos a actualizar
        """
        try:
            # DEBUGGING: Log detallado de lo que vamos a enviar
            logger.info(f"🔍 DEBUG REST UPDATE - Variant ID: {variant_id}")
            logger.info(f"🔍 DEBUG REST UPDATE - Input data: {update_data}")

            # VALIDACIÓN CRÍTICA: Verificar precio antes de enviar
            if "price" in update_data:
                price_to_send = update_data["price"]

                # DEBUGGING CRÍTICO: Log extra para variante problemática
                if variant_id == "45313831174204":  # ID de la variante 24YM05051
                    logger.error("🚨 REST UPDATE - VARIANTE PROBLEMÁTICA 24YM05051!")
                    logger.error(f"   Variant ID: {variant_id}")
                    logger.error(f"   Price input RAW: {repr(price_to_send)}")
                    logger.error(f"   Price input type: {type(price_to_send)}")
                    logger.error(f"   Full update_data: {update_data}")

                try:
                    price_float = float(price_to_send)
                    if price_float > 1000000:  # 1 millón de colones
                        logger.error("🚨 PRECIO EXTREMO DETECTADO ANTES DE ENVIAR A REST API!")
                        logger.error(f"   Variant ID: {variant_id}")
                        logger.error(f"   Precio a enviar: ₡{price_float:,.2f}")
                        logger.error("   🛑 ABORTANDO actualización REST para prevenir corrupción")
                        return None
                    else:
                        logger.info(f"✅ Precio válido a enviar: ₡{price_float:,.2f}")

                        # SOLUCIÓN CRÍTICA: Formato específico para Shopify REST API
                        # Shopify espera precios en formato string con máximo 2 decimales
                        # y usando punto como separador decimal (no coma)
                        formatted_price = f"{price_float:.2f}"
                        logger.info(f"🔧 Precio formateado para Shopify: '{formatted_price}'")
                        update_data["price"] = formatted_price

                except ValueError:
                    logger.error(f"🚨 Precio no es un número válido: {price_to_send}")
                    return None

            # SOLUCIÓN ADICIONAL: Formatear compare_at_price también
            if "compare_at_price" in update_data:
                try:
                    compare_price_float = float(update_data["compare_at_price"])
                    if compare_price_float <= 1000000:  # Solo si es válido
                        formatted_compare_price = f"{compare_price_float:.2f}"
                        logger.info(f"🔧 Compare price formateado: '{formatted_compare_price}'")
                        update_data["compare_at_price"] = formatted_compare_price
                    else:
                        # Remover precio de comparación inválido
                        del update_data["compare_at_price"]
                        logger.warning(f"⚠️ Removido compare_at_price inválido: {compare_price_float}")
                except (ValueError, TypeError):
                    # Remover precio de comparación malformado
                    del update_data["compare_at_price"]
                    logger.warning("⚠️ Removido compare_at_price malformado")

            # Usar el HTTP client del shopify_client para REST API
            shop_domain = self.shopify_client.shop_url.replace("https://", "").replace(".myshopify.com", "")
            rest_url = f"https://{shop_domain}.myshopify.com/admin/api/2025-04/variants/{variant_id}.json"

            headers = {"X-Shopify-Access-Token": self.shopify_client.access_token, "Content-Type": "application/json"}

            data = {"variant": {"id": int(variant_id), **update_data}}

            # DEBUGGING: Log del payload exacto con formato corregido
            logger.info(f"🔍 DEBUG REST UPDATE - URL: {rest_url}")
            logger.info(f"🔍 DEBUG REST UPDATE - Formatted payload: {data}")

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.put(rest_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        variant_result = result.get("variant")

                        # VERIFICACIÓN POST-UPDATE: Confirmar que Shopify recibió el precio correcto
                        if variant_result and "price" in variant_result:
                            returned_price = float(variant_result["price"])
                            sent_price = float(update_data.get("price", 0))

                            logger.info(f"📤 Precio enviado: ₡{sent_price:,.2f}")
                            logger.info(f"📥 Precio confirmado por Shopify: ₡{returned_price:,.2f}")

                            if abs(returned_price - sent_price) > 0.01:  # Diferencia mayor a 1 centavo
                                logger.error("🚨 DISCREPANCIA DE PRECIO DETECTADA!")
                                logger.error(f"   Enviado: ₡{sent_price:,.2f}")
                                logger.error(f"   Recibido: ₡{returned_price:,.2f}")
                                logger.error(f"   Diferencia: ₡{returned_price - sent_price:,.2f}")

                                # Si el precio devuelto es extremo, loguearlo como error crítico
                                if returned_price > 1000000:
                                    logger.error("🚨 SHOPIFY DEVOLVIÓ PRECIO EXTREMO - PROBLEMA DE FORMATO!")
                            else:
                                logger.info("✅ Precio confirmado correctamente por Shopify")

                        return variant_result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ REST API error {response.status}: {error_text}")
                        raise Exception(f"REST API error {response.status}: {error_text}")

        except Exception as e:
            logger.error(f"❌ Error updating variant via REST: {e}")
            raise

    async def _update_single_variant_sku(self, variant_data: Dict[str, Any]) -> None:
        """
        Actualiza el SKU de una sola variante usando REST API (compatible con API 2025-04).

        Args:
            variant_data: Datos de la variante con id y sku
        """
        try:
            variant_id = variant_data["id"].split("/")[-1]  # Extract numeric ID
            sku = variant_data["sku"]

            # Usar REST API para actualizar SKU
            await self._update_variant_sku_via_rest(variant_id, sku)
            logger.info(f"✅ SKU updated via REST: {variant_data['id']} -> {sku}")

        except Exception as e:
            logger.warning(f"❌ Error updating variant SKU: {e}")
            raise

    async def _update_variant_sku_via_rest(self, variant_id: str, sku: str) -> None:
        """
        Actualiza el SKU de una variante usando la REST API de Shopify.

        Args:
            variant_id: ID numérico de la variante
            sku: Nuevo SKU a asignar
        """
        try:
            # Usar el HTTP client del shopify_client para REST API
            shop_domain = self.shopify_client.shop_url.replace("https://", "").replace(".myshopify.com", "")
            rest_url = f"https://{shop_domain}.myshopify.com/admin/api/2025-04/variants/{variant_id}.json"

            headers = {"X-Shopify-Access-Token": self.shopify_client.access_token, "Content-Type": "application/json"}

            data = {"variant": {"id": int(variant_id), "sku": sku}}

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.put(rest_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("variant")
                    else:
                        error_text = await response.text()
                        raise Exception(f"REST API error {response.status}: {error_text}")

        except Exception as e:
            logger.warning(f"❌ Error updating variant SKU via REST: {e}")
            raise

    async def _update_variant_skus(
        self, created_variants: List[Dict[str, Any]], original_variants: List[Any], product_id: str
    ) -> None:
        """
        Actualiza los SKUs de las variantes creadas ya que ProductVariantsBulkInput no acepta SKU.

        Args:
            created_variants: Variantes creadas por Shopify
            original_variants: Variantes originales con SKUs
        """
        try:
            # Crear mapeo de variantes por opciones
            sku_map = {}
            for original_variant in original_variants:
                if hasattr(original_variant, "options") and original_variant.options:
                    options_key = "-".join(str(opt) for opt in original_variant.options)
                    sku_map[options_key] = original_variant.sku

            # Actualizar SKUs usando productVariantsBulkUpdate
            variants_update_data = []
            for created_variant in created_variants:
                selected_options = created_variant.get("selectedOptions", [])
                if selected_options:
                    # Crear clave de opciones flexible (puede ser 1 o más opciones)
                    options_key = "-".join([opt["value"] for opt in selected_options])
                    if options_key in sku_map:
                        variants_update_data.append({"id": created_variant["id"], "sku": sku_map[options_key]})

            if variants_update_data:
                logger.info(f"🔄 Updating SKUs for {len(variants_update_data)} variants...")

                # Usar REST API para actualizar SKUs (más simple y confiable)
                try:
                    logger.info(f"🔄 Updating SKUs using REST API for {len(variants_update_data)} variants...")

                    success_count = 0
                    for variant_update in variants_update_data:
                        try:
                            # Usar REST API para actualizar SKU
                            variant_id = variant_update["id"].split("/")[-1]  # Extract numeric ID
                            await self._update_variant_sku_via_rest(variant_id, variant_update["sku"])
                            success_count += 1
                            logger.info(
                                f"   ✅ SKU updated via REST: {variant_update['id']} -> {variant_update['sku']}"
                            )
                        except Exception as e:
                            logger.warning(f"   ❌ Failed to update SKU for {variant_update['id']}: {e}")

                    logger.info(
                        f"✅ Successfully updated {success_count}/{len(variants_update_data)} variant SKUs via REST API"
                    )

                except Exception as e:
                    logger.warning(f"❌ Error during SKU updates: {e}")
                    logger.info("⏭️ Skipping SKU updates due to error")

        except Exception as e:
            logger.warning(f"❌ Error updating variant SKUs: {e}")
            # No es crítico si no se pueden actualizar los SKUs

    async def _remove_default_variant(self, product_id: str) -> None:
        """
        No elimina la variante por defecto, ya que Shopify no permite eliminar la última variante.
        En su lugar, actualizaremos la variante por defecto con los datos de la primera variante.

        Args:
            product_id: ID del producto
        """
        try:
            logger.info("🔄 Skipping default variant removal - Shopify requires at least one variant")
            # No intentamos eliminar la variante por defecto ya que:
            # 1. Shopify no permite eliminar la última variante de un producto
            # 2. El bulk creation agregará las nuevas variantes junto a la por defecto
            # 3. Podemos actualizar la variante por defecto después si es necesario

        except Exception as e:
            logger.warning(f"❌ Error in default variant handling: {e}")
            # No es crítico si no se puede manejar la variante por defecto

    async def _update_default_variant(self, product_id: str, variant: Any) -> None:
        """
        Actualiza la variante por defecto cuando solo hay una variante.

        Args:
            product_id: ID del producto
            variant: Datos de la variante
        """
        try:
            # Obtener la variante por defecto
            query = """
            query GetDefaultVariant($id: ID!) {
              product(id: $id) {
                variants(first: 1) {
                  edges {
                    node {
                      id
                    }
                  }
                }
              }
            }
            """

            result = await self.shopify_client._execute_query(query, {"id": product_id})

            if result and result.get("product"):
                variants = result["product"].get("variants", {}).get("edges", [])
                if variants:
                    default_variant_id = variants[0]["node"]["id"]

                    # Actualizar la variante por defecto usando REST API
                    variant_id = default_variant_id.split("/")[-1]  # Extract numeric ID

                    # SOLUCIÓN: Formatear precio correctamente para REST API
                    price_float = float(variant.price)
                    formatted_price = f"{price_float:.2f}"

                    update_payload = {
                        "price": formatted_price,
                        "sku": variant.sku,
                    }

                    if variant.compareAtPrice:
                        compare_price_float = float(variant.compareAtPrice)
                        formatted_compare_price = f"{compare_price_float:.2f}"
                        update_payload["compare_at_price"] = formatted_compare_price

                    await self._update_variant_via_rest(variant_id, update_payload)
                    logger.info(f"✅ Updated default variant via REST: {variant.sku} - ${variant.price}")

        except Exception as e:
            logger.error(f"❌ Error updating default variant: {e}")

    def _prepare_variant_data(self, variant: Any) -> Dict[str, Any]:
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
            for i, option_value in enumerate(variant.options):
                option_values.append({"optionName": "Color" if i == 0 else "Size", "name": str(option_value)})
            variant_data["optionValues"] = option_values

        # Inventario usando inventoryQuantities
        if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
            variant_data["inventoryQuantities"] = variant.inventoryQuantities

        # Política de inventario
        if variant.inventoryPolicy:
            variant_data["inventoryPolicy"] = (
                variant.inventoryPolicy.value if hasattr(variant.inventoryPolicy, "value") else variant.inventoryPolicy
            )

        return variant_data

    async def _create_metafields(self, product_id: str, metafields: List[Dict[str, Any]]) -> None:
        """
        Crea metafields para el producto.

        Args:
            product_id: ID del producto
            metafields: Lista de metafields a crear
        """
        try:
            metafields_set_input = []
            for metafield in metafields:
                metafield_input = {
                    "key": metafield["key"],
                    "namespace": metafield["namespace"],
                    "ownerId": product_id,
                    "type": metafield["type"],
                    "value": metafield["value"],
                }
                metafields_set_input.append(metafield_input)

            # Usar metafieldsSet mutation
            metafields_mutation = """
            mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
              metafieldsSet(metafields: $metafields) {
                metafields {
                  id
                  key
                  value
                  definition {
                    name
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """

            metafields_result = await self.shopify_client._execute_query(
                metafields_mutation, {"metafields": metafields_set_input}
            )

            if metafields_result and metafields_result.get("metafieldsSet"):
                set_result = metafields_result["metafieldsSet"]

                if set_result.get("userErrors"):
                    logger.warning(f"Metafields errors: {set_result['userErrors']}")

                created_metafields = set_result.get("metafields", [])
                logger.info(f"✅ Created {len(created_metafields)} metafields")

        except Exception as e:
            logger.warning(f"❌ Failed to create metafields: {e}")

    async def _activate_inventory_for_all_variants(self, product_id: str, variants: List[Any]) -> None:
        """
        Activa el tracking de inventario para todas las variantes.

        Args:
            product_id: ID del producto
            variants: Lista de variantes con datos de inventario
        """
        try:
            # Obtener todas las variantes del producto creado
            query = """
            query GetProductVariants($id: ID!) {
              product(id: $id) {
                variants(first: 50) {
                  edges {
                    node {
                      id
                      sku
                      inventoryItem {
                        id
                        tracked
                      }
                    }
                  }
                }
              }
            }
            """

            result = await self.shopify_client._execute_query(query, {"id": product_id})

            if result and result.get("product"):
                shopify_variants = result["product"].get("variants", {}).get("edges", [])
                logger.info(f"🔍 Activating inventory for {len(shopify_variants)} variants")

                # Mapear variantes por SKU
                variant_map = {}
                for input_variant in variants:
                    if hasattr(input_variant, "inventoryQuantities") and input_variant.inventoryQuantities:
                        variant_map[input_variant.sku] = input_variant.inventoryQuantities

                # Activar inventario para cada variante
                for variant_edge in shopify_variants:
                    variant_node = variant_edge["node"]
                    sku = variant_node.get("sku")
                    inventory_item_id = variant_node.get("inventoryItem", {}).get("id")

                    if sku in variant_map and inventory_item_id:
                        inventory_quantities = variant_map[sku]

                        for inv_qty in inventory_quantities:
                            try:
                                # Activar tracking y establecer cantidad
                                activation_result = await self.shopify_client.activate_inventory_tracking(
                                    inventory_item_id,
                                    inv_qty.get("locationId", self.primary_location_id),
                                    inv_qty.get("availableQuantity", 0),
                                )

                                if activation_result.get("success"):
                                    logger.info(
                                        f"✅ Activated inventory for variant {sku}: \
                                            {inv_qty.get('availableQuantity', 0)} units"
                                    )
                                else:
                                    logger.warning(f"❌ Failed to activate inventory for variant {sku}")

                            except Exception as inv_error:
                                logger.warning(f"❌ Error activating inventory for {sku}: {inv_error}")

        except Exception as e:
            logger.warning(f"❌ Error activating inventory for variants: {e}")
