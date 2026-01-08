"""
Shopify GraphQL Client para integración RMS-Shopify.

Este módulo proporciona compatibilidad hacia atrás importando el cliente unificado
de la nueva estructura modular.

DEPRECATED: Use app.db.shopify_clients.ShopifyGraphQLClient directly for new code.
"""

import logging

# Import the new unified client for backward compatibility
from app.db.shopify_clients import ShopifyGraphQLClient

logger = logging.getLogger(__name__)

# For backward compatibility, expose the client at module level
__all__ = ["ShopifyGraphQLClient"]

logger.info("Loading Shopify GraphQL client with new modular structure")
