"""
Core GraphQL queries used across multiple domains.

This module contains fundamental queries that are used by multiple parts
of the application, such as shop information and location queries.
"""

# Shop information query
SHOP_INFO_QUERY = """
query GetShopInfo {
  shop {
    id
    name
    email
    domain
    myshopifyDomain
    currencyCode
    timezone
    weightUnit
    plan {
      displayName
      partnerDevelopment
      shopifyPlus
    }
    billingAddress {
      address1
      address2
      city
      country
      countryCodeV2
      province
      provinceCode
      zip
    }
  }
}
"""

# Locations query for inventory management
LOCATIONS_QUERY = """
query GetLocations {
  locations(first: 250) {
    edges {
      node {
        id
        name
        address {
          address1
          address2
          city
          country
          countryCode
          province
          provinceCode
          zip
        }
        fulfillsOnlineOrders
        hasActiveInventory
        hasUnfulfilledOrders
        isActive
        isPrimary
        shipsInventory
        inventoryLevels(first: 250) {
          edges {
            node {
              id
              available
              inventoryItem {
                id
                sku
              }
            }
          }
        }
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

# Simple locations query (lightweight)
LOCATIONS_SIMPLE_QUERY = """
query GetLocationsSimple {
  locations(first: 250) {
    edges {
      node {
        id
        name
        fulfillsOnlineOrders
        hasActiveInventory
        isActive
        isPrimary
      }
    }
  }
}
"""

# App installation query
APP_INSTALLATION_QUERY = """
query GetAppInstallation {
  app {
    id
    handle
    installation {
      id
      launchUrl
      uninstallUrl
      accessScopes {
        description
        handle
      }
    }
  }
}
"""

# API version query
API_VERSION_QUERY = """
query GetAPIVersion {
  __schema {
    queryType {
      name
    }
  }
}
"""