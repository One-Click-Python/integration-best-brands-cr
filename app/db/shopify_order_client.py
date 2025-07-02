"""
Cliente GraphQL especializado para operaciones de órdenes con Shopify.

Este módulo maneja todas las operaciones relacionadas con pedidos de Shopify,
incluyendo obtención, actualización de estado y manejo de fulfillments.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.utils.error_handler import ShopifyAPIException

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyOrderClient:
    """
    Cliente especializado para operaciones de órdenes con la API GraphQL de Shopify.
    """

    def __init__(self, graphql_client):
        """
        Inicializa el cliente de órdenes.

        Args:
            graphql_client: Instancia del cliente GraphQL base
        """
        self.client = graphql_client
        logger.info("ShopifyOrderClient initialized")

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene una orden específica por ID con todos sus detalles.

        Args:
            order_id: ID de la orden en Shopify (formato: gid://shopify/Order/...)

        Returns:
            Dict: Datos completos de la orden o None si no se encuentra
        """
        try:
            query = """
            query GetOrder($id: ID!) {
              order(id: $id) {
                id
                name
                createdAt
                updatedAt
                cancelledAt
                closedAt
                processedAt
                email
                phone
                note
                tags
                test
                displayFinancialStatus
                displayFulfillmentStatus
                returnStatus
                totalPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                subtotalPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalTaxSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalShippingPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalDiscountsSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                customer {
                  id
                  email
                  firstName
                  lastName
                  phone
                  acceptsMarketing
                  defaultAddress {
                    address1
                    address2
                    city
                    province
                    country
                    zip
                    phone
                  }
                }
                billingAddress {
                  firstName
                  lastName
                  company
                  address1
                  address2
                  city
                  province
                  country
                  zip
                  phone
                }
                shippingAddress {
                  firstName
                  lastName
                  company
                  address1
                  address2
                  city
                  province
                  country
                  zip
                  phone
                }
                lineItems(first: 250) {
                  edges {
                    node {
                      id
                      title
                      quantity
                      sku
                      vendor
                      requiresShipping
                      taxable
                      originalUnitPriceSet {
                        shopMoney {
                          amount
                          currencyCode
                        }
                      }
                      discountedUnitPriceSet {
                        shopMoney {
                          amount
                          currencyCode
                        }
                      }
                      variant {
                        id
                        sku
                        title
                        price
                        inventoryQuantity
                        product {
                          id
                          title
                        }
                      }
                    }
                  }
                }
                fulfillments {
                  id
                  status
                  createdAt
                  updatedAt
                  trackingCompany
                  trackingNumber
                  trackingUrl
                  fulfillmentLineItems(first: 250) {
                    edges {
                      node {
                        id
                        quantity
                        lineItem {
                          id
                          sku
                        }
                      }
                    }
                  }
                }
                transactions {
                  id
                  kind
                  status
                  test
                  processedAt
                  amountSet {
                    shopMoney {
                      amount
                      currencyCode
                    }
                  }
                  gateway
                }
              }
            }
            """
            
            variables = {"id": order_id}
            result = await self.client._execute_query(query, variables)

            order = result.get("order")
            if order:
                logger.info(f"Found order {order_id}: {order.get('name')} - Status: {order.get('displayFinancialStatus')}")
                return order
            
            logger.warning(f"Order {order_id} not found")
            return None

        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            raise ShopifyAPIException(f"Failed to get order {order_id}: {str(e)}")

    async def get_orders(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        financial_status: Optional[str] = None,
        fulfillment_status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        updated_at_min: Optional[datetime] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene una lista de órdenes con filtros opcionales.

        Args:
            limit: Número máximo de órdenes por página (max 250)
            cursor: Cursor para paginación
            status: Estado de la orden (open, closed, cancelled, any)
            financial_status: Estado financiero (paid, pending, refunded, etc)
            fulfillment_status: Estado de fulfillment (unfulfilled, partial, fulfilled)
            created_at_min: Fecha mínima de creación
            updated_at_min: Fecha mínima de actualización
            tag: Tag específico para filtrar

        Returns:
            Dict con órdenes y información de paginación
        """
        try:
            from .shopify_graphql_queries import ORDERS_QUERY
            
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            # Construir query filter
            query_parts = []
            
            if status:
                query_parts.append(f"status:{status}")
            if financial_status:
                query_parts.append(f"financial_status:{financial_status}")
            if fulfillment_status:
                query_parts.append(f"fulfillment_status:{fulfillment_status}")
            if created_at_min:
                query_parts.append(f"created_at:>={created_at_min.isoformat()}")
            if updated_at_min:
                query_parts.append(f"updated_at:>={updated_at_min.isoformat()}")
            if tag:
                query_parts.append(f"tag:{tag}")

            if query_parts:
                variables["query"] = " AND ".join(query_parts)

            result = await self.client._execute_query(ORDERS_QUERY, variables)

            orders = []
            for edge in result.get("orders", {}).get("edges", []):
                orders.append(edge.get("node"))

            page_info = result.get("orders", {}).get("pageInfo", {})
            
            logger.info(f"Retrieved {len(orders)} orders with filters: {query_parts}")

            return {
                "orders": orders,
                "pageInfo": page_info,
                "hasNextPage": page_info.get("hasNextPage", False),
                "endCursor": page_info.get("endCursor"),
            }

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            raise ShopifyAPIException(f"Failed to get orders: {str(e)}")

    async def update_order_tags(self, order_id: str, tags: List[str]) -> Dict[str, Any]:
        """
        Actualiza los tags de una orden.

        Args:
            order_id: ID de la orden
            tags: Lista de tags a asignar

        Returns:
            Dict: Orden actualizada
        """
        try:
            mutation = """
            mutation UpdateOrderTags($input: OrderInput!) {
              orderUpdate(input: $input) {
                order {
                  id
                  tags
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "input": {
                    "id": order_id,
                    "tags": tags
                }
            }
            
            result = await self.client._execute_query(mutation, variables)
            
            update_result = result.get("orderUpdate", {})
            user_errors = update_result.get("userErrors", [])
            
            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Failed to update order tags: {', '.join(error_messages)}")
            
            order = update_result.get("order")
            if order:
                logger.info(f"Updated tags for order {order_id}: {tags}")
                return order
            
            raise ShopifyAPIException("Order tag update failed: No order returned")
            
        except Exception as e:
            logger.error(f"Error updating order tags: {e}")
            raise

    async def create_fulfillment(
        self,
        order_id: str,
        line_items: List[Dict[str, Any]],
        tracking_info: Optional[Dict[str, Any]] = None,
        notify_customer: bool = True,
    ) -> Dict[str, Any]:
        """
        Crea un fulfillment para una orden.

        Args:
            order_id: ID de la orden
            line_items: Lista de items a fulfil con formato [{"id": "lineItemId", "quantity": 1}]
            tracking_info: Información de tracking {"company": "UPS", "number": "123456", "url": "http://..."}
            notify_customer: Si notificar al cliente

        Returns:
            Dict: Fulfillment creado
        """
        try:
            mutation = """
            mutation CreateFulfillment($fulfillment: FulfillmentInput!) {
              fulfillmentCreate(fulfillment: $fulfillment) {
                fulfillment {
                  id
                  status
                  createdAt
                  trackingCompany
                  trackingNumber
                  trackingUrl
                  fulfillmentLineItems(first: 250) {
                    edges {
                      node {
                        id
                        quantity
                      }
                    }
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            fulfillment_data = {
                "orderId": order_id,
                "lineItems": line_items,
                "notifyCustomer": notify_customer
            }
            
            if tracking_info:
                fulfillment_data.update({
                    "trackingCompany": tracking_info.get("company"),
                    "trackingNumber": tracking_info.get("number"),
                    "trackingUrl": tracking_info.get("url")
                })
            
            variables = {"fulfillment": fulfillment_data}
            result = await self.client._execute_query(mutation, variables)
            
            create_result = result.get("fulfillmentCreate", {})
            user_errors = create_result.get("userErrors", [])
            
            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Failed to create fulfillment: {', '.join(error_messages)}")
            
            fulfillment = create_result.get("fulfillment")
            if fulfillment:
                logger.info(f"Created fulfillment {fulfillment['id']} for order {order_id}")
                return fulfillment
            
            raise ShopifyAPIException("Fulfillment creation failed: No fulfillment returned")
            
        except Exception as e:
            logger.error(f"Error creating fulfillment: {e}")
            raise

    async def cancel_order(self, order_id: str, reason: str = "customer", notify_customer: bool = True) -> Dict[str, Any]:
        """
        Cancela una orden.

        Args:
            order_id: ID de la orden
            reason: Razón de cancelación (customer, inventory, fraud, declined, other)
            notify_customer: Si notificar al cliente

        Returns:
            Dict: Orden cancelada
        """
        try:
            mutation = """
            mutation CancelOrder($orderId: ID!, $reason: OrderCancelReason!, $notifyCustomer: Boolean!) {
              orderCancel(orderId: $orderId, reason: $reason, notifyCustomer: $notifyCustomer) {
                order {
                  id
                  name
                  cancelledAt
                  displayFinancialStatus
                  displayFulfillmentStatus
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "orderId": order_id,
                "reason": reason.upper(),
                "notifyCustomer": notify_customer
            }
            
            result = await self.client._execute_query(mutation, variables)
            
            cancel_result = result.get("orderCancel", {})
            user_errors = cancel_result.get("userErrors", [])
            
            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Failed to cancel order: {', '.join(error_messages)}")
            
            order = cancel_result.get("order")
            if order:
                logger.info(f"Cancelled order {order_id} with reason: {reason}")
                return order
            
            raise ShopifyAPIException("Order cancellation failed: No order returned")
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            raise

    async def get_orders_by_customer(self, customer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtiene todas las órdenes de un cliente específico.

        Args:
            customer_id: ID del cliente en Shopify
            limit: Número máximo de órdenes

        Returns:
            List: Lista de órdenes del cliente
        """
        try:
            query = """
            query GetCustomerOrders($customerId: ID!, $first: Int!) {
              customer(id: $customerId) {
                orders(first: $first, sortKey: CREATED_AT, reverse: true) {
                  edges {
                    node {
                      id
                      name
                      createdAt
                      totalPriceSet {
                        shopMoney {
                          amount
                          currencyCode
                        }
                      }
                      displayFinancialStatus
                      displayFulfillmentStatus
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                "customerId": customer_id,
                "first": min(limit, 250)
            }
            
            result = await self.client._execute_query(query, variables)
            
            customer = result.get("customer", {})
            if not customer:
                logger.warning(f"Customer {customer_id} not found")
                return []
            
            orders = []
            for edge in customer.get("orders", {}).get("edges", []):
                orders.append(edge.get("node"))
            
            logger.info(f"Found {len(orders)} orders for customer {customer_id}")
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders for customer {customer_id}: {e}")
            raise ShopifyAPIException(f"Failed to get customer orders: {str(e)}")


# Funciones de conveniencia
async def sync_order_to_rms(order_client: ShopifyOrderClient, order_id: str) -> Dict[str, Any]:
    """
    Sincroniza una orden específica de Shopify a RMS.

    Args:
        order_client: Cliente de órdenes de Shopify
        order_id: ID de la orden a sincronizar

    Returns:
        Dict: Resultado de la sincronización
    """
    from app.services.shopify_to_rms import ShopifyToRMSSync
    
    sync_service = ShopifyToRMSSync()
    result = await sync_service.sync_orders([order_id])
    
    # Marcar la orden como sincronizada con un tag
    if result.get("created", 0) > 0 or result.get("updated", 0) > 0:
        await order_client.update_order_tags(order_id, ["synced-to-rms"])
    
    return result


async def sync_recent_orders(order_client: ShopifyOrderClient, hours: int = 24) -> Dict[str, Any]:
    """
    Sincroniza órdenes recientes de las últimas X horas.

    Args:
        order_client: Cliente de órdenes
        hours: Número de horas hacia atrás

    Returns:
        Dict: Resultado de la sincronización
    """
    from datetime import timedelta, timezone

    from app.services.shopify_to_rms import ShopifyToRMSSync
    
    # Calcular fecha mínima
    min_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Obtener órdenes recientes pagadas
    orders_result = await order_client.get_orders(
        limit=250,
        created_at_min=min_date,
        financial_status="paid"
    )
    
    order_ids = [order["id"] for order in orders_result["orders"]]
    
    if order_ids:
        sync_service = ShopifyToRMSSync()
        return await sync_service.sync_orders(order_ids)
    
    return {
        "total_orders": 0,
        "message": f"No paid orders found in the last {hours} hours"
    }