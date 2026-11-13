"""Bootstrap and cache for the bundled SimsDataSDK.

The SDK lives in ``SimsDataSDK/`` (an unmodified upstream checkout).  This module
is the only place that touches ``sys.path`` and the workspace lifecycle; every
other backend module talks to the SDK through the helpers exported here.

If the SDK or the game install is missing, :func:`workspace` returns ``None`` and
the studio falls back to its own supplemental readers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .settings import APP_DIR, DATA_DIR, paths

SDK_ROOT = APP_DIR / "SimsDataSDK"
SDK_SRC = SDK_ROOT / "src"
SDK_AVAILABLE = (SDK_SRC / "sims4_sdk" / "__init__.py").is_file()

if SDK_AVAILABLE and str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

try:  # pragma: no cover - import guard for a missing checkout
    from sims4_sdk import Sims4Workspace  # type: ignore[import-not-found]
    from sims4_sdk.catalog.models import Catalog  # type: ignore[import-not-found]
    from sims4_sdk.installation import Installation  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    Sims4Workspace = None  # type: ignore[assignment]
    Catalog = None  # type: ignore[assignment]
    Installation = None  # type: ignore[assignment]

CACHE_DIR = DATA_DIR / "sdk_cache"

_WORKSPACE: Any = None
_STATIC: Any = None
_SKILL_CURVES: Any = None
_SKILL_CURVES_CHECKED = False


def workspace(refresh: bool = False):
    """Return a cached :class:`Sims4Workspace`, or ``None`` when unavailable."""
    global _WORKSPACE
    if _WORKSPACE is not None and not refresh:
        return _WORKSPACE
    if not SDK_AVAILABLE or Sims4Workspace is None:
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _WORKSPACE = Sims4Workspace(
            install_dir=str(paths.game) if paths.game else None,
            user_dir=str(paths.docs) if paths.docs else None,
            cache_dir=CACHE_DIR,
            include_mods=True,
        )
    except Exception:
        _WORKSPACE = None
    return _WORKSPACE


def static_data(refresh: bool = False, progress=None):
    """Return cached SDK static data (catalog + premades + lots)."""
    global _STATIC
    ws = workspace(refresh=refresh)
    if ws is None:
        return None
    if _STATIC is not None and not refresh:
        return _STATIC
    try:
        _STATIC = ws.static_data(refresh=refresh, use_cache=not refresh, progress=progress)
    except Exception:
        if not refresh:
            return None
        raise
    return _STATIC


def catalog(refresh: bool = False):
    data = static_data(refresh=refresh)
    return data.catalog if data is not None else None


def reset() -> None:
    """Drop the cached workspace/static data so the next call re-reads the game."""
    global _WORKSPACE, _STATIC, _SKILL_CURVES, _SKILL_CURVES_CHECKED
    _WORKSPACE = None
    _STATIC = None
    _SKILL_CURVES = None
    _SKILL_CURVES_CHECKED = False


def skill_curves():
    """Discover the installation's skill curves once per workspace refresh."""
    global _SKILL_CURVES, _SKILL_CURVES_CHECKED
    if not _SKILL_CURVES_CHECKED:
        _SKILL_CURVES_CHECKED = True
        install = installation()
        if install is not None:
            try:
                from sims4_sdk.skill_discovery import discover_skill_curves
                _SKILL_CURVES = discover_skill_curves(install.packages)
            except (OSError, ValueError):
                _SKILL_CURVES = None
    return _SKILL_CURVES


def installation():
    ws = workspace()
    return ws.installation if ws is not None else None


def available() -> bool:
    return workspace() is not None


def refresh(progress=None):
    """Rebuild the SDK catalog; used by the studio's *Scan Content* action."""
    reset()
    return static_data(refresh=True, progress=progress)


def pack_label(source) -> str:
    """Return a short pack label from a ``TuningSource`` or ``PackageInfo``."""
    if source is None:
        return ""
    pack = getattr(source, "pack", None) or ""
    if getattr(source, "is_mod", False):
        return "Mod"
    return pack or ""
