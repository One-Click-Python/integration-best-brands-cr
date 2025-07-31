"""
Product-related GraphQL queries and mutations.

This module contains all product operations organized by function:
- Product queries (fetch, search, filter)
- Product mutations (create, update, delete)
- Variant operations (create, update, bulk operations)
- Product publishing and status management
"""

# =============================================
# PRODUCT QUERIES
# =============================================

# Single product query with full details
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
    description
    descriptionHtml
    onlineStoreUrl
    createdAt
    updatedAt
    publishedAt
    category {
      id
      name
      fullName
    }
    seo {
      title
      description
    }
    options {
      id
      name
      values
      position
    }
    images(first: 250) {
      edges {
        node {
          id
          url
          altText
          width
          height
        }
      }
    }
    variants(first: 250) {
      edges {
        node {
          id
          sku
          title
          price
          compareAtPrice
          position
          weight
          weightUnit
          availableForSale
          inventoryQuantity
          inventoryPolicy
          inventoryItem {
            id
            sku
            tracked
            requiresShipping
          }
          selectedOptions {
            name
            value
          }
          metafields(first: 10) {
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
    metafields(first: 20) {
      edges {
        node {
          id
          namespace
          key
          value
          type
          description
        }
      }
    }
  }
}
"""

# Products query with pagination
PRODUCTS_QUERY = """
query GetProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
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
        publishedAt
        onlineStoreUrl
        category {
          id
          name
        }
        totalInventory
        variants(first: 5) {
          edges {
            node {
              id
              sku
              price
              compareAtPrice
              inventoryQuantity
              availableForSale
            }
          }
        }
        images(first: 3) {
          edges {
            node {
              id
              url
              altText
            }
          }
        }
      }
      cursor
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
"""

# Product search by SKU
PRODUCT_BY_SKU_QUERY = """
query GetProductBySKU($query: String!) {
  products(first: 10, query: $query) {
    edges {
      node {
        id
        title
        handle
        status
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
            }
          }
        }
      }
    }
  }
}
"""

# Product search by handle
PRODUCT_BY_HANDLE_QUERY = """
query GetProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    title
    handle
    status
    productType
    vendor
    tags
    description
    variants(first: 250) {
      edges {
        node {
          id
          sku
          title
          price
          compareAtPrice
          inventoryQuantity
          availableForSale
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
"""

# Advanced product search query
PRODUCT_SEARCH_QUERY = """
query SearchProducts($first: Int!, $after: String, $query: String, $sortKey: ProductSortKeys, $reverse: Boolean) {
  products(first: $first, after: $after, query: $query, sortKey: $sortKey, reverse: $reverse) {
    edges {
      node {
        id
        title
        handle
        status
        productType
        vendor
        tags
        totalInventory
        createdAt
        updatedAt
        variants(first: 1) {
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
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# =============================================
# PRODUCT MUTATIONS
# =============================================

# Create product mutation
CREATE_PRODUCT_MUTATION = """
mutation CreateProduct($input: ProductInput!) {
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
      }
      variants(first: 250) {
        edges {
          node {
            id
            sku
            title
            price
            compareAtPrice
            inventoryItem {
              id
            }
          }
        }
      }
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
    userErrors {
      field
      message
    }
  }
}
"""

# Update product mutation
UPDATE_PRODUCT_MUTATION = """
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      productType
      vendor
      tags
      updatedAt
      category {
        id
        name
      }
      variants(first: 250) {
        edges {
          node {
            id
            sku
            title
            price
            compareAtPrice
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

# Delete product mutation
DELETE_PRODUCT_MUTATION = """
mutation DeleteProduct($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    shop {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Publish product mutation
PUBLISH_PRODUCT_MUTATION = """
mutation PublishProduct($input: ProductPublishInput!) {
  productPublish(input: $input) {
    product {
      id
      title
      status
      publishedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Unpublish product mutation
UNPUBLISH_PRODUCT_MUTATION = """
mutation UnpublishProduct($input: ProductUnpublishInput!) {
  productUnpublish(input: $input) {
    product {
      id
      title
      status
      publishedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# VARIANT OPERATIONS
# =============================================

# Create single variant
CREATE_VARIANT_MUTATION = """
mutation CreateVariant($input: ProductVariantInput!) {
  productVariantCreate(input: $input) {
    productVariant {
      id
      sku
      title
      price
      compareAtPrice
      position
      inventoryQuantity
      inventoryItem {
        id
      }
      product {
        id
        title
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Update single variant
UPDATE_VARIANT_MUTATION = """
mutation UpdateVariant($input: ProductVariantInput!) {
  productVariantUpdate(input: $input) {
    productVariant {
      id
      sku
      title
      price
      compareAtPrice
      inventoryQuantity
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Delete variant
DELETE_VARIANT_MUTATION = """
mutation DeleteVariant($input: ProductVariantDeleteInput!) {
  productVariantDelete(input: $input) {
    deletedProductVariantId
    product {
      id
      title
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Bulk create variants
CREATE_VARIANTS_BULK_MUTATION = """
mutation CreateVariantsBulk($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    product {
      id
      title
      variants(first: 250) {
        edges {
          node {
            id
            sku
            title
            price
            compareAtPrice
            inventoryItem {
              id
            }
          }
        }
      }
    }
    productVariants {
      id
      sku
      title
      price
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Bulk update variants
UPDATE_VARIANTS_BULK_MUTATION = """
mutation UpdateVariantsBulk($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    product {
      id
      title
      variants(first: 250) {
        edges {
          node {
            id
            sku
            title
            price
            compareAtPrice
            updatedAt
          }
        }
      }
    }
    productVariants {
      id
      sku
      title
      price
    }
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# PRODUCT WITH CATEGORY OPERATIONS
# =============================================

# Create product with category
CREATE_PRODUCT_WITH_CATEGORY_MUTATION = """
mutation CreateProductWithCategory($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      productType
      category {
        id
        name
        fullName
      }
      variants(first: 250) {
        edges {
          node {
            id
            sku
            price
            inventoryItem {
              id
            }
          }
        }
      }
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
    userErrors {
      field
      message
    }
  }
}
"""

# Update product with category
UPDATE_PRODUCT_WITH_CATEGORY_MUTATION = """
mutation UpdateProductWithCategory($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      category {
        id
        name
        fullName
      }
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""