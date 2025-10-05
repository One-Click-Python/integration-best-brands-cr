"""
Base Repository for RMS Database Operations.

This module provides an abstract base class for all RMS repository classes,
implementing common functionality like connection management, session handling,
error handling, and table access verification.

Follows SOLID principles:
- Single Responsibility: Connection and session management only
- Open/Closed: Extensible through inheritance, closed for modification
- Liskov Substitution: All derived repositories can be used interchangeably
- Interface Segregation: Minimal interface with only necessary methods
- Dependency Inversion: Depends on abstractions (ConnDB) not concretions
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncContextManager, Callable, Dict, Optional, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.connection import ConnDB, get_db_connection
from app.utils.error_handler import RMSConnectionException

settings = get_settings()
logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3, 
    delay: float = 1.0, 
    backoff: float = 2.0,
    exceptions: tuple = (RMSConnectionException,)
) -> Callable:
    """
    Decorator for retrying database operations with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            # If all attempts failed, raise the last exception
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def log_operation(operation_name: str = None) -> Callable:
    """
    Decorator for logging database operations.
    
    Args:
        operation_name: Optional custom name for the operation
        
    Returns:
        Decorated function with logging
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            op_name = operation_name or f"{self.__class__.__name__}.{func.__name__}"
            logger.debug(f"Starting operation: {op_name}")
            
            try:
                result = await func(self, *args, **kwargs)
                logger.debug(f"Operation successful: {op_name}")
                return result
            except Exception as e:
                logger.error(f"Operation failed: {op_name} - {e}")
                raise
                
        return wrapper
    return decorator


class BaseRepository(ABC):
    """
    Abstract base repository for RMS database operations.
    
    This class provides common functionality for all repository classes:
    - Connection management with pooling
    - Session handling with context managers
    - Table access verification
    - Error handling and retry logic
    - Logging configuration
    
    All derived repositories should inherit from this class and implement
    their specific domain operations.
    """
    
    def __init__(self, conn_db: Optional[ConnDB] = None):
        """
        Initialize the base repository.
        
        Args:
            conn_db: Optional database connection. If not provided, uses global connection.
        """
        self.conn_db: ConnDB = conn_db or get_db_connection()
        self._initialized: bool = False
        self._repository_name: str = self.__class__.__name__
        logger.info(f"{self._repository_name} instantiated")
    
    @log_operation("repository_initialization")
    @with_retry(max_attempts=3, delay=1.0)
    async def initialize(self) -> None:
        """
        Initialize the repository ensuring database connection is available.
        
        Raises:
            RMSConnectionException: If initialization fails
        """
        try:
            # Initialize connection if not ready
            if not self.conn_db.is_initialized():
                await self.conn_db.initialize()
            
            # Verify access to required tables
            await self._verify_table_access()
            
            self._initialized = True
            logger.info(f"{self._repository_name} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self._repository_name}: {e}")
            raise RMSConnectionException(
                message=f"Failed to initialize {self._repository_name}: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="repository_initialization"
            ) from e
    
    @abstractmethod
    async def _verify_table_access(self) -> None:
        """
        Verify access to the tables required by this repository.
        
        This method must be implemented by derived classes to check
        access to their specific tables.
        
        Raises:
            RMSConnectionException: If table access verification fails
        """
        pass
    
    async def close(self) -> None:
        """
        Close the repository.
        
        Note: The actual connection is managed by ConnDB singleton,
        so we only mark the repository as uninitialized.
        """
        try:
            self._initialized = False
            logger.info(f"{self._repository_name} closed")
        except Exception as e:
            logger.error(f"Error closing {self._repository_name}: {e}")
    
    def is_initialized(self) -> bool:
        """
        Check if the repository is initialized and ready for operations.
        
        Returns:
            bool: True if repository is initialized
        """
        return self._initialized and self.conn_db.is_initialized()
    
    def get_session(self) -> AsyncContextManager[AsyncSession]:
        """
        Get a database session from the connection pool.
        
        Returns:
            AsyncContextManager[AsyncSession]: Database session context manager
            
        Raises:
            RMSConnectionException: If repository is not initialized
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message=f"{self._repository_name} not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="session_acquisition"
            )
        
        return self.conn_db.get_session()
    
    @log_operation()
    async def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a database query with parameters.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Query result
            
        Raises:
            RMSConnectionException: If query execution fails
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text(query), params or {})
                return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise RMSConnectionException(
                message=f"Query execution failed: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution"
            ) from e
    
    @log_operation()
    async def execute_query_with_commit(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a database query with automatic commit.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Query result
            
        Raises:
            RMSConnectionException: If query execution fails
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text(query), params or {})
                await session.commit()
                return result
        except Exception as e:
            logger.error(f"Query execution with commit failed: {e}")
            raise RMSConnectionException(
                message=f"Query execution with commit failed: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution_commit"
            ) from e
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the repository.
        
        Returns:
            Dict containing health status information
        """
        try:
            if not self.is_initialized():
                return {
                    "status": "unhealthy",
                    "repository": self._repository_name,
                    "initialized": False,
                    "error": "Repository not initialized"
                }
            
            # Try a simple query
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            
            return {
                "status": "healthy",
                "repository": self._repository_name,
                "initialized": True,
                "connection_pool_size": getattr(self.conn_db, 'pool_size', 'N/A')
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "repository": self._repository_name,
                "initialized": self._initialized,
                "error": str(e)
            }
    
    def __repr__(self) -> str:
        """String representation of the repository."""
        return f"<{self._repository_name}(initialized={self._initialized})>"