"""
Taxonomy-related GraphQL queries.

This module contains product taxonomy operations:
- Standard Product Taxonomy queries
- Category browsing and search
- Taxonomy hierarchy navigation
"""

# Product taxonomy categories query
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

# Taxonomy category details query
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

# Browse taxonomy hierarchy
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
