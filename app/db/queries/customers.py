"""
Customer-related GraphQL queries and mutations.

This module contains all customer management operations:
- Customer queries and search
- Customer creation and updates
- Customer address management
- Customer order history
"""

# Customer queries
CUSTOMERS_QUERY = """
query GetCustomers($first: Int!, $after: String, $query: String) {
  customers(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        firstName
        lastName
        email
        phone
        createdAt
        updatedAt
        acceptsMarketing
        state
        tags
        ordersCount
        totalSpentV2 {
          amount
          currencyCode
        }
        defaultAddress {
          firstName
          lastName
          address1
          city
          province
          country
          zip
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

# Single customer query
CUSTOMER_BY_ID_QUERY = """
query GetCustomerById($id: ID!) {
  customer(id: $id) {
    id
    firstName
    lastName
    email
    phone
    createdAt
    updatedAt
    acceptsMarketing
    state
    tags
    note
    ordersCount
    totalSpentV2 {
      amount
      currencyCode
    }
    defaultAddress {
      id
      firstName
      lastName
      company
      address1
      address2
      city
      province
      country
      zip
      phone
    }
    addresses(first: 10) {
      id
      firstName
      lastName
      company
      address1
      address2
      city
      province
      country
      zip
      phone
      isDefault
    }
    orders(first: 10) {
      edges {
        node {
          id
          name
          createdAt
          financialStatus
          totalPriceV2 {
            amount
            currencyCode
          }
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
        }
      }
    }
  }
}
"""

# Create customer mutation
CREATE_CUSTOMER_MUTATION = """
mutation CreateCustomer($input: CustomerInput!) {
  customerCreate(input: $input) {
    customer {
      id
      firstName
      lastName
      email
      phone
      createdAt
      acceptsMarketing
      state
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Update customer mutation
UPDATE_CUSTOMER_MUTATION = """
mutation UpdateCustomer($input: CustomerInput!) {
  customerUpdate(input: $input) {
    customer {
      id
      firstName
      lastName
      email
      phone
      updatedAt
      acceptsMarketing
      state
      tags
      note
    }
    userErrors {
      field
      message
    }
  }
}
"""