#!/usr/bin/env python3
"""
Manejo de variantes de productos para Shopify.

Este módulo se encarga específicamente de:
- Crear variantes en Shopify
- Actualizar variantes existentes
- Sincronizar variantes (crear nuevas, actualizar existentes)
- Actualizar SKUs de variantes
- Operaciones REST API para variantes
"""

import logging
from typing import Any, Dict, List

import aiohttp

from .data_preparator import DataPreparator

logger = logging.getLogger(__name__)


class VariantManager:
    """
    Maneja todas las operaciones relacionadas con variantes de productos.
    """

    def __init__(self, shopify_client, primary_location_id: str):
        """
        Inicializa el manejador de variantes.

        Args:
            shopify_client: Cliente de Shopify GraphQL
            primary_location_id: ID de la ubicación principal
        """
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id
        self.data_preparator = DataPreparator()

    async def get_existing_variants(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene las variantes existentes de un producto.

        Args:
            product_id: ID del producto

        Returns:
            List: Lista de variantes existentes
        """
        try:
            all_variants = []
            has_next_page = True
            cursor = None
            
            while has_next_page:
                if cursor:
                    query = """
                    query GetProductVariants($id: ID!, $cursor: String!) {
                      product(id: $id) {
                        variants(first: 100, after: $cursor) {
                          edges {
                            node {
                              id
                              sku
                              price
                              selectedOptions {
                                name
                                value
                              }
                            }
                            cursor
                          }
                          pageInfo {
                            hasNextPage
                            endCursor
                          }
                        }
                      }
                    }
                    """
                    variables = {"id": product_id, "cursor": cursor}
                else:
                    query = """
                    query GetProductVariants($id: ID!) {
                      product(id: $id) {
                        variants(first: 100) {
                          edges {
                            node {
                              id
                              sku
                              price
                              selectedOptions {
                                name
                                value
                              }
                            }
                            cursor
                          }
                          pageInfo {
                            hasNextPage
                            endCursor
                          }
                        }
                      }
                    }
                    """
                    variables = {"id": product_id}

                result = await self.shopify_client._execute_query(query, variables)

                if result and result.get("product"):
                    variants_response = result["product"].get("variants", {})
                    variants = variants_response.get("edges", [])
                    all_variants.extend([variant["node"] for variant in variants])
                    
                    page_info = variants_response.get("pageInfo", {})
                    has_next_page = page_info.get("hasNextPage", False)
                    cursor = page_info.get("endCursor")
                    
                    logger.info(f"📄 Fetched page with {len(variants)} variants (total so far: {len(all_variants)})")
                else:
                    has_next_page = False

            logger.info(f"🔍 Found {len(all_variants)} total existing variants in product")
            
            # Log details of existing variants for debugging
            for variant in all_variants[:5]:  # Show first 5 for debugging
                options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                logger.debug(f"   Existing: SKU={variant.get('sku', 'N/A')}, Options={options_str}")
            
            if len(all_variants) > 5:
                logger.debug(f"   ... and {len(all_variants) - 5} more variants")
            
            return all_variants

        except Exception as e:
            logger.warning(f"❌ Error getting existing variants: {e}")
            return []

    async def sync_product_variants(
        self, product_id: str, new_variants: List[Any], existing_variants: List[Dict[str, Any]]
    ) -> None:
        """
        Sincroniza las variantes del producto (crear nuevas, actualizar existentes).

        Args:
            product_id: ID del producto
            new_variants: Nuevas variantes a sincronizar
            existing_variants: Variantes existentes en Shopify
        """
        try:
            logger.info(f"🔄 Syncing {len(new_variants)} variants with {len(existing_variants)} existing variants")

            # Build a set of existing variant option combinations for fast lookup
            existing_combinations = {}  # Map combo to existing variant
            for existing in existing_variants:
                existing_options = existing.get("selectedOptions", [])
                # Sort options by name to ensure consistent comparison
                sorted_options = sorted(existing_options, key=lambda x: x.get("name", ""))
                # Create a normalized string representation
                combo = " / ".join([f"{opt['name']}:{opt['value']}" for opt in sorted_options])
                existing_combinations[combo] = existing

            # Separar variantes en crear/actualizar
            variants_to_create = []
            variants_to_update = []

            for new_variant in new_variants:
                # Buscar si existe una variante con las mismas opciones
                existing_match = None
                variant_combo = ""

                if hasattr(new_variant, "options") and new_variant.options:
                    # Create normalized option representation
                    # Assume first option is Color, second is Size (as per RMS convention)
                    option_pairs = []
                    for i, option_value in enumerate(new_variant.options):
                        option_name = "Color" if i == 0 else "Size" if i == 1 else f"Option{i+1}"
                        option_pairs.append((option_name, str(option_value)))
                    
                    # Sort by option name for consistent comparison
                    option_pairs.sort(key=lambda x: x[0])
                    variant_combo = " / ".join([f"{name}:{value}" for name, value in option_pairs])
                    
                    # Check if this exact combination exists in Shopify
                    existing_match = existing_combinations.get(variant_combo)

                if existing_match:
                    variants_to_update.append((existing_match, new_variant))
                    logger.info(f"🔄 Will update variant: {new_variant.sku} - {variant_combo}")
                else:
                    variants_to_create.append(new_variant)
                    logger.info(f"🆕 Will create variant: {new_variant.sku} - {variant_combo}")

            # Crear nuevas variantes si las hay
            if variants_to_create:
                await self.create_multiple_variants(product_id, variants_to_create, existing_variants)

            # Actualizar variantes existentes si las hay
            if variants_to_update:
                await self.update_existing_variants(variants_to_update)

            logger.info(
                f"✅ Variant sync completed: {len(variants_to_create)} created, {len(variants_to_update)} updated"
            )

        except Exception as e:
            logger.error(f"❌ Error syncing product variants: {e}")
            raise

    async def create_multiple_variants(
        self, product_id: str, variants: List[Any], existing_variants: List[Dict[str, Any]] = None
    ) -> None:
        """
        Crea múltiples variantes usando productVariantsBulkCreate.

        Args:
            product_id: ID del producto
            variants: Lista de variantes a crear
            existing_variants: Lista de variantes existentes (opcional)
        """
        try:
            existing_variants = existing_variants or []

            # Build a set of existing variant option combinations for fast lookup
            existing_combinations = set()
            for existing in existing_variants:
                existing_options = existing.get("selectedOptions", [])
                # Sort options by name to ensure consistent comparison
                sorted_options = sorted(existing_options, key=lambda x: x.get("name", ""))
                # Create a normalized string representation
                combo = " / ".join([f"{opt['name']}:{opt['value']}" for opt in sorted_options])
                existing_combinations.add(combo)
                logger.debug(f"   Existing combo in Shopify: {combo}")

            # Determinar qué variantes necesitamos crear (evitar duplicados)
            variants_to_create = []
            variants_to_update = []
            seen_combinations = set()  # Track combinations we're trying to create

            for variant in variants:
                # Verificar si esta variante ya existe
                existing_match = None
                variant_combo = ""
                
                if hasattr(variant, "options") and variant.options:
                    # Create normalized option representation
                    # Assume first option is Color, second is Size (as per RMS convention)
                    option_pairs = []
                    for i, option_value in enumerate(variant.options):
                        option_name = "Color" if i == 0 else "Size" if i == 1 else f"Option{i+1}"
                        option_pairs.append((option_name, str(option_value)))
                    
                    # Sort by option name for consistent comparison
                    option_pairs.sort(key=lambda x: x[0])
                    variant_combo = " / ".join([f"{name}:{value}" for name, value in option_pairs])
                    
                    logger.debug(f"   Checking variant: SKU={variant.sku}, Combo={variant_combo}")
                    
                    # Check if this exact combination exists in Shopify
                    if variant_combo in existing_combinations:
                        # Find the matching existing variant for update
                        for existing in existing_variants:
                            existing_options = existing.get("selectedOptions", [])
                            sorted_existing = sorted(existing_options, key=lambda x: x.get("name", ""))
                            existing_combo = " / ".join([f"{opt['name']}:{opt['value']}" for opt in sorted_existing])
                            if existing_combo == variant_combo:
                                existing_match = existing
                                break

                if existing_match:
                    # Variante existe - marcar para actualización
                    variants_to_update.append((existing_match, variant))
                    logger.info(f"🔄 Will update existing variant: SKU={variant.sku}, Options={variant_combo}")
                elif variant_combo in seen_combinations:
                    # We're already trying to create this combination - skip duplicate
                    logger.warning(f"⚠️ Skipping duplicate in batch: SKU={variant.sku}, Options={variant_combo}")
                else:
                    # Variante nueva - marcar para creación
                    variants_to_create.append(variant)
                    seen_combinations.add(variant_combo)
                    logger.info(f"🆕 Will create new variant: SKU={variant.sku}, Options={variant_combo}")

            # Preparar datos de variantes para bulk creation (solo las nuevas)
            variants_data = []
            for variant in variants_to_create:
                variant_data = self.data_preparator.prepare_variant_data(variant)
                variants_data.append(variant_data)

            # Crear variantes nuevas si las hay
            if variants_data:
                logger.info(f"🚀 Creating {len(variants_data)} new variants using bulk creation...")

                # Preparar cantidades de inventario para las nuevas variantes
                inventory_quantities = {}
                for variant in variants_to_create:
                    if hasattr(variant, "sku") and hasattr(variant, "inventory_quantity"):
                        inventory_quantities[variant.sku] = variant.inventory_quantity

                # Crear variantes con inventario
                bulk_result = await self.shopify_client.create_variants_bulk(
                    product_id,
                    variants_data,
                    location_id=self.primary_location_id,
                    inventory_quantities=inventory_quantities,
                )

                # Check if duplicates were skipped
                duplicates_skipped = bulk_result.get("duplicatesSkipped", 0)
                if duplicates_skipped > 0:
                    logger.warning(f"⚠️ {duplicates_skipped} variants were already present and skipped")

                if bulk_result and bulk_result.get("productVariants"):
                    created_variants = bulk_result["productVariants"]
                    logger.info(f"✅ Successfully created {len(created_variants)} new variants")

                    # Actualizar SKUs después de la creación (ya que ProductVariantsBulkInput no acepta SKU)
                    await self.update_variant_skus(created_variants, variants_to_create, product_id)

                    # Log de cada variante creada
                    for variant in created_variants:
                        options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                        logger.info(
                            f"   ✅ New variant: {variant.get('sku', 'NO-SKU')} - {options_str} - ${variant['price']}"
                        )
                elif duplicates_skipped > 0:
                    logger.info(f"ℹ️ All {duplicates_skipped} variants already existed, none created")
                else:
                    logger.warning("❌ No variants returned from bulk creation")
            else:
                logger.info("ℹ️  No new variants to create")

            # Actualizar variantes existentes si las hay
            if variants_to_update:
                logger.info(f"🔄 Updating {len(variants_to_update)} existing variants...")
                await self.update_existing_variants(variants_to_update)

        except Exception as e:
            logger.error(f"❌ Error creating multiple variants: {e}")
            raise

    async def update_existing_variants(self, variants_to_update: List[tuple]) -> None:
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

                # CORRECCIÓN DE PRECIOS: Verificar si el precio existente tiene problema de doble IVA
                try:
                    existing_price_float = float(existing_price_str)
                    price_difference = abs(existing_price_float - new_price_float)
                    
                    # Si el precio existente es significativamente más alto (posible doble IVA)
                    if existing_price_float > new_price_float and price_difference > 1000:
                        # Verificar si parece ser doble aplicación de IVA (13%)
                        expected_inflated_price = new_price_float * 1.13
                        if abs(existing_price_float - expected_inflated_price) < 1.0:
                            logger.warning(f"🔧 CORRIGIENDO DOBLE IVA para {new_variant.sku}:")
                            logger.warning(f"   Precio con doble IVA: ₡{existing_price_float:,.2f}")
                            logger.warning(f"   Precio correcto RMS: ₡{new_price_float:,.2f}")
                            logger.warning("   ➡️ Forzando corrección")
                except (ValueError, TypeError):
                    pass  # Usar el precio nuevo de RMS

                # DEBUGGING: Log de datos antes de preparar actualización
                logger.info(f"🔍 DEBUG VARIANT PREP - SKU: {new_variant.sku}")
                logger.info(
                    f"🔍 DEBUG VARIANT PREP - Original price object: {new_variant.price} "
                    f"(type: {type(new_variant.price)})"
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
                logger.info(f"🔄 Using bulk update for {len(update_data)} variants")

                # Como no tenemos product_id aquí, vamos a actualizar una por una usando la API correcta
                for variant_update in update_data:
                    await self.update_single_variant(variant_update)

                logger.info(f"✅ Updated {len(update_data)} existing variants")

        except Exception as e:
            logger.warning(f"❌ Error updating existing variants: {e}")

    async def update_single_variant(self, variant_data: Dict[str, Any]) -> None:
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
                await self.update_variant_via_rest(variant_id, update_payload)
                logger.info(f"   ✅ Updated variant via REST: {variant_data.get('sku')} - ${variant_data.get('price')}")
            else:
                logger.warning(f"   ⚠️ No fields to update for variant {variant_data.get('id')}")

        except Exception as e:
            logger.warning(f"❌ Error updating single variant: {e}")

    async def update_variant_via_rest(self, variant_id: str, update_data: Dict[str, Any]) -> None:
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

    async def update_variant_sku_via_rest(self, variant_id: str, sku: str) -> None:
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

    async def update_variant_skus(
        self, created_variants: List[Dict[str, Any]], original_variants: List[Any], product_id: str
    ) -> None:
        """
        Actualiza los SKUs de las variantes creadas ya que ProductVariantsBulkInput no acepta SKU.

        Args:
            created_variants: Variantes creadas por Shopify
            original_variants: Variantes originales con SKUs
            product_id: ID del producto (para compatibilidad)
        """
        try:
            logger.info("🔄 Updating SKUs for existing variants... Product ID: " + str(product_id))
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
                            await self.update_variant_sku_via_rest(variant_id, variant_update["sku"])
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
