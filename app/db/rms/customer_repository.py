"""
CustomerRepository: Customer lookup and creation for RMS.

Encapsulates customer-related operations extracted from the legacy RMSHandler,
following Single Responsibility. Since the Customer table isn't confirmed in
structure.md, this repository is resilient: it will operate in "no-table"
mode by returning safe defaults while logging diagnostics.
"""

import logging
from typing import Any, Dict, Optional, List

from sqlalchemy import text

from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class CustomerRepository(BaseRepository):
    """Repository for customer-related operations in RMS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_customer_table: bool = False
        self._customer_table_name: Optional[str] = None  # "Customer" or "Customers"

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation("verify_table_access_customers")
    async def _verify_table_access(self) -> None:
        """
        Verify access to a customer table if present. Does not raise if missing to
        keep the system operable (as per original behavior where customer features were optional).
        """
        try:
            async with self.conn_db.get_session() as session:
                # Try common table names in RMS-like schemas
                for table_name in ("Customer", "Customers"):
                    try:
                        result = await session.execute(text(f"SELECT COUNT(*) FROM [{table_name}]"))
                        _ = result.scalar()
                        self._has_customer_table = True
                        self._customer_table_name = table_name
                        logger.info(f"CustomerRepository: detected table [{table_name}]")
                        return
                    except Exception:
                        continue

                # If we reach here, table not found; keep repository usable in no-table mode
                self._has_customer_table = False
                self._customer_table_name = None
                logger.warning(
                    "CustomerRepository: no Customer table detected. Operating in no-table mode (safe fallbacks)."
                )
        except Exception as e:
            # Treat verification failures as non-fatal for this repository
            self._has_customer_table = False
            self._customer_table_name = None
            logger.warning(
                f"CustomerRepository table verification error (continuing in no-table mode): {e}"
            )

    # ------------------------- Lookups -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def find_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a customer by email. Returns None if table/column isn't available.
        Mirrors original behavior where Customer table wasn't guaranteed.
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="CustomerRepository not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        if not self._has_customer_table or not self._customer_table_name:
            logger.debug(
                f"Customer lookup by email {email} skipped: customer table not available"
            )
            return None

        try:
            async with self.get_session() as session:
                # Attempt a generic lookup by Email column; handle schema differences gracefully.
                query = f"""
                SELECT TOP 1 * FROM [{self._customer_table_name}] 
                WHERE Email = :email
                """
                result = await session.execute(text(query), {"email": email})
                row = result.fetchone()
                return row._asdict() if row else None
        except Exception as e:
            logger.warning(
                f"Customer lookup by email failed (schema may differ or column missing): {e}"
            )
            return None

    # ------------------------- Creation -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def create_customer(self, customer_data: Dict[str, Any]) -> int:
        """
        Create a new customer.
        If the customer table is not available or schema is unknown, return a stub ID (1)
        to preserve backward-compatible behavior from the legacy handler.
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="CustomerRepository not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        if not self._has_customer_table or not self._customer_table_name:
            logger.debug(
                "Customer creation skipped (no customer table). Returning stub ID.",
            )
            return 1  # Stub ID for compatibility

        # Schema unknown; safest approach is to avoid blind inserts.
        logger.warning(
            "Customer table detected but schema is unknown; returning stub ID to avoid schema mismatch."
        )
        return 1

    # ------------------------- Optional extensions (stubs) -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_customer(self, customer_id: int, data: Dict[str, Any]) -> None:
        """Stub for updating a customer. No-op unless schema is defined in the project."""
        if not self._has_customer_table or not self._customer_table_name:
            logger.debug("update_customer skipped (no customer table)")
            return
        logger.warning("update_customer not implemented due to unknown schema")

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_customer_by_id(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Stub for retrieving a customer by ID. Returns None unless schema is known."""
        if not self._has_customer_table or not self._customer_table_name:
            return None
        try:
            async with self.get_session() as session:
                query = f"SELECT * FROM [{self._customer_table_name}] WHERE ID = :id"
                result = await session.execute(text(query), {"id": customer_id})
                row = result.fetchone()
                return row._asdict() if row else None
        except Exception as e:
            logger.warning(f"get_customer_by_id failed: {e}")
            return None

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def search_customers(self, term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Stub for searching customers by a free-text term. Empty unless schema known."""
        if not self._has_customer_table or not self._customer_table_name:
            return []
        try:
            async with self.get_session() as session:
                # Very conservative search; may be adapted once schema is defined.
                query = f"""
                SELECT TOP {limit} * FROM [{self._customer_table_name}] 
                WHERE (Email LIKE :like_term OR Name LIKE :like_term)
                ORDER BY ID DESC
                """
                result = await session.execute(text(query), {"like_term": f"%{term}%"})
                rows = result.fetchall()
                return [row._asdict() for row in rows]
        except Exception as e:
            logger.warning(f"search_customers failed: {e}")
            return []
