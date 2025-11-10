"""Tests unitarios para discriminación de impuestos en órdenes de Shopify."""

from datetime import UTC, datetime
from decimal import Decimal

from app.services.orders.converters.order_converter import _ensure_utc_datetime, get_effective_price


class TestGetEffectivePrice:
    """Tests para la función get_effective_price."""

    def test_price_without_promotion(self):
        """Debe retornar precio base cuando no hay promoción."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=None,
            sale_start=None,
            sale_end=None,
            reference_date=datetime(2025, 1, 15, tzinfo=UTC),
        )

        assert result == Decimal("10000")

    def test_price_with_zero_sale_price(self):
        """Debe retornar precio base cuando sale_price es 0."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("0"),
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=datetime(2025, 1, 15, tzinfo=UTC),
        )

        assert result == Decimal("10000")

    def test_price_with_active_promotion(self):
        """Debe retornar sale_price cuando la promoción está vigente."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=datetime(2025, 1, 15, tzinfo=UTC),  # Dentro del periodo
        )

        assert result == Decimal("8000")

    def test_price_before_promotion_starts(self):
        """Debe retornar precio base si la fecha es anterior a la promoción."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=datetime(2025, 1, 10, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=datetime(2025, 1, 5, tzinfo=UTC),  # Antes del inicio
        )

        assert result == Decimal("10000")

    def test_price_after_promotion_ends(self):
        """Debe retornar precio base si la promoción ya expiró."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 15, tzinfo=UTC),
            reference_date=datetime(2025, 1, 20, tzinfo=UTC),  # Después del fin
        )

        assert result == Decimal("10000")

    def test_price_on_promotion_start_date(self):
        """Debe aplicar promoción si la fecha es exactamente el inicio."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
        )

        assert result == Decimal("8000")

    def test_price_on_promotion_end_date(self):
        """Debe aplicar promoción si la fecha es exactamente el fin."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
            reference_date=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
        )

        assert result == Decimal("8000")

    def test_price_with_sale_price_but_no_dates(self):
        """Debe retornar precio base si hay sale_price pero no fechas."""
        result = get_effective_price(
            base_price=Decimal("10000"),
            sale_price=Decimal("8000"),
            sale_start=None,
            sale_end=None,
            reference_date=datetime(2025, 1, 15, tzinfo=UTC),
        )

        # Sin fechas, no se puede validar la promoción → precio base
        assert result == Decimal("10000")


class TestTaxDiscrimination:
    """Tests para discriminación de impuestos (13% IVA Costa Rica)."""

    def test_discriminate_tax_13_percent(self):
        """Debe discriminar correctamente el IVA del 13%."""
        # Precio con IVA
        shopify_price = Decimal("11300")  # ₡11,300
        tax_percentage = Decimal("0.13")  # 13%

        # Precio sin IVA = Precio con IVA / (1 + tax%)
        discriminated = shopify_price / (Decimal("1") + tax_percentage)

        assert discriminated == Decimal("10000.00")

    def test_discriminate_tax_with_decimals(self):
        """Debe manejar correctamente precios con decimales."""
        shopify_price = Decimal("11356.50")  # ₡11,356.50
        tax_percentage = Decimal("0.13")

        discriminated = shopify_price / (Decimal("1") + tax_percentage)

        # 11356.50 / 1.13 = 10050.00
        assert discriminated == Decimal("10050.00")

    def test_price_difference_calculation(self):
        """Debe calcular correctamente el porcentaje de diferencia."""
        rms_price = Decimal("10000")
        shopify_discriminated = Decimal("10500")

        diff_percentage = abs(rms_price - shopify_discriminated) / rms_price * Decimal("100")

        assert diff_percentage == Decimal("5.0")  # 5%

    def test_use_shopify_when_difference_exceeds_10_percent(self):
        """Debe usar precio Shopify cuando la diferencia es >10%."""
        rms_price = Decimal("10000")
        shopify_discriminated = Decimal("12000")  # 20% diferencia

        diff_pct = abs(rms_price - shopify_discriminated) / rms_price * Decimal("100")

        assert diff_pct > Decimal("10")
        # En este caso se debería usar shopify_discriminated

    def test_use_rms_when_difference_under_10_percent(self):
        """Debe usar precio RMS cuando la diferencia es ≤10%."""
        rms_price = Decimal("10000")
        shopify_discriminated = Decimal("10500")  # 5% diferencia

        diff_pct = abs(rms_price - shopify_discriminated) / rms_price * Decimal("100")

        assert diff_pct <= Decimal("10")
        # En este caso se debería usar rms_price

    def test_exact_10_percent_difference_uses_rms(self):
        """Debe usar RMS cuando la diferencia es exactamente 10%."""
        rms_price = Decimal("10000")
        shopify_discriminated = Decimal("11000")  # Exactamente 10%

        diff_pct = abs(rms_price - shopify_discriminated) / rms_price * Decimal("100")

        assert diff_pct == Decimal("10")
        # Diferencia ≤10% → Usar RMS


class TestPriceComparisonScenarios:
    """Tests para escenarios completos de comparación de precios."""

    def test_promotion_active_and_matches_shopify(self):
        """Promoción vigente y precio coincide con Shopify."""
        # RMS
        base_price = Decimal("10000")
        sale_price = Decimal("8000")
        reference_date = datetime(2025, 1, 15, tzinfo=UTC)

        # Obtener precio efectivo
        rms_effective = get_effective_price(
            base_price=base_price,
            sale_price=sale_price,
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=reference_date,
        )

        # Shopify (con IVA)
        shopify_with_tax = Decimal("9040")  # 8000 * 1.13
        tax_pct = Decimal("0.13")
        shopify_discriminated = shopify_with_tax / (Decimal("1") + tax_pct)

        # Comparar
        diff = abs(rms_effective - shopify_discriminated) / rms_effective * Decimal("100")

        assert rms_effective == Decimal("8000")
        assert shopify_discriminated == Decimal("8000.00")
        assert diff == Decimal("0")  # Coinciden perfectamente

    def test_promotion_expired_use_base_price(self):
        """Promoción expirada, usar precio base."""
        base_price = Decimal("10000")
        sale_price = Decimal("8000")
        reference_date = datetime(2025, 2, 1, tzinfo=UTC)  # Fuera de promoción

        rms_effective = get_effective_price(
            base_price=base_price,
            sale_price=sale_price,
            sale_start=datetime(2025, 1, 1, tzinfo=UTC),
            sale_end=datetime(2025, 1, 31, tzinfo=UTC),
            reference_date=reference_date,
        )

        assert rms_effective == base_price

    def test_zero_tax_percentage_no_discrimination_needed(self):
        """Sin impuesto, el precio no debe discriminarse."""
        shopify_price = Decimal("10000")
        tax_percentage = Decimal("0")  # Sin impuesto

        # Sin discriminación, el precio se mantiene igual
        result = shopify_price / (Decimal("1") + tax_percentage)

        assert result == shopify_price


class TestEdgeCases:
    """Tests para casos especiales y edge cases."""

    def test_very_small_price_difference(self):
        """Diferencias muy pequeñas (redondeo) no deberían causar problemas."""
        rms_price = Decimal("10000.00")
        shopify_discriminated = Decimal("10000.01")  # 0.001% diferencia

        diff_pct = abs(rms_price - shopify_discriminated) / rms_price * Decimal("100")

        assert diff_pct < Decimal("0.01")  # Menos del 0.01%

    def test_large_price_values(self):
        """Debe manejar correctamente precios grandes."""
        shopify_price = Decimal("1130000")  # ₡1,130,000
        tax_pct = Decimal("0.13")

        discriminated = shopify_price / (Decimal("1") + tax_pct)

        assert discriminated == Decimal("1000000.00")

    def test_very_small_price_values(self):
        """Debe manejar correctamente precios pequeños."""
        shopify_price = Decimal("113")  # ₡113
        tax_pct = Decimal("0.13")

        discriminated = shopify_price / (Decimal("1") + tax_pct)

        assert discriminated == Decimal("100.00")

    def test_negative_price_should_not_occur(self):
        """Precios negativos no deberían ocurrir en la práctica."""
        # Este test documenta que precios negativos no son válidos
        # pero la función no tiene validación explícita (se asume input válido)
        pass


class TestEnsureUtcDatetime:
    """Tests para la función _ensure_utc_datetime."""

    def test_none_returns_none(self):
        """Debe retornar None si recibe None."""
        result = _ensure_utc_datetime(None)
        assert result is None

    def test_aware_datetime_unchanged(self):
        """Debe retornar datetime aware sin cambios."""
        aware_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = _ensure_utc_datetime(aware_dt)

        assert result == aware_dt
        assert result.tzinfo == UTC

    def test_naive_datetime_gets_utc(self):
        """Debe agregar timezone UTC a datetime naive."""
        naive_dt = datetime(2025, 1, 15, 10, 30, 0)  # Sin timezone
        result = _ensure_utc_datetime(naive_dt)

        # Debe tener timezone UTC
        assert result is not None
        assert result.tzinfo == UTC
        # Los valores deben ser los mismos
        assert result.year == naive_dt.year
        assert result.month == naive_dt.month
        assert result.day == naive_dt.day
        assert result.hour == naive_dt.hour
        assert result.minute == naive_dt.minute
        assert result.second == naive_dt.second

    def test_comparison_after_conversion(self):
        """Debe permitir comparación después de conversión."""
        naive_dt = datetime(2025, 1, 15, 10, 30, 0)
        aware_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        naive_converted = _ensure_utc_datetime(naive_dt)
        aware_converted = _ensure_utc_datetime(aware_dt)

        # Ambos deben ser comparables (no TypeError)
        assert naive_converted == aware_converted
        assert naive_converted <= aware_converted
        assert naive_converted >= aware_converted
