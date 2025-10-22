"""
Tests unitarios para la vinculación de órdenes Shopify ↔ RMS.

Este módulo verifica que los campos críticos de vinculación se mapean correctamente
y que las órdenes pueden ser encontradas y actualizadas correctamente.
"""

import pytest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.shopify_to_rms import ShopifyToRMSSync
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


class TestReferenceNumberMapping:
    """Tests para el mapeo correcto del ReferenceNumber."""

    @pytest.mark.asyncio
    async def test_reference_number_format(self, shopify_order_paid):
        """Verifica que ReferenceNumber tenga el formato correcto SHOPIFY-{id}."""
        sync_service = ShopifyToRMSSync()

        # Mock de métodos que no queremos ejecutar realmente
        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar que existe el campo reference_number
            assert "reference_number" in rms_order["order"]

            # Verificar formato correcto
            reference = rms_order["order"]["reference_number"]
            assert reference.startswith("SHOPIFY-")
            assert reference == "SHOPIFY-123456789"

    @pytest.mark.asyncio
    async def test_reference_number_extraction_from_gid(self, shopify_order_paid):
        """Verifica que se extraiga correctamente el ID numérico del GID de Shopify."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # El GID es "gid://shopify/Order/123456789"
            # Debe extraer "123456789"
            reference = rms_order["order"]["reference_number"]
            assert reference.endswith("123456789")


class TestChannelTypeMapping:
    """Tests para el mapeo correcto del ChannelType."""

    @pytest.mark.asyncio
    async def test_channel_type_is_shopify(self, shopify_order_paid):
        """Verifica que ChannelType sea 2 (Shopify)."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar ChannelType
            assert rms_order["order"]["channel_type"] == 2


class TestClosedFieldMapping:
    """Tests para el campo Closed."""

    @pytest.mark.asyncio
    async def test_closed_is_zero_for_new_orders(self, shopify_order_paid):
        """Verifica que Closed sea 0 para órdenes nuevas."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar que Closed sea 0 (abierta)
            assert rms_order["order"]["closed"] == 0


class TestShippingChargeMapping:
    """Tests para el mapeo del costo de envío."""

    @pytest.mark.asyncio
    async def test_shipping_charge_from_shipping_line(self, shopify_order_paid):
        """Verifica que ShippingChargeOnOrder se mapee desde shippingLine."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar que se mapeó el costo de envío
            assert "shipping_charge_on_order" in rms_order["order"]
            assert rms_order["order"]["shipping_charge_on_order"] == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_shipping_charge_zero_when_no_shipping_line(self, shopify_order_paid):
        """Verifica que ShippingChargeOnOrder sea 0 si no hay shippingLine."""
        # Remover shippingLine
        shopify_order_no_shipping = shopify_order_paid.copy()
        shopify_order_no_shipping["shippingLine"] = None

        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_no_shipping)

            # Verificar que sea 0.00
            assert rms_order["order"]["shipping_charge_on_order"] == Decimal("0.00")


class TestDepositCalculation:
    """Tests para el cálculo correcto del depósito."""

    def test_deposit_paid_order(self, shopify_order_paid):
        """Verifica que deposit = total para órdenes PAID."""
        sync_service = ShopifyToRMSSync()

        deposit = sync_service._calculate_deposit(shopify_order_paid)

        # Para PAID, deposit debe ser igual al total
        assert deposit == Decimal("150.00")

    def test_deposit_partially_paid_order(self, shopify_order_partially_paid):
        """Verifica que deposit sume transacciones SALE/CAPTURE para PARTIALLY_PAID."""
        sync_service = ShopifyToRMSSync()

        deposit = sync_service._calculate_deposit(shopify_order_partially_paid)

        # Debe sumar: SALE(100.00) + CAPTURE(50.00) = 150.00
        assert deposit == Decimal("150.00")

    def test_deposit_pending_order(self):
        """Verifica que deposit = 0 para órdenes PENDING."""
        pending_order = {
            "displayFinancialStatus": "PENDING",
            "totalPriceSet": {"shopMoney": {"amount": "100.00"}},
            "transactions": [],
        }

        sync_service = ShopifyToRMSSync()
        deposit = sync_service._calculate_deposit(pending_order)

        assert deposit == Decimal("0.00")

    def test_deposit_authorized_order(self):
        """Verifica que deposit = 0 para órdenes AUTHORIZED (no capturado)."""
        authorized_order = {
            "displayFinancialStatus": "AUTHORIZED",
            "totalPriceSet": {"shopMoney": {"amount": "100.00"}},
            "transactions": [
                {
                    "kind": "AUTHORIZATION",
                    "status": "SUCCESS",
                    "test": False,
                    "amountSet": {"shopMoney": {"amount": "100.00"}},
                }
            ],
        }

        sync_service = ShopifyToRMSSync()
        deposit = sync_service._calculate_deposit(authorized_order)

        # AUTHORIZATION no cuenta como depósito
        assert deposit == Decimal("0.00")

    def test_deposit_excludes_test_transactions(self):
        """Verifica que se excluyan transacciones de prueba."""
        order_with_test = {
            "displayFinancialStatus": "PARTIALLY_PAID",
            "totalPriceSet": {"shopMoney": {"amount": "200.00"}},
            "transactions": [
                {
                    "kind": "SALE",
                    "status": "SUCCESS",
                    "test": True,  # Transacción de prueba
                    "amountSet": {"shopMoney": {"amount": "100.00"}},
                },
                {
                    "kind": "SALE",
                    "status": "SUCCESS",
                    "test": False,  # Transacción real
                    "amountSet": {"shopMoney": {"amount": "50.00"}},
                },
            ],
        }

        sync_service = ShopifyToRMSSync()
        deposit = sync_service._calculate_deposit(order_with_test)

        # Solo debe contar la transacción real
        assert deposit == Decimal("50.00")

    def test_deposit_with_refund(self):
        """Verifica que se resten los REFUND del depósito."""
        order_with_refund = {
            "displayFinancialStatus": "PARTIALLY_REFUNDED",
            "totalPriceSet": {"shopMoney": {"amount": "100.00"}},
            "transactions": [
                {
                    "kind": "SALE",
                    "status": "SUCCESS",
                    "test": False,
                    "amountSet": {"shopMoney": {"amount": "100.00"}},
                },
                {
                    "kind": "REFUND",
                    "status": "SUCCESS",
                    "test": False,
                    "amountSet": {"shopMoney": {"amount": "30.00"}},
                },
            ],
        }

        sync_service = ShopifyToRMSSync()
        deposit = sync_service._calculate_deposit(order_with_refund)

        # SALE(100) - REFUND(30) = 70
        assert deposit == Decimal("70.00")


class TestTaxableFieldMapping:
    """Tests para el mapeo del campo taxable en OrderEntry."""

    @pytest.mark.asyncio
    async def test_taxable_field_mapped_correctly(self, shopify_order_paid):
        """Verifica que el campo taxable se mapee correctamente desde Shopify."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar que line items tengan campo taxable
            line_items = rms_order["line_items"]
            assert len(line_items) > 0

            for line_item in line_items:
                assert "taxable" in line_item
                # El item de prueba tiene taxable=True, debe ser 1
                assert line_item["taxable"] == 1

    @pytest.mark.asyncio
    async def test_taxable_false_maps_to_zero(self):
        """Verifica que taxable=False se mapee a 0."""
        order_non_taxable = {
            "id": "gid://shopify/Order/999",
            "name": "#999",
            "createdAt": "2025-01-15T10:00:00Z",
            "displayFinancialStatus": "PAID",
            "totalPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
            "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
            "totalDiscountsSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
            "shippingLine": None,
            "customer": None,
            "billingAddress": None,
            "shippingAddress": None,
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
                                "product": {"id": "gid://shopify/Product/999"},
                            },
                            "originalUnitPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
                            "discountedUnitPriceSet": {"shopMoney": {"amount": "50.00", "currencyCode": "USD"}},
                        }
                    }
                ]
            },
            "transactions": [],
        }

        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=None),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(order_non_taxable)

            # Verificar que taxable sea 0
            line_items = rms_order["line_items"]
            assert line_items[0]["taxable"] == 0


class TestRMSOrderDataValidation:
    """Tests para la validación de datos de órdenes RMS."""

    def test_validation_passes_with_valid_data(self):
        """Verifica que la validación pase con datos válidos."""
        sync_service = ShopifyToRMSSync()

        valid_order_data = {
            "store_id": 40,
            "time": datetime.now(UTC),
            "type": 1,
            "total": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "deposit": Decimal("100.00"),
            "reference_number": "SHOPIFY-123456",
            "channel_type": 2,
            "closed": 0,
            "shipping_charge_on_order": Decimal("5.00"),
        }

        # No debe lanzar excepción
        sync_service._validate_rms_order_data(valid_order_data)

    def test_validation_fails_missing_required_field(self):
        """Verifica que falle si falta un campo requerido."""
        sync_service = ShopifyToRMSSync()

        invalid_order_data = {
            "store_id": 40,
            "time": datetime.now(UTC),
            "type": 1,
            "total": Decimal("100.00"),
            # Falta: tax, deposit, reference_number, channel_type, closed
        }

        # Debe lanzar ValidationException
        with pytest.raises(ValidationException) as exc_info:
            sync_service._validate_rms_order_data(invalid_order_data)

        assert "Missing required RMS field" in str(exc_info.value)

    def test_validation_fails_invalid_reference_number_format(self):
        """Verifica que falle si ReferenceNumber no empieza con SHOPIFY-."""
        sync_service = ShopifyToRMSSync()

        invalid_order_data = {
            "store_id": 40,
            "time": datetime.now(UTC),
            "type": 1,
            "total": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "deposit": Decimal("100.00"),
            "reference_number": "INVALID-123456",  # No empieza con SHOPIFY-
            "channel_type": 2,
            "closed": 0,
        }

        # Debe lanzar ValidationException
        with pytest.raises(ValidationException) as exc_info:
            sync_service._validate_rms_order_data(invalid_order_data)

        assert "ReferenceNumber must start with SHOPIFY-" in str(exc_info.value)

    def test_validation_fails_negative_total(self):
        """Verifica que falle si total es negativo."""
        sync_service = ShopifyToRMSSync()

        invalid_order_data = {
            "store_id": 40,
            "time": datetime.now(UTC),
            "type": 1,
            "total": Decimal("-100.00"),  # Negativo
            "tax": Decimal("10.00"),
            "deposit": Decimal("0.00"),
            "reference_number": "SHOPIFY-123456",
            "channel_type": 2,
            "closed": 0,
        }

        # Debe lanzar ValidationException
        with pytest.raises(ValidationException) as exc_info:
            sync_service._validate_rms_order_data(invalid_order_data)

        assert "cannot be negative" in str(exc_info.value)


class TestOrderLinkingIntegration:
    """Tests de integración para vinculación completa."""

    @pytest.mark.asyncio
    async def test_complete_order_mapping_flow(self, shopify_order_paid):
        """Test de integración: verifica el flujo completo de mapeo."""
        sync_service = ShopifyToRMSSync()

        with (
            patch.object(sync_service, "_ensure_clients_initialized", new_callable=AsyncMock),
            patch.object(sync_service, "_resolve_customer", new_callable=AsyncMock, return_value=1),
            patch.object(sync_service, "_resolve_sku_to_item_id", new_callable=AsyncMock, return_value=100),
        ):
            rms_order = await sync_service._convert_to_rms_format(shopify_order_paid)

            # Verificar todos los campos críticos de vinculación
            order_data = rms_order["order"]

            # 1. ReferenceNumber
            assert order_data["reference_number"] == "SHOPIFY-123456789"

            # 2. ChannelType
            assert order_data["channel_type"] == 2

            # 3. Closed
            assert order_data["closed"] == 0

            # 4. ShippingChargeOnOrder
            assert order_data["shipping_charge_on_order"] == Decimal("5.00")

            # 5. Deposit calculado correctamente
            assert order_data["deposit"] == Decimal("150.00")

            # 6. Total
            assert order_data["total"] == Decimal("150.00")

            # 7. Tax
            assert order_data["tax"] == Decimal("15.00")

            # 8. StoreID
            assert order_data["store_id"] == 40

            # 9. Type
            assert order_data["type"] == 1

            # Verificar line items
            line_items = rms_order["line_items"]
            assert len(line_items) == 1
            assert line_items[0]["taxable"] == 1
            assert line_items[0]["item_id"] == 100
            assert line_items[0]["price"] == Decimal("70.00")
            assert line_items[0]["full_price"] == Decimal("75.00")

            # Validar que los datos pasen la validación
            sync_service._validate_rms_order_data(order_data)
