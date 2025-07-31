"""
Collection-related GraphQL queries and mutations.

This module contains all collection operations organized by function:
- Collection queries (fetch, search, filter)
- Collection mutations (create, update, delete)
- Product-collection relationship management
- Smart collections and rules
"""

# =============================================
# COLLECTION QUERIES
# =============================================

# Collections query with pagination and full details
COLLECTIONS_QUERY = """
query GetCollections($first: Int!, $after: String, $query: String) {
  collections(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        title
        handle
        description
        descriptionHtml
        sortOrder
        templateSuffix
        updatedAt
        image {
          id
          url
          altText
          width
          height
        }
        seo {
          title
          description
        }
        productsCount {
          count
        }
        products(first: 10) {
          edges {
            node {
              id
              title
              handle
              featuredImage {
                url
                altText
              }
              priceRangeV2 {
                minVariantPrice {
                  amount
                  currencyCode
                }
                maxVariantPrice {
                  amount
                  currencyCode
                }
              }
              totalInventory
            }
          }
        }
        metafields(first: 10) {
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

# Simple collections query (lightweight)
COLLECTIONS_SIMPLE_QUERY = """
query GetCollectionsSimple($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        productsCount {
          count
        }
        updatedAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# Single collection by ID
COLLECTION_BY_ID_QUERY = """
query GetCollectionById($id: ID!) {
  collection(id: $id) {
    id
    title
    handle
    description
    descriptionHtml
    sortOrder
    templateSuffix
    updatedAt
    image {
      id
      url
      altText
      width
      height
    }
    seo {
      title
      description
    }
    productsCount {
      count
    }
    products(first: 50) {
      edges {
        node {
          id
          title
          handle
          featuredImage {
            url
            altText
          }
          priceRangeV2 {
            minVariantPrice {
              amount
              currencyCode
            }
            maxVariantPrice {
              amount
              currencyCode
            }
          }
          variants(first: 5) {
            edges {
              node {
                id
                sku
                price
                availableForSale
                inventoryQuantity
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

# Collection by handle
COLLECTION_BY_HANDLE_QUERY = """
query GetCollectionByHandle($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    title
    handle
    description
    descriptionHtml
    sortOrder
    templateSuffix
    updatedAt
    image {
      id
      url
      altText
      width
      height
    }
    seo {
      title
      description
    }
    productsCount {
      count
    }
    products(first: 50) {
      edges {
        node {
          id
          title
          handle
          featuredImage {
            url
            altText
          }
          priceRangeV2 {
            minVariantPrice {
              amount
              currencyCode
            }
            maxVariantPrice {
              amount
              currencyCode
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

# Smart collections query
SMART_COLLECTIONS_QUERY = """
query GetSmartCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after, query: "collection_type:smart") {
    edges {
      node {
        id
        title
        handle
        description
        sortOrder
        productsCount {
          count
        }
        ruleSet {
          appliedDisjunctively
          rules {
            column
            relation
            condition
          }
        }
        updatedAt
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
# COLLECTION MUTATIONS
# =============================================

# Create collection mutation
CREATE_COLLECTION_MUTATION = """
mutation CreateCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      title
      handle
      description
      descriptionHtml
      sortOrder
      templateSuffix
      image {
        id
        url
        altText
      }
      seo {
        title
        description
      }
      productsCount {
        count
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

# Update collection mutation
UPDATE_COLLECTION_MUTATION = """
mutation UpdateCollection($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      handle
      description
      descriptionHtml
      sortOrder
      templateSuffix
      image {
        id
        url
        altText
      }
      seo {
        title
        description
      }
      productsCount {
        count
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

# Delete collection mutation
DELETE_COLLECTION_MUTATION = """
mutation DeleteCollection($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) {
    deletedCollectionId
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# PRODUCT-COLLECTION RELATIONSHIP MANAGEMENT
# =============================================

# Add products to collection
COLLECTION_ADD_PRODUCTS_MUTATION = """
mutation CollectionAddProducts($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
      title
      handle
      productsCount {
        count
      }
      products(first: 10) {
        edges {
          node {
            id
            title
            handle
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

# Remove products from collection
COLLECTION_REMOVE_PRODUCTS_MUTATION = """
mutation CollectionRemoveProducts($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) {
    collection {
      id
      title
      handle
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Reorder products in collection
COLLECTION_REORDER_PRODUCTS_MUTATION = """
mutation CollectionReorderProducts($id: ID!, $moves: [MoveInput!]!) {
  collectionReorderProducts(id: $id, moves: $moves) {
    collection {
      id
      title
      products(first: 50) {
        edges {
          node {
            id
            title
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

# =============================================
# SMART COLLECTION OPERATIONS
# =============================================

# Create smart collection with rules
CREATE_SMART_COLLECTION_MUTATION = """
mutation CreateSmartCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      title
      handle
      description
      sortOrder
      ruleSet {
        appliedDisjunctively
        rules {
          column
          relation
          condition
        }
      }
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Update smart collection rules
UPDATE_SMART_COLLECTION_MUTATION = """
mutation UpdateSmartCollection($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      handle
      ruleSet {
        appliedDisjunctively
        rules {
          column
          relation
          condition
        }
      }
      productsCount {
        count
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

# =============================================
# COLLECTION ANALYTICS AND INSIGHTS
# =============================================

# Collection with product analytics
COLLECTION_WITH_ANALYTICS_QUERY = """
query GetCollectionAnalytics($id: ID!) {
  collection(id: $id) {
    id
    title
    handle
    productsCount {
      count
    }
    products(first: 250) {
      edges {
        node {
          id
          title
          handle
          totalInventory
          variants(first: 1) {
            edges {
              node {
                id
                price
                inventoryQuantity
              }
            }
          }
          tags
          createdAt
          updatedAt
        }
      }
    }
  }
}
"""

# Collections with inventory summary
COLLECTIONS_WITH_INVENTORY_QUERY = """
query GetCollectionsWithInventory($first: Int!) {
  collections(first: $first) {
    edges {
      node {
        id
        title
        handle
        productsCount {
          count
        }
        products(first: 250) {
          edges {
            node {
              id
              totalInventory
              variants(first: 1) {
                edges {
                  node {
                    inventoryQuantity
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""