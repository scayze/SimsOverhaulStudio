"""Map catalog items to the Sims 4 icon pack provided by the user."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from .settings import APP_DIR

PACK = APP_DIR / "sims icons" / "sims 4" / "_pack"

KIND_DIRS = {
    "traits": [
        "Main Traits",
        "Reward Traits",
        "Bonus Traits",
        "Toddler Traits",
        "Pet Traits",
        "Fears",
        "Kuttoe Traits Icons",
        "Infants/Infant Traits",
        "Child and Teen",
        "Misc Traits",
        "Attraction",
        "Lifestyles",
    ],
    "skills": ["Skills"],
    "careers": ["Careers"],
    "aspirations": ["Aspirations"],
    "degrees": ["Degrees"],
    "milestones": ["Milestones"],
    "preferences": ["Likes and Dislikes"],
    "relationship_bits": ["Sentiments", "Relationship Bits"],
}

_INDEX: dict[str, list[tuple[str, str]]] = {}

SYNONYMS = {
    "traits": {
        "cheerful": "cheeful",  # typo in the icon pack filename
    },
    "skills": {
        "bartending": "mixology",
        "homestylecooking": "cooking",
        "equestrianskill": "riding",
        "ranchnectar": "nectarmaking",
        "reaping": "thanatology",
    },
    "aspirations": {
        "beachbum": "beachlife",
        "citylife": "citynative",
        "childcreativity": "creativegenius",
        "childmental": "mindandbody",
        "childsocial": "playtimecaptain",
        "childmotor": "rambunctiousscamp",
        "childcoolkid": "coolkidontheblock",
        "naturecritterhunter": "critterhunter",
    },
    "careers": {
        "buisness": "business",
    },
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _split_words(text: str) -> str:
    text = re.sub(r"^(trait|statistic|skill|career|aspiration|milestone)[_ ]+", "", text, flags=re.I)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return _norm(text)


def _candidate_keys(label: str, tuning: str) -> list[str]:
    keys = []
    if tuning:
        twords = [w for w in re.split(r"[_\s]+", tuning) if w]
        if twords:
            keys.append(_norm(twords[-1]))
        keys.append(_split_words(tuning))
        if len(twords) >= 2:
            keys.append(_norm(" ".join(twords[-2:])))
    keys.append(_norm(label))
    words = re.sub(r"[^A-Za-z0-9 ]", " ", label).split()
    if len(words) >= 2:
        keys.append(_norm(" ".join(words[-2:])))
    if words:
        keys.append(_norm(words[-1]))
    return [k for k in dict.fromkeys(keys) if k]


def _build() -> None:
    if _INDEX:
        return
    for kind, dirs in KIND_DIRS.items():
        entries: list[tuple[str, str]] = []
        for dirname in dirs:
            root = PACK / dirname
            if not root.is_dir():
                continue
            for path in root.rglob("*.png"):
                rel = path.relative_to(PACK).as_posix()
                entries.append((_norm(path.stem), rel))
        _INDEX[kind] = entries


@lru_cache(maxsize=8192)
def icon_for_strict(kind: str, label: str, tuning: str = "") -> str | None:
    """Exact-label / tuning-word matching only. Used to filter real traits."""
    _build()
    entries = _INDEX.get(kind, [])
    if not entries:
        return None
    keys = [_norm(label)]
    if tuning:
        keys.append(_split_words(tuning))
        words = [w for w in re.split(r"[_\s]+", tuning) if w]
        if words:
            keys.append(_norm(words[-1]))
    synonyms = SYNONYMS.get(kind, {})
    for cand in keys:
        cand = synonyms.get(cand, cand)
        for stem, rel in entries:
            if stem == cand:
                return _url(rel)
    return None


@lru_cache(maxsize=8192)
def icon_for(kind: str, label: str, tuning: str = "") -> str | None:
    _build()
    entries = _INDEX.get(kind, [])
    if not entries:
        return None
    candidates = _candidate_keys(label, tuning)
    synonyms = SYNONYMS.get(kind, {})
    for cand in candidates:
        cand = synonyms.get(cand, cand)
        for stem, rel in entries:
            if stem == cand:
                return _url(rel)

    # tuning names often contain extra words; require a close length match
    for cand in candidates:
        if len(cand) < 4:
            continue
        for stem, rel in entries:
            if stem and (cand in stem or stem in cand) and abs(len(stem) - len(cand)) <= 10:
                return _url(rel)

    # fuzzy matching only as a last resort
    for cand in candidates:
        if len(cand) < 4:
            continue
        best = None
        best_ratio = 0.0
        for stem, rel in entries:
            ratio = SequenceMatcher(None, cand, stem).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = rel
        if best and best_ratio >= 0.86:
            return _url(best)
    return None


def _url(rel: str) -> str:
    return "/icons/sims%204/_pack/" + quote(rel, safe="/")
