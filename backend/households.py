"""Shared name resolver for supplemental relationship data.

Household relationship bits and cross-household starting relationships are now
read directly from the SimsDataSDK (``PremadeHouseholdTemplate`` and
``PremadeSimRelationships``).  The remaining supplemental datasets (clubs,
secrets, EP21 NPC setup tunings) identify sims by tuning tokens or display
names, so they still need this normalising resolver.
"""
from __future__ import annotations

import re
import unicodedata

ALIASES = {
    "xochitilluna": "xochitlluna",
    "nigelgomezralston": "nigelchavezralston",
    "saragomezralston": "sarachavezralston",
    "aerisgomezralston": "aerischavezralston",
    "eringomezralston": "erinchavezralston",
}

PACK_TOKEN = re.compile(r"(?i)(ep|gp|sp|hs|bg|mp)\d*")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return ALIASES.get(re.sub(r"[^a-z0-9]", "", text.lower()), re.sub(r"[^a-z0-9]", "", text.lower()))


def _member_candidates(text: str) -> list[str]:
    t = re.sub(r"(?i)premadesimtemplate_|simtemplate_", "", text or "")
    parts = [p for p in t.split("_") if p]
    while parts and PACK_TOKEN.fullmatch(parts[0]):
        parts.pop(0)
    while parts and PACK_TOKEN.fullmatch(parts[-1]):
        parts.pop()
    out = []
    if parts:
        out.append(parts[-1])
        out.append("".join(parts))
    out.append(t)
    for cand in list(out):
        words = re.findall(r"[A-Z][a-z]+", cand)
        if words:
            out.append("".join(words))
            out.append(words[0])
    return list(dict.fromkeys(c for c in out if c))


FAMILY_META = {
    "Father": ("Child", 1, "parent"),
    "Mother": ("Child", 1, "parent"),
    "Child": ("Parent", -1, "child"),
    "Sibling": ("Sibling", 0, "sibling"),
    "Brother": ("Sibling", 0, "sibling"),
    "Sister": ("Sibling", 0, "sibling"),
    "Aunt / Uncle": ("Niece / Nephew", 1, "collateral"),
    "Niece / Nephew": ("Aunt / Uncle", -1, "collateral"),
    "Grandfather": ("Grandchild", 2, "grandparent"),
    "Grandmother": ("Grandchild", 2, "grandparent"),
    "Grandchild": ("Grandparent", -2, "grandchild"),
    "Spouse": ("Spouse", 0, "partner"),
}


def _apply_family(a: dict, b: dict, a_rel: str, b_rel: str, source: str = "household_tuning") -> None:
    for src, dst, relation in ((a, b, a_rel), (b, a, b_rel)):
        inverse, generation, category = FAMILY_META.get(relation, ("Relative", 0, "relative"))
        if not any(f.get("target") == dst["key"] for f in src.get("family", [])):
            src.setdefault("family", []).append({
                "target": dst["key"], "relation": relation, "inverse": inverse,
                "generation": generation, "category": category,
                "from_game": True, "source": source,
            })
        row = next((r for r in src.get("relationships", []) if r.get("target") == dst["key"]), None)
        if row is None:
            src.setdefault("relationships", []).append({
                "target": dst["key"], "label": relation, "friendship": 45, "romance": 0,
                "bits": [], "from_game": True, "source": source,
            })


def _resolver(sims: list[dict]):
    by_full, by_first, by_last = {}, {}, {}
    for sim in sims:
        row = sim
        by_full.setdefault(_norm(sim["first"] + sim["last"]), []).append(row)
        by_first.setdefault(_norm(sim["first"]), []).append(row)
        by_last.setdefault(_norm(sim["last"]), []).append(row)

    def unique(rows):
        seen = {}
        for row in rows:
            seen[(row["first"], row["last"], row.get("household"))] = row
        return list(seen.values())[0] if len(seen) == 1 else None

    def resolve(token: str):
        for candidate in _member_candidates(token):
            t = _norm(candidate)
            if not t:
                continue
            for table in (by_full, by_first, by_last):
                hit = unique(table.get(t, []))
                if hit:
                    return hit
        return None

    return resolve
