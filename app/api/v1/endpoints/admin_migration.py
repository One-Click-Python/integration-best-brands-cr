"""
Endpoints administrativos para migraciones y correcciones de datos.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/admin/migration",
    tags=["admin", "migration"],
    responses={404: {"description": "Not found"}},
)


class MigrationRequest(BaseModel):
    """Request para ejecutar migración."""

    dry_run: bool = Field(default=True, description="Si True, solo simula los cambios sin ejecutarlos")
    specific_handles: Optional[List[str]] = Field(
        default=None, description="Lista opcional de handles específicos a migrar"
    )


class MigrationResponse(BaseModel):
    """Response de migración."""

    status: str
    message: str
    stats: dict
    errors: List[str]


@router.get("/status")
async def get_migration_status():
    """
    Obtiene el estado actual de las migraciones.

    Returns:
        Estado y estadísticas de migraciones recientes
    """
    # TODO: Implementar tracking de estado de migraciones en Redis
    return {
        "status": "ready",
        "message": "Sistema de migración disponible",
        "available_migrations": ["fix-truncated-products", "fix-price-inconsistencies"],
    }
