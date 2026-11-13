"""Build the clean-save premade world from the bundled SimsDataSDK.

The SDK now exposes both the static ``PremadeBundle`` and every decoded
``0xB3C438F0`` household resource through ``StaticData.world``.  This module
converts those models into the studio's household JSON.

The SDK resolves localized member names; this module combines its models with
studio-specific display rules and supplemental premade datasets.

Nothing here writes to the game install.  The result is cached in
``backend/premade_world_complete.json``.
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable, Iterable

from . import sdk
from .catalog import _display_label, pretty
from .sdkconvert import (
    AGE_LABELS,
    GENDER_LABELS,
    SPECIES_LABELS,
    milestone_payload,
    title_enum,
)
from .settings import APP_DIR, PACK_NAMES
from .skillcurve import level_for_skill

COMPLETE_FILE = APP_DIR / "backend" / "premade_world_complete.json"

DYNASTY_TUNING: list[dict] | None = None
LEGACY_ANCESTORS: dict[str, dict] | None = None

BIT_LABELS = {
    "romantic_FirstKiss": "First kiss",
    "romantic-HaveDoneWooHoo": "WooHoo",
    "romantic-Significant_Other": "Partner",
    "living_roommate": "Roommate",
    "friendship-bff": "Best friends",
    "friendship-good_friends": "Good friends",
    "friendship-friend": "Friends",
    "friendship-acquaintances": "Acquaintances",
    "friendship-disliked": "Disliked",
    "relbit_SocialContext_Romance_Amorous": "Amorous",
    "relbit_SocialContext_Romance_Steamy": "Steamy",
    "relbit_SocialContext_Friendship_Friendly": "Friendly",
}

FAMILY_KIND_LABELS = {
    "MOTHER": "Mother",
    "FATHER": "Father",
    "PARENT": "Parent",
    "SECRET_PARENT": "Parent",
    "CHILD": "Child",
    "SIBLING": "Sibling",
    "GRANDPARENT": "Grandparent",
    "GRANDCHILD": "Grandchild",
    "PARENTS_SIBLING": "Parent's Sibling",
    "SIBLINGS_CHILDREN": "Sibling's Child",
    "COUSIN": "Cousin",
    "STEP_SIBLING": "Step-Sibling",
    "ADOPTED_BY": "Parent",
    "ADOPTED": "Child",
    "MOTHERS_MOM": "Mother's Mother",
    "MOTHERS_FATHER": "Mother's Father",
    "FATHERS_MOM": "Father's Mother",
    "FATHERS_FATHER": "Father's Father",
    "GREAT_GRANDPARENT": "Great Grandparent",
    "GREAT_GRANDCHILD": "Great Grandchild",
}


# ------------------------------------------------------------------ helpers
def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _legacy_ancestor_details() -> dict[str, dict]:
    """Full-name -> legacy ancestor row (titles/regions) from the bundled data."""
    global LEGACY_ANCESTORS
    if LEGACY_ANCESTORS is not None:
        return LEGACY_ANCESTORS
    rows: dict[str, dict] = {}
    try:
        payload = json.loads((APP_DIR / "data" / "premade_dynasties.json").read_text(encoding="utf-8"))
        for row in payload.get("ancestors", []):
            name = row.get("sim") or ""
            if name:
                rows[_norm(name)] = row
    except (OSError, ValueError):
        pass
    LEGACY_ANCESTORS = rows
    return rows


def _family_link_rows(premade) -> list[dict]:
    """Convert the SDK's typed kinship links into studio ``family`` rows."""
    rows: dict[tuple[int, str], dict] = {}
    for attr in (
        "parent_links",
        "child_links",
        "sibling_links",
        "extended_family_links",
        "unlinked_relations",
    ):
        for link in getattr(premade, attr, []) or []:
            target = link.sim_id or link.target_id
            if not target or getattr(link, "target_kind", "sim") == "ancestor":
                continue
            relation = FAMILY_KIND_LABELS.get(
                (link.kind or "").upper(),
                (link.kind or "Relative").replace("_", " ").title(),
            )
            rows.setdefault((target, relation), {"target_id": target, "relation": relation, "from_game": True})
    return list(rows.values())


def _ancestor_rows(bundle, premade, catalog) -> list[dict]:
    """Ancestors connected to this Sim's family tree, enriched with legacy titles."""
    try:
        tree = bundle.family_tree(premade)
    except Exception:
        tree = None
    if tree is None:
        return []
    legacy = _legacy_ancestor_details()
    rows: dict[str, dict] = {}
    for node in tree.ancestors_of():
        if node.kind != "ancestor":
            continue
        detail = legacy.get(_norm(node.full_name))
        if detail:
            row = dict(detail)
        else:
            death = None
            trait = catalog.traits.get(node.death_trait_id) if node.death_trait_id else None
            if trait is not None:
                death = trait.display_name
            surname = (node.full_name or "").split()[-1] if node.full_name else ""
            row = {
                "sim": node.full_name,
                "surname": surname,
                "gender": node.gender,
                "death": death,
                "title": "",
                "region": "",
                "template": node.name,
            }
        row.setdefault("sim", node.full_name)
        row.setdefault("surname", (node.full_name or "").split()[-1] if node.full_name else "")
        rows.setdefault(row["sim"], row)
    return list(rows.values())


def dynasty_tuning() -> list[dict]:
    """Dynasty seeds as defined by the game, with legacy descriptions if present."""
    global DYNASTY_TUNING
    if DYNASTY_TUNING is not None:
        return DYNASTY_TUNING
    descriptions = {}
    try:
        payload = json.loads((APP_DIR / "data" / "premade_dynasties.json").read_text(encoding="utf-8"))
        for row in payload.get("dynasties", []):
            name = (row.get("name") or "").replace(" dynasty", "").strip()
            if name:
                descriptions[name.lower()] = row.get("description", "")
    except (OSError, ValueError):
        pass

    found: dict[str, dict] = {}
    catalog = sdk.catalog()
    if catalog is not None:
        for tuning_id, name in catalog.tuning_names.items():
            low = (name or "").lower()
            if not low.startswith("dynastyseed_"):
                continue
            label = name.split("_", 1)[1]
            found[label.lower()] = {
                "id": name,
                "name": label,
                "description": descriptions.get(label.lower(), ""),
            }
    DYNASTY_TUNING = list(found.values())
    return DYNASTY_TUNING


# ------------------------------------------------------------------- merging
def _display_household(name: str) -> str:
    raw = (name or "").strip()
    low = raw.lower()
    if "test" in low or raw.startswith("ep3testhousehold"):
        return ""
    for prefix in ("premadeHouseholdTemplate_", "HH_Template_", "hH_Template_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    parts = [part for part in raw.split("_") if part]
    if parts and re.fullmatch(r"(?i)(ep|gp|sp|fp)\d+", parts[0]):
        parts = parts[1:]
    if parts and parts[-1].lower() == "townie" and len(parts) > 1:
        family = parts[-2]
        return f"{re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', family)} (Townie)"
    label = parts[-1] if parts else raw
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).strip()


def _trait_kind(catalog, trait_id: int) -> tuple[str, object]:
    trait = catalog.traits.get(trait_id)
    if trait is not None:
        if (trait.name or "").lower().startswith("trait_simpreference"):
            return "preference", trait
        return "trait", trait
    preference = catalog.preferences.get(trait_id)
    if preference is not None:
        return "preference", preference
    return "", None


def _reference(item, label: str | None = None) -> dict:
    name = getattr(item, "name", "") or ""
    display = label or getattr(item, "display_name", None) or pretty(name)
    source = getattr(item, "source", None)
    pack_code = (getattr(source, "pack", "") or "").upper() if source else ""
    pack_code = "Base" if pack_code == "BASE" else pack_code
    pack = "Mod" if getattr(source, "is_mod", False) else PACK_NAMES.get(pack_code, pack_code)
    return {
        "id": getattr(item, "id", 0) or 0,
        "label": display,
        "modded": getattr(source, "is_mod", False),
        "pack": pack,
        "tuning": name,
        "trait_type": getattr(item, "trait_type", ""),
    }


def _is_internal_trait(model) -> bool:
    if getattr(model, "is_internal", False):
        return True
    low = (getattr(model, "name", "") or "").lower()
    return low.startswith(
        (
            "trait_gender", "trait_species", "trait_occult", "trait_handedness",
            "trait_reputation", "trait_hidden", "trait_walkstyle", "trait_cas_",
            "trait_is", "trait_npc", "trait_service", "trait_debug",
        )
    )


def _merge_trait_ids(catalog, ids: Iterable[int]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    traits, likes, dislikes, degrees = [], [], [], []
    seen: set[int] = set()
    for trait_id in ids:
        if trait_id in seen:
            continue
        seen.add(trait_id)
        kind, item = _trait_kind(catalog, trait_id)
        if item is None:
            continue
        name = getattr(item, "name", "") or ""
        if kind == "preference":
            row = _reference(item)
            if getattr(item, "is_dislike", False) or "dislike" in name.lower():
                dislikes.append(row)
            else:
                likes.append(row)
            continue
        low = name.lower()
        if low.startswith("trait_university_"):
            degrees.append(_reference(item))
            continue
        if _is_internal_trait(item):
            continue
        traits.append(_reference(item))
    return traits, likes, dislikes, degrees


def _merge_skills(catalog, premade_skills, world_skills) -> list[dict]:
    rows: dict[int, dict] = {}
    for skill in premade_skills or []:
        # Starter-save templates seed every skill at the 100 XP floor; only a
        # higher value or an explicit level above 1 is a real starting skill.
        if skill.value is not None and float(skill.value) <= 100 and (skill.level is None or skill.level <= 1):
            continue
        name = catalog.tuning_names.get(skill.skill_id, "") if catalog else ""
        if not name:
            name = skill.skill_name or ""
        label = pretty(name[len("skill_"):]) if name.lower().startswith("skill_") else pretty(name)
        level = skill.level
        if level is None and skill.value is not None:
            level = level_for_skill(float(skill.value), skill.skill_id, name, catalog)
        rows[skill.skill_id] = {
            "id": skill.skill_id,
            "label": label if name else f"Skill {skill.skill_id}",
            "tuning": name,
            "modded": False,
            "pack": "",
            "level": level,
        }
        if skill.value is not None:
            rows[skill.skill_id]["xp"] = round(float(skill.value), 1)
    for skill_id, value in world_skills or []:
        if skill_id in rows:
            continue
        if float(value or 0) <= 100:
            continue
        name = catalog.tuning_names.get(skill_id, "") if catalog else ""
        label = pretty(name[len("skill_"):]) if name.lower().startswith("skill_") else pretty(name)
        rows[skill_id] = {
            "id": skill_id,
            "label": label if name else f"Skill {skill_id}",
            "tuning": name,
            "modded": False,
            "pack": "",
            "xp": round(float(value), 1),
            "level": level_for_skill(float(value), skill_id, name, catalog),
        }
    return list(rows.values())


def _merge_career(catalog, premade, world_member) -> tuple[dict | None, dict | None]:
    career_id = getattr(premade, "career_id", None) or getattr(world_member, "career_id", None)
    track_id = getattr(premade, "career_track_id", None) or getattr(world_member, "career_track_id", None)
    if not career_id and not track_id:
        return None, None
    career = catalog.careers.get(career_id) if catalog and career_id else None
    track = catalog.career_tracks.get(track_id) if catalog and track_id else None
    level = (
        getattr(premade, "career_display_level", None)
        or getattr(world_member, "career_display_level", None)
        or getattr(premade, "career_track_level", None)
        or 1
    )
    label = (
        getattr(career, "display_name", None)
        if career is not None
        else None
    ) or (
        getattr(track, "display_name", None)
        if track is not None
        else pretty(getattr(career, "name", "") or "")
    )
    payload = {
        "id": career_id or track_id,
        "label": label,
        "modded": False,
        "pack": "",
        "tuning": getattr(career, "name", "") if career is not None else "",
        "trait_type": "",
        "level": int(level),
    }
    if track_id:
        payload["track_uid"] = track_id
    track_payload = None
    if track is not None:
        track_payload = {
            "id": track.id,
            "label": track.display_name or pretty(track.name),
            "modded": False,
            "pack": "",
            "tuning": track.name,
        }
    return payload, track_payload


def _merge_aspiration(catalog, premade, world_member) -> tuple[dict | None, str | None]:
    aspiration = getattr(premade, "aspiration", None)
    track = getattr(premade, "aspiration_track", None)
    if aspiration is None and track is None and getattr(world_member, "aspiration_track_id", None):
        track = catalog.aspiration_tracks.get(world_member.aspiration_track_id) if catalog else None
    if aspiration is not None:
        return _reference(aspiration), None
    if track is not None:
        label = _display_label("aspiration_tracks", track.name)
        return {"id": track.id, "label": label, "modded": False, "pack": "", "tuning": track.name, "track": True}, label
    return None, None


def _bit_rows(catalog, bit_ids: Iterable[int]) -> list[dict]:
    rows: dict[str, dict] = {}
    for bit_id in bit_ids or []:
        bit = catalog.relationship_bits.get(bit_id) if catalog else None
        name = getattr(bit, "name", "") or (catalog.tuning_names.get(bit_id, "") if catalog else "")
        label = BIT_LABELS.get(name) or getattr(bit, "display_name", None) or pretty(name) or f"Bit {bit_id}"
        if "should not be seen" in label.lower() or "dnt" in label.lower():
            continue
        rows.setdefault(label, {"id": bit_id, "label": label, "modded": False})
    return list(rows.values())


def _relationship_label(catalog, bit_ids, friendship: int, romance: int) -> str:
    names = " ".join(
        ((catalog.tuning_names.get(bit_id, "") if catalog else "") or "").lower()
        for bit_id in bit_ids or []
    )
    if "romanticcombo_lovebirds" in names or "soulmates" in names:
        return "Lovebirds"
    if "romanticcombo_lovers" in names:
        return "Lovers"
    if "friendship-bff" in names:
        return "Best friends"
    if "friendship-disliked" in names:
        return "Disliked"
    if romance >= 60:
        return "Partner"
    if friendship >= 80:
        return "Best friend"
    if friendship >= 60:
        return "Friend"
    if friendship >= 30:
        return "Acquaintance"
    if friendship < 0:
        return "Disliked"
    return "Household member"


def _world_relationship_rows(catalog, member) -> list[dict]:
    rows = []
    for relationship in getattr(member, "relationships", []) or []:
        tracks = {track.track_id: track.value for track in relationship.track_values}
        friendship = int(round(tracks.get(16650, relationship.value or 0)))
        romance = int(round(tracks.get(16651, 0)))
        rows.append(
            {
                "target_id": relationship.target_id,
                "label": _relationship_label(catalog, relationship.bits, friendship, romance),
                "friendship": friendship,
                "romance": romance,
                "bits": _bit_rows(catalog, relationship.bits),
                "from_game": True,
            }
        )
    return rows


def _world_milestone_rows(catalog, member) -> list[dict]:
    rows = []
    for entry in getattr(member, "milestones", []) or []:
        model = getattr(entry, "milestone", None) or (
            catalog.milestones.get(entry.milestone_id) if catalog else None
        )
        if model is not None:
            payload = milestone_payload(model)
        else:
            payload = {"id": entry.milestone_id, "label": f"Milestone {entry.milestone_id}", "modded": False}
        if payload and not any(row.get("id") == payload["id"] for row in rows):
            rows.append(payload)
    return rows


def _build_sim(catalog, premade, world_member, household_name, dynasty_name) -> tuple[dict, int | None]:
    trait_ids = [trait.id for trait in getattr(premade, "traits", [])]
    if world_member is not None:
        trait_ids.extend(world_member.trait_ids or [])
    traits, likes, dislikes, degrees = _merge_trait_ids(catalog, trait_ids)
    if premade is not None:
        for preference in getattr(premade, "preferences", []) or []:
            row = _reference(preference)
            if getattr(preference, "is_dislike", False):
                dislikes.append(row)
            else:
                likes.append(row)
        likes = list({row["id"]: row for row in likes}.values())
        dislikes = list({row["id"]: row for row in dislikes}.values())

    career, career_track = _merge_career(catalog, premade, world_member)
    aspiration, aspiration_track = _merge_aspiration(catalog, premade, world_member)
    skills = _merge_skills(
        catalog,
        getattr(premade, "skills", None),
        getattr(world_member, "skills", None),
    )

    sim_id = getattr(world_member, "sim_id", None) or getattr(premade, "id", None)
    species = getattr(premade, "species", None) if premade is not None else None
    if not species:
        for trait_id in trait_ids:
            name = catalog.tuning_names.get(trait_id, "") if catalog else ""
            if name.lower().startswith("trait_species_"):
                species = name[len("trait_species_"):]
                break
    gender = getattr(premade, "gender", None) or getattr(world_member, "gender", None)
    age = getattr(premade, "age", None) or getattr(world_member, "age", None)
    occult_values = [
        value for value in (getattr(world_member, "occult", None) or [])
        if value and value.upper() != "HUMAN"
    ]
    occult = getattr(premade, "occult", None) or (occult_values[0] if occult_values else None)

    rows = {
        "sim_id": sim_id,
        "first": getattr(premade, "first_name", None) or (world_member.first_name if world_member else ""),
        "last": getattr(premade, "last_name", None) or (world_member.last_name if world_member else ""),
        "traits": traits,
        "likes": likes,
        "dislikes": dislikes,
        "skills": skills,
        "careers": [career] if career else [],
        "career_history": [],
        "career": career,
        "career_track": career_track,
        "aspiration": aspiration,
        "aspiration_track": aspiration_track,
        "relationships": _world_relationship_rows(catalog, world_member) if world_member else [],
        "family": _family_link_rows(premade) if premade else [],
        "degrees": degrees,
        "milestones": _world_milestone_rows(catalog, world_member) if world_member else [],
        "occult": title_enum(occult, None, "Human") if occult else "Human",
        "significant_other": (
            getattr(premade, "spouse_id", None)
            or (getattr(world_member, "spouse_id", None) if world_member else None)
        ),
        "fiance": (
            getattr(premade, "fiance_id", None)
            or (getattr(world_member, "fiance_id", None) if world_member else None)
        ),
        "steady": list(
            getattr(premade, "steady_ids", None)
            or (getattr(world_member, "steady_ids", []) if world_member else [])
        ),
        "gender": title_enum(gender, GENDER_LABELS, "Female"),
        "age": title_enum(age, AGE_LABELS, "Adult"),
        "species": title_enum(species, SPECIES_LABELS, "Human"),
        "household": household_name,
        "game_dynasty": dynasty_name,
        "pronouns": getattr(premade, "pronouns", None),
    }
    return rows, sim_id


# ------------------------------------------------------------------- builder
def build_complete_dataset(progress: Callable[[str], None] | None = None) -> dict:
    started = time.time()
    static = sdk.static_data()
    if static is None:
        payload = {"households": [], "dynasties": [], "meta": {"error": "SimsDataSDK unavailable"}}
        COMPLETE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        return payload
    catalog = static.catalog
    bundle = static.premades
    world = getattr(static, "world", None)
    records = list(world.households.values()) if world is not None else []
    if world is not None:
        world.resolve_names(catalog.strings)

    # Match SDK tuning households to their 0xB3C438F0 resource by member names.
    record_by_members: dict[frozenset[str], object] = {}
    record_by_name: dict[str, object] = {}
    for record in records:
        key = frozenset(
            _norm(f"{member.first_name}{member.last_name}")
            for member in record.members
            if member.first_name
        )
        if key:
            record_by_members.setdefault(key, record)
        if record.name:
            record_by_name.setdefault(_norm(record.name), record)

    premade_by_id = {sim.id: sim for sim in bundle.sims}
    dynasty_names = {_norm(row["name"]): row["name"] for row in dynasty_tuning()}
    lots_by_id = {lot.id: lot for lot in bundle.lots}
    lots_by_household = {
        lot.household_id: lot for lot in bundle.lots if getattr(lot, "household_id", None)
    }

    households = []
    seen: set[tuple] = set()
    for household in bundle.households:
        member_names = frozenset(
            _norm(f"{premade_by_id[member.sim_template_id].first_name}{premade_by_id[member.sim_template_id].last_name}")
            for member in household.members
            if member.sim_template_id in premade_by_id
        )
        resource = record_by_members.get(member_names) or record_by_name.get(_norm(household.name))
        world_members = {
            _norm(f"{member.first_name}{member.last_name}"): member
            for member in (resource.members if resource else [])
        }

        display = (
            getattr(household, "localized_name", None)
            or _display_household(household.name)
            or getattr(household, "display_name", None)
            or household.name
        )
        if not display or "test" in household.name.lower() or "test" in display.lower():
            continue

        dynasty = ""
        for member in household.members:
            sim = premade_by_id.get(member.sim_template_id)
            seed = (getattr(sim, "dynasty", {}) or {}).get("seed") if sim is not None else None
            if seed:
                seed_name = catalog.tuning_names.get(seed, "")
                label = seed_name.split("_", 1)[1] if "_" in seed_name else ""
                if label:
                    dynasty = dynasty_names.get(_norm(label), label)
                    break
        if dynasty and "townie" in household.name.lower():
            display = f"{dynasty} (Townie)"

        lot = lots_by_id.get(household.lot_id) if getattr(household, "lot_id", None) else None
        if lot is None:
            lot = lots_by_household.get(household.id)
        hh = {
            "name": display,
            "description": getattr(household, "description", None) or (lot.household_description if lot else ""),
            "money": household.funds if household.funds is not None else (resource.funds if resource else None),
            "id": resource.instance if resource else household.id,
            # Keep the 0xB3C438F0 resource instance as the project key so
            # existing projects and cached portraits stay valid.
            "template_id": resource.instance if resource else household.id,
            "lot": lot.lot_name if lot else "",
            "lot_description": lot.lot_description if lot else "",
            "template_kind": "premade" if household.name.startswith("premadeHouseholdTemplate_") else "additional",
            "game_dynasty": dynasty or None,
            "sims": [],
        }

        tag_to_id: dict[str, int] = {}
        for member in household.members:
            premade = premade_by_id.get(member.sim_template_id)
            if premade is None:
                continue
            world_member = world_members.get(_norm(f"{premade.first_name}{premade.last_name}"))
            sim_dynasty = None
            seed = (getattr(premade, "dynasty", {}) or {}).get("seed")
            if seed:
                seed_name = catalog.tuning_names.get(seed, "")
                label = seed_name.split("_", 1)[1] if "_" in seed_name else ""
                sim_dynasty = dynasty_names.get(_norm(label), label) if label else None
            sim, sim_id = _build_sim(catalog, premade, world_member, display, sim_dynasty)
            if not sim["first"]:
                continue
            sim["premade_id"] = premade.id
            ancestors = _ancestor_rows(bundle, premade, catalog)
            if ancestors:
                sim["ancestors"] = ancestors
            key_identity = (display.lower(), sim["first"].lower(), sim["last"].lower())
            if key_identity in seen:
                continue
            seen.add(key_identity)
            sim["household_id"] = resource.instance if resource else household.id
            hh["sims"].append(sim)
            if sim_id:
                tag_to_id[member.tag] = sim_id

        if not hh["sims"]:
            continue

        # Household relationships from the SDK: spouse, parent/child and the
        # tuning's relationship bits (Roommate, BFF, Lovers, ...).
        for relationship in household.relationships:
            a_id = tag_to_id.get(relationship.a_tag)
            b_id = tag_to_id.get(relationship.b_tag)
            if not a_id or not b_id:
                continue
            bits = _bit_rows(catalog, relationship.bit_ids)
            if relationship.kind == "spouse":
                _add_relationship(hh["sims"], a_id, b_id, "Spouse", relationship.friendship or 45, relationship.romance or 75, bits)
                _add_relationship(hh["sims"], b_id, a_id, "Spouse", relationship.friendship or 45, relationship.romance or 75, bits)
            elif relationship.kind == "family":
                relation = (relationship.family_relationship or "PARENT").title()
                _add_family(hh["sims"], b_id, a_id, relation)
            else:
                _add_relationship(hh["sims"], a_id, b_id, "Household member", 45, 0, bits)
                _add_relationship(hh["sims"], b_id, a_id, "Household member", 45, 0, bits)

        households.append(hh)

    _remap_premade_ids(households)
    _apply_sdk_premade_relationships(catalog, bundle, households)

    payload = {
        "households": households,
        "dynasties": dynasty_tuning(),
        "meta": {
            "built": time.time(),
            "seconds": round(time.time() - started, 2),
            "households": len(households),
            "sims": sum(len(h["sims"]) for h in households),
            "likes": sum(len(s.get("likes", [])) for h in households for s in h["sims"]),
            "dislikes": sum(len(s.get("dislikes", [])) for h in households for s in h["sims"]),
            "skills": sum(len(s.get("skills", [])) for h in households for s in h["sims"]),
            "relationship_bits": sum(
                len(r.get("bits", [])) for h in households for s in h["sims"] for r in s.get("relationships", [])
            ),
            "premade_relationships": len(bundle.premade_relationships),
            "household_resources": len(records),
            "sdk_diagnostics": len(getattr(world, "diagnostics", []) or []),
            "sdk": True,
        },
    }
    try:
        COMPLETE_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return payload


# ------------------------------------------------------------------ relations
def _find_sim(sims: list[dict], sim_id: int) -> dict | None:
    return next((sim for sim in sims if sim.get("sim_id") == sim_id), None)


def _add_relationship(sims, a_id, b_id, label, friendship, romance, bits) -> None:
    a = _find_sim(sims, a_id)
    b = _find_sim(sims, b_id)
    if not a or not b or a is b:
        return
    row = next((r for r in a.setdefault("relationships", []) if r.get("target_id") == b_id), None)
    if row is None:
        a["relationships"].append(
            {
                "target_id": b_id,
                "label": label,
                "friendship": int(friendship or 0),
                "romance": int(romance or 0),
                "bits": list(bits or []),
                "from_game": True,
            }
        )
    else:
        if bits:
            have = {bit.get("id") for bit in row.get("bits", [])}
            row.setdefault("bits", []).extend(bit for bit in bits if bit.get("id") not in have)
        if row.get("label") in (None, "", "Household member") and label:
            row["label"] = label
        if friendship is not None and not row.get("friendship"):
            row["friendship"] = int(friendship)
        if romance is not None and not row.get("romance"):
            row["romance"] = int(romance)


def _add_family(sims, child_id, parent_id, relation) -> None:
    child = _find_sim(sims, child_id)
    if not child:
        return
    if not any(row.get("target_id") == parent_id for row in child.setdefault("family", [])):
        child["family"].append({"target_id": parent_id, "relation": relation, "from_game": True})


def _remap_premade_ids(households: list[dict]) -> None:
    """Map SDK ``PremadeSim.id`` references to the household-resource Sim IDs.

    The typed family links and spouse/fiancé/steady fields use the tuning
    instance ID, while the studio's project keys use the ``0xB3C438F0`` member
    ID.  Both refer to the same Sim; convert the references once all payloads
    have been built.
    """
    sims = households_sims(households)
    id_map = {
        sim.get("premade_id"): sim.get("sim_id")
        for sim in sims
        if sim.get("premade_id") and sim.get("sim_id")
    }
    if not id_map:
        return

    def convert(value):
        return id_map.get(value, value)

    for sim in sims:
        for field in ("significant_other", "fiance"):
            if sim.get(field):
                sim[field] = convert(sim[field])
        if sim.get("steady"):
            sim["steady"] = [convert(value) for value in sim["steady"]]
        family = sim.get("family", []) or []
        for row in family:
            if row.get("target_id"):
                row["target_id"] = convert(row["target_id"])
        seen = set()
        deduped = []
        for row in family:
            key = (row.get("target_id"), row.get("relation"))
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        sim["family"] = deduped
        for row in sim.get("relationships", []) or []:
            if row.get("target_id"):
                row["target_id"] = convert(row["target_id"])


def _apply_sdk_premade_relationships(catalog, bundle, households) -> None:
    """Apply ``Catalog.premade_relationships`` (cross-household starting links)."""
    if not bundle.premade_relationships:
        return
    sims = households_sims(households)
    by_name = {
        _norm(f"{sim.get('first', '')}{sim.get('last', '')}"): sim
        for sim in sims
    }
    for relation in bundle.premade_relationships:
        a = by_name.get(_norm(relation.sim_a_name or ""))
        b = by_name.get(_norm(relation.sim_b_name or ""))
        if not a or not b or a is b:
            continue
        a_id, b_id = a.get("sim_id"), b.get("sim_id")
        tracks = {track.track_id: track.value for track in relation.tracks}
        friendship = int(round(tracks.get(16650, 0)))
        romance = int(round(tracks.get(16651, 0)))
        operation_bits = [op.bit_id for op in getattr(relation, "bit_operations", []) or []]
        bits = _bit_rows(catalog, [*relation.bit_ids, *operation_bits, *relation.sentiment_track_ids])
        label = _relationship_label(catalog, [*relation.bit_ids], friendship, romance)
        _add_relationship(sims, a_id, b_id, label, friendship, romance, bits)
        _add_relationship(sims, b_id, a_id, label, friendship, romance, bits)


def households_sims(households: list[dict]) -> list[dict]:
    return [sim for household in households for sim in household.get("sims", [])]


def load_complete_dataset() -> dict:
    if COMPLETE_FILE.exists():
        try:
            return json.loads(COMPLETE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return build_complete_dataset()


if __name__ == "__main__":
    print(json.dumps(build_complete_dataset(print)["meta"], indent=2))
