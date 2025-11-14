"""
GraphQL queries and mutations for reverse stock synchronization.

This module contains GraphQL operations for:
- Querying products without specific sync tags
- Deleting variants with zero stock
- Batch inventory updates
"""

# Query products that DON'T have a specific tag (unsynced products)
PRODUCTS_WITHOUT_TAG_QUERY = """
query productsWithoutTag($query: String!, $first: Int!, $after: String) {
  products(query: $query, first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        tags
        status
        variants(first: 100) {
          edges {
            node {
              id
              sku
              title
              inventoryItem {
                id
              }
              inventoryQuantity
              selectedOptions {
                name
                value
              }
            }
          }
        }
        metafields(first: 50) {
          edges {
            node {
              namespace
              key
              value
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

# Delete product variants using bulk delete (API 2025-04 compatible)
DELETE_VARIANTS_BULK_MUTATION = """
mutation DeleteVariantsBulk($productId: ID!, $variantsIds: [ID!]!) {
  productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
    product {
      id
      title
      variants(first: 100) {
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
    userErrors {
      field
      message
    }
  }
}
"""

# Query product with variants and inventory (for validation)
PRODUCT_WITH_INVENTORY_QUERY = """
query productWithInventory($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    tags
    variants(first: 100) {
      edges {
        node {
          id
          sku
          title
          inventoryItem {
            id
            tracked
          }
          inventoryQuantity
          selectedOptions {
            name
            value
          }
        }
      }
    }
    metafields(first: 50, namespace: "rms") {
      edges {
        node {
          key
          value
        }
      }
    }
  }
}
"""

# Bulk update inventory levels (for efficiency)
BULK_UPDATE_INVENTORY_MUTATION = """
mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
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
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Query recent orders containing a specific variant (for deletion validation)
VARIANT_RECENT_ORDERS_QUERY = """
query variantRecentOrders($variantId: ID!, $createdAfter: DateTime!) {
  orders(first: 10, query: $query) {
    edges {
      node {
        id
        name
        createdAt
        financialStatus
        fulfillmentStatus
        lineItems(first: 50) {
          edges {
            node {
              id
              variant {
                id
              }
              quantity
            }
          }
        }
      }
    }
  }
}
"""

# Query inventory item with levels (API 2025-04 compatible)
INVENTORY_ITEM_QUERY = """
query inventoryItem($id: ID!) {
  inventoryItem(id: $id) {
    id
    sku
    tracked
    inventoryLevels(first: 10) {
      edges {
        node {
          id
          location {
            id
            name
          }
          quantities(names: ["available", "incoming", "committed"]) {
            name
            quantity
          }
        }
      }
    }
  }
}
"""
