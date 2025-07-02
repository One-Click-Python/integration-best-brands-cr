"""
Bulk operation GraphQL queries for Shopify API.

This module contains all GraphQL queries and mutations specifically related
to bulk operations, which allow processing large amounts of data efficiently.
"""

# Bulk Operations
BULK_OPERATION_PRODUCTS_QUERY = """
mutation BulkProductsQuery {
  bulkOperationRunQuery(
    query: \"\"\"
    {
      products {
        edges {
          node {
            id
            title
            handle
            status
            productType
            vendor
            tags
            createdAt
            updatedAt
            variants {
              edges {
                node {
                  id
                  sku
                  title
                  price
                  compareAtPrice
                  inventoryQuantity
                  inventoryItem {
                    id
                  }
                  selectedOptions {
                    name
                    value
                  }
                }
              }
            }
          }
        }
      }
    }
    \"\"\"
  ) {
    bulkOperation {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

BULK_OPERATION_STATUS_QUERY = """
query BulkOperationStatus($id: ID!) {
  node(id: $id) {
    ... on BulkOperation {
      id
      status
      errorCode
      createdAt
      completedAt
      objectCount
      fileSize
      url
      partialDataUrl
    }
  }
}
"""