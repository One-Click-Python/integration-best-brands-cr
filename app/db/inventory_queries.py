"""
Inventory and location-related GraphQL queries and mutations for Shopify API.

This module contains all inventory management and location-specific GraphQL queries
and mutations extracted from the main shopify_graphql_queries.py file for better
organization and maintainability.
"""

# Inventory Mutations
INVENTORY_ACTIVATE_MUTATION = """
mutation ActivateInventory($inventoryItemId: ID!, $locationId: ID!) {
  inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
    inventoryLevel {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Enable inventory tracking for an inventory item
INVENTORY_ITEM_UPDATE_MUTATION = """
mutation UpdateInventoryItem($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      tracked
    }
    userErrors {
      field
      message
    }
  }
}
"""

INVENTORY_ADJUST_MUTATION = """
mutation AdjustInventory($input: InventoryAdjustQuantityInput!) {
  inventoryAdjustQuantity(input: $input) {
    inventoryLevel {
      id
      available
    }
    userErrors {
      field
      message
    }
  }
}
"""

INVENTORY_SET_MUTATION = """
mutation SetInventory($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup {
      reason
      referenceDocumentUri
      changes {
        name
        delta
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

INVENTORY_ADJUST_QUANTITIES_MUTATION = """
mutation InventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      reason
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Location Queries
LOCATIONS_QUERY = """
query GetLocations {
  locations(first: 10) {
    edges {
      node {
        id
        name
        isActive
        address {
          address1
          address2
          city
          country
          province
        }
      }
    }
  }
}
"""