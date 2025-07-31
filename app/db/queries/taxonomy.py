"""
Taxonomy-related GraphQL queries.

This module contains product taxonomy operations:
- Standard Product Taxonomy queries
- Category browsing and search
- Taxonomy hierarchy navigation
"""

# Product taxonomy categories query
TAXONOMY_CATEGORIES_QUERY = """
query GetTaxonomyCategories($query: String!) {
  productTaxonomyNodes(first: 50, query: $query) {
    edges {
      node {
        id
        name
        fullName
        isLeaf
        isRoot
        level
        childrenCount
        parentId
        ancestors(first: 10) {
          id
          name
          level
        }
        children(first: 20) {
          id
          name
          fullName
          isLeaf
          childrenCount
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

# Taxonomy category details query
TAXONOMY_CATEGORY_DETAILS_QUERY = """
query GetTaxonomyCategoryDetails($id: ID!) {
  productTaxonomyNode(id: $id) {
    id
    name
    fullName
    isLeaf
    isRoot
    level
    childrenCount
    parentId
    ancestors(first: 20) {
      id
      name
      fullName
      level
    }
    children(first: 50) {
      id
      name
      fullName
      isLeaf
      childrenCount
      children(first: 10) {
        id
        name
        fullName
        isLeaf
      }
    }
    parent {
      id
      name
      fullName
      level
    }
  }
}
"""

# Browse taxonomy hierarchy
TAXONOMY_BROWSE_QUERY = """
query BrowseTaxonomy($first: Int = 50) {
  productTaxonomyNodes(first: $first, query: "level:1") {
    edges {
      node {
        id
        name
        fullName
        level
        childrenCount
        children(first: 20) {
          id
          name
          fullName
          level
          childrenCount
          isLeaf
          children(first: 10) {
            id
            name
            fullName
            level
            isLeaf
            childrenCount
          }
        }
      }
    }
  }
}
"""