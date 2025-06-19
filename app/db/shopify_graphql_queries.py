"""
GraphQL queries and mutations for Shopify API.

This module contains all GraphQL queries and mutations used to interact
with the Shopify API, following the 2024-10 API version specifications.
"""

# Product Queries
PRODUCT_QUERY = """
query GetProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    status
    productType
    vendor
    tags
    options {
      id
      name
      values
    }
    variants(first: 250) {
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
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

PRODUCTS_QUERY = """
query GetProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
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
        options {
          id
          name
          values
        }
        variants(first: 100) {
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
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

PRODUCT_BY_SKU_QUERY = """
query GetProductBySku($sku: String!) {
  products(first: 1, query: $sku) {
    edges {
      node {
        id
        title
        variants(first: 250) {
          edges {
            node {
              id
              sku
              inventoryItem {
                id
              }
            }
          }
        }
      }
    }
  }
}
"""

# Product Mutations
CREATE_PRODUCT_MUTATION = """
mutation CreateProduct($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      variants(first: 100) {
        edges {
          node {
            id
            sku
            price
            inventoryQuantity
            inventoryItem {
              id
            }
          }
        }
      }
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

UPDATE_PRODUCT_MUTATION = """
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      variants(first: 100) {
        edges {
          node {
            id
            sku
            price
            inventoryQuantity
          }
        }
      }
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

UPDATE_VARIANT_MUTATION = """
mutation UpdateVariant($input: ProductVariantInput!) {
  productVariantUpdate(input: $input) {
    productVariant {
      id
      sku
      price
      inventoryQuantity
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

# Inventory Mutations
INVENTORY_ACTIVATE_MUTATION = """
mutation ActivateInventory($inventoryItemId: ID!, $locationId: ID!, $available: Int) {
  inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId, available: $available) {
    inventoryLevel {
      id
      available
    }
    userErrors {
      field
      message
      code
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
      code
    }
  }
}
"""

INVENTORY_SET_MUTATION = """
mutation SetInventory($input: InventorySetOnHandQuantitiesInput!) {
  inventorySetOnHandQuantities(input: $input) {
    inventoryAdjustmentGroup {
      id
      createdAt
      reason
    }
    userErrors {
      field
      message
      code
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

# Order Queries
ORDERS_QUERY = """
query GetOrders($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        createdAt
        updatedAt
        displayFinancialStatus
        displayFulfillmentStatus
        email
        phone
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
        customer {
          id
          email
          firstName
          lastName
          phone
        }
        shippingAddress {
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
              sku
              quantity
              variant {
                id
                sku
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
      errorCode
      createdAt
      objectCount
      url
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

# Webhook Subscriptions
CREATE_WEBHOOK_SUBSCRIPTION = """
mutation CreateWebhookSubscription($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    webhookSubscription {
      id
      topic
      callbackUrl
      format
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Metafields
CREATE_METAFIELD_MUTATION = """
mutation CreateMetafield($input: MetafieldInput!) {
  metafieldCreate(input: $input) {
    metafield {
      id
      namespace
      key
      value
      type
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

UPDATE_METAFIELD_MUTATION = """
mutation UpdateMetafield($input: MetafieldInput!) {
  metafieldUpdate(input: $input) {
    metafield {
      id
      namespace
      key
      value
      type
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""