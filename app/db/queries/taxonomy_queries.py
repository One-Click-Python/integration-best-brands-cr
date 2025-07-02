"""
GraphQL queries for Shopify Taxonomy operations.

This module contains all GraphQL queries related to Shopify's Standard Product Taxonomy,
including category searches, browsing, and detailed taxonomy information.
"""

# Taxonomy Queries
TAXONOMY_CATEGORIES_QUERY = """
query GetTaxonomyCategories($search: String) {
  taxonomy {
    categories(search: $search, first: 50) {
      edges {
        node {
          id
          name
          fullName
        }
      }
    }
  }
}
"""

# Enhanced taxonomy query with full details
TAXONOMY_CATEGORY_DETAILS_QUERY = """
query GetTaxonomyCategoryDetails($categoryId: ID!) {
  taxonomy {
    category(id: $categoryId) {
      id
      name
      fullName
      isRoot
      isLeaf
      level
      attributes {
        id
        name
        choices
      }
      ancestors {
        id
        name
        fullName
      }
      children {
        id
        name
        fullName
      }
    }
  }
}
"""

# Query to browse taxonomy categories by level
TAXONOMY_BROWSE_QUERY = """
query BrowseTaxonomyCategories($parentId: ID, $first: Int = 50) {
  taxonomy {
    categories(parentId: $parentId, first: $first) {
      edges {
        node {
          id
          name
          fullName
          isLeaf
          level
          childrenCount
        }
      }
    }
  }
}
"""