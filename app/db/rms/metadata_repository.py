"""
MetadataRepository: Lookup data and metadata operations for RMS.

Encapsulates retrieval of categories, families, genders, and other metadata
from RMS. These values change infrequently, making them good candidates for
caching. Extracted from legacy RMSHandler following Single Responsibility.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import text

from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class MetadataRepository(BaseRepository):
    """Repository for metadata and lookup operations in RMS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Simple in-memory cache for metadata (no Redis dependency required)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=30)  # Cache for 30 minutes
        self._cache_timestamps: Dict[str, datetime] = {}

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation("verify_table_access_metadata")
    async def _verify_table_access(self) -> None:
        """Verify access to View_Items for metadata queries."""
        try:
            async with self.conn_db.get_session() as session:
                # Only need View_Items for metadata
                result = await session.execute(text("SELECT COUNT(*) FROM View_Items"))
                _ = result.scalar()
                logger.info("MetadataRepository: View_Items access verified")
        except Exception as e:
            logger.error(f"MetadataRepository table access verification failed: {e}")
            raise RMSConnectionException(
                message=f"Cannot access View_Items for metadata: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="table_access_metadata",
            ) from e

    # ------------------------- Cache helpers -------------------------
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache and key in self._cache_timestamps:
            if datetime.utcnow() - self._cache_timestamps[key] < self._cache_ttl:
                logger.debug(f"Cache hit for metadata key: {key}")
                return self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Store value in cache with timestamp."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.utcnow()
        logger.debug(f"Cached metadata key: {key}")

    def clear_cache(self) -> None:
        """Clear all cached metadata."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("MetadataRepository cache cleared")

    # ------------------------- Metadata retrieval -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_categories(self) -> List[str]:
        """Get unique list of product categories from View_Items."""
        cache_key = "categories"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.get_session() as session:
                query = """
                SELECT DISTINCT Categoria 
                FROM View_Items 
                WHERE Categoria IS NOT NULL AND Categoria != ''
                ORDER BY Categoria
                """
                result = await session.execute(text(query))
                categories = [row[0] for row in result.fetchall()]
                
                self._set_cached(cache_key, categories)
                logger.info(f"Retrieved {len(categories)} unique categories")
                return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_families(self) -> List[str]:
        """Get unique list of product families from View_Items."""
        cache_key = "families"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.get_session() as session:
                query = """
                SELECT DISTINCT Familia 
                FROM View_Items 
                WHERE Familia IS NOT NULL AND Familia != ''
                ORDER BY Familia
                """
                result = await session.execute(text(query))
                families = [row[0] for row in result.fetchall()]
                
                self._set_cached(cache_key, families)
                logger.info(f"Retrieved {len(families)} unique families")
                return families
        except Exception as e:
            logger.error(f"Error getting families: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_genders(self) -> List[str]:
        """Get unique list of genders from View_Items."""
        cache_key = "genders"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.get_session() as session:
                query = """
                SELECT DISTINCT Genero 
                FROM View_Items 
                WHERE Genero IS NOT NULL AND Genero != ''
                ORDER BY Genero
                """
                result = await session.execute(text(query))
                genders = [row[0] for row in result.fetchall()]
                
                self._set_cached(cache_key, genders)
                logger.info(f"Retrieved {len(genders)} unique genders")
                return genders
        except Exception as e:
            logger.error(f"Error getting genders: {e}")
            return []

    # ------------------------- Extended metadata operations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_colors(self) -> List[str]:
        """Get unique list of colors from View_Items."""
        cache_key = "colors"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.get_session() as session:
                query = """
                SELECT DISTINCT color 
                FROM View_Items 
                WHERE color IS NOT NULL AND color != ''
                ORDER BY color
                """
                result = await session.execute(text(query))
                colors = [row[0] for row in result.fetchall()]
                
                self._set_cached(cache_key, colors)
                logger.info(f"Retrieved {len(colors)} unique colors")
                return colors
        except Exception as e:
            logger.error(f"Error getting colors: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_sizes(self) -> List[str]:
        """Get unique list of sizes (talla) from View_Items."""
        cache_key = "sizes"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            async with self.get_session() as session:
                query = """
                SELECT DISTINCT talla 
                FROM View_Items 
                WHERE talla IS NOT NULL AND talla != ''
                ORDER BY talla
                """
                result = await session.execute(text(query))
                sizes = [row[0] for row in result.fetchall()]
                
                self._set_cached(cache_key, sizes)
                logger.info(f"Retrieved {len(sizes)} unique sizes")
                return sizes
        except Exception as e:
            logger.error(f"Error getting sizes: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_all_metadata(self) -> Dict[str, List[str]]:
        """Get all metadata in a single call (useful for initialization)."""
        return {
            "categories": await self.get_categories(),
            "families": await self.get_families(),
            "genders": await self.get_genders(),
            "colors": await self.get_colors(),
            "sizes": await self.get_sizes(),
        }

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_metadata_stats(self) -> Dict[str, int]:
        """Get counts of all metadata types."""
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    COUNT(DISTINCT Categoria) as unique_categories,
                    COUNT(DISTINCT Familia) as unique_families,
                    COUNT(DISTINCT Genero) as unique_genders,
                    COUNT(DISTINCT color) as unique_colors,
                    COUNT(DISTINCT talla) as unique_sizes,
                    COUNT(DISTINCT CCOD) as unique_products
                FROM View_Items
                WHERE C_ARTICULO IS NOT NULL
                """
                result = await session.execute(text(query))
                row = result.fetchone()
                
                if row:
                    stats = row._asdict()
                    logger.info(f"Metadata stats: {stats}")
                    return stats
                return {}
        except Exception as e:
            logger.error(f"Error getting metadata stats: {e}")
            return {}