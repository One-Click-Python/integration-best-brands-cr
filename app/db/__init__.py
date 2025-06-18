"""
Módulo de acceso a bases de datos para RMS-Shopify Integration.

Este módulo proporciona acceso unificado a las bases de datos RMS
con separación clara de responsabilidades:

- ConnDB: Gestión exclusiva de conexiones
- RMSHandler: Operaciones de negocio específicas de RMS
"""

# Importaciones principales
from app.db.connection import (
    ConnDB,
    close_database,
    get_db_connection,
    initialize_database,
    test_database_connection,
)
from app.db.rms_handler import RMSHandler, initialize_rms_handler, test_rms_connection

# Exports principales
__all__ = [
    # Clase de conexión
    "ConnDB",
    "get_db_connection",
    # Funciones de gestión de conexión
    "initialize_database",
    "close_database",
    "test_database_connection",
    # Clase de operaciones RMS
    "RMSHandler",
    "initialize_rms_handler",
    "test_rms_connection",
]

# Información del módulo
__version__ = "1.0.0"
__author__ = "Leonardo Illanez"
__description__ = "Database access module with separated responsibilities"


# Funciones de conveniencia para compatibilidad con código existente
async def initialize_connection_pool():
    """
    Función de compatibilidad para inicializar pool de conexiones.

    Esta función mantiene compatibilidad con código existente
    mientras usa la nueva arquitectura internamente.
    """
    await initialize_database()


async def close_connection_pool():
    """
    Función de compatibilidad para cerrar pool de conexiones.

    Esta función mantiene compatibilidad con código existente
    mientras usa la nueva arquitectura internamente.
    """
    await close_database()


# Alias para compatibilidad
test_rms_connection = test_database_connection
