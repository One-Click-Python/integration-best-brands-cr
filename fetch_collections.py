#!/usr/bin/env python3
"""
Shopify Collections Fetcher Script

This script fetches all collections from Shopify using the existing GraphQL client
and displays them in a readable format. It demonstrates proper usage of the
ShopifyGraphQLClient with comprehensive collection data including:

- Collection metadata (id, title, handle, description)
- SEO information
- Product counts and sample products
- Collection rules and sorting
- Custom metafields
- Image information

Usage:
    python fetch_collections.py [options]

Options:
    --format {table,json,detailed}    Output format (default: detailed)
    --limit N                         Limit number of collections to display
    --export FILE                     Export results to JSON file
    --verbose                         Enable verbose logging
    --handle HANDLE                   Fetch specific collection by handle
    --id ID                          Fetch specific collection by ID

Examples:
    python fetch_collections.py
    python fetch_collections.py --format table --limit 10
    python fetch_collections.py --handle "featured-products"
    python fetch_collections.py --export collections.json --verbose
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.db.shopify_client import get_graphql_client


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def format_collection_table(collections: List[Dict[str, Any]]) -> str:
    """Format collections as a simple table."""
    if not collections:
        return "No collections found."
    
    # Calculate column widths
    max_title = max(len(c.get("title", "")) for c in collections)
    max_handle = max(len(c.get("handle", "")) for c in collections)
    max_title = min(max_title, 40)  # Limit width
    max_handle = min(max_handle, 30)
    
    # Header
    header = f"{'Title':<{max_title}} | {'Handle':<{max_handle}} | {'Products':>8} | {'Updated':<19}"
    separator = "-" * len(header)
    
    lines = [header, separator]
    
    for collection in collections:
        title = (collection.get("title", "N/A")[:max_title-3] + "...") if len(collection.get("title", "")) > max_title else collection.get("title", "N/A")
        handle = (collection.get("handle", "N/A")[:max_handle-3] + "...") if len(collection.get("handle", "")) > max_handle else collection.get("handle", "N/A")
        products_count = collection.get("productsCount", {}).get("count", 0) if isinstance(collection.get("productsCount"), dict) else collection.get("productsCount", 0)
        updated_at = collection.get("updatedAt", "")[:19] if collection.get("updatedAt") else "N/A"
        
        line = f"{title:<{max_title}} | {handle:<{max_handle}} | {products_count:>8} | {updated_at:<19}"
        lines.append(line)
    
    return "\n".join(lines)


def format_collection_detailed(collections: List[Dict[str, Any]]) -> str:
    """Format collections with detailed information."""
    if not collections:
        return "No collections found."
    
    lines = []
    
    for i, collection in enumerate(collections, 1):
        lines.append(f"\n{'='*80}")
        lines.append(f"Collection #{i}: {collection.get('title', 'N/A')}")
        lines.append(f"{'='*80}")
        
        # Basic information
        lines.append(f"ID: {collection.get('id', 'N/A')}")
        lines.append(f"Handle: {collection.get('handle', 'N/A')}")
        products_count = collection.get("productsCount", {}).get("count", 0) if isinstance(collection.get("productsCount"), dict) else collection.get("productsCount", 0)
        lines.append(f"Products Count: {products_count}")
        lines.append(f"Created: {collection.get('createdAt', 'N/A')}")
        lines.append(f"Updated: {collection.get('updatedAt', 'N/A')}")
        lines.append(f"Sort Order: {collection.get('sortOrder', 'N/A')}")
        
        # Description
        if collection.get("description"):
            desc = collection["description"][:200] + "..." if len(collection["description"]) > 200 else collection["description"]
            lines.append(f"Description: {desc}")
        
        # SEO information
        seo = collection.get("seo", {})
        if seo:
            lines.append(f"SEO Title: {seo.get('title', 'N/A')}")
            if seo.get("description"):
                seo_desc = seo["description"][:150] + "..." if len(seo["description"]) > 150 else seo["description"]
                lines.append(f"SEO Description: {seo_desc}")
        
        # Image information
        image = collection.get("image")
        if image:
            lines.append(f"Image: {image.get('url', 'N/A')}")
            if image.get("altText"):
                lines.append(f"Image Alt: {image['altText']}")
        
        # Collection rules
        rules = collection.get("rules", [])
        if rules:
            lines.append("Collection Rules:")
            for rule in rules[:5]:  # Limit to first 5 rules
                lines.append(f"  - {rule.get('field', 'N/A')} {rule.get('relation', 'N/A')} {rule.get('condition', 'N/A')}")
        
        # Sample products
        products = collection.get("products", {}).get("edges", [])
        if products:
            lines.append("Sample Products:")
            for product_edge in products[:3]:  # Show first 3 products
                product = product_edge.get("node", {})
                lines.append(f"  - {product.get('title', 'N/A')} ({product.get('handle', 'N/A')})")
        
        # Metafields
        metafields = collection.get("metafields", {}).get("edges", [])
        if metafields:
            lines.append("Metafields:")
            for mf_edge in metafields[:5]:  # Show first 5 metafields
                mf = mf_edge.get("node", {})
                lines.append(f"  - {mf.get('namespace', 'N/A')}.{mf.get('key', 'N/A')}: {mf.get('value', 'N/A')}")
    
    return "\n".join(lines)


def format_collection_json(collections: List[Dict[str, Any]], pretty: bool = True) -> str:
    """Format collections as JSON."""
    if pretty:
        return json.dumps(collections, indent=2, ensure_ascii=False)
    else:
        return json.dumps(collections, ensure_ascii=False)


async def fetch_all_collections(client, logger: logging.Logger, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch all collections using the GraphQL client."""
    logger.info("Starting to fetch all collections from Shopify...")
    
    try:
        # Initialize the client
        await client.initialize()
        
        # Test connection first
        logger.info("Testing Shopify connection...")
        if not await client.test_connection():
            logger.error("Failed to connect to Shopify. Please check your credentials.")
            return []
        
        logger.info("Connection successful! Fetching collections...")
        
        # Fetch all collections
        all_collections = await client.get_all_collections()
        
        # Apply limit if specified
        if limit and limit > 0:
            all_collections = all_collections[:limit]
            logger.info(f"Limited results to {len(all_collections)} collections")
        
        logger.info(f"Successfully fetched {len(all_collections)} collections")
        return all_collections
        
    except Exception as e:
        logger.error(f"Error fetching collections: {e}")
        return []
    finally:
        # Clean up the client
        await client.close()


async def fetch_collection_by_handle(client, handle: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """Fetch a specific collection by handle."""
    logger.info(f"Fetching collection by handle: {handle}")
    
    try:
        await client.initialize()
        
        if not await client.test_connection():
            logger.error("Failed to connect to Shopify. Please check your credentials.")
            return None
        
        collection = await client.get_collection_by_handle(handle)
        if collection:
            logger.info(f"Found collection: {collection.get('title')}")
        else:
            logger.warning(f"Collection not found with handle: {handle}")
        
        return collection
        
    except Exception as e:
        logger.error(f"Error fetching collection by handle: {e}")
        return None
    finally:
        await client.close()


async def fetch_collection_by_id(client, collection_id: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """Fetch a specific collection by ID."""
    logger.info(f"Fetching collection by ID: {collection_id}")
    
    try:
        await client.initialize()
        
        if not await client.test_connection():
            logger.error("Failed to connect to Shopify. Please check your credentials.")
            return None
        
        collection = await client.get_collection_by_id(collection_id)
        if collection:
            logger.info(f"Found collection: {collection.get('title')}")
        else:
            logger.warning(f"Collection not found with ID: {collection_id}")
        
        return collection
        
    except Exception as e:
        logger.error(f"Error fetching collection by ID: {e}")
        return None
    finally:
        await client.close()


def export_to_file(data: List[Dict[str, Any]], filename: str, logger: logging.Logger) -> bool:
    """Export collections data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "exported_at": datetime.now().isoformat(),
                "total_collections": len(data),
                "collections": data
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Collections exported to: {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to export to {filename}: {e}")
        return False


async def main():
    """Main function to handle CLI arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="Fetch and display Shopify collections using GraphQL API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Fetch all collections (detailed format)
  %(prog)s --format table --limit 10    # Show 10 collections as table
  %(prog)s --handle "summer-collection"  # Fetch specific collection by handle
  %(prog)s --id "gid://shopify/Collection/123"  # Fetch by ID
  %(prog)s --export collections.json    # Export to JSON file
        """
    )
    
    parser.add_argument(
        "--format",
        choices=["table", "json", "detailed"],
        default="detailed",
        help="Output format (default: detailed)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of collections to display"
    )
    
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export results to JSON file"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--handle",
        help="Fetch specific collection by handle"
    )
    
    parser.add_argument(
        "--id",
        help="Fetch specific collection by ID"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    # Get the GraphQL client
    client = get_graphql_client()
    
    try:
        collections = []
        
        # Determine what to fetch
        if args.handle:
            collection = await fetch_collection_by_handle(client, args.handle, logger)
            if collection:
                collections = [collection]
        elif args.id:
            collection = await fetch_collection_by_id(client, args.id, logger)
            if collection:
                collections = [collection]
        else:
            collections = await fetch_all_collections(client, logger, args.limit)
        
        if not collections:
            print("No collections found or error occurred.")
            return 1
        
        # Format and display results
        if args.format == "table":
            output = format_collection_table(collections)
        elif args.format == "json":
            output = format_collection_json(collections)
        else:  # detailed
            output = format_collection_detailed(collections)
        
        print(output)
        
        # Export if requested
        if args.export:
            if export_to_file(collections, args.export, logger):
                print(f"\nResults exported to: {args.export}")
            else:
                print(f"\nFailed to export to: {args.export}")
                return 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Summary: Found {len(collections)} collection(s)")
        if collections:
            total_products = sum(c.get("productsCount", {}).get("count", 0) if isinstance(c.get("productsCount"), dict) else c.get("productsCount", 0) for c in collections)
            print(f"Total products across all collections: {total_products}")
        print(f"{'='*60}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))