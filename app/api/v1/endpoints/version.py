"""
Version information endpoints.

This module provides endpoints for version information, including
current version, build metadata, and update availability checks.
"""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.version import (
    VERSION,
    check_for_updates,
    clear_update_cache,
    version_info,
    version_string,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class VersionResponse(BaseModel):
    """Full version information response."""

    version: str
    python_version: str
    git_commit: str | None
    git_branch: str | None
    build_date: str
    build_number: str | None
    environment: str


class ShortVersionResponse(BaseModel):
    """Short version response."""

    version: str
    version_string: str


class UpdateCheckResponse(BaseModel):
    """Update check response."""

    current_version: str
    latest_version: str | None
    update_available: bool
    release_url: str | None
    release_notes: str | None
    checked_at: str
    error: str | None


@router.get(
    "",
    response_model=VersionResponse,
    summary="Get version information",
    description="Returns comprehensive version information including git metadata and build info",
)
async def get_version() -> dict[str, Any]:
    """
    Get comprehensive version information.

    Returns:
        Version info including git commit, branch, build date, and environment
    """
    return version_info()


@router.get(
    "/short",
    response_model=ShortVersionResponse,
    summary="Get short version",
    description="Returns just the version number and formatted string",
)
async def get_version_short() -> dict[str, str]:
    """
    Get short version string.

    Returns:
        Version number and formatted version string
    """
    return {
        "version": VERSION,
        "version_string": version_string(),
    }


@router.get(
    "/check",
    response_model=UpdateCheckResponse,
    summary="Check for updates",
    description="Checks GitHub releases for available updates (cached for 1 hour)",
)
async def check_version_updates() -> dict[str, Any]:
    """
    Check for available updates from GitHub releases.

    Returns:
        Update check result with current version, latest version,
        and whether an update is available
    """
    return await check_for_updates()


@router.post(
    "/check/refresh",
    response_model=UpdateCheckResponse,
    summary="Force update check",
    description="Clears cache and performs fresh update check",
)
async def force_update_check() -> dict[str, Any]:
    """
    Force a fresh update check by clearing the cache.

    Returns:
        Fresh update check result
    """
    clear_update_cache()
    logger.info("Update cache cleared, performing fresh check")
    return await check_for_updates()
