"""
CustomerDataFetcher service for extracting customer information from Shopify orders.

This service follows SRP (Single Responsibility Principle) by focusing only on
extracting and formatting customer data from Shopify order structures.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CustomerDataFetcher:
    """
    Extrae información del cliente desde datos de orden de Shopify.

    Responsabilidades:
    - Extraer nombre completo del cliente
    - Extraer email del cliente
    - Manejar casos de órdenes sin cliente (guest orders)
    - Formatear información para uso en RMS
    """

    def fetch_customer_info(self, shopify_order: dict[str, Any]) -> dict[str, Any]:
        """
        Extrae información del cliente desde una orden de Shopify.

        Args:
            shopify_order: Diccionario con datos de la orden de Shopify

        Returns:
            Dict con formato:
            {
                "name": "Juan Pérez" o "Cliente Invitado",
                "email": "juan@example.com" o "sin-email@guest.com",
                "first_name": "Juan" o "",
                "last_name": "Pérez" o "",
                "is_guest": True/False
            }

        Raises:
            ValueError: Si el formato de la orden es inválido
        """
        try:
            customer = shopify_order.get("customer")

            # Caso 1: Orden sin cliente (guest order)
            if not customer:
                logger.info(f"Order {shopify_order.get('id', 'unknown')} has no customer data - treating as guest")
                return self._create_guest_customer_info(shopify_order)

            # Caso 2: Cliente registrado
            first_name = (customer.get("firstName") or "").strip()
            last_name = (customer.get("lastName") or "").strip()
            email = (customer.get("email") or "").strip()

            # Construir nombre completo
            if first_name or last_name:
                full_name = f"{first_name} {last_name}".strip()
            else:
                full_name = "Cliente Shopify"

            # Validar email
            if not email:
                logger.warning(f"Customer in order {shopify_order.get('id')} has no email")
                email = "sin-email@shopify.com"

            customer_info = {
                "name": full_name,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_guest": False,
            }

            logger.debug(f"Extracted customer info: {customer_info['name']} ({customer_info['email']})")
            return customer_info

        except Exception as e:
            logger.error(f"Error extracting customer info from order: {e}")
            raise ValueError(f"Failed to extract customer information: {str(e)}") from e

    def _create_guest_customer_info(self, shopify_order: dict[str, Any]) -> dict[str, Any]:
        """
        Crea información de cliente para órdenes de invitados (guest orders).

        Args:
            shopify_order: Datos de la orden de Shopify

        Returns:
            Dict con información de cliente invitado
        """
        # Intentar obtener email de la orden (puede existir sin customer)
        order_email = (shopify_order.get("email") or "").strip()

        # Intentar obtener nombre de billing o shipping address
        guest_name = self._extract_name_from_addresses(shopify_order)

        return {
            "name": guest_name,
            "email": order_email if order_email else "invitado@shopify.com",
            "first_name": "",
            "last_name": "",
            "is_guest": True,
        }

    def _extract_name_from_addresses(self, shopify_order: dict[str, Any]) -> str:
        """
        Intenta extraer nombre desde las direcciones de facturación o envío.

        Args:
            shopify_order: Datos de la orden

        Returns:
            str: Nombre extraído o "Cliente Invitado" por defecto
        """
        # Intentar desde billing address
        billing_address = shopify_order.get("billingAddress")
        if billing_address:
            first_name = (billing_address.get("firstName") or "").strip()
            last_name = (billing_address.get("lastName") or "").strip()
            if first_name or last_name:
                return f"{first_name} {last_name}".strip()

        # Intentar desde shipping address
        shipping_address = shopify_order.get("shippingAddress")
        if shipping_address:
            first_name = (shipping_address.get("firstName") or "").strip()
            last_name = (shipping_address.get("lastName") or "").strip()
            if first_name or last_name:
                return f"{first_name} {last_name}".strip()

        # Default para invitados sin nombre
        return "Cliente Invitado"

    def format_comment_for_rms(
        self, customer_info: dict[str, Any], order_name: str | None = None, payment_status: str | None = None
    ) -> str:
        """
        Formatea un comentario para RMS incluyendo información del cliente.

        Args:
            customer_info: Información del cliente obtenida de fetch_customer_info
            order_name: Nombre/número de la orden de Shopify (opcional)
            payment_status: Estado de pago de la orden (ej: PARTIALLY_PAID, PAID, PENDING)

        Returns:
            str: Comentario formateado para campo Comment de RMS

        Example:
            >>> fetcher = CustomerDataFetcher()
            >>> info = {"name": "Juan Pérez", "email": "juan@example.com"}
            >>> comment = fetcher.format_comment_for_rms(info, "ABCD123", "PARTIALLY_PAID")
            >>> print(comment)
            "Order reference: ABCD123, Customer: Juan Pérez, email: juan@example.com, Pago: PARTIALLY_PAID"
        """
        name = customer_info.get("name", "Cliente Desconocido")
        email = customer_info.get("email", "sin-email")

        if order_name:
            # Formato: Order reference: YFHLSHWPO, Customer: Name, email: x@y.com, Pago: PAID
            payment_str = f", Pago: {payment_status}" if payment_status else ""
            return f"Order reference: {order_name}, Customer: {name}, email: {email}{payment_str}"
        else:
            # Sin order_name, solo datos del cliente
            return f"Customer: {name}, email: {email}"
