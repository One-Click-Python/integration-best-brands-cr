#!/usr/bin/env python3
"""
Manejo de inventario para productos y variantes en Shopify.

Este módulo se encarga específicamente de:
- Activar tracking de inventario para variantes
- Actualizar cantidades de inventario
- Verificar inventario existente
"""

import logging
from typing import Any, Dict, List

from app.db.queries import (
    INVENTORY_ACTIVATE_MUTATION,
    INVENTORY_BULK_ADJUST_MUTATION,
    INVENTORY_ITEM_UPDATE_MUTATION,
    INVENTORY_SET_QUANTITIES_MUTATION,
)
from app.db.queries.products import PRODUCT_QUERY

logger = logging.getLogger(__name__)


class InventoryManager:
    """
    Maneja todas las operaciones relacionadas con inventario de variantes.
    """

    def __init__(self, shopify_client, primary_location_id: str):
        """
        Inicializa el manejador de inventario.

        Args:
            shopify_client: Cliente de Shopify GraphQL
            primary_location_id: ID de la ubicación principal
        """
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id

    async def activate_inventory_for_all_variants(self, product_id: str, variants: List[Any]) -> None:
        """
        MÉTODO ACTUALIZADO: Ahora usa activate_inventory_tracking_well que está probado y funciona.
        Procesa todas las variantes que tengan datos de inventario sin importar el formato.

        Args:
            product_id: ID del producto
            variants: Lista de variantes con datos de inventario
        """
        try:
            # CAMBIO: Procesar todas las variantes que tengan cualquier tipo de datos de inventario
            variants_with_inventory = []
            for variant in variants:
                has_inventory_data = False

                # Verificar formato inventoryQuantities (complejo)
                if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                    has_inventory_data = True

                # Verificar formato inventory_quantity (simple)
                if hasattr(variant, "inventory_quantity") and variant.inventory_quantity is not None:
                    has_inventory_data = True

                if has_inventory_data:
                    variants_with_inventory.append(variant)

            if not variants_with_inventory:
                logger.info("ℹ️ No inventory data found in any variants")
                return

            logger.info(f"🔄 Processing inventory for {len(variants_with_inventory)} variants with inventory data")

            # Obtener todas las variantes del producto creado
            result = await self.shopify_client._execute_query(PRODUCT_QUERY, {"id": product_id})

            if result and result.get("product"):
                shopify_variants = result["product"].get("variants", {}).get("edges", [])
                logger.info(f"🔍 Processing inventory for {len(shopify_variants)} variants using proven working method")

                # Procesar todas las variantes que tengan datos de inventario
                for variant_edge in shopify_variants:
                    variant_node = variant_edge["node"]
                    sku = variant_node.get("sku")
                    inventory_item_id = variant_node.get("inventoryItem", {}).get("id")

                    if not inventory_item_id:
                        logger.warning(f"⚠️ No inventory item found for variant {sku}")
                        continue

                    # Buscar datos de inventario para esta variante
                    target_variant = None
                    for input_variant in variants_with_inventory:
                        if hasattr(input_variant, "sku") and input_variant.sku == sku:
                            target_variant = input_variant
                            break

                    if not target_variant:
                        logger.info(f"ℹ️ No inventory data found for variant {sku}")
                        continue

                    # Determinar cantidad deseada
                    desired_quantity = 0
                    location_id = self.primary_location_id

                    # Formato inventoryQuantities (complejo)
                    if hasattr(target_variant, "inventoryQuantities") and target_variant.inventoryQuantities:
                        for inv_qty in target_variant.inventoryQuantities:
                            loc_id = inv_qty.get("locationId", self.primary_location_id)
                            if loc_id == self.primary_location_id:
                                desired_quantity = inv_qty.get("availableQuantity", 0)
                                location_id = loc_id
                                break
                    # Formato inventory_quantity (simple)
                    elif (
                        hasattr(target_variant, "inventory_quantity") and target_variant.inventory_quantity is not None
                    ):
                        desired_quantity = target_variant.inventory_quantity

                    if desired_quantity > 0:
                        try:
                            logger.info(f"🔄 Using proven working method for variant {sku}: {desired_quantity} units")

                            # CAMBIO CRÍTICO: Usar el método correcto con queries importadas
                            tracking_result = await self._activate_inventory_tracking_well(
                                inventory_item_id, location_id, desired_quantity
                            )

                            if tracking_result.get("success"):
                                final_quantity = tracking_result.get("finalQuantity", desired_quantity)
                                logger.info(f"✅ Successfully set inventory for variant {sku}: {final_quantity} units")
                            else:
                                error_msg = tracking_result.get("error", "Unknown error")
                                logger.warning(f"❌ Failed to set inventory for variant {sku}: {error_msg}")

                        except Exception as inv_error:
                            logger.warning(f"❌ Error setting inventory for {sku}: {inv_error}")
                    else:
                        logger.info(f"ℹ️ No quantity to set for variant {sku} (quantity: {desired_quantity})")

        except Exception as e:
            logger.warning(f"❌ Error verifying inventory for variants: {e}")

    async def force_inventory_update_for_new_product(self, product_id: str, variants: List[Any]) -> None:
        """
        Fuerza la activación de tracking y actualización de inventario para un producto recién creado.
        CAMBIO CRÍTICO: Ahora usa el mismo método probado que funciona en UPDATE
        para evitar el problema de quantities no establecidas.

        Args:
            product_id: ID del producto
            variants: Lista de variantes con datos de inventario
        """
        try:
            logger.info(f"🔄 Force updating inventory for newly created product {product_id}")

            # CAMBIO: Usar el mismo método que funciona correctamente en UPDATE
            # En lugar del complejo flujo de 2 pasos, usar activate_inventory_for_all_variants
            logger.info("🔧 Using the proven working method from UPDATE flow...")
            await self.activate_inventory_for_all_variants(product_id, variants)

            logger.info("✅ Successfully updated inventory using proven working method")

        except Exception as e:
            logger.error(f"❌ Error force updating inventory for new product: {e}")

    async def _apply_inventory_adjustments(self, adjustments: List[Dict[str, Any]]) -> None:
        """
        Aplica ajustes de inventario usando inventoryBulkAdjustQuantityAtLocation.

        Args:
            adjustments: Lista de ajustes a aplicar
        """
        try:
            # Preparar input para la mutation
            inventory_item_adjustments = []
            for adj in adjustments:
                inventory_item_adjustments.append(
                    {"inventoryItemId": adj["inventory_item_id"], "availableDelta": adj["delta"]}
                )

            # Usar mutation correcta de Shopify para ajustar inventario
            variables = {
                "input": {
                    "inventoryItemAdjustments": inventory_item_adjustments,
                    "locationId": self.primary_location_id,
                }
            }

            logger.info(f"📦 Applying {len(inventory_item_adjustments)} inventory adjustments...")
            result = await self.shopify_client._execute_query(INVENTORY_BULK_ADJUST_MUTATION, variables)

            if result and result.get("inventoryBulkAdjustQuantities"):
                bulk_result = result["inventoryBulkAdjustQuantities"]

                if bulk_result.get("userErrors"):
                    error_messages = [err.get("message", "Unknown error") for err in bulk_result["userErrors"]]
                    logger.warning(f"❌ Inventory adjustment errors: {error_messages}")
                    return

                adjustment_group = bulk_result.get("inventoryAdjustmentGroup", {})
                changes = adjustment_group.get("changes", [])
                logger.info(f"✅ Successfully adjusted inventory for {len(changes)} variants:")

                for change in changes:
                    item_sku = change.get("item", {}).get("sku", "NO-SKU")
                    delta = change.get("delta", 0)
                    quantity_after = change.get("quantityAfterChange", 0)
                    logger.info(f"   📦 {item_sku}: Δ{delta:+d} → {quantity_after} units available")

            else:
                logger.warning("❌ No response from inventory bulk adjustment")

        except Exception as e:
            logger.error(f"❌ Error applying inventory adjustments: {e}")

    async def activate_inventory_tracking(self, variant_node: Dict[str, Any]) -> bool:
        """
        Activa el tracking de inventario para una variante usando inventoryItemUpdate mutation.

        Args:
            variant_node: Nodo de la variante obtenido de GraphQL

        Returns:
            bool: True si se activó correctamente
        """
        try:
            inventory_item_id = variant_node.get("inventoryItem", {}).get("id")
            sku = variant_node.get("sku", "NO-SKU")

            if not inventory_item_id:
                logger.warning(f"❌ No inventory item ID found for variant {sku}")
                return False

            logger.info(f"🔧 Activating inventory tracking for variant {sku}")

            # Usar GraphQL mutation inventoryItemUpdate para activar tracking
            variables = {"id": inventory_item_id, "input": {"tracked": True, "requiresShipping": True}}

            result = await self.shopify_client._execute_query(INVENTORY_ITEM_UPDATE_MUTATION, variables)

            if result and result.get("inventoryItemUpdate"):
                update_result = result["inventoryItemUpdate"]

                if update_result.get("userErrors"):
                    error_messages = [err.get("message", "Unknown error") for err in update_result["userErrors"]]
                    logger.warning(f"❌ Error activating tracking for {sku}: {error_messages}")
                    return False

                inventory_item = update_result.get("inventoryItem", {})
                if inventory_item.get("tracked"):
                    logger.info(f"✅ Successfully activated inventory tracking for variant {sku}")
                    return True
                else:
                    logger.warning(f"❌ Failed to activate tracking for variant {sku}")
                    return False
            else:
                logger.warning(f"❌ No response from inventory tracking activation for {sku}")
                return False

        except Exception as e:
            logger.error(f"❌ Error activating inventory tracking for {variant_node.get('sku', 'NO-SKU')}: {e}")
            return False

    async def update_variant_inventory(
        self, variant_node: Dict[str, Any], location_id: str, quantity: int
    ) -> Dict[str, Any]:
        """
        Actualiza la cantidad de inventario para una variante específica.

        Args:
            variant_node: Nodo de variante con información de inventario
            location_id: ID de la ubicación
            quantity: Nueva cantidad de inventario

        Returns:
            Dict: Resultado de la operación
        """
        try:
            logger.info(f"🔄 Updating inventory for variant {variant_node.get('sku', 'NO-SKU')}: {quantity} units")

            # Usar el método del cliente Shopify para actualizar inventario
            result = await self.shopify_client.set_variant_inventory_quantity(variant_node, location_id, quantity)

            if result.get("success"):
                logger.info(f"✅ Successfully updated inventory: {quantity} units")
                return {"success": True, "quantity": quantity}
            else:
                logger.warning(f"❌ Failed to update inventory: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get("error", "Unknown error")}

        except Exception as e:
            logger.warning(f"❌ Error updating variant inventory: {e}")
            return {"success": False, "error": str(e)}

    async def bulk_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Actualiza inventario para múltiples variantes en lote.

        Args:
            inventory_updates: Lista de actualizaciones de inventario
                Formato: [{"variant_node": {}, "location_id": "", "quantity": 0}, ...]

        Returns:
            Dict: Resultado con éxitos y fallos
        """
        try:
            logger.info(f"🔄 Bulk updating inventory for {len(inventory_updates)} variants")

            successes = []
            failures = []

            for update in inventory_updates:
                variant_node = update.get("variant_node")
                location_id = update.get("location_id", self.primary_location_id)
                quantity = update.get("quantity", 0)

                try:
                    result = await self.update_variant_inventory(variant_node, location_id, quantity)

                    if result.get("success"):
                        successes.append({"sku": variant_node.get("sku", "NO-SKU"), "quantity": quantity})
                    else:
                        failures.append(
                            {"sku": variant_node.get("sku", "NO-SKU"), "error": result.get("error", "Unknown error")}
                        )

                except Exception as e:
                    failures.append({"sku": variant_node.get("sku", "NO-SKU"), "error": str(e)})

            logger.info(f"✅ Bulk inventory update completed: {len(successes)} successes, {len(failures)} failures")

            return {
                "success": True,
                "total": len(inventory_updates),
                "successes": len(successes),
                "failures": len(failures),
                "success_details": successes,
                "failure_details": failures,
            }

        except Exception as e:
            logger.error(f"❌ Error in bulk inventory update: {e}")
            return {
                "success": False,
                "error": str(e),
                "total": len(inventory_updates),
                "successes": 0,
                "failures": len(inventory_updates),
            }

    def validate_inventory_data(self, variants: List[Any]) -> Dict[str, Any]:
        """
        Valida que los datos de inventario sean correctos antes de aplicarlos.

        Args:
            variants: Lista de variantes con datos de inventario

        Returns:
            Dict: Resultado de la validación
        """
        try:
            validation_results = {"valid": [], "invalid": [], "warnings": []}

            for variant in variants:
                sku = getattr(variant, "sku", "NO-SKU")

                # Verificar si tiene inventoryQuantities
                if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                    for inv_qty in variant.inventoryQuantities:
                        location_id = inv_qty.get("locationId")
                        quantity = inv_qty.get("availableQuantity")

                        # Validaciones
                        if location_id is None:
                            validation_results["warnings"].append(
                                f"SKU {sku}: locationId not specified, will use default"
                            )

                        if quantity is None or quantity < 0:
                            validation_results["invalid"].append(f"SKU {sku}: Invalid quantity {quantity}")
                            continue

                        if quantity > 1000000:  # Cantidad muy alta
                            validation_results["warnings"].append(f"SKU {sku}: Very high quantity {quantity}")

                        validation_results["valid"].append(f"SKU {sku}: Valid inventory {quantity}")
                else:
                    validation_results["warnings"].append(f"SKU {sku}: No inventory quantities specified")

            logger.info(
                f"📋 Inventory validation: {len(validation_results['valid'])} valid, {
                    len(validation_results['invalid'])
                } invalid, {len(validation_results['warnings'])} warnings"
            )

            return {"is_valid": len(validation_results["invalid"]) == 0, "results": validation_results}

        except Exception as e:
            logger.error(f"❌ Error validating inventory data: {e}")
            return {"is_valid": False, "error": str(e), "results": {"valid": [], "invalid": [], "warnings": []}}

    async def _activate_inventory_tracking_well(
        self, inventory_item_id: str, location_id: str, available_quantity: int = None
    ) -> Dict[str, Any]:
        """
        Activa el tracking de inventario y establece la cantidad disponible inicial.

        Flujo de 3 pasos:
        1. Habilitar tracking en el inventory item
        2. Activar inventory en la ubicación
        3. Establecer cantidad disponible

        Args:
            inventory_item_id: ID del item de inventario
            location_id: ID de la ubicación
            available_quantity: Cantidad disponible inicial

        Returns:
            Resultado completo con el inventory level final
        """
        try:
            # 📝 PASO 1: Habilitar tracking en el inventory item
            logger.info(f"🔄 Step 1: Enabling tracking for item {inventory_item_id}")
            update_variables = {"id": inventory_item_id, "input": {"tracked": True}}
            update_result = await self.shopify_client._execute_query(INVENTORY_ITEM_UPDATE_MUTATION, update_variables)
            update_data = update_result.get("inventoryItemUpdate", {})
            if update_errors := update_data.get("userErrors", []):
                logger.error(f"❌ Step 1 failed: {update_errors}")
                return {"success": False, "step": 1, "errors": update_errors}

            logger.info("✅ Step 1: Tracking enabled successfully")

            # 📍 PASO 2: Activar inventory en la ubicación
            activation_variables = {"inventoryItemId": inventory_item_id, "locationId": location_id}
            activation_result = await self.shopify_client._execute_query(
                INVENTORY_ACTIVATE_MUTATION, activation_variables
            )
            activation_data = activation_result.get("inventoryActivate", {})
            if activation_errors := activation_data.get("userErrors", []):
                logger.error(f"❌ Step 2 failed: {activation_errors}")
                return {"success": False, "step": 2, "errors": activation_errors}

            inventory_level = activation_data.get("inventoryLevel", {})
            logger.info("✅ Step 2: Inventory activated at location")

            # 📊 PASO 3: Establecer cantidad disponible (si se especifica)
            if available_quantity is not None and available_quantity > 0:
                logger.info(f"🔄 Step 3: Setting available quantity to {available_quantity}")
                # Obtener la cantidad actual del inventory level
                current_quantity = inventory_level.get("available", 0)
                logger.info(f"   Current quantity: {current_quantity}")
                # Para establecer la cantidad, usamos inventorySetQuantities
                # Incluir ignoreCompareQuantity para forzar el establecimiento
                set_quantity_variables = {
                    "input": {
                        "name": "available",
                        "reason": "correction",
                        "referenceDocumentUri": f"https://inventory-setup/item/{inventory_item_id.split('/')[-1]}",
                        "ignoreCompareQuantity": True,
                        "quantities": [
                            {
                                "inventoryItemId": inventory_item_id,
                                "locationId": location_id,
                                "quantity": available_quantity,
                            }
                        ],
                    }
                }

                try:
                    logger.debug(f"Sending inventorySetQuantities with variables: {set_quantity_variables}")
                    set_result = await self.shopify_client._execute_query(
                        INVENTORY_SET_QUANTITIES_MUTATION, set_quantity_variables
                    )
                    logger.debug(f"inventorySetQuantities response: {set_result}")
                except Exception as query_error:
                    logger.error(f"❌ Step 3 failed: GraphQL query error: {query_error}")
                    return {
                        "success": False,
                        "step": 3,
                        "errors": [{"message": f"GraphQL query failed: {str(query_error)}"}],
                    }

                # Verificar que set_result no sea None
                if not set_result:
                    logger.error("❌ Step 3 failed: No response from inventorySetQuantities")
                    return {"success": False, "step": 3, "errors": [{"message": "No response from GraphQL"}]}

                set_data = set_result.get("inventorySetQuantities", {})
                if not set_data:
                    logger.error("❌ Step 3 failed: No inventorySetQuantities in response")
                    return {
                        "success": False,
                        "step": 3,
                        "errors": [{"message": "No inventorySetQuantities field in response"}],
                    }

                if set_errors := set_data.get("userErrors", []):
                    logger.error(f"❌ Step 3 failed: {set_errors}")
                    return {"success": False, "step": 3, "errors": set_errors}

                adjustment_group = set_data.get("inventoryAdjustmentGroup")
                if adjustment_group is None:
                    # Si no hay errores y adjustment_group es None, significa que no hubo cambios
                    # Esto puede pasar cuando la cantidad ya es la deseada
                    logger.info("✅ Step 3: Quantity already at desired value (no changes needed)")
                    final_quantity = available_quantity
                else:
                    # Procesar cambios normalmente
                    changes = adjustment_group.get("changes", [])

                    if changes:
                        available_change = next((c for c in changes if c.get("name") == "available"), changes[0])
                        delta = available_change.get("delta", 0)
                        final_quantity = available_change.get("quantityAfterChange", current_quantity + delta)
                        logger.info(f"✅ Step 3: Quantity set (Δ{delta:+d}) → Final: {final_quantity}")
                    else:
                        final_quantity = available_quantity
                        logger.info("✅ Step 3: Quantity operation completed")
            else:
                logger.info("ℹ️ Step 3: No quantity specified, skipping adjustment")
                final_quantity = 0

            return {
                "success": True,
                "inventoryLevel": inventory_level,
                "tracked": True,
                "finalQuantity": final_quantity,
            }

        except Exception as e:
            logger.error(f"❌ Failed to activate inventory tracking: {e}")
            return {"success": False, "error": str(e)}
