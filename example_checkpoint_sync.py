#!/usr/bin/env python3
"""
Example script demonstrating how to use the Update Checkpoint System
for efficient RMS → Shopify synchronization.

This script shows how to:
1. Enable the checkpoint system for incremental updates
2. Only sync products modified since the last successful run
3. Update checkpoint after successful sync
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.services.rms_to_shopify.sync_orchestrator import RMSToShopifySyncOrchestrator
from app.utils.update_checkpoint import UpdateCheckpointManager
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_incremental_sync():
    """
    Run an incremental sync using the checkpoint system.
    
    This will only sync products that have been created or modified
    since the last successful sync.
    """
    settings = get_settings()
    
    # Initialize checkpoint manager to check status
    checkpoint_mgr = UpdateCheckpointManager()
    
    # Show current checkpoint status
    status = checkpoint_mgr.get_checkpoint_status()
    if status['exists']:
        logger.info(f"📅 Found existing checkpoint from {status['last_run_timestamp']}")
        logger.info(f"   Age: {status['age_hours']:.2f} hours")
    else:
        logger.info("📅 No checkpoint found - will look back 30 days by default")
    
    # Get the timestamp we'll use for filtering
    last_update_timestamp = checkpoint_mgr.get_last_update_timestamp(
        default_days_back=settings.CHECKPOINT_DEFAULT_DAYS
    )
    logger.info(f"🔍 Will sync products modified since: {last_update_timestamp}")
    
    # Create sync orchestrator with checkpoint system enabled
    sync_service = RMSToShopifySyncOrchestrator(
        sync_id=f"incremental_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        use_update_checkpoint=True,  # Enable update checkpoint system
        checkpoint_success_threshold=0.95,  # Update checkpoint if 95% success rate
        checkpoint_frequency=100,  # Save progress checkpoint every 100 products
        resume_from_checkpoint=True,  # Resume if interrupted
    )
    
    try:
        # Initialize sync service
        await sync_service.initialize()
        logger.info("✅ Sync service initialized successfully")
        
        # Run the sync
        logger.info("🚀 Starting incremental sync...")
        result = await sync_service.sync_products(
            force_update=False,  # Only update changed products
            batch_size=25,  # Process 25 products at a time
            include_zero_stock=False,  # Skip products with no stock
            use_streaming=True,  # Use streaming for efficiency
            page_size=100,  # Process 100 products per page
        )
        
        # Check results
        success_rate = result.get('success_rate', 0)
        total_processed = result.get('statistics', {}).get('total_processed', 0)
        errors = result.get('statistics', {}).get('errors', 0)
        
        logger.info(f"📊 Sync completed:")
        logger.info(f"   Products processed: {total_processed}")
        logger.info(f"   Errors: {errors}")
        logger.info(f"   Success rate: {success_rate:.2f}%")
        
        # Check if checkpoint was updated
        if result.get('update_checkpoint_saved'):
            logger.info(f"✅ Checkpoint updated successfully!")
            logger.info(f"   Next sync will start from: {result['update_checkpoint_timestamp']}")
        else:
            reason = result.get('update_checkpoint_reason', 'Unknown')
            logger.warning(f"⚠️ Checkpoint not updated: {reason}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        raise
        
    finally:
        await sync_service.close()


async def run_full_sync_with_checkpoint():
    """
    Run a full sync but still update the checkpoint for future incremental syncs.
    
    This is useful when you want to do a complete sync but still maintain
    the checkpoint for future incremental updates.
    """
    settings = get_settings()
    
    logger.info("🔄 Running full sync with checkpoint update...")
    
    # Create sync orchestrator with checkpoint enabled
    sync_service = RMSToShopifySyncOrchestrator(
        sync_id=f"full_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        use_update_checkpoint=True,  # Still update checkpoint after success
        checkpoint_success_threshold=0.90,  # Lower threshold for full sync
        force_fresh_start=True,  # Ignore existing progress checkpoints
    )
    
    try:
        await sync_service.initialize()
        
        # Run full sync (no timestamp filter)
        result = await sync_service.sync_products(
            force_update=True,  # Force update all products
            include_zero_stock=True,  # Include all products
        )
        
        logger.info(f"✅ Full sync completed")
        if result.get('update_checkpoint_saved'):
            logger.info(f"📅 Checkpoint updated for future incremental syncs")
        
        return result
        
    finally:
        await sync_service.close()


async def check_pending_updates():
    """
    Check how many products need to be synced based on the checkpoint.
    """
    from app.db.rms_handler import RMSHandler
    
    checkpoint_mgr = UpdateCheckpointManager()
    rms_handler = RMSHandler()
    
    try:
        await rms_handler.initialize()
        
        # Get last checkpoint timestamp
        last_timestamp = checkpoint_mgr.get_last_update_timestamp(30)
        
        # Count products modified since checkpoint
        count = await rms_handler.count_view_items_since(
            since_timestamp=last_timestamp,
            include_zero_stock=False
        )
        
        logger.info(f"📊 Products pending sync since {last_timestamp}:")
        logger.info(f"   Total products to sync: {count}")
        
        if count > 0:
            logger.info(f"   Estimated sync time: {(count * 2) / 60:.1f} minutes")
        
        return count
        
    finally:
        await rms_handler.close()


async def main():
    """Main function demonstrating different sync scenarios."""
    
    print("\n" + "="*60)
    print("CHECKPOINT-BASED SYNC EXAMPLES")
    print("="*60)
    
    print("\nChoose an option:")
    print("1. Run incremental sync (only modified products)")
    print("2. Run full sync with checkpoint update")
    print("3. Check pending updates")
    print("4. Reset checkpoint and run fresh sync")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        await run_incremental_sync()
        
    elif choice == "2":
        await run_full_sync_with_checkpoint()
        
    elif choice == "3":
        await check_pending_updates()
        
    elif choice == "4":
        checkpoint_mgr = UpdateCheckpointManager()
        checkpoint_mgr.reset_checkpoint()
        logger.info("✅ Checkpoint reset successfully")
        await run_incremental_sync()
        
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())