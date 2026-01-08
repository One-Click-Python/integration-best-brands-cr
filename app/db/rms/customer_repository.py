"""
CustomerRepository: Customer lookup and creation for RMS.

Encapsulates customer-related operations extracted from the legacy RMSHandler,
following Single Responsibility. Since the Customer table isn't confirmed in
structure.md, this repository is resilient: it will operate in "no-table"
mode by returning safe defaults while logging diagnostics.
"""

import logging
from typing import Any, Dict, List, Optional

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
        self._guest_customer_id: Optional[int] = None  # Cache for guest customer ID

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
            logger.warning(f"CustomerRepository table verification error (continuing in no-table mode): {e}")

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
            logger.debug(f"Customer lookup by email {email} skipped: customer table not available")
            return None

        try:
            async with self.get_session() as session:
                # Lookup by EmailAddress column (RMS Customer table schema)
                query = f"""
                SELECT TOP 1 * FROM [{self._customer_table_name}]
                WHERE EmailAddress = :email
                """
                result = await session.execute(text(query), {"email": email})
                row = result.fetchone()
                return row._asdict() if row else None
        except Exception as e:
            logger.warning(f"Customer lookup by email failed (schema may differ or column missing): {e}")
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
            return 9111  # Stub ID for compatibility

        # Schema unknown; safest approach is to avoid blind inserts.
        logger.warning("Customer table detected but schema is unknown; returning stub ID to avoid schema mismatch.")
        return 9111

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def find_or_create_guest_customer(self, account_number: str | None = None) -> int:
        """
        Find or create a guest customer for orders without customer data.

        This method searches for a customer with the specified account number.
        If not found, creates a new customer with safe default values.
        The guest customer ID is cached to avoid repeated lookups.

        Args:
            account_number: Account number for guest customer.
                Uses GUEST_CUSTOMER_ACCOUNT_NUMBER from settings if not provided.

        Returns:
            int: Customer ID for guest customer

        Raises:
            RMSConnectionException: If repository not initialized
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="CustomerRepository not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        # Use configured account number if not provided
        if account_number is None:
            account_number = settings.GUEST_CUSTOMER_ACCOUNT_NUMBER

        # Return cached ID if available
        if self._guest_customer_id is not None:
            logger.debug(f"Using cached guest customer ID: {self._guest_customer_id}")
            return self._guest_customer_id

        # If no customer table, return stub ID
        if not self._has_customer_table or not self._customer_table_name:
            logger.warning("No customer table available - using stub guest customer ID=9111")
            self._guest_customer_id = 9111
            return 9111

        try:
            # Search for existing guest customer
            async with self.get_session() as session:
                search_query = f"""
                SELECT ID FROM [{self._customer_table_name}]
                WHERE AccountNumber = :account_number
                """
                result = await session.execute(text(search_query), {"account_number": account_number})
                row = result.fetchone()

                if row:
                    customer_id = row[0]
                    logger.info(f"Found existing guest customer: ID={customer_id}, " f"AccountNumber={account_number}")
                    self._guest_customer_id = customer_id
                    return customer_id

                # Create new guest customer with all required fields
                logger.info(f"Creating new guest customer with AccountNumber={account_number}")

                # Get current timestamp for dates
                from datetime import UTC, datetime

                now = datetime.now(UTC)

                insert_query = f"""
                INSERT INTO [{self._customer_table_name}] (
                    AccountNumber, FirstName, LastName, Email,
                    Address, City, State, Zip, Country,
                    Company, Address2, StoreID,
                    AccountTypeID, AccountBalance, CreditLimit, TotalSales,
                    AccountOpened, LastVisit, TotalVisits, TotalSavings,
                    CurrentDiscount, LastUpdated,
                    AssessFinanceCharges, GlobalCustomer, HQID,
                    LimitPurchase, LayawayCustomer, Employee,
                    PrimaryShipToID, LastClosingBalance,
                    CustomNumber1, CustomNumber2, CustomNumber3, CustomNumber4, CustomNumber5,
                    CustomText1, CustomText2, CustomText3, CustomText4, CustomText5
                )
                OUTPUT INSERTED.ID
                VALUES (
                    :account_number, :first_name, :last_name, :email,
                    :address, :city, :state, :zip, :country,
                    :company, :address2, :store_id,
                    :account_type_id, :account_balance, :credit_limit, :total_sales,
                    :account_opened, :last_visit, :total_visits, :total_savings,
                    :current_discount, :last_updated,
                    :assess_finance_charges, :global_customer, :hqid,
                    :limit_purchase, :layaway_customer, :employee,
                    :primary_ship_to_id, :last_closing_balance,
                    :custom_num1, :custom_num2, :custom_num3, :custom_num4, :custom_num5,
                    :custom_text1, :custom_text2, :custom_text3, :custom_text4, :custom_text5
                )
                """

                params = {
                    # Identification
                    "account_number": account_number,
                    "first_name": "Cliente",
                    "last_name": "Invitado",
                    "email": "invitado@shopify.com",
                    # Address
                    "address": "N/A",
                    "city": "N/A",
                    "state": "N/A",
                    "zip": "00000",
                    "country": "CR",  # Costa Rica
                    "company": "",
                    "address2": "",
                    # Store
                    "store_id": settings.RMS_STORE_ID,
                    # Account settings
                    "account_type_id": 1,  # Default account type
                    "account_balance": 0.0,
                    "credit_limit": 0.0,
                    "total_sales": 0.0,
                    "total_savings": 0.0,
                    "current_discount": 0.0,
                    "last_closing_balance": 0.0,
                    # Dates
                    "account_opened": now,
                    "last_visit": now,
                    "last_updated": now,
                    # Counters
                    "total_visits": 0,
                    # Flags (all false/0)
                    "assess_finance_charges": 0,
                    "global_customer": 0,
                    "hqid": 0,
                    "limit_purchase": 0,
                    "layaway_customer": 0,
                    "employee": 0,
                    "primary_ship_to_id": 0,
                    # Custom fields (empty)
                    "custom_num1": 0.0,
                    "custom_num2": 0.0,
                    "custom_num3": 0.0,
                    "custom_num4": 0.0,
                    "custom_num5": 0.0,
                    "custom_text1": "",
                    "custom_text2": "",
                    "custom_text3": "",
                    "custom_text4": "",
                    "custom_text5": "",
                }

                result = await session.execute(text(insert_query), params)
                await session.commit()

                customer_id = result.scalar()
                if customer_id is None:
                    raise RMSConnectionException(
                        message="Failed to get customer ID after insert",
                        db_host=settings.RMS_DB_HOST,
                    )

                logger.info(f"✅ Created guest customer: ID={customer_id}, " f"AccountNumber={account_number}")

                # Cache the ID
                self._guest_customer_id = customer_id
                return customer_id

        except Exception as e:
            logger.error(f"Failed to find/create guest customer: {e}")
            logger.warning("Falling back to stub guest customer ID=9111")
            self._guest_customer_id = 9111
            return 9111

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
