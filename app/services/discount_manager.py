"""
Gestor de descuentos automáticos para Shopify.

Este módulo maneja la creación y gestión de descuentos automáticos
basados en las fechas de promoción de RMS.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput

logger = logging.getLogger(__name__)


class DiscountManager:
    """
    Gestiona la creación y actualización de descuentos automáticos en Shopify.
    """

    def __init__(self, shopify_client):
        """
        Inicializa el gestor de descuentos.

        Args:
            shopify_client: Cliente GraphQL de Shopify
        """
        self.shopify_client = shopify_client
        self.discount_function_id = None  # Se obtendrá dinámicamente

    async def initialize(self):
        """
        Inicializa el gestor. No requiere funciones especiales para descuentos básicos.
        """
        try:
            logger.info("🎯 Discount Manager initialized - using basic automatic discounts")
            # No necesitamos obtener funciones de descuento para usar discountAutomaticBasicCreate
            
        except Exception as e:
            logger.error(f"❌ Error initializing discount manager: {e}")

    async def create_discount_for_product(
        self,
        product_id: str,
        shopify_input: ShopifyProductInput,
        sale_start_date: Optional[datetime] = None,
        sale_end_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crea un descuento automático para un producto si tiene precio de oferta.

        Args:
            product_id: ID del producto en Shopify
            shopify_input: Datos del producto con información de precios
            sale_start_date: Fecha de inicio de la promoción
            sale_end_date: Fecha de fin de la promoción

        Returns:
            Dict: Descuento creado o None si no aplica
        """
        try:
            # Verificar si hay precio de oferta
            if not self._has_sale_price(shopify_input):
                logger.info(f"ℹ️ No sale price for product {product_id}, skipping discount")
                return None

            # Calcular el porcentaje de descuento
            discount_percentage = self._calculate_discount_percentage(shopify_input)
            
            if discount_percentage <= 0:
                logger.info(f"ℹ️ Invalid discount percentage for product {product_id}")
                return None

            # Preparar fechas
            start_date = sale_start_date or datetime.now(timezone.utc)
            end_date = sale_end_date
            
            # Crear título del descuento
            discount_title = f"Sale - {shopify_input.title} - {discount_percentage}% OFF"
            
            logger.info(f"🎯 Creating discount: {discount_title}")
            
            # Crear el descuento usando GraphQL
            discount = await self._create_automatic_discount(
                title=discount_title,
                product_id=product_id,
                percentage=discount_percentage,
                starts_at=start_date,
                ends_at=end_date
            )
            
            if discount:
                logger.info(f"✅ Created discount for product {product_id}")
                return discount
            else:
                logger.warning(f"❌ Failed to create discount for product {product_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating discount for product {product_id}: {e}")
            return None

    def _has_sale_price(self, shopify_input: ShopifyProductInput) -> bool:
        """
        Verifica si el producto tiene precio de oferta.

        Args:
            shopify_input: Datos del producto

        Returns:
            bool: True si tiene precio de oferta
        """
        # Verificar si alguna variante tiene compareAtPrice (precio original)
        # y price (precio de oferta) donde price < compareAtPrice
        for variant in shopify_input.variants or []:
            if variant.compareAtPrice and variant.price:
                compare_price = float(variant.compareAtPrice)
                sale_price = float(variant.price)
                if sale_price < compare_price:
                    return True
        return False

    def _calculate_discount_percentage(self, shopify_input: ShopifyProductInput) -> float:
        """
        Calcula el porcentaje de descuento basado en los precios.

        Args:
            shopify_input: Datos del producto

        Returns:
            float: Porcentaje de descuento (0-100)
        """
        max_discount = 0.0
        
        # Calcular el mayor descuento entre todas las variantes
        for variant in shopify_input.variants or []:
            if variant.compareAtPrice and variant.price:
                compare_price = float(variant.compareAtPrice)
                sale_price = float(variant.price)
                
                if compare_price > 0 and sale_price < compare_price:
                    discount = ((compare_price - sale_price) / compare_price) * 100
                    max_discount = max(max_discount, discount)
        
        # Redondear a 2 decimales
        return round(max_discount, 2)

    async def _create_automatic_discount(
        self,
        title: str,
        product_id: str,
        percentage: float,
        starts_at: datetime,
        ends_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crea un descuento automático usando la API GraphQL.
        Utiliza descuentos básicos automáticos de Shopify.

        Args:
            title: Título del descuento
            product_id: ID del producto
            percentage: Porcentaje de descuento
            starts_at: Fecha de inicio
            ends_at: Fecha de fin (opcional)

        Returns:
            Dict: Descuento creado o None
        """
        try:
            # Usar descuento básico automático directamente (según DISCOUNT_SYSTEM_IMPLEMENTATION.md)
            logger.info(f"🎯 Creating basic automatic discount: {percentage}% for product {product_id}")
            return await self._create_basic_automatic_discount(
                title, product_id, percentage, starts_at, ends_at
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating automatic discount: {e}")
            return None

    async def _create_basic_automatic_discount(
        self,
        title: str,
        product_id: str,
        percentage: float,
        starts_at: datetime,
        ends_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crea un descuento automático básico (sin función de app).

        Args:
            title: Título del descuento
            product_id: ID del producto
            percentage: Porcentaje de descuento
            starts_at: Fecha de inicio
            ends_at: Fecha de fin (opcional)

        Returns:
            Dict: Descuento creado o None
        """
        try:
            # Usar descuento automático básico de Shopify
            mutation = """
            mutation discountAutomaticBasicCreate($discount: DiscountAutomaticBasicInput!) {
              discountAutomaticBasicCreate(automaticBasicDiscount: $discount) {
                automaticBasicDiscount {
                  id
                  title
                  status
                  startsAt
                  endsAt
                  customerGets {
                    value {
                      ... on DiscountPercentage {
                        percentage
                      }
                    }
                    items {
                      ... on DiscountProducts {
                        products(first: 5) {
                          edges {
                            node {
                              id
                            }
                          }
                        }
                      }
                    }
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            # Preparar variables
            variables = {
                "discount": {
                    "title": title,
                    "startsAt": starts_at.isoformat(),
                    "combinesWith": {
                        "productDiscounts": False,
                        "shippingDiscounts": True
                    },
                    "customerGets": {
                        "value": {
                            "percentage": percentage / 100  # API espera decimal (0.1 = 10%)
                        },
                        "items": {
                            "products": {
                                "productsToAdd": [product_id]
                            }
                        }
                    }
                }
            }
            
            # Agregar fecha de fin si existe
            if ends_at:
                variables["discount"]["endsAt"] = ends_at.isoformat()
            
            result = await self.shopify_client._execute_query(mutation, variables)
            
            if result and result.get("discountAutomaticBasicCreate"):
                create_result = result["discountAutomaticBasicCreate"]
                
                if create_result.get("userErrors"):
                    logger.error(f"❌ Basic discount creation errors: {create_result['userErrors']}")
                    return None
                
                return create_result.get("automaticBasicDiscount")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error creating basic automatic discount: {e}")
            return None

    async def check_and_update_discounts(
        self,
        product_id: str,
        shopify_input: ShopifyProductInput,
        sale_start_date: Optional[datetime] = None,
        sale_end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verifica y actualiza descuentos para un producto.

        Args:
            product_id: ID del producto
            shopify_input: Datos del producto
            sale_start_date: Fecha de inicio de promoción
            sale_end_date: Fecha de fin de promoción

        Returns:
            Dict: Resultado de la operación
        """
        result = {
            "created": False,
            "updated": False,
            "deleted": False,
            "discount_id": None,
            "message": ""
        }
        
        try:
            # Verificar si el producto necesita descuento
            if self._has_sale_price(shopify_input):
                # Crear o actualizar descuento
                discount = await self.create_discount_for_product(
                    product_id, shopify_input, sale_start_date, sale_end_date
                )
                
                if discount:
                    result["created"] = True
                    result["discount_id"] = discount.get("discountId") or discount.get("id")
                    result["message"] = "Discount created successfully"
                else:
                    result["message"] = "Failed to create discount"
            else:
                # No hay precio de oferta, verificar si hay que eliminar descuento existente
                # TODO: Implementar búsqueda y eliminación de descuentos existentes
                result["message"] = "No sale price, discount not needed"
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Error checking/updating discounts: {e}")
            result["message"] = f"Error: {str(e)}"
            return result


# === FUNCIONES DE CONVENIENCIA ===

async def create_product_discount(
    shopify_client,
    product_id: str,
    shopify_input: ShopifyProductInput,
    sale_dates: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Función de conveniencia para crear descuento de producto.

    Args:
        shopify_client: Cliente de Shopify
        product_id: ID del producto
        shopify_input: Datos del producto
        sale_dates: Diccionario con 'start_date' y 'end_date'

    Returns:
        Dict: Descuento creado o None
    """
    manager = DiscountManager(shopify_client)
    await manager.initialize()
    
    start_date = None
    end_date = None
    
    if sale_dates:
        start_date = sale_dates.get("start_date")
        end_date = sale_dates.get("end_date")
    
    return await manager.create_discount_for_product(
        product_id, shopify_input, start_date, end_date
    )