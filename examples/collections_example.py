#!/usr/bin/env python3
"""
Example script showing how to use the Shopify Collections GraphQL functionality.

This example demonstrates:
1. Basic connection and authentication
2. Fetching all collections with pagination
3. Fetching a specific collection by handle or ID
4. Processing collection data including products, metafields, and rules
5. Error handling and proper resource cleanup

Usage:
    python examples/collections_example.py

Make sure your .env file contains:
    SHOPIFY_SHOP_URL=your-shop.myshopify.com
    SHOPIFY_ACCESS_TOKEN=your_access_token
    SHOPIFY_API_VERSION=2025-04
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.db.shopify_client import get_graphql_client


async def demonstrate_collections_api():
    """Demonstrate various collections API operations."""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Get the GraphQL client
    client = get_graphql_client()
    
    try:
        # Initialize the client
        logger.info("🔄 Initializing Shopify GraphQL client...")
        await client.initialize()
        
        # Test connection
        logger.info("🔄 Testing connection...")
        if not await client.test_connection():
            logger.error("❌ Failed to connect to Shopify. Check your credentials.")
            return
        
        logger.info("✅ Connected to Shopify successfully!")
        
        # Example 1: Fetch first page of collections
        logger.info("\n📋 Example 1: Fetching first page of collections (limit 5)")
        try:
            result = await client.get_collections(limit=5)
            collections = result.get("collections", [])
            
            logger.info(f"Found {len(collections)} collections on first page")
            for i, collection in enumerate(collections[:3], 1):  # Show first 3
                logger.info(f"  {i}. {collection.get('title')} - {collection.get('productsCount')} products")
        
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
        
        # Example 2: Fetch all collections (be careful with large stores!)
        logger.info("\n📋 Example 2: Fetching all collections")
        try:
            all_collections = await client.get_all_collections()
            logger.info(f"Total collections in store: {len(all_collections)}")
            
            # Show some statistics
            if all_collections:
                total_products = sum(c.get("productsCount", 0) for c in all_collections)
                avg_products = total_products / len(all_collections) if all_collections else 0
                logger.info(f"Total products across all collections: {total_products}")
                logger.info(f"Average products per collection: {avg_products:.1f}")
                
                # Show collections with most products
                sorted_collections = sorted(all_collections, key=lambda x: x.get("productsCount", 0), reverse=True)
                logger.info("\nTop 3 collections by product count:")
                for i, collection in enumerate(sorted_collections[:3], 1):
                    logger.info(f"  {i}. {collection.get('title')} - {collection.get('productsCount')} products")
        
        except Exception as e:
            logger.error(f"Error fetching all collections: {e}")
        
        # Example 3: Try to fetch a specific collection by handle
        logger.info("\n📋 Example 3: Fetching collection by handle (if exists)")
        test_handles = ["featured", "all", "frontpage", "sale", "new"]  # Common handles
        
        for handle in test_handles:
            try:
                collection = await client.get_collection_by_handle(handle)
                if collection:
                    logger.info(f"✅ Found collection '{handle}': {collection.get('title')}")
                    logger.info(f"   Description: {collection.get('description', 'No description')[:100]}...")
                    logger.info(f"   Products: {collection.get('productsCount')}")
                    
                    # Show collection rules if it's a smart collection
                    rules = collection.get("rules", [])
                    if rules:
                        logger.info(f"   Smart collection with {len(rules)} rules:")
                        for rule in rules[:2]:  # Show first 2 rules
                            logger.info(f"     - {rule.get('field')} {rule.get('relation')} {rule.get('condition')}")
                    
                    # Show sample products
                    products = collection.get("products", {}).get("edges", [])
                    if products:
                        logger.info(f"   Sample products:")
                        for product_edge in products[:2]:  # Show first 2 products
                            product = product_edge.get("node", {})
                            logger.info(f"     - {product.get('title')}")
                    
                    break  # Found one, stop looking
                else:
                    logger.info(f"   Collection '{handle}' not found")
            
            except Exception as e:
                logger.error(f"Error fetching collection '{handle}': {e}")
        
        # Example 4: Show collection details
        if all_collections:
            logger.info("\n📋 Example 4: Detailed view of first collection")
            first_collection = all_collections[0]
            
            logger.info(f"Collection: {first_collection.get('title')}")
            logger.info(f"Handle: {first_collection.get('handle')}")
            logger.info(f"ID: {first_collection.get('id')}")
            logger.info(f"Created: {first_collection.get('createdAt')}")
            logger.info(f"Updated: {first_collection.get('updatedAt')}")
            logger.info(f"Sort Order: {first_collection.get('sortOrder')}")
            
            # SEO information
            seo = first_collection.get("seo", {})
            if seo:
                logger.info(f"SEO Title: {seo.get('title', 'N/A')}")
                logger.info(f"SEO Description: {seo.get('description', 'N/A')}")
            
            # Image information
            image = first_collection.get("image")
            if image:
                logger.info(f"Image URL: {image.get('url')}")
                logger.info(f"Image Alt Text: {image.get('altText', 'N/A')}")
            
            # Metafields
            metafields = first_collection.get("metafields", {}).get("edges", [])
            if metafields:
                logger.info(f"Metafields ({len(metafields)}):")
                for mf_edge in metafields[:3]:  # Show first 3
                    mf = mf_edge.get("node", {})
                    logger.info(f"  - {mf.get('namespace')}.{mf.get('key')}: {mf.get('value')}")
        
        logger.info("\n✅ Collections API demonstration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        
    finally:
        # Always clean up the client
        logger.info("🔄 Cleaning up client...")
        await client.close()
        logger.info("✅ Client closed successfully")


if __name__ == "__main__":
    print("🛍️  Shopify Collections API Example")
    print("=" * 50)
    
    try:
        asyncio.run(demonstrate_collections_api())
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)