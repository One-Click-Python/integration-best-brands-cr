"""
Manejador de webhooks de Shopify para sincronización en tiempo real.

Este módulo procesa webhooks de Shopify para mantener sincronización bidireccional
en tiempo real entre Shopify y RMS.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request

from app.api.v1.schemas.shopify_schemas import (
    ShopifyOrder,
    ShopifyProduct,
)
from app.core.config import get_settings
from app.utils.error_handler import (
    AppException,
    ErrorAggregator,
    ValidationException,
)
from app.utils.retry_handler import get_handler

settings = get_settings()
logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Procesador principal de webhooks de Shopify.
    """

    def __init__(self):
        """Inicializa el procesador de webhooks."""
        self.retry_handler = get_handler("shopify")
        self.error_aggregator = ErrorAggregator()
        self.processed_webhooks = set()  # Para evitar duplicados

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verifica la firma HMAC del webhook.
        
        Args:
            payload: Payload del webhook en bytes
            signature: Firma HMAC del header
            
        Returns:
            bool: True si la firma es válida
        """
        if not settings.SHOPIFY_WEBHOOK_SECRET:
            logger.warning("No webhook secret configured, skipping verification")
            return True

        try:
            # Crear HMAC usando el secret
            expected_signature = hmac.new(
                settings.SHOPIFY_WEBHOOK_SECRET.encode('utf-8'),
                payload,
                hashlib.sha256
            ).digest()
            
            # Comparar con la firma recibida (base64 encoded)
            import base64
            received_signature = base64.b64decode(signature)
            
            # Comparación segura contra timing attacks
            return hmac.compare_digest(expected_signature, received_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    async def process_webhook(
        self,
        topic: str,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Procesa un webhook según su topic.
        
        Args:
            topic: Topic del webhook (ej: products/create)
            payload: Datos del webhook
            webhook_id: ID único del webhook
            
        Returns:
            Dict: Resultado del procesamiento
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Verificar duplicados
            if webhook_id and webhook_id in self.processed_webhooks:
                logger.info(f"Webhook {webhook_id} already processed, skipping")
                return {"status": "skipped", "reason": "duplicate"}

            # Agregar a procesados
            if webhook_id:
                self.processed_webhooks.add(webhook_id)
                # Limpiar cache después de 1000 items
                if len(self.processed_webhooks) > 1000:
                    self.processed_webhooks.clear()

            logger.info(f"Processing webhook: {topic} (ID: {webhook_id})")

            # Enrutar según el topic
            result = await self._route_webhook(topic, payload)
            
            # Registrar éxito
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Webhook processed successfully in {duration:.2f}s: {topic}")
            
            return {
                "status": "success",
                "topic": topic,
                "webhook_id": webhook_id,
                "duration_seconds": duration,
                "result": result
            }

        except Exception as e:
            self.error_aggregator.add_error(e, {
                "topic": topic,
                "webhook_id": webhook_id,
                "payload_keys": list(payload.keys()) if payload else []
            })
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Webhook processing failed in {duration:.2f}s: {topic} - {e}")
            
            return {
                "status": "error",
                "topic": topic,
                "webhook_id": webhook_id,
                "duration_seconds": duration,
                "error": str(e)
            }

    async def _route_webhook(self, topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enruta webhooks a sus manejadores específicos.
        
        Args:
            topic: Topic del webhook
            payload: Datos del webhook
            
        Returns:
            Dict: Resultado del manejador específico
        """
        # Normalizar topic
        topic_normalized = topic.lower().replace("/", "_")
        
        # Mapeo de topics a manejadores
        handlers = {
            "products_create": self._handle_product_create,
            "products_update": self._handle_product_update,
            "products_delete": self._handle_product_delete,
            "orders_create": self._handle_order_create,
            "orders_updated": self._handle_order_update,
            "orders_fulfilled": self._handle_order_fulfilled,
            "inventory_levels_update": self._handle_inventory_update,
            "app_uninstalled": self._handle_app_uninstall,
        }
        
        handler = handlers.get(topic_normalized)
        if not handler:
            logger.warning(f"No handler found for webhook topic: {topic}")
            return {"status": "ignored", "reason": f"unsupported topic: {topic}"}
        
        return await handler(payload)

    async def _handle_product_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja creación de productos en Shopify.
        
        Args:
            payload: Datos del producto creado
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            # Validar payload
            product = self._validate_product_payload(payload)
            
            # En creación, típicamente no necesitamos sincronizar de vuelta a RMS
            # ya que la creación viene de RMS hacia Shopify
            logger.info(f"Product created in Shopify: {product.id} - {product.title}")
            
            # Podríamos actualizar estado en base de datos local si es necesario
            await self._update_local_product_sync_status(
                product.id,
                "created",
                {"created_at": product.createdAt}
            )
            
            return {
                "action": "product_created",
                "product_id": product.id,
                "sku": self._extract_sku_from_variants(payload),
                "sync_needed": False
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process product creation: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_product_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja actualización de productos en Shopify.
        
        Args:
            payload: Datos del producto actualizado
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            # Validar payload
            product = self._validate_product_payload(payload)
            
            # Verificar si la actualización viene de nuestra sincronización
            if await self._is_internal_update(product.id):
                logger.info(f"Internal update detected for {product.id}, skipping sync back")
                return {"action": "internal_update", "skipped": True}
            
            # Si viene de una modificación externa (admin de Shopify),
            # podríamos necesitar sincronizar de vuelta a RMS
            logger.info(f"External product update detected: {product.id} - {product.title}")
            
            # Por ahora, solo loggear - implementar sync bidireccional según necesidades
            await self._update_local_product_sync_status(
                product.id,
                "updated",
                {"updated_at": product.updatedAt}
            )
            
            return {
                "action": "product_updated",
                "product_id": product.id,
                "sku": self._extract_sku_from_variants(payload),
                "sync_needed": False,  # Cambiar a True si implementas sync bidireccional
                "source": "external"
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process product update: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_product_delete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja eliminación de productos en Shopify.
        
        Args:
            payload: Datos del producto eliminado
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            product_id = payload.get("id")
            if not product_id:
                raise ValidationException(
                    message="Product ID missing in delete webhook",
                    field="id",
                    invalid_value=payload.get("id")
                )
            
            logger.info(f"Product deleted in Shopify: {product_id}")
            
            # Actualizar estado local
            await self._update_local_product_sync_status(
                product_id,
                "deleted",
                {"deleted_at": datetime.now(timezone.utc).isoformat()}
            )
            
            return {
                "action": "product_deleted",
                "product_id": product_id,
                "sync_needed": False
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process product deletion: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_order_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja creación de órdenes en Shopify.
        
        Args:
            payload: Datos de la orden creada
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            # Validar y parsear orden
            order = self._validate_order_payload(payload)
            
            logger.info(f"New order created in Shopify: {order.name} - {order.email}")
            
            # Iniciar sincronización a RMS en background
            asyncio.create_task(self._sync_order_to_rms(order, payload))
            
            return {
                "action": "order_created",
                "order_id": order.id,
                "order_number": order.name,
                "customer_email": order.email,
                "total_amount": str(order.total_amount),
                "sync_initiated": True
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process order creation: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_order_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja actualización de órdenes en Shopify.
        
        Args:
            payload: Datos de la orden actualizada
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            order = self._validate_order_payload(payload)
            
            logger.info(f"Order updated in Shopify: {order.name} - Status: {order.displayFinancialStatus}")
            
            # Determinar si necesita sync según el tipo de cambio
            financial_status = order.displayFinancialStatus
            fulfillment_status = order.displayFulfillmentStatus
            
            sync_needed = financial_status in ["PAID", "PARTIALLY_REFUNDED", "REFUNDED"]
            
            if sync_needed:
                asyncio.create_task(self._sync_order_to_rms(order, payload))
            
            return {
                "action": "order_updated",
                "order_id": order.id,
                "order_number": order.name,
                "financial_status": financial_status,
                "fulfillment_status": fulfillment_status,
                "sync_needed": sync_needed
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process order update: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_order_fulfilled(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja cumplimiento de órdenes en Shopify.
        
        Args:
            payload: Datos del cumplimiento
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            order_id = payload.get("order_id")
            if not order_id:
                raise ValidationException(
                    message="Order ID missing in fulfillment webhook",
                    field="order_id",
                    invalid_value=payload.get("order_id")
                )
            
            logger.info(f"Order fulfilled in Shopify: {order_id}")
            
            # Actualizar estado de cumplimiento en RMS si es necesario
            # Esto podría activar procesos de inventario o contabilidad
            
            return {
                "action": "order_fulfilled",
                "order_id": order_id,
                "fulfillment_id": payload.get("id"),
                "tracking_number": payload.get("tracking_number"),
                "sync_needed": True
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process order fulfillment: {str(e)}",
                details={"payload_id": payload.get("id")}
            ) from e

    async def _handle_inventory_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja actualizaciones de inventario en Shopify.
        
        Args:
            payload: Datos de la actualización de inventario
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            inventory_item_id = payload.get("inventory_item_id")
            location_id = payload.get("location_id")
            available = payload.get("available")
            
            logger.info(f"Inventory updated in Shopify: Item {inventory_item_id} at {location_id} = {available}")
            
            # Si la actualización no viene de nuestra sincronización,
            # podríamos necesitar sincronizar de vuelta a RMS
            is_internal = await self._is_internal_inventory_update(inventory_item_id)
            
            return {
                "action": "inventory_updated",
                "inventory_item_id": inventory_item_id,
                "location_id": location_id,
                "available": available,
                "is_internal": is_internal,
                "sync_needed": not is_internal
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process inventory update: {str(e)}",
                details={"payload": payload}
            ) from e

    async def _handle_app_uninstall(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja desinstalación de la app.
        
        Args:
            payload: Datos de la desinstalación
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            shop_domain = payload.get("domain")
            logger.warning(f"App uninstalled from shop: {shop_domain}")
            
            # Limpiar datos locales, cancelar webhooks, etc.
            await self._cleanup_shop_data(shop_domain)
            
            return {
                "action": "app_uninstalled",
                "shop_domain": shop_domain,
                "cleanup_initiated": True
            }
            
        except Exception as e:
            raise AppException(
                message=f"Failed to process app uninstall: {str(e)}",
                details={"payload": payload}
            ) from e

    def _validate_product_payload(self, payload: Dict[str, Any]) -> ShopifyProduct:
        """
        Valida y convierte payload de producto.
        
        Args:
            payload: Payload del webhook
            
        Returns:
            ShopifyProduct: Producto validado
        """
        try:
            # Convertir variants al formato esperado por el schema
            if "variants" in payload:
                variants = []
                for variant in payload["variants"]:
                    variants.append({
                        "id": variant.get("id"),
                        "sku": variant.get("sku", ""),
                        "price": str(variant.get("price", "0")),
                        "compareAtPrice": str(variant.get("compare_at_price")) if variant.get("compare_at_price") else None,
                        "inventoryQuantity": variant.get("inventory_quantity", 0)
                    })
                payload["variants"] = variants
            
            return ShopifyProduct(**payload)
            
        except Exception as e:
            raise ValidationException(
                message=f"Invalid product payload: {str(e)}",
                field="payload",
                invalid_value=str(payload)[:100]
            ) from e

    def _validate_order_payload(self, payload: Dict[str, Any]) -> ShopifyOrder:
        """
        Valida y convierte payload de orden.
        
        Args:
            payload: Payload del webhook
            
        Returns:
            ShopifyOrder: Orden validada
        """
        try:
            # Adaptar estructura del webhook al schema
            adapted_payload = {
                "id": payload.get("id"),
                "name": payload.get("name", payload.get("order_number", "")),
                "createdAt": payload.get("created_at"),
                "updatedAt": payload.get("updated_at"),
                "displayFinancialStatus": payload.get("financial_status", "").upper(),
                "displayFulfillmentStatus": payload.get("fulfillment_status", "").upper(),
                "email": payload.get("email"),
                "phone": payload.get("phone"),
                "totalPriceSet": {
                    "shopMoney": {
                        "amount": payload.get("total_price", "0"),
                        "currencyCode": payload.get("currency", "USD")
                    }
                },
                "subtotalPriceSet": {
                    "shopMoney": {
                        "amount": payload.get("subtotal_price", "0"),
                        "currencyCode": payload.get("currency", "USD")
                    }
                },
                "totalTaxSet": {
                    "shopMoney": {
                        "amount": payload.get("total_tax", "0"),
                        "currencyCode": payload.get("currency", "USD")
                    }
                },
                "lineItems": payload.get("line_items", [])
            }
            
            return ShopifyOrder(**adapted_payload)
            
        except Exception as e:
            raise ValidationException(
                message=f"Invalid order payload: {str(e)}",
                field="payload",
                invalid_value=str(payload)[:100]
            ) from e

    def _extract_sku_from_variants(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extrae SKU de las variantes del payload."""
        variants = payload.get("variants", [])
        if variants and len(variants) > 0:
            return variants[0].get("sku")
        return None

    async def _is_internal_update(self, product_id: str) -> bool:
        """
        Verifica si una actualización viene de nuestro sistema.
        
        Args:
            product_id: ID del producto
            
        Returns:
            bool: True si es actualización interna
        """
        # Implementar lógica para rastrear actualizaciones internas
        # Por ejemplo, usando cache o base de datos
        # Por ahora, retorna False (todas son externas)
        return False

    async def _is_internal_inventory_update(self, inventory_item_id: str) -> bool:
        """
        Verifica si una actualización de inventario viene de nuestro sistema.
        
        Args:
            inventory_item_id: ID del item de inventario
            
        Returns:
            bool: True si es actualización interna
        """
        # Similar a _is_internal_update
        return False

    async def _update_local_product_sync_status(
        self,
        product_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Actualiza estado de sincronización en base de datos local.
        
        Args:
            product_id: ID del producto
            status: Estado de sincronización
            metadata: Metadatos adicionales
        """
        # Implementar actualización en base de datos local
        # Por ahora, solo logging
        logger.debug(f"Would update sync status: {product_id} -> {status} ({metadata})")

    async def _sync_order_to_rms(self, order: ShopifyOrder, raw_payload: Dict[str, Any]):
        """
        Sincroniza orden a RMS en background.
        
        Args:
            order: Orden validada
            raw_payload: Payload original del webhook
        """
        try:
            logger.info(f"Starting background sync of order {order.name} to RMS")
            
            # Aquí iría la lógica para sincronizar a RMS
            # usando el servicio shopify_to_rms
            from app.services.shopify_to_rms import sync_shopify_to_rms
            
            await sync_shopify_to_rms([order.id])
            
            logger.info(f"Successfully synced order {order.name} to RMS")
            
        except Exception as e:
            self.error_aggregator.add_error(e, {
                "order_id": order.id,
                "order_number": order.name
            })
            logger.error(f"Failed to sync order {order.name} to RMS: {e}")

    async def _cleanup_shop_data(self, shop_domain: str):
        """
        Limpia datos cuando se desinstala la app.
        
        Args:
            shop_domain: Dominio de la tienda
        """
        try:
            logger.info(f"Cleaning up data for shop: {shop_domain}")
            
            # Implementar limpieza:
            # - Cancelar webhooks activos
            # - Limpiar datos locales
            # - Notificar a sistemas externos
            
        except Exception as e:
            logger.error(f"Error during cleanup for {shop_domain}: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del procesador de webhooks.
        
        Returns:
            Dict: Métricas actuales
        """
        return {
            "processed_webhooks_cache_size": len(self.processed_webhooks),
            "error_summary": self.error_aggregator.get_summary(),
            "retry_metrics": self.retry_handler.get_metrics(),
        }


# === FUNCIONES AUXILIARES ===

async def validate_webhook_request(request: Request) -> Tuple[str, Dict[str, Any]]:
    """
    Valida una request de webhook de Shopify.
    
    Args:
        request: Request de FastAPI
        
    Returns:
        Tuple: (topic, payload)
        
    Raises:
        HTTPException: Si la validación falla
    """
    # Obtener headers
    topic = request.headers.get("X-Shopify-Topic")
    signature = request.headers.get("X-Shopify-Hmac-Sha256")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain")
    
    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Shopify-Topic header"
        )
    
    # Leer payload
    try:
        payload_bytes = await request.body()
        payload = json.loads(payload_bytes.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON payload: {str(e)}"
        )
    
    # Verificar firma si está configurada
    if signature and settings.SHOPIFY_WEBHOOK_SECRET:
        processor = WebhookProcessor()
        if not processor.verify_webhook_signature(payload_bytes, signature):
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
    
    logger.info(f"Validated webhook: {topic} from {shop_domain}")
    return topic, payload


# === INSTANCIA GLOBAL ===

# Procesador global para webhooks
WEBHOOK_PROCESSOR = WebhookProcessor()