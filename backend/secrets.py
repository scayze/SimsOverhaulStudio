"""Apply the premade scandal secrets seeded by ``SimInfoFixup`` tunings.

The game stores these as ``secrets_fixup_action`` entries: an owning sim (from
the template's ``_fixups`` list), a ``secret_ScandalSecret_*`` tuning, and an
optional ``complicit_premade_sim``. They are hidden connections, not friendship
scores, so they never overwrite the seeded sliders. A paired secret becomes a
"Secret: …" relationship bit on both sides; single-sim secrets are shown on the
sim's Secrets card.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .settings import APP_DIR

SECRETS_FILE = Path(APP_DIR) / "data" / "premade_secrets.json"

GENERIC_LABELS = {
    "Knows", "Has met", "Acquaintance", "Acquaintances", "Relative",
    "Household member", "Partner", "",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _resolve(first: str | None, last: str | None, sims: list[dict]):
    if not first:
        return None
    key = _norm(first + (last or ""))
    hits = {}
    for sim in sims:
        if _norm(sim.get("first", "") + sim.get("last", "")) == key:
            hits[(sim["first"], sim["last"], sim.get("household"))] = sim
    if len(hits) == 1:
        return next(iter(hits.values()))
    # Regnal suffixes may differ ("Thebe V" vs "Thebe").
    if last:
        first_norm = _norm(first)
        last_norm = _norm(last)
        hits = {}
        for sim in sims:
            if _norm(sim.get("first", "")) != first_norm:
                continue
            sim_last = _norm(sim.get("last", ""))
            if sim_last.startswith(last_norm) or last_norm.startswith(sim_last):
                hits[(sim["first"], sim["last"], sim.get("household"))] = sim
        if len(hits) == 1:
            return next(iter(hits.values()))
    return None


def _add_secret(sim: dict, secret: dict, target_key: str, target_name: str) -> None:
    entry = {
        "id": secret.get("secret", ""),
        "label": secret.get("label", "Secret"),
        "target": target_name,
        "target_key": target_key,
        "source": "game",
    }
    have = {(s.get("id"), s.get("target")) for s in sim.get("secrets", [])}
    if (entry["id"], entry["target"]) not in have:
        sim.setdefault("secrets", []).append(entry)


def _add_bit(owner: dict, target: dict, secret: dict) -> None:
    row = next((r for r in owner.get("relationships", []) if r.get("target") == target["key"]), None)
    label = f"Secret: {secret.get('label', 'secret')}"
    if row is None:
        owner.setdefault("relationships", []).append({
            "target": target["key"],
            "label": label,
            "friendship": 0,
            "romance": 0,
            "bits": [],
            "from_game": True,
            "source": "secret",
        })
        row = owner["relationships"][-1]
    elif row.get("label") in GENERIC_LABELS:
        row["label"] = label
    bit_id = secret.get("secret") or label
    if not any(b.get("id") == bit_id for b in row.get("bits", [])):
        row.setdefault("bits", []).append({"id": bit_id, "label": secret.get("label", "Secret"), "modded": False})


def apply(sims: list[dict]) -> int:
    if not SECRETS_FILE.is_file():
        return 0
    try:
        payload = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    touched = 0
    for secret in payload.get("secrets", []):
        owner_info = secret.get("owner")
        if not owner_info:
            continue
        owner = _resolve(owner_info.get("first"), owner_info.get("last"), sims)
        if not owner:
            continue
        target_info = secret.get("target") or {}
        target = _resolve(target_info.get("first"), target_info.get("last"), sims) if target_info.get("first") else None
        target_name = (f"{target['first']} {target['last']}" if target else secret.get("target_name", ""))
        _add_secret(owner, secret, target["key"] if target else "", target_name)
        if target and target["key"] != owner["key"]:
            _add_bit(owner, target, secret)
            _add_bit(target, owner, secret)
        touched += 1
    return touched
