"""
Modelos Pydantic para datos de RMS basados en las especificaciones del cliente.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RMSViewItem(BaseModel):
    """
    Modelo para la vista View_Items de RMS.
    Basado en la estructura proporcionada por Les Antonio.
    """

    # Clasificación del producto
    familia: Optional[str] = Field(None, max_length=50, description="Clasificación general del producto")
    genero: Optional[str] = Field(None, max_length=20, description="Público objetivo")
    categoria: Optional[str] = Field(None, max_length=50, description="Categoría del producto")

    # Códigos identificadores
    ccod: Optional[str] = Field(None, max_length=20, description="Código de modelo (Modelo + color)")
    c_articulo: str = Field(..., max_length=20, description="Código final único del artículo (SKU)")
    item_id: int = Field(..., description="ID secuencial RMS")

    # Información del producto
    description: Optional[str] = Field(None, max_length=150, description="Nombre comercial completo")
    color: Optional[str] = Field(None, max_length=30, description="Color del artículo")
    talla: Optional[str] = Field(None, max_length=10, description="Código o texto de talla")

    # Inventario y precios
    quantity: int = Field(default=0, ge=0, description="Cantidad disponible")
    price: Decimal = Field(..., decimal_places=2, description="Precio de lista antes de impuestos")

    # Promociones y ofertas
    sale_start_date: Optional[datetime] = Field(None, description="Fecha de inicio de oferta")
    sale_end_date: Optional[datetime] = Field(None, description="Fecha de fin de oferta")
    sale_price: Optional[Decimal] = Field(None, decimal_places=2, description="Precio de oferta")

    # Clasificación extendida e impuestos
    extended_category: Optional[str] = Field(None, max_length=80, description="Agrupación extendida para filtros")
    tax: int = Field(default=13, description="Porcentaje de impuesto")

    # Existencias (campos informativos)
    exis00: Optional[int] = Field(None, description="Existencia en bodega principal")
    exis57: Optional[int] = Field(None, description="Existencia alternativa")

    @field_validator("price", "sale_price", mode="before")
    @classmethod
    def validate_prices(cls, v):
        """Valida que los precios sean positivos."""
        if v is not None and v < 0:
            raise ValueError("Los precios deben ser positivos")
        return v

    @field_validator("sale_start_date", "sale_end_date", mode="before")
    @classmethod
    def validate_sale_dates(cls, v):
        """Valida fechas de promoción."""
        if v is not None and isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                return None
        return v

    @property
    def is_on_sale(self) -> bool:
        """
        Verifica si el producto está en oferta con validación de fechas.

        Criterios:
        1. Debe tener sale_price válido y menor al precio regular
        2. Si hay fechas de promoción, debe estar dentro del período activo
        3. Si no hay fechas, se considera válido (promoción sin límite de tiempo)
        """
        # Verificar si hay precio de oferta válido
        if not (self.sale_price and self.sale_price > 0 and self.sale_price < self.price):
            return False

        # Si hay fechas definidas, verificar que estemos dentro del período
        if self.sale_start_date and self.sale_end_date:
            from datetime import timezone

            now = datetime.now(timezone.utc)

            # Asegurar que las fechas tienen timezone
            start_date = self.sale_start_date
            end_date = self.sale_end_date

            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            # Verificar que estemos dentro del período de promoción
            is_within_period = start_date <= now <= end_date

            if not is_within_period:
                return False  # Fuera del período de promoción

        # Si llegamos aquí, está en oferta (ya sea sin fechas o dentro del período)
        return True

    @property
    def effective_price(self) -> Decimal:
        """Obtiene el precio efectivo (considerando promociones)."""
        if self.is_on_sale and self.sale_price:
            return self.sale_price
        return self.price

    @property
    def has_variants(self) -> bool:
        """Verifica si el producto tiene variantes (color/talla)."""
        return bool(self.color or self.talla)


class RMSOrder(BaseModel):
    """
    Modelo para la tabla Order de RMS.
    Representa la cabecera de una orden de venta.
    """

    id: Optional[int] = Field(None, description="ID único de la orden (identity)")
    store_id: int = Field(default=40, description="ID de la tienda (40 para tienda virtual)")
    time: datetime = Field(default_factory=datetime.now, description="Fecha y hora de creación")
    type: int = Field(default=1, description="Tipo de orden (1=venta, 2=devolución, etc.)")
    customer_id: Optional[int] = Field(None, description="ID del cliente")

    # Valores financieros
    deposit: Decimal = Field(default=Decimal("0.00"), decimal_places=2, description="Depósito inicial")
    tax: Decimal = Field(default=Decimal("0.00"), decimal_places=2, description="Impuestos totales")
    total: Decimal = Field(..., decimal_places=2, description="Total de la orden")

    # Personal y envío
    sales_rep_id: Optional[int] = Field(None, description="ID del vendedor")
    shipping_service_id: Optional[int] = Field(None, description="ID del servicio de envío")
    shipping_tracking_number: Optional[str] = Field(None, max_length=100, description="Número de seguimiento")

    # Identificación externa
    reference_number: Optional[str] = Field(None, max_length=50, description="Número de referencia (ej: SHOPIFY-123456)")
    channel_type: int = Field(default=1, description="Tipo de canal (1=tienda, 2=Shopify, 3=web, etc.)")

    # Comentarios
    comment: Optional[str] = Field(None, max_length=500, description="Comentarios del usuario")
    shipping_notes: Optional[str] = Field(None, max_length=500, description="Notas de envío")


class RMSOrderEntry(BaseModel):
    """
    Modelo para la tabla OrderEntry de RMS.
    Representa las líneas de productos dentro de una orden.
    """

    id: Optional[int] = Field(None, description="ID único de la línea (identity)")
    order_id: int = Field(..., description="ID de la orden padre")
    item_id: int = Field(..., description="ID del producto (ItemID de View_Items)")

    # Precios y costos
    price: Decimal = Field(..., decimal_places=2, description="Precio unitario con descuentos aplicados")
    full_price: Decimal = Field(..., decimal_places=2, description="Precio base sin descuentos")
    cost: Optional[Decimal] = Field(None, decimal_places=2, description="Costo del producto")

    # Cantidades
    quantity_on_order: float = Field(..., gt=0, description="Cantidad pedida")
    quantity_rtd: float = Field(default=0, description="Cantidad despachada")

    # Información adicional
    sales_rep_id: Optional[int] = Field(None, description="ID del vendedor")
    discount_reason_code_id: Optional[int] = Field(None, description="Código de razón de descuento")
    return_reason_code_id: Optional[int] = Field(None, description="Código de razón de devolución")
    description: Optional[str] = Field(None, max_length=255, description="Descripción del producto")

    # Campos especiales
    is_add_money: bool = Field(default=False, description="Indica si es un cargo adicional")
    voucher_id: Optional[int] = Field(None, description="ID de cupón o voucher si aplica")


class RMSOrderHistory(BaseModel):
    """
    Modelo para la tabla OrderHistory de RMS.
    Auditoría de movimientos de órdenes.
    """

    id: Optional[int] = Field(None, description="ID único del movimiento")
    order_id: int = Field(..., description="ID de la orden")
    batch_number: Optional[str] = Field(None, max_length=50, description="Lote de procesamiento")
    date: datetime = Field(default_factory=datetime.now, description="Fecha del movimiento")
    cashier_id: Optional[int] = Field(None, description="ID del cajero responsable")
    delta_deposit: Decimal = Field(default=Decimal("0.00"), decimal_places=2, description="Cambio en depósito")
    transaction_number: Optional[int] = Field(None, description="Número de transacción dentro del batch")
    comment: Optional[str] = Field(None, max_length=255, description="Descripción del movimiento")


# Modelos de respuesta y agregación


class RMSOrderWithEntries(BaseModel):
    """
    Modelo agregado que incluye una orden con sus líneas.
    """

    order: RMSOrder
    entries: list[RMSOrderEntry]
    history: Optional[list[RMSOrderHistory]] = None


class RMSProductSyncStatus(BaseModel):
    """
    Modelo para tracking del estado de sincronización de productos.
    """

    c_articulo: str = Field(..., description="SKU del producto")
    last_synced: Optional[datetime] = Field(None, description="Última sincronización")
    shopify_product_id: Optional[str] = Field(None, description="ID en Shopify")
    shopify_variant_id: Optional[str] = Field(None, description="ID de variante en Shopify")
    sync_status: str = Field(default="pending", description="Estado: pending, synced, error")
    error_message: Optional[str] = Field(None, description="Mensaje de error si aplica")


class RMSSyncBatch(BaseModel):
    """
    Modelo para lotes de sincronización.
    """

    batch_id: str = Field(..., description="ID único del lote")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = Field(None)
    total_items: int = Field(default=0)
    processed_items: int = Field(default=0)
    success_items: int = Field(default=0)
    error_items: int = Field(default=0)
    status: str = Field(default="running")  # running, completed, failed
