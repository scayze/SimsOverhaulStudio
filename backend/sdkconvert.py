"""Convert SimsDataSDK models into the JSON shape the studio UI expects."""
from __future__ import annotations

from typing import Any, Iterable

from .catalog import pretty
from .settings import PACK_NAMES
from .skillcurve import level_for_xp, level_type_for_tuning

AGE_LABELS = {
    "BABY": "Baby",
    "INFANT": "Infant",
    "TODDLER": "Toddler",
    "CHILD": "Child",
    "TEEN": "Teen",
    "YOUNGADULT": "Young Adult",
    "YOUNG_ADULT": "Young Adult",
    "ADULT": "Adult",
    "ELDER": "Elder",
}
SPECIES_LABELS = {
    "HUMAN": "Human",
    "DOG": "Dog",
    "CAT": "Cat",
    "HORSE": "Horse",
    "FOX": "Fox",
    "RACCOON": "Raccoon",
    "CHICKEN": "Chicken",
    "LLAMA": "Llama",
    "GOAT": "Goat",
    "SHEEP": "Sheep",
}
GENDER_LABELS = {
    "MALE": "Male",
    "FEMALE": "Female",
    "NONBINARY": "Non-binary",
    "NON_BINARY": "Non-binary",
}


def title_enum(value: str | None, table: dict[str, str] | None = None, default: str = "") -> str:
    if not value:
        return default
    key = str(value).upper().replace(" ", "_")
    if table and key in table:
        return table[key]
    return str(value).replace("_", " ").title()


def source_pack(source) -> tuple[str, str]:
    """Return ``(pack_code, pack_label)`` for an SDK tuning source."""
    if source is None:
        return "", ""
    if getattr(source, "is_mod", False):
        return "MOD", "Mod"
    raw = (getattr(source, "pack", "") or "").upper()
    pack = "Base" if raw == "BASE" else raw
    return pack, PACK_NAMES.get(pack, pack)


def item_payload(item, kind: str = "", label: str | None = None) -> dict:
    """Build the studio's compact reference object for a catalog model."""
    name = getattr(item, "name", "") or ""
    display = getattr(item, "display_name", None) or getattr(item, "title", None)
    pack, pack_label = source_pack(getattr(item, "source", None))
    return {
        "id": getattr(item, "id", 0) or 0,
        "label": label or display or pretty(name),
        "tuning": name,
        "modded": pack == "MOD",
        "pack": PACK_NAMES.get(pack, pack_label) if pack != "MOD" else "Mod",
    }


def trait_payload(trait, label: str | None = None) -> dict:
    payload = item_payload(trait, "traits", label)
    payload.update(
        {
            "trait_type": getattr(trait, "trait_type", "") or "",
            "hidden": bool(getattr(trait, "is_hidden", False)),
        }
    )
    return payload


def preference_payload(preference, label: str | None = None) -> dict:
    payload = item_payload(preference, "preferences", label)
    ptype = (getattr(preference, "preference_type", "") or "").upper()
    payload["preference_type"] = ptype
    payload["like"] = ptype in {"LIKE", "LIKES", "LIKED"}
    return payload


def skill_payload(skill, catalog=None, label: str | None = None) -> dict:
    name = getattr(skill, "name", None) or getattr(skill, "skill_name", None) or ""
    if not name and catalog is not None:
        name = catalog.tuning_names.get(getattr(skill, "skill_id", 0), "") or ""
    display = label or (
        getattr(skill, "display_name", None)
        or (pretty(name) if name else f"Skill {getattr(skill, 'skill_id', 0)}")
    )
    value = getattr(skill, "value", None)
    level = getattr(skill, "level", None)
    if level is None and value is not None:
        try:
            level = level_for_xp(float(value), level_type_for_tuning(name))
        except Exception:
            level = None
    payload = {
        "id": getattr(skill, "skill_id", 0) or 0,
        "label": display,
        "tuning": name,
        "modded": False,
        "pack": "",
    }
    if value is not None:
        payload["xp"] = round(float(value), 1)
    if level is not None:
        payload["level"] = int(level)
    else:
        payload["level_unknown"] = True
    return payload


def career_payload(career, track=None, level=None, display_level=None, label: str | None = None) -> dict | None:
    if career is None and track is None:
        return None
    career_name = getattr(career, "name", "") or ""
    track_name = getattr(track, "name", "") or ""
    payload = {
        "id": getattr(career, "id", 0) or getattr(track, "id", 0) or 0,
        "label": label
        or getattr(track, "display_name", None)
        or pretty(track_name or career_name),
        "modded": False,
        "level": int(level or display_level or 1),
    }
    if track is not None:
        payload["track"] = getattr(track, "display_name", None) or pretty(track_name)
        payload["track_id"] = getattr(track, "id", 0) or 0
    return payload


def career_payload_from_saved(career, label: str | None = None) -> dict:
    level = getattr(career, "level", None)
    display = (
        getattr(level, "title", None)
        if level is not None
        else None
    ) or getattr(career, "title", None)
    payload = {
        "id": getattr(career, "career_id", 0) or 0,
        "label": label or pretty(getattr(career, "career_name", None) or ""),
        "modded": False,
        "level": int(getattr(career, "user_display_level", None) or (getattr(career, "track_level", 0) + 1) or 1),
    }
    track = getattr(career, "track", None)
    if track is not None:
        payload["track"] = getattr(track, "display_name", None) or pretty(getattr(track, "name", "") or "")
        payload["track_id"] = getattr(track, "id", 0) or 0
    if display:
        payload["title"] = display
    if getattr(career, "pay_per_hour", None) is not None:
        payload["pay_per_hour"] = career.pay_per_hour
    return payload


def aspiration_payload(aspiration, label: str | None = None) -> dict | None:
    if aspiration is None:
        return None
    payload = item_payload(aspiration, "aspirations", label)
    payload["track"] = False
    return payload


def aspiration_track_payload(track, label: str | None = None) -> dict | None:
    if track is None:
        return None
    name = getattr(track, "name", "") or ""
    payload = item_payload(track, "aspiration_tracks", label or pretty(name).replace("Track ", ""))
    payload["track"] = True
    return payload


def milestone_payload(milestone) -> dict | None:
    if milestone is None:
        return None
    payload = item_payload(milestone, "milestones")
    payload["label"] = (
        getattr(milestone, "display_name", None)
        or pretty(getattr(milestone, "name", "") or "")
    )
    return payload


def degree_payload(trait) -> dict:
    payload = trait_payload(trait)
    payload["kind"] = "degree"
    return payload


def saved_relationship_payload(relationship, key_for_target: dict[int, str] | None = None) -> dict | None:
    key_for_target = key_for_target or {}
    target_key = key_for_target.get(getattr(relationship, "target_id", 0))
    if not target_key:
        return None
    tracks = {track.track_id: track.value for track in getattr(relationship, "track_values", [])}
    return {
        "target": target_key,
        "label": "Acquaintance",
        "friendship": int(round(tracks.get(16650, getattr(relationship, "value", 0.0) or 0.0))),
        "romance": int(round(tracks.get(16651, 0.0))),
        "bits": [
            {"id": bit, "label": name, "modded": False}
            for bit, name in zip(
                getattr(relationship, "bits", []) or [],
                getattr(relationship, "bit_names", []) or [],
            )
            if "should not be seen" not in (name or "").lower()
            and "dnt" not in (name or "").lower()
        ],
    }


def tray_sim_payload(sim, catalog, key: str, source_ref: str, household: str | None = None) -> dict:
    """Convert a Tray ``SavedSim`` (SDK) into the studio's sim payload."""
    household_name = household or getattr(sim, "household_name", None) or sim.last_name
    payload = {
        "key": key,
        "first": sim.first_name,
        "last": sim.last_name,
        "household": household_name,
        "household_key": f"tray:{source_ref}",
        "source": "tray",
        "source_ref": source_ref,
        "age": title_enum(getattr(sim, "age", None), AGE_LABELS, "Adult"),
        "gender": title_enum(getattr(sim, "gender", None), GENDER_LABELS, "Female"),
        "species": title_enum(getattr(sim, "species", None), SPECIES_LABELS, "Human"),
        "occult": ", ".join(getattr(sim, "occult", []) or []) or "Human",
        "traits": [
            trait_payload(trait)
            for trait in (getattr(sim, "visible_traits", None) or getattr(sim, "traits", []))
        ],
        "likes": [preference_payload(pref) for pref in getattr(sim, "likes", [])],
        "dislikes": [preference_payload(pref) for pref in getattr(sim, "dislikes", [])],
        "degrees": [],
        "skills": [skill_payload(skill, catalog) for skill in getattr(sim, "skills", [])],
        "career": None,
        "career_history": [],
        "aspiration": None,
        "aspiration_track": None,
        "milestones": [],
        "relationships": [],
        "family": [],
        "data_quality": "full",
        "sim_id": getattr(sim, "sim_id", None),
    }

    careers = [career_payload_from_saved(career) for career in getattr(sim, "careers", []) or []]
    careers.sort(key=lambda item: item.get("level", 0), reverse=True)
    payload["career"] = careers[0] if careers else None
    payload["career_history"] = careers[1:]

    track = getattr(sim, "aspiration_track", None)
    if track is not None:
        payload["aspiration_track"] = getattr(track, "display_name", None) or pretty(track.name)
        # A save stores the track only; the specific aspiration is not encoded.
    payload["milestones"] = [
        milestone
        for milestone in (milestone_payload(item.milestone) for item in getattr(sim, "milestones", []))
        if milestone
    ]
    payload["occult"] = (
        payload["occult"].split(",")[0].strip().title()
        if payload["occult"] == payload["occult"].upper()
        else payload["occult"]
    )
    return payload


def _degree_traits(sim) -> list[dict]:
    out = []
    for trait in getattr(sim, "traits", []) or []:
        if (getattr(trait, "name", "") or "").lower().startswith("trait_university_"):
            out.append(degree_payload(trait))
    return out


def saved_sim_payload(sim, catalog, key: str, source_ref: str, household: str | None = None) -> dict:
    """Convert a live-save ``SavedSim`` (SDK) into the studio's sim payload."""
    household_name = household or getattr(sim, "household_name", None) or sim.last_name
    payload = tray_sim_payload(sim, catalog, key, source_ref, household_name)
    payload["source"] = "save"
    payload["household_key"] = f"save:{source_ref}"
    payload["data_quality"] = "full"
    payload["degrees"] = _degree_traits(sim)
    return payload


def premade_sim_payload(sim, catalog, key: str, household: str, source_ref: str) -> dict:
    """Convert a static ``PremadeSim`` (SDK) into the studio's sim payload."""
    payload = {
        "key": key,
        "first": sim.first_name,
        "last": sim.last_name,
        "household": household,
        "household_key": f"premade:{source_ref}",
        "source": "premade",
        "source_ref": source_ref,
        "age": title_enum(getattr(sim, "age", None), AGE_LABELS, "Adult"),
        "gender": title_enum(getattr(sim, "gender", None), GENDER_LABELS, "Female"),
        "species": title_enum(getattr(sim, "species", None), SPECIES_LABELS, "Human"),
        "occult": title_enum(getattr(sim, "occult", None), None, "Human"),
        "traits": [
            trait_payload(trait)
            for trait in (getattr(sim, "visible_traits", None) or getattr(sim, "traits", []))
        ],
        "likes": [preference_payload(pref) for pref in getattr(sim, "likes", [])],
        "dislikes": [preference_payload(pref) for pref in getattr(sim, "dislikes", [])],
        "degrees": _degree_traits(sim),
        "skills": [skill_payload(skill, catalog) for skill in getattr(sim, "skills", [])],
        "career": None,
        "career_history": [],
        "aspiration": aspiration_payload(getattr(sim, "aspiration", None)),
        "aspiration_track": (
            getattr(sim.aspiration_track, "display_name", None)
            if getattr(sim, "aspiration_track", None) is not None
            else None
        ),
        "milestones": [],
        "relationships": [],
        "family": [],
        "data_quality": "full",
        "sim_id": getattr(sim, "id", None),
        "game_dynasty": None,
    }

    career = career_payload(
        getattr(sim, "career", None),
        getattr(sim, "career_track", None),
        getattr(sim, "career_display_level", None) or getattr(sim, "career_track_level", None),
        label=getattr(getattr(sim, "career_track", None), "display_name", None),
    )
    if career:
        payload["career"] = career
        if getattr(sim, "career_track", None) is not None:
            payload["career_track"] = item_payload(sim.career_track, "career_tracks")
    if sim.pronouns:
        payload["pronouns"] = sim.pronouns
    return payload


def family_rows(sim_ids: dict[int, str], relations: Iterable[tuple[int, str]]) -> list[dict]:
    rows = []
    for target_id, relation in relations:
        target = sim_ids.get(target_id)
        if target:
            rows.append({"target": target, "relation": relation})
    return rows
