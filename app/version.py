"""
Version information for RMS-Shopify Integration.

Single source of truth: pyproject.toml
Runtime access via importlib.metadata with fallback.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx

# Fallback version if package metadata unavailable (dev mode)
_FALLBACK_VERSION = "1.0.0"

# GitHub repository configuration
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "rms-shopify-integration")
GITHUB_API_BASE = "https://api.github.com"

# Cache TTL for update checks (1 hour)
_UPDATE_CHECK_CACHE_TTL = 3600


def get_version() -> str:
    """Get the package version from metadata or fallback."""
    try:
        from importlib.metadata import version

        return version("rms-shopify-integration")
    except Exception:
        return _FALLBACK_VERSION


VERSION = get_version()


@lru_cache(maxsize=1)
def get_git_info() -> dict[str, str | None]:
    """
    Get git commit info (cached for performance).

    Returns:
        dict with commit hash, branch name, and source
    """
    # Check for Docker build args first (priority)
    commit = os.environ.get("GIT_COMMIT")
    branch = os.environ.get("GIT_BRANCH")

    if commit:
        return {
            "commit": commit[:8] if len(commit) > 8 else commit,
            "branch": branch,
            "source": "env",
        }

    # Fall back to git commands (development mode)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        return {"commit": commit, "branch": branch, "source": "git"}
    except Exception:
        return {"commit": None, "branch": None, "source": None}


@lru_cache(maxsize=1)
def get_build_info() -> dict[str, str | None]:
    """
    Get build metadata from environment.

    Returns:
        dict with build_date and build_number
    """
    return {
        "build_date": os.environ.get("BUILD_DATE"),
        "build_number": os.environ.get("BUILD_NUMBER"),
    }


def version_info() -> dict[str, Any]:
    """
    Get comprehensive version information.

    Returns:
        dict with version, python_version, git info, and build info
    """
    git = get_git_info()
    build = get_build_info()

    return {
        "version": VERSION,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "git_commit": git.get("commit"),
        "git_branch": git.get("branch"),
        "build_date": build.get("build_date") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build_number": build.get("build_number"),
        "environment": os.environ.get("ENV", os.environ.get("ENVIRONMENT", "development")),
    }


def version_string() -> str:
    """
    Get formatted version string for display.

    Returns:
        Formatted version string like "v1.0.0 (abc1234)"
    """
    info = version_info()
    parts = [f"v{info['version']}"]
    if info.get("git_commit"):
        parts.append(f"({info['git_commit']})")
    return " ".join(parts)


def version_string_full() -> str:
    """
    Get full formatted version string with branch.

    Returns:
        Formatted version string like "v1.0.0 (abc1234) - main"
    """
    info = version_info()
    parts = [f"v{info['version']}"]
    if info.get("git_commit"):
        parts.append(f"({info['git_commit']})")
    if info.get("git_branch"):
        parts.append(f"- {info['git_branch']}")
    return " ".join(parts)


# Cache for update check results
_update_check_cache: dict[str, Any] = {}
_update_check_timestamp: float = 0


async def check_for_updates() -> dict[str, Any]:
    """
    Check GitHub releases for available updates.

    Returns:
        dict with current_version, latest_version, update_available,
        release_url, and checked_at
    """
    import time

    global _update_check_cache, _update_check_timestamp

    # Return cached result if still valid
    current_time = time.time()
    if _update_check_cache and (current_time - _update_check_timestamp) < _UPDATE_CHECK_CACHE_TTL:
        return _update_check_cache

    result = {
        "current_version": VERSION,
        "latest_version": None,
        "update_available": False,
        "release_url": None,
        "release_notes": None,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": None,
    }

    # Skip if GitHub repo not configured
    if not GITHUB_REPO_OWNER:
        result["error"] = "GitHub repository not configured (set GITHUB_REPO_OWNER)"
        _update_check_cache = result
        _update_check_timestamp = current_time
        return result

    try:
        url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"RMS-Shopify-Integration/{VERSION}",
                },
            )

            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                result["latest_version"] = latest_tag
                result["release_url"] = data.get("html_url")
                result["release_notes"] = data.get("body", "")[:500]  # Truncate notes

                # Compare versions
                if latest_tag and _compare_versions(latest_tag, VERSION) > 0:
                    result["update_available"] = True

            elif response.status_code == 404:
                result["error"] = "No releases found in repository"
            else:
                result["error"] = f"GitHub API error: {response.status_code}"

    except httpx.TimeoutException:
        result["error"] = "GitHub API timeout"
    except Exception as e:
        result["error"] = f"Update check failed: {str(e)}"

    # Cache the result
    _update_check_cache = result
    _update_check_timestamp = current_time

    return result


def check_for_updates_sync() -> dict[str, Any]:
    """
    Synchronous version of check_for_updates for dashboard use.

    Returns:
        dict with update check results
    """
    import time

    global _update_check_cache, _update_check_timestamp

    # Return cached result if still valid
    current_time = time.time()
    if _update_check_cache and (current_time - _update_check_timestamp) < _UPDATE_CHECK_CACHE_TTL:
        return _update_check_cache

    result = {
        "current_version": VERSION,
        "latest_version": None,
        "update_available": False,
        "release_url": None,
        "release_notes": None,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": None,
    }

    # Skip if GitHub repo not configured
    if not GITHUB_REPO_OWNER:
        result["error"] = "GitHub repository not configured (set GITHUB_REPO_OWNER)"
        _update_check_cache = result
        _update_check_timestamp = current_time
        return result

    try:
        url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"RMS-Shopify-Integration/{VERSION}",
                },
            )

            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                result["latest_version"] = latest_tag
                result["release_url"] = data.get("html_url")
                result["release_notes"] = data.get("body", "")[:500]

                if latest_tag and _compare_versions(latest_tag, VERSION) > 0:
                    result["update_available"] = True

            elif response.status_code == 404:
                result["error"] = "No releases found in repository"
            else:
                result["error"] = f"GitHub API error: {response.status_code}"

    except httpx.TimeoutException:
        result["error"] = "GitHub API timeout"
    except Exception as e:
        result["error"] = f"Update check failed: {str(e)}"

    _update_check_cache = result
    _update_check_timestamp = current_time

    return result


def _compare_versions(v1: str, v2: str) -> int:
    """
    Compare two semantic version strings.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        1 if v1 > v2, -1 if v1 < v2, 0 if equal
    """
    try:
        # Remove 'v' prefix if present
        v1 = v1.lstrip("v")
        v2 = v2.lstrip("v")

        # Split version and pre-release parts
        v1_parts = v1.split("-")[0].split(".")
        v2_parts = v2.split("-")[0].split(".")

        # Pad with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_nums = [int(p) for p in v1_parts] + [0] * (max_len - len(v1_parts))
        v2_nums = [int(p) for p in v2_parts] + [0] * (max_len - len(v2_parts))

        # Compare
        for a, b in zip(v1_nums, v2_nums, strict=True):
            if a > b:
                return 1
            if a < b:
                return -1

        # Handle pre-release (versions without pre-release are newer)
        v1_has_pre = "-" in v1
        v2_has_pre = "-" in v2
        if v1_has_pre and not v2_has_pre:
            return -1
        if v2_has_pre and not v1_has_pre:
            return 1

        return 0
    except Exception:
        return 0


def clear_update_cache() -> None:
    """Clear the update check cache to force a fresh check."""
    global _update_check_cache, _update_check_timestamp
    _update_check_cache = {}
    _update_check_timestamp = 0


# Export public API
__all__ = [
    "VERSION",
    "get_version",
    "get_git_info",
    "get_build_info",
    "version_info",
    "version_string",
    "version_string_full",
    "check_for_updates",
    "check_for_updates_sync",
    "clear_update_cache",
]
