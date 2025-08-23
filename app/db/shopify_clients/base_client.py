"""
Base Shopify GraphQL client with common functionality.

This module provides the foundation for all Shopify GraphQL clients,
including connection management, rate limiting, and basic query execution.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientTimeout

from app.core.config import get_settings
from app.utils.error_handler import ShopifyAPIException

logger = logging.getLogger(__name__)


class BaseShopifyGraphQLClient:
    """
    Base client for Shopify GraphQL API operations.

    Provides common functionality like connection management, rate limiting,
    error handling, and basic query execution that all specialized clients inherit.
    """

    def __init__(self):
        """Initialize the base Shopify GraphQL client."""
        self.settings = get_settings()
        self.shop_url = self.settings.SHOPIFY_SHOP_URL
        self.access_token = self.settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = self.settings.SHOPIFY_API_VERSION

        # Build GraphQL endpoint URL
        if not self.shop_url.startswith(("http://", "https://")):
            self.shop_url = f"https://{self.shop_url}"

        self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"

        # Session and rate limiting
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0
        self._min_request_interval = 0.5  # 500ms between requests for rate limiting

        logger.info(f"Initialized Shopify GraphQL client for {self.shop_url}")

    async def initialize(self):
        """
        Initialize the HTTP session and test the connection.

        Raises:
            ShopifyAPIException: If initialization fails
        """
        try:
            # Create HTTP session
            timeout = ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self.access_token,
                    "User-Agent": f"RMS-Shopify-Integration/{self.api_version}",
                },
            )

            # Test connection
            await self.test_connection()
            logger.info("✅ Shopify GraphQL client initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Shopify GraphQL client: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            raise ShopifyAPIException(f"Client initialization failed: {str(e)}") from e

    async def close(self):
        """Close the HTTP session and clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Shopify GraphQL client closed")

    async def _execute_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None, max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query with rate limiting and error handling.

        Args:
            query: GraphQL query string
            variables: Query variables
            max_retries: Maximum number of retry attempts

        Returns:
            Dict: Query response data

        Raises:
            ShopifyAPIException: If the query fails after retries
        """
        if not self.session:
            raise ShopifyAPIException("Client not initialized. Call initialize() first.")

        # Apply rate limiting
        await self._check_rate_limit()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        last_exception = None

        for attempt in range(max_retries):
            try:
                async with self.session.post(self.graphql_url, json=payload) as response:
                    self._last_request_time = time.time()

                    if response.status == 429:
                        # Rate limit exceeded
                        retry_after = int(response.headers.get("Retry-After", 2))
                        logger.warning(f"Rate limit exceeded, waiting {retry_after}s (attempt {attempt + 1})")
                        await asyncio.sleep(retry_after)
                        continue

                    response_data = await response.json()

                    if response.status != 200:
                        raise ShopifyAPIException(
                            f"HTTP {response.status}: {response_data.get('error', 'Unknown error')}"
                        )

                    # Check for GraphQL errors
                    if "errors" in response_data:
                        errors = response_data["errors"]
                        error_messages = [err.get("message", str(err)) for err in errors]
                        raise ShopifyAPIException(f"GraphQL errors: {', '.join(error_messages)}")

                    return response_data.get("data", {})

            except aiohttp.ClientError as e:
                last_exception = ShopifyAPIException(f"Network error: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 10)  # Exponential backoff, max 10s
                    logger.warning(f"Network error, retrying in {wait_time}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                    continue

            except Exception as e:
                last_exception = ShopifyAPIException(f"Unexpected error: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 10)
                    logger.warning(f"Error executing query, retrying in {wait_time}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                    continue

        # All retries failed
        raise last_exception or ShopifyAPIException("Query execution failed after retries")

    async def _execute_single_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a single GraphQL query without retries (for simple operations).

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Dict: Query response data
        """
        return await self._execute_query(query, variables, max_retries=1)

    async def _check_rate_limit(self):
        """
        Implement basic rate limiting to avoid overwhelming Shopify's API.
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            await asyncio.sleep(sleep_time)

    async def test_connection(self) -> bool:
        """
        Test the connection to Shopify GraphQL API.

        Returns:
            bool: True if connection is successful

        Raises:
            ShopifyAPIException: If connection test fails
        """
        test_query = """
        query {
          shop {
            name
            id
            currencyCode
          }
        }
        """

        try:
            result = await self._execute_single_query(test_query)
            shop_info = result.get("shop", {})
            shop_name = shop_info.get("name", "Unknown")
            currency = shop_info.get("currencyCode", "Unknown")

            logger.info(f"✅ Connected to Shopify store: {shop_name} ({currency})")
            return True

        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            raise ShopifyAPIException(f"Connection test failed: {str(e)}") from e

    def _handle_graphql_errors(self, response_data: Dict[str, Any], operation: str = "operation"):
        """
        Handle GraphQL errors consistently across all clients.

        Args:
            response_data: GraphQL response
            operation: Operation name for error context

        Raises:
            ShopifyAPIException: If there are user errors or GraphQL errors
        """
        # Check for user errors (business logic errors)
        if "userErrors" in response_data and response_data["userErrors"]:
            user_errors = response_data["userErrors"]
            error_messages = []
            for error in user_errors:
                field = error.get("field", [])
                message = error.get("message", "Unknown error")
                field_str = ".".join(field) if field else "general"
                error_messages.append(f"{field_str}: {message}")

            raise ShopifyAPIException(f"{operation} failed: {', '.join(error_messages)}")

        # Check for general GraphQL errors
        if "errors" in response_data and response_data["errors"]:
            errors = response_data["errors"]
            error_messages = [err.get("message", str(err)) for err in errors]
            raise ShopifyAPIException(f"{operation} GraphQL errors: {', '.join(error_messages)}")

    async def get_locations(self) -> List[Dict[str, Any]]:
        """
        Get all locations for the shop.

        Returns:
            List of location dictionaries
        """
        from app.db.queries import LOCATIONS_QUERY

        try:
            result = await self._execute_query(LOCATIONS_QUERY)
            locations = result.get("locations", {}).get("edges", [])
            return [edge["node"] for edge in locations]

        except Exception as e:
            logger.error(f"Error fetching locations: {e}")
            raise ShopifyAPIException(f"Failed to fetch locations: {str(e)}") from e

    async def get_primary_location_id(self, preferred_location_name: Optional[str] = None) -> Optional[str]:
        """
        Get the primary location ID for inventory management.

        Args:
            preferred_location_name: Name of preferred location (optional)

        Returns:
            Primary location ID or None if not found
        """
        try:
            locations = await self.get_locations()

            if not locations:
                logger.warning("No locations found in Shopify")
                return None

            # Try to find preferred location by name
            if preferred_location_name:
                for location in locations:
                    if location.get("name", "").lower() == preferred_location_name.lower():
                        location_id = location.get("id")
                        logger.info(f"Found preferred location '{preferred_location_name}': {location_id}")
                        return location_id

            # Find primary location (fulfills orders)
            for location in locations:
                if location.get("fulfillsOnlineOrders", False):
                    location_id = location.get("id")
                    location_name = location.get("name", "Unknown")
                    logger.info(f"Found primary location: {location_name} ({location_id})")
                    return location_id

            # Fallback to first active location
            for location in locations:
                if location.get("active", False):
                    location_id = location.get("id")
                    location_name = location.get("name", "Unknown")
                    logger.info(f"Using first active location: {location_name} ({location_id})")
                    return location_id

            # Last resort: first location
            if locations:
                location_id = locations[0].get("id")
                location_name = locations[0].get("name", "Unknown")
                logger.warning(f"Using first available location: {location_name} ({location_id})")
                return location_id

            logger.error("No suitable location found")
            return None

        except Exception as e:
            logger.error(f"Error getting primary location: {e}")
            return None

    def __str__(self):
        """String representation of the client."""
        return f"BaseShopifyGraphQLClient(shop={self.shop_url}, api_version={self.api_version})"

    def __repr__(self):
        """Detailed string representation of the client."""
        return (
            f"BaseShopifyGraphQLClient("
            f"shop_url='{self.shop_url}', "
            f"api_version='{self.api_version}', "
            f"initialized={self.session is not None})"
        )

