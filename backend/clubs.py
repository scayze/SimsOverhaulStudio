"""Club memberships (``PremadeSimTemplate.clubs``).

Clubs are a separate social system in The Sims 4, but the relationship panel
shows a club filter with the members. The game stores each premade sim's clubs
in ``PremadeSimTemplate.clubs``; the club seed (``clubSeed_*``) has the name.

This module reads the extracted ``data/premade_clubs.json`` and adds a
"Club member: <club>" link between members that otherwise have no relationship.
Existing relationships just get the club bit, so family/friend links are kept.
"""
from __future__ import annotations

import json
from pathlib import Path

from .settings import APP_DIR
from .households import _resolver

CLUBS_FILE = Path(APP_DIR) / "data" / "premade_clubs.json"


def _add(a: dict, b: dict, club: dict) -> None:
    bit_id = f"club:{club.get('seed')}"
    bit = {"id": bit_id, "label": club.get("name") or "Club", "modded": False}
    row = next((r for r in a.get("relationships", []) if r.get("target") == b["key"]), None)
    if row is not None:
        if not any(x.get("id") == bit_id for x in row.get("bits", [])):
            row.setdefault("bits", []).append(bit)
        return
    a.setdefault("relationships", []).append({
        "target": b["key"],
        "label": f"Club member: {club.get('name') or 'Club'}",
        "friendship": 0,
        "romance": 0,
        "bits": [bit],
        "from_game": True,
        "source": "club",
    })


def apply(sims: list[dict]) -> int:
    if not CLUBS_FILE.is_file():
        return 0
    try:
        payload = json.loads(CLUBS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    resolve = _resolver(sims)
    added = 0
    for club in payload.get("clubs", []):
        members = []
        for token in club.get("members", []):
            sim = resolve(token)
            if sim and all(sim["key"] != m["key"] for m in members):
                members.append(sim)
        if len(members) < 2:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                before = any(r.get("target") == b["key"] for r in a.get("relationships", []))
                _add(a, b, club)
                _add(b, a, club)
                if not before:
                    added += 1
    return added
