"""
GraphQL queries and mutations for Shopify API.

This module contains all GraphQL queries and mutations used to interact
with the Shopify API, following the 2024-10 API version specifications.
"""

# Taxonomy Queries
TAXONOMY_CATEGORIES_QUERY = """
query GetTaxonomyCategories($search: String) {
  taxonomy {
    categories(search: $search, first: 50) {
      edges {
        node {
          id
          name
          fullName
        }
      }
    }
  }
}
"""

# Enhanced taxonomy query with full details
TAXONOMY_CATEGORY_DETAILS_QUERY = """
query GetTaxonomyCategoryDetails($categoryId: ID!) {
  taxonomy {
    category(id: $categoryId) {
      id
      name
      fullName
      isRoot
      isLeaf
      level
      attributes {
        id
        name
        choices
      }
      ancestors {
        id
        name
        fullName
      }
      children {
        id
        name
        fullName
      }
    }
  }
}
"""

# Query to browse taxonomy categories by level
TAXONOMY_BROWSE_QUERY = """
query BrowseTaxonomyCategories($parentId: ID, $first: Int = 50) {
  taxonomy {
    categories(parentId: $parentId, first: $first) {
      edges {
        node {
          id
          name
          fullName
          isLeaf
          level
          childrenCount
        }
      }
    }
  }
}
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
    userErrors {
      field
      message
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
    }
  }
}
"""

CREATE_VARIANT_MUTATION = """
mutation productVariantCreate($input: ProductVariantInput!) {
  productVariantCreate(input: $input) {
    productVariant {
      id
      sku
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
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_VARIANTS_BULK_MUTATION = """
mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(
    productId: $productId
    variants: $variants
  ) {
    product {
      id
    }
    productVariants {
      id
      sku
      price
      compareAtPrice
      inventoryQuantity
    }
    userErrors {
      field
      message
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
    }
  }
}
"""

# Bulk metafields mutation (up to 25 metafields at once)
METAFIELDS_SET_MUTATION = """
mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      id
      namespace
      key
      value
      type
      createdAt
      updatedAt
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""

# Create metafield definition
CREATE_METAFIELD_DEFINITION_MUTATION = """
mutation CreateMetafieldDefinition($definition: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $definition) {
    metafieldDefinition {
      id
      name
      namespace
      key
      type {
        name
        category
        supportsVariants
      }
      description
      ownerType
      validations {
        name
        type
        value
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

# Query metafield definitions
METAFIELD_DEFINITIONS_QUERY = """
query GetMetafieldDefinitions($ownerType: MetafieldOwnerType!, $first: Int = 50) {
  metafieldDefinitions(ownerType: $ownerType, first: $first) {
    edges {
      node {
        id
        name
        namespace
        key
        type {
          name
          category
          supportsVariants
        }
        description
        ownerType
        validations {
          name
          type
          value
        }
      }
    }
  }
}
"""

# Enhanced product creation with category and metafields
CREATE_PRODUCT_WITH_CATEGORY_MUTATION = """
mutation CreateProductWithCategory($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      productType
      vendor
      tags
      category {
        id
        name
        fullName
      }
      metafields(first: 50) {
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
            metafields(first: 20) {
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
    userErrors {
      field
      message
      code
    }
  }
}
"""

# Enhanced product update with category and metafields
UPDATE_PRODUCT_WITH_CATEGORY_MUTATION = """
mutation UpdateProductWithCategory($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      productType
      vendor
      tags
      category {
        id
        name
        fullName
      }
      metafields(first: 50) {
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
    userErrors {
      field
      message
      code
    }
  }
}
"""
