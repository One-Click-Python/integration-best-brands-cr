"""
GraphQL queries for Shopify Collections API.

This module contains GraphQL queries and mutations for interacting with Shopify collections,
following the 2025-04 API version specifications.
"""

# Query to fetch collections with pagination support
COLLECTIONS_QUERY = """
query getCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        description
        descriptionHtml
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
        updatedAt
        sortOrder
        templateSuffix
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
        products(first: 5) {
          edges {
            node {
              id
              title
              handle
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

# Query to fetch a single collection by ID
COLLECTION_BY_ID_QUERY = """
query getCollectionById($id: ID!) {
  collection(id: $id) {
    id
    title
    handle
    description
    descriptionHtml
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
    updatedAt
    sortOrder
    templateSuffix
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
          variants(first: 1) {
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
  }
}
"""

# Query to fetch collection by handle
COLLECTION_BY_HANDLE_QUERY = """
query getCollectionByHandle($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    title
    handle
    description
    descriptionHtml
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
    updatedAt
    sortOrder
    templateSuffix
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
        }
      }
    }
  }
}
"""

# Mutation to create a new collection
CREATE_COLLECTION_MUTATION = """
mutation createCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      title
      handle
      description
      descriptionHtml
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
      sortOrder
      templateSuffix
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Mutation to update an existing collection
UPDATE_COLLECTION_MUTATION = """
mutation updateCollection($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      handle
      description
      descriptionHtml
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
      sortOrder
      templateSuffix
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Mutation to delete a collection
DELETE_COLLECTION_MUTATION = """
mutation deleteCollection($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) {
    deletedCollectionId
    userErrors {
      field
      message
    }
  }
}
"""

# Mutation to add products to a collection
COLLECTION_ADD_PRODUCTS_MUTATION = """
mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
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

# Mutation to remove products from a collection
COLLECTION_REMOVE_PRODUCTS_MUTATION = """
mutation collectionRemoveProducts($id: ID!, $productIds: [ID!]!) {
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