# Automatic Shipping Cost OrderEntry

**Purpose**: Automatically create OrderEntry records for shipping costs when syncing Shopify orders to RMS.

## Overview

When orders are synced from Shopify to RMS, the system **creates a shipping cost OrderEntry ONLY when the order has shipping charges (> 0)** using a designated shipping item from VIEW_Items (ItemID=481461 by default). This ensures complete order tracking including shipping charges.

**Key Features**:
- **Conditional Creation**: Shipping entry created ONLY when shipping > 0
- **Tax Calculation**: Properly discriminates and re-applies tax from VIEW_Items
- **Update Support**: Handles shipping amount changes in order updates
- **Zero Handling**: Updates existing entry to 0 when shipping removed (not deleted)
- **Error Resilience**: Logs warning and continues if shipping item not found
- **Caching**: Shipping item data cached to avoid repeated queries

## Configuration

```bash
# Environment Variable (.env)
SHIPPING_ITEM_ID=481461  # ItemID from VIEW_Items for shipping costs
```

**Settings** (`app/core/config.py:171`):
```python
SHIPPING_ITEM_ID: int = Field(
    default=481461,
    env="SHIPPING_ITEM_ID",
    description="ItemID de VIEW_Items para costos de envio (OrderEntry automatico)"
)
```

## How It Works

### 1. Order Creation Flow
**File**: `app/services/orders/converters/order_converter.py:130-149`

1. Extract shipping charge from Shopify order (`shippingLine.currentDiscountedPriceSet`)
2. **Check if shipping > 0**: Only proceed if order has shipping charges
3. **If shipping > 0**: Call `_create_shipping_entry()` to create shipping OrderEntry
4. Query shipping item from VIEW_Items (ItemID=481461) with caching
5. Calculate tax using discrimination formula from VIEW_Items
6. Create OrderEntryDomain with shipping data
7. Add to `entries_with_tax_info` for Order.Tax calculation
8. Shipping entry included in Order.Total and Order.Tax
9. **If shipping = 0**: Skip entry creation, log info message

### 2. Tax Calculation Formula
**File**: `app/services/orders/converters/order_converter.py:454-468`

```python
# Given: Shopify shipping WITH tax (e.g., 11,300)
# Step 1: Get tax percentage from VIEW_Items (e.g., 13%)
tax_percentage = Decimal("13") / Decimal("100")  # 0.13

# Step 2: Discriminate to remove tax
shipping_without_tax = shipping_with_tax / (Decimal("1") + tax_percentage)
# 11,300 / 1.13 = 10,000

# Step 3: Re-apply tax for consistency
calculated_with_tax = shipping_without_tax * (Decimal("1") + tax_percentage)
# 10,000 * 1.13 = 11,300

# Step 4: Create Money object (auto-rounds to 2 decimals)
price_money = Money(calculated_with_tax, "CRC")  # 11,300.00
```

### 3. OrderEntry Fields
**Created Entry** (Open Order Pattern for Shipping):
```python
OrderEntryDomain(
    item_id=481461,              # Shipping item from VIEW_Items
    store_id=40,                 # Virtual store
    price=Money("11300.00"),     # Price WITH 13% tax
    full_price=Money("11300.00"), # Same as price (no promotion for shipping)
    cost=Money("0.00"),          # Usually 0 for shipping
    quantity_on_order=1.0,       # 1.0 for shipping (reserved for order)
    quantity_rtd=0.0,            # 0.0 for shipping (pending fulfillment)
    description="ENVIO",         # From VIEW_Items.Description
    taxable=True,                # Usually True (shipping taxable in CR)
    sales_rep_id=1000,
    comment="Shipping Item",     # Identifies this as shipping
    price_source=10,             # 10 charges Price*(1+tax%), 1 is standard
    # ... other standard fields
)
```

## Inventory Reservation Logic

Shipping entries now use the same **"open order" logic** as product entries:

- **QuantityOnOrder = 1.0**: Reserved for order (pending fulfillment)
- **QuantityRTD = 0.0**: Not yet ready to deliver
- **Previous behavior**: Used POS logic (OnOrder=0, RTD=1) for immediate pickup

This change aligns shipping entries with product entries, ensuring consistent order processing workflow across all items.

**Important RMS Pattern**:
- `quantity_on_order=1.0` - Reserved for order (pending fulfillment)
- `quantity_rtd=0.0` - Not yet ready to deliver
- `comment="Shipping Item"` - Text identifier for shipping entries
- `price_source=10` - Tells RMS to charge `Price*(1+(Tax/100))`

### 4. Tax Calculation with Shipping
**File**: `app/services/orders/converters/order_converter.py:158-189`

The tax calculation loop now treats all entries (products and shipping) uniformly:

```python
for entry, tax_percentage in entries_with_tax_info:
    # All entries (products and shipping) now use quantity_on_order for calculation
    # This follows the "open order" logic: OnOrder=1.0, RTD=0.0 (pending fulfillment)
    quantity_for_calc = entry.quantity_on_order

    # Calculate: 11,300.00 * 1.0 = 11,300.00
    subtotal_with_tax = entry.price.amount * Decimal(str(quantity_for_calc))

    # Discriminate tax and add to Order.Tax
    tax_divisor = Decimal("1") + (tax_percentage / Decimal("100"))
    subtotal_without_tax = subtotal_with_tax / tax_divisor
    tax_item = subtotal_with_tax - subtotal_without_tax
    total_tax += tax_item  # Shipping tax INCLUDED
```

**Simplified Logic**: Both products and shipping use `quantity_on_order=1.0`, so no special handling needed

## Update Scenarios

| Scenario | Shopify State | RMS Action | Result |
|----------|--------------|------------|--------|
| **New order with shipping** | Shipping = 5,000 | Create order + shipping entry | Order with shipping OrderEntry (5,000) |
| **New order without shipping** | Shipping = 0 | Create order WITHOUT shipping entry | Order synced, no shipping OrderEntry |
| **Update: Shipping changed** | 5,000 to 3,000 | Update existing shipping entry price | Entry price = 3,000 |
| **Update: Shipping removed** | 5,000 to 0 | Update entry: Price=0, Qty=0 | Entry exists with all zeros (not deleted) |
| **Update: Shipping added** | 0 to 5,000 | Create new shipping entry | New entry created with price 5,000 |
| **Missing VIEW_Items** | Any | Log warning, skip entry | Order syncs without shipping entry |

## Implementation Files

| File | Line | Purpose |
|------|------|---------|
| `app/core/config.py` | 171 | SHIPPING_ITEM_ID configuration |
| `app/domain/models/order_entry.py` | 57-58 | Added `comment` and `price_source` fields |
| `app/domain/models/order_entry.py` | 65 | Special validation for shipping (quantity=0 allowed) |
| `app/db/rms/order_repository.py` | 63-64 | Column mapping for Comment and PriceSource |
| `app/db/rms/query_executor.py` | 328 | `get_shipping_item()` - Query VIEW_Items |
| `app/db/rms/query_executor.py` | 400 | `get_shipping_item_cached()` - Cached query |
| `app/services/orders/converters/order_converter.py` | 427 | `_create_shipping_entry()` - Entry creation method |
| `app/services/orders/converters/order_converter.py` | 509-526 | Shipping entry with correct RMS pattern |
| `app/services/orders/converters/order_converter.py` | 134-149 | **Conditional creation logic (shipping > 0)** |
| `app/services/orders/converters/order_converter.py` | 156-157 | Tax calculation fix for quantity=0 |
| `app/services/orders/managers/order_creator.py` | 153-172 | Defensive validation for shipping entry in `update()` |
| `app/services/orders/managers/order_creator.py` | 174-221 | **Orphan deletion with shipping special handling (update to 0, not delete)** |

## Error Handling

**Missing Shipping Item** (ItemID=481461 not in VIEW_Items):
- Logs warning: "Shipping item not found in VIEW_Items"
- Order continues syncing WITHOUT shipping entry
- Order.ShippingChargeOnOrder still populated
- Shipping cost NOT tracked as separate OrderEntry

**Zero Shipping** (New Behavior):
- **Creation**: Skips entry creation if `shipping_charge.amount <= 0`
- **Update (positive to 0)**: Updates existing entry to Price=0, QuantityOnOrder=0, QuantityRTD=0 (NOT deleted)
- **Update (0 to positive)**: Creates new shipping entry with correct price from VIEW_Items
- **Rationale**: Preserving entry as 0 maintains audit trail without deletion permissions

**Caching**:
- Shipping item data cached on first query
- Cache persists for QueryExecutor instance lifetime
- Prevents repeated queries for same shipping item
- Cache invalidated on QueryExecutor re-initialization

## Database Requirements

**VIEW_Items Shipping Item** (ItemID=481461):
```sql
SELECT
    vi.ItemID,           -- 481461
    vi.Description,      -- "ENVIO"
    vi.Price,            -- Base price (WITHOUT tax, e.g., 5000.00)
    vi.Tax,              -- Tax percentage (e.g., 13)
    i.Cost,              -- Usually 0.00 for shipping
    i.Taxable            -- 1 (True) - shipping is taxable in Costa Rica
FROM View_Items vi
INNER JOIN Item i ON vi.ItemID = i.ID
WHERE vi.ItemID = 481461
```

**Required**: This item MUST exist in VIEW_Items for shipping entry creation to work.

## Logs & Monitoring

**Success Log - Created** (`order_converter.py:537-545`):
```
Created shipping OrderEntry: ItemID=481461,
Description='ENVIO', Price=5,650.00 (WITH 13% tax),
Base price from VIEW_Items=5,000.00, QuantityOnOrder=1.0, QuantityRTD=0.0 (open order logic),
Comment='Shipping Item', PriceSource=10, Taxable=True
```

**Info Log - Skipped** (`order_converter.py:149`):
```
Skipping shipping OrderEntry creation (shipping=0)
```

**Info Log - Updated to Zero** (`order_creator.py:209`):
```
Updated shipping entry 12345 to 0 (shipping removed from Shopify order,
ItemID=481461, QuantityOnOrder=0, QuantityRTD=0)
```

**Warning Log** (item not found):
```
Shipping item 481461 not found in VIEW_Items.
Skipping shipping OrderEntry creation. Order will sync WITHOUT shipping entry.
```

**Defensive Check Log** (`order_creator.py:161`):
```
DEFENSIVE CHECK: Order 12345 has shipping charge 5,000.00
but no shipping entry (ItemID=481461) found in order.entries.
```

## Advantages

1. **Complete Order Tracking**: All order costs (products + shipping) tracked as OrderEntry records
2. **Consistent Data Model**: Shipping handled same way as products (ItemID, Price, Tax, etc.)
3. **Tax Accuracy**: Shipping tax properly calculated and included in Order.Tax
4. **Update Support**: Shipping changes automatically reflected in RMS
5. **Backwards Compatible**: Existing orders without shipping entry continue working
6. **Performance**: Caching prevents repeated database queries

## Troubleshooting

**Issue**: Shipping entries not being created
- Verify: ItemID=481461 exists in VIEW_Items
- Check: Logs for "Shipping item not found" warnings
- Verify: `SHIPPING_ITEM_ID` in `.env` matches database
- Test: Query VIEW_Items manually to confirm item exists

**Issue**: Wrong shipping amounts
- Check: Tax percentage in VIEW_Items.Tax (should be 13 for Costa Rica)
- Verify: Shopify `shippingLine.currentDiscountedPriceSet` has correct amount
- Review: Tax calculation logs for discrimination formula
- Compare: Order.ShippingChargeOnOrder vs OrderEntry.Price

**Issue**: Duplicate shipping entries
- Check: OrderConverter creates only ONE shipping entry per order
- Verify: Update logic doesn't create duplicate entries
- Review: Logs for "Updated order entry" vs "Created new order entry"
