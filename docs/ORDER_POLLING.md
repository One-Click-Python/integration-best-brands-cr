# Order Polling System (PRIMARY METHOD)

**PRIMARY and RECOMMENDED method** for syncing orders from Shopify to RMS using GraphQL polling. Webhooks are optional/backup.

## Purpose

Order polling is the **default and most reliable method** for syncing orders from Shopify to RMS:
- **Primary Method**: Enabled by default (`ENABLE_ORDER_POLLING=True`, `ENABLE_WEBHOOKS=False`)
- **Detects ALL Changes**: New orders, edited orders (quantity/address changes), and cancelled orders
- **More Reliable**: Automatic retry logic and resilient to network issues
- **Better Observability**: Full statistics, metrics, and monitoring capabilities
- **Smart Update Logic**: Creates new orders, updates existing ones, or marks as cancelled
- **Historical Orders**: Can fetch orders from specific time windows (not just real-time)
- **Full Control**: Control sync timing, frequency, and batch sizes

## Order Sync Methods Comparison

| Feature | Order Polling (PRIMARY) | Webhooks (OPTIONAL) |
|---------|-------------------------|---------------------|
| **Reliability** | High (retry logic) | Medium (can fail silently) |
| **Observability** | Full stats/metrics | Limited visibility |
| **Update Detection** | Detects edits & cancellations | Only new orders |
| **Smart Sync Logic** | Create/Update/Cancel | Create only |
| **Deduplication** | Built-in (SQL check) | Memory-based only |
| **Historical Orders** | Can fetch past orders | Real-time only |
| **Network Resilience** | Resilient (auto retry) | Shopify won't retry |
| **Control** | Full control | Shopify-controlled timing |
| **Default Status** | **ENABLED** | **DISABLED** |
| **Recommendation** | **RECOMMENDED** | Optional backup |

## Architecture

**Components**:
1. **OrderPollingClient** (`app/db/shopify_clients/order_polling_client.py`) - GraphQL client with pagination
2. **OrderPollingService** (`app/services/order_polling_service.py`) - Orchestrator with deduplication
3. **Scheduler Integration** (`app/core/scheduler.py`) - Automatic polling intervals
4. **Repositories** - RMS order existence checking (deduplication)

**Flow** (Enhanced with Update/Cancellation Detection):
1. Scheduler triggers polling every N minutes (configurable)
2. OrderPollingClient fetches orders **updated** in last N minutes (GraphQL `updated_at` filter)
3. OrderRepository checks which orders already exist in RMS (batch query)
4. For each order, ShopifyToRMSSync determines action:
   - **New order** - Create in RMS (`action: "created"`)
   - **Edited order** - Update in RMS (`action: "updated"`)
   - **Cancelled + Exists** - Mark as Closed in RMS (`action: "cancelled"`)
   - **Cancelled + Not exists** - Skip (don't create cancelled orders) (`action: "skipped"`)
5. Statistics tracked: `newly_synced`, `updated`, `sync_errors` persisted to Redis

## Order Update Synchronization (COMPLETE IMPLEMENTATION)

**How Order Updates Are Handled**:

When an order is edited in Shopify (quantities changed, products added/removed, addresses modified), the system performs a **complete and atomic synchronization** to RMS:

### 1. Update Detection (`shopify_to_rms.py:197-276`)

- GraphQL `updated_at` filter catches ALL order modifications
- Existence check via `OrderRepository.find_order_by_shopify_id()`
- Decision tree determines action: `created`, `updated`, `cancelled`, or `skipped`

### 2. Atomic Transaction (`order_creator.py:83-190`)

**ALL operations wrapped in single database transaction** for complete atomicity:

```python
async with self.order_repo.get_session() as session:
    # 1. Update order header (total, tax, customer, etc.)
    # 2. Get existing OrderEntry rows
    # 3. Update existing entries (quantity/price changes)
    # 4. Create new entries (products added)
    # 5. Delete orphaned entries (products removed)
    await session.commit()  # All or nothing
```

**Benefits**:
- **All or nothing**: If any step fails, entire update rolls back
- **No partial updates**: Order always in consistent state
- **Shared session**: Single transaction for all operations

### 3. OrderEntry Operations

**Update Existing Entries** (`order_repository.py:471-516`):
- Detects items present in both Shopify and RMS
- Updates: `Price`, `Quantity`, `FullPrice`, `Description`, etc.
- Logs: `"Updated order entry {entry_id} for item {item_id}"`

**Create New Entries** (`order_repository.py:189-257`):
- Detects items in Shopify but NOT in RMS (products added)
- Creates new `OrderEntry` rows with full data
- Logs: `"Created new order entry for item {item_id}"`

**Delete Orphaned Entries** (`order_repository.py:520-563`, `order_creator.py:174-221`):
- **NEW**: Detects items in RMS but NOT in Shopify (products removed)
- Compares item IDs: `shopify_item_ids` vs `existing_entries`
- Deletes entries no longer in Shopify order
- Logs: `"Deleted orphaned order entry {entry_id} for item {item_id}"`

### 4. Zero-Quantity Filtering (`order_converter.py:244-251`)

Line items with `quantity <= 0` are **automatically skipped** during conversion:

```python
if item_quantity <= 0:
    logger.warning(f"Skipping line item with zero/negative quantity")
    continue
```

**Prevents**:
- Invalid entries with 0 quantity
- Negative quantity errors
- Cancelled line items from being created

### 5. Update Scenarios

| Scenario | Shopify Action | RMS Action | Result |
|----------|---------------|------------|--------|
| **Quantity changed** | Edit order quantity | `UPDATE OrderEntry SET QuantityOnOrder = X` | Quantity updated |
| **Product added** | Add line item | `INSERT INTO OrderEntry (...)` | New entry created |
| **Product removed** | Delete line item | `DELETE FROM OrderEntry WHERE ID = X` | Entry deleted |
| **Price changed** | Edit price | `UPDATE OrderEntry SET Price = X` | Price updated |
| **Customer changed** | Edit billing | `UPDATE [Order] SET CustomerID = X` | Customer updated |
| **Order cancelled** | Cancel order | `UPDATE [Order] SET Closed = 1` | Marked closed |
| **Quantity = 0** | Set qty to 0 | (skipped during conversion) | Not created/updated |

### 6. Rollback on Failure

If ANY operation fails during update:
- **Automatic rollback** via transaction context manager
- **No partial state** in RMS database
- **Error logged** with full context
- **Order remains in previous valid state**

### 7. Code Locations

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Update decision | `shopify_to_rms.py` | 224 | Detect existing orders via find_order_by_shopify_id |
| Atomic transaction | `order_creator.py` | 102 | Wrap all operations in single session |
| Update header | `order_repository.py` | 352-402 | Order table update |
| Get entries | `order_repository.py` | 406-436 | Fetch existing entries |
| Update entry | `order_repository.py` | 471-516 | Update existing line item |
| Create entry | `order_repository.py` | 189-257 | Create new line item |
| **Delete entry** | `order_repository.py` | 520-563 | **Delete removed line item** |
| Zero filter | `order_converter.py` | 244-251 | Skip invalid quantities |
| Orphan deletion | `order_creator.py` | 174-221 | Remove obsolete entries (with shipping special handling) |

## API Endpoints

```bash
GET  /api/v1/orders/polling/status        # Polling status & statistics
POST /api/v1/orders/polling/trigger       # Manual trigger
GET  /api/v1/orders/polling/stats         # Cumulative statistics
POST /api/v1/orders/polling/reset-stats   # Reset statistics
PUT  /api/v1/orders/polling/config        # Update config (runtime)
GET  /api/v1/orders/polling/health        # Health check
```

## Configuration

```bash
# === PRIMARY METHOD: Order Polling (ENABLED BY DEFAULT) ===
ENABLE_ORDER_POLLING=true                      # Enable polling (PRIMARY method)
ORDER_POLLING_INTERVAL_MINUTES=10              # Polling interval (default: 10 min)
ORDER_POLLING_LOOKBACK_MINUTES=15              # Time window to search (default: 15 min, buffer overlap)
ORDER_POLLING_BATCH_SIZE=50                    # Orders per GraphQL page (max 250)
ORDER_POLLING_MAX_PAGES=10                     # Maximum pages per poll (prevents runaway queries)

# === OPTIONAL: Webhooks (DISABLED BY DEFAULT) ===
ENABLE_WEBHOOKS=false                          # Optional backup/complement to polling

# Order Filtering (applies to both polling and webhooks)
ALLOWED_ORDER_FINANCIAL_STATUSES=PAID,PARTIALLY_PAID,AUTHORIZED,PENDING
```

**Why Order Polling is Default**:
- **10-minute delay** is acceptable for most use cases (vs instant webhooks)
- **More reliable** than webhooks (Shopify won't retry failed webhook deliveries)
- **Simpler system** with one sync method vs two potentially conflicting methods
- **Better observability** with full statistics and monitoring
- **Can enable webhooks** later if instant sync needed (set `ENABLE_WEBHOOKS=true`)

## Status Response

**Endpoint**: `GET /api/v1/orders/polling/status`

```json
{
  "status": "success",
  "data": {
    "enabled": true,
    "interval_minutes": 10,
    "lookback_minutes": 15,
    "batch_size": 50,
    "last_poll_time": "2025-01-23T15:30:00+00:00",
    "polling_service_initialized": true,
    "will_execute_next_cycle": false,
    "seconds_until_next_poll": 420,
    "webhooks_enabled": true,
    "status": "waiting_for_interval",
    "statistics": {
      "total_polled": 1247,
      "already_synced": 1100,
      "newly_synced": 120,
      "updated": 25,
      "sync_errors": 2,
      "success_rate": 98.6,
      "last_poll_time": "2025-01-23T15:30:00+00:00"
    }
  }
}
```

## Manual Trigger

**Endpoint**: `POST /api/v1/orders/polling/trigger`

**Request** (all fields optional):
```json
{
  "lookback_minutes": 30,
  "batch_size": 50,
  "max_pages": 10,
  "dry_run": false
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "status": "success",
    "timestamp": "2025-01-23T15:35:00+00:00",
    "duration_seconds": 12.45,
    "message": "Polling complete: 25/28 orders synced",
    "statistics": {
      "total_polled": 28,
      "already_synced": 3,
      "newly_synced": 25,
      "sync_errors": 0,
      "success_rate": 100.0
    }
  }
}
```

## Testing & Verification

**Test Script**: `scripts/test_order_polling.py`

```bash
# Dry-run (only check, don't sync)
python scripts/test_order_polling.py --dry-run

# Normal polling (last 15 minutes)
python scripts/test_order_polling.py

# Custom lookback window
python scripts/test_order_polling.py --lookback 60

# Custom configuration
python scripts/test_order_polling.py --lookback 30 --batch-size 50 --max-pages 5

# View statistics only
python scripts/test_order_polling.py --stats-only

# Reset statistics before polling
python scripts/test_order_polling.py --reset-stats
```

## Features

- **Deduplication**: Batch checking prevents duplicate orders in RMS
- **Pagination**: Handles large order volumes with cursor pagination
- **Financial Status Filtering**: Only syncs configured order statuses
- **Statistics Tracking**: Cumulative metrics with error aggregation
- **Redis Persistence**: State survives application restarts
- **Dry-Run Support**: Test without making changes
- **Parallel with Webhooks**: Can run simultaneously for redundancy

## Troubleshooting

**Issue**: Polling not executing
- Check: `ENABLE_ORDER_POLLING=true` in `.env`
- Check: Scheduler is running (`GET /api/v1/sync/monitor/status`)
- Check: Redis connectivity
- Check: Logs for errors

**Issue**: Duplicate orders
- Check: Deduplication is working (logs show "already in RMS")
- Check: RMS database connectivity
- Check: Order repository queries

**Issue**: Missing orders
- Increase: `ORDER_POLLING_LOOKBACK_MINUTES` (e.g., 30 or 60)
- Check: Financial status filters in configuration
- Check: Shopify order timestamps vs polling window
- Use: Manual trigger with custom lookback

**Issue**: High resource usage
- Decrease: `ORDER_POLLING_BATCH_SIZE` (e.g., 25 instead of 50)
- Decrease: `ORDER_POLLING_MAX_PAGES` (e.g., 5 instead of 10)
- Increase: `ORDER_POLLING_INTERVAL_MINUTES` (e.g., 15 or 30)

## Best Practices

1. **Polling + Webhooks**: Enable both for maximum reliability
2. **Lookback Buffer**: Set lookback > interval (e.g., 15 min lookback, 10 min interval)
3. **Financial Filters**: Only sync orders in desired states (avoid TEST, VOIDED)
4. **Monitor Statistics**: Check success rates and error counts regularly
5. **Test First**: Always dry-run before production changes
