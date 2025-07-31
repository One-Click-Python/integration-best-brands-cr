"""
Webhook-related GraphQL queries and mutations.

This module contains webhook management operations:
- Webhook subscription queries
- Webhook creation and updates
- Webhook event management
"""

# Webhook subscriptions query
WEBHOOK_SUBSCRIPTIONS_QUERY = """
query GetWebhookSubscriptions($first: Int!) {
  webhookSubscriptions(first: $first) {
    edges {
      node {
        id
        callbackUrl
        topic
        format
        createdAt
        updatedAt
        includeFields
        metafieldNamespaces
        privateMetafieldNamespaces
        filter
        legacyResourceId
        apiVersion
        endpoint {
          __typename
          ... on WebhookHttpEndpoint {
            callbackUrl
          }
          ... on WebhookEventBridgeEndpoint {
            arn
          }
          ... on WebhookPubSubEndpoint {
            pubSubProject
            pubSubTopic
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

# Create webhook subscription mutation
CREATE_WEBHOOK_SUBSCRIPTION = """
mutation CreateWebhookSubscription($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    webhookSubscription {
      id
      callbackUrl
      topic
      format
      createdAt
      includeFields
      metafieldNamespaces
      privateMetafieldNamespaces
      filter
      apiVersion
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Update webhook subscription mutation
UPDATE_WEBHOOK_SUBSCRIPTION = """
mutation UpdateWebhookSubscription($id: ID!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionUpdate(id: $id, webhookSubscription: $webhookSubscription) {
    webhookSubscription {
      id
      callbackUrl
      topic
      format
      updatedAt
      includeFields
      metafieldNamespaces
      privateMetafieldNamespaces
      filter
      apiVersion
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Delete webhook subscription mutation
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

# Get webhook subscription by ID
GET_WEBHOOK_SUBSCRIPTION = """
query GetWebhookSubscription($id: ID!) {
  webhookSubscription(id: $id) {
    id
    callbackUrl
    topic
    format
    createdAt
    updatedAt
    includeFields
    metafieldNamespaces
    privateMetafieldNamespaces
    filter
    legacyResourceId
    apiVersion
    endpoint {
      __typename
      ... on WebhookHttpEndpoint {
        callbackUrl
      }
      ... on WebhookEventBridgeEndpoint {
        arn
      }
      ... on WebhookPubSubEndpoint {
        pubSubProject
        pubSubTopic
      }
    }
  }
}
"""

# Get webhook subscriptions with filtering
GET_WEBHOOK_SUBSCRIPTIONS = """
query GetWebhookSubscriptions($first: Int!, $after: String, $callbackUrl: String, $topic: WebhookSubscriptionTopic) {
  webhookSubscriptions(first: $first, after: $after, callbackUrl: $callbackUrl, topic: $topic) {
    edges {
      node {
        id
        callbackUrl
        topic
        format
        createdAt
        updatedAt
        includeFields
        metafieldNamespaces
        filter
        apiVersion
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""