"""
Metafield-related GraphQL queries and mutations.

This module contains all metafield operations:
- Metafield queries and filtering
- Metafield creation and updates
- Metafield definition management
- Bulk metafield operations
"""

# Metafields query
METAFIELDS_QUERY = """
query GetMetafields($first: Int!, $after: String, $namespace: String, $key: String) {
  metafields(first: $first, after: $after, namespace: $namespace, key: $key) {
    edges {
      node {
        id
        namespace
        key
        value
        type
        description
        createdAt
        updatedAt
        owner {
          ... on Product {
            id
            title
          }
          ... on ProductVariant {
            id
            title
          }
          ... on Collection {
            id
            title
          }
          ... on Customer {
            id
            firstName
            lastName
          }
          ... on Order {
            id
            name
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

# Metafield definitions query
METAFIELD_DEFINITIONS_QUERY = """
query GetMetafieldDefinitions($first: Int!, $after: String, $ownerType: MetafieldOwnerType) {
  metafieldDefinitions(first: $first, after: $after, ownerType: $ownerType) {
    edges {
      node {
        id
        namespace
        key
        name
        description
        type {
          name
          category
          supportsVariableDefinitions
        }
        ownerType
        visibleToStorefrontApi
        useAsCollectionCondition
        validations {
          name
          type
          value
        }
        standardDefinition {
          id
          name
          description
        }
        metafields(first: 10) {
          edges {
            node {
              id
              value
              owner {
                ... on Product {
                  id
                  title
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

# Create metafield mutation
CREATE_METAFIELD_MUTATION = """
mutation CreateMetafield($input: MetafieldInput!) {
  metafieldCreate(input: $input) {
    metafield {
      id
      namespace
      key
      value
      type
      description
      createdAt
      owner {
        ... on Product {
          id
          title
        }
        ... on ProductVariant {
          id
          title
        }
        ... on Collection {
          id
          title
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

# Update metafield mutation
UPDATE_METAFIELD_MUTATION = """
mutation UpdateMetafield($input: MetafieldInput!) {
  metafieldUpdate(input: $input) {
    metafield {
      id
      namespace
      key
      value
      type
      description
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Bulk set metafields mutation
METAFIELDS_SET_MUTATION = """
mutation SetMetafields($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      id
      namespace
      key
      value
      type
      description
      owner {
        ... on Product {
          id
          title
        }
        ... on ProductVariant {
          id
          title
        }
        ... on Collection {
          id
          title
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

# Create metafield definition mutation
CREATE_METAFIELD_DEFINITION_MUTATION = """
mutation CreateMetafieldDefinition($input: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $input) {
    metafieldDefinition {
      id
      namespace
      key
      name
      description
      type {
        name
        category
      }
      ownerType
      visibleToStorefrontApi
      useAsCollectionCondition
      validations {
        name
        type
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
