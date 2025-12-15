# Reverse Stock Sync (Shopify to RMS Inventory)

**Complementary inventory synchronization** ensuring complete accuracy by catching products missed in the main RMS-Shopify sync.

## Purpose

Reverse Stock Sync is a **complementary system** that synchronizes inventory **from Shopify to RMS** for products that weren't updated in the primary sync:
- **Finds Unsynced Products**: Queries Shopify for products WITHOUT today's sync tag
- **Queries RMS Stock**: Gets current inventory quantities from RMS (source of truth)
- **Updates Shopify**: Synchronizes inventory to match RMS
- **Deletes Zero Stock**: Optionally removes variants with zero inventory
- **Prevents Reprocessing**: Tags processed products to avoid infinite loops

## Architecture

**Components**:
1. **ReverseStockSynchronizer** (`app/services/reverse_stock_sync.py:34`) - Main sync orchestrator
2. **ProductLock** - Distributed locking to prevent concurrent processing
3. **ShopifyGraphQLClient** - API communication with batch operations
4. **ProductRepository** - RMS stock queries by CCOD

**Flow** (4-Phase Atomic Process):
1. **Discovery Phase**: Query products WITHOUT today's sync tag (e.g., "RMS-SYNC-25-01-23")
2. **Analysis Phase**: For each product, extract CCOD and query RMS stock
3. **Synchronization Phase**: Batch update inventory + delete zero-stock variants
4. **Tagging Phase**: Mark product with sync tag to prevent reprocessing

## Key Features

- **Parallel Processing**: Concurrent product processing with semaphore control (max 10 concurrent workers)
- **Distributed Locking**: Prevents race conditions between concurrent syncs
- **Batch Operations**: Efficient inventory updates using Shopify bulk mutations
- **Rollback Support**: Automatic rollback on partial failures
- **Safety Validations**: Prevents deletion of variants with incoming inventory
- **Dry-Run Mode**: Test without making changes
- **Performance Metrics**: Throughput tracking (products/s, variants/s)
- **Tag-Based Tracking**: Prevents infinite reprocessing loops

## Configuration

```bash
# Reverse Stock Sync Configuration
ENABLE_REVERSE_STOCK_SYNC=true                    # Enable reverse sync (default: true)
REVERSE_SYNC_DELAY_MINUTES=5                      # Delay after RMS sync (default: 5 min)
REVERSE_SYNC_DELETE_ZERO_STOCK=true               # Delete zero-stock variants (default: true)
REVERSE_SYNC_BATCH_SIZE=50                        # Products per batch (default: 50, max: 250)
REVERSE_SYNC_PRESERVE_SINGLE_VARIANT=true         # Don't delete if it's the only variant (default: true)
REVERSE_SYNC_MAX_CONCURRENT=10                    # Max concurrent workers (default: 10)
```

## API Endpoints

```bash
# Execute reverse stock sync
POST /api/v1/reverse-stock-sync/
{
  "dry_run": false,
  "delete_zero_stock": true,
  "batch_size": 50,
  "limit": null,
  "max_concurrent": 10
}

# Get status of last sync
GET /api/v1/reverse-stock-sync/status

# Get current configuration
GET /api/v1/reverse-stock-sync/config

# Dry-run (simulation only, limit 10 products)
POST /api/v1/reverse-stock-sync/dry-run?limit=10
```

## Sync Process Details

### Phase 1: Discovery
**File**: `app/services/reverse_stock_sync.py:192`

1. Generate today's sync tag (e.g., "RMS-SYNC-25-01-23")
2. Query Shopify GraphQL API: `products(query: "-tag:RMS-SYNC-25-01-23")`
3. Paginate through all results (cursor-based)
4. Extract product data including variants and metafields

### Phase 2: CCOD Extraction & Stock Query
**File**: `app/services/reverse_stock_sync.py:408-464`

1. Extract CCOD from metafields (namespace: `rms`, key: `ccod`)
2. Query RMS: `ProductRepository.get_products_by_ccod(ccod)`
3. Build SKU to Quantity mapping (case-insensitive)
4. Normalize negative quantities to 0

### Phase 3: Synchronization (Atomic with Rollback)
**File**: `app/services/reverse_stock_sync.py:327-401`

**Sub-Phase 3.1 - Analysis**:
- Compare Shopify quantities vs RMS quantities
- Identify variants to update (qty differs)
- Identify variants to delete (RMS qty = 0)
- Prepare batch operations

**Sub-Phase 3.2 - Batch Inventory Update**:
- Execute bulk inventory mutation (all updates in single API call)
- Track successful updates for rollback
- Log errors for failed updates

**Sub-Phase 3.3 - Safe Variant Deletion**:
- **Validation**: Check for incoming inventory, recent orders
- **Safety**: Skip if it's the only variant (configurable)
- **Execution**: Delete using productVariantsBulkDelete mutation
- **Audit**: Log all deletions with SKU and reason

**Sub-Phase 3.4 - Rollback on Failure**:
- If ANY operation fails, revert ALL inventory updates
- Uses LIFO (Last In First Out) rollback order
- Logs rollback success/failure separately

### Phase 4: Tag Marking
**File**: `app/services/reverse_stock_sync.py:708-772`

1. Add today's sync tag to product (e.g., "RMS-SYNC-25-01-23")
2. Prevents reprocessing in future runs
3. Only marks if sync was successful
4. Skip if tag already exists

## Distributed Locking

**Purpose**: Prevent concurrent processing of same product

**File**: `app/services/reverse_stock_sync.py:264-276`

```python
async with ProductLock(product_id=product_id, timeout_seconds=300):
    await self._process_product_locked(product, dry_run, delete_zero_stock)
```

**Behavior**:
- **Lock Acquired**: Process product normally
- **Lock Failed**: Skip product (already being processed by another sync)
- **Timeout**: 5 minutes (300 seconds) max lock duration
- **Auto-Release**: Lock released automatically on completion or exception

## Safety Validations

**Delete Variant Validation** (`app/services/reverse_stock_sync.py:554-605`):

| Check | Action | Reason |
|-------|--------|--------|
| **Incoming Inventory > 0** | Skip deletion | Stock arriving, variant will be active soon |
| **Only Variant Remaining** | Skip deletion (if `PRESERVE_SINGLE_VARIANT=true`) | Prevents orphaned products |
| **Recent Orders** | Skip deletion | Variant recently sold, may have returns/exchanges |
| **Validation Error** | Skip deletion | Conservative approach: preserve on uncertainty |

## Performance

**Parallel Processing**:
- Configurable concurrent workers (default: 10)
- Semaphore-controlled concurrency
- Rate limiting (0.5s delay between GraphQL pages)

**Batch Operations**:
- Single bulk mutation for all inventory updates
- Reduces API calls by ~90%
- Improves throughput to 5-10 products/second

**Metrics Tracked**:
- Products checked, variants checked
- Variants updated, variants deleted
- Throughput (products/s, variants/s)
- Average time per product
- Success rate percentage

## Response Format

```json
{
  "success": true,
  "message": "Reverse sync completed successfully - 98.6% success rate",
  "sync_id": "reverse_stock_20250123_153000",
  "report": {
    "timestamp": "2025-01-23T15:35:00+00:00",
    "duration_seconds": 45.23,
    "statistics": {
      "products_checked": 125,
      "variants_checked": 450,
      "variants_updated": 320,
      "variants_deleted": 15,
      "errors": 5,
      "skipped": 110,
      "products_without_ccod": 10,
      "products_with_ccod": 115
    },
    "performance": {
      "throughput_products_per_second": 2.76,
      "throughput_variants_per_second": 9.95,
      "avg_time_per_product_seconds": 0.362,
      "max_concurrent_workers": 10,
      "parallel_processing_enabled": true,
      "batch_operations_enabled": true
    },
    "details": {
      "updated": [{"sku": "24X104-37", "old_qty": 5, "new_qty": 3}],
      "deleted": [{"sku": "24X104-45", "reason": "zero_stock"}],
      "errors": [],
      "rollbacks": 0,
      "rollback_failures": 0,
      "deletion_validation_failures": []
    }
  }
}
```

## Troubleshooting

**Issue**: Products not being synced
- Check: Today's sync tag format matches main sync (variant_mapper.py)
- Check: CCOD metafield exists (namespace: `rms`, key: `ccod`)
- Check: RMS connectivity and product queries
- Try: Dry-run to see which products would be processed

**Issue**: Variants not being deleted
- Check: `REVERSE_SYNC_DELETE_ZERO_STOCK=true`
- Check: Not the only variant (or `PRESERVE_SINGLE_VARIANT=false`)
- Check: No incoming inventory
- Review: `deletion_validation_failures` in report

**Issue**: High error rate
- Check: Shopify API rate limits (reduce `max_concurrent`)
- Check: RMS database connectivity
- Review: Error details in response
- Try: Smaller batch size (e.g., 25 instead of 50)

**Issue**: Lock acquisition failures
- Reduce: `REVERSE_SYNC_MAX_CONCURRENT` to avoid congestion
- Check: Redis connectivity (locks stored in Redis)
- Increase: Lock timeout if products take longer to process

## Best Practices

1. **Run After Main Sync**: Set `REVERSE_SYNC_DELAY_MINUTES` to allow main sync to complete
2. **Use Dry-Run First**: Test with `/dry-run?limit=10` before production
3. **Monitor Success Rate**: Aim for >=95% success rate
4. **Review Deletion Logs**: Audit all variant deletions
5. **Coordinate with Order Polling**: Ensure both syncs don't conflict
6. **Check Lock Status**: Monitor lock acquisition failures
