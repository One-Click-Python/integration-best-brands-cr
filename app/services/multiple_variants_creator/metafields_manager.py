#!/usr/bin/env python3
"""
Manejo de metafields para productos en Shopify.

Este módulo se encarga específicamente de:
- Crear metafields para productos
- Actualizar metafields existentes
- Validar estructura de metafields
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MetafieldsManager:
    """
    Maneja todas las operaciones relacionadas con metafields de productos.
    """

    def __init__(self, shopify_client):
        """
        Inicializa el manejador de metafields.

        Args:
            shopify_client: Cliente de Shopify GraphQL
        """
        self.shopify_client = shopify_client

    async def create_metafields(self, product_id: str, metafields: List[Dict[str, Any]]) -> None:
        """
        Crea metafields para el producto.

        Args:
            product_id: ID del producto
            metafields: Lista de metafields a crear
        """
        try:
            metafields_set_input = []
            for metafield in metafields:
                metafield_input = {
                    "key": metafield["key"],
                    "namespace": metafield["namespace"],
                    "ownerId": product_id,
                    "type": metafield["type"],
                    "value": metafield["value"],
                }
                metafields_set_input.append(metafield_input)

            # Usar metafieldsSet mutation
            metafields_mutation = """
            mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
              metafieldsSet(metafields: $metafields) {
                metafields {
                  id
                  key
                  value
                  definition {
                    name
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """

            metafields_result = await self.shopify_client._execute_query(
                metafields_mutation, {"metafields": metafields_set_input}
            )

            if metafields_result and metafields_result.get("metafieldsSet"):
                set_result = metafields_result["metafieldsSet"]

                if set_result.get("userErrors"):
                    logger.warning(f"Metafields errors: {set_result['userErrors']}")

                created_metafields = set_result.get("metafields", [])
                logger.info(f"✅ Created {len(created_metafields)} metafields")

        except Exception as e:
            logger.warning(f"❌ Failed to create metafields: {e}")

    async def update_metafields(self, product_id: str, metafields: List[Dict[str, Any]]) -> None:
        """
        Actualiza metafields del producto. Si no existen, los crea.

        Args:
            product_id: ID del producto
            metafields: Lista de metafields a actualizar/crear
        """
        try:
            # Por simplicidad, usar el mismo método que crear metafields
            # metafieldsSet es upsert (crea o actualiza según el caso)
            await self.create_metafields(product_id, metafields)
            logger.info(f"✅ Updated metafields for product {product_id}")

        except Exception as e:
            logger.warning(f"❌ Failed to update metafields: {e}")

    def _validate_metafield_value(self, value: Any, metafield_type: str) -> Dict[str, Any]:
        """
        Valida el valor de un metafield según su tipo.

        Args:
            value: Valor a validar
            metafield_type: Tipo del metafield

        Returns:
            Dict: Resultado de la validación del valor
        """
        try:
            if metafield_type == "string":
                if not isinstance(value, str):
                    return {"valid": False, "error": f"Value must be string, got {type(value).__name__}"}
                if len(value) > 5000:  # Límite aproximado de Shopify
                    return {"valid": False, "error": "String value too long (max 5000 characters)"}

            elif metafield_type == "integer":
                try:
                    int(value)
                except (ValueError, TypeError):
                    return {"valid": False, "error": f"Value '{value}' is not a valid integer"}

            elif metafield_type == "number":
                try:
                    float(value)
                except (ValueError, TypeError):
                    return {"valid": False, "error": f"Value '{value}' is not a valid number"}

            elif metafield_type == "boolean":
                if not isinstance(value, bool) and str(value).lower() not in ["true", "false"]:
                    return {"valid": False, "error": f"Value '{value}' is not a valid boolean"}

            elif metafield_type == "date":
                # Validación básica de formato de fecha
                if not isinstance(value, str) or len(value) != 10:
                    return {"valid": False, "error": "Date must be in YYYY-MM-DD format"}

            elif metafield_type == "date_time":
                # Validación básica de formato de fecha y hora
                if not isinstance(value, str) or "T" not in value:
                    return {"valid": False, "error": "DateTime must be in ISO 8601 format"}

            elif metafield_type == "url":
                if not isinstance(value, str) or not (value.startswith("http://") or value.startswith("https://")):
                    return {"valid": False, "error": "URL must start with http:// or https://"}

            elif metafield_type == "json":
                import json

                try:
                    if isinstance(value, str):
                        json.loads(value)
                    elif not isinstance(value, (dict, list)):
                        return {"valid": False, "error": "JSON value must be a valid JSON string, dict, or list"}
                except json.JSONDecodeError:
                    return {"valid": False, "error": "Invalid JSON format"}

            return {"valid": True}

        except Exception as e:
            return {"valid": False, "error": f"Error validating value: {str(e)}"}

    async def bulk_create_metafields(self, metafields_by_product: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Crea metafields para múltiples productos en lote.

        Args:
            metafields_by_product: Diccionario con product_id como key y lista de metafields como value

        Returns:
            Dict: Resultado con éxitos y fallos
        """
        try:
            logger.info(f"🔄 Bulk creating metafields for {len(metafields_by_product)} products")

            successes = []
            failures = []

            for product_id, metafields in metafields_by_product.items():
                try:
                    await self.create_metafields(product_id, metafields)
                    successes.append({"product_id": product_id, "metafields_count": len(metafields)})
                except Exception as e:
                    failures.append({"product_id": product_id, "error": str(e), "metafields_count": len(metafields)})

            logger.info(f"✅ Bulk metafields creation completed: {len(successes)} successes, {len(failures)} failures")

            return {
                "success": True,
                "total_products": len(metafields_by_product),
                "successes": len(successes),
                "failures": len(failures),
                "success_details": successes,
                "failure_details": failures,
            }

        except Exception as e:
            logger.error(f"❌ Error in bulk metafields creation: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_products": len(metafields_by_product),
                "successes": 0,
                "failures": len(metafields_by_product),
            }
