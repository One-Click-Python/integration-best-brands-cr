"""Tests unitarios para Reverse Stock Synchronization (Shopify → RMS)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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

class TestDeleteVariantsSafely:
    """Tests para eliminación segura de variantes."""

    @pytest.mark.asyncio
    async def test_delete_multiple_variants_keeps_at_least_one(self):
        """Debe mantener al menos una variante si preserve_single_variant=True."""
        mock_client = MagicMock()
        mock_client.products.delete_variant = AsyncMock()

        synchronizer = ReverseStockSynchronizer(
            shopify_client=mock_client,
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        variants = [
            {"id": "gid://shopify/ProductVariant/1", "sku": "SKU1"},
            {"id": "gid://shopify/ProductVariant/2", "sku": "SKU2"},
            {"id": "gid://shopify/ProductVariant/3", "sku": "SKU3"},
        ]

        # Intentar eliminar todas (debería dejar 1)
        deleted = await synchronizer._delete_variants_safely(
            variants=variants,
            dry_run=False,
            preserve_single_variant=True,
        )

        # Debería eliminar solo 2 (dejar 1)
        assert len(deleted) == 2
        assert mock_client.products.delete_variant.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_single_variant_when_preserve_enabled(self):
        """No debe eliminar si solo hay 1 variante y preserve=True."""
        mock_client = MagicMock()
        mock_client.products.delete_variant = AsyncMock()

        synchronizer = ReverseStockSynchronizer(
            shopify_client=mock_client,
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        variants = [
            {"id": "gid://shopify/ProductVariant/1", "sku": "SKU1"},
        ]

        deleted = await synchronizer._delete_variants_safely(
            variants=variants,
            dry_run=False,
            preserve_single_variant=True,
        )

        # No debería eliminar nada
        assert len(deleted) == 0
        assert mock_client.products.delete_variant.call_count == 0

    @pytest.mark.asyncio
    async def test_delete_all_variants_when_preserve_disabled(self):
        """Debe eliminar todas las variantes si preserve=False."""
        mock_client = MagicMock()
        mock_client.products.delete_variant = AsyncMock()

        synchronizer = ReverseStockSynchronizer(
            shopify_client=mock_client,
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        variants = [
            {"id": "gid://shopify/ProductVariant/1", "sku": "SKU1"},
            {"id": "gid://shopify/ProductVariant/2", "sku": "SKU2"},
        ]

        deleted = await synchronizer._delete_variants_safely(
            variants=variants,
            dry_run=False,
            preserve_single_variant=False,
        )

        # Debería eliminar todas
        assert len(deleted) == 2
        assert mock_client.products.delete_variant.call_count == 2

    @pytest.mark.asyncio
    async def test_dry_run_does_not_delete(self):
        """En dry-run no debe ejecutar eliminaciones."""
        mock_client = MagicMock()
        mock_client.products.delete_variant = AsyncMock()

        synchronizer = ReverseStockSynchronizer(
            shopify_client=mock_client,
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        variants = [
            {"id": "gid://shopify/ProductVariant/1", "sku": "SKU1"},
            {"id": "gid://shopify/ProductVariant/2", "sku": "SKU2"},
        ]

        deleted = await synchronizer._delete_variants_safely(
            variants=variants,
            dry_run=True,
            preserve_single_variant=False,
        )

        # Debería reportar 2 eliminados pero sin ejecutar
        assert len(deleted) == 2
        assert mock_client.products.delete_variant.call_count == 0


class TestGetRmsStockByCcod:
    """Tests para consulta de stock en RMS por CCOD."""

    @pytest.mark.asyncio
    async def test_get_stock_with_existing_product(self):
        """Debe retornar diccionario de stock cuando el producto existe."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            return_value=[
                {
                    "ItemLookupCode": "26TS00-41-BEIGE",
                    "Quantity": Decimal("5"),
                },
                {
                    "ItemLookupCode": "26TS00-42-BEIGE",
                    "Quantity": Decimal("3"),
                },
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("26TS00")

        assert result == {
            "26TS00-41-BEIGE": 5,
            "26TS00-42-BEIGE": 3,
        }

    @pytest.mark.asyncio
    async def test_get_stock_with_zero_quantities(self):
        """Debe manejar correctamente cantidades en cero."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            return_value=[
                {
                    "ItemLookupCode": "26TS00-41-BEIGE",
                    "Quantity": Decimal("0"),
                },
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("26TS00")

        assert result == {
            "26TS00-41-BEIGE": 0,
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
                {
                    "ItemLookupCode": "TEST-SKU",
                    "Quantity": Decimal("10.00"),
                },
            ]
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        result = await synchronizer._get_rms_stock_by_ccod("TEST")

        assert result == {"TEST-SKU": 10}
        assert isinstance(result["TEST-SKU"], int)


class TestGenerateSyncReport:
    """Tests para generación de reporte de sincronización."""

    def test_report_structure(self):
        """Debe generar reporte con estructura correcta."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        start_time = datetime.now(UTC)
        statistics = {
            "products_checked": 10,
            "variants_checked": 50,
            "variants_updated": 30,
            "variants_deleted": 5,
            "errors": 2,
            "skipped": 3,
            "products_without_ccod": 1,
            "products_with_ccod": 9,
        }
        details = {
            "updated": [
                {"sku": "SKU1", "old_qty": 5, "new_qty": 10},
            ],
            "deleted": [
                {"sku": "SKU2", "reason": "Zero stock"},
            ],
            "errors": [
                {"product": "Product1", "error": "GraphQL error"},
            ],
        }

        report = synchronizer._generate_sync_report(
            sync_id="test_sync_123",
            start_time=start_time,
            statistics=statistics,
            details=details,
            dry_run=False,
            delete_zero_stock=True,
        )

        assert report["sync_id"] == "test_sync_123"
        assert report["dry_run"] is False
        assert report["delete_zero_stock"] is True
        assert report["statistics"] == statistics
        assert report["details"] == details
        assert "timestamp" in report
        assert "duration_seconds" in report
        assert report["duration_seconds"] >= 0

    def test_report_duration_calculation(self):
        """Debe calcular correctamente la duración."""
        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        start_time = datetime(2025, 1, 11, 10, 0, 0, tzinfo=UTC)

        with patch("app.services.reverse_stock_sync.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 11, 10, 5, 30, tzinfo=UTC)

            report = synchronizer._generate_sync_report(
                sync_id="test_sync",
                start_time=start_time,
                statistics={
                    "products_checked": 0,
                    "variants_checked": 0,
                    "variants_updated": 0,
                    "variants_deleted": 0,
                    "errors": 0,
                    "skipped": 0,
                    "products_without_ccod": 0,
                    "products_with_ccod": 0,
                },
                details={"updated": [], "deleted": [], "errors": []},
                dry_run=False,
                delete_zero_stock=True,
            )

            # 5 minutos 30 segundos = 330 segundos
            assert report["duration_seconds"] == 330.0


class TestEdgeCases:
    """Tests para casos especiales y edge cases."""

    @pytest.mark.asyncio
    async def test_empty_product_list(self):
        """Debe manejar correctamente lista vacía de productos."""
        mock_client = MagicMock()
        mock_client.products.query_products = AsyncMock(
            return_value={
                "data": {
                    "products": {
                        "edges": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=mock_client,
            product_repository=MagicMock(),
            primary_location_id="gid://shopify/Location/123",
        )

        report = await synchronizer.execute_reverse_sync(
            dry_run=True,
            delete_zero_stock=True,
            batch_size=50,
            limit=None,
        )

        assert report["statistics"]["products_checked"] == 0
        assert report["statistics"]["variants_checked"] == 0

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
        """Debe manejar errores del repositorio correctamente."""
        mock_repo = MagicMock()
        mock_repo.get_products_by_ccod = AsyncMock(
            side_effect=Exception("Database connection error")
        )

        synchronizer = ReverseStockSynchronizer(
            shopify_client=MagicMock(),
            product_repository=mock_repo,
            primary_location_id="gid://shopify/Location/123",
        )

        # Debería propagar la excepción
        with pytest.raises(Exception, match="Database connection error"):
            await synchronizer._get_rms_stock_by_ccod("26TS00")


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
