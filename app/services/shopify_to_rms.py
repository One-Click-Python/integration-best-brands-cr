"""
Servicio de sincronización de pedidos de Shopify hacia RMS.

Este módulo maneja la sincronización de pedidos específicos
desde Shopify hacia Microsoft Retail Management System.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.config import get_settings
from app.core.logging_config import LogContext
from app.services.orders.converters.customer_fetcher import CustomerDataFetcher
from app.services.orders.orchestrator import create_orchestrator
from app.utils.distributed_lock import LockAcquisitionError
from app.utils.error_handler import (
    ErrorAggregator,
    SyncException,
    ValidationException,
)
from app.utils.order_lock import OrderLock

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyToRMSSync:
    """
    Clase principal para sincronización de pedidos Shopify → RMS.
    """

    def __init__(self):
        """Inicializa el servicio de sincronización."""
        self.sync_id = f"shopify_to_rms_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.error_aggregator = ErrorAggregator()
        self.customer_fetcher = CustomerDataFetcher()  # Service for extracting customer data
        self.orchestrator = None  # Will be initialized after RMS handler

        try:
            # Inicializar repositorios SOLID y clientes Shopify
            from app.db.rms.customer_repository import CustomerRepository
            from app.db.rms.order_repository import OrderRepository
            from app.db.rms.product_repository import ProductRepository
            from app.db.rms.query_executor import QueryExecutor
            from app.db.shopify_graphql_client import ShopifyGraphQLClient

            # SOLID repositories
            self.query_executor = QueryExecutor()
            self.customer_repo = CustomerRepository()
            self.order_repo = OrderRepository()
            self.product_repo = ProductRepository()

            self.graphql_client = ShopifyGraphQLClient()
            self.shopify_client = None  # Se inicializará en _ensure_clients_initialized

            logger.info(f"Shopify to RMS sync service initialized - ID: {self.sync_id}")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize Shopify to RMS sync service: {str(e)}",
                service="shopify_to_rms",
                operation="initialize",
            ) from e

    async def _ensure_clients_initialized(self):
        """Asegura que los clientes y repositorios estén inicializados."""
        if self.shopify_client is None:
            from app.db.shopify_order_client import ShopifyOrderClient

            await self.graphql_client.initialize()
            self.shopify_client = ShopifyOrderClient(self.graphql_client)

        # Inicializar repositorios SOLID si es necesario
        if not self.query_executor.is_initialized():
            await self.query_executor.initialize()
        if not self.customer_repo.is_initialized():
            await self.customer_repo.initialize()
        if not self.order_repo.is_initialized():
            await self.order_repo.initialize()
        if not self.product_repo.is_initialized():
            await self.product_repo.initialize()

        # Inicializar orchestrator si es necesario
        if self.orchestrator is None:
            self.orchestrator = create_orchestrator(
                self.query_executor,
                self.customer_repo,
                self.order_repo,
                self.product_repo,
            )

    async def close(self):
        """Cierra los clientes y repositorios."""
        # Cerrar repositorios SOLID
        if self.query_executor:
            await self.query_executor.close()
        if self.customer_repo:
            await self.customer_repo.close()
        if self.order_repo:
            await self.order_repo.close()
        if self.product_repo:
            await self.product_repo.close()

        # Cerrar cliente Shopify
        if self.graphql_client:
            await self.graphql_client.close()

    async def sync_orders(
        self,
        order_ids: List[str],
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        Sincroniza pedidos específicos de Shopify hacia RMS.

        Args:
            order_ids: Lista de IDs de pedidos de Shopify
            skip_validation: Omitir validaciones de negocio

        Returns:
            Dict: Resultado de la sincronización
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Asegurar que los clientes estén inicializados
            await self._ensure_clients_initialized()

            with LogContext(sync_id=self.sync_id, operation="sync_orders"):
                logger.info(f"Starting Shopify to RMS sync for {len(order_ids)} orders")

                # Estadísticas
                stats = {
                    "total_orders": len(order_ids),
                    "processed": 0,
                    "created": 0,
                    "updated": 0,
                    "errors": 0,
                    "skipped": 0,
                }

                # Procesar pedidos en lotes
                batch_size = settings.SYNC_BATCH_SIZE
                for i in range(0, len(order_ids), batch_size):
                    batch = order_ids[i : i + batch_size]
                    batch_results = await self._process_order_batch(batch, skip_validation)

                    # Agregar estadísticas del batch
                    for key in ["processed", "created", "updated", "errors", "skipped"]:
                        stats[key] += batch_results.get(key, 0)

                # Generar reporte final
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                return self._generate_sync_report(stats, duration)

        except Exception as e:
            logger.error(f"Failed to sync Shopify orders: {e}")
            raise SyncException(
                message=f"Failed to sync Shopify orders: {str(e)}",
                service="shopify_to_rms",
                operation="sync_orders",
            ) from e

    async def _process_order_batch(self, order_ids: List[str], skip_validation: bool) -> Dict[str, int]:
        """
        Procesa un lote de pedidos.

        Args:
            order_ids: IDs de pedidos del lote
            skip_validation: Omitir validaciones

        Returns:
            Dict: Estadísticas del lote
        """
        batch_stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0,
        }

        for order_id in order_ids:
            try:
                result = await self._sync_single_order(order_id, skip_validation)
                batch_stats[result["action"]] += 1
                batch_stats["processed"] += 1

            except Exception as e:
                self.error_aggregator.add_error(e, {"order_id": order_id})
                batch_stats["errors"] += 1
                logger.error(f"Failed to sync order {order_id}: {e}")

        return batch_stats

    async def _sync_single_order(self, order_id: str, skip_validation: bool) -> Dict[str, Any]:
        """
        Sincroniza un pedido individual usando el orchestrator (SOLID).

        Uses distributed lock to prevent race conditions when multiple triggers
        (polling, webhooks, manual API) try to sync the same order simultaneously.

        Args:
            order_id: ID del pedido de Shopify
            skip_validation: Omitir validaciones

        Returns:
            Dict: Resultado de la sincronización
        """
        try:
            # 1. Obtener pedido de Shopify
            logger.debug(f"Fetching Shopify order: {order_id}")
            shopify_order = await self.shopify_client.get_order(order_id)

            if not shopify_order:
                raise ValidationException(
                    message=f"Order {order_id} not found in Shopify", field="order_id", invalid_value=order_id
                )

            # 2. Extract numeric ID for lock
            shopify_id_numeric = order_id.split("/")[-1]

            # 3. CRITICAL: Acquire distributed lock BEFORE any check or creation
            # This prevents race conditions between polling, webhooks, and manual API
            try:
                async with OrderLock(shopify_id_numeric, timeout_seconds=120):
                    logger.debug(f"Lock acquired for Shopify order {shopify_id_numeric}")
                    return await self._sync_order_within_lock(
                        order_id, shopify_order, shopify_id_numeric, skip_validation
                    )
            except LockAcquisitionError as e:
                # Another process is already handling this order
                logger.warning(
                    f"Could not acquire lock for order {order_id} after {e.waited:.2f}s - "
                    f"order is being processed by another request"
                )
                return {
                    "order_id": order_id,
                    "action": "skipped",
                    "status": "locked",
                    "rms_order_id": None,
                    "shopify_order_number": shopify_order.get("name", ""),
                    "reason": "Order being processed by another request",
                }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error syncing order {order_id}: {e}")
            raise

    async def _sync_order_within_lock(
        self,
        order_id: str,
        shopify_order: Dict[str, Any],
        shopify_id_numeric: str,
        skip_validation: bool,
    ) -> Dict[str, Any]:
        """
        Synchronize order while holding the distributed lock.

        This method performs the actual sync logic within the safety of the
        OrderLock to prevent duplicate order creation.

        Args:
            order_id: Full Shopify order ID (GID format)
            shopify_order: Shopify order data
            shopify_id_numeric: Numeric Shopify order ID
            skip_validation: Whether to skip order validation

        Returns:
            Dict: Sync result
        """
        # 1. Detectar si orden está cancelada en Shopify
        is_cancelled = shopify_order.get("cancelledAt") is not None
        cancel_reason = shopify_order.get("cancelReason", "")

        # 2. Verificar si ya existe para determinar acción (CRITICAL: deduplication check)
        # Now safe from race conditions because we hold the lock
        try:
            existing_order = await self.order_repo.find_order_by_shopify_id(shopify_id_numeric)
        except Exception as dedup_error:
            # FAIL SAFE: If deduplication check fails after all retries, DON'T create
            # a potentially duplicate order. This prevents data integrity issues.
            logger.error(
                f"DEDUPLICATION CHECK FAILED for order {order_id} after all retries: {dedup_error}. "
                f"Refusing to create potentially duplicate order."
            )
            return {
                "order_id": order_id,
                "action": "deduplication_failed",
                "status": "error",
                "rms_order_id": None,
                "shopify_order_number": shopify_order.get("name", ""),
                "error": f"Could not verify if order exists in RMS: {dedup_error}",
            }

        # 3. Manejar orden cancelada
        if is_cancelled:
            if existing_order:
                # Marcar orden existente como cancelada en RMS
                logger.info(f"Order {order_id} is CANCELLED in Shopify, marking as closed in RMS")
                await self._mark_order_cancelled(existing_order["ID"], cancel_reason or "Cancelled in Shopify")
                return {
                    "order_id": order_id,
                    "action": "cancelled",
                    "rms_order_id": existing_order["ID"],
                    "shopify_order_number": shopify_order.get("name", ""),
                }
            else:
                # Orden cancelada que no existe en RMS → skip (no crear órdenes canceladas)
                logger.info(f"Order {order_id} is CANCELLED and doesn't exist in RMS - skipping")
                return {
                    "order_id": order_id,
                    "action": "skipped",
                    "rms_order_id": None,
                    "shopify_order_number": shopify_order.get("name", ""),
                    "reason": "Order cancelled in Shopify",
                }

        # 4. Actualizar orden existente (no cancelada)
        if existing_order:
            logger.info(f"Order {order_id} already exists in RMS (ID: {existing_order.get('ID')}), updating...")
            result = await self.orchestrator.update_order(
                existing_order["ID"], shopify_order, skip_validation=skip_validation
            )
            logger.info(f"Successfully updated order {order_id} using orchestrator")
            return {
                "order_id": order_id,
                "action": result["action"],
                "rms_order_id": result["rms_order_id"],
                "shopify_order_number": shopify_order.get("name", ""),
            }

        # 5. Crear nueva orden usando orchestrator (SOLID approach)
        # Now safe from duplicates because we hold the lock
        logger.info(f"Creating new order {order_id} using SOLID orchestrator (lock held)")
        result = await self.orchestrator.sync_order(shopify_order, skip_validation=skip_validation)

        logger.info(f"Successfully created order {order_id} using orchestrator")
        return {
            "order_id": order_id,
            "action": result["action"],
            "rms_order_id": result["rms_order_id"],
            "shopify_order_number": shopify_order.get("name", ""),
        }

    async def _mark_order_cancelled(self, rms_order_id: int, cancel_reason: str) -> None:
        """
        Marca una orden como cancelada en RMS.

        Args:
            rms_order_id: ID de la orden en RMS
            cancel_reason: Razón de cancelación desde Shopify
        """
        try:
            comment = "CANCELADA EN SHOPIFY"
            if cancel_reason:
                comment += f": {cancel_reason}"

            await self.order_repo.update_order(rms_order_id, {"closed": True, "comment": comment})
            logger.info(f"✅ Marked RMS order {rms_order_id} as cancelled")

        except Exception as e:
            logger.error(f"❌ Error marking order {rms_order_id} as cancelled: {e}")
            raise SyncException(
                message=f"Failed to mark order as cancelled: {str(e)}",
                service="shopify_to_rms",
                operation="mark_cancelled",
            ) from e

    def _generate_sync_report(self, stats: Dict[str, Any], duration: float) -> Dict[str, Any]:
        """
        Genera reporte final de sincronización.

        Args:
            stats: Estadísticas de la sincronización
            duration: Duración en segundos

        Returns:
            Dict: Reporte completo
        """
        error_summary = self.error_aggregator.get_summary()

        report = {
            "sync_id": self.sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": stats,
            "errors": error_summary,
            "duration_seconds": duration,
            "success_rate": ((stats["processed"] - stats["errors"]) / max(stats["total_orders"], 1) * 100),
        }

        logger.info(f"Shopify to RMS sync completed - ID: {self.sync_id} - Success rate: {report['success_rate']:.1f}%")

        return report


# Funciones de conveniencia para la API
async def sync_shopify_to_rms(
    order_ids: List[str],
    skip_validation: bool = False,
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronizar pedidos de Shopify a RMS.

    Args:
        order_ids: Lista de IDs de pedidos
        skip_validation: Omitir validaciones

    Returns:
        Dict: Resultado de la sincronización
    """
    sync_service = ShopifyToRMSSync()
    try:
        return await sync_service.sync_orders(order_ids, skip_validation)
    finally:
        await sync_service.close()
