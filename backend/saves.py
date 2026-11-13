"""Read Sims 4 ``.save`` files (read-only) through the bundled SimsDataSDK."""
from __future__ import annotations

import base64
import time

from . import sdk
from .sdkconvert import saved_sim_payload
from .settings import paths

_CACHE: dict[tuple[str, float], dict] = {}


def list_saves() -> list[dict]:
    if not paths.saves or not paths.saves.is_dir():
        return []
    out = []
    for p in sorted(paths.saves.glob("*.save"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            stat = p.stat()
        except OSError:
            continue
        slot = p.stem.replace("Slot_", "")
        try:
            slot_int = int(slot, 16)
        except ValueError:
            slot_int = 0
        out.append(
            {
                "file": p.name,
                "slot": p.stem,
                "slot_number": slot_int,
                "modified": stat.st_mtime,
                "modified_label": time.strftime("%d %b %Y %H:%M", time.localtime(stat.st_mtime)),
                "size": stat.st_size,
            }
        )
    return out


def _jpeg_data_url(raw: bytes | None) -> str | None:
    if not raw:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


def _artwork_data_url(artwork) -> str | None:
    if artwork is None:
        return None
    try:
        return "data:image/png;base64," + base64.b64encode(artwork.to_png()).decode("ascii")
    except (ValueError, OSError, ImportError):
        return _jpeg_data_url(artwork.jpeg)


def parse_save(filename: str) -> dict:
    if not paths.saves:
        raise FileNotFoundError("Saves folder not found")
    path = paths.saves / filename
    if not path.exists():
        raise FileNotFoundError(filename)

    stat = path.stat()
    key = (str(path), stat.st_mtime)
    if key in _CACHE:
        return _CACHE[key]

    workspace = sdk.workspace()
    if workspace is None:
        raise RuntimeError("SimsDataSDK could not find The Sims 4 installation")

    save = workspace.read_save(path)
    catalog = sdk.catalog()

    sims = []
    for sim in save.sims.values():
        if not sim.sim_id or not sim.first_name:
            continue
        sim_key = f"save:{filename}:{sim.sim_id:x}:{sim.first_name}|{sim.last_name}"
        payload = saved_sim_payload(sim, catalog, sim_key, filename)
        payload["household"] = sim.household_name or sim.last_name or "Household"
        payload["household_key"] = f"save:{filename}:{sim.household_id or payload['household']}"
        sims.append(payload)

    sims.sort(key=lambda item: (item["last"].lower(), item["first"].lower()))

    thumbnail = _artwork_data_url(save.thumbnail_image) or _jpeg_data_url(save.thumbnail)
    artwork = [
        image
        for image in save.artwork.values()
        if image.jpeg and image.jpeg != save.thumbnail
    ]
    artwork.sort(key=lambda image: len(image.jpeg), reverse=True)
    result = {
        "file": filename,
        "slot": path.stem,
        "thumbnail": thumbnail,
        "house_thumbnails": [_artwork_data_url(image) for image in artwork[:3]],
        "sims": sims,
        "households": [
            {
                "id": household.household_id,
                "name": household.name,
                "funds": household.money,
                "members": household.members,
                "is_player": household.is_player,
            }
            for household in save.households.values()
        ],
        "meta": {
            "modified": stat.st_mtime,
            "modified_label": time.strftime("%d %b %Y %H:%M", time.localtime(stat.st_mtime)),
            "size": stat.st_size,
            "slot_name": save.slot.slot_name,
            "artwork": len(save.artwork),
            "artwork_errors": len(save.artwork_errors),
        },
    }
    _CACHE[key] = result
    return result


def invalidate(filename: str | None = None) -> None:
    if filename is None:
        _CACHE.clear()
        return
    for key in list(_CACHE):
        if key[0].endswith(filename):
            del _CACHE[key]
