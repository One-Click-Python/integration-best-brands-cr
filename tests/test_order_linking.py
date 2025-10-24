"""
Tests for order synchronization Shopify → RMS using SOLID architecture.

This module verifies that the new SOLID services correctly handle order conversion,
validation, and field mapping from Shopify to RMS.
"""

import pytest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.orders.converters import OrderConverter
from app.services.orders.validators import OrderValidator
from app.services.orders.converters.customer_fetcher import CustomerDataFetcher
from app.domain.models import OrderDomain, OrderEntryDomain
from app.domain.value_objects import Money
from app.utils.error_handler import ValidationException


@pytest.fixture
def shopify_order_paid():
    """Orden de Shopify completamente pagada (PAID)."""
    return {
        "id": "gid://shopify/Order/123456789",
        "name": "#1001",
        "createdAt": "2025-01-15T10:30:00Z",
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "email": "customer@example.com",
        "totalPriceSet": {"shopMoney": {"amount": "150.00", "currencyCode": "USD"}},
        "totalTaxSet": {"shopMoney": {"amount": "15.00", "currencyCode": "USD"}},
        "totalDiscountsSet": {"shopMoney": {"amount": "10.00", "currencyCode": "USD"}},
        "shippingLine": {
            "title": "Standard Shipping",
            "code": "STANDARD",
            "currentDiscountedPriceSet": {"shopMoney": {"amount": "5.00", "currencyCode": "USD"}},
        },
        "customer": {
            "id": "gid://shopify/Customer/987654321",
            "firstName": "John",
            "lastName": "Doe",
            "email": "customer@example.com",
        },
        "billingAddress": {
            "firstName": "John",
            "lastName": "Doe",
            "address1": "123 Main St",
            "city": "New York",
            "province": "NY",
            "country": "United States",
            "zip": "10001",
        },
        "shippingAddress": {
            "firstName": "John",
            "lastName": "Doe",
            "address1": "123 Main St",
            "city": "New York",
            "province": "NY",
            "country": "United States",
            "zip": "10001",
        },
        "lineItems": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/LineItem/111",
                        "title": "Blue Sneakers",
                        "quantity": 2,
                        "sku": "SNEAK-BLUE-42",
                        "taxable": True,
                        "variant": {
                            "id": "gid://shopify/ProductVariant/222",
                            "sku": "SNEAK-BLUE-42",
                            "product": {"id": "gid://shopify/Product/333"},
                        },
                        "originalUnitPriceSet": {"shopMoney": {"amount": "75.00", "currencyCode": "USD"}},
                        "discountedUnitPriceSet": {"shopMoney": {"amount": "70.00", "currencyCode": "USD"}},
                    }
                }
            ]
        },
        "transactions": [
            {
                "id": "gid://shopify/OrderTransaction/1",
                "kind": "SALE",
                "status": "SUCCESS",
                "test": False,
                "amountSet": {"shopMoney": {"amount": "150.00", "currencyCode": "USD"}},
            }
        ],
    }


@pytest.fixture
def shopify_order_partially_paid():
    """Orden de Shopify parcialmente pagada (PARTIALLY_PAID)."""
    return {
        "id": "gid://shopify/Order/123456790",
        "name": "#1002",
        "createdAt": "2025-01-15T11:00:00Z",
        "displayFinancialStatus": "PARTIALLY_PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "email": "customer2@example.com",
        "totalPriceSet": {"shopMoney": {"amount": "200.00", "currencyCode": "USD"}},
        "totalTaxSet": {"shopMoney": {"amount": "20.00", "currencyCode": "USD"}},
        "totalDiscountsSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
        "shippingLine": {
            "title": "Express Shipping",
            "currentDiscountedPriceSet": {"shopMoney": {"amount": "15.00", "currencyCode": "USD"}},
        },
        "customer": {
            "id": "gid://shopify/Customer/987654322",
            "firstName": "Jane",
            "lastName": "Smith",
            "email": "customer2@example.com",
        },
        "billingAddress": {
            "firstName": "Jane",
            "lastName": "Smith",
            "address1": "456 Oak Ave",
            "city": "Los Angeles",
            "province": "CA",
            "country": "United States",
            "zip": "90001",
        },
        "shippingAddress": {
            "firstName": "Jane",
            "lastName": "Smith",
            "address1": "456 Oak Ave",
            "city": "Los Angeles",
            "province": "CA",
            "country": "United States",
            "zip": "90001",
        },
        "lineItems": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/LineItem/112",
                        "title": "Red Boots",
                        "quantity": 1,
                        "sku": "BOOT-RED-38",
                        "taxable": True,
                        "variant": {
                            "id": "gid://shopify/ProductVariant/223",
                            "sku": "BOOT-RED-38",
                            "product": {"id": "gid://shopify/Product/334"},
                        },
                        "originalUnitPriceSet": {"shopMoney": {"amount": "200.00", "currencyCode": "USD"}},
                        "discountedUnitPriceSet": {"shopMoney": {"amount": "200.00", "currencyCode": "USD"}},
                    }
                }
            ]
        },
        "transactions": [
            {
                "id": "gid://shopify/OrderTransaction/2",
                "kind": "SALE",
                "status": "SUCCESS",
                "test": False,
                "amountSet": {"shopMoney": {"amount": "100.00", "currencyCode": "USD"}},
            },
            {
                "id": "gid://shopify/OrderTransaction/3",
                "kind": "CAPTURE",
                "status": "SUCCESS",
                "test": False,
                "amountSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
            },
        ],
    }


@pytest.fixture
def mock_query_executor():
    """Mock QueryExecutor for testing."""
    executor = AsyncMock()
    # Mock SKU lookup to return item data
    executor.find_item_by_sku = AsyncMock(
        return_value={"item_id": 100, "cost": 50.00, "description": "Test Item"}
    )
    executor.is_initialized = MagicMock(return_value=True)
    return executor


class TestReferenceNumberMapping:
    """Tests para el mapeo correcto del ReferenceNumber."""

    @pytest.mark.asyncio
    async def test_reference_number_format(self, shopify_order_paid, mock_query_executor):
        """Verifica que ReferenceNumber tenga el formato correcto SHOPIFY-{id}."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # Verificar formato correcto
        assert order_domain.reference_number.startswith("SHOPIFY-")
        assert order_domain.reference_number == "SHOPIFY-123456789"

    @pytest.mark.asyncio
    async def test_reference_number_extraction_from_gid(self, shopify_order_paid, mock_query_executor):
        """Verifica que se extraiga correctamente el ID numérico del GID de Shopify."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # El GID es "gid://shopify/Order/123456789"
        # Debe extraer "123456789"
        assert order_domain.reference_number.endswith("123456789")


class TestChannelTypeMapping:
    """Tests para el mapeo correcto del ChannelType."""

    @pytest.mark.asyncio
    async def test_channel_type_is_shopify(self, shopify_order_paid, mock_query_executor):
        """Verifica que ChannelType sea 2 (Shopify)."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # Verificar ChannelType
        assert order_domain.channel_type == 2


class TestClosedFieldMapping:
    """Tests para el campo Closed."""

    @pytest.mark.asyncio
    async def test_closed_is_zero_for_new_orders(self, shopify_order_paid, mock_query_executor):
        """Verifica que Closed sea 0 para órdenes nuevas."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # Verificar que Closed sea 0 (abierta)
        assert order_domain.closed == 0


class TestShippingChargeMapping:
    """Tests para el mapeo del costo de envío."""

    @pytest.mark.asyncio
    async def test_shipping_charge_from_shipping_line(self, shopify_order_paid, mock_query_executor):
        """Verifica que ShippingChargeOnOrder se mapee desde shippingLine."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # Verificar que se mapeó el costo de envío
        assert order_domain.shipping_charge_on_order.amount == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_shipping_charge_zero_when_no_shipping_line(self, mock_query_executor):
        """Verifica que ShippingChargeOnOrder sea 0 si no hay shippingLine."""
        # Remover shippingLine
        shopify_order_no_shipping = {
            "id": "gid://shopify/Order/999",
            "name": "#999",
            "createdAt": "2025-01-15T10:00:00Z",
            "displayFinancialStatus": "PAID",
            "totalPriceSet": {"shopMoney": {"amount": "100.00", "currencyCode": "USD"}},
            "totalTaxSet": {"shopMoney": {"amount": "10.00", "currencyCode": "USD"}},
            "totalDiscountsSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
            "shippingLine": None,
            "lineItems": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/LineItem/999",
                            "title": "Test Item",
                            "quantity": 1,
                            "sku": "TEST-001",
                            "taxable": True,
                            "variant": {"id": "gid://shopify/ProductVariant/999", "sku": "TEST-001"},
                            "originalUnitPriceSet": {"shopMoney": {"amount": "90.00", "currencyCode": "USD"}},
                            "discountedUnitPriceSet": {"shopMoney": {"amount": "90.00", "currencyCode": "USD"}},
                        }
                    }
                ]
            },
        }

        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_no_shipping)

        # Verificar que sea 0.00
        assert order_domain.shipping_charge_on_order.amount == Decimal("0.00")


class TestDepositCalculation:
    """Tests para el cálculo correcto del depósito."""

    @pytest.mark.asyncio
    async def test_deposit_defaults_to_zero(self, shopify_order_paid, mock_query_executor):
        """Verifica que deposit se inicialice en 0 (será calculado por otro servicio)."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # En la nueva arquitectura, deposit se inicializa en 0
        # El cálculo del deposit real se hará en otro servicio
        assert order_domain.deposit.amount == Decimal("0.00")

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_paid_order(self, shopify_order_paid):
        """TODO: Implementar servicio de cálculo de depósito para PAID."""
        pass

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_partially_paid_order(self, shopify_order_partially_paid):
        """TODO: Implementar servicio de cálculo de depósito para PARTIALLY_PAID."""
        pass

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_pending_order(self):
        """TODO: Implementar servicio de cálculo de depósito para PENDING."""
        pass

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_authorized_order(self):
        """TODO: Implementar servicio de cálculo de depósito para AUTHORIZED."""
        pass

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_excludes_test_transactions(self):
        """TODO: Implementar servicio de cálculo de depósito excluyendo transacciones de prueba."""
        pass

    @pytest.mark.skip(reason="Deposit calculation not yet implemented in new architecture")
    def test_deposit_with_refund(self):
        """TODO: Implementar servicio de cálculo de depósito con REFUND."""
        pass


class TestTaxableFieldMapping:
    """Tests para el mapeo del campo taxable en OrderEntry."""

    @pytest.mark.asyncio
    async def test_taxable_field_mapped_correctly(self, shopify_order_paid, mock_query_executor):
        """Verifica que el campo taxable se mapee correctamente desde Shopify."""
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(shopify_order_paid)

        # Verificar que line items tengan campo taxable
        assert len(order_domain.entries) > 0

        for entry in order_domain.entries:
            # El item de prueba tiene taxable=True
            assert entry.taxable is True

    @pytest.mark.asyncio
    async def test_taxable_false_maps_to_false(self, mock_query_executor):
        """Verifica que taxable=False se mapee correctamente."""
        order_non_taxable = {
            "id": "gid://shopify/Order/999",
            "name": "#999",
            "createdAt": "2025-01-15T10:00:00Z",
            "displayFinancialStatus": "PAID",
            "totalPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
            "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
            "totalDiscountsSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
            "shippingLine": None,
            "lineItems": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/LineItem/999",
                            "title": "Non-taxable Item",
                            "quantity": 1,
                            "sku": "NON-TAX-001",
                            "taxable": False,  # NO gravable
                            "variant": {
                                "id": "gid://shopify/ProductVariant/999",
                                "sku": "NON-TAX-001",
                            },
                            "originalUnitPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
                            "discountedUnitPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
                        }
                    }
                ]
            },
        }

        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(order_non_taxable)

        # Verificar que taxable sea False
        assert order_domain.entries[0].taxable is False


class TestOrderDomainValidation:
    """Tests para la validación del dominio OrderDomain."""

    def test_validation_passes_with_valid_data(self):
        """Verifica que la validación pase con datos válidos."""
        # Crear orden directamente con datos válidos
        order = OrderDomain(
            store_id=40,
            time=datetime.now(UTC),
            type=2,
            total=Money(Decimal("100.00")),
            tax=Money(Decimal("10.00")),
            deposit=Money(Decimal("0.00")),
            reference_number="SHOPIFY-123456",
            channel_type=2,
            closed=0,
            shipping_charge_on_order=Money(Decimal("5.00")),
            comment="Test order",
        )

        # No debe lanzar excepción
        assert order.reference_number == "SHOPIFY-123456"
        assert order.channel_type == 2

    def test_validation_fails_invalid_reference_number_format(self):
        """Verifica que falle si ReferenceNumber no empieza con SHOPIFY-."""
        # Debe lanzar ValueError en __post_init__
        with pytest.raises(ValueError) as exc_info:
            OrderDomain(
                total=Money(Decimal("100.00")),
                tax=Money(Decimal("10.00")),
                reference_number="INVALID-123456",  # No empieza con SHOPIFY-
                comment="Test",
            )

        assert "Invalid reference number format" in str(exc_info.value)

    def test_validation_fails_negative_total(self):
        """Verifica que falle si total es negativo."""
        # Debe lanzar ValueError en __post_init__
        with pytest.raises(ValueError) as exc_info:
            OrderDomain(
                total=Money(Decimal("-100.00")),  # Negativo
                tax=Money(Decimal("10.00")),
                reference_number="SHOPIFY-123456",
                comment="Test",
            )

        assert "cannot be negative" in str(exc_info.value)


class TestOrderValidatorService:
    """Tests para el servicio OrderValidator."""

    def test_validate_passes_with_valid_order(self, shopify_order_paid):
        """Verifica que la validación pase con una orden válida."""
        validator = OrderValidator()

        # No debe lanzar excepción
        validated = validator.validate(shopify_order_paid)
        assert validated == shopify_order_paid

    def test_validate_fails_missing_required_field(self):
        """Verifica que falle si falta un campo requerido."""
        validator = OrderValidator()

        invalid_order = {
            "id": "gid://shopify/Order/123",
            "name": "#123",
            # Falta: createdAt, totalPriceSet, lineItems
        }

        # Debe lanzar ValidationException
        with pytest.raises(ValidationException) as exc_info:
            validator.validate(invalid_order)

        assert "Missing required field" in str(exc_info.value)

    def test_validate_fails_invalid_financial_status(self):
        """Verifica que falle si el financial status no es válido."""
        validator = OrderValidator()

        invalid_order = {
            "id": "gid://shopify/Order/123",
            "name": "#123",
            "createdAt": "2025-01-15T10:00:00Z",
            "displayFinancialStatus": "PENDING",  # No es PAID, PARTIALLY_PAID, o AUTHORIZED
            "totalPriceSet": {"shopMoney": {"amount": "100.00"}},
            "lineItems": {"edges": [{"node": {"sku": "TEST", "quantity": 1}}]},
        }

        # Debe lanzar ValidationException
        with pytest.raises(ValidationException) as exc_info:
            validator.validate(invalid_order)

        assert "not valid for sync" in str(exc_info.value)


class TestOrderLinkingIntegration:
    """Tests de integración para vinculación completa."""

    @pytest.mark.asyncio
    async def test_complete_order_mapping_flow(self, shopify_order_paid, mock_query_executor):
        """Test de integración: verifica el flujo completo de mapeo."""
        # Step 1: Validate
        validator = OrderValidator()
        validated_order = validator.validate(shopify_order_paid)
        assert validated_order is not None

        # Step 2: Convert to domain
        converter = OrderConverter(mock_query_executor)
        order_domain = await converter.convert_to_domain(validated_order)

        # Verificar todos los campos críticos de vinculación
        # 1. ReferenceNumber
        assert order_domain.reference_number == "SHOPIFY-123456789"

        # 2. ChannelType
        assert order_domain.channel_type == 2

        # 3. Closed
        assert order_domain.closed == 0

        # 4. ShippingChargeOnOrder
        assert order_domain.shipping_charge_on_order.amount == Decimal("5.00")

        # 5. Deposit (inicializado en 0, será calculado por otro servicio)
        assert order_domain.deposit.amount == Decimal("0.00")

        # 6. Total
        assert order_domain.total.amount == Decimal("150.00")

        # 7. Tax
        assert order_domain.tax.amount == Decimal("15.00")

        # 8. StoreID
        assert order_domain.store_id == 40

        # 9. Type
        assert order_domain.type == 2

        # Verificar line items
        assert len(order_domain.entries) == 1
        entry = order_domain.entries[0]
        assert entry.taxable is True
        assert entry.item_id == 100
        assert entry.price.amount == Decimal("70.00")
        assert entry.full_price.amount == Decimal("75.00")
