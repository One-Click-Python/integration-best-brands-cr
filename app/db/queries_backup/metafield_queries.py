"""
Metafield-related GraphQL operations for Shopify API.

This module contains all GraphQL queries and mutations specifically related
to metafield operations, including creation, updates, bulk operations,
and metafield definition management.
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
      createdAt
      updatedAt
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
      createdAt
      updatedAt
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
    createdDefinition {
      id
      name
      namespace
      key
      type {
        name
        category
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