#!/usr/bin/env python3
"""
Monitor sync progress by reading checkpoint files and logs
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path


def monitor_sync(sync_id=None):
    """Monitor sync progress via checkpoint files"""

    checkpoint_dir = Path("checkpoints")

    if not sync_id:
        # Find the most recent checkpoint file
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        if not checkpoint_files:
            print("No checkpoint files found. Sync may not have started yet.")
            return

        # Get the most recent file
        latest_file = max(checkpoint_files, key=lambda f: f.stat().st_mtime)
        sync_id = latest_file.stem
        print(f"Monitoring sync: {sync_id}")

    checkpoint_file = checkpoint_dir / f"{sync_id}.json"

    print("=" * 70)
    print(f"MONITORING SYNC: {sync_id}")
    print("=" * 70)
    print("Press Ctrl+C to stop monitoring\n")

    last_processed_count = 0
    start_time = time.time()

    try:
        while True:
            if checkpoint_file.exists():
                try:
                    with open(checkpoint_file, "r") as f:
                        data = json.load(f)

                    processed = data.get("processed_count", 0)
                    total = data.get("total_count", 0)
                    current_page = data.get("additional_data", {}).get("current_page", 1)
                    total_pages = data.get("additional_data", {}).get("total_pages", 1)
                    last_ccod = data.get("last_processed_ccod", "unknown")
                    stats = data.get("stats", {})

                    # Calculate progress
                    progress = (processed / total * 100) if total > 0 else 0

                    # Calculate rate
                    elapsed = time.time() - start_time
                    if elapsed > 0 and processed > 0:
                        rate = processed / elapsed * 60  # products per minute
                        eta_seconds = ((total - processed) / (processed / elapsed)) if processed > 0 else 0
                        eta_minutes = int(eta_seconds / 60)
                        eta_seconds = int(eta_seconds % 60)
                    else:
                        rate = 0
                        eta_minutes = 0
                        eta_seconds = 0

                    # Clear screen and show update
                    print("\033[H\033[J", end="")  # Clear screen
                    print("=" * 70)
                    print(f"SYNC PROGRESS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("=" * 70)
                    print(f"Sync ID:        {sync_id}")
                    print(f"Progress:       {processed}/{total} products ({progress:.1f}%)")
                    print(f"Current Page:   {current_page}/{total_pages}")
                    print(f"Last Product:   {last_ccod}")
                    print(f"Rate:           {rate:.1f} products/minute")
                    print(f"ETA:            {eta_minutes}m {eta_seconds}s")
                    print("")
                    print("Statistics:")
                    print(f"  Created:      {stats.get('created', 0)}")
                    print(f"  Updated:      {stats.get('updated', 0)}")
                    print(f"  Skipped:      {stats.get('skipped', 0)}")
                    print(f"  Errors:       {stats.get('errors', 0)}")
                    print("")

                    # Progress bar
                    bar_width = 50
                    filled = int(bar_width * progress / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    print(f"[{bar}] {progress:.1f}%")

                    # Check if new products were processed
                    if processed > last_processed_count:
                        products_in_batch = processed - last_processed_count
                        print(f"\n✅ Processed {products_in_batch} new products")
                        last_processed_count = processed

                    # Check if sync is complete
                    if processed >= total:
                        print("\n" + "=" * 70)
                        print("🎉 SYNC COMPLETED SUCCESSFULLY!")
                        print(f"Total products synced: {processed}/{total}")
                        print(f"Total time: {int(elapsed/60)}m {int(elapsed%60)}s")
                        print("=" * 70)
                        break

                except json.JSONDecodeError:
                    print("Checkpoint file is being updated, retrying...")
                except Exception as e:
                    print(f"Error reading checkpoint: {e}")
            else:
                # Checkpoint file doesn't exist - sync might have completed
                print("\nCheckpoint file no longer exists.")
                print("Sync may have completed successfully (checkpoint deleted on completion)")
                print("Or sync hasn't started yet.")
                break

            time.sleep(2)  # Update every 2 seconds

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        print(f"Last known progress: {last_processed_count} products processed")


if __name__ == "__main__":
    sync_id = sys.argv[1] if len(sys.argv) > 1 else None
    monitor_sync(sync_id)
