# app/db/connection.py
"""
Clase ConnDB para gestión exclusiva de conexiones a base de datos SQL Server.

Esta clase maneja únicamente la conexión, configuración del pool,
y ciclo de vida de las conexiones a la base de datos RMS.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings
from app.utils.error_handler import RMSConnectionException

settings = get_settings()
logger = logging.getLogger(__name__)


class ConnDB:
    """
    Clase para gestión exclusiva de conexiones a la base de datos SQL Server.

    Esta clase implementa el patrón Singleton para garantizar una única
    instancia de conexión y maneja todo el ciclo de vida de las conexiones.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Implementa patrón Singleton."""
        if cls._instance is None:
            cls._instance = super(ConnDB, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa la clase ConnDB."""
        if not self._initialized:
            self.engine: Optional[AsyncEngine] = None
            self.session_factory: Optional[sessionmaker] = None
            self.connection_string = settings.rms_connection_string_async
            self._connection_tested = False
            ConnDB._initialized = True
            logger.info("ConnDB instance created")

    async def initialize(self):
        """
        Inicializa el engine de base de datos y el pool de conexiones.

        Raises:
            RMSConnectionException: Si falla la inicialización
        """
        try:
            if self.engine is not None:
                logger.info("Database connection already initialized")
                return

            logger.info("Initializing database connection...")

            # Crear engine con configuración optimizada para SQL Server
            self.engine = create_async_engine(
                self.connection_string,
                poolclass=QueuePool,
                pool_size=settings.RMS_MAX_POOL_SIZE,
                max_overflow=20,
                pool_pre_ping=True,  # Verificar conexiones antes de usar
                pool_recycle=3600,  # Reciclar conexiones cada hora
                pool_timeout=30,  # Timeout para obtener conexión del pool
                echo=settings.DEBUG,  # Log de queries SQL en modo debug
                echo_pool=settings.DEBUG,  # Log del pool en modo debug
                future=True,
                # Configuraciones específicas para SQL Server
                connect_args={
                    "server_settings": {
                        "application_name": f"{settings.APP_NAME}_v{settings.APP_VERSION}",
                        "connect_timeout": str(settings.RMS_CONNECTION_TIMEOUT),
                    }
                },
            )

            # Crear factory de sesiones
            self.session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False, autoflush=True, autocommit=False
            )

            # Verificar conexión inicial
            await self._test_connection()

            logger.info("Database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            await self._cleanup_failed_initialization()
            raise RMSConnectionException(
                message=f"Failed to initialize database connection: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="initialization",
            ) from e

    async def _test_connection(self):
        """
        Prueba la conexión a la base de datos.

        Raises:
            RMSConnectionException: Si la prueba de conexión falla
        """
        try:
            logger.info("Testing database connection...")

            async with self.get_session() as session:
                # Test simple de conexión
                result = await session.execute(text("SELECT 1 as test_connection"))
                test_value = result.scalar()

                if test_value != 1:
                    raise RMSConnectionException(
                        message="Connection test returned unexpected value",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="test",
                    )

                # Test de acceso a View_Items
                result = await session.execute(text("SELECT TOP 1 C_ARTICULO FROM View_Items"))
                sample_sku = result.scalar()

                if sample_sku:
                    logger.info(f"Connection test successful - Sample SKU: {sample_sku}")
                else:
                    logger.warning("Connection successful but View_Items appears empty")

                self._connection_tested = True

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise RMSConnectionException(
                message=f"Database connection test failed: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="test",
            ) from e

    async def _cleanup_failed_initialization(self):
        """Limpia recursos en caso de fallo de inicialización."""
        try:
            if self.engine:
                await self.engine.dispose()
                self.engine = None
            self.session_factory = None
            self._connection_tested = False
        except Exception as e:
            logger.error(f"Error during cleanup of failed initialization: {e}")

    def get_session(self) -> AsyncSession:
        """
        Obtiene una nueva sesión de base de datos.

        Returns:
            AsyncSession: Sesión asíncrona de SQLAlchemy

        Raises:
            RMSConnectionException: Si no hay conexión inicializada
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="Database connection not initialized. Call initialize() first.",
                db_host=settings.RMS_DB_HOST,
                connection_type="session_creation",
            )

        if self.session_factory is None:
            raise RMSConnectionException(
                message="Session factory is None. Database not properly initialized.",
                db_host=settings.RMS_DB_HOST,
                connection_type="session_creation",
            )

        return self.session_factory()

    def is_initialized(self) -> bool:
        """
        Verifica si la conexión está inicializada.

        Returns:
            bool: True si está inicializada y probada
        """
        return self.engine is not None and self.session_factory is not None and self._connection_tested

    async def test_connection(self) -> bool:
        """
        Prueba la conexión a la base de datos de forma no destructiva.

        Returns:
            bool: True si la conexión funciona correctamente
        """
        try:
            if not self.is_initialized():
                return False

            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def execute_raw_query(self, query: str, params: Optional[dict] = None):
        """
        Ejecuta una consulta SQL raw y retorna los resultados.

        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros opcionales para la consulta

        Returns:
            Result: Resultado de SQLAlchemy

        Raises:
            RMSConnectionException: Si falla la ejecución
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text(query), params or {})
                return result

        except Exception as e:
            logger.error(f"Failed to execute raw query: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute query: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution",
            ) from e

    async def close(self):
        """
        Cierra la conexión y limpia todos los recursos.
        """
        try:
            logger.info("Closing database connection...")

            if self.engine:
                await self.engine.dispose()
                logger.info("Database engine disposed")

            self.engine = None
            self.session_factory = None
            self._connection_tested = False

            logger.info("Database connection closed successfully")

        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise RMSConnectionException(
                message=f"Error closing database connection: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="close",
            ) from e

    def get_engine_info(self) -> dict:
        """
        Obtiene información sobre el engine de base de datos.

        Returns:
            dict: Información del engine y pool de conexiones
        """
        if not self.engine:
            return {"status": "not_initialized"}

        pool = self.engine.pool

        return {
            "status": "initialized",
            "connection_string": self.connection_string[:50] + "...",  # Truncar por seguridad
            "pool_size": getattr(pool, "size", lambda: 0)(),
            "checked_in": getattr(pool, "checkedin", lambda: 0)(),
            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
            "overflow": getattr(pool, "overflow", lambda: 0)(),
            "invalidated": getattr(pool, "invalidated", lambda: 0)(),
            "is_tested": self._connection_tested,
        }

    async def health_check(self) -> dict:
        """
        Realiza un health check completo de la conexión.

        Returns:
            dict: Estado de salud de la conexión
        """
        health_info = {
            "connection_initialized": self.is_initialized(),
            "engine_info": self.get_engine_info(),
            "test_passed": False,
            "response_time_ms": None,
            "error": None,
        }

        try:
            import time

            start_time = time.time()

            health_info["test_passed"] = await self.test_connection()

            end_time = time.time()
            health_info["response_time_ms"] = round((end_time - start_time) * 1000, 2)

        except Exception as e:
            health_info["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health_info

    def __str__(self) -> str:
        """Representación string de la conexión."""
        status = "initialized" if self.is_initialized() else "not_initialized"
        return f"ConnDB(status={status}, host={settings.RMS_DB_HOST})"

    def __repr__(self) -> str:
        """Representación detallada de la conexión."""
        return (
            f"ConnDB(initialized={self.is_initialized()}, "
            f"engine={self.engine is not None}, "
            f"session_factory={self.session_factory is not None})"
        )


# Instancia global singleton
_conn_db_instance = None


def get_db_connection() -> ConnDB:
    """
    Obtiene la instancia singleton de ConnDB.

    Returns:
        ConnDB: Instancia de conexión a base de datos
    """
    global _conn_db_instance

    if _conn_db_instance is None:
        _conn_db_instance = ConnDB()

    return _conn_db_instance


async def initialize_database():
    """
    Función de conveniencia para inicializar la base de datos.
    """
    conn_db = get_db_connection()
    await conn_db.initialize()


async def close_database():
    """
    Función de conveniencia para cerrar la base de datos.
    """
    conn_db = get_db_connection()
    await conn_db.close()


async def test_database_connection() -> bool:
    """
    Función de conveniencia para probar la conexión.

    Returns:
        bool: True si la conexión funciona
    """
    try:
        conn_db = get_db_connection()
        return await conn_db.test_connection()
    except Exception:
        return False
