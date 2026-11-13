"""Locate The Sims 4 install + user folders and app paths."""
from __future__ import annotations

import os
import winreg
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
PROJECT_DIR = APP_DIR / "projects"
EXPORT_DIR = APP_DIR / "exports"

DATA_DIR.mkdir(exist_ok=True)
PROJECT_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)


def _docs_dir() -> Path | None:
    home = Path(os.path.expanduser("~"))
    candidates = [
        home / "Documents" / "Electronic Arts" / "The Sims 4",
        home / "OneDrive" / "Documents" / "Electronic Arts" / "The Sims 4",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _registry_game_dir() -> Path | None:
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Maxis\The Sims 4"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Maxis\The Sims 4"),
    ]
    for hive, key in keys:
        try:
            with winreg.OpenKey(hive, key) as handle:
                for value_name in ("Install Dir", "InstallDir", "Path"):
                    try:
                        value, _ = winreg.QueryValueEx(handle, value_name)
                    except OSError:
                        continue
                    p = Path(str(value).strip('"'))
                    if (p / "Game" / "Bin" / "TS4_x64.exe").exists():
                        return p
        except OSError:
            continue
    return None


def _guess_game_dir() -> Path | None:
    candidates: list[Path] = []
    for drive in ("C", "D", "E", "F", "G"):
        root = Path(drive + ":\\")
        candidates.extend(
            [
                root / "Spellen" / "The Sims 4",
                root / "Games" / "The Sims 4",
                root / "EA Games" / "The Sims 4",
                root / "Program Files" / "EA Games" / "The Sims 4",
                root / "Program Files (x86)" / "EA Games" / "The Sims 4",
                root / "Program Files (x86)" / "Origin Games" / "The Sims 4",
                root / "Program Files (x86)" / "Steam" / "steamapps" / "common" / "The Sims 4",
                root / "SteamLibrary" / "steamapps" / "common" / "The Sims 4",
                root / "The Sims 4",
            ]
        )
    for c in candidates:
        if (c / "Game" / "Bin" / "TS4_x64.exe").exists():
            return c
    return None


class Paths:
    def __init__(self) -> None:
        self.docs = _docs_dir()
        self.game = _registry_game_dir() or _guess_game_dir()
        self.mods = (self.docs / "Mods") if self.docs else None
        self.saves = (self.docs / "saves") if self.docs else None
        self.tray = (self.docs / "Tray") if self.docs else None

    def as_dict(self) -> dict:
        return {
            "app": str(APP_DIR),
            "docs": str(self.docs) if self.docs else None,
            "game": str(self.game) if self.game else None,
            "mods": str(self.mods) if self.mods else None,
            "saves": str(self.saves) if self.saves else None,
            "tray": str(self.tray) if self.tray else None,
            "exports": str(EXPORT_DIR),
        }


paths = Paths()

PACK_NAMES = {
    "Base": "Base Game",
    "EP01": "Get to Work",
    "EP02": "Get Together",
    "EP03": "City Living",
    "EP04": "Cats & Dogs",
    "EP05": "Seasons",
    "EP06": "Get Famous",
    "EP07": "Island Living",
    "EP08": "Discover University",
    "EP09": "Eco Lifestyle",
    "EP10": "Snowy Escape",
    "EP11": "Cottage Living",
    "EP12": "High School Years",
    "EP13": "Growing Together",
    "EP14": "Horse Ranch",
    "EP15": "For Rent",
    "EP16": "Lovestruck",
    "EP17": "Life & Death",
    "EP18": "EP18",
    "EP19": "EP19",
    "EP20": "EP20",
    "EP21": "EP21",
    "GP01": "Outdoor Retreat",
    "GP02": "Spa Day",
    "GP03": "Dine Out",
    "GP04": "Vampires",
    "GP05": "Parenthood",
    "GP06": "Jungle Adventure",
    "GP07": "StrangerVille",
    "GP08": "Realm of Magic",
    "GP09": "Journey to Batuu",
    "GP10": "Dream Home Decorator",
    "GP11": "My Wedding Stories",
    "GP12": "Werewolves",
    "FP01": "Free Pack",
}
