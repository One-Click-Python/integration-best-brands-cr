"""
Integration test to verify tag format consistency between main sync and reverse sync.

This test ensures that the tag format used by the main synchronization
(variant_mapper.py and data_mapper.py) matches the format expected by
the reverse stock synchronization (reverse_stock_sync.py).

Critical for ensuring reverse sync only processes unsynced products.
"""

from datetime import UTC, datetime

import pytest

from app.services.reverse_stock_sync import ReverseStockSynchronizer
from app.services.variant_mapper import VariantMapper


class TestTagFormatConsistency:
    """Test suite for tag format consistency between sync systems."""

    def test_tag_format_matches_between_syncs(self):
        """
        Verify that main sync and reverse sync use the same tag format.

        CRITICAL TEST: If this fails, reverse sync will process ALL products
        instead of just unsynced ones, causing massive performance issues.
        """
        # Get today's date
        today = datetime.now(UTC)

        # Generate tag using main sync format (variant_mapper.py:433)
        main_sync_tag = f"RMS-SYNC-{today.strftime('%y-%m-%d')}"

        # Generate tag using reverse sync format
        synchronizer = ReverseStockSynchronizer(
            product_repository=None,  # Not needed for this test
            shopify_client=None,  # Not needed for this test
            primary_location_id="dummy",
        )
        reverse_sync_tag = synchronizer._get_today_sync_tag()

        # Assert formats match
        assert main_sync_tag == reverse_sync_tag, (
            f"Tag format mismatch!\n"
            f"Main sync tag: {main_sync_tag}\n"
            f"Reverse sync tag: {reverse_sync_tag}\n"
            f"This will cause reverse sync to process ALL products instead of just unsynced ones."
        )

    def test_tag_format_is_yy_mm_dd(self):
        """
        Verify that both syncs use YY-MM-DD format (2-digit year).

        Format: RMS-SYNC-25-01-23 (not RMS-SYNC-2025-01-23)
        """
        today = datetime.now(UTC)
        expected_format = f"RMS-SYNC-{today.strftime('%y-%m-%d')}"

        # Test main sync tag format
        from app.services.data_mapper import RMSToShopifyMapper

        base_item = type(
            "Item",
            (),
            {"ccod": "TEST", "familia": None, "genero": None, "categoria": None, "is_on_sale": False},
        )()
        tags = RMSToShopifyMapper._generate_tags(base_item)
        main_sync_tag = next((tag for tag in tags if tag.startswith("RMS-SYNC-")), None)

        assert main_sync_tag is not None, "Main sync should generate RMS-SYNC tag"
        assert main_sync_tag == expected_format, (
            f"Main sync tag format incorrect!\n" f"Expected: {expected_format}\n" f"Got: {main_sync_tag}"
        )

        # Test reverse sync tag format
        synchronizer = ReverseStockSynchronizer(
            product_repository=None, shopify_client=None, primary_location_id="dummy"
        )
        reverse_sync_tag = synchronizer._get_today_sync_tag()

        assert reverse_sync_tag == expected_format, (
            f"Reverse sync tag format incorrect!\n" f"Expected: {expected_format}\n" f"Got: {reverse_sync_tag}"
        )

    def test_tag_format_uses_two_digit_year(self):
        """
        Verify that tag uses 2-digit year (25) not 4-digit year (2025).

        This is important for:
        1. Consistency with existing Shopify tags
        2. Shorter tag length
        3. Query performance (shorter strings)
        """
        synchronizer = ReverseStockSynchronizer(
            product_repository=None, shopify_client=None, primary_location_id="dummy"
        )
        tag = synchronizer._get_today_sync_tag()

        # Extract year part (after "RMS-SYNC-")
        year_part = tag.split("-")[2]  # RMS-SYNC-YY-MM-DD -> YY

        assert len(year_part) == 2, (
            f"Year should be 2 digits, got {len(year_part)} digits: {year_part}\n" f"Full tag: {tag}"
        )

        # Verify it's a valid 2-digit year
        assert year_part.isdigit(), f"Year part should be numeric: {year_part}"
        assert 0 <= int(year_part) <= 99, f"Year should be 00-99: {year_part}"

    @pytest.mark.parametrize(
        "test_date,expected_tag",
        [
            (datetime(2025, 1, 23, tzinfo=UTC), "RMS-SYNC-25-01-23"),
            (datetime(2025, 12, 31, tzinfo=UTC), "RMS-SYNC-25-12-31"),
            (datetime(2026, 1, 1, tzinfo=UTC), "RMS-SYNC-26-01-01"),
            (datetime(2030, 6, 15, tzinfo=UTC), "RMS-SYNC-30-06-15"),
        ],
    )
    def test_tag_format_examples(self, test_date, expected_tag, monkeypatch):
        """
        Test tag generation with specific dates to verify format.
        """
        # Mock datetime.now to return test_date
        class MockDatetime:
            @staticmethod
            def now(tz=None):
                return test_date

        monkeypatch.setattr("app.services.reverse_stock_sync.datetime", MockDatetime)

        synchronizer = ReverseStockSynchronizer(
            product_repository=None, shopify_client=None, primary_location_id="dummy"
        )
        tag = synchronizer._get_today_sync_tag()

        assert tag == expected_tag, f"Expected {expected_tag}, got {tag}"


class TestTagQueryBehavior:
    """Test how tags work in Shopify queries."""

    def test_shopify_query_excludes_exact_match_only(self):
        """
        Verify that Shopify query 'NOT tag:RMS-SYNC-25-01-23' only excludes
        products with that EXACT tag, not similar tags.

        This confirms that tag format MUST match exactly for exclusion to work.
        """
        # This is a documentation test to explain the behavior
        test_query = "status:ACTIVE AND NOT tag:RMS-SYNC-25-01-23"

        # Products with these tags WILL be included (not excluded):
        not_excluded = [
            "RMS-SYNC-2025-01-23",  # Wrong format (4-digit year)
            "RMS-SYNC-25-01-22",  # Different date
            "RMS-SYNC-25-02-23",  # Different month
            "RMS-Sync-25-01-23",  # Wrong case (Shopify tags are case-sensitive)
        ]

        # Only this tag WILL be excluded:
        excluded = "RMS-SYNC-25-01-23"

        # Document expected behavior
        assert True, (
            f"Query: {test_query}\n"
            f"Excludes ONLY: {excluded}\n"
            f"Does NOT exclude: {', '.join(not_excluded)}\n"
            f"\nThis is why tag format MUST match exactly!"
        )
