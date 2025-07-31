"""
Webhook-related GraphQL operations for Shopify API.

This module contains all GraphQL queries and mutations specifically related
to webhook subscriptions, allowing the system to register for and manage
Shopify event notifications.
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

# Query webhook subscriptions
GET_WEBHOOK_SUBSCRIPTIONS = """
query GetWebhookSubscriptions($first: Int = 50) {
  webhookSubscriptions(first: $first) {
    edges {
      node {
        id
        topic
        callbackUrl
        format
        createdAt
        updatedAt
        includeFields
        metafieldNamespaces
      }
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

# Get specific webhook subscription
GET_WEBHOOK_SUBSCRIPTION = """
query GetWebhookSubscription($id: ID!) {
  webhookSubscription(id: $id) {
    id
    topic
    callbackUrl
    format
    createdAt
    updatedAt
    includeFields
    metafieldNamespaces
  }
}
"""

# Update webhook subscription
UPDATE_WEBHOOK_SUBSCRIPTION = """
mutation UpdateWebhookSubscription($id: ID!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionUpdate(id: $id, webhookSubscription: $webhookSubscription) {
    webhookSubscription {
      id
      topic
      callbackUrl
      format
      includeFields
      metafieldNamespaces
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Delete webhook subscription
DELETE_WEBHOOK_SUBSCRIPTION = """
mutation DeleteWebhookSubscription($id: ID!) {
  webhookSubscriptionDelete(id: $id) {
    deletedWebhookSubscriptionId
    userErrors {
      field
      message
    }
  }
}
"""