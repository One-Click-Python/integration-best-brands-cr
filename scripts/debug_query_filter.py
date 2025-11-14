"""
Debug script to check the exact query filter being generated.
"""

from datetime import UTC, datetime, timedelta

# Test the query filter generation
lookback_minutes = 30
financial_statuses = ['PAID', 'PARTIALLY_PAID', 'AUTHORIZED', 'PENDING']

filters = []

# Date filter
cutoff_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)
cutoff_str = cutoff_time.strftime("%Y-%m-%dT%H:%M:%S%z")
filters.append(f"updated_at:>='{cutoff_str}'")

# Financial status filter
if financial_statuses:
    status_conditions = " OR ".join(
        [f"financial_status:{status}" for status in financial_statuses]
    )
    if len(financial_statuses) > 1:
        filters.append(f"({status_conditions})")
    else:
        filters.append(status_conditions)

# Combine filters
query_filter = " AND ".join(filters)

print("=" * 80)
print("QUERY FILTER DEBUG")
print("=" * 80)
print(f"Cutoff time: {cutoff_time}")
print(f"Cutoff string: {cutoff_str}")
print(f"\nFull query filter:")
print(query_filter)
print("=" * 80)

# Check order #1013 updated time
order_1013_updated = datetime.fromisoformat("2025-11-13T04:10:09+00:00")
print(f"\nOrder #1013 updated: {order_1013_updated}")
print(f"Cutoff time:         {cutoff_time}")
print(f"Should be included:  {order_1013_updated >= cutoff_time}")
print("=" * 80)
