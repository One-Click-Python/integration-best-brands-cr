"""
Servicio de operaciones en lote para Shopify.

Este módulo implementa operaciones bulk para manejar grandes volúmenes de datos
usando la API de Bulk Operations de Shopify, que no tiene límites de rate.
"""

import asyncio
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp

from app.core.config import get_settings
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.db.shopify_graphql_queries import (
    BULK_OPERATION_PRODUCTS_QUERY,
    BULK_OPERATION_STATUS_QUERY,
)
from app.utils.error_handler import AppException, ErrorAggregator
from app.utils.retry_handler import get_handler

settings = get_settings()
logger = logging.getLogger(__name__)


class BulkOperationStatus:
    """Estados de operaciones bulk."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ShopifyBulkOperations:
    """
    Servicio para manejar operaciones bulk de Shopify.

    Las operaciones bulk permiten extraer o procesar grandes cantidades de datos
    sin estar limitados por rate limits de la API normal.
    """

    def __init__(self, shopify_client: Optional[ShopifyGraphQLClient] = None):
        """
        Inicializa el servicio de operaciones bulk.

        Args:
            shopify_client: Cliente GraphQL de Shopify (opcional)
        """
        self.shopify_client = shopify_client or ShopifyGraphQLClient()
        self.retry_handler = get_handler("shopify")
        self.error_aggregator = ErrorAggregator()

    async def initialize(self):
        """Inicializa el cliente si no está inicializado."""
        if not self.shopify_client.session:
            await self.shopify_client.initialize()

    async def extract_all_products_bulk(
        self, fields: Optional[List[str]] = None, timeout_minutes: int = 30
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extrae todos los productos usando operación bulk.

        Args:
            fields: Campos específicos a extraer
            timeout_minutes: Timeout para la operación

        Returns:
            Tuple: (productos, estadísticas)
        """
        logger.info("Starting bulk product extraction")
        start_time = datetime.now(timezone.utc)

        try:
            # Inicializar cliente
            await self.initialize()

            # Crear query bulk personalizada si se especifican campos
            if fields:
                bulk_query = self._create_custom_product_query(fields)
            else:
                bulk_query = BULK_OPERATION_PRODUCTS_QUERY

            # Iniciar operación bulk
            operation_id = await self._start_bulk_operation(bulk_query)
            logger.info(f"Started bulk operation: {operation_id}")

            # Esperar a que complete
            operation_result = await self._wait_for_completion(operation_id, timeout_minutes * 60)

            if operation_result["status"] != BulkOperationStatus.COMPLETED:
                raise AppException(
                    message=f"Bulk operation failed with status: {operation_result['status']}", details=operation_result
                )

            # Descargar y procesar resultados
            products = await self._download_and_parse_results(operation_result["url"])

            # Generar estadísticas
            end_time = datetime.now(timezone.utc)
            stats = {
                "operation_id": operation_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "total_products": len(products),
                "file_size_bytes": operation_result.get("fileSize", 0),
                "object_count": operation_result.get("objectCount", 0),
                "errors": self.error_aggregator.get_summary(),
            }

            logger.info(f"Bulk extraction completed: {len(products)} products in {stats['duration_seconds']:.2f}s")
            return products, stats

        except Exception as e:
            self.error_aggregator.add_error(e)
            logger.error(f"Bulk product extraction failed: {e}")
            raise

    async def _start_bulk_operation(self, query: str) -> str:
        """
        Inicia una operación bulk.

        Args:
            query: Query GraphQL para la operación bulk

        Returns:
            str: ID de la operación
        """
        try:
            result = await self.shopify_client._execute_query(query)

            bulk_operation = result.get("bulkOperationRunQuery", {})
            user_errors = bulk_operation.get("userErrors", [])

            if user_errors:
                error_messages = [error["message"] for error in user_errors]
                raise AppException(
                    message=f"Failed to start bulk operation: {', '.join(error_messages)}",
                    details={"user_errors": user_errors},
                )

            operation = bulk_operation.get("bulkOperation", {})
            operation_id = operation.get("id")

            if not operation_id:
                raise AppException(
                    message="No operation ID returned from bulk operation", details={"response": bulk_operation}
                )

            return operation_id

        except Exception as e:
            raise AppException(
                message=f"Failed to start bulk operation: {str(e)}", details={"original_error": str(e)}
            ) from e

    async def _wait_for_completion(self, operation_id: str, timeout_seconds: int = 1800) -> Dict[str, Any]:
        """
        Espera a que una operación bulk complete.

        Args:
            operation_id: ID de la operación
            timeout_seconds: Timeout en segundos

        Returns:
            Dict: Resultado de la operación
        """
        start_time = datetime.now(timezone.utc)
        check_interval = 5  # Empezar con 5 segundos
        max_interval = 30  # Máximo 30 segundos

        while True:
            # Verificar timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise AppException(
                    message=f"Bulk operation timed out after {timeout_seconds} seconds",
                    details={"operation_id": operation_id, "elapsed": elapsed},
                )

            # Consultar estado
            try:
                variables = {"id": operation_id}
                result = await self.shopify_client._execute_query(
                    BULK_OPERATION_STATUS_QUERY,
                    variables,
                    use_retry=False,  # No usar retry aquí para evitar delays
                )

                operation = result.get("node", {})
                if not operation:
                    raise AppException(
                        message=f"Bulk operation not found: {operation_id}", details={"operation_id": operation_id}
                    )

                status = operation.get("status")
                logger.debug(f"Bulk operation {operation_id} status: {status}")

                # Verificar si completó
                if status == BulkOperationStatus.COMPLETED:
                    return operation

                elif status in [BulkOperationStatus.FAILED, BulkOperationStatus.CANCELED, BulkOperationStatus.EXPIRED]:
                    raise AppException(
                        message=f"Bulk operation failed with status: {status}",
                        details={
                            "operation_id": operation_id,
                            "status": status,
                            "error_code": operation.get("errorCode"),
                            "operation_details": operation,
                        },
                    )

                # Esperar antes del siguiente check con backoff progresivo
                await asyncio.sleep(check_interval)
                check_interval = min(check_interval * 1.2, max_interval)

            except Exception as e:
                if isinstance(e, AppException):
                    raise

                logger.warning(f"Error checking bulk operation status: {e}")
                await asyncio.sleep(check_interval)

    async def _download_and_parse_results(self, download_url: str) -> List[Dict[str, Any]]:
        """
        Descarga y parsea los resultados de una operación bulk.

        Args:
            download_url: URL para descargar resultados

        Returns:
            List: Productos parseados
        """
        if not download_url:
            logger.warning("No download URL provided, returning empty results")
            return []

        try:
            logger.info(f"Downloading bulk results from: {urlparse(download_url).netloc}")

            # Descargar archivo
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise AppException(
                            message=f"Failed to download bulk results: HTTP {response.status}",
                            details={"download_url": download_url, "status": response.status},
                        )

                    content = await response.text()

            # Parsear JSONL (JSON Lines)
            products = []
            lines = content.strip().split("\n")

            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)

                    # Filtrar solo productos (no variantes u otros objetos)
                    if data.get("__typename") == "Product":
                        products.append(data)

                except json.JSONDecodeError as e:
                    self.error_aggregator.add_error(
                        AppException(
                            message=f"Failed to parse line {line_num}: {str(e)}",
                            details={"line": line[:100], "line_number": line_num},
                        )
                    )
                    continue

            logger.info(f"Parsed {len(products)} products from {len(lines)} lines")
            return products

        except Exception as e:
            raise AppException(
                message=f"Failed to download and parse bulk results: {str(e)}", details={"download_url": download_url}
            ) from e

    def _create_custom_product_query(self, fields: List[str]) -> str:
        """
        Crea una query personalizada para operación bulk.

        Args:
            fields: Campos a incluir en la query

        Returns:
            str: Query GraphQL personalizada
        """
        # Campos base siempre incluidos
        base_fields = ["id", "title", "handle"]
        all_fields = list(set(base_fields + fields))

        # Construir query fields
        field_str = "\n".join([f"              {field}" for field in all_fields])

        # Incluir variantes si se solicitan campos relacionados
        variant_fields = ["sku", "price", "inventoryQuantity"]
        include_variants = any(field in variant_fields for field in fields)

        variants_query = ""
        if include_variants:
            variant_field_str = "\n".join([f"                  {field}" for field in variant_fields if field in fields])
            variants_query = f"""
            variants {{
              edges {{
                node {{
{variant_field_str}
                }}
              }}
            }}"""

        query = f"""
        mutation BulkProductsQuery {{
          bulkOperationRunQuery(
            query: \"\"\"
            {{
              products {{
                edges {{
                  node {{
{field_str}{variants_query}
                  }}
                }}
              }}
            }}
            \"\"\"
          ) {{
            bulkOperation {{
              id
              status
              errorCode
              createdAt
              objectCount
              url
            }}
            userErrors {{
              field
              message
            }}
          }}
        }}
        """

        return query

    async def bulk_update_inventory(
        self, inventory_updates: List[Dict[str, Any]], chunk_size: int = 100
    ) -> Dict[str, Any]:
        """
        Actualiza inventario en lote usando múltiples operaciones paralelas.

        Args:
            inventory_updates: Lista de actualizaciones de inventario
            chunk_size: Tamaño de chunks para procesamiento

        Returns:
            Dict: Estadísticas de la operación
        """
        logger.info(f"Starting bulk inventory update for {len(inventory_updates)} items")
        start_time = datetime.now(timezone.utc)

        try:
            await self.initialize()

            # Dividir en chunks
            chunks = [inventory_updates[i : i + chunk_size] for i in range(0, len(inventory_updates), chunk_size)]

            # Procesar chunks en paralelo (con límite de concurrencia)
            semaphore = asyncio.Semaphore(5)  # Máximo 5 chunks paralelos

            async def process_chunk(chunk):
                async with semaphore:
                    return await self.shopify_client.batch_update_inventory(chunk)

            # Ejecutar todos los chunks
            chunk_results = await asyncio.gather(*[process_chunk(chunk) for chunk in chunks], return_exceptions=True)

            # Consolidar resultados
            total_success = 0
            total_errors = []

            for i, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    self.error_aggregator.add_error(result, {"chunk": i})
                    total_errors.extend([{"chunk": i, "error": str(result)}])
                else:
                    success_count, chunk_errors = result  # type: ignore
                    total_success += success_count
                    total_errors.extend(chunk_errors)

            # Generar estadísticas
            end_time = datetime.now(timezone.utc)
            stats = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "total_items": len(inventory_updates),
                "successful_updates": total_success,
                "failed_updates": len(total_errors),
                "chunks_processed": len(chunks),
                "success_rate": (total_success / len(inventory_updates) * 100) if inventory_updates else 0,
                "errors": total_errors[:10],  # Primeros 10 errores para logging
                "error_summary": self.error_aggregator.get_summary(),
            }

            logger.info(
                f"Bulk inventory update completed: {total_success}/{len(inventory_updates)} successful "
                f"({stats['success_rate']:.1f}%) in {stats['duration_seconds']:.2f}s"
            )

            return stats

        except Exception as e:
            self.error_aggregator.add_error(e)
            logger.error(f"Bulk inventory update failed: {e}")
            raise

    async def export_products_to_csv(
        self, file_path: str, fields: Optional[List[str]] = None, include_variants: bool = True
    ) -> Dict[str, Any]:
        """
        Exporta productos a un archivo CSV usando operación bulk.

        Args:
            file_path: Ruta del archivo CSV a crear
            fields: Campos específicos a exportar
            include_variants: Si incluir variantes como filas separadas

        Returns:
            Dict: Estadísticas de la exportación
        """
        logger.info(f"Starting CSV export to: {file_path}")
        start_time = datetime.now(timezone.utc)

        try:
            # Extraer productos usando bulk operation
            products, bulk_stats = await self.extract_all_products_bulk(fields)

            # Preparar datos para CSV
            csv_rows = []

            for product in products:
                if include_variants and product.get("variants", {}).get("edges"):
                    # Una fila por variante
                    for variant_edge in product["variants"]["edges"]:
                        variant = variant_edge["node"]
                        row = {
                            "product_id": product.get("id", ""),
                            "product_title": product.get("title", ""),
                            "product_handle": product.get("handle", ""),
                            "product_type": product.get("productType", ""),
                            "vendor": product.get("vendor", ""),
                            "variant_id": variant.get("id", ""),
                            "variant_sku": variant.get("sku", ""),
                            "variant_price": variant.get("price", ""),
                            "inventory_quantity": variant.get("inventoryQuantity", 0),
                        }
                        csv_rows.append(row)
                else:
                    # Una fila por producto
                    row = {
                        "product_id": product.get("id", ""),
                        "product_title": product.get("title", ""),
                        "product_handle": product.get("handle", ""),
                        "product_type": product.get("productType", ""),
                        "vendor": product.get("vendor", ""),
                        "variant_count": len(product.get("variants", {}).get("edges", [])),
                    }
                    csv_rows.append(row)

            # Escribir CSV
            if csv_rows:
                async with aiofiles.open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = csv_rows[0].keys()

                    # Crear contenido CSV en memoria
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(csv_rows)

                    # Escribir al archivo
                    await csvfile.write(output.getvalue())

            # Generar estadísticas
            end_time = datetime.now(timezone.utc)
            stats = {
                "file_path": file_path,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "total_products": len(products),
                "csv_rows": len(csv_rows),
                "include_variants": include_variants,
                "bulk_operation_stats": bulk_stats,
                "error_summary": self.error_aggregator.get_summary(),
            }

            logger.info(f"CSV export completed: {len(csv_rows)} rows written to {file_path}")
            return stats

        except Exception as e:
            self.error_aggregator.add_error(e)
            logger.error(f"CSV export failed: {e}")
            raise

    async def get_bulk_operation_status(self, operation_id: str) -> Dict[str, Any]:
        """
        Obtiene el estado de una operación bulk.

        Args:
            operation_id: ID de la operación

        Returns:
            Dict: Estado de la operación
        """
        try:
            await self.initialize()

            variables = {"id": operation_id}
            result = await self.shopify_client._execute_query(BULK_OPERATION_STATUS_QUERY, variables)

            operation = result.get("node", {})
            if not operation:
                raise AppException(
                    message=f"Bulk operation not found: {operation_id}", details={"operation_id": operation_id}
                )

            return {
                "id": operation.get("id"),
                "status": operation.get("status"),
                "error_code": operation.get("errorCode"),
                "created_at": operation.get("createdAt"),
                "completed_at": operation.get("completedAt"),
                "object_count": operation.get("objectCount"),
                "file_size": operation.get("fileSize"),
                "download_url": operation.get("url"),
                "partial_data_url": operation.get("partialDataUrl"),
            }

        except Exception as e:
            logger.error(f"Failed to get bulk operation status: {e}")
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del servicio de operaciones bulk.

        Returns:
            Dict: Métricas actuales
        """
        return {
            "error_summary": self.error_aggregator.get_summary(),
            "retry_metrics": self.retry_handler.get_metrics() if self.retry_handler else None,
        }

