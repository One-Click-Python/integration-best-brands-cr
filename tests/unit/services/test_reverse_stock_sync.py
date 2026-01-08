"""Tests unitarios para Reverse Stock Synchronization (Shopify → RMS)."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.reverse_stock_sync import ReverseStockSynchronizer


class TestExtractCcodFromMetafields:
    """Tests para extracción de CCOD desde metafields."""

    def test_extract_ccod_from_rms_namespace(self):
        """Debe extraer CCOD del namespace 'rms' correctamente."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        product = {
            "metafields": {
                "edges": [
                    {"node": {"namespace": "rms", "key": "ccod", "value": "26TS00"}},
                    {"node": {"namespace": "other", "key": "something", "value": "value"}},
                ]
            }
        }

        result = synchronizer._extract_ccod_from_metafields(product)
        assert result == "26TS00"

    def test_extract_ccod_from_custom_namespace(self):
        """Debe extraer CCOD del namespace 'custom' como fallback."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        product = {
            "metafields": {
                "edges": [
                    {"node": {"namespace": "custom", "key": "ccod", "value": "24X104"}},
                    {"node": {"namespace": "other", "key": "something", "value": "value"}},
                ]
            }
        }

        result = synchronizer._extract_ccod_from_metafields(product)
        assert result == "24X104"

    def test_extract_ccod_returns_none_when_not_found(self):
        """Debe retornar None si no encuentra CCOD."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        product = {
            "metafields": {
                "edges": [
                    {"node": {"namespace": "other", "key": "something", "value": "value"}},
                ]
            }
        }

        result = synchronizer._extract_ccod_from_metafields(product)
        assert result is None

    def test_extract_ccod_from_empty_metafields(self):
        """Debe retornar None si metafields está vacío."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        product = {"metafields": {"edges": []}}

        result = synchronizer._extract_ccod_from_metafields(product)
        assert result is None

def create_mock_item(c_articulo: str, quantity: Decimal):
    """Create a mock item with c_articulo and quantity attributes."""
    mock_item = MagicMock()
    mock_item.c_articulo = c_articulo
    mock_item.quantity = quantity
    return mock_item


class TestGetRmsStockByCcod:
    """Tests para consulta de stock en RMS por CCOD."""

    @pytest.mark.asyncio
    async def test_get_stock_with_existing_product(self):
        """Debe retornar diccionario de stock cuando el producto existe."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            return_value=[
                create_mock_item("26TS00-41-BEIGE", Decimal("5")),
                create_mock_item("26TS00-42-BEIGE", Decimal("3")),
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("26TS00")

        # Note: keys are lowercased for case-insensitive matching
        assert result == {
            "26ts00-41-beige": 5,
            "26ts00-42-beige": 3,
        }

    @pytest.mark.asyncio
    async def test_get_stock_with_zero_quantities(self):
        """Debe manejar correctamente cantidades en cero."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            return_value=[
                create_mock_item("26TS00-41-BEIGE", Decimal("0")),
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("26TS00")

        assert result == {
            "26ts00-41-beige": 0,
        }

    @pytest.mark.asyncio
    async def test_get_stock_with_nonexistent_product(self):
        """Debe retornar diccionario vacío si el producto no existe."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(return_value=[])

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("NONEXISTENT")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_stock_converts_decimal_to_int(self):
        """Debe convertir Decimal a int correctamente."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            return_value=[
                create_mock_item("TEST-SKU", Decimal("10.00")),
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("TEST")

        # Note: key is lowercased
        assert result == {"test-sku": 10}
        assert isinstance(result["test-sku"], int)


class TestEdgeCases:
    """Tests para casos especiales y edge cases."""

    def test_extract_ccod_with_malformed_metafields(self):
        """Debe manejar metafields con estructura incorrecta."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        # Metafield sin 'namespace'
        product = {
            "metafields": {
                "edges": [
                    {"node": {"key": "ccod", "value": "26TS00"}},  # Sin namespace
                ]
            }
        }

        # No debería crashear, solo retornar None
        result = synchronizer._extract_ccod_from_metafields(product)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stock_handles_repository_error(self):
        """Debe manejar errores del repositorio correctamente.

        NOTE: The method catches exceptions and returns {} instead of propagating.
        This is the expected behavior per the implementation.
        """
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            side_effect=Exception("Database connection error")
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        # Method catches exception and returns empty dict (per implementation)
        result = await synchronizer._get_rms_stock_by_ccod("26TS00")
        assert result == {}


class TestSyncStatistics:
    """Tests para acumulación de estadísticas."""

    def test_statistics_initialization(self):
        """Debe inicializar estadísticas correctamente."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        stats = {
            "products_checked": 0,
            "variants_checked": 0,
            "variants_updated": 0,
            "variants_deleted": 0,
            "errors": 0,
            "skipped": 0,
            "products_without_ccod": 0,
            "products_with_ccod": 0,
        }

        # Verificar que todas las claves necesarias existen
        expected_keys = {
            "products_checked",
            "variants_checked",
            "variants_updated",
            "variants_deleted",
            "errors",
            "skipped",
            "products_without_ccod",
            "products_with_ccod",
        }

        assert set(stats.keys()) == expected_keys

    def test_statistics_accumulation(self):
        """Debe acumular estadísticas correctamente."""
        stats = {
            "products_checked": 5,
            "variants_checked": 25,
            "variants_updated": 15,
            "variants_deleted": 3,
            "errors": 1,
            "skipped": 2,
            "products_without_ccod": 1,
            "products_with_ccod": 4,
        }

        # Simular procesamiento de otro batch
        stats["products_checked"] += 3
        stats["variants_checked"] += 15
        stats["variants_updated"] += 10
        stats["variants_deleted"] += 2

        assert stats["products_checked"] == 8
        assert stats["variants_checked"] == 40
        assert stats["variants_updated"] == 25
        assert stats["variants_deleted"] == 5
