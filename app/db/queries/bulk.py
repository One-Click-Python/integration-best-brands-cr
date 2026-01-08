"""
Bulk operation GraphQL queries and mutations.

This module contains bulk operation management:
- Bulk operation status and monitoring
- Bulk data export operations
- Bulk query execution
"""

# Bulk operation status query
BULK_OPERATION_STATUS_QUERY = """
query GetBulkOperationStatus($id: ID!) {
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
      query
      rootObjectCount
      type
    }
  }
}
"""

# Current bulk operation query
CURRENT_BULK_OPERATION_QUERY = """
query GetCurrentBulkOperation {
  currentBulkOperation {
    id
    status
    errorCode
    createdAt
    completedAt
    objectCount
    fileSize
    url
    partialDataUrl
    query
    rootObjectCount
    type
  }
}
"""

# Bulk operation for products export
BULK_OPERATION_PRODUCTS_QUERY = """
query BulkExportProducts {
  products {
    edges {
      node {
        id
        title
        handle
        status
        createdAt
        updatedAt
        productType
        vendor
        tags
        totalInventory
        variants {
          edges {
            node {
              id
              sku
              title
              price
              compareAtPrice
              inventoryQuantity
              weight
              weightUnit
              availableForSale
              inventoryItem {
                id
                tracked
                requiresShipping
              }
              selectedOptions {
                name
                value
              }
            }
          }
        }
        metafields {
          edges {
            node {
              id
              namespace
              key
              value
              type
            }
          }
        }
      }
    }
  }
}
"""

# Create bulk operation mutation
CREATE_BULK_OPERATION_MUTATION = """
mutation CreateBulkOperation($query: String!, $type: BulkOperationType!) {
  bulkOperationRunQuery(query: $query, type: $type) {
    bulkOperation {
      id
      status
      query
      rootObjectCount
      type
      createdAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Cancel bulk operation mutation
CANCEL_BULK_OPERATION_MUTATION = """
mutation CancelBulkOperation($id: ID!) {
  bulkOperationCancel(id: $id) {
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
