#!/usr/bin/env python3
"""
Test script for the Update Checkpoint System.

This script demonstrates the functionality of the checkpoint system
for RMS → Shopify synchronization.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.update_checkpoint import UpdateCheckpointManager
from app.db.rms_handler import RMSHandler
from app.core.config import get_settings


async def test_checkpoint_manager():
    """Test the checkpoint manager functionality."""
    print("\n" + "="*60)
    print("TESTING UPDATE CHECKPOINT SYSTEM")
    print("="*60)
    
    # Initialize checkpoint manager
    checkpoint_mgr = UpdateCheckpointManager()
    
    # Test 1: Get status when no checkpoint exists
    print("\n1. Checking initial checkpoint status...")
    status = checkpoint_mgr.get_checkpoint_status()
    print(f"   Status: {status}")
    
    # Test 2: Get default timestamp
    print("\n2. Getting default timestamp (30 days back)...")
    default_timestamp = checkpoint_mgr.get_last_update_timestamp(30)
    print(f"   Default timestamp: {default_timestamp}")
    print(f"   Age: {(datetime.now(timezone.utc) - default_timestamp).days} days")
    
    # Test 3: Save a checkpoint
    print("\n3. Saving a new checkpoint...")
    test_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
    success = checkpoint_mgr.save_checkpoint(test_timestamp)
    print(f"   Save successful: {success}")
    
    # Test 4: Load the checkpoint
    print("\n4. Loading the saved checkpoint...")
    checkpoint = checkpoint_mgr.load_checkpoint()
    if checkpoint:
        print(f"   Loaded timestamp: {checkpoint['last_run_timestamp']}")
        print(f"   Version: {checkpoint.get('version', 'unknown')}")
    
    # Test 5: Get status with existing checkpoint
    print("\n5. Checking checkpoint status after save...")
    status = checkpoint_mgr.get_checkpoint_status()
    print(f"   Exists: {status['exists']}")
    print(f"   Age (hours): {status.get('age_hours', 'N/A')}")
    
    # Test 6: Validate checkpoint
    print("\n6. Validating checkpoint...")
    is_valid = checkpoint_mgr.validate_checkpoint()
    print(f"   Checkpoint is valid: {is_valid}")
    
    print("\n" + "="*60)
    print("CHECKPOINT MANAGER TESTS COMPLETED")
    print("="*60)


async def test_rms_integration():
    """Test RMS integration with checkpoint system."""
    print("\n" + "="*60)
    print("TESTING RMS INTEGRATION WITH CHECKPOINT")
    print("="*60)
    
    settings = get_settings()
    
    # Initialize RMS handler
    rms_handler = RMSHandler()
    
    try:
        await rms_handler.initialize()
        print("\n✓ RMS Handler initialized successfully")
        
        # Test 1: Count all products
        print("\n1. Counting all products...")
        total_count = await rms_handler.count_view_items_since(
            since_timestamp=None,
            include_zero_stock=False
        )
        print(f"   Total products in RMS: {total_count}")
        
        # Test 2: Count products modified in last 7 days
        print("\n2. Counting products modified in last 7 days...")
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_count = await rms_handler.count_view_items_since(
            since_timestamp=seven_days_ago,
            include_zero_stock=False
        )
        print(f"   Products modified in last 7 days: {recent_count}")
        
        # Test 3: Count products modified in last 24 hours
        print("\n3. Counting products modified in last 24 hours...")
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        today_count = await rms_handler.count_view_items_since(
            since_timestamp=one_day_ago,
            include_zero_stock=False
        )
        print(f"   Products modified in last 24 hours: {today_count}")
        
        # Test 4: Get sample of recent products
        if recent_count > 0:
            print("\n4. Getting sample of recently modified products...")
            recent_products = await rms_handler.get_view_items_since(
                since_timestamp=seven_days_ago,
                limit=5,
                include_zero_stock=False
            )
            print(f"   Retrieved {len(recent_products)} sample products:")
            for product in recent_products[:3]:
                print(f"   - {product.c_articulo}: {product.description[:50]}...")
        
        print("\n" + "="*60)
        print("RMS INTEGRATION TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error in RMS integration test: {e}")
    finally:
        await rms_handler.close()


async def test_checkpoint_workflow():
    """Test complete checkpoint workflow."""
    print("\n" + "="*60)
    print("TESTING COMPLETE CHECKPOINT WORKFLOW")
    print("="*60)
    
    checkpoint_mgr = UpdateCheckpointManager()
    
    # Simulate a sync workflow
    print("\n1. Starting simulated sync process...")
    sync_start = datetime.now(timezone.utc)
    
    # Get last checkpoint or default
    last_checkpoint = checkpoint_mgr.get_last_update_timestamp(30)
    print(f"   Using checkpoint: {last_checkpoint}")
    
    # Simulate successful sync
    print("\n2. Simulating successful sync...")
    success_rate = 0.98  # 98% success rate
    threshold = 0.95
    
    if success_rate >= threshold:
        print(f"   Success rate {success_rate:.2%} >= {threshold:.2%} threshold")
        print("   Updating checkpoint...")
        checkpoint_mgr.save_checkpoint(sync_start)
        print("   ✓ Checkpoint updated successfully")
    else:
        print(f"   Success rate {success_rate:.2%} < {threshold:.2%} threshold")
        print("   ✗ Checkpoint not updated")
    
    # Verify update
    print("\n3. Verifying checkpoint update...")
    status = checkpoint_mgr.get_checkpoint_status()
    if status['exists']:
        print(f"   Last run: {status['last_run_timestamp']}")
        print(f"   Age: {status['age_hours']:.2f} hours")
    
    print("\n" + "="*60)
    print("WORKFLOW TEST COMPLETED")
    print("="*60)


async def main():
    """Main test function."""
    print("\n" + "="*60)
    print("UPDATE CHECKPOINT SYSTEM TEST SUITE")
    print(f"Started at: {datetime.now()}")
    print("="*60)
    
    try:
        # Run tests
        await test_checkpoint_manager()
        await test_checkpoint_workflow()
        
        # Optional: Test RMS integration (requires database connection)
        print("\nDo you want to test RMS integration? (requires database connection)")
        response = input("Enter 'yes' to test RMS integration: ").strip().lower()
        if response == 'yes':
            await test_rms_integration()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())