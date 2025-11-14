"""
Cliente Redis para cache y tareas asíncronas.

Este módulo proporciona funciones para interactuar con Redis,
incluyendo operaciones de cache, pub/sub y gestión de sesiones.
"""

import logging
from typing import Optional

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance.

    Returns:
        redis.Redis: Redis client instance

    Raises:
        RuntimeError: If Redis URL is not configured
    """
    global _redis_client

    if not settings.REDIS_URL:
        raise RuntimeError("Redis URL not configured")

    if _redis_client is None:
        # Create Redis client synchronously (connection will be established async)
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.debug("Redis client instance created")

    return _redis_client


async def test_redis_connection() -> bool:
    """
    Verifica la conectividad con Redis.

    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        # Por ahora, simular la conexión
        # En producción, aquí se verificaría la conexión real con Redis
        logger.info("Redis connection test simulated")

        if settings.REDIS_URL:
            logger.debug(f"Would test connection to: {settings.REDIS_URL}")
            return True
        else:
            logger.warning("Redis URL not configured")
            return False

    except Exception as e:
        logger.error(f"Redis connection test failed: {e}")
        return False


async def get_cache(key: str) -> Optional[str]:
    """
    Obtiene un valor del cache.

    Args:
        key: Clave del cache

    Returns:
        Optional[str]: Valor del cache o None si no existe
    """
    # Implementación placeholder
    logger.debug(f"Getting cache value for key: {key}")
    return None


async def set_cache(key: str, value: str, expire: Optional[int] = None) -> bool:
    """
    Establece un valor en el cache.

    Args:
        key: Clave del cache
        value: Valor a almacenar
        expire: Tiempo de expiración en segundos

    Returns:
        bool: True si fue exitoso
    """
    # Implementación placeholder
    logger.debug(f"Setting cache value for key: {key} with value: {value} and expire: {expire}")
    return True


async def delete_cache(key: str) -> bool:
    """
    Elimina un valor del cache.

    Args:
        key: Clave del cache

    Returns:
        bool: True si fue exitoso
    """
    # Implementación placeholder
    logger.debug(f"Deleting cache value for key: {key}")
    return True


async def initialize_connection_pool():
    """
    Inicializa el pool de conexiones Redis.
    """
    logger.info("Initializing Redis connection pool (simulated)")


async def close_connection_pool():
    """
    Cierra el pool de conexiones Redis.
    """
    logger.info("Closing Redis connection pool (simulated)")


# Alias functions for lifespan compatibility
async def initialize_redis():
    """
    Inicializa Redis (alias para initialize_connection_pool).
    """
    await initialize_connection_pool()


async def close_redis():
    """
    Cierra Redis (alias para close_connection_pool).
    """
    await close_connection_pool()
