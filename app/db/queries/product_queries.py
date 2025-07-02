"""
Product-related GraphQL operations for Shopify API.

This module contains all GraphQL queries and mutations specifically related
to product operations, including product creation, updates, variant management,
and product queries. Extracted from the main GraphQL queries module for
better organization and maintainability.
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

PRODUCT_BY_HANDLE_QUERY = """
query GetProductByHandle($handle: String!) {
  products(first: 1, query: $handle) {
    edges {
      node {
        id
        title
        handle
        status
        productType
        vendor
        tags
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

CREATE_VARIANTS_BULK_MUTATION = """
mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(
    productId: $productId
    variants: $variants
  ) {
    product {
      id
      title
      options {
        name
        values
      }
    }
    productVariants {
      id
      sku
      price
      compareAtPrice
      inventoryQuantity
      selectedOptions {
        name
        value
      }
      inventoryItem {
        id
        tracked
      }
    }
    userErrors {
      field
      message
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