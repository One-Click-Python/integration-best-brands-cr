"""
Update Checkpoint Management System for RMS → Shopify Sync.

This module handles the checkpoint mechanism for tracking the last successful
update timestamp. It allows the sync process to only fetch records that have
been created or modified since the last successful run, improving efficiency.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class UpdateCheckpointManager:
    """
    Manages the update checkpoint system for RMS synchronization.
    
    The checkpoint stores the timestamp of the last successful update,
    allowing subsequent runs to only process new or modified records.
    """
    
    def __init__(self, checkpoint_dir: str = "./checkpoint", 
                 checkpoint_filename: str = "checkpoint.json"):
        """
        Initialize the UpdateCheckpointManager.
        
        Args:
            checkpoint_dir: Directory path for checkpoint file
            checkpoint_filename: Name of the checkpoint JSON file
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_file = self.checkpoint_dir / checkpoint_filename
        self._ensure_checkpoint_directory()
    
    def _ensure_checkpoint_directory(self) -> None:
        """Ensure the checkpoint directory exists."""
        try:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Checkpoint directory ensured at: {self.checkpoint_dir}")
        except Exception as e:
            logger.error(f"Failed to create checkpoint directory: {e}")
            raise
    
    def load_checkpoint(self) -> Optional[Dict[str, str]]:
        """
        Load checkpoint data from JSON file.
        
        Returns:
            Dict containing checkpoint data or None if file doesn't exist/invalid
        """
        try:
            if not self.checkpoint_file.exists():
                logger.info("No checkpoint file found - will use default time range")
                return None
            
            with open(self.checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                
            # Validate checkpoint structure
            if not isinstance(checkpoint_data, dict):
                logger.warning("Invalid checkpoint structure - expected dictionary")
                return None
                
            if "last_run_timestamp" not in checkpoint_data:
                logger.warning("Missing 'last_run_timestamp' in checkpoint")
                return None
            
            # Validate timestamp format
            try:
                timestamp_str = checkpoint_data["last_run_timestamp"]
                datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                logger.info(f"📅 [UPDATE CHECKPOINT] Loaded - Last sync: {timestamp_str}")
                return checkpoint_data
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp format in checkpoint: {e}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted checkpoint file - JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def save_checkpoint(self, timestamp: Optional[datetime] = None) -> bool:
        """
        Save checkpoint with current or specified timestamp.
        
        Args:
            timestamp: Datetime to save (defaults to current UTC time)
            
        Returns:
            True if checkpoint was saved successfully
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        try:
            # Ensure timestamp is UTC
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            checkpoint_data = {
                "last_run_timestamp": timestamp.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0"
            }
            
            # Write checkpoint file
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            
            logger.info(f"✅ [UPDATE CHECKPOINT] Saved - New timestamp: {timestamp.isoformat()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def get_last_update_timestamp(self, default_days_back: int = 30) -> datetime:
        """
        Get the last update timestamp from checkpoint or default.
        
        Args:
            default_days_back: Number of days to look back if no checkpoint exists
            
        Returns:
            DateTime of last update or default time range
        """
        checkpoint = self.load_checkpoint()
        
        if checkpoint and "last_run_timestamp" in checkpoint:
            try:
                timestamp_str = checkpoint["last_run_timestamp"]
                # Handle ISO format with proper timezone
                last_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                # Ensure timezone awareness
                if last_timestamp.tzinfo is None:
                    last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)
                
                logger.info(f"🕐 [UPDATE CHECKPOINT] Using timestamp: {last_timestamp.isoformat()} for change detection")
                return last_timestamp
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse checkpoint timestamp, using default: {e}")
        
        # Default to specified days back
        default_timestamp = datetime.now(timezone.utc) - timedelta(days=default_days_back)
        logger.info(f"⚠️ [UPDATE CHECKPOINT] Not found - Using default: {default_days_back} days back")
        return default_timestamp
    
    def reset_checkpoint(self) -> bool:
        """
        Reset (delete) the checkpoint file.
        
        Returns:
            True if checkpoint was reset successfully
        """
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.info("Checkpoint file reset successfully")
            else:
                logger.info("No checkpoint file to reset")
            return True
        except Exception as e:
            logger.error(f"Failed to reset checkpoint: {e}")
            return False
    
    def get_checkpoint_status(self) -> Dict[str, any]:
        """
        Get detailed status information about the checkpoint.
        
        Returns:
            Dictionary with checkpoint status information
        """
        checkpoint = self.load_checkpoint()
        
        if checkpoint:
            try:
                timestamp_str = checkpoint["last_run_timestamp"]
                last_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                if last_timestamp.tzinfo is None:
                    last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                age_hours = (now - last_timestamp).total_seconds() / 3600
                
                return {
                    "exists": True,
                    "last_run_timestamp": timestamp_str,
                    "age_hours": round(age_hours, 2),
                    "file_path": str(self.checkpoint_file),
                    "updated_at": checkpoint.get("updated_at"),
                    "version": checkpoint.get("version", "unknown")
                }
            except Exception as e:
                logger.error(f"Error parsing checkpoint status: {e}")
                return {
                    "exists": True,
                    "error": str(e),
                    "file_path": str(self.checkpoint_file)
                }
        
        return {
            "exists": False,
            "file_path": str(self.checkpoint_file),
            "message": "No checkpoint file found"
        }
    
    def validate_checkpoint(self) -> bool:
        """
        Validate that checkpoint file exists and contains valid data.
        
        Returns:
            True if checkpoint is valid
        """
        checkpoint = self.load_checkpoint()
        return checkpoint is not None and "last_run_timestamp" in checkpoint


# Module-level convenience functions
_default_manager = None


def get_default_manager() -> UpdateCheckpointManager:
    """Get or create the default checkpoint manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = UpdateCheckpointManager()
    return _default_manager


def load_checkpoint() -> Optional[Dict[str, str]]:
    """Load checkpoint using default manager."""
    return get_default_manager().load_checkpoint()


def save_checkpoint(timestamp: Optional[datetime] = None) -> bool:
    """Save checkpoint using default manager."""
    return get_default_manager().save_checkpoint(timestamp)


def get_last_update_timestamp(default_days_back: int = 30) -> datetime:
    """Get last update timestamp using default manager."""
    return get_default_manager().get_last_update_timestamp(default_days_back)


def reset_checkpoint() -> bool:
    """Reset checkpoint using default manager."""
    return get_default_manager().reset_checkpoint()


def get_checkpoint_status() -> Dict[str, any]:
    """Get checkpoint status using default manager."""
    return get_default_manager().get_checkpoint_status()