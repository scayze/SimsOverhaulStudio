"""Apply the EP21 ``loot_WorldEP21_NPC_*`` relationship seeds.

These tunings encode the Bellacorde NPC social/family graph: exact friendship /
romance values plus sentiments and family/romance tropes, including the
cross-household Capp/Monty/Abrantes/Thebe/Darong links.

The pair is in the tuning name; the values/sentiments are extracted into
``data/premade_npc_relations.json``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .settings import APP_DIR
from .households import _apply_family

REL_FILE = Path(APP_DIR) / "data" / "premade_npc_relations.json"

EP21_HOUSEHOLDS = {
    "abrantes", "acosta", "alto", "ananou", "capp", "capp (townie)", "darong",
    "fidential", "monty", "onoja", "romualdo", "thebe",
}
ALIASES = {"virgil": "virgilio"}

# First names alone are not enough: the EP21 world has several base-game sims
# with the same first name (Mara Summerdream vs Mara Acosta, Sofia Bjergsen vs
# Sofia Abrantes, Celeste Michaelson vs Celeste Capp). The tuning pack is EP21,
# so require the surname that the EP21 template uses; if that sim is not in the
# clean-world project (some NPC-only templates are not placed), skip the pair
# instead of linking the wrong sim.
SURNAME_HINTS = {
    "adekoya": "darong", "afua": "ananou", "akachi": "onoja",
    "beatrice": "capp", "celeste": "capp", "consort": "capp",
    "cordelia": "thebe", "dante": "monty", "ekene": "ananou",
    "ikenna": "darong", "jawara": "darong", "joana": "abrantes",
    "juliette": "monty", "laxmi": "kunal", "mara": "acosta",
    "obi": "darong", "raheel": "kunal", "romeo": "monty",
    "sofia": "abrantes", "thiago": "abrantes", "tybalt": "capp",
    "virgilio": "capp", "virgil": "capp",
}

# Inferred family edges: the tuning names/tropes identify a family relationship
# but do not encode the exact parent/child/sibling edge. The UI marks these as
# "Inferred". Consort is deliberately NOT made Tybalt/Juliette's father: the
# tuning only says "difficult family", and the game's own family tree has
# Consort as their grandfather (Caliban/Cordelia are the parents).
FAMILY_PAIRS = {
    frozenset(("tybalt", "juliette")): ("Sibling", "Sibling"),
    frozenset(("sofia", "thiago")): ("Sibling", "Sibling"),
}

BIT_LABELS = {
    "has_met": "Has met",
    "loot_FamilyTrope_difficult": "Family trope: difficult",
    "loot_FamilyTrope_compliant": "Family trope: compliant",
    "loot_FamilyTrope_loving": "Family trope: loving",
    "loot_FamilyTrope_close": "Family trope: close",
    "loot_FamilyTrope_permissive": "Family trope: permissive",
    "loot_FamilyTrope_distant": "Family trope: distant",
    "loot_FamilyTrope_Cheat_loving": "Family trope: cheating",
    "loot_RomanceTrope_wholesome": "Romance trope: wholesome",
    "loot_RomanceTrope_steamy": "Romance trope: steamy",
    "loot_RomanceTrope_strained": "Romance trope: strained",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _bit_label(bit: str) -> str:
    if bit in BIT_LABELS:
        return BIT_LABELS[bit]
    if bit.startswith("loot_Sentiment_AddSentiment_"):
        tail = bit[len("loot_Sentiment_AddSentiment_"):]
        tail = re.sub(r"_(generic|AboutTarget|TargetAboutActor|TargetToActor|LT|ST|AboutTargetSim|TargetAboutActorSim).*$", "", tail)
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", tail).replace("_", " ").strip()
    return bit.split("_")[-1]


def _resolve(token: str, sims: list[dict]):
    t = _norm(ALIASES.get(_norm(token), token))
    if not t:
        return None
    candidates = [s for s in sims if _norm(s["first"]) == t or _norm(s["first"] + s["last"]) == t
                  or _norm(s["last"]) == t]
    hint = SURNAME_HINTS.get(t)
    if hint:
        candidates = [s for s in candidates if hint in _norm(s.get("last", ""))]
    if not candidates:
        return None
    unique = {(s["first"], s["last"], s.get("household")): s for s in candidates}
    if len(unique) == 1:
        return next(iter(unique.values()))
    # Prefer the Bellacorde (EP21) sim, then a dynasty sim.
    ep21 = [s for s in unique.values() if (s.get("household") or "").lower() in EP21_HOUSEHOLDS]
    if len(ep21) == 1:
        return ep21[0]
    if ep21:
        return ep21[0]
    dyn = [s for s in unique.values() if s.get("game_dynasty")]
    return dyn[0] if len(dyn) == 1 else None


def apply(sims: list[dict]) -> int:
    if not REL_FILE.is_file():
        return 0
    try:
        payload = json.loads(REL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    touched = 0
    for pair in payload.get("pairs", []):
        tokens = pair.get("tokens") or []
        if len(tokens) < 2:
            continue
        a = _resolve(tokens[0], sims)
        b = _resolve(tokens[1], sims)
        if not a or not b or a["key"] == b["key"]:
            continue
        family = FAMILY_PAIRS.get(frozenset((_norm(tokens[0]), _norm(tokens[1]))))
        if family:
            _apply_family(a, b, family[0], family[1], source="inferred")
        friendship = pair.get("friendship")
        romance = pair.get("romance")
        bits = [bit for bit in (pair.get("bits") or []) if bit != "has_met" or
                (friendship is None and romance is None and len(pair.get("bits") or []) == 1)]
        for src, dst in ((a, b), (b, a)):
            row = next((r for r in src.get("relationships", []) if r.get("target") == dst["key"]), None)
            if row is None:
                row = {
                    "target": dst["key"], "label": "Knows",
                    "friendship": 0, "romance": 0, "bits": [],
                    "from_game": True, "source": "npc",
                }
                src.setdefault("relationships", []).append(row)
            if friendship is not None:
                row["friendship"] = friendship
            if romance is not None:
                row["romance"] = romance
            have = {x.get("id") for x in row.get("bits", [])}
            for bit in bits:
                if bit not in have:
                    row.setdefault("bits", []).append({"id": bit, "label": _bit_label(bit), "modded": False})
            if not family_label(row):
                if romance:
                    row["label"] = "Secret love" if any("SecretLove" in bit for bit in bits) else "Romantic"
                elif friendship is not None and friendship < 0:
                    row["label"] = "Bitter" if any("Bitter" in bit for bit in bits) else "Disliked"
                elif any("FamilyTrope" in bit for bit in bits):
                    row["label"] = "Family (difficult)"
        touched += 1
    return touched


def family_label(row: dict) -> bool:
    return (row.get("label") or "") in {
        "Mother", "Father", "Child", "Sibling", "Brother", "Sister",
        "Niece / Nephew", "Aunt / Uncle", "Grandparent", "Grandchild", "Spouse",
    }
