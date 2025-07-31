# Shopify GraphQL Examples

This directory contains example scripts demonstrating how to use the Shopify GraphQL client functionality.

## Available Examples

### `collections_example.py`
Demonstrates how to use the collections API functionality:
- Fetching all collections with pagination
- Fetching specific collections by handle or ID
- Processing collection data including products, metafields, and rules
- Error handling and proper resource cleanup

**Usage:**
```bash
cd /path/to/rms-shopify-integration
python examples/collections_example.py
```

## Requirements

Make sure your `.env` file contains the required Shopify credentials:

```env
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token
SHOPIFY_API_VERSION=2025-04
```

## Running Examples

All examples can be run from the project root directory:

```bash
# Run collections example
python examples/collections_example.py

# Or make them executable and run directly
chmod +x examples/collections_example.py
./examples/collections_example.py
```

## Adding New Examples

When creating new examples:

1. Follow the existing pattern of importing from the parent app directory
2. Include proper error handling and resource cleanup
3. Add comprehensive logging to show what's happening
4. Document the example in this README
5. Make the script executable with `chmod +x`