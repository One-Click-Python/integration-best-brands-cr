"""
Order-related GraphQL queries and mutations.

This module contains all order management operations:
- Order queries and filtering
- Draft order operations
- Order fulfillment and shipping
- Order modifications and cancellations
- Customer order history
"""

# =============================================
# ORDER QUERIES
# =============================================

# Orders query with pagination and filtering
ORDERS_QUERY = """
query GetOrders($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        email
        phone
        createdAt
        updatedAt
        processedAt
        cancelledAt
        cancelReason
        confirmed
        closed
        test
        totalPriceV2 {
          amount
          currencyCode
        }
        subtotalPriceV2 {
          amount
          currencyCode
        }
        totalTaxV2 {
          amount
          currencyCode
        }
        totalShippingPriceV2 {
          amount
          currencyCode
        }
        financialStatus
        fulfillmentStatus
        customer {
          id
          firstName
          lastName
          email
          phone
        }
        shippingAddress {
          firstName
          lastName
          address1
          address2
          city
          province
          country
          zip
          phone
        }
        billingAddress {
          firstName
          lastName
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
              variant {
                id
                sku
                title
                product {
                  id
                  title
                  handle
                }
              }
              originalUnitPriceV2 {
                amount
                currencyCode
              }
              discountedUnitPriceV2 {
                amount
                currencyCode
              }
              originalTotalPriceV2 {
                amount
                currencyCode
              }
              discountedTotalPriceV2 {
                amount
                currencyCode
              }
            }
          }
        }
        fulfillments {
          id
          status
          trackingNumber
          trackingUrls
          trackingCompany
          createdAt
          updatedAt
          estimatedDeliveryAt
          inTransitAt
          deliveredAt
        }
        transactions {
          id
          kind
          status
          amount
          gateway
          createdAt
          processedAt
        }
        tags
        note
        clientDetails {
          browserIp
          acceptLanguage
          userAgent
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

# Single order query with full details
ORDER_BY_ID_QUERY = """
query GetOrderById($id: ID!) {
  order(id: $id) {
    id
    name
    email
    phone
    createdAt
    updatedAt
    processedAt
    cancelledAt
    cancelReason
    confirmed
    closed
    test
    totalPriceV2 {
      amount
      currencyCode
    }
    subtotalPriceV2 {
      amount
      currencyCode
    }
    totalTaxV2 {
      amount
      currencyCode
    }
    totalShippingPriceV2 {
      amount
      currencyCode
    }
    financialStatus
    fulfillmentStatus
    customer {
      id
      firstName
      lastName
      email
      phone
      defaultAddress {
        firstName
        lastName
        address1
        address2
        city
        province
        country
        zip
      }
    }
    shippingAddress {
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
      latitude
      longitude
    }
    billingAddress {
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
    lineItems(first: 250) {
      edges {
        node {
          id
          title
          quantity
          variant {
            id
            sku
            title
            image {
              url
              altText
            }
            product {
              id
              title
              handle
              vendor
            }
          }
          originalUnitPriceV2 {
            amount
            currencyCode
          }
          discountedUnitPriceV2 {
            amount
            currencyCode
          }
          originalTotalPriceV2 {
            amount
            currencyCode
          }
          discountedTotalPriceV2 {
            amount
            currencyCode
          }
          taxLines {
            title
            priceV2 {
              amount
              currencyCode
            }
            rate
            ratePercentage
          }
          discountAllocations {
            allocatedAmountV2 {
              amount
              currencyCode
            }
            discountApplication {
              ... on ManualDiscountApplication {
                title
                description
              }
              ... on DiscountCodeApplication {
                code
              }
              ... on AutomaticDiscountApplication {
                title
              }
            }
          }
        }
      }
    }
    fulfillments {
      id
      status
      trackingNumber
      trackingUrls
      trackingCompany
      createdAt
      updatedAt
      estimatedDeliveryAt
      inTransitAt
      deliveredAt
      fulfillmentLineItems(first: 250) {
        edges {
          node {
            id
            quantity
            lineItem {
              id
              title
              variant {
                sku
              }
            }
          }
        }
      }
    }
    transactions {
      id
      kind
      status
      amount
      gateway
      createdAt
      processedAt
      errorCode
      authorizationCode
      parentTransaction {
        id
      }
    }
    discountApplications(first: 10) {
      edges {
        node {
          ... on ManualDiscountApplication {
            title
            description
            valueV2 {
              ... on MoneyV2 {
                amount
                currencyCode
              }
              ... on PricingPercentageValue {
                percentage
              }
            }
          }
          ... on DiscountCodeApplication {
            code
            applicable
            valueV2 {
              ... on MoneyV2 {
                amount
                currencyCode
              }
              ... on PricingPercentageValue {
                percentage
              }
            }
          }
          ... on AutomaticDiscountApplication {
            title
            valueV2 {
              ... on MoneyV2 {
                amount
                currencyCode
              }
              ... on PricingPercentageValue {
                percentage
              }
            }
          }
        }
      }
    }
    shippingLines {
      title
      priceV2 {
        amount
        currencyCode
      }
      discountedPriceV2 {
        amount
        currencyCode
      }
      code
      source
    }
    tags
    note
    attributes {
      key
      value
    }
    clientDetails {
      browserIp
      acceptLanguage
      userAgent
      browserHeight
      browserWidth
    }
    customAttributes {
      key
      value
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

# Orders by customer
ORDERS_BY_CUSTOMER_QUERY = """
query GetOrdersByCustomer($customerId: ID!, $first: Int!) {
  customer(id: $customerId) {
    id
    firstName
    lastName
    email
    orders(first: $first) {
      edges {
        node {
          id
          name
          createdAt
          financialStatus
          fulfillmentStatus
          totalPriceV2 {
            amount
            currencyCode
          }
          lineItems(first: 10) {
            edges {
              node {
                title
                quantity
                variant {
                  sku
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

# =============================================
# DRAFT ORDER OPERATIONS
# =============================================

# Draft orders query
DRAFT_ORDERS_QUERY = """
query GetDraftOrders($first: Int!, $after: String, $query: String) {
  draftOrders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        email
        phone
        createdAt
        updatedAt
        invoiceUrl
        invoiceSentAt
        status
        totalPriceV2 {
          amount
          currencyCode
        }
        subtotalPriceV2 {
          amount
          currencyCode
        }
        totalTaxV2 {
          amount
          currencyCode
        }
        customer {
          id
          firstName
          lastName
          email
        }
        shippingAddress {
          firstName
          lastName
          address1
          city
          province
          country
          zip
        }
        lineItems(first: 250) {
          edges {
            node {
              id
              title
              quantity
              variant {
                id
                sku
                title
                product {
                  id
                  title
                }
              }
              originalUnitPriceV2 {
                amount
                currencyCode
              }
              discountedUnitPriceV2 {
                amount
                currencyCode
              }
            }
          }
        }
        tags
        note
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# Single draft order query
DRAFT_ORDER_QUERY = """
query GetDraftOrder($id: ID!) {
  draftOrder(id: $id) {
    id
    name
    email
    phone
    createdAt
    updatedAt
    invoiceUrl
    invoiceSentAt
    status
    totalPriceV2 {
      amount
      currencyCode
    }
    subtotalPriceV2 {
      amount
      currencyCode
    }
    totalTaxV2 {
      amount
      currencyCode
    }
    customer {
      id
      firstName
      lastName
      email
      phone
    }
    shippingAddress {
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
    billingAddress {
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
    lineItems(first: 250) {
      edges {
        node {
          id
          title
          quantity
          variant {
            id
            sku
            title
            image {
              url
              altText
            }
            product {
              id
              title
              handle
            }
          }
          originalUnitPriceV2 {
            amount
            currencyCode
          }
          discountedUnitPriceV2 {
            amount
            currencyCode
          }
          taxable
          requiresShipping
          giftCard
          customAttributes {
            key
            value
          }
        }
      }
    }
    shippingLine {
      title
      priceV2 {
        amount
        currencyCode
      }
      code
    }
    appliedDiscount {
      title
      description
      valueV2 {
        ... on MoneyV2 {
          amount
          currencyCode
        }
        ... on PricingPercentageValue {
          percentage
        }
      }
      amountV2 {
        amount
        currencyCode
      }
    }
    taxExempt
    taxLines {
      title
      priceV2 {
        amount
        currencyCode
      }
      rate
      ratePercentage
    }
    tags
    note
    customAttributes {
      key
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
"""

# =============================================
# ORDER MUTATIONS
# =============================================

# Create order mutation
CREATE_ORDER_MUTATION = """
mutation CreateOrder($input: OrderInput!) {
  orderCreate(input: $input) {
    order {
      id
      name
      email
      createdAt
      financialStatus
      fulfillmentStatus
      totalPriceV2 {
        amount
        currencyCode
      }
      customer {
        id
        firstName
        lastName
        email
      }
      lineItems(first: 250) {
        edges {
          node {
            id
            title
            quantity
            variant {
              id
              sku
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

# Update order mutation
UPDATE_ORDER_MUTATION = """
mutation UpdateOrder($input: OrderInput!) {
  orderUpdate(input: $input) {
    order {
      id
      name
      email
      updatedAt
      tags
      note
      metafields(first: 10) {
        edges {
          node {
            id
            namespace
            key
            value
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

# Cancel order mutation
CANCEL_ORDER_MUTATION = """
mutation CancelOrder($input: OrderCancelInput!) {
  orderCancel(input: $input) {
    order {
      id
      name
      cancelledAt
      cancelReason
      financialStatus
      fulfillmentStatus
    }
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# FULFILLMENT OPERATIONS
# =============================================

# Create fulfillment mutation
CREATE_FULFILLMENT_MUTATION = """
mutation CreateFulfillment($input: FulfillmentInput!) {
  fulfillmentCreate(input: $input) {
    fulfillment {
      id
      status
      trackingNumber
      trackingUrls
      trackingCompany
      createdAt
      fulfillmentLineItems(first: 250) {
        edges {
          node {
            id
            quantity
            lineItem {
              id
              title
            }
          }
        }
      }
    }
    order {
      id
      fulfillmentStatus
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Update fulfillment tracking mutation
UPDATE_FULFILLMENT_MUTATION = """
mutation UpdateFulfillment($input: FulfillmentInput!) {
  fulfillmentUpdate(input: $input) {
    fulfillment {
      id
      status
      trackingNumber
      trackingUrls
      trackingCompany
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Cancel fulfillment mutation
CANCEL_FULFILLMENT_MUTATION = """
mutation CancelFulfillment($input: FulfillmentCancelInput!) {
  fulfillmentCancel(input: $input) {
    fulfillment {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

# =============================================
# DRAFT ORDER MUTATIONS
# =============================================

# Create draft order mutation
CREATE_DRAFT_ORDER_MUTATION = """
mutation CreateDraftOrder($input: DraftOrderInput!) {
  draftOrderCreate(input: $input) {
    draftOrder {
      id
      name
      email
      createdAt
      status
      totalPriceV2 {
        amount
        currencyCode
      }
      customer {
        id
        firstName
        lastName
        email
      }
      lineItems(first: 250) {
        edges {
          node {
            id
            title
            quantity
            variant {
              id
              sku
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

# Update draft order mutation
UPDATE_DRAFT_ORDER_MUTATION = """
mutation UpdateDraftOrder($input: DraftOrderInput!) {
  draftOrderUpdate(input: $input) {
    draftOrder {
      id
      name
      email
      updatedAt
      status
      totalPriceV2 {
        amount
        currencyCode
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Complete draft order mutation
COMPLETE_DRAFT_ORDER_MUTATION = """
mutation CompleteDraftOrder($input: DraftOrderCompleteInput!) {
  draftOrderComplete(input: $input) {
    draftOrder {
      id
      status
    }
    order {
      id
      name
      financialStatus
      fulfillmentStatus
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Delete draft order mutation
DELETE_DRAFT_ORDER_MUTATION = """
mutation DeleteDraftOrder($input: DraftOrderDeleteInput!) {
  draftOrderDelete(input: $input) {
    deletedId
    userErrors {
      field
      message
    }
  }
}
"""