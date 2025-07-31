"""
Inventory-related GraphQL queries and mutations.

This module contains all inventory management operations:
- Inventory level queries and management
- Inventory item operations
- Location-based inventory tracking
- Bulk inventory operations
- Inventory adjustments and tracking
"""

# =============================================
# INVENTORY LEVEL QUERIES
# =============================================

# Inventory levels query with location details
INVENTORY_LEVELS_QUERY = """
query GetInventoryLevels($first: Int!, $after: String, $query: String) {
  inventoryLevels(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        available
        item {
          id
          sku
          tracked
          requiresShipping
          countryCodeOfOrigin
          provinceCodeOfOrigin
          harmonizedSystemCode
          countryHarmonizedSystemCodes {
            countryCode
            harmonizedSystemCode
          }
          variant {
            id
            title
            price
            product {
              id
              title
              handle
            }
          }
        }
        location {
          id
          name
          address {
            city
            country
          }
        }
        quantities {
          name
          quantity
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# Simple inventory levels query
INVENTORY_LEVELS_SIMPLE_QUERY = """
query GetInventoryLevelsSimple($first: Int!, $locationId: ID) {
  inventoryLevels(first: $first, query: $locationId) {
    edges {
      node {
        id
        available
        item {
          id
          sku
        }
        location {
          id
          name
        }
      }
    }
  }
}
"""

# Inventory level by item and location
INVENTORY_LEVEL_BY_ITEM_QUERY = """
query GetInventoryLevelByItem($inventoryItemId: ID!, $locationId: ID!) {
  inventoryLevel(inventoryItemId: $inventoryItemId, locationId: $locationId) {
    id
    available
    item {
      id
      sku
      tracked
    }
    location {
      id
      name
    }
    quantities {
      name
      quantity
    }
  }
}
"""

# =============================================
# INVENTORY ITEM QUERIES
# =============================================

# Inventory items query
INVENTORY_ITEMS_QUERY = """
query GetInventoryItems($first: Int!, $after: String, $query: String) {
  inventoryItems(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        sku
        tracked
        requiresShipping
        cost
        countryCodeOfOrigin
        provinceCodeOfOrigin
        harmonizedSystemCode
        countryHarmonizedSystemCodes {
          countryCode
          harmonizedSystemCode
        }
        variant {
          id
          title
          price
          weight
          weightUnit
          product {
            id
            title
            handle
            vendor
          }
        }
        inventoryLevels(first: 50) {
          edges {
            node {
              id
              available
              location {
                id
                name
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# Single inventory item query
INVENTORY_ITEM_QUERY = """
query GetInventoryItem($id: ID!) {
  inventoryItem(id: $id) {
    id
    sku
    tracked
    requiresShipping
    cost
    countryCodeOfOrigin
    provinceCodeOfOrigin
    harmonizedSystemCode
    countryHarmonizedSystemCodes {
      countryCode
      harmonizedSystemCode
    }
    variant {
      id
      title
      price
      weight
      weightUnit
      product {
        id
        title
        handle
      }
    }
    inventoryLevels(first: 50) {
      edges {
        node {
          id
          available
          location {
            id
            name
            fulfillsOnlineOrders
          }
          quantities {
            name
            quantity
          }
        }
      }
    }
  }
}
"""

# =============================================
# INVENTORY MUTATIONS
# =============================================

# Set inventory quantity mutation
INVENTORY_SET_MUTATION = """
mutation InventorySetOnHandQuantities($input: InventorySetOnHandQuantitiesInput!) {
  inventorySetOnHandQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      reason
      referenceDocumentUri
      changes {
        name
        delta
        quantityAfterChange
        item {
          id
          sku
        }
        location {
          id
          name
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

# Adjust inventory quantities mutation
INVENTORY_ADJUST_QUANTITIES_MUTATION = """
mutation InventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      reason
      referenceDocumentUri
      changes {
        name
        delta
        quantityAfterChange
        item {
          id
          sku
        }
        location {
          id
          name
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

# Legacy inventory adjust mutation (for compatibility)
INVENTORY_ADJUST_MUTATION = """
mutation InventoryAdjust($input: InventoryAdjustInput!) {
  inventoryAdjust(input: $input) {
    inventoryLevel {
      id
      available
      item {
        id
        sku
      }
      location {
        id
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

# Activate inventory tracking
INVENTORY_ACTIVATE_MUTATION = """
mutation InventoryActivate($inventoryItemId: ID!, $locationId: ID!, $tracked: Boolean, $availableWhenSoldOut: Boolean) {
  inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId, tracked: $tracked, availableWhenSoldOut: $availableWhenSoldOut) {
    inventoryLevel {
      id
      available
      item {
        id
        sku
        tracked
      }
      location {
        id
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

# Deactivate inventory tracking
INVENTORY_DEACTIVATE_MUTATION = """
mutation InventoryDeactivate($inventoryLevelId: ID!) {
  inventoryDeactivate(inventoryLevelId: $inventoryLevelId) {
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# INVENTORY ITEM MUTATIONS
# =============================================

# Update inventory item
INVENTORY_ITEM_UPDATE_MUTATION = """
mutation InventoryItemUpdate($input: InventoryItemInput!) {
  inventoryItemUpdate(input: $input) {
    inventoryItem {
      id
      sku
      tracked
      requiresShipping
      cost
      countryCodeOfOrigin
      provinceCodeOfOrigin
      harmonizedSystemCode
      countryHarmonizedSystemCodes {
        countryCode
        harmonizedSystemCode
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# BULK INVENTORY OPERATIONS
# =============================================

# Bulk set inventory quantities
INVENTORY_BULK_SET_MUTATION = """
mutation InventoryBulkSetQuantities($input: InventoryBulkSetQuantitiesInput!) {
  inventoryBulkSetQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      reason
      changes {
        name
        delta
        quantityAfterChange
        item {
          id
          sku
        }
        location {
          id
          name
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

# Bulk adjust inventory quantities
INVENTORY_BULK_ADJUST_MUTATION = """
mutation InventoryBulkAdjustQuantities($input: InventoryBulkAdjustQuantitiesInput!) {
  inventoryBulkAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      reason
      changes {
        name
        delta
        quantityAfterChange
        item {
          id
          sku
        }
        location {
          id
          name
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

# =============================================
# INVENTORY ANALYTICS AND REPORTING
# =============================================

# Low stock inventory query
LOW_STOCK_INVENTORY_QUERY = """
query GetLowStockInventory($first: Int!, $threshold: Int = 5) {
  inventoryLevels(first: $first, query: "available:<${threshold}") {
    edges {
      node {
        id
        available
        item {
          id
          sku
          variant {
            id
            title
            product {
              id
              title
              handle
            }
          }
        }
        location {
          id
          name
        }
      }
    }
  }
}
"""

# Out of stock inventory query
OUT_OF_STOCK_INVENTORY_QUERY = """
query GetOutOfStockInventory($first: Int!) {
  inventoryLevels(first: $first, query: "available:0") {
    edges {
      node {
        id
        available
        item {
          id
          sku
          variant {
            id
            title
            product {
              id
              title
              handle
              tags
            }
          }
        }
        location {
          id
          name
        }
      }
    }
  }
}
"""

# Inventory summary by location
INVENTORY_SUMMARY_BY_LOCATION_QUERY = """
query GetInventorySummaryByLocation($locationId: ID!, $first: Int!) {
  location(id: $locationId) {
    id
    name
    inventoryLevels(first: $first) {
      edges {
        node {
          id
          available
          item {
            id
            sku
            cost
            variant {
              id
              title
              price
              product {
                id
                title
                handle
                productType
              }
            }
          }
          quantities {
            name
            quantity
          }
        }
      }
    }
  }
}
"""

# Inventory value calculation query
INVENTORY_VALUE_QUERY = """
query GetInventoryValue($first: Int!, $locationId: ID) {
  inventoryLevels(first: $first, query: $locationId) {
    edges {
      node {
        id
        available
        item {
          id
          sku
          cost
          variant {
            id
            price
            product {
              id
              title
            }
          }
        }
        location {
          id
          name
        }
      }
    }
  }
}
"""