"""
Servicio de gestión de inventario multi-ubicación.

Este módulo maneja la sincronización de inventario entre RMS y múltiples ubicaciones
en Shopify, incluyendo operaciones de actualización y reconciliación.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.utils.error_handler import AppException, ErrorAggregator
from app.utils.retry_handler import get_handler

settings = get_settings()
logger = logging.getLogger(__name__)


class InventoryLocation:
    """Modelo para ubicación de inventario."""

    def __init__(self, id: str, name: str, is_active: bool = True, address: Optional[Dict[str, Any]] = None):
        self.id = id
        self.name = name
        self.is_active = is_active
        self.address = address or {}

    def __repr__(self):
        return f"InventoryLocation(id='{self.id}', name='{self.name}', active={self.is_active})"


class InventoryLevel:
    """Modelo para nivel de inventario en una ubicación."""

    def __init__(
        self,
        inventory_item_id: str,
        location_id: str,
        available: int,
        on_hand: Optional[int] = None,
        committed: Optional[int] = None,
        incoming: Optional[int] = None,
    ):
        self.inventory_item_id = inventory_item_id
        self.location_id = location_id
        self.available = available
        self.on_hand = on_hand
        self.committed = committed
        self.incoming = incoming

    def __repr__(self):
        return (
            f"InventoryLevel(item='{self.inventory_item_id}', "
            f"location='{self.location_id}', available={self.available})"
        )


class InventoryManager:
    """
    Gestor de inventario multi-ubicación para Shopify.

    Proporciona funcionalidades para:
    - Gestión de ubicaciones de inventario
    - Sincronización de niveles de inventario
    - Distribución de inventario entre ubicaciones
    - Reconciliación entre RMS y Shopify
    """

    def __init__(self, shopify_client: Optional[ShopifyGraphQLClient] = None):
        """
        Inicializa el gestor de inventario.

        Args:
            shopify_client: Cliente GraphQL de Shopify (opcional)
        """
        self.shopify_client = shopify_client or ShopifyGraphQLClient()
        self.retry_handler = get_handler("shopify")
        self.error_aggregator = ErrorAggregator()
        self.locations_cache: Dict[str, InventoryLocation] = {}
        self.cache_expiry: Optional[datetime] = None

    async def initialize(self):
        """Inicializa el gestor y carga ubicaciones."""
        if not self.shopify_client.session:
            await self.shopify_client.initialize()

        # Cargar ubicaciones
        await self.refresh_locations()

    async def refresh_locations(self) -> List[InventoryLocation]:
        """
        Actualiza la caché de ubicaciones desde Shopify.

        Returns:
            List[InventoryLocation]: Lista de ubicaciones activas
        """
        try:
            logger.info("Refreshing inventory locations from Shopify")

            shopify_locations = await self.shopify_client.get_locations()

            # Limpiar caché
            self.locations_cache.clear()

            # Procesar ubicaciones
            for location_data in shopify_locations:
                location = InventoryLocation(
                    id=location_data.get("id"),
                    name=location_data.get("name"),
                    is_active=location_data.get("isActive", True),
                    address=location_data.get("address", {}),
                )

                if location.is_active:
                    self.locations_cache[location.id] = location

            self.cache_expiry = datetime.now(timezone.utc)
            logger.info(f"Loaded {len(self.locations_cache)} active locations")

            return list(self.locations_cache.values())

        except Exception as e:
            self.error_aggregator.add_error(e)
            logger.error(f"Failed to refresh locations: {e}")
            raise

    async def get_locations(self, force_refresh: bool = False) -> List[InventoryLocation]:
        """
        Obtiene ubicaciones de inventario con caché.

        Args:
            force_refresh: Forzar actualización de caché

        Returns:
            List[InventoryLocation]: Lista de ubicaciones
        """
        # Verificar si necesita refresh
        needs_refresh = (
            force_refresh
            or not self.locations_cache
            or not self.cache_expiry
            or (datetime.now(timezone.utc) - self.cache_expiry).total_seconds() > 3600  # 1 hora
        )

        if needs_refresh:
            return await self.refresh_locations()

        return list(self.locations_cache.values())

    async def get_primary_location(self) -> Optional[InventoryLocation]:
        """
        Obtiene la ubicación principal.

        Returns:
            InventoryLocation: Ubicación principal o None
        """
        locations = await self.get_locations()

        if not locations:
            return None

        # Por defecto, la primera ubicación activa
        # En un escenario real, podrías tener lógica para identificar la principal
        return locations[0]

    async def update_inventory_single_location(
        self, sku: str, available_quantity: int, location_id: Optional[str] = None
    ) -> bool:
        """
        Actualiza inventario para un SKU en una ubicación específica.

        Args:
            sku: SKU del producto
            available_quantity: Cantidad disponible
            location_id: ID de ubicación (usa principal si no se especifica)

        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            # Obtener ubicación
            if not location_id:
                primary_location = await self.get_primary_location()
                if not primary_location:
                    raise AppException(
                        message="No primary location available for inventory update",
                        details={"sku": sku, "quantity": available_quantity},
                    )
                location_id = primary_location.id

            # Buscar producto por SKU para obtener inventory_item_id
            product = await self.shopify_client.get_product_by_sku(sku)
            if not product:
                raise AppException(message=f"Product not found for SKU: {sku}", details={"sku": sku})

            # Obtener inventory_item_id de la primera variante
            inventory_item_id = None
            variants = product.get("variants", {}).get("edges", [])

            for variant_edge in variants:
                variant = variant_edge.get("node", {})
                if variant.get("sku") == sku:
                    inventory_item = variant.get("inventoryItem")
                    if inventory_item:
                        inventory_item_id = inventory_item.get("id")
                        break

            if not inventory_item_id:
                raise AppException(
                    message=f"Inventory item ID not found for SKU: {sku}",
                    details={"sku": sku, "product_id": product.get("id")},
                )

            # Actualizar inventario
            success = await self.shopify_client.update_inventory(inventory_item_id, location_id, available_quantity)

            if success:
                logger.info(f"Updated inventory for SKU {sku}: {available_quantity} at location {location_id}")
            else:
                logger.warning(f"Failed to update inventory for SKU {sku}")

            return success

        except Exception as e:
            self.error_aggregator.add_error(e, {"sku": sku, "quantity": available_quantity, "location_id": location_id})
            logger.error(f"Error updating inventory for SKU {sku}: {e}")
            return False

    async def update_inventory_multiple_locations(
        self, sku: str, location_quantities: Dict[str, int]
    ) -> Dict[str, bool]:
        """
        Actualiza inventario para un SKU en múltiples ubicaciones.

        Args:
            sku: SKU del producto
            location_quantities: Dict con location_id -> quantity

        Returns:
            Dict[str, bool]: Resultado por ubicación
        """
        try:
            # Validar ubicaciones
            valid_locations = await self.get_locations()
            valid_location_ids = {loc.id for loc in valid_locations}

            invalid_locations = set(location_quantities.keys()) - valid_location_ids
            if invalid_locations:
                logger.warning(f"Invalid location IDs provided: {invalid_locations}")
                # Filtrar ubicaciones inválidas
                location_quantities = {
                    loc_id: qty for loc_id, qty in location_quantities.items() if loc_id in valid_location_ids
                }

            if not location_quantities:
                raise AppException(
                    message="No valid locations provided for inventory update",
                    details={"sku": sku, "provided_locations": list(location_quantities.keys())},
                )

            # Actualizar en paralelo con límite de concurrencia
            semaphore = asyncio.Semaphore(3)  # Máximo 3 actualizaciones paralelas

            async def update_location(location_id: str, quantity: int) -> Tuple[str, bool]:
                async with semaphore:
                    success = await self.update_inventory_single_location(sku, quantity, location_id)
                    return location_id, success

            # Ejecutar actualizaciones
            tasks = [update_location(loc_id, qty) for loc_id, qty in location_quantities.items()]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Procesar resultados
            update_results = {}
            for result in results:
                if isinstance(result, Exception):
                    self.error_aggregator.add_error(result, {"sku": sku})
                    continue

                location_id, success = result  # type: ignore
                update_results[location_id] = success

            # Log resumen
            successful_updates = sum(1 for success in update_results.values() if success)
            logger.info(
                f"Multi-location inventory update for SKU {sku}: "
                f"{successful_updates}/{len(location_quantities)} successful"
            )

            return update_results

        except Exception as e:
            self.error_aggregator.add_error(e, {"sku": sku, "location_quantities": location_quantities})
            logger.error(f"Error in multi-location inventory update for SKU {sku}: {e}")
            raise

    async def distribute_inventory(
        self, sku: str, total_quantity: int, distribution_strategy: str = "primary_only"
    ) -> Dict[str, int]:
        """
        Distribuye inventario entre ubicaciones según una estrategia.

        Args:
            sku: SKU del producto
            total_quantity: Cantidad total a distribuir
            distribution_strategy: Estrategia de distribución

        Returns:
            Dict[str, int]: Distribución por ubicación
        """
        try:
            locations = await self.get_locations()
            if not locations:
                raise AppException(
                    message="No locations available for inventory distribution",
                    details={"sku": sku, "total_quantity": total_quantity},
                )

            distribution = {}

            if distribution_strategy == "primary_only":
                # Todo el inventario a la ubicación principal
                primary = await self.get_primary_location()
                if primary:
                    distribution[primary.id] = total_quantity

            elif distribution_strategy == "equal_split":
                # Dividir igualmente entre todas las ubicaciones
                quantity_per_location = total_quantity // len(locations)
                remainder = total_quantity % len(locations)

                for i, location in enumerate(locations):
                    distribution[location.id] = quantity_per_location
                    if i < remainder:  # Distribuir resto
                        distribution[location.id] += 1

            elif distribution_strategy == "weighted":
                # Distribución ponderada (implementación básica)
                # En un escenario real, podrías usar datos históricos de ventas
                primary = await self.get_primary_location()
                if primary and len(locations) > 1:
                    distribution[primary.id] = int(total_quantity * 0.7)  # 70% principal
                    remaining = total_quantity - distribution[primary.id]

                    other_locations = [loc for loc in locations if loc.id != primary.id]
                    if other_locations:
                        per_other = remaining // len(other_locations)
                        for location in other_locations:
                            distribution[location.id] = per_other
                else:
                    # Fallback a primary_only
                    if primary:
                        distribution[primary.id] = total_quantity

            else:
                raise AppException(
                    message=f"Unknown distribution strategy: {distribution_strategy}",
                    details={"sku": sku, "strategy": distribution_strategy},
                )

            logger.info(f"Calculated distribution for SKU {sku}: {distribution}")
            return distribution

        except Exception as e:
            self.error_aggregator.add_error(
                e, {"sku": sku, "total_quantity": total_quantity, "strategy": distribution_strategy}
            )
            logger.error(f"Error calculating inventory distribution for SKU {sku}: {e}")
            raise

    async def sync_inventory_from_rms(
        self, rms_inventory_data: List[Dict[str, Any]], distribution_strategy: str = "primary_only"
    ) -> Dict[str, Any]:
        """
        Sincroniza inventario desde RMS aplicando estrategia de distribución.

        Args:
            rms_inventory_data: Lista de datos de inventario desde RMS
            distribution_strategy: Estrategia de distribución

        Returns:
            Dict: Estadísticas de sincronización
        """
        try:
            logger.info(f"Starting inventory sync from RMS: {len(rms_inventory_data)} items")
            start_time = datetime.now(timezone.utc)

            sync_stats = {
                "total_items": len(rms_inventory_data),
                "successful_updates": 0,
                "failed_updates": 0,
                "skipped_items": 0,
                "locations_updated": set(),
                "errors": [],
            }

            # Procesar en lotes para no sobrecargar la API
            batch_size = 10
            for i in range(0, len(rms_inventory_data), batch_size):
                batch = rms_inventory_data[i : i + batch_size]

                # Procesar lote
                batch_results = await self._process_inventory_batch(batch, distribution_strategy)

                # Agregar estadísticas
                for result in batch_results:
                    if result["success"]:
                        sync_stats["successful_updates"] += 1
                        sync_stats["locations_updated"].update(result.get("locations", []))
                    else:
                        sync_stats["failed_updates"] += 1
                        sync_stats["errors"].append(result.get("error"))

                # Pausa entre lotes
                if i + batch_size < len(rms_inventory_data):
                    await asyncio.sleep(0.5)

            # Finalizar estadísticas
            end_time = datetime.now(timezone.utc)
            sync_stats.update(
                {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": (end_time - start_time).total_seconds(),
                    "locations_updated": list(sync_stats["locations_updated"]),
                    "success_rate": (
                        sync_stats["successful_updates"] / sync_stats["total_items"] * 100
                        if sync_stats["total_items"] > 0
                        else 0
                    ),
                    "error_summary": self.error_aggregator.get_summary(),
                }
            )

            logger.info(
                f"Inventory sync completed: {sync_stats['successful_updates']}/{sync_stats['total_items']} "
                f"successful ({sync_stats['success_rate']:.1f}%) in {sync_stats['duration_seconds']:.2f}s"
            )

            return sync_stats

        except Exception as e:
            self.error_aggregator.add_error(e)
            logger.error(f"Error in inventory sync from RMS: {e}")
            raise

    async def _process_inventory_batch(
        self, batch: List[Dict[str, Any]], distribution_strategy: str
    ) -> List[Dict[str, Any]]:
        """
        Procesa un lote de actualizaciones de inventario.

        Args:
            batch: Lote de datos de inventario
            distribution_strategy: Estrategia de distribución

        Returns:
            List[Dict]: Resultados del lote
        """
        results = []

        for item in batch:
            try:
                sku = item.get("sku")
                quantity = int(item.get("quantity", 0))

                if not sku:
                    results.append({"success": False, "error": "Missing SKU", "item": item})
                    continue

                # Calcular distribución
                distribution = await self.distribute_inventory(sku, quantity, distribution_strategy)

                # Aplicar distribución
                if distribution:
                    update_results = await self.update_inventory_multiple_locations(sku, distribution)

                    # Verificar éxito
                    successful_locations = [loc_id for loc_id, success in update_results.items() if success]

                    if successful_locations:
                        results.append(
                            {
                                "success": True,
                                "sku": sku,
                                "quantity": quantity,
                                "locations": successful_locations,
                                "distribution": distribution,
                            }
                        )
                    else:
                        results.append(
                            {
                                "success": False,
                                "error": "All location updates failed",
                                "sku": sku,
                                "distribution": distribution,
                            }
                        )
                else:
                    results.append(
                        {"success": False, "error": "No distribution calculated", "sku": sku, "quantity": quantity}
                    )

            except Exception as e:
                results.append({"success": False, "error": str(e), "item": item})

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del gestor de inventario.

        Returns:
            Dict: Métricas actuales
        """
        return {
            "cached_locations": len(self.locations_cache),
            "cache_expiry": self.cache_expiry.isoformat() if self.cache_expiry else None,
            "error_summary": self.error_aggregator.get_summary(),
            "locations": [
                {"id": loc.id, "name": loc.name, "is_active": loc.is_active} for loc in self.locations_cache.values()
            ],
        }

