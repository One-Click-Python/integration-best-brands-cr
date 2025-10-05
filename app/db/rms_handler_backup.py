"""
Manejador de base de datos RMS.

Este módulo proporciona funciones para interactuar con la base de datos
de Microsoft Retail Management System (RMS), incluyendo conexiones,
consultas y operaciones CRUD.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry, RMSViewItem
from app.core.config import get_settings
from app.db.connection import ConnDB, get_db_connection
from app.utils.error_handler import RMSConnectionException

settings = get_settings()
logger = logging.getLogger(__name__)


class RMSHandler:
    """
    Manejador para operaciones específicas de RMS.

    Esta clase implementa operaciones de negocio para:
    - Consultas a View_Items
    - Creación de órdenes y entradas de orden
    - Validaciones específicas de RMS
    - Transformaciones de datos
    """

    def __init__(self):
        """Inicializa el manejador RMS."""
        self.conn_db: ConnDB = get_db_connection()
        self._initialized = False
        logger.info("RMSHandler initialized")

    async def initialize(self):
        """
        Inicializa el handler asegurando que la conexión esté disponible.

        Raises:
            RMSConnectionException: Si falla la inicialización
        """
        try:
            # Inicializar conexión si no está lista
            if not self.conn_db.is_initialized():
                await self.conn_db.initialize()

            # Verificar acceso a tablas críticas
            await self._verify_table_access()

            self._initialized = True
            logger.info("RMSHandler initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RMSHandler: {e}")
            raise RMSConnectionException(
                message=f"Failed to initialize RMS handler: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_initialization",
            ) from e

    async def _verify_table_access(self):
        """
        Verifica acceso a las tablas críticas de RMS.

        Raises:
            RMSConnectionException: Si no se puede acceder a las tablas
        """
        try:
            async with self.conn_db.get_session() as session:
                # Verificar acceso a View_Items
                result = await session.execute(text("SELECT COUNT(*) FROM View_Items"))
                items_count = result.scalar()
                logger.info(f"View_Items contains {items_count} items")

                # Verificar acceso a tablas Order
                result = await session.execute(
                    text("SELECT COUNT(*) FROM [Order] WHERE StoreID = :store_id"),
                    {"store_id": settings.RMS_STORE_ID},
                )
                orders_count = result.scalar()
                logger.info(f"Order table contains {orders_count} orders for store {settings.RMS_STORE_ID}")

        except Exception as e:
            logger.error(f"Table access verification failed: {e}")
            raise RMSConnectionException(
                message=f"Cannot access required RMS tables: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="table_access",
            ) from e

    async def close(self):
        """
        Cierra el handler (la conexión se maneja por ConnDB).
        """
        try:
            self._initialized = False
            logger.info("RMSHandler closed")
        except Exception as e:
            logger.error(f"Error closing RMSHandler: {e}")

    def is_initialized(self) -> bool:
        """
        Verifica si el handler está inicializado.

        Returns:
            bool: True si está inicializado
        """
        return self._initialized and self.conn_db.is_initialized()

    async def get_view_items_since(
        self,
        since_timestamp: Optional[datetime] = None,
        category_filter: Optional[List[str]] = None,
        family_filter: Optional[List[str]] = None,
        gender_filter: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_zero_stock: bool = False,
    ) -> List[RMSViewItem]:
        """
        Get products modified since a specific timestamp.
        
        This method uses the Item.LastUpdated field to filter only products
        that have been created or modified since the specified timestamp.
        
        Args:
            since_timestamp: Only return items modified after this timestamp
            category_filter: Filter by categories
            family_filter: Filter by families
            gender_filter: Filter by gender
            limit: Limit of results
            offset: Offset for pagination
            include_zero_stock: Include products with zero stock
            
        Returns:
            List[RMSViewItem]: Products modified since timestamp
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="RMSHandler not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )
        
        try:
            async with self.conn_db.get_session() as session:
                # Build query with JOIN to Item table for LastUpdated filtering
                query = """
                SELECT 
                    v.Familia as familia,
                    v.Genero as genero, 
                    v.Categoria as categoria,
                    v.CCOD as ccod,
                    v.C_ARTICULO as c_articulo,
                    v.ItemID as item_id,
                    v.Description as description,
                    v.color,
                    v.talla,
                    v.Quantity as quantity,
                    v.Price as price,
                    v.SaleStartDate as sale_start_date,
                    v.SaleEndDate as sale_end_date, 
                    v.SalePrice as sale_price,
                    v.ExtendedCategory as extended_category,
                    v.Tax as tax,
                    v.Exis00 as exis00,
                    v.Exis57 as exis57
                FROM View_Items v
                """
                
                params = {}
                
                # Add JOIN if we need to filter by LastUpdated
                if since_timestamp:
                    query += """
                    INNER JOIN Item i ON v.ItemID = i.ID
                    WHERE i.LastUpdated > :since_timestamp
                    """
                    params["since_timestamp"] = since_timestamp
                else:
                    query += " WHERE 1=1"
                
                # Apply other filters
                query, params = self._apply_filters(
                    query,
                    params,
                    category_filter,
                    family_filter,
                    gender_filter,
                    None,  # Don't use incremental_hours since we have since_timestamp
                )
                
                # Only products with valid data
                query += " AND v.C_ARTICULO IS NOT NULL AND v.Description IS NOT NULL"
                query += " AND v.Price > 0"
                
                # Filter by stock if specified
                if not include_zero_stock:
                    query += " AND v.Quantity > 0"
                
                # Order by ItemID for consistency
                query += " ORDER BY v.ItemID"
                
                # Pagination
                if limit:
                    query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
                
                if since_timestamp:
                    logger.info(f"Executing View_Items query for items modified since {since_timestamp}")
                else:
                    logger.debug(f"Executing View_Items query with {len(params)} parameters")
                
                result = await session.execute(text(query), params)
                rows = result.fetchall()
                
                # Convert to Pydantic models
                products = []
                for row in rows:
                    try:
                        row_dict = row._asdict()
                        product = RMSViewItem(**row_dict)
                        products.append(product)
                    except Exception as e:
                        logger.warning(f"Error converting row to RMSViewItem: {e} - SKU: {row.c_articulo}")
                        continue
                
                logger.info(f"Retrieved {len(products)} products from View_Items" + 
                           (f" modified since {since_timestamp}" if since_timestamp else ""))
                return products
                
        except Exception as e:
            logger.error(f"Error retrieving products from View_Items: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve products: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution",
            ) from e

    async def get_view_items(
        self,
        category_filter: Optional[List[str]] = None,
        family_filter: Optional[List[str]] = None,
        gender_filter: Optional[List[str]] = None,
        incremental_hours: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_zero_stock: bool = False,
    ) -> List[RMSViewItem]:
        """
        Obtiene productos desde la vista View_Items.

        Args:
            category_filter: Filtrar por categorías
            family_filter: Filtrar por familias
            gender_filter: Filtrar por género
            incremental_hours: Solo productos modificados en las últimas N horas
            limit: Límite de resultados
            offset: Offset para paginación
            include_zero_stock: Incluir productos sin stock (cantidad = 0)

        Returns:
            List[RMSViewItem]: Lista de productos

        Raises:
            RMSConnectionException: Si falla la consulta
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="RMSHandler not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )

        try:
            async with self.conn_db.get_session() as session:
                # Query base optimizada
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE 1=1
                """

                params = {}

                # Aplicar filtros dinámicamente
                query, params = self._apply_filters(
                    query,
                    params,
                    category_filter,
                    family_filter,
                    gender_filter,
                    incremental_hours,
                )

                # Solo productos con datos válidos
                query += " AND C_ARTICULO IS NOT NULL AND Description IS NOT NULL"
                query += " AND Price > 0"

                # Filtrar por stock si se especifica
                if not include_zero_stock:
                    query += " AND Quantity > 0"

                # Ordenar por modificación reciente y ID para consistencia
                query += " ORDER BY ItemID"

                # Paginación
                if limit:
                    query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

                logger.debug(f"Executing View_Items query with {len(params)} parameters")

                result = await session.execute(text(query), params)
                rows = result.fetchall()

                # Convertir a modelos Pydantic
                products = []
                for row in rows:
                    try:
                        # Convertir row a dict
                        row_dict = row._asdict()
                        product = RMSViewItem(**row_dict)
                        products.append(product)
                    except Exception as e:
                        logger.warning(f"Error converting row to RMSViewItem: {e} - SKU: {row.c_articulo}")
                        continue

                logger.info(f"Retrieved {len(products)} products from View_Items")
                return products

        except Exception as e:
            logger.error(f"Error retrieving products from View_Items: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve products: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution",
            ) from e

    def _apply_filters(
        self,
        query: str,
        params: dict,
        category_filter: Optional[List[str]],
        family_filter: Optional[List[str]],
        gender_filter: Optional[List[str]],
        incremental_hours: Optional[int],
    ) -> tuple[str, dict]:
        """
        Aplica filtros dinámicos a la consulta.

        Args:
            query: Query base
            params: Parámetros actuales
            category_filter: Filtro de categorías
            family_filter: Filtro de familias
            gender_filter: Filtro de género
            incremental_hours: Horas para filtro incremental

        Returns:
            tuple: (query_modificada, params_actualizados)
        """
        # Filtro por categorías
        if category_filter:
            placeholders = ", ".join([f":cat_{i}" for i in range(len(category_filter))])
            query += f" AND Categoria IN ({placeholders})"
            for i, cat in enumerate(category_filter):
                params[f"cat_{i}"] = cat

        # Filtro por familias
        if family_filter:
            placeholders = ", ".join([f":fam_{i}" for i in range(len(family_filter))])
            query += f" AND Familia IN ({placeholders})"
            for i, fam in enumerate(family_filter):
                params[f"fam_{i}"] = fam

        # Filtro por género
        if gender_filter:
            placeholders = ", ".join([f":gen_{i}" for i in range(len(gender_filter))])
            query += f" AND Genero IN ({placeholders})"
            for i, gen in enumerate(gender_filter):
                params[f"gen_{i}"] = gen

        # Filtro incremental por tiempo
        if incremental_hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=incremental_hours)
            query += " AND LastModified >= :cutoff_time"
            params["cutoff_time"] = cutoff_time

        return query, params

    async def get_product_by_sku(self, sku: str) -> Optional[RMSViewItem]:
        """
        Obtiene un producto específico por SKU.

        Args:
            sku: SKU del producto (C_ARTICULO)

        Returns:
            RMSViewItem o None si no se encuentra
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="RMSHandler not initialized", db_host=settings.RMS_DB_HOST)

        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE C_ARTICULO = :sku
                """

                result = await session.execute(text(query), {"sku": sku})
                row = result.fetchone()

                if row:
                    return RMSViewItem(**row._asdict())
                return None

        except Exception as e:
            logger.error(f"Error retrieving product by SKU {sku}: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve product by SKU: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="single_product_query",
            ) from e

    async def create_order(self, order: RMSOrder) -> int:
        """
        Crea una nueva orden en RMS.

        Args:
            order: Datos de la orden

        Returns:
            int: ID de la orden creada

        Raises:
            RMSConnectionException: Si falla la creación
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="RMSHandler not initialized", db_host=settings.RMS_DB_HOST)

        try:
            async with self.conn_db.get_session() as session:
                # Preparar query de inserción
                query = """
                INSERT INTO [Order] (
                    StoreID, Time, Type, CustomerID, Deposit, Tax, Total,
                    SalesRepID, ShippingServiceID, ShippingTrackingNumber,
                    Comment, ShippingNotes
                ) 
                OUTPUT INSERTED.ID
                VALUES (
                    :store_id, :time, :type, :customer_id, :deposit, :tax, :total,
                    :sales_rep_id, :shipping_service_id, :shipping_tracking_number,
                    :comment, :shipping_notes
                )
                """

                params = {
                    "store_id": order.store_id,
                    "time": order.time,
                    "type": order.type,
                    "customer_id": order.customer_id,
                    "deposit": float(order.deposit),
                    "tax": float(order.tax),
                    "total": float(order.total),
                    "sales_rep_id": order.sales_rep_id,
                    "shipping_service_id": order.shipping_service_id,
                    "shipping_tracking_number": order.shipping_tracking_number,
                    "comment": order.comment,
                    "shipping_notes": order.shipping_notes,
                }

                result = await session.execute(text(query), params)
                order_id = result.scalar()

                if not order_id:
                    raise RMSConnectionException(
                        message="Order creation did not return an ID",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="order_creation",
                    )

                await session.commit()

                logger.info(f"Created order in RMS with ID: {order_id}")
                return int(order_id)

        except Exception as e:
            logger.error(f"Error creating order in RMS: {e}")
            raise RMSConnectionException(
                message=f"Failed to create order: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_creation",
            ) from e

    async def create_order_entry(self, entry: RMSOrderEntry) -> int:
        """
        Crea una entrada de orden (línea de producto).

        Args:
            entry: Datos de la línea de orden

        Returns:
            int: ID de la entrada creada
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="RMSHandler not initialized", db_host=settings.RMS_DB_HOST)

        try:
            async with self.conn_db.get_session() as session:
                query = """
                INSERT INTO OrderEntry (
                    OrderID, ItemID, Price, FullPrice, Cost,
                    QuantityOnOrder, QuantityRTD, SalesRepID,
                    DiscountReasonCodeID, ReturnReasonCodeID,
                    Description, IsAddMoney, VoucherID
                ) 
                OUTPUT INSERTED.ID
                VALUES (
                    :order_id, :item_id, :price, :full_price, :cost,
                    :quantity_on_order, :quantity_rtd, :sales_rep_id,
                    :discount_reason_code_id, :return_reason_code_id,
                    :description, :is_add_money, :voucher_id
                )
                """

                params = {
                    "order_id": entry.order_id,
                    "item_id": entry.item_id,
                    "price": float(entry.price),
                    "full_price": float(entry.full_price),
                    "cost": float(entry.cost) if entry.cost else None,
                    "quantity_on_order": entry.quantity_on_order,
                    "quantity_rtd": entry.quantity_rtd,
                    "sales_rep_id": entry.sales_rep_id,
                    "discount_reason_code_id": entry.discount_reason_code_id,
                    "return_reason_code_id": entry.return_reason_code_id,
                    "description": entry.description,
                    "is_add_money": entry.is_add_money,
                    "voucher_id": entry.voucher_id,
                }

                result = await session.execute(text(query), params)
                entry_id = result.scalar()

                if not entry_id:
                    raise RMSConnectionException(
                        message="Order entry creation did not return an ID",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="order_entry_creation",
                    )

                await session.commit()

                logger.info(f"Created order entry in RMS with ID: {entry_id}")
                return int(entry_id)

        except Exception as e:
            logger.error(f"Error creating order entry in RMS: {e}")
            raise RMSConnectionException(
                message=f"Failed to create order entry: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_entry_creation",
            ) from e

    async def get_categories(self) -> List[str]:
        """
        Obtiene lista única de categorías disponibles.

        Returns:
            List[str]: Lista de categorías
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT DISTINCT Categoria 
                FROM View_Items 
                WHERE Categoria IS NOT NULL AND Categoria != ''
                ORDER BY Categoria
                """
                result = await session.execute(text(query))
                return [row[0] for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    async def get_families(self) -> List[str]:
        """
        Obtiene lista única de familias disponibles.

        Returns:
            List[str]: Lista de familias
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT DISTINCT Familia 
                FROM View_Items 
                WHERE Familia IS NOT NULL AND Familia != ''
                ORDER BY Familia
                """
                result = await session.execute(text(query))
                return [row[0] for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Error getting families: {e}")
            return []

    async def get_genders(self) -> List[str]:
        """
        Obtiene lista única de géneros disponibles.

        Returns:
            List[str]: Lista de géneros
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT DISTINCT Genero 
                FROM View_Items 
                WHERE Genero IS NOT NULL AND Genero != ''
                ORDER BY Genero
                """
                result = await session.execute(text(query))
                return [row[0] for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Error getting genders: {e}")
            return []

    async def get_products_by_ccod(self, ccod: str) -> List[RMSViewItem]:
        """
        Obtiene todas las variantes de un producto por CCOD.

        Args:
            ccod: Código de modelo (CCOD)

        Returns:
            List[RMSViewItem]: Lista de variantes del producto
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE CCOD = :ccod
                ORDER BY C_ARTICULO
                """

                result = await session.execute(text(query), {"ccod": ccod})
                rows = result.fetchall()

                products = []
                for row in rows:
                    try:
                        product = RMSViewItem(**row._asdict())
                        products.append(product)
                    except Exception as e:
                        logger.warning(f"Error converting row to RMSViewItem: {e}")
                        continue

                return products

        except Exception as e:
            logger.error(f"Error retrieving products by CCOD {ccod}: {e}")
            return []

    async def execute_custom_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Ejecuta una consulta SQL personalizada.

        Args:
            query: Consulta SQL
            params: Parámetros opcionales

        Returns:
            List[Dict]: Resultados de la consulta
        """
        try:
            async with self.conn_db.get_session() as session:
                result = await session.execute(text(query), params or {})
                return [row._asdict() for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute custom query: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="custom_query",
            ) from e

    async def execute_paginated_query(
        self, query: str, offset: int, limit: int, params: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta una consulta SQL con paginación usando OFFSET/FETCH.

        Args:
            query: Consulta SQL (sin ORDER BY ni OFFSET/FETCH)
            offset: Número de filas a saltar
            limit: Número de filas a retornar
            params: Parámetros opcionales

        Returns:
            List[Dict]: Resultados paginados de la consulta
        """
        try:
            # Agregar paginación a la query
            # SQL Server requiere ORDER BY para usar OFFSET/FETCH
            paginated_query = f"{query} OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

            async with self.conn_db.get_session() as session:
                result = await session.execute(text(paginated_query), params or {})
                return [row._asdict() for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Error executing paginated query: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute paginated query: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="paginated_query",
            ) from e

    async def count_query_results(self, base_query: str, params: Optional[Dict] = None) -> int:
        """
        Cuenta el número total de resultados de una query.

        Args:
            base_query: Query base (se convertirá a COUNT)
            params: Parámetros opcionales

        Returns:
            int: Número total de registros
        """
        try:
            # Convertir la query a una COUNT query
            # Buscar el FROM y reemplazar el SELECT
            from_index = base_query.upper().find("FROM")
            if from_index == -1:
                raise ValueError("Query must contain FROM clause")

            # Extraer solo la parte después del FROM, ignorando ORDER BY si existe
            from_part = base_query[from_index:]
            order_by_index = from_part.upper().find("ORDER BY")
            if order_by_index != -1:
                from_part = from_part[:order_by_index]

            count_query = f"SELECT COUNT(*) as total {from_part}"

            async with self.conn_db.get_session() as session:
                result = await session.execute(text(count_query), params or {})
                row = result.fetchone()
                return row.total if row else 0

        except Exception as e:
            logger.error(f"Error counting query results: {e}")
            raise RMSConnectionException(
                message=f"Failed to count query results: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="count_query",
            ) from e

    async def count_view_items_since(
        self,
        since_timestamp: Optional[datetime] = None,
        category_filter: Optional[List[str]] = None,
        include_zero_stock: bool = False,
    ) -> int:
        """
        Count products modified since a specific timestamp.
        
        Args:
            since_timestamp: Only count items modified after this timestamp
            category_filter: Filter by categories
            include_zero_stock: Include products with zero stock
            
        Returns:
            int: Number of products modified since timestamp
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="RMSHandler not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )
        
        try:
            async with self.conn_db.get_session() as session:
                query = "SELECT COUNT(DISTINCT v.CCOD) as total FROM View_Items v"
                params = {}
                
                # Add JOIN if we need to filter by LastUpdated
                if since_timestamp:
                    query += " INNER JOIN Item i ON v.ItemID = i.ID WHERE i.LastUpdated > :since_timestamp"
                    params["since_timestamp"] = since_timestamp
                else:
                    query += " WHERE 1=1"
                
                # Apply filters
                query += " AND v.C_ARTICULO IS NOT NULL AND v.Description IS NOT NULL AND v.Price > 0"
                
                if not include_zero_stock:
                    query += " AND v.Quantity > 0"
                
                if category_filter:
                    placeholders = ", ".join([f":cat_{i}" for i in range(len(category_filter))])
                    query += f" AND v.Categoria IN ({placeholders})"
                    for i, cat in enumerate(category_filter):
                        params[f"cat_{i}"] = cat
                
                result = await session.execute(text(query), params)
                row = result.fetchone()
                count = row.total if row else 0
                
                logger.info(f"Found {count} products" + 
                           (f" modified since {since_timestamp}" if since_timestamp else ""))
                return count
                
        except Exception as e:
            logger.error(f"Error counting products: {e}")
            return 0

    async def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Obtiene resumen de inventario.

        Returns:
            Dict: Resumen de inventario
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT 
                    COUNT(*) as total_products,
                    SUM(CASE WHEN Quantity > 0 THEN 1 ELSE 0 END) as products_with_stock,
                    SUM(Quantity) as total_quantity,
                    COUNT(DISTINCT Categoria) as unique_categories,
                    COUNT(DISTINCT Familia) as unique_families,
                    COUNT(DISTINCT CCOD) as unique_models
                FROM View_Items
                WHERE C_ARTICULO IS NOT NULL
                """

                result = await session.execute(text(query))
                row = result.fetchone()

                if row:
                    return row._asdict()

                return {}

        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return {}

    async def find_order_by_shopify_id(self, shopify_order_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca una orden en RMS por ID de Shopify usando ReferenceNumber y ChannelType.

        Args:
            shopify_order_id: ID de la orden en Shopify

        Returns:
            Dict con datos de la orden o None si no existe
        """
        try:
            async with self.conn_db.get_session() as session:
                # Buscar usando ReferenceNumber con prefijo SHOPIFY- y ChannelType=2 (Shopify)
                reference_number = f"SHOPIFY-{shopify_order_id}"
                query = """
                SELECT * FROM [ORDER] 
                WHERE ReferenceNumber = :reference_number 
                AND ChannelType = 2
                """
                result = await session.execute(text(query), {"reference_number": reference_number})
                row = result.fetchone()
                return row._asdict() if row else None

        except Exception as e:
            logger.error(f"Error finding order by Shopify ID {shopify_order_id}: {e}")
            return None

    async def find_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Busca un cliente en RMS por email.
        NOTA: Tabla Customer no existe en structure.md, retorna None por ahora.

        Args:
            email: Email del cliente

        Returns:
            Dict con datos del cliente o None si no existe
        """
        try:
            # TODO: Verificar si existe tabla Customer en la base de datos
            # Por ahora retornar None ya que la tabla no está definida
            logger.debug(f"Customer lookup by email {email} - Customer table not defined")
            return None

        except Exception as e:
            logger.error(f"Error finding customer by email {email}: {e}")
            return None

    async def create_customer(self, customer_data: Dict[str, Any]) -> int:
        """
        Crea un nuevo cliente en RMS.
        NOTA: Tabla Customer no existe en structure.md, retorna ID ficticio.

        Args:
            customer_data: Datos del cliente

        Returns:
            ID del cliente creado (ficticio por ahora)
        """
        try:
            # TODO: Verificar si existe tabla Customer en la base de datos
            # Por ahora retornar ID ficticio ya que la tabla no está definida
            logger.debug("Customer creation - Customer table not defined, returning default ID", customer_data)
            return 1  # ID ficticio para pruebas

        except Exception as e:
            logger.error(f"Error creating customer: {e}")
            raise

    async def find_item_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Busca un item en RMS por SKU.

        Args:
            sku: SKU del item

        Returns:
            Dict con datos del item o None si no existe
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT * FROM Item 
                WHERE ItemLookupCode = :sku
                """
                result = await session.execute(text(query), {"sku": sku})
                row = result.fetchone()
                return row._asdict() if row else None

        except Exception as e:
            logger.error(f"Error finding item by SKU {sku}: {e}")
            return None

    async def update_order(self, order_id: int, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza una orden existente en RMS.

        Args:
            order_id: ID de la orden
            order_data: Nuevos datos de la orden

        Returns:
            Dict con datos de la orden actualizada
        """
        try:
            async with self.conn_db.get_session() as session:
                # Construir query dinámicamente basado en los campos a actualizar
                set_clauses = []
                params = {"order_id": order_id}

                for key, value in order_data.items():
                    if key != "id":  # No actualizar el ID
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                if not set_clauses:
                    logger.warning("No fields to update in order")
                    return {"id": order_id}

                query = f"""
                UPDATE [ORDER] 
                SET {", ".join(set_clauses)}
                WHERE ID = :order_id
                """

                await session.execute(text(query), params)
                await session.commit()
                logger.info(f"Updated order {order_id}")
                return {"id": order_id, **order_data}

        except Exception as e:
            logger.error(f"Error updating order {order_id}: {e}")
            raise

    async def get_item_stock(self, item_id: int) -> int:
        """
        Obtiene el stock actual de un item.

        Args:
            item_id: ID del item

        Returns:
            Cantidad en stock
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT Quantity FROM Item 
                WHERE ID = :item_id
                """
                result = await session.execute(text(query), {"item_id": item_id})
                row = result.fetchone()
                return row[0] if row else 0

        except Exception as e:
            logger.error(f"Error getting stock for item {item_id}: {e}")
            return 0

    async def update_item_stock(self, item_id: int, quantity_change: int) -> None:
        """
        Actualiza el stock de un item.

        Args:
            item_id: ID del item
            quantity_change: Cambio en la cantidad (puede ser negativo)
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                UPDATE Item 
                SET Quantity = Quantity + :quantity_change
                WHERE ID = :item_id
                """
                await session.execute(text(query), {"item_id": item_id, "quantity_change": quantity_change})
                await session.commit()
                logger.info(f"Updated stock for item {item_id}: {quantity_change:+d}")

        except Exception as e:
            logger.error(f"Error updating stock for item {item_id}: {e}")
            raise

    async def get_order_entries(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene las entradas de una orden.

        Args:
            order_id: ID de la orden

        Returns:
            Lista de entradas de la orden
        """
        try:
            async with self.conn_db.get_session() as session:
                query = """
                SELECT * FROM OrderEntry 
                WHERE OrderID = :order_id
                """
                result = await session.execute(text(query), {"order_id": order_id})
                rows = result.fetchall()
                return [row._asdict() for row in rows]

        except Exception as e:
            logger.error(f"Error getting order entries for order {order_id}: {e}")
            return []

    async def update_order_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> None:
        """
        Actualiza una entrada de orden.

        Args:
            entry_id: ID de la entrada
            entry_data: Nuevos datos de la entrada
        """
        try:
            async with self.conn_db.get_session() as session:
                # Construir query dinámicamente
                set_clauses = []
                params = {"entry_id": entry_id}

                for key, value in entry_data.items():
                    if key != "id":
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                if set_clauses:
                    query = f"""
                    UPDATE OrderEntry 
                    SET {", ".join(set_clauses)}
                    WHERE ID = :entry_id
                    """
                    await session.execute(text(query), params)
                    await session.commit()
                    logger.info(f"Updated order entry {entry_id}")

        except Exception as e:
            logger.error(f"Error updating order entry {entry_id}: {e}")
            raise

    async def create_order_history(self, history_data: Dict[str, Any]) -> int:
        """
        Crea un registro de historial de orden.

        Args:
            history_data: Datos del historial

        Returns:
            ID del registro creado
        """
        try:
            async with self.conn_db.get_session() as session:
                # Usar los campos correctos según la estructura de OrderHistory
                query = """
                INSERT INTO OrderHistory (
                    StoreID, BatchNumber, Date, OrderID, CashierID, 
                    DeltaDeposit, TransactionNumber, Comment
                ) 
                OUTPUT INSERTED.ID
                VALUES (
                    :store_id, :batch_number, :date, :order_id, :cashier_id,
                    :delta_deposit, :transaction_number, :comment
                )
                """

                # Preparar datos con valores por defecto si no están presentes
                params = {
                    "store_id": history_data.get("store_id", 40),  # Default store
                    "batch_number": history_data.get("batch_number", 1),
                    "date": history_data.get("date", datetime.now()),
                    "order_id": history_data.get("order_id"),
                    "cashier_id": history_data.get("cashier_id", 1),  # Default cashier
                    "delta_deposit": history_data.get("delta_deposit", 0),
                    "transaction_number": history_data.get("transaction_number", 1),
                    "comment": history_data.get("comment", ""),
                }

                result = await session.execute(text(query), params)
                await session.commit()
                history_id = result.fetchone()[0]  # type: ignore
                logger.info(f"Created order history with ID: {history_id}")
                return history_id

        except Exception as e:
            logger.error(f"Error creating order history: {e}")
            raise


# Funciones de conveniencia para uso global
async def initialize_rms_handler() -> RMSHandler:
    """
    Inicializa y retorna un handler RMS listo para usar.

    Returns:
        RMSHandler: Handler inicializado
    """
    handler = RMSHandler()
    await handler.initialize()
    return handler


async def test_rms_connection() -> bool:
    """
    Función de conveniencia para probar conexión RMS.

    Returns:
        bool: True si la conexión funciona
    """
    try:
        conn_db = get_db_connection()
        if not conn_db.is_initialized():
            await conn_db.initialize()
        return await conn_db.test_connection()
    except Exception:
        return False


# Funciones de compatibilidad para lifespan.py
async def initialize_connection_pool():
    """
    Función de compatibilidad para inicializar pool de conexiones.
    """
    try:
        conn_db = get_db_connection()
        if not conn_db.is_initialized():
            await conn_db.initialize()
        logger.info("RMS connection pool initialized via compatibility function")
    except Exception as e:
        logger.error(f"Error initializing RMS connection pool: {e}")
        raise


async def close_connection_pool():
    """
    Función de compatibilidad para cerrar pool de conexiones.
    """
    try:
        conn_db = get_db_connection()
        await conn_db.close()
        logger.info("RMS connection pool closed via compatibility function")
    except Exception as e:
        logger.error(f"Error closing RMS connection pool: {e}")
        raise
