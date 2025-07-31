"""
Order and draft order GraphQL operations for Shopify API.

This module contains all GraphQL queries and mutations specifically related
to order operations, including regular orders and draft orders management.
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
              quantity
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

# Draft Orders Queries
DRAFT_ORDERS_QUERY = """
query GetDraftOrders($first: Int!, $after: String, $query: String) {
  draftOrders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        status
        email
        phone
        createdAt
        updatedAt
        completedAt
        tags
        totalPriceSet {
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
        subtotalPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
        totalShippingPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
        totalDiscountsSet {
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
          defaultAddress {
            address1
            address2
            city
            province
            country
            zip
            phone
          }
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
        billingAddress {
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
              quantity
              originalUnitPrice
              discountedUnitPrice
              product {
                id
                title
                handle
              }
              variant {
                id
                title
                sku
                price
              }
            }
          }
        }
        appliedDiscount {
          title
          description
          valueType
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
"""

DRAFT_ORDER_QUERY = """
query GetDraftOrder($id: ID!) {
  draftOrder(id: $id) {
    id
    name
    status
    email
    phone
    createdAt
    updatedAt
    completedAt
    tags
    totalPriceSet {
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
    subtotalPriceSet {
      shopMoney {
        amount
        currencyCode
      }
    }
    totalShippingPriceSet {
      shopMoney {
        amount
        currencyCode
      }
    }
    totalDiscountsSet {
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
      defaultAddress {
        address1
        address2
        city
        province
        country
        zip
        phone
      }
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
    billingAddress {
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
          quantity
          originalUnitPrice
          discountedUnitPrice
          product {
            id
            title
            handle
          }
          variant {
            id
            title
            sku
            price
          }
        }
      }
    }
    appliedDiscount {
      title
      description
      valueType
      value
    }
  }
}
"""