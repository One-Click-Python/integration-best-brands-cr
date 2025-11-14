#!/usr/bin/env python3
"""
Script de verificación de coordinación entre sincronizaciones RMS→Shopify y Reverse Stock Sync.

Este script valida que:
1. Las notificaciones de sincronización RMS→Shopify funcionan correctamente
2. El scheduler registra correctamente el estado de las sincronizaciones
3. El reverse stock sync se programa adecuadamente después del delay configurado
4. El estado se persiste correctamente en Redis

Uso:
    poetry run python scripts/test_sync_coordination.py [--verbose] [--skip-redis]

Opciones:
    --verbose: Muestra logs detallados de la verificación
    --skip-redis: Omite verificación de persistencia Redis (útil si Redis no está disponible)
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.core.scheduler import (
    get_scheduler_status,
    notify_rms_sync_completed,
    start_scheduler,
    stop_scheduler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class SyncCoordinationTester:
    """Tester for sync coordination between RMS→Shopify and Reverse Stock Sync."""

    def __init__(self, verbose: bool = False, skip_redis: bool = False):
        """
        Initialize tester.

        Args:
            verbose: Enable verbose logging
            skip_redis: Skip Redis persistence checks
        """
        self.verbose = verbose
        self.skip_redis = skip_redis
        self.settings = get_settings()
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []

        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    def _log_test(self, test_name: str, passed: bool, message: str):
        """Log test result with color formatting."""
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        logger.info(f"{status} - {test_name}: {message}")

        self.test_results.append({"test": test_name, "passed": passed, "message": message})

        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1

    async def test_scheduler_initialization(self) -> bool:
        """Test 1: Verify scheduler can be initialized and provides status."""
        test_name = "Scheduler Initialization"

        try:
            # Get initial status
            status = get_scheduler_status()

            # Verify basic structure
            assert "running" in status, "Status missing 'running' field"
            assert "reverse_stock_sync" in status, "Status missing 'reverse_stock_sync' field"

            reverse_info = status["reverse_stock_sync"]
            assert "enabled" in reverse_info, "Reverse sync info missing 'enabled' field"
            assert "delay_minutes" in reverse_info, "Reverse sync info missing 'delay_minutes' field"
            assert "status" in reverse_info, "Reverse sync info missing 'status' field"

            self._log_test(test_name, True, f"Scheduler status structure is correct - Reverse sync enabled: {reverse_info['enabled']}")
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Status structure validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    async def test_successful_rms_sync_notification(self) -> bool:
        """Test 2: Verify successful RMS sync notification updates scheduler state."""
        test_name = "Successful RMS Sync Notification"

        try:
            # Notify successful sync
            notify_rms_sync_completed(success=True)

            # Small delay to allow state update
            await asyncio.sleep(0.5)

            # Get updated status
            status = get_scheduler_status()
            reverse_info = status["reverse_stock_sync"]

            # Verify state was updated
            assert reverse_info["last_rms_sync_time"] is not None, "Last RMS sync time not updated"
            assert reverse_info["last_rms_sync_success"] is True, "Last RMS sync success not set to True"
            assert reverse_info["seconds_until_eligible"] is not None, "Seconds until eligible not calculated"

            # Verify status is waiting for delay (since we just notified)
            expected_status = "waiting_for_delay"
            actual_status = reverse_info["status"]

            assert actual_status == expected_status, (
                f"Status should be '{expected_status}' after successful sync, got '{actual_status}'"
            )

            self._log_test(
                test_name,
                True,
                f"Notification received - Status: {actual_status}, "
                f"Wait time: {reverse_info['seconds_until_eligible']}s",
            )
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Notification validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    async def test_failed_rms_sync_notification(self) -> bool:
        """Test 3: Verify failed RMS sync notification blocks reverse sync."""
        test_name = "Failed RMS Sync Notification"

        try:
            # Notify failed sync
            notify_rms_sync_completed(success=False)

            # Small delay to allow state update
            await asyncio.sleep(0.5)

            # Get updated status
            status = get_scheduler_status()
            reverse_info = status["reverse_stock_sync"]

            # Verify state was updated
            assert reverse_info["last_rms_sync_time"] is not None, "Last RMS sync time not updated"
            assert reverse_info["last_rms_sync_success"] is False, "Last RMS sync success not set to False"

            # Verify reverse sync won't execute
            assert reverse_info["will_execute_next_cycle"] is False, "Reverse sync should not execute after failed RMS sync"

            expected_status = "blocked_by_failed_rms_sync"
            actual_status = reverse_info["status"]

            assert actual_status == expected_status, (
                f"Status should be '{expected_status}' after failed sync, got '{actual_status}'"
            )

            self._log_test(test_name, True, f"Failed sync correctly blocks reverse sync - Status: {actual_status}")
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Failed notification validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    async def test_delay_calculation(self) -> bool:
        """Test 4: Verify delay calculation is accurate."""
        test_name = "Delay Calculation"

        try:
            # Notify successful sync
            notify_rms_sync_completed(success=True)
            notification_time = datetime.now(timezone.utc)

            # Small delay
            await asyncio.sleep(0.5)

            # Get status
            status = get_scheduler_status()
            reverse_info = status["reverse_stock_sync"]

            # Calculate expected delay
            delay_minutes = self.settings.REVERSE_SYNC_DELAY_MINUTES
            expected_delay_seconds = delay_minutes * 60

            # Verify delay is approximately correct (allow 2 second tolerance)
            actual_delay = reverse_info["seconds_until_eligible"]
            tolerance = 2

            assert actual_delay is not None, "Seconds until eligible not calculated"
            assert abs(actual_delay - expected_delay_seconds) <= tolerance, (
                f"Delay calculation incorrect: expected ~{expected_delay_seconds}s, "
                f"got {actual_delay}s (tolerance: {tolerance}s)"
            )

            self._log_test(
                test_name,
                True,
                f"Delay calculated correctly - Expected: {expected_delay_seconds}s, " f"Got: {actual_delay}s",
            )
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Delay calculation validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    async def test_ready_to_execute_status(self) -> bool:
        """Test 5: Verify status changes to 'ready_to_execute' after delay."""
        test_name = "Ready to Execute Status"

        try:
            # Import necessary modules for time manipulation
            from unittest.mock import patch

            # Simulate time passage by mocking current time
            current_time = datetime.now(timezone.utc)
            past_time = current_time - timedelta(minutes=self.settings.REVERSE_SYNC_DELAY_MINUTES + 1)

            # Notify sync with past time
            notify_rms_sync_completed(success=True)

            # Mock the scheduler's internal time to simulate delay passage
            with patch("app.core.scheduler._last_rms_sync_time", past_time):
                # Get status
                status = get_scheduler_status()
                reverse_info = status["reverse_stock_sync"]

                # Verify status is ready
                assert reverse_info["will_execute_next_cycle"] is True, "Should be ready to execute after delay"
                assert reverse_info["seconds_until_eligible"] == 0, "Should have 0 seconds remaining"

                expected_status = "ready_to_execute"
                actual_status = reverse_info["status"]

                assert actual_status == expected_status, (
                    f"Status should be '{expected_status}' after delay, got '{actual_status}'"
                )

            self._log_test(test_name, True, f"Status correctly changes to '{expected_status}' after delay")
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Ready status validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    async def test_redis_persistence(self) -> bool:
        """Test 6: Verify scheduler state persists to Redis."""
        test_name = "Redis Persistence"

        if self.skip_redis:
            self._log_test(test_name, True, "Skipped (--skip-redis flag)")
            return True

        try:
            # Notify successful sync
            notify_rms_sync_completed(success=True)

            # Allow time for async Redis save
            await asyncio.sleep(1.5)

            # Get Redis client
            redis = get_redis_client()

            # Check if state exists in Redis
            state_json = await redis.get("scheduler:state")

            assert state_json is not None, "Scheduler state not found in Redis"

            # Parse and verify state
            state = json.loads(state_json)

            assert "last_rms_sync_time" in state, "Redis state missing 'last_rms_sync_time'"
            assert "last_rms_sync_success" in state, "Redis state missing 'last_rms_sync_success'"

            assert state["last_rms_sync_time"] is not None, "Redis state has null last_rms_sync_time"
            assert state["last_rms_sync_success"] is True, "Redis state has incorrect last_rms_sync_success"

            self._log_test(test_name, True, f"State correctly persisted to Redis - Keys: {list(state.keys())}")
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Redis persistence validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error (Redis may not be available): {e}")
            return False

    async def test_configuration_loading(self) -> bool:
        """Test 7: Verify configuration values are loaded correctly."""
        test_name = "Configuration Loading"

        try:
            status = get_scheduler_status()
            reverse_info = status["reverse_stock_sync"]

            # Verify configuration matches settings
            assert reverse_info["enabled"] == self.settings.ENABLE_REVERSE_STOCK_SYNC, (
                f"Enabled status doesn't match settings: "
                f"status={reverse_info['enabled']}, settings={self.settings.ENABLE_REVERSE_STOCK_SYNC}"
            )

            assert reverse_info["delay_minutes"] == self.settings.REVERSE_SYNC_DELAY_MINUTES, (
                f"Delay minutes doesn't match settings: "
                f"status={reverse_info['delay_minutes']}, settings={self.settings.REVERSE_SYNC_DELAY_MINUTES}"
            )

            self._log_test(
                test_name,
                True,
                f"Configuration correct - Enabled: {reverse_info['enabled']}, "
                f"Delay: {reverse_info['delay_minutes']} min",
            )
            return True

        except AssertionError as e:
            self._log_test(test_name, False, f"Configuration validation failed: {e}")
            return False
        except Exception as e:
            self._log_test(test_name, False, f"Unexpected error: {e}")
            return False

    def print_summary(self):
        """Print test summary with color formatting."""
        print("\n" + "=" * 80)
        print(f"{BLUE}SYNC COORDINATION TEST SUMMARY{RESET}")
        print("=" * 80)

        total_tests = self.tests_passed + self.tests_failed
        success_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\nTotal Tests:    {total_tests}")
        print(f"{GREEN}Passed:         {self.tests_passed}{RESET}")
        print(f"{RED}Failed:         {self.tests_failed}{RESET}")
        print(f"Success Rate:   {success_rate:.1f}%")

        # Print failed tests details
        if self.tests_failed > 0:
            print(f"\n{RED}FAILED TESTS:{RESET}")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  ❌ {result['test']}: {result['message']}")

        print("\n" + "=" * 80)

        # Return exit code
        return 0 if self.tests_failed == 0 else 1

    async def run_all_tests(self) -> int:
        """Run all coordination tests."""
        logger.info(f"{BLUE}Starting Sync Coordination Tests...{RESET}\n")

        # Run tests sequentially
        await self.test_scheduler_initialization()
        await self.test_successful_rms_sync_notification()
        await self.test_failed_rms_sync_notification()
        await self.test_delay_calculation()
        await self.test_ready_to_execute_status()
        await self.test_redis_persistence()
        await self.test_configuration_loading()

        # Print summary and return exit code
        return self.print_summary()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test sync coordination between RMS→Shopify and Reverse Stock Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis persistence checks")

    args = parser.parse_args()

    try:
        # Create tester
        tester = SyncCoordinationTester(verbose=args.verbose, skip_redis=args.skip_redis)

        # Run tests
        exit_code = await tester.run_all_tests()

        # Exit with appropriate code
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"{RED}Fatal error running tests: {e}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
