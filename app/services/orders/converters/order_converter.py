"""OrderConverter service - converts Shopify orders to domain models (SRP)."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.db.rms.query_executor import QueryExecutor
from app.domain.models import OrderDomain, OrderEntryDomain
from app.domain.value_objects import Money
from app.services.orders.converters.customer_fetcher import CustomerDataFetcher
from app.utils.error_handler import ValidationException

logger = logging.getLogger(__name__)


def _ensure_utc_datetime(dt: datetime | None) -> datetime | None:
    """
    Asegura que un datetime tenga timezone UTC.

    Args:
        dt: Datetime que puede ser naive o aware

    Returns:
        Datetime con timezone UTC, o None si input es None
    """
    if dt is None:
        return None

    # Si ya tiene timezone, retornar tal cual
    if dt.tzinfo is not None:
        return dt

    # Si es naive (sin timezone), asumir que es UTC
    return dt.replace(tzinfo=UTC)


def get_effective_price(
    base_price: Decimal,
    sale_price: Decimal | None,
    sale_start: datetime | None,
    sale_end: datetime | None,
    reference_date: datetime,
) -> Decimal:
    """
    Determina el precio efectivo considerando promociones vigentes en la fecha de referencia.

    Args:
        base_price: Precio regular del producto (sin IVA)
        sale_price: Precio promocional (sin IVA)
        sale_start: Inicio de la promoción
        sale_end: Fin de la promoción
        reference_date: Fecha de referencia (processed_at de Shopify)

    Returns:
        Precio efectivo a usar (con o sin promoción)

    Examples:
        >>> from decimal import Decimal
        >>> from datetime import datetime, UTC
        >>> # Sin promoción
        >>> get_effective_price(Decimal("10000"), None, None, None, datetime.now(UTC))
        Decimal('10000')
        >>> # Con promoción vigente
        >>> get_effective_price(
        ...     Decimal("10000"),
        ...     Decimal("8000"),
        ...     datetime(2025, 1, 1, tzinfo=UTC),
        ...     datetime(2025, 1, 31, tzinfo=UTC),
        ...     datetime(2025, 1, 15, tzinfo=UTC)
        ... )
        Decimal('8000')
    """
    # Si no hay precio de oferta o es 0, usar precio base
    if not sale_price or sale_price <= 0:
        return base_price

    # Si hay promoción vigente en la fecha de referencia, usar sale_price
    if sale_start and sale_end:
        # Asegurar que todas las fechas tengan timezone UTC para comparación
        sale_start_utc = _ensure_utc_datetime(sale_start)
        sale_end_utc = _ensure_utc_datetime(sale_end)
        reference_date_utc = _ensure_utc_datetime(reference_date)

        if sale_start_utc and sale_end_utc and reference_date_utc:
            if sale_start_utc <= reference_date_utc <= sale_end_utc:
                logger.debug(
                    f"Aplicando promoción: SalePrice={sale_price} "
                    f"(vigente desde {sale_start_utc} hasta {sale_end_utc})"
                )
                return sale_price

    # Fuera del periodo promocional, usar precio base
    return base_price


class OrderConverter:
    """Converts Shopify orders to domain models (SRP: Conversion only)."""

    def __init__(self, query_executor: QueryExecutor, customer_fetcher: CustomerDataFetcher | None = None):
        """
        Initialize with SOLID dependencies (DIP).

        Args:
            query_executor: Repository for custom SQL queries (find_item_by_sku)
            customer_fetcher: Service for extracting customer data
        """
        self.query_executor = query_executor
        self.customer_fetcher = customer_fetcher or CustomerDataFetcher()

    async def convert_to_domain(self, shopify_order: dict[str, Any]) -> OrderDomain:
        """Convert Shopify order to domain model."""
        # 🔍 Logging - valores de Shopify
        total_with_tax_shopify = Money.from_string(shopify_order["totalPriceSet"]["shopMoney"]["amount"], "CRC")
        tax_amount_shopify = Money.from_string(
            shopify_order.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", "0"), "CRC"
        )
        logger.info(
            f"🔍 Shopify order financial data: "
            f"totalPriceSet={total_with_tax_shopify.amount}, "
            f"totalTaxSet={tax_amount_shopify.amount}"
        )

        # Convert line items first - necesitamos los datos de RMS para calcular correctamente
        entries_with_tax_info = await self._convert_line_items(shopify_order)

        # Calcular Order.Total y Order.Tax desde los line items (datos de RMS)
        # OrderEntry.price AHORA incluye IVA, necesitamos discriminarlo para calcular Order.Tax
        # Order.Total = suma de (OrderEntry.price * quantity) [YA incluye impuestos]
        # Order.Tax = suma de impuestos discriminados
        total_without_tax = Decimal("0")
        total_tax = Decimal("0")

        for entry, tax_percentage in entries_with_tax_info:
            # entry.price AHORA incluye IVA, calcular subtotal con IVA
            subtotal_with_tax = entry.price.amount * Decimal(str(entry.quantity_on_order))

            # Discriminar para obtener base sin impuestos
            tax_divisor = Decimal("1") + (tax_percentage / Decimal("100"))
            subtotal_without_tax = subtotal_with_tax / tax_divisor

            # Calcular impuesto como la diferencia
            tax_item = subtotal_with_tax - subtotal_without_tax

            total_without_tax += subtotal_without_tax
            total_tax += tax_item

            logger.debug(
                f"  Line item calculation: price_with_tax={entry.price.amount}, qty={entry.quantity_on_order}, "
                f"tax%={tax_percentage}, subtotal_with_tax={subtotal_with_tax}, "
                f"subtotal_without_tax={subtotal_without_tax:.2f}, tax={tax_item:.2f}"
            )

        # Calcular total CON impuestos (subtotal + tax)
        total_with_tax = total_without_tax + total_tax
        total_amount = Money(total_with_tax, "CRC")
        tax_amount = Money(total_tax, "CRC")

        # 🔍 Logging de depuración - valores calculados desde RMS
        logger.info(
            f"✅ Calculated from RMS line items: "
            f"total_amount (WITH tax)={total_amount.amount}, "
            f"tax_amount={tax_amount.amount}, "
            f"subtotal (without tax)={total_without_tax}"
        )

        # Verificar consistencia con Shopify (total_amount ya incluye impuestos)
        if abs(total_amount.amount - total_with_tax_shopify.amount) > Decimal("1.0"):
            diff = abs(total_amount.amount - total_with_tax_shopify.amount)
            logger.warning(
                f"⚠️ Total mismatch: RMS calculated={total_amount.amount} vs "
                f"Shopify={total_with_tax_shopify.amount} (diff={diff})"
            )

        # Extraer solo los entries (sin tax_percentage que ya no necesitamos)
        entries = [entry for entry, _ in entries_with_tax_info]

        order_date = datetime.fromisoformat(shopify_order["createdAt"].replace("Z", "+00:00"))
        shopify_id_numeric = shopify_order["id"].split("/")[-1]

        # Get shipping charge
        shipping_charge = self._extract_shipping_charge(shopify_order)

        # Get customer info for comment (payment_status will be added later in orchestrator)
        customer_info = self.customer_fetcher.fetch_customer_info(shopify_order)
        order_comment = self.customer_fetcher.format_comment_for_rms(
            customer_info, order_name=shopify_order.get("name"), payment_status=None
        )

        # Create order domain model with calculated totals from RMS
        order = OrderDomain(
            store_id=40,
            time=order_date,
            type=2,  # Tipo 2 para órdenes de Shopify
            total=total_amount,
            tax=tax_amount,
            deposit=Money.zero("CRC"),
            reference_number=f"SHOPIFY-{shopify_id_numeric}",
            channel_type=2,
            closed=0,
            shipping_charge_on_order=shipping_charge,
            comment=order_comment,
            shipping_notes="",
            sales_rep_id=1000,
            shipping_service_id=0,
            shipping_tracking_number="",
        )

        # Add line items (already converted above)
        for entry in entries:
            order.add_entry(entry)

        return order

    def _extract_shipping_charge(self, shopify_order: dict[str, Any]) -> Money:
        """Extract shipping charge from order."""
        shipping_line = shopify_order.get("shippingLine")
        if shipping_line:
            shipping_money = (
                shipping_line.get("currentDiscountedPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")
            )
            return Money.from_string(shipping_money, "CRC") if shipping_money else Money.zero("CRC")
        return Money.zero("CRC")

    async def _convert_line_items(
        self, shopify_order: dict[str, Any]
    ) -> list[tuple[OrderEntryDomain, Decimal]]:
        """
        Convert Shopify line items to order entry domain models.

        Returns:
            list of tuples: (OrderEntryDomain, tax_percentage_decimal)
        """
        line_items_data = []

        # Extract line items from GraphQL format
        line_items_raw = shopify_order.get("lineItems", {})
        if isinstance(line_items_raw, dict) and "edges" in line_items_raw:
            line_items = [edge["node"] for edge in line_items_raw["edges"]]
        else:
            line_items = line_items_raw if isinstance(line_items_raw, list) else []

        for item in line_items:
            # Get SKU
            variant_sku = (item.get("variant") or {}).get("sku")
            item_level_sku = item.get("sku")
            item_sku = variant_sku or item_level_sku

            # Fallback to variant ID if no SKU
            if not item_sku or item_sku.strip() == "":
                variant_id = (item.get("variant") or {}).get("id", "")
                if variant_id:
                    variant_id_num = variant_id.split("/")[-1] if "/" in variant_id else variant_id
                    item_sku = f"VAR-{variant_id_num}"
                    logger.info(f"Using variant ID as SKU: {item_sku}")
                else:
                    logger.warning(f"Skipping item without SKU: {item.get('title', 'Unknown')}")
                    continue

            # PASO 1: Obtener fecha de procesamiento de la orden
            processed_at_str = shopify_order.get("processedAt")
            if not processed_at_str:
                # Fallback a createdAt si no hay processedAt
                processed_at_str = shopify_order.get("createdAt")

            order_date = datetime.fromisoformat(processed_at_str.replace("Z", "+00:00"))

            # PASO 2: Resolver SKU → ItemID y obtener datos completos del producto
            rms_item = await self.query_executor.find_item_by_sku(item_sku)
            if not rms_item:
                logger.error(f"Could not find RMS Item for SKU: {item_sku}")
                continue

            item_id = rms_item["item_id"]
            item_cost = Money.from_string(str(rms_item.get("cost") or 0.0), "CRC")

            # PASO 3: Determinar precio efectivo de RMS según promoción vigente en la fecha de pago
            rms_price_decimal = get_effective_price(
                base_price=Decimal(str(rms_item.get("price") or 0)),
                sale_price=Decimal(str(rms_item.get("sale_price") or 0)) if rms_item.get("sale_price") else None,
                sale_start=rms_item.get("sale_start"),
                sale_end=rms_item.get("sale_end"),
                reference_date=order_date,
            )

            # PASO 4: Calcular precio de Shopify discriminado (sin IVA) para validación
            discounted_price_set = item.get("discountedUnitPriceSet", item.get("originalUnitPriceSet"))
            shopify_price_with_tax = Money.from_string(discounted_price_set["shopMoney"]["amount"], "CRC")

            tax_percentage = Decimal(str(rms_item.get("tax_percentage", 13))) / Decimal("100")
            shopify_price_without_tax = shopify_price_with_tax.amount / (Decimal("1") + tax_percentage)

            # PASO 5: Comparar y decidir qué precio usar (unit_price)
            if rms_price_decimal > 0:
                price_diff_percentage = (
                    abs(rms_price_decimal - shopify_price_without_tax) / rms_price_decimal * Decimal("100")
                )

                if price_diff_percentage > Decimal("10"):
                    # Diferencia >10% → Usar precio discriminado de Shopify
                    logger.warning(
                        f"⚠️ Diferencia de precio >10% para SKU {item_sku}: "
                        f"RMS={rms_price_decimal} vs Shopify discriminado={shopify_price_without_tax} "
                        f"({price_diff_percentage:.2f}%). Usando precio de Shopify."
                    )
                    final_price = shopify_price_without_tax
                else:
                    # Diferencia ≤10% → Usar precio de RMS
                    logger.info(
                        f"✅ Usando precio RMS para SKU {item_sku}: {rms_price_decimal} "
                        f"(diferencia con Shopify: {price_diff_percentage:.2f}%)"
                    )
                    final_price = rms_price_decimal
            else:
                # Si RMS no tiene precio válido, usar Shopify
                logger.warning(f"⚠️ RMS price inválido para SKU {item_sku}, usando precio Shopify discriminado")
                final_price = shopify_price_without_tax

            # Aplicar impuesto al precio final para OrderEntry.Price
            final_price_with_tax = final_price * (Decimal("1") + tax_percentage)
            unit_price = Money(final_price_with_tax, "CRC")

            # PASO 6: Calcular full_price usando precio base de RMS (View_Items.Price) + IVA
            base_price_decimal = Decimal(str(rms_item.get("price") or 0))

            if base_price_decimal > 0:
                # Aplicar impuesto al precio base de RMS
                final_full_price = base_price_decimal * (Decimal("1") + tax_percentage)
                logger.debug(
                    f"FullPrice calculado desde View_Items.Price: "
                    f"base={base_price_decimal}, tax={tax_percentage*100:.0f}%, "
                    f"final={final_full_price}"
                )
            else:
                logger.error(
                    f"❌ View_Items.Price es 0 o nulo para SKU {item_sku}. "
                    f"FullPrice se establecerá en 0."
                )
                final_full_price = Decimal("0")

            full_price = Money(final_full_price, "CRC")

            # PASO 7: Obtener taxable desde RMS
            is_taxable = bool(rms_item.get("taxable", True))

            # PASO 8: Logging detallado de la decisión final
            logger.info(
                f"📦 Line item procesado - SKU: {item_sku}, "
                f"Precio final: ₡{final_price_with_tax:.2f} (CON IVA), "
                f"Full price: ₡{final_full_price:.2f} (CON IVA desde View_Items.Price), "
                f"Precio base (sin IVA): ₡{final_price:.2f}, "
                f"Precio RMS base: ₡{base_price_decimal:.2f}, "
                f"Precio RMS efectivo: ₡{rms_price_decimal:.2f}, "
                f"Tax: {tax_percentage*100:.0f}%, "
                f"Taxable: {is_taxable}, "
                f"Promoción aplicada: {rms_price_decimal != base_price_decimal}"
            )

            # PASO 9: Crear domain entry - Price CON IVA, FullPrice=View_Items.Price con IVA
            entry = OrderEntryDomain(
                item_id=item_id,
                store_id=40,
                price=unit_price,
                full_price=full_price,
                cost=item_cost,
                quantity_on_order=float(item["quantity"]),
                quantity_rtd=0.0,
                description=item["title"][:255],
                taxable=is_taxable,
                sales_rep_id=1000,  # Valor estándar para Shopify
                discount_reason_code_id=0,
                return_reason_code_id=0,
                is_add_money=False,
                voucher_id=0,
            )

            # Guardar tax_percentage original (sin dividir por 100) para cálculos de Order
            # tax_percentage está en formato decimal (0.13), lo convertimos a porcentaje (13)
            tax_percentage_whole = tax_percentage * Decimal("100")

            # Retornar tupla (entry, tax_percentage_whole)
            line_items_data.append((entry, tax_percentage_whole))

        if not line_items_data:
            raise ValidationException(
                message=f"No valid line items found for order {shopify_order['id']}",
                field="lineItems",
                invalid_value=shopify_order.get("lineItems", []),
            )

        return line_items_data
