"""
Order Polling Client for Shopify GraphQL API.

This module provides specialized client functionality for polling recent orders
from Shopify as an alternative/complement to webhooks. Optimized for periodic
polling with efficient GraphQL queries and cursor-based pagination.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.utils.error_handler import ShopifyAPIException

from .base_client import BaseShopifyGraphQLClient

logger = logging.getLogger(__name__)
settings = get_settings()


# Optimized GraphQL query for polling recent orders
POLL_ORDERS_QUERY = """
query PollRecentOrders($first: Int!, $after: String, $query: String!) {
  orders(
    first: $first
    after: $after
    query: $query
    sortKey: UPDATED_AT
    reverse: true
  ) {
    edges {
      node {
        id
        legacyResourceId
        name
        createdAt
        updatedAt
        email
        phone
        displayFinancialStatus
        displayFulfillmentStatus
        test
        confirmed
        closed
        cancelledAt
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
          legacyResourceId
          email
          firstName
          lastName
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
        lineItems(first: 250) {
          edges {
            node {
              id
              title
              quantity
              sku
              vendor
              variantTitle
              variant {
                id
                legacyResourceId
                sku
                title
                price
                product {
                  id
                  legacyResourceId
                  title
                  handle
                }
              }
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
              originalTotalSet {
                shopMoney {
                  amount
                  currencyCode
                }
              }
              discountedTotalSet {
                shopMoney {
                  amount
                  currencyCode
                }
              }
              taxLines {
                title
                priceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                rate
                ratePercentage
              }
            }
          }
        }
        shippingLine {
          title
          code
          originalPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
          discountedPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
        }
        note
        tags
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


class OrderPollingClient(BaseShopifyGraphQLClient):
    """
    Specialized client for polling recent orders from Shopify.

    This client is optimized for periodic polling operations as an alternative
    to webhooks. It provides efficient GraphQL queries with cursor pagination
    and filtering capabilities.
    """

    def __init__(self):
        """Initialize the order polling client."""
        super().__init__()
        logger.info("OrderPollingClient initialized")

    async def fetch_recent_orders(
        self,
        lookback_minutes: int | None = None,
        financial_statuses: list[str] | None = None,
        fulfillment_statuses: list[str] | None = None,
        batch_size: int = 50,
        max_pages: int = 10,
        include_test_orders: bool = False,
    ) -> dict[str, Any]:
        """
        Fetch recent orders with filtering and pagination.

        Args:
            lookback_minutes: Minutes to look back from now (default from config)
            financial_statuses: Filter by financial status (PAID, AUTHORIZED, etc.)
            fulfillment_statuses: Filter by fulfillment status (UNFULFILLED, FULFILLED, etc.)
            batch_size: Orders per page (max 250)
            max_pages: Maximum pages to fetch
            include_test_orders: Include test orders

        Returns:
            Dict containing:
                - orders: List of order dicts
                - total_fetched: Total orders retrieved
                - has_more: Boolean indicating if more orders exist
                - last_cursor: Pagination cursor for next fetch

        Raises:
            ShopifyAPIException: If query fails
        """
        try:
            # Use config defaults if not specified
            if lookback_minutes is None:
                lookback_minutes = settings.ORDER_POLLING_LOOKBACK_MINUTES

            if financial_statuses is None:
                # Use configured allowed financial statuses (parsed to list by validator)
                statuses = settings.ALLOWED_ORDER_FINANCIAL_STATUSES
                financial_statuses = [statuses] if isinstance(statuses, str) else statuses

            # Build query filter
            query_filter = self._build_query_filter(
                lookback_minutes=lookback_minutes,
                financial_statuses=financial_statuses,
                fulfillment_statuses=fulfillment_statuses,
                include_test_orders=include_test_orders,
            )

            logger.info(
                f"📊 Polling orders: lookback={lookback_minutes}m, "
                f"financial_statuses={financial_statuses}, "
                f"batch_size={batch_size}, max_pages={max_pages}"
            )
            logger.debug(f"Query filter: {query_filter}")

            # Fetch orders with pagination
            all_orders = []
            cursor = None
            pages_fetched = 0
            has_more = False

            while pages_fetched < max_pages:
                variables = {
                    "first": min(batch_size, 250),  # Shopify max is 250
                    "query": query_filter,
                }

                if cursor:
                    variables["after"] = cursor

                # Execute GraphQL query
                result = await self._execute_query(POLL_ORDERS_QUERY, variables)

                # Extract orders from response
                orders_data = result.get("orders", {})
                edges = orders_data.get("edges", [])
                page_info = orders_data.get("pageInfo", {})

                if not edges:
                    logger.info("No more orders found")
                    break

                # Extract and flatten order nodes
                orders_batch = [edge["node"] for edge in edges]
                all_orders.extend(orders_batch)

                pages_fetched += 1
                logger.info(f"✅ Fetched page {pages_fetched}/{max_pages}: {len(orders_batch)} orders")

                # Check if more pages exist
                has_more = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

                if not has_more:
                    logger.info("No more pages available")
                    break

            # Summary
            logger.info(f"📦 Polling complete: {len(all_orders)} orders fetched " f"across {pages_fetched} pages")

            return {
                "orders": all_orders,
                "total_fetched": len(all_orders),
                "has_more": has_more,
                "last_cursor": cursor,
                "pages_fetched": pages_fetched,
            }

        except Exception as e:
            logger.error(f"❌ Error polling orders: {e}")
            raise ShopifyAPIException(f"Failed to poll orders: {str(e)}") from e

    def _build_query_filter(
        self,
        lookback_minutes: int,
        financial_statuses: list[str] | None = None,
        fulfillment_statuses: list[str] | None = None,
        include_test_orders: bool = False,
    ) -> str:
        """
        Build Shopify query filter string for order polling.

        Args:
            lookback_minutes: Minutes to look back
            financial_statuses: Financial status filters
            fulfillment_statuses: Fulfillment status filters
            include_test_orders: Include test orders

        Returns:
            Query filter string for Shopify API
        """
        filters = []

        # Date filter (updated_at >= X minutes ago)
        # Using updated_at captures both new AND edited orders
        cutoff_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)
        # Shopify expects ISO 8601 format with timezone (+00:00 with colons)
        cutoff_str = cutoff_time.isoformat()
        filters.append(f"updated_at:>='{cutoff_str}'")

        # Financial status filter
        if financial_statuses:
            status_conditions = " OR ".join([f"financial_status:{status}" for status in financial_statuses])
            if len(financial_statuses) > 1:
                filters.append(f"({status_conditions})")
            else:
                filters.append(status_conditions)

        # Fulfillment status filter
        if fulfillment_statuses:
            fulfillment_conditions = " OR ".join([f"fulfillment_status:{status}" for status in fulfillment_statuses])
            if len(fulfillment_statuses) > 1:
                filters.append(f"({fulfillment_conditions})")
            else:
                filters.append(fulfillment_conditions)

        # Test orders filter (exclude by default)
        if not include_test_orders:
            filters.append("test:false")

        # Combine all filters with AND
        query = " AND ".join(filters)

        return query

    async def fetch_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        """
        Fetch a single order by Shopify ID.

        Args:
            order_id: Shopify order ID (format: gid://shopify/Order/...)

        Returns:
            Order dict or None if not found

        Raises:
            ShopifyAPIException: If query fails
        """
        try:
            # Simple query for single order
            query = """
            query GetOrderById($id: ID!) {
              order(id: $id) {
                id
                legacyResourceId
                name
                createdAt
                email
                displayFinancialStatus
                displayFulfillmentStatus
              }
            }
            """

            variables = {"id": order_id}
            result = await self._execute_query(query, variables)

            order = result.get("order")
            if order:
                logger.info(f"✅ Fetched order {order.get('name')} (ID: {order_id})")
            else:
                logger.warning(f"⚠️ Order not found: {order_id}")

            return order

        except Exception as e:
            logger.error(f"❌ Error fetching order {order_id}: {e}")
            raise ShopifyAPIException(f"Failed to fetch order {order_id}: {str(e)}") from e

    async def get_order_count(self, lookback_minutes: int | None = None) -> dict[str, Any]:
        """
        Get count of recent orders for estimation/monitoring.

        Args:
            lookback_minutes: Minutes to look back (default from config)

        Returns:
            Dict with order count and date range info

        Raises:
            ShopifyAPIException: If query fails
        """
        try:
            if lookback_minutes is None:
                lookback_minutes = settings.ORDER_POLLING_LOOKBACK_MINUTES

            # Build query filter (reuse existing method)
            query_filter = self._build_query_filter(
                lookback_minutes=lookback_minutes,
                financial_statuses=None,  # Count all statuses
                fulfillment_statuses=None,
                include_test_orders=False,
            )

            # Simplified query for counting
            count_query = """
            query CountOrders($query: String!) {
              orders(first: 1, query: $query) {
                edges {
                  node {
                    id
                  }
                }
                pageInfo {
                  hasNextPage
                }
              }
            }
            """

            variables = {"query": query_filter}
            result = await self._execute_query(count_query, variables)

            orders_data = result.get("orders", {})
            has_orders = len(orders_data.get("edges", [])) > 0
            has_more = orders_data.get("pageInfo", {}).get("hasNextPage", False)

            cutoff_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

            return {
                "has_orders": has_orders,
                "has_multiple_pages": has_more,
                "lookback_minutes": lookback_minutes,
                "cutoff_time": cutoff_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Error counting orders: {e}")
            raise ShopifyAPIException(f"Failed to count orders: {str(e)}") from e

    def __str__(self):
        """String representation."""
        return f"OrderPollingClient(shop={self.shop_url})"

    def __repr__(self):
        """Detailed string representation."""
        return (
            f"OrderPollingClient("
            f"shop_url='{self.shop_url}', "
            f"api_version='{self.api_version}', "
            f"initialized={self.session is not None})"
        )
