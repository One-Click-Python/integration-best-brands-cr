"""
Servicio de sincronización de pedidos de Shopify hacia RMS.

Este módulo maneja la sincronización de pedidos específicos
desde Shopify hacia Microsoft Retail Management System.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging_config import LogContext
from app.utils.error_handler import (
    ErrorAggregator,
    SyncException,
    ValidationException,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyToRMSSync:
    """
    Clase principal para sincronización de pedidos Shopify → RMS.
    """

    def __init__(self):
        """Inicializa el servicio de sincronización."""
        self.sync_id = f"shopify_to_rms_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.error_aggregator = ErrorAggregator()

        try:
            # Inicializar clientes RMS y Shopify
            from app.db.rms_handler import RMSHandler
            from app.db.shopify_graphql_client import ShopifyGraphQLClient
            
            self.rms_handler = RMSHandler()
            self.graphql_client = ShopifyGraphQLClient()
            self.shopify_client = None  # Se inicializará en _ensure_clients_initialized

            logger.info(f"Shopify to RMS sync service initialized - ID: {self.sync_id}")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize Shopify to RMS sync service: {str(e)}",
                service="shopify_to_rms",
                operation="initialize",
            ) from e

    async def _ensure_clients_initialized(self):
        """Asegura que los clientes estén inicializados."""
        if self.shopify_client is None:
            from app.db.shopify_order_client import ShopifyOrderClient
            await self.graphql_client.initialize()
            self.shopify_client = ShopifyOrderClient(self.graphql_client)
        
        # Inicializar RMS handler si es necesario
        if not self.rms_handler.is_initialized():
            await self.rms_handler.initialize()

    async def close(self):
        """Cierra los clientes."""
        if self.graphql_client:
            await self.graphql_client.close()

    async def sync_orders(
        self,
        order_ids: List[str],
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        Sincroniza pedidos específicos de Shopify hacia RMS.

        Args:
            order_ids: Lista de IDs de pedidos de Shopify
            skip_validation: Omitir validaciones de negocio

        Returns:
            Dict: Resultado de la sincronización
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Asegurar que los clientes estén inicializados
            await self._ensure_clients_initialized()
            
            with LogContext(sync_id=self.sync_id, operation="sync_orders"):
                logger.info(f"Starting Shopify to RMS sync for {len(order_ids)} orders")

                # Estadísticas
                stats = {
                    "total_orders": len(order_ids),
                    "processed": 0,
                    "created": 0,
                    "updated": 0,
                    "errors": 0,
                    "skipped": 0,
                }

                # Procesar pedidos en lotes
                batch_size = settings.SYNC_BATCH_SIZE
                for i in range(0, len(order_ids), batch_size):
                    batch = order_ids[i : i + batch_size]
                    batch_results = await self._process_order_batch(batch, skip_validation)

                    # Agregar estadísticas del batch
                    for key in ["processed", "created", "updated", "errors", "skipped"]:
                        stats[key] += batch_results.get(key, 0)

                # Generar reporte final
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                return self._generate_sync_report(stats, duration)

        except Exception as e:
            logger.error(f"Failed to sync Shopify orders: {e}")
            raise SyncException(
                message=f"Failed to sync Shopify orders: {str(e)}",
                service="shopify_to_rms",
                operation="sync_orders",
            ) from e

    async def _process_order_batch(self, order_ids: List[str], skip_validation: bool) -> Dict[str, int]:
        """
        Procesa un lote de pedidos.

        Args:
            order_ids: IDs de pedidos del lote
            skip_validation: Omitir validaciones

        Returns:
            Dict: Estadísticas del lote
        """
        batch_stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0,
        }

        for order_id in order_ids:
            try:
                result = await self._sync_single_order(order_id, skip_validation)
                batch_stats[result["action"]] += 1
                batch_stats["processed"] += 1

            except Exception as e:
                self.error_aggregator.add_error(e, {"order_id": order_id})
                batch_stats["errors"] += 1
                logger.error(f"Failed to sync order {order_id}: {e}")

        return batch_stats

    async def _sync_single_order(self, order_id: str, skip_validation: bool) -> Dict[str, Any]:
        """
        Sincroniza un pedido individual.

        Args:
            order_id: ID del pedido de Shopify
            skip_validation: Omitir validaciones

        Returns:
            Dict: Resultado de la sincronización
        """
        try:
            # 1. Obtener pedido de Shopify
            logger.debug(f"Fetching Shopify order: {order_id}")
            shopify_order = await self.shopify_client.get_order(order_id)
            
            if not shopify_order:
                raise ValidationException(
                    message=f"Order {order_id} not found in Shopify",
                    field="order_id",
                    invalid_value=order_id
                )

            # 2. Validar pedido si no se omite validación
            if not skip_validation:
                validated_order = self._validate_shopify_order(shopify_order)
            else:
                validated_order = shopify_order

            # 3. Convertir a formato RMS
            logger.debug(f"Converting order {order_id} to RMS format")
            rms_order = await self._convert_to_rms_format(validated_order)

            # 4. Verificar si el pedido ya existe en RMS
            existing_order = await self.rms_handler.find_order_by_shopify_id(order_id)

            # 5. Crear o actualizar en RMS
            if existing_order:
                logger.info(f"Updating existing RMS order for Shopify order {order_id}")
                result = await self._update_rms_order(existing_order, rms_order)
                action = "updated"
            else:
                logger.info(f"Creating new RMS order for Shopify order {order_id}")
                result = await self._create_rms_order(rms_order)
                action = "created"

            logger.info(f"Successfully synced order {order_id} - action: {action}")
            return {
                "order_id": order_id,
                "action": action,
                "rms_order_id": result.get("order_id"),
                "shopify_order_number": shopify_order.get("name", ""),
            }

        except Exception as e:
            logger.error(f"Error syncing order {order_id}: {e}")
            raise

    def _validate_shopify_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida un pedido de Shopify.

        Args:
            order: Datos del pedido

        Returns:
            Dict: Pedido validado

        Raises:
            ValidationException: Si la validación falla
        """
        # Validar campos requeridos básicos
        required_fields = ["id", "name", "createdAt", "totalPriceSet", "lineItems"]

        for field in required_fields:
            if not order.get(field):
                raise ValidationException(
                    message=f"Missing required field: {field}",
                    field=field,
                    invalid_value=order.get(field),
                )

        # Validar que tenga líneas de pedido
        line_items = order.get("lineItems", [])
        if not line_items or len(line_items) == 0:
            raise ValidationException(
                message="Order must have at least one line item",
                field="lineItems",
                invalid_value=line_items,
            )

        # Validar que cada línea tenga SKU para mapear a RMS
        for i, item in enumerate(line_items):
            if not item.get("sku"):
                logger.warning(f"Line item {i+1} in order {order['id']} has no SKU - will be skipped")

        # Validar total del pedido
        total_price = order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount")
        if not total_price or float(total_price) <= 0:
            raise ValidationException(
                message="Order total must be greater than zero",
                field="totalPriceSet.shopMoney.amount",
                invalid_value=total_price,
            )

        # Validar estado financiero (debe estar pagado para sincronizar)
        financial_status = order.get("displayFinancialStatus", "").upper()
        valid_financial_statuses = ["PAID", "PARTIALLY_PAID", "AUTHORIZED"]
        
        if financial_status not in valid_financial_statuses:
            raise ValidationException(
                message=f"Order financial status '{financial_status}' not valid for sync. Must be one of: {valid_financial_statuses}",
                field="displayFinancialStatus",
                invalid_value=financial_status,
            )

        logger.info(f"Order {order['id']} validation passed - {len(line_items)} items, total: {total_price}")
        return order

    async def _convert_to_rms_format(self, shopify_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte un pedido de Shopify al formato RMS.

        Args:
            shopify_order: Pedido de Shopify

        Returns:
            Dict: Pedido en formato RMS con ORDER y ORDERENTRY data
        """
        from datetime import datetime
        from decimal import Decimal
        
        # Extraer datos básicos
        total_amount = Decimal(shopify_order["totalPriceSet"]["shopMoney"]["amount"])
        tax_amount = Decimal(shopify_order.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", "0"))
        order_date = datetime.fromisoformat(shopify_order["createdAt"].replace("Z", "+00:00"))
        
        # Mapear datos de cabecera del pedido (tabla ORDER)
        order_data = {
            "store_id": 40,  # Tienda virtual
            "time": order_date,
            "type": 1,  # Venta normal
            "total": total_amount,
            "tax": tax_amount,
            "deposit": Decimal("0.00"),
            "shopify_order_id": shopify_order["id"],
            "shopify_order_number": shopify_order["name"].replace("#", ""),
            "customer_email": shopify_order.get("email"),
            "comment": f"Shopify Order {shopify_order['name']} - {shopify_order.get('displayFinancialStatus', '')}",
        }
        
        # Procesar cliente (crear si no existe)
        customer_data = shopify_order.get("customer")
        if customer_data:
            customer_id = await self._resolve_customer(customer_data, shopify_order.get("billingAddress"))
            order_data["customer_id"] = customer_id
        
        # Procesar líneas de pedido (tabla ORDERENTRY)
        line_items_data = []
        
        # Manejar formato GraphQL de line items (edges/node structure)
        line_items_raw = shopify_order.get("lineItems", {})
        if isinstance(line_items_raw, dict) and "edges" in line_items_raw:
            # GraphQL format: lineItems.edges[].node
            line_items = [edge["node"] for edge in line_items_raw["edges"]]
        else:
            # Formato simple (lista directa)
            line_items = line_items_raw if isinstance(line_items_raw, list) else []
        
        for item in line_items:
            # Verificar SKU (priorizar variant.sku sobre item.sku)
            item_sku = item.get("variant", {}).get("sku") or item.get("sku")
            
            # Para testing: usar variant ID como fallback si no hay SKU
            if not item_sku or item_sku.strip() == "":
                variant_id = item.get("variant", {}).get("id", "")
                if variant_id:
                    # Extraer ID numerico del GID
                    variant_id_num = variant_id.split("/")[-1] if "/" in variant_id else variant_id
                    item_sku = f"VAR-{variant_id_num}"
                    logger.info(f"Using variant ID as SKU fallback: {item_sku} for item {item.get('title', 'Unknown')}")
                else:
                    logger.warning(f"Skipping line item without SKU or variant ID in order {shopify_order['id']}: {item.get('title', 'Unknown item')}")
                    continue
                
            # Resolver SKU a ItemID de RMS
            item_id = await self._resolve_sku_to_item_id(item_sku)
            if not item_id:
                logger.error(f"Could not find RMS ItemID for SKU: {item_sku} in order {shopify_order['id']}")
                continue
            
            # Obtener precios (usar precio con descuento si existe)
            discounted_price_set = item.get("discountedUnitPriceSet", item.get("originalUnitPriceSet"))
            unit_price = Decimal(discounted_price_set["shopMoney"]["amount"])
            original_price = Decimal(item["originalUnitPriceSet"]["shopMoney"]["amount"])
            
            line_item_data = {
                "item_id": item_id,
                "price": unit_price,
                "full_price": original_price,
                "quantity_on_order": float(item["quantity"]),
                "quantity_rtd": 0.0,  # No despachado aún
                "description": item["title"][:255],  # Límite de campo
                "shopify_variant_id": item.get("variant", {}).get("id"),
                "shopify_product_id": item.get("variant", {}).get("product", {}).get("id"),
            }
            
            line_items_data.append(line_item_data)
        
        if not line_items_data:
            raise ValidationException(
                message=f"No valid line items found for order {shopify_order['id']} - all items missing SKU or ItemID mapping",
                field="lineItems",
                invalid_value=shopify_order.get("lineItems", [])
            )
        
        return {
            "order": order_data,
            "line_items": line_items_data,
            "addresses": {
                "billing": self._format_address(shopify_order.get("billingAddress")),
                "shipping": self._format_address(shopify_order.get("shippingAddress")),
            }
        }

    async def _resolve_customer(self, customer_data: Dict[str, Any], billing_address: Optional[Dict[str, Any]]) -> Optional[int]:
        """
        Resuelve o crea un cliente en RMS.

        Args:
            customer_data: Datos del cliente de Shopify
            billing_address: Dirección de facturación

        Returns:
            int: ID del cliente en RMS
        """
        try:
            # Verificar si se permiten pedidos sin cliente
            if not settings.ALLOW_ORDERS_WITHOUT_CUSTOMER:
                if not customer_data or not customer_data.get("email"):
                    raise ValidationException(
                        message="Orders without customer are not allowed",
                        field="customer",
                        invalid_value=customer_data
                    )
            
            # Si hay un customer ID predeterminado para invitados
            if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS and not customer_data:
                logger.info(f"Using default customer ID {settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS} for guest order")
                return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
            
            # Si no hay datos de cliente, permitir NULL
            if not customer_data:
                logger.warning("No customer data provided, creating order with customer_id=NULL")
                return None
            
            email = customer_data.get("email")
            
            # Verificar si se requiere email
            if settings.REQUIRE_CUSTOMER_EMAIL and not email:
                raise ValidationException(
                    message="Customer email is required",
                    field="customer.email",
                    invalid_value=email
                )
            
            # Si no hay email pero se permiten pedidos sin cliente
            if not email:
                if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
                    logger.info(f"Using default customer ID {settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS} for customer without email")
                    return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
                else:
                    logger.warning("Customer has no email, using customer_id=NULL")
                    return None
            
            # Buscar cliente existente por email
            existing_customer = await self.rms_handler.find_customer_by_email(email)
            if existing_customer:
                logger.debug(f"Found existing customer: {existing_customer['id']} for email {email}")
                return existing_customer["id"]
            
            # Crear nuevo cliente
            customer_info = {
                "email": email,
                "first_name": customer_data.get("firstName", ""),
                "last_name": customer_data.get("lastName", ""),
                "phone": customer_data.get("phone", ""),
                "shopify_customer_id": customer_data.get("id"),
            }
            
            # Agregar dirección si existe
            if billing_address:
                customer_info.update({
                    "address1": billing_address.get("address1", ""),
                    "address2": billing_address.get("address2", ""),
                    "city": billing_address.get("city", ""),
                    "province": billing_address.get("province", ""),
                    "country": billing_address.get("country", ""),
                    "zip": billing_address.get("zip", ""),
                })
            
            new_customer_id = await self.rms_handler.create_customer(customer_info)
            logger.info(f"Created new customer: {new_customer_id} for email {email}")
            return new_customer_id
            
        except Exception as e:
            logger.error(f"Error resolving customer: {e}")
            
            # Si se permite, usar customer_id=NULL como fallback
            if settings.ALLOW_ORDERS_WITHOUT_CUSTOMER:
                if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
                    return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
                return None
            else:
                # Re-raise si no se permiten pedidos sin cliente
                raise

    async def _resolve_sku_to_item_id(self, sku: str) -> Optional[int]:
        """
        Resuelve un SKU de Shopify al ItemID correspondiente en RMS.

        Args:
            sku: SKU del producto

        Returns:
            int: ItemID de RMS o None si no se encuentra
        """
        try:
            # Buscar en la vista View_Items por c_articulo (SKU)
            item = await self.rms_handler.find_item_by_sku(sku)
            if item:
                logger.debug(f"Found RMS ItemID {item['item_id']} for SKU {sku}")
                return item["item_id"]
            
            logger.warning(f"No RMS ItemID found for SKU: {sku}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving SKU {sku} to ItemID: {e}")
            return None

    def _format_address(self, address: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Formatea una dirección para RMS.

        Args:
            address: Dirección de Shopify

        Returns:
            Dict: Dirección formateada para RMS
        """
        if not address:
            return None

        return {
            "FirstName": address.get("first_name"),
            "LastName": address.get("last_name"),
            "Company": address.get("company"),
            "Address1": address.get("address1"),
            "Address2": address.get("address2"),
            "City": address.get("city"),
            "Province": address.get("province"),
            "PostalCode": address.get("zip"),
            "Country": address.get("country"),
            "Phone": address.get("phone"),
        }

    async def _create_rms_order(self, rms_order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una nueva orden en RMS.

        Args:
            rms_order_data: Datos de la orden en formato RMS

        Returns:
            Dict: Resultado de la creación
        """
        try:
            from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry
            
            # Crear la orden principal (tabla ORDER)
            order_model = RMSOrder(**rms_order_data["order"])
            order_id = await self.rms_handler.create_order(order_model.model_dump())
            
            logger.info(f"Created RMS order {order_id} for Shopify order {rms_order_data['order']['shopify_order_id']}")
            
            # Crear las líneas de la orden (tabla ORDERENTRY)
            created_entries = []
            for line_item in rms_order_data["line_items"]:
                line_item["order_id"] = order_id
                entry_model = RMSOrderEntry(**line_item)
                entry_id = await self.rms_handler.create_order_entry(entry_model.model_dump())
                created_entries.append({"id": entry_id, **line_item})
                
                logger.debug(f"Created order entry {entry_id} for item {line_item['item_id']}")
            
            # Validar inventario y actualizar existencias
            await self._validate_and_update_inventory(created_entries)
            
            # Crear registro de historial
            await self._create_order_history(order_id, "ORDER_CREATED", "Order created from Shopify")
            
            logger.info(f"Successfully created RMS order {order_id} with {len(created_entries)} line items")
            
            return {
                "order_id": order_id,
                "line_items_count": len(created_entries),
                "total_amount": rms_order_data["order"]["total"],
            }
            
        except Exception as e:
            logger.error(f"Error creating RMS order: {e}")
            raise SyncException(
                message=f"Failed to create RMS order: {str(e)}",
                service="shopify_to_rms",
                operation="create_order",
            ) from e

    async def _update_rms_order(self, existing_order: Dict[str, Any], rms_order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza una orden existente en RMS.

        Args:
            existing_order: Orden existente en RMS
            rms_order_data: Nuevos datos de la orden

        Returns:
            Dict: Resultado de la actualización
        """
        try:
            order_id = existing_order["id"]
            logger.info(f"Updating existing RMS order {order_id}")
            
            # Actualizar la orden principal si hay cambios
            updated_order = await self.rms_handler.update_order(order_id, rms_order_data["order"])
            logger.debug(f"Updated order {updated_order['id']} with new data")
            
            # Sincronizar líneas de la orden (agregar/actualizar/eliminar según sea necesario)
            await self._sync_order_entries(order_id, rms_order_data["line_items"])
            
            # Crear registro de historial
            await self._create_order_history(order_id, "ORDER_UPDATED", "Order updated from Shopify")
            
            logger.info(f"Successfully updated RMS order {order_id}")
            
            return {
                "order_id": order_id,
                "action": "updated",
                "total_amount": rms_order_data["order"]["total"],
            }
            
        except Exception as e:
            logger.error(f"Error updating RMS order {existing_order['id']}: {e}")
            raise SyncException(
                message=f"Failed to update RMS order: {str(e)}",
                service="shopify_to_rms",
                operation="update_order",
            ) from e

    async def _validate_and_update_inventory(self, order_entries: List[Dict[str, Any]]) -> None:
        """
        Valida existencias y actualiza inventario en RMS.

        Args:
            order_entries: Lista de entradas de la orden
        """
        try:
            for entry in order_entries:
                item_id = entry["item_id"]
                quantity_ordered = entry["quantity_on_order"]
                
                # Verificar stock disponible
                current_stock = await self.rms_handler.get_item_stock(item_id)
                if current_stock is None:
                    logger.warning(f"Could not get stock for item {item_id}")
                    continue
                
                if current_stock < quantity_ordered:
                    logger.warning(
                        f"Insufficient stock for item {item_id}: "
                        f"ordered {quantity_ordered}, available {current_stock}"
                    )
                    # No bloquear la orden, solo registrar warning
                    # En producción podrías decidir si bloquear o permitir oversell
                
                # Actualizar stock (restar cantidad ordenada)
                await self.rms_handler.update_item_stock(item_id, -quantity_ordered)
                logger.debug(f"Updated stock for item {item_id}: -{quantity_ordered}")
                
        except Exception as e:
            logger.error(f"Error validating/updating inventory: {e}")
            # No re-raise para no bloquear la creación de la orden
            # El inventario se puede ajustar manualmente después

    async def _sync_order_entries(self, order_id: int, new_line_items: List[Dict[str, Any]]) -> None:
        """
        Sincroniza las líneas de una orden existente.

        Args:
            order_id: ID de la orden en RMS
            new_line_items: Nuevas líneas de la orden
        """
        try:
            # Obtener líneas existentes
            existing_entries = await self.rms_handler.get_order_entries(order_id)
            existing_items = {entry["item_id"]: entry for entry in existing_entries}
            
            # Procesar nuevas líneas
            for line_item in new_line_items:
                line_item["order_id"] = order_id
                item_id = line_item["item_id"]
                
                if item_id in existing_items:
                    # Actualizar línea existente
                    entry_id = existing_items[item_id]["id"]
                    await self.rms_handler.update_order_entry(entry_id, line_item)
                    logger.debug(f"Updated order entry {entry_id} for item {item_id}")
                else:
                    # Crear nueva línea
                    from app.api.v1.schemas.rms_schemas import RMSOrderEntry
                    entry_model = RMSOrderEntry(**line_item)
                    await self.rms_handler.create_order_entry(entry_model.model_dump())
                    logger.debug(f"Created new order entry for item {item_id}")
                    
        except Exception as e:
            logger.error(f"Error syncing order entries for order {order_id}: {e}")
            raise

    async def _create_order_history(self, order_id: int, action: str, comment: str) -> None:
        """
        Crea un registro en el historial de la orden.

        Args:
            order_id: ID de la orden
            action: Acción realizada
            comment: Comentario descriptivo
        """
        try:
            from datetime import datetime

            from app.api.v1.schemas.rms_schemas import RMSOrderHistory
            
            history_data = {
                "order_id": order_id,
                "date": datetime.now(),
                "comment": f"{action}: {comment}",
                "batch_number": self.sync_id,
            }
            
            history_model = RMSOrderHistory(**history_data)
            await self.rms_handler.create_order_history(history_model.model_dump())
            logger.debug(f"Created order history: {action} for order {order_id}")
            
        except Exception as e:
            logger.error(f"Error creating order history: {e}")
            # No re-raise para no bloquear el procesamiento principal

    def _generate_sync_report(self, stats: Dict[str, Any], duration: float) -> Dict[str, Any]:
        """
        Genera reporte final de sincronización.

        Args:
            stats: Estadísticas de la sincronización
            duration: Duración en segundos

        Returns:
            Dict: Reporte completo
        """
        error_summary = self.error_aggregator.get_summary()

        report = {
            "sync_id": self.sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": stats,
            "errors": error_summary,
            "duration_seconds": duration,
            "success_rate": ((stats["processed"] - stats["errors"]) / max(stats["total_orders"], 1) * 100),
        }

        logger.info(f"Shopify to RMS sync completed - ID: {self.sync_id} - Success rate: {report['success_rate']:.1f}%")

        return report


# Funciones de conveniencia para la API
async def sync_shopify_to_rms(
    order_ids: List[str],
    skip_validation: bool = False,
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronizar pedidos de Shopify a RMS.

    Args:
        order_ids: Lista de IDs de pedidos
        skip_validation: Omitir validaciones

    Returns:
        Dict: Resultado de la sincronización
    """
    sync_service = ShopifyToRMSSync()
    return await sync_service.sync_orders(order_ids, skip_validation)


async def get_shopify_sync_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual de las sincronizaciones de Shopify.

    Returns:
        Dict: Estado de sincronización
    """
    # TODO: Implementar cuando tengamos un sistema de gestión de estado
    return {
        "status": "idle",
        "active_syncs": [],
        "last_sync": None,
    }
