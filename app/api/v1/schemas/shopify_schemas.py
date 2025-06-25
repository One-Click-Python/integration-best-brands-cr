"""
Modelos Pydantic para datos de Shopify GraphQL API.

Este módulo define los schemas para trabajar con la API GraphQL de Shopify,
incluyendo productos, variantes, inventario y pedidos.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProductStatus(str, Enum):
    """Estados disponibles para productos en Shopify."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DRAFT = "DRAFT"


class FulfillmentStatus(str, Enum):
    """Estados de cumplimiento de pedidos."""

    UNFULFILLED = "UNFULFILLED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    SCHEDULED = "SCHEDULED"
    ON_HOLD = "ON_HOLD"


class FinancialStatus(str, Enum):
    """Estados financieros de pedidos."""

    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    VOIDED = "VOIDED"


# Product Models


class ShopifyOption(BaseModel):
    """Modelo para opciones de producto (ej: Talla, Color)."""

    id: Optional[str] = None
    name: str
    values: List[str]


class ShopifySelectedOption(BaseModel):
    """Modelo para opción seleccionada en una variante."""

    name: str
    value: str


class ShopifyInventoryItem(BaseModel):
    """Modelo para item de inventario."""

    id: str
    tracked: bool = True
    requires_shipping: bool = True


class ShopifyVariant(BaseModel):
    """Modelo para variante de producto."""

    id: Optional[str] = None
    sku: str
    title: Optional[str] = None
    price: str
    compareAtPrice: Optional[str] = None
    inventoryQuantity: Optional[int] = None
    inventoryItem: Optional[ShopifyInventoryItem] = None
    selectedOptions: List[ShopifySelectedOption] = Field(default_factory=list)
    weight: Optional[float] = None
    weightUnit: Optional[str] = "KILOGRAMS"

    @field_validator("price", "compareAtPrice", mode="before")
    @classmethod
    def validate_price(cls, v):
        """Valida y convierte precios a string."""
        if v is None:
            return None
        if isinstance(v, (int, float, Decimal)):
            return str(v)
        return v


class ShopifyProduct(BaseModel):
    """Modelo para producto de Shopify."""

    id: Optional[str] = None
    title: str
    handle: Optional[str] = None
    status: ProductStatus = ProductStatus.DRAFT
    productType: Optional[str] = None
    vendor: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    options: List[ShopifyOption] = Field(default_factory=list)
    variants: List[ShopifyVariant] = Field(default_factory=list)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        """Convierte string de tags a lista."""
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        return v or []


# Input Models for Mutations


class ShopifyVariantInput(BaseModel):
    """Input para crear/actualizar variantes."""

    id: Optional[str] = None
    sku: str
    price: str
    compareAtPrice: Optional[str] = None
    options: Optional[List[str]] = None
    inventoryQuantities: Optional[List[Dict[str, Any]]] = None

    @field_validator("price", "compareAtPrice", mode="before")
    @classmethod
    def validate_price_input(cls, v):
        """Valida y convierte precios a string."""
        if v is None:
            return None
        if isinstance(v, (int, float, Decimal)):
            return str(v)
        return v


class ShopifyProductInput(BaseModel):
    """Input para crear/actualizar productos."""

    id: Optional[str] = None
    title: str
    handle: Optional[str] = None
    status: Optional[ProductStatus] = ProductStatus.DRAFT
    productType: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[str] = None  # Shopify Standard Product Taxonomy category ID
    tags: Optional[List[str]] = None
    options: Optional[List[str]] = None
    variants: Optional[List[ShopifyVariantInput]] = None
    description: Optional[str] = None  # HTML description

    def to_graphql_input(self) -> Dict[str, Any]:
        """Convierte el modelo a formato de input GraphQL para productCreate."""
        # Create a minimal product without options, variants, and description
        # These will be added through separate API calls
        data = self.model_dump(exclude_none=True, exclude={"id", "variants", "options", "description"})

        # Convert tags list to comma-separated string
        if data.get("tags"):
            data["tags"] = ", ".join(data["tags"])

        return data

    def get_variant_data_for_creation(self) -> Optional[Dict[str, Any]]:
        """Obtiene datos de variante formateados para creación separada."""
        if not self.variants:
            return None

        variant = self.variants[0]
        variant_data = variant.model_dump(exclude_none=True, exclude={"id"})

        # For productVariantCreate, we use options array directly
        # No need for selectedOptions when creating the first variant
        # Shopify will automatically create the product options

        return variant_data


# Order Models


class ShopifyMoney(BaseModel):
    """Modelo para representar dinero en Shopify."""

    amount: str
    currencyCode: str


class ShopifyMoneySet(BaseModel):
    """Modelo para conjunto de valores monetarios."""

    shopMoney: ShopifyMoney


class ShopifyAddress(BaseModel):
    """Modelo para direcciones."""

    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None


class ShopifyCustomer(BaseModel):
    """Modelo para cliente."""

    id: str
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None


class ShopifyLineItem(BaseModel):
    """Modelo para línea de pedido."""

    id: str
    title: str
    sku: Optional[str] = None
    quantity: int
    variant: Optional[Dict[str, Any]] = None
    originalUnitPriceSet: Optional[ShopifyMoneySet] = None
    discountedUnitPriceSet: Optional[ShopifyMoneySet] = None


class ShopifyOrder(BaseModel):
    """Modelo para pedido de Shopify."""

    id: str
    name: str  # Order number like #1001
    createdAt: datetime
    updatedAt: datetime
    displayFinancialStatus: Optional[str] = None
    displayFulfillmentStatus: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    customer: Optional[ShopifyCustomer] = None
    shippingAddress: Optional[ShopifyAddress] = None
    billingAddress: Optional[ShopifyAddress] = None
    totalPriceSet: ShopifyMoneySet
    subtotalPriceSet: ShopifyMoneySet
    totalTaxSet: ShopifyMoneySet
    lineItems: List[ShopifyLineItem] = Field(default_factory=list)

    @property
    def order_number(self) -> str:
        """Extrae el número de orden sin el #."""
        return self.name.replace("#", "")

    @property
    def total_amount(self) -> Decimal:
        """Obtiene el monto total como Decimal."""
        return Decimal(self.totalPriceSet.shopMoney.amount)

    @property
    def tax_amount(self) -> Decimal:
        """Obtiene el monto de impuestos como Decimal."""
        return Decimal(self.totalTaxSet.shopMoney.amount)


# Inventory Models


class ShopifyInventoryLevel(BaseModel):
    """Modelo para nivel de inventario."""

    id: Optional[str] = None
    available: int
    inventoryItemId: str
    locationId: str


class ShopifyLocation(BaseModel):
    """Modelo para ubicación de inventario."""

    id: str
    name: str
    isActive: bool = True
    address: Optional[ShopifyAddress] = None


# Bulk Operation Models


class BulkOperationStatus(str, Enum):
    """Estados de operación bulk."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ShopifyBulkOperation(BaseModel):
    """Modelo para operación bulk."""

    id: str
    status: BulkOperationStatus
    errorCode: Optional[str] = None
    createdAt: datetime
    completedAt: Optional[datetime] = None
    objectCount: Optional[int] = None
    fileSize: Optional[int] = None
    url: Optional[str] = None
    partialDataUrl: Optional[str] = None


# Response Models


class ShopifyProductResponse(BaseModel):
    """Respuesta de productos con paginación."""

    products: List[ShopifyProduct]
    pageInfo: Dict[str, Any]
    hasNextPage: bool
    endCursor: Optional[str] = None


class ShopifyOrderResponse(BaseModel):
    """Respuesta de pedidos con paginación."""

    orders: List[ShopifyOrder]
    pageInfo: Dict[str, Any]
    hasNextPage: bool
    endCursor: Optional[str] = None


class ShopifyError(BaseModel):
    """Modelo para errores de Shopify."""

    field: Optional[List[str]] = None
    message: str
    code: Optional[str] = None


class ShopifyMutationResponse(BaseModel):
    """Respuesta base para mutaciones."""

    userErrors: List[ShopifyError] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Verifica si hay errores."""
        return len(self.userErrors) > 0

    @property
    def error_messages(self) -> List[str]:
        """Obtiene lista de mensajes de error."""
        return [error.message for error in self.userErrors]


# Webhook Models


class ShopifyWebhookTopic(str, Enum):
    """Topics disponibles para webhooks."""

    PRODUCTS_CREATE = "PRODUCTS_CREATE"
    PRODUCTS_UPDATE = "PRODUCTS_UPDATE"
    PRODUCTS_DELETE = "PRODUCTS_DELETE"
    INVENTORY_LEVELS_UPDATE = "INVENTORY_LEVELS_UPDATE"
    ORDERS_CREATE = "ORDERS_CREATE"
    ORDERS_UPDATED = "ORDERS_UPDATED"
    ORDERS_FULFILLED = "ORDERS_FULFILLED"


class ShopifyWebhookPayload(BaseModel):
    """Modelo base para payloads de webhook."""

    id: str
    admin_graphql_api_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
