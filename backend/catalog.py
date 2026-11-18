"""
Builds a catalog of traits / skills / careers / aspirations / milestones /
preferences / relationship data from the user's own game + mods.

EA content lives in compiled "SimData" resources (type 0x545AC67A). Each
resource carries a schema, a class name and the tuning name as the last two
printable tokens, while the DBPF index gives us the tuning instance id.

Mods normally ship XML tuning. The resource type for XML tuning is the FNV-1
32 bit hash of the tuning class, and the tuning name (``n``) / instance
(``s``) are plain attributes.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Iterable

from . import sdk
from .dbpf import DBPF, DBPFError
from .settings import DATA_DIR, PACK_NAMES, paths

CACHE_FILE = DATA_DIR / "catalog_cache.json"
CACHE_VERSION = 34

#: Definition kinds the SDK's ``Catalog`` models directly.
SDK_KINDS = {
    "traits", "preferences", "aspirations", "aspiration_tracks", "careers",
    "career_tracks", "milestones", "relationship_bits",
}
#: Definition kinds the SDK does not model yet; the supplemental scanner still
#: reads these from SimData/XML tuning.  See docs/sdk-migration.md.
SUPPLEMENTAL_KINDS = {
    "skills", "degrees", "identity", "occults", "objectives", "relationship_tracks",
}

SIMDATA_TYPE = 0x545AC67A

TOKEN_RE = re.compile(rb"[\x20-\x7e]{2,90}")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,90}$")
CLASS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{1,60}$")

PREFIX_STRIP = (
    "statistic_Skill_",
    "statistic_",
    "trait_SimPreference_Likes_",
    "trait_SimPreference_Dislikes_",
    "trait_SimPreference_",
    "trait_",
    "careers_",
    "career_",
    "aspiration_",
    "milestone_",
    "buff_",
    "loot_",
    "reward_",
    "relationshipBit_",
    "sentimentBit_",
    "rbc_",
    "occult_",
    "Occult_",
    "preferenceItem_",
    "client_CASOccultTuning_",
)

DISPLAY_BLOCKLIST = {
    "DATA",
    "None",
    "True",
    "False",
    "Trait",
    "Buff",
    "Skill",
    "Career",
    "Aspiration",
    "Milestone",
    "Preference",
    "LootActions",
    "TunableCareerTrack",
    "RelationshipBit",
    "OccultTrackerItem",
}


def fnv1_32(text: str) -> int:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= byte
    return h


def pretty(tuning: str) -> str:
    value = tuning
    lower = value.lower()
    for prefix in PREFIX_STRIP:
        if lower.startswith(prefix.lower()):
            value = value[len(prefix):]
            break
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value).strip()
    for lead in ("Adult Major ", "Adult Minor ", "Adult "):
        if value.startswith(lead) and len(value) > len(lead) + 2:
            value = value[len(lead):]
            break
    if not value:
        return tuning
    value = value.replace(" RnB", " R&B").replace("Rnb", "R&B")
    return " ".join(part if part.isupper() else part[:1].upper() + part[1:] for part in value.split())


def _pack_from_path(path: Path) -> str:
    parts = [p.upper() for p in path.parts]
    for part in parts:
        if part in PACK_NAMES:
            return part
    return "Base"


def _game_packages() -> list[Path]:
    if not paths.game:
        return []
    root = paths.game
    found: list[Path] = []
    data_sim = root / "Data" / "Simulation"
    for name in ("SimulationDeltaBuild0.package", "SimulationFullBuild0.package"):
        p = data_sim / name
        if p.exists():
            found.append(p)

    delta = root / "Delta"
    if delta.is_dir():
        for child in sorted(delta.iterdir()):
            if child.is_dir():
                p = child / "SimulationDeltaBuild0.package"
                if p.exists():
                    found.append(p)

    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name.upper() in PACK_NAMES:
            p = child / "SimulationFullBuild0.package"
            if p.exists():
                found.append(p)
    return found


INTERNAL_TRAIT_PREFIXES = (
    "trait_hidden",
    "trait_genderoptions",
    "trait_noblefavor",
    "trait_noblecareer_exrank",
    "trait_masteryperk",
    "trait_magic_fixups",
    "trait_ghost",
    "trait_occultmermaid",
    "trait_occultfairytyae",
    "trait_occultwerewolfhad",
    "trait_occultwerewolfimmortal",
    "trait_occultwerewolfnatural",
    "trait_occultwerewolftemperament",
    "trait_occultwerewolfinitiation",
    "trait_isburglar",
    "trait_isrobinhood",
    "trait_ispremadepo",
    "trait_isschoolghost",
    "trait_introtovampire",
    "trait_werewolfpack",
    "trait_gradeschool",
    "trait_hsexit",
    "trait_dynasty",
    "trait_witchoccultperk",
    "trait_reputation",
    "trait_simreputation",
    "trait_sim_reputation",
    "trait_relexpectations",
    "trait_sexualorientation",
    "trait_handedness",
    "trait_walkstyle",
    "trait_iscustomgender",
    "trait_umbrella",
    "trait_lifestyles",
    "trait_cas_",
    "trait_natethel0ser",
    "trait_species",
    "trait_occult_",
    "trait_gender_",
    "trait_human_",
    "trait_npc",
    "trait_service",
    "trait_debug",
)

ASPIRATION_NAMES = {
    "aspiration_Popularity_A1": "Friend of the World",
    "aspiration_Popularity_B1": "Party Animal",
    "aspiration_Popularity_C1": "Neighborhood Confidante",
    "aspiration_Knowledge_A1": "Renaissance Sim",
    "aspiration_Knowledge_B1": "Computer Whiz",
    "aspiration_Knowledge_C1": "Nerd Brain",
    "aspiration_Fortune_A1": "Fabulously Wealthy",
    "aspiration_Fortune_B1": "Mansion Baron",
    "aspiration_Fortune_C1": "Business Savvy",
    "aspiration_Family_A1": "Successful Lineage",
    "aspiration_Family_B1": "Big Happy Family",
    "aspiration_Family_C1": "Super Parent",
    "aspiration_Love_A1": "Soulmate",
    "aspiration_Love_B1": "Serial Romantic",
    "aspiration_Love_C1": "Player",
    "aspiration_Romance_A1": "Soulmate",
    "aspiration_Romance_B1": "Serial Romantic",
    "aspiration_Romance_C1": "Player",
    "aspiration_Creativity_A1": "Painter Extraordinaire",
    "aspiration_Creativity_B1": "Bestselling Author",
    "aspiration_Creativity_C1": "Musical Genius",
    "aspiration_Athletic_A1": "Bodybuilder",
    "aspiration_Athletic_B1": "Fitness Nut",
    "aspiration_Nature_A1": "Freelance Botanist",
    "aspiration_Nature_B1": "The Curator",
    "aspiration_Nature_C1": "Angling Ace",
    "aspiration_Food_A1": "Master Chef",
    "aspiration_Food_B1": "Master Mixologist",
    "aspiration_Deviance_A1": "Public Enemy",
    "aspiration_Deviance_B1": "Chief of Mischief",
    "aspiration_Deviance_C1": "Sleight of Hand",
}

AGE_HINT_WORDS = (
    ("toddler", "Toddler"),
    ("infant", "Infant"),
    ("child", "Child"),
    ("teen", "Teen"),
    ("elder", "Elder"),
)

SPECIES_WORDS = {
    "horse": "Horse",
    "cat": "Cat",
    "dog": "Dog",
    "fox": "Fox",
    "raccoon": "Raccoon",
    "chicken": "Chicken",
    "llama": "Llama",
    "goat": "Goat",
    "sheep": "Sheep",
}

OCCULT_WORDS = {
    "vampire": "Vampire",
    "werewolf": "Werewolf",
    "mermaid": "Mermaid",
    "spellcaster": "Spellcaster",
    "witch": "Spellcaster",
    "alien": "Alien",
    "plantsim": "PlantSim",
    "fairy": "Fairy",
    "ghost": "Ghost",
    "servo": "Servo",
}

INTERNAL_TRAIT_TOKENS = {
    "hidden",
    "npc",
    "scenario",
    "quest",
    "identifier",
    "walkstyle",
    "animalclothing",
    "quirk",
    "competition",
    "gameplay",
    "ftue",
    "debug",
    "test",
    "default",
    "fear",
    "age",
    "mission",
    "missions",
    "reputation",
    "scenario",
    "quest",
    "npc",
    "tracker",
    "track",
    "object",
    "buff",
    "stat",
    "force",
    "attraction",
    "daycare",
    "bonehilda",
    "breasts",
    "tier",
    "smallbusiness",
    "trait_tracker",
}


def _name_parts(name: str) -> list[str]:
    return [p for p in re.split(r"[_\s]+", name) if p]


def _age_hint(name: str, label: str = "") -> str | None:
    parts = [p.lower() for p in _name_parts(name)]
    for word, age in AGE_HINT_WORDS:
        if word in parts:
            return age
    return None


def _species_hint(name: str) -> str | None:
    parts = [p.lower() for p in _name_parts(name)]
    for word, species in SPECIES_WORDS.items():
        if word in parts or f"{word}s" in parts:
            if word in ("cat", "dog") and "lover" in parts:
                continue
            return species
    return None


def _occult_hint(name: str) -> str | None:
    parts = [p.lower() for p in _name_parts(name)]
    for word, occult in OCCULT_WORDS.items():
        if word in parts:
            return occult
    return None


def _is_internal_trait(name: str) -> bool:
    parts = [p.lower() for p in _name_parts(name)]
    return any(token in part for part in parts for token in INTERNAL_TRAIT_TOKENS)


def _aspiration_tier(name: str) -> int | None:
    match = re.search(r"_(?:A|B|C|D|Level)(\d+)$", name)
    return int(match.group(1)) if match else None


def _classify(name: str, cls: str) -> str | None:
    low = name.lower()
    if "trait" in cls.lower() and low.startswith("trait_"):
        if low.startswith("trait_simpreference"):
            return "preferences"
        if low.startswith("trait_university_"):
            return "degrees"
        if low in (
            "trait_adult",
            "trait_teen",
            "trait_youngadult",
            "trait_child",
            "trait_toddler",
            "trait_infant",
            "trait_baby",
            "trait_elder",
        ) or low.startswith(("trait_gender_", "trait_species_", "trait_occult_")):
            return "identity"
        if "hidden" in low or low.startswith(INTERNAL_TRAIT_PREFIXES):
            return None
        if _is_internal_trait(name):
            return None
        return "traits"
    if cls == "Skill" and (low.startswith("statistic_skill") or low.startswith("skill_")):
        return "skills"
    if cls == "Career" and (low.startswith("career_") or low.startswith("careers_")):
        return "careers"
    if cls == "TunableCareerTrack":
        return "career_tracks"
    if cls == "Aspiration" and low.startswith("aspiration_"):
        tier = _aspiration_tier(name)
        if tier is not None and tier > 1:
            return None
        return "aspirations"
    if cls == "AspirationTrack":
        return "aspiration_tracks"
    if cls == "Objective" and low.startswith("objective_"):
        return "objectives"
    if cls in ("Milestone", "DevelopmentalMilestone") and "milestone" in low:
        return "milestones"
    if cls == "Preference":
        return "preferences"
    if cls == "RelationshipBit":
        return "relationship_bits"
    if cls in ("RelationshipTrack", "ShortTermContextRelationshipTrack", "ObjectRelationshipTrack"):
        return "relationship_tracks"
    if "occult" in low and "occult" in cls.lower() and "skintone" not in low:
        if "occulttrait" in cls.lower() or cls == "OccultTrackerItem":
            return "occults"
    if low.startswith("milestone_") and "infant" in low:
        return "milestones"
    return None


def _display_label(kind: str, name: str) -> str:
    if kind == "aspiration_tracks":
        label = pretty(name).replace("Track ", "")
        label = re.sub(r"\bEP\d+\s+Asp\s+", "", label)
        label = re.sub(r"\bAsp\s+", "", label)
        return label
    if kind == "aspirations":
        if name in ASPIRATION_NAMES:
            return ASPIRATION_NAMES[name]
        label = re.sub(r"\s+(?:A|B|C|D)[1-4]$", "", pretty(name))
        label = re.sub(r"\s+Level\s*1$", "", label)
        label = re.sub(r"\bEP\d+\s+Asp\s+", "", label)
        label = re.sub(r"\bEP\d+\s+", "", label)
        label = re.sub(r"\bAsp\s+", "", label)
        return label
    if kind == "skills":
        game_names = {
            "statistic_skill_hidden_vampirelore": "Vampire Lore",
            "statistic_skill_ranchnectar": "Nectar Making",
            "statistic_skill_dogtraining": "Pet Training",
            "statistic_skill_divingboard": "Diving",
            "statistic_skill_researchdebate": "Research & Debate",
            "statistic_skill_toddler_potty": "Potty",
        }
        if name.lower() in game_names:
            return game_names[name.lower()]
        if name.lower().startswith("skill_"):
            return pretty(name[len("skill_"):])
    if kind == "degrees":
        label = pretty(name).replace("University ", "")
        label = label.replace(" Degree", "")
        label = label.replace("BAHonors", "BA Honors").replace("BSHonors", "BS Honors")
        return label
    if kind == "preferences":
        label = pretty(name)
        if "Dislikes" in name:
            return "Dislikes " + label
        if "Likes" in name:
            return "Likes " + label
        return label
    return pretty(name)


def _scan_simdata_package(path: Path, add, wanted: set[str] | None = None) -> None:
    try:
        package = DBPF(path)
    except (DBPFError, OSError):
        return
    pack = _pack_from_path(path)
    for entry, data in package.iter_type(SIMDATA_TYPE):
        if not data or len(data) > 260_000:
            continue
        tokens = [t.decode("ascii") for t in TOKEN_RE.findall(data)]
        if len(tokens) < 3:
            continue
        name = tokens[-1]
        cls = tokens[-2]
        if "AspirationTrack" in tokens:
            cls = "AspirationTrack"
        if not NAME_RE.match(name) or not CLASS_RE.match(cls):
            continue
        kind = _classify(name, cls)
        if not kind:
            continue
        if wanted is not None and kind not in wanted:
            continue
        add(
            {
                "kind": kind,
                "id": entry.instance,
                "tuning": name,
                "class": cls,
                "label": _display_label(kind, name),
                "pack": pack,
                "pack_label": PACK_NAMES.get(pack, pack),
                "modded": False,
                "source": str(path),
                "age_hint": _age_hint(name, cls),
                "species_hint": _species_hint(name),
                "occult_hint": _occult_hint(name),
                "npc": kind == "careers" and "_npc_" in name.lower(),
            }
        )


XML_CLASSES = [
    "Trait",
    "Skill",
    "TunableSkill",
    "Statistic",
    "Career",
    "TunableCareerTrack",
    "Aspiration",
    "Milestone",
    "DevelopmentalMilestone",
    "Preference",
    "RelationshipBit",
    "OccultTrait",
    "Occult",
]
XML_HASHES = {fnv1_32(c.lower()) for c in XML_CLASSES}
XML_TO_KIND = {
    "Trait": "traits",
    "Skill": "skills",
    "TunableSkill": "skills",
    "Statistic": "skills",
    "Career": "careers",
    "TunableCareerTrack": "career_tracks",
    "Aspiration": "aspirations",
    "Milestone": "milestones",
    "DevelopmentalMilestone": "milestones",
    "Preference": "preferences",
    "RelationshipBit": "relationship_bits",
    "OccultTrait": "occults",
    "Occult": "occults",
}

ATTR_RE = re.compile(rb'(\w+)="([^"]*)"')


def _scan_mod_package(path: Path, add, mod_root: Path, wanted: set[str] | None = None) -> None:
    try:
        package = DBPF(path)
    except (DBPFError, OSError):
        return
    seen_here: set[tuple[str, int]] = set()
    for entry in package.entries:
        if entry.type not in XML_HASHES:
            continue
        if entry.size > 500_000:
            continue
        try:
            data = package.read_entry(entry)
        except Exception:
            continue
        if not data.startswith(b"<I "):
            continue
        header = data[: data.find(b">") + 1]
        attrs = dict(ATTR_RE.findall(header))
        try:
            cls = attrs.get(b"c", b"").decode()
            name = attrs.get(b"n", b"").decode()
            module = attrs.get(b"m", b"").decode()
            inst = int(attrs.get(b"s", b"0").decode() or 0)
        except Exception:
            continue
        kind = XML_TO_KIND.get(cls)
        if not kind or not name:
            continue
        if wanted is not None and kind not in wanted:
            continue
        low = name.lower()
        if kind == "skills" and "skill" not in low:
            continue
        if inst == 0:
            inst = entry.instance
        key = (kind, inst)
        if key in seen_here:
            continue
        seen_here.add(key)
        try:
            source = str(path.relative_to(mod_root))
        except ValueError:
            source = path.name
        add(
            {
                "kind": kind,
                "id": inst,
                "tuning": name,
                "class": cls,
                "label": _display_label(kind, name),
                "pack": "MOD",
                "pack_label": "Mod",
                "modded": True,
                "source": source,
                "module": module,
                "age_hint": _age_hint(name, cls),
                "species_hint": _species_hint(name),
                "occult_hint": _occult_hint(name),
                "npc": kind == "careers" and "_npc_" in name.lower(),
            }
        )


def _iter_mod_packages() -> Iterable[Path]:
    if not paths.mods or not paths.mods.is_dir():
        return []
    skip = {"cache", "cachestr", "onlinethumbnailcache"}
    out = []
    for p in paths.mods.rglob("*.package"):
        if any(part.lower() in skip for part in p.parts):
            continue
        try:
            if p.stat().st_size > 400 * 1024 * 1024:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def _age_label(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("_", " ").title()
    return "Young Adult" if text == "Youngadult" else text


def _sdk_icon_key(model) -> str:
    key = getattr(model, "icon_key", None)
    if key is None:
        return ""
    return f"{key.type_id:08x}:{key.group:08x}:{key.instance:016x}"


def _sdk_source(source) -> tuple[str, str, bool, str]:
    if source is None:
        return "Base", "Base Game", False, ""
    package = str(getattr(source, "path", None) or getattr(source, "package", "") or "")
    if getattr(source, "is_mod", False):
        return "MOD", "Mod", True, package
    raw = (getattr(source, "pack", "") or "Base").upper()
    pack = "Base" if raw == "BASE" else raw
    return pack, PACK_NAMES.get(pack, pack), False, package


def _sdk_item(kind: str, model) -> dict | None:
    name = getattr(model, "name", "") or ""
    if not name:
        return None
    pack, pack_label, modded, package = _sdk_source(getattr(model, "source", None))
    if kind == "traits":
        trait_type = (getattr(model, "trait_type", "") or "").upper()
        low = name.lower()
        if (
            trait_type in {"HIDDEN", "GENDER_OPTIONS", "WALKSTYLE", "TAILSTYLE", "SIM_PHONE", "AGENT", "SPECIES", "AGE", "PREFERENCE"}
            or getattr(model, "is_hidden", False)
            or getattr(model, "is_internal", False)
            or low.startswith(INTERNAL_TRAIT_PREFIXES)
            or low.startswith(("trait_university_", "trait_simpreference"))
            or _is_internal_trait(name)
        ):
            return None
    label = getattr(model, "display_name", None) or _display_label(kind, name)
    if kind in ("aspirations", "aspiration_tracks"):
        label = _display_label(kind, name)
    elif kind == "careers":
        label = getattr(model, "display_name", None) or _display_label(kind, name)
    elif kind == "career_tracks":
        label = _display_label(kind, name)
    item = {
        "kind": kind,
        "id": getattr(model, "id", 0) or 0,
        "tuning": name,
        "class": model.__class__.__name__,
        "label": label,
        "pack": pack,
        "pack_label": pack_label,
        "modded": modded,
        "source": package,
        "age_hint": "",
        "species_hint": "",
        "occult_hint": "",
        "npc": kind == "careers" and "_npc_" in name.lower(),
    }
    icon_key = _sdk_icon_key(model)
    if icon_key:
        item["icon_key"] = icon_key
    ages = getattr(model, "ages", None) or getattr(model, "valid_ages", None) or []
    if ages:
        item["ages"] = [_age_label(age) for age in ages]
    # ``age_hint`` is a single-value restriction in the UI's compatibility
    # filter, so only set it when the tuning really targets one life stage.
    if len(ages) == 1:
        item["age_hint"] = _age_label(ages[0])
    species = getattr(model, "species", None) or []
    if species:
        item["species_hint"] = str(species[0]).replace("_", " ").title()
    occults = getattr(model, "occults", None) or []
    if occults:
        item["occult_hint"] = str(occults[0]).replace("_", " ").title()
    if kind == "aspiration_tracks":
        display_name = getattr(model, "display_name", None)
        if display_name and not re.fullmatch(r"0x[0-9a-f]+", display_name, re.I):
            item["display_name"] = display_name
    if kind == "traits":
        item["trait_type"] = getattr(model, "trait_type", "") or ""
    return item


def _reset_buckets() -> dict[str, dict[int, dict]]:
    return {
        k: {}
        for k in (
            "traits", "skills", "careers", "career_tracks", "aspirations",
            "aspiration_tracks", "objectives", "milestones", "preferences",
            "degrees", "identity", "relationship_bits", "relationship_tracks",
            "occults",
        )
    }


def _build_from_sdk(
    buckets: dict[str, dict[int, dict]],
    add,
    progress: Callable[[str, int, int], None] | None,
) -> bool:
    """Fill the SDK-modelled kinds from ``sims4_sdk.catalog.Catalog``."""
    catalog = sdk.catalog()
    if catalog is None:
        return False
    collections = {
        "traits": catalog.traits.values(),
        "preferences": catalog.preferences.values(),
        "aspiration_tracks": catalog.aspiration_tracks.values(),
        "careers": catalog.careers.values(),
        "career_tracks": catalog.career_tracks.values(),
        "milestones": catalog.milestones.values(),
        "relationship_bits": catalog.relationship_bits.values(),
    }
    total = sum(len(list(values)) for values in collections.values())
    done = 0
    for kind, values in collections.items():
        for model in values:
            done += 1
            if progress and done % 500 == 0:
                progress(f"Reading SDK catalog {done}/{total}", done, total + 1)
            item = _sdk_item(kind, model)
            if item:
                if kind == "aspiration_tracks" and model.category_id is not None:
                    track = model
                    stage = next((catalog.aspirations.get(stage_id) for stage_id in track.aspiration_ids
                                  if catalog.aspirations.get(stage_id) is not None), None)
                    aspiration_item = _sdk_item("aspirations", stage) if stage is not None else None
                    if aspiration_item is None:
                        add(item)
                        continue
                    aspiration_item["id"] = track.id
                    aspiration_item["aspiration_id"] = stage.id
                    aspiration_item["label"] = item.get("display_name") or _display_label("aspirations", stage.name)
                    aspiration_item["pack"], aspiration_item["pack_label"], aspiration_item["modded"], aspiration_item["source"] = _sdk_source(track.source)
                    icon_key = _sdk_icon_key(track)
                    if icon_key:
                        aspiration_item["icon_key"] = icon_key
                    stages = []
                    for stage_id in getattr(track, "aspiration_ids", []):
                        stage = catalog.aspirations.get(stage_id)
                        if stage is None:
                            continue
                        objectives = []
                        for objective_id in stage.objective_ids:
                            objective = catalog.aspiration_objectives.get(objective_id)
                            if objective is None:
                                continue
                            skill = catalog.statistics.get(objective.skill_id)
                            objectives.append({
                                "text": objective.display_text,
                                "tooltip": objective.tooltip,
                                "skill": (skill.display_name or pretty(skill.name)) if skill else None,
                                "skill_level": objective.skill_level,
                            })
                        if objectives:
                            stages.append({"name": stage.display_name or _display_label("aspirations", stage.name),
                                           "objectives": objectives})
                    aspiration_item["aspiration_stages"] = stages
                    add(aspiration_item)
                add(item)
    # Some packs ship likes/dislikes as ``Trait`` resources rather than
    # ``Preference`` resources.  The SDK catalog keeps them under traits.
    for model in catalog.traits.values():
        if (model.name or "").lower().startswith("trait_simpreference"):
            item = _sdk_item("preferences", model)
            if item:
                add(item)
    # The SDK can identify explicit skill definitions, while some generic
    # statistics still have unknown classification and need the local scan.
    for model in getattr(catalog, "statistics", {}).values():
        if model.is_skill is True:
            item = _sdk_item("skills", model)
            if item:
                item["class"] = model.tuning_class
                add(item)
    return True


def build_catalog(progress: Callable[[str, int, int], None] | None = None) -> dict:
    started = time.time()
    if not sdk.SDK_AVAILABLE or sdk.Sims4Workspace is None:
        raise RuntimeError("SimsDataSDK is missing or could not be loaded. Initialize the SimsDataSDK submodule and restart the studio.")
    if not paths.game or not paths.game.is_dir():
        raise RuntimeError("The Sims 4 installation could not be found. Check the game path and restart the studio.")
    game_packages = _game_packages()
    if not game_packages:
        raise RuntimeError(f"No simulation packages were found in {paths.game}.")
    buckets = _reset_buckets()

    def add(item: dict) -> None:
        bucket = buckets[item["kind"]]
        existing = bucket.get(item["id"])
        if existing is None or (item["modded"] and not existing["modded"]):
            bucket[item["id"]] = item

    # The SDK catalog covers traits, preferences, aspirations (+tracks),
    # careers (+tracks), milestones and relationship bits for the game and mods.
    used_sdk = _build_from_sdk(buckets, add, progress)
    sdk_skill_ids = set(buckets["skills"])
    wanted = SUPPLEMENTAL_KINDS if used_sdk else None

    def add_supplemental(item: dict) -> None:
        if item["kind"] == "skills" and item["id"] in sdk_skill_ids:
            return
        add(item)

    total = len(game_packages)
    for i, path in enumerate(game_packages, 1):
        if progress:
            progress(f"Reading {path.parent.name}/{path.name}", i, total + 1)
        _scan_simdata_package(path, add_supplemental, wanted)

    mod_packages = list(_iter_mod_packages())
    total_mods = len(mod_packages)
    for i, path in enumerate(mod_packages, 1):
        if progress and (i % 25 == 0 or i == total_mods):
            progress(f"Scanning mods {i}/{total_mods}", total + 1, total + total_mods + 1)
        try:
            _scan_mod_package(path, add_supplemental, paths.mods, wanted)
        except Exception:
            continue

    catalog = {}
    for kind, items in buckets.items():
        catalog[kind] = sorted(items.values(), key=lambda x: x["label"].lower())
    if not any(catalog[kind] for kind in ("traits", "skills", "careers", "aspirations")):
        raise RuntimeError("No game content could be read from the simulation packages. Check that the game files are accessible and SimsDataSDK is working.")

    sdk_catalog = sdk.catalog() if used_sdk else None
    sdk_diagnostics = getattr(sdk_catalog, "diagnostics", []) if sdk_catalog is not None else []
    meta = {
        "version": CACHE_VERSION,
        "built": time.time(),
        "seconds": round(time.time() - started, 2),
        "counts": {k: len(v) for k, v in catalog.items()},
        "game_packages": [str(p) for p in game_packages],
        "mod_packages": total_mods,
        "sdk": used_sdk,
        "sdk_kinds": sorted(SDK_KINDS) if used_sdk else [],
        "supplemental_kinds": sorted(SUPPLEMENTAL_KINDS) if used_sdk else [],
        "sdk_diagnostics": len(sdk_diagnostics),
        "sdk_diagnostic_messages": [
            f"{issue.stage}: {issue.message}"[:300] for issue in sdk_diagnostics[:20]
        ],
    }
    payload = {"meta": meta, "catalog": catalog}
    try:
        CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return payload


XML_ITEMS_FILE = DATA_DIR / "xml_tuning_items.json"


def _merge_xml_items(payload: dict) -> dict:
    """Merge tunings that only exist as CombinedTuning XML into the catalog."""
    if not XML_ITEMS_FILE.exists():
        return payload
    try:
        extra = json.loads(XML_ITEMS_FILE.read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return payload
    catalog = payload.get("catalog")
    if not isinstance(catalog, dict):
        return payload
    existing_by_tuning = {
        (item.get("tuning") or "").lower(): item
        for items in catalog.values() if isinstance(items, list)
        for item in items
    }
    for item in extra:
        kind = item.get("kind")
        tuning = (item.get("tuning") or "").lower()
        if not kind or not tuning:
            continue
        existing = existing_by_tuning.get(tuning)
        if existing is not None:
            # Enrich compiled SimData entries with XML-only metadata such as
            # trait_type (PERSONALITY / ASPIRATION / HIDDEN).
            if item.get("trait_type"):
                existing["trait_type"] = item["trait_type"]
            continue
        if kind == "aspirations":
            continue
        bucket = catalog.setdefault(kind, [])
        bucket.append(item)
        existing_by_tuning[tuning] = item
    for kind, items in catalog.items():
        if isinstance(items, list):
            items.sort(key=lambda x: (x.get("label") or "").lower())
    meta = payload.setdefault("meta", {})
    meta["counts"] = {k: len(v) for k, v in catalog.items() if isinstance(v, list)}
    return payload


_MEM_CACHE: dict = {"mtime": None, "payload": None}


def load_catalog(force: bool = False) -> dict:
    if not force and CACHE_FILE.exists():
        try:
            mtime = CACHE_FILE.stat().st_mtime
            if _MEM_CACHE["payload"] is not None and _MEM_CACHE["mtime"] == mtime:
                return _MEM_CACHE["payload"]
            payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if payload.get("meta", {}).get("version") == CACHE_VERSION:
                payload = _merge_xml_items(payload)
                _MEM_CACHE["mtime"] = mtime
                _MEM_CACHE["payload"] = payload
                return payload
        except (OSError, ValueError):
            pass
    payload = _merge_xml_items(build_catalog())
    try:
        _MEM_CACHE["mtime"] = CACHE_FILE.stat().st_mtime
        _MEM_CACHE["payload"] = payload
    except OSError:
        pass
    return payload
