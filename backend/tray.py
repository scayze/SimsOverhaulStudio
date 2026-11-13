"""Read the Tray library (read-only). Tray files are never modified."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import sdk
from .catalog import load_catalog
from .images import has_image, household_image_url, mask_url_if_any, premade_mask_url_if_any, sim_image_url
from .icons import icon_for
from .protobuf import fast_sim_names
from .sdkconvert import tray_sim_payload
from .settings import APP_DIR, paths
from . import gamedata, premade_art

_CACHE: dict[float, list[dict]] = {}
_GROUPS: dict[str, dict] = {}
_RICH_CACHE: dict[tuple[str, float], list[dict]] = {}


def _sdk_rich(path: Path) -> list[dict]:
    """Read a ``.householdbinary`` with the SDK's schema-driven Tray reader.

    The SDK currently raises ``TypeError`` for some Tray files whose float
    fields are varint-encoded (see docs/sdk-migration.md); callers fall back to
    the supplemental generic decoder when this returns ``[]``.
    """
    workspace = sdk.workspace()
    catalog = sdk.catalog()
    if workspace is None or catalog is None:
        return []
    try:
        from sims4_sdk.save.tray import read_household_binary

        household = read_household_binary(path, catalog)
    except Exception:
        return []
    ident = path.stem.split("!")[-1]
    by_id = {sim.sim_id: sim for sim in household.sims if sim.sim_id}
    name_by_id = {sim.sim_id: f"{sim.first_name}|{sim.last_name}" for sim in household.sims if sim.sim_id}
    rows: list[dict] = []
    for index, sim in enumerate(household.sims):
        if not sim.first_name:
            continue
        key = f"tray:{ident}:{index}:{sim.first_name}|{sim.last_name}"
        payload = tray_sim_payload(
            sim,
            catalog,
            key,
            ident,
            household=household.family_name or sim.last_name,
        )
        payload["household_key"] = f"tray:{ident}"
        # Family links the SDK already decodes from the genealogy tracker.
        family = []
        for relation in getattr(sim, "parents", []) or []:
            target = name_by_id.get(relation.sim_id, relation.name)
            if target:
                family.append({"target_name": target, "relation": relation.kind.title(), "from_game": True})
        for relation in getattr(sim, "siblings", []) or []:
            target = name_by_id.get(relation.sim_id, relation.name)
            if target:
                family.append({"target_name": target, "relation": "Sibling", "from_game": True})
        for relation in getattr(sim, "extended_family", []) or []:
            target = name_by_id.get(relation.sim_id, relation.name)
            if target:
                family.append({"target_name": target, "relation": relation.kind.title(), "from_game": True})
        for relation in getattr(sim, "children", []) or []:
            target = name_by_id.get(relation.sim_id, relation.name)
            if target:
                family.append({"target_name": target, "relation": "Child", "from_game": True})
        payload["family"] = family

        relationships = []
        for relation in getattr(sim, "relationships", []) or []:
            target = name_by_id.get(relation.target_id)
            if not target:
                continue
            tracks = {track.track_id: track.value for track in relation.track_values}
            relationships.append(
                {
                    "target_name": target,
                    "label": _relationship_label(catalog, relation.bits),
                    "friendship": int(round(tracks.get(16650, relation.value or 0))),
                    "romance": int(round(tracks.get(16651, 0))),
                    "bits": [
                        {"id": bit, "label": name, "modded": False}
                        for bit, name in zip(relation.bits, relation.bit_names)
                        if "should not be seen" not in (name or "").lower()
                        and "dnt" not in (name or "").lower()
                    ],
                    "from_game": True,
                }
            )
        if sim.spouse_name and not any(row["target_name"] == sim.spouse_name for row in relationships):
            relationships.append({"target_name": sim.spouse_name, "label": "Spouse", "friendship": 60, "romance": 60, "from_game": True})
        for name in ([sim.fiance_name] if getattr(sim, "fiance_name", None) else []):
            if name and not any(row["target_name"] == name for row in relationships):
                relationships.append({"target_name": name, "label": "Fiancé(e)", "friendship": 60, "romance": 70, "from_game": True})
        for name in getattr(sim, "steady_names", []) or []:
            if name and not any(row["target_name"] == name for row in relationships):
                relationships.append({"target_name": name, "label": "Steady", "friendship": 50, "romance": 50, "from_game": True})
        payload["relationships"] = relationships
        rows.append(payload)
    return rows


def _relationship_label(catalog, bits: list[int]) -> str:
    names = " ".join((catalog.tuning_names.get(bit, "") or "").lower() for bit in bits or [])
    if "romanticcombo_lovebirds" in names or "soulmates" in names:
        return "Lovebirds"
    if "romanticcombo_lovers" in names:
        return "Lovers"
    if "friendship-bff" in names:
        return "Best friends"
    if "friendship-disliked" in names:
        return "Disliked"
    if "romantic" in names:
        return "Partner"
    if "friendship" in names:
        return "Friend"
    return "Acquaintance"


def _rich(path: Path) -> list[dict]:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    key = (str(path), mtime)
    if key not in _RICH_CACHE:
        _RICH_CACHE[key] = _sdk_rich(path)
    return _RICH_CACHE[key]


def _add_icons(sim: dict) -> None:
    for t in sim.get("traits", []):
        icon = icon_for("traits", t.get("label", ""), t.get("tuning", ""))
        if icon:
            t["icon"] = icon
    for t in sim.get("remove_traits", []):
        icon = icon_for("traits", t.get("label", ""), t.get("tuning", ""))
        if icon:
            t["icon"] = icon
    for s in sim.get("skills", []):
        icon = icon_for("skills", s.get("label", ""), s.get("tuning", ""))
        if icon:
            s["icon"] = icon
    for m in sim.get("milestones", []):
        icon = icon_for("milestones", m.get("label", ""), m.get("tuning", ""))
        if icon:
            m["icon"] = icon
    c = sim.get("career")
    if c:
        icon = icon_for("careers", c.get("label", ""), c.get("tuning", ""))
        if icon:
            c["icon"] = icon
    a = sim.get("aspiration")
    if a and not a.get("track"):
        icon = icon_for("aspirations", a.get("label", ""), a.get("tuning", ""))
        if icon:
            a["icon"] = icon


def _prepare(ident: str, rich_sims: list[dict]) -> list[dict]:
    name_to_key = {}
    prepared = []
    hh_image = household_image_url(ident) if has_image(ident, "household") else ""
    hh_mask = mask_url_if_any(ident, "household") if hh_image else ""
    for index, sim in enumerate(rich_sims):
        key = f"tray:{ident}:{index}:{sim['first']}|{sim['last']}"
        sim = dict(sim)
        sim["key"] = key
        sim["source"] = "tray"
        sim["source_ref"] = ident
        sim["household"] = sim.get("household") or sim["last"]
        sim["household_key"] = f"tray:{ident}"
        sim["image"] = sim_image_url(sim.get("sim_id")) if has_image(f"0x{sim.get('sim_id'):016x}" if sim.get("sim_id") else "", "sim") else ""
        # The .sgi portrait carries an ALFA mask. Apply it with the crisp pass
        # so the game's soft white glow becomes a clean edge (no halo).
        sim["image_mask"] = (
            mask_url_if_any(f"0x{sim.get('sim_id'):016x}", "sim")
            if sim.get("sim_id") and sim["image"]
            else ""
        )
        sim["household_image"] = hh_image
        sim["household_image_mask"] = hh_mask
        if "careers" in sim:
            careers = sorted(sim.pop("careers") or [], key=lambda c: c.get("level", 0), reverse=True)
            sim["career_history"] = careers[1:] if len(careers) > 1 else []
            sim["career"] = careers[0] if careers else None
        _add_icons(sim)
        name_to_key[(sim["first"], sim["last"])] = key
        prepared.append(sim)

    rich = [
        s
        for s in prepared
        if s.get("identity_found")
        or s.get("traits")
        or s.get("skills")
        or s.get("career")
        or s.get("likes")
        or s.get("dislikes")
        or s.get("degrees")
    ]
    if rich and len(rich) < len(prepared):
        prepared = rich

    for sim in prepared:
        rels = []
        for rel in sim.get("relationships", []):
            target_name = rel.pop("target_name", None)
            if not target_name or "|" not in target_name:
                continue
            first, last = target_name.split("|", 1)
            target_key = name_to_key.get((first, last))
            if target_key:
                rel["target"] = target_key
                rels.append(rel)
        sim["relationships"] = rels

        fams = []
        for fam in sim.get("family", []):
            target_name = fam.pop("target_name", None)
            if not target_name or "|" not in target_name:
                continue
            first, last = target_name.split("|", 1)
            target_key = name_to_key.get((first, last))
            if target_key:
                fam["target"] = target_key
                fams.append(fam)
        sim["family"] = fams
    return prepared


def _name_only(ident: str, hb: Path) -> list[dict]:
    try:
        data = hb.read_bytes()
    except OSError:
        return []
    payload = data[8:] if len(data) > 8 else data
    sims = []
    for index, s in enumerate(fast_sim_names(payload)):
        sims.append(
            {
                "key": f"tray:{ident}:{index}:{s.first}|{s.last}",
                "first": s.first,
                "last": s.last,
                "household": s.last,
                "source": "tray",
                "source_ref": ident,
                "household_key": f"tray:{ident}",
                "age": "Adult",
                "gender": "Female",
                "occult": "Human",
                "traits": [],
                "likes": [],
                "dislikes": [],
                "degrees": [],
                "skills": [],
                "career": None,
                "career_history": [],
                "relationships": [],
                "data_quality": "names",
            }
        )
    return sims


def _scan_groups() -> tuple[dict[str, dict], float]:
    if not paths.tray or not paths.tray.is_dir():
        return {}, 0
    try:
        mtime = paths.tray.stat().st_mtime
    except OSError:
        mtime = 0
    if _GROUPS and _CACHE.get("mtime") == mtime:
        return _GROUPS, mtime

    groups: dict[str, dict] = {}
    for p in paths.tray.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if "!" not in name:
            continue
        ident = name.split("!", 1)[1].split(".", 1)[0]
        if not ident.startswith("0x"):
            continue
        group = groups.setdefault(
            ident,
            {
                "id": ident,
                "files": [],
                "householdbinary": None,
                "trayitem": None,
                "sgi": [],
                "modified": 0,
            },
        )
        group["files"].append(name)
        lower = name.lower()
        try:
            group["modified"] = max(group["modified"], p.stat().st_mtime)
        except OSError:
            pass
        if lower.endswith(".householdbinary"):
            group["householdbinary"] = p
        elif lower.endswith(".trayitem"):
            group["trayitem"] = p
        elif lower.endswith(".sgi"):
            group["sgi"].append(p)
    _GROUPS.clear()
    _GROUPS.update(groups)
    _CACHE.clear()
    _CACHE["mtime"] = mtime
    return groups, mtime


def list_tray(force: bool = False) -> list[dict]:
    groups, mtime = _scan_groups()
    if not force and mtime in _CACHE:
        return _CACHE[mtime]

    items = []
    for ident, group in groups.items():
        hb: Path | None = group["householdbinary"]
        if hb is None:
            continue
        sims = _name_only(ident, hb)
        if not sims:
            continue
        items.append(
            {
                "id": ident,
                "sims": sims,
                "household": sims[0]["last"] if sims else "Tray Household",
                "has_household": True,
                "modified": group["modified"],
                "modified_label": time.strftime("%d %b %Y", time.localtime(group["modified"]))
                if group["modified"]
                else "",
                "files": len(group["files"]),
                "quality": "names",
                "household_image": household_image_url(ident) if has_image(ident, "household") else "",
                "household_image_mask": mask_url_if_any(ident, "household") if has_image(ident, "household") else "",
                "image": household_image_url(ident) if has_image(ident, "household") else "",
            }
        )
    items.sort(key=lambda x: x["modified"], reverse=True)
    _CACHE[mtime] = items
    return items


def _apply_trayitem_aspirations(path: Path, sims: list[dict]) -> None:
    try:
        data = path.read_bytes()
    except OSError:
        return
    strings = [m.decode("ascii") for m in re.findall(rb"[\x20-\x7E]{4,120}", data)]
    aspirations = load_catalog()["catalog"].get("aspirations", [])
    by_label = {a["label"].lower(): a for a in aspirations}
    first_positions = {}
    for idx, text in enumerate(strings):
        low = text.lower()
        for sim in sims:
            if sim["first"].lower() == low or low.startswith(sim["first"].lower() + " "):
                first_positions[sim["key"]] = idx
    for idx, text in enumerate(strings):
        item = by_label.get(text.strip().lower())
        if not item:
            continue
        candidates = [(pos, key) for key, pos in first_positions.items() if pos < idx]
        if candidates:
            _, key = max(candidates)
            sim = next((s for s in sims if s["key"] == key), None)
        else:
            sim = next((s for s in sims if not s.get("aspiration")), None)
        if sim and not sim.get("aspiration"):
            sim["aspiration"] = {
                "id": item["id"],
                "label": item["label"],
                "modded": item.get("modded", False),
                "pack": item.get("pack_label", ""),
            }


def get_household(ident: str) -> dict | None:
    groups, _ = _scan_groups()
    group = groups.get(ident)
    if not group or not group.get("householdbinary"):
        return None
    hb: Path = group["householdbinary"]
    rich = _rich(hb)
    if rich:
        sims = _prepare(ident, rich)
        if sims and group.get("trayitem"):
            _apply_trayitem_aspirations(group["trayitem"], sims)
        quality = "full"
    else:
        sims = _name_only(ident, hb)
        quality = "names"
    return {
        "id": ident,
        "sims": sims,
        "household": sims[0]["last"] if sims else "Tray Household",
        "modified": group["modified"],
        "modified_label": time.strftime("%d %b %Y", time.localtime(group["modified"]))
        if group["modified"]
        else "",
        "quality": quality,
        "household_image": household_image_url(ident) if has_image(ident, "household") else "",
        "household_image_mask": mask_url_if_any(ident, "household") if has_image(ident, "household") else "",
        "image": household_image_url(ident) if has_image(ident, "household") else "",
    }


def find_tray_sims(ident: str) -> list[dict]:
    item = get_household(ident)
    return item["sims"] if item else []


PREMADE_NAMES = {
    "goth", "caliente", "landgraab", "pancakes", "lothario", "vatores", "vladislaus",
    "straud", "bjergsen", "spencer-kim-lewis", "spencer-kim", "pleasant", "dreamer",
    "broke", "bunch", "roomies", "bff", "villareal", "fyres", "behr", "partihaus",
    "hecking", "sigworth", "bailey", "bailey-moon", "feng", "jang", "kealoha",
    "kahananui", "ngata", "iona", "ito", "kim-lewis", "munch", "harris", "laurent",
    "okada", "kibo", "akiyama", "nishidake", "sakamoto", "yuki", "haas", "faba",
    "charm", "silversweater", "amicable", "patel", "price", "prescott", "warez",
    "cahill", "cardwell", "sterling", "lewis", "goldbloom", "merchant", "terrell",
    "mahi'ai", "lobo", "lopez", "garcia", "flores", "martinez", "sato", "tanaka",
    "romero", "washington", "young", "scott", "capp", "tinker", "penn", "williams",
}


def seed_tray_premades():
    """Return a unique, rich Tray household for each known premade name."""
    chosen = {}
    for item in sorted(list_tray(), key=lambda x: x.get("modified", 0), reverse=True):
        name = (item.get("household") or "").lower()
        if name not in PREMADE_NAMES or name in chosen:
            continue
        rich = get_household(item["id"])
        if not rich or rich.get("quality") != "full" or not rich.get("sims"):
            continue
        chosen[name] = rich
    return list(chosen.values())


AGE_RANK = {"Elder": 6, "Adult": 5, "Young Adult": 4, "Teen": 3, "Child": 2, "Toddler": 1, "Baby": 0}

INVERSE_CATEGORY = {
    "parent": "child", "child": "parent",
    "grandparent": "grandchild", "grandchild": "grandparent",
    "great_grandparent": "great_grandchild", "great_grandchild": "great_grandparent",
    "collateral": "collateral", "sibling": "sibling", "cousin": "cousin",
    "partner": "partner", "relative": "relative",
}

# The real dynasties defined by the game (EP21 DynastySeed tuning instances).
GAME_DYNASTIES = ["Abrantes", "Alto", "Capp", "Darong", "Goth", "Landgraab", "Monty", "Thebe"]

_PORTRAIT_MAP: dict | None = None
_WORLD_CACHE: dict | None = None


def seed_premade_world():
    """Return the clean premade households, fully decoded from the game files."""
    global _WORLD_CACHE
    if _WORLD_CACHE is not None:
        return _WORLD_CACHE
    from . import gamedata, premade_art
    from .templatedata import load_complete_dataset

    try:
        premade_art.ensure_premade_images()
    except Exception:
        pass
    aspirations = load_catalog()["catalog"].get("aspirations", [])
    dataset = load_complete_dataset()
    households = dataset.get("households", [])
    all_ids = {}
    for hh in households:
        for s in hh.get("sims", []):
            if s.get("sim_id"):
                all_ids[s["sim_id"]] = f"premade:{hh.get('template_id')}:{s['sim_id']}"

    sims = []
    for hh in households:
        name = hh.get("name") or "Household"
        template_id = hh.get("template_id")
        tpl_hex = f"{template_id:016x}"
        image_file = APP_DIR / "data" / "premade_images" / f"{tpl_hex}.jpg"
        hh_image = f"/api/premade/image?template={tpl_hex}" if image_file.is_file() else ""
        hh_mask = premade_mask_url_if_any(tpl_hex) if hh_image else ""
        dynasty = hh.get("game_dynasty")

        for s in hh.get("sims", []):
            key = all_ids.get(s.get("sim_id")) or f"premade:{template_id}:{s.get('first')}|{s.get('last')}"
            raw_asp = s.get("aspiration") or {}
            track = raw_asp.get("label") if raw_asp.get("track") else None
            # The install template stores an aspiration track (e.g. Family A),
            # not a specific aspiration. Do not invent one from the track; show
            # the track and let the user pick the specific aspiration.
            aspiration = None if track else (raw_asp or None)

            family = []
            for fam in s.get("family", []) or []:
                target = all_ids.get(fam.get("target_id"))
                if not target:
                    continue
                raw = fam.get("relation", "Relative")
                info = gamedata.relation_info(raw)
                family.append({
                    "target": target, "relation": info["label"], "relation_raw": raw,
                    "inverse": info["inverse"], "generation": info["generation"],
                    "category": info["category"],
                })

            relationships = []
            for rel in s.get("relationships", []) or []:
                target = all_ids.get(rel.get("target_id"))
                if not target:
                    continue
                relationships.append({
                    "target": target,
                    "label": rel.get("label") or "Partner",
                    "friendship": int(round(rel.get("friendship", 0))),
                    "romance": int(round(rel.get("romance", 0))),
                    "bits": rel.get("bits", []),
                    "from_game": True,
                })
            if s.get("significant_other"):
                target = all_ids.get(s["significant_other"])
                if target and not any(r["target"] == target for r in relationships):
                    relationships.append({"target": target, "label": "Spouse", "friendship": 45, "romance": 75})
            if s.get("fiance"):
                target = all_ids.get(s["fiance"])
                if target and not any(r["target"] == target for r in relationships):
                    relationships.append({"target": target, "label": "Fiancé(e)", "friendship": 55, "romance": 70})
            for steady_id in s.get("steady", []) or []:
                target = all_ids.get(steady_id)
                if target and not any(r["target"] == target for r in relationships):
                    relationships.append({"target": target, "label": "Steady", "friendship": 50, "romance": 50})

            payload = {
                **s,
                "key": key,
                "household": name,
                "household_key": f"premade:{template_id}",
                "source": "premade",
                "source_ref": tpl_hex,
                "data_quality": "full",
                "species": s.get("species") or "Human",
                "occult": s.get("occult") or "Human",
                "funds": hh.get("money"),
                "household_image": hh_image,
                "household_image_mask": hh_mask,
                "household_description": hh.get("description", ""),
                "lot": hh.get("lot", ""),
                "lot_description": hh.get("lot_description", ""),
                "aspiration": aspiration,
                "aspiration_track": track,
                "likes": s.get("likes") or [],
                "dislikes": s.get("dislikes") or [],
                "career_track": s.get("career_track"),
                "family": family,
                "relationships": relationships,
                # Clean-save sims use the game's own household picture. We do
                # NOT match Tray sims by name — those are different sims.
                "image": hh_image,
                "image_mask": hh_mask,
                "image_kind": "household" if hh_image else "",
                "game_dynasty": dynasty,
            }
            for stale in ("significant_other", "fiance", "first_key", "last_key", "aspiration_id",
                          "portrait_crop", "portrait_options"):
                payload.pop(stale, None)
            _add_icons(payload)
            sims.append(payload)

    by_key = {p["key"]: p for p in sims}

    def add_family(sim, target_key, relation, meta=None):
        if not target_key or target_key not in by_key or target_key == sim["key"]:
            return
        if not any(f.get("target") == target_key for f in sim["family"]):
            row = {"target": target_key, "relation": relation}
            if meta:
                row.update(meta)
            sim["family"].append(row)

    def add_relationship(sim, target_key, label, friendship=45, romance=0):
        if not target_key or target_key not in by_key or target_key == sim["key"]:
            return
        if not any(r.get("target") == target_key for r in sim["relationships"]):
            sim["relationships"].append({
                "target": target_key, "label": label,
                "friendship": friendship, "romance": romance,
            })

    # 1. Bidirectional family links with the *inverted* category.
    for sim in sims:
        for fam in list(sim["family"]):
            target = by_key.get(fam.get("target"))
            if not target:
                continue
            inverse = fam.get("inverse") or "Relative"
            gen = fam.get("generation") or 0
            add_family(target, sim["key"], inverse, {
                "relation_raw": fam.get("relation_raw", inverse),
                "inverse": fam["relation"], "generation": -gen,
                "category": INVERSE_CATEGORY.get(fam.get("category", "relative"), "relative"),
            })
            add_relationship(sim, target["key"], fam["relation"], 45, 0)
            add_relationship(target, sim["key"], inverse, 45, 0)

    # 2. Mirror spouse/partner relationship rows.
    for sim in sims:
        for rel in list(sim["relationships"]):
            target = by_key.get(rel.get("target"))
            if target:
                add_relationship(target, sim["key"], rel.get("label"),
                                 rel.get("friendship", 45), rel.get("romance", 0))

    # 3. Siblings share a parent (ancestor links have generation > 0).
    parents = {
        s["key"]: {f["target"] for f in s["family"] if (f.get("generation") or 0) > 0}
        for s in sims
    }
    keys = [s["key"] for s in sims]
    sibling_meta = {"relation_raw": "Sibling", "inverse": "Sibling", "generation": 0, "category": "sibling"}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if not (parents[a] & parents[b]):
                continue
            add_family(by_key[a], b, "Sibling", sibling_meta)
            add_family(by_key[b], a, "Sibling", sibling_meta)
            add_relationship(by_key[a], b, "Sibling", 45, 0)
            add_relationship(by_key[b], a, "Sibling", 45, 0)

    # 4. Extended family: grandparents, aunts/uncles and cousins.
    for s in sims:
        for pkey in list(parents[s["key"]]):
            parent = by_key.get(pkey)
            if not parent:
                continue
            for f in list(parent["family"]):
                gen = f.get("generation") or 0
                target = f.get("target")
                if not target or target == s["key"]:
                    continue
                if gen > 0:
                    add_family(s, target, "Grandparent", {"relation_raw": "Grandparent", "inverse": "Grandchild", "generation": gen + 1, "category": "grandparent"})
                    if target in by_key:
                        add_family(by_key[target], s["key"], "Grandchild", {"relation_raw": "Grandchild", "inverse": "Grandparent", "generation": -(gen + 1), "category": "grandchild"})
                    add_relationship(s, target, "Grandparent", 45, 0)
                    if target in by_key:
                        add_relationship(by_key[target], s["key"], "Grandchild", 45, 0)
                elif gen == 0 and f.get("category") == "sibling":
                    add_family(s, target, "Aunt / Uncle", {"relation_raw": "Parent's Sibling", "inverse": "Niece / Nephew", "generation": 1, "category": "collateral"})
                    if target in by_key:
                        add_family(by_key[target], s["key"], "Niece / Nephew", {"relation_raw": "Sibling's Child", "inverse": "Aunt / Uncle", "generation": -1, "category": "collateral"})
                        for cf in by_key[target]["family"]:
                            cousin = cf.get("target")
                            if cousin and cousin != s["key"] and cousin in by_key and (cf.get("generation") or 0) < 0:
                                add_family(s, cousin, "Cousin", {"relation_raw": "Cousin", "inverse": "Cousin", "generation": 0, "category": "cousin"})
                                add_family(by_key[cousin], s["key"], "Cousin", {"relation_raw": "Cousin", "inverse": "Cousin", "generation": 0, "category": "cousin"})

    # 5. Every household member has a relationship entry, like a fresh save.
    hh_groups = {}
    for s in sims:
        hh_groups.setdefault(s["household_key"], []).append(s)
    for group in hh_groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                add_relationship(a, b["key"], "Household member", 15, 0)
                add_relationship(b, a["key"], "Household member", 15, 0)

    # 6. Specific household relationship bits (Roommate, Lovers, BFF, ...) and
    # the game's cross-household starting relationships already come from the
    # SDK's PremadeHouseholdTemplate / PremadeSimRelationships extraction in
    # backend/templatedata.py, so no separate tuning JSON is needed here.

    # 7. Club memberships (PremadeSimTemplate.clubs) are not modelled by the
    # SDK yet — see docs/sdk-migration.md for the gap list.
    try:
        from . import clubs as clubs_mod

        clubs_mod.apply(sims)
    except Exception:
        pass

    # 8. The EP21 `loot_WorldEP21_NPC_*` tunings seed the Bellacorde NPC social
    # and family graph: exact friendship/romance values, sentiments, family and
    # romance tropes, plus the cross-household Capp/Monty/Thebe/Abrantes links.
    try:
        from . import npc_relations as npc_mod

        npc_mod.apply(sims)
    except Exception:
        pass

    # 10. Premade scandal secrets (SimInfoFixup -> secrets_fixup_action). These
    # are hidden connections, not scores; paired secrets become secret bits.
    try:
        from . import secrets as secrets_mod

        secrets_mod.apply(sims)
    except Exception:
        pass

    # 11. The game's tapestry ancestors now come from
    # ``PremadeBundle.family_tree()`` in backend/templatedata.py, including the
    # typed parent/sibling links and ``Catalog.family_fixups``.  No surname
    # heuristic is applied here.

    # Identity already records gender; the CAS gender trait is not a gameplay
    # trait and should not appear in the trait list.
    try:
        _apply_premade_milestones(sims)
        _apply_premade_careers(sims)
    except Exception:
        pass
    for sim in sims:
        if sim.get("traits"):
            sim["traits"] = [t for t in sim["traits"]
                             if not (t.get("tuning") or "").lower().startswith("trait_gender")]
        _add_icons(sim)

    _WORLD_CACHE = {"sims": sims, "households": len(households), "save": None, "save_label": "game premades"}
    return _WORLD_CACHE


def _apply_premade_milestones(sims) -> None:
    """Apply the starting milestones seeded by install SimInfoFixup tunings."""
    path = APP_DIR / "data" / "premade_milestones.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    by_name = {}
    for entry in payload.get("sims", []):
        key = (entry.get("first"), entry.get("last"))
        if key[0] and key[1]:
            by_name[key] = entry.get("milestones") or []
    for sim in sims:
        milestones = by_name.get((sim.get("first"), sim.get("last")))
        if not milestones:
            continue
        have = {row.get("id") for row in sim.get("milestones", [])}
        for milestone in milestones:
            if milestone.get("id") not in have:
                sim.setdefault("milestones", []).append(json.loads(json.dumps(milestone)))
        sim["milestone_source"] = "premade"


def _apply_premade_careers(sims) -> None:
    """Apply careers and aspiration tracks from PremadeSimTemplate.career_level."""
    path = APP_DIR / "data" / "premade_careers.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    by_name = {}
    for entry in payload.get("sims", []):
        key = (entry.get("first"), entry.get("last"))
        if key[0] and key[1]:
            by_name[key] = entry
    for sim in sims:
        entry = by_name.get((sim.get("first"), sim.get("last")))
        if not entry:
            continue
        career = entry.get("career")
        if career and not sim.get("career"):
            sim["career"] = {
                "id": career.get("career_id") or 0,
                "label": career.get("career") or "",
                "level": career.get("level") or 1,
                "modded": False,
            }
            if career.get("track"):
                sim["career_track"] = {
                    "id": career.get("track_id") or 0,
                    "label": career.get("track"),
                    "modded": False,
                }
            else:
                sim["career_track"] = None
        track = entry.get("aspiration_track")
        if track and track.get("label") and not sim.get("aspiration_track"):
            # The household template's aspiration track is the actual premade
            # value; the sim template's primary_aspiration is only a fallback.
            sim["aspiration_track"] = track["label"]
        identity = entry.get("gender_identity")
        if identity:
            if identity != sim.get("gender") and not sim.get("frame"):
                sim["frame"] = sim.get("gender")
            sim["gender"] = identity
        if entry.get("pronouns"):
            sim["pronouns"] = entry["pronouns"]
        if entry.get("pronoun_words"):
            sim["pronoun_words"] = entry["pronoun_words"]
        # The household trait tracker omits some reward/aspiration traits that
        # are explicit in the PremadeSimTemplate. Add those without inventing
        # anything: the template is still an install file.
        existing = {
            ((t.get("tuning") or "").lower(), (t.get("label") or "").lower())
            for t in sim.get("traits", [])
        }
        for trait in entry.get("template_traits", []) or []:
            tuning = (trait.get("tuning") or "").lower()
            label = (trait.get("label") or "").lower()
            if not tuning or not label:
                continue
            if (tuning, label) in existing or any(
                (t.get("tuning") or "").lower() == tuning
                or (t.get("label") or "").lower() == label
                for t in sim.get("traits", [])
            ):
                continue
            sim.setdefault("traits", []).append({
                "id": trait.get("id") or 0,
                "label": trait.get("label") or "",
                "modded": False,
                "pack": "",
                "tuning": trait.get("tuning") or "",
                "trait_type": trait.get("trait_type", ""),
                "source": "premade_template",
            })
            existing.add((tuning, label))


def _load_premade_dynasties() -> dict:
    path = APP_DIR / "data" / "premade_dynasties.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"dynasties": []}


_ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def _family_surname(last: str) -> str:
    """Family name, ignoring regnal suffixes such as ``Thebe V``."""
    parts = [p for p in (last or "").split() if p]
    while parts and parts[-1].strip(".").lower() in _ROMAN:
        parts.pop()
    return parts[-1] if parts else ""


def _attach_premade_ancestors(sims: list[dict]) -> None:
    """Attach the game's dynasty-tapestry ancestors to matching family names.

    Ancestors are first matched by family name (Capp, Thebe, Ananou, ...), then
    propagated along parent edges so children of an heiress keep the maternal
    lineage even when their surname changed (e.g. Juliette Monty, née Capp).
    """
    ancestors = _load_premade_dynasties().get("ancestors") or []
    if not ancestors:
        return
    for sim in sims:
        surname = _family_surname(sim.get("last"))
        if not surname:
            continue
        hits = [a for a in ancestors
                if (a.get("surname") or "").lower() == surname.lower()]
        if hits:
            # The SDK family tree now supplies the connected ancestors; this
            # surname pass only adds legacy title/region details that are not
            # part of the SDK model.
            existing = sim.setdefault("ancestors", [])
            have = {row.get("sim") for row in existing}
            for hit in hits:
                if hit.get("sim") not in have:
                    existing.append(json.loads(json.dumps(hit)))
                    have.add(hit.get("sim"))
    by_key = {s.get("key"): s for s in sims}
    changed = True
    while changed:
        changed = False
        for sim in sims:
            have = {a.get("sim") for a in sim.get("ancestors", [])}
            for link in sim.get("family", []) or []:
                if (link.get("relation") or "").lower() not in ("father", "mother", "parent"):
                    continue
                parent = by_key.get(link.get("target"))
                if not parent:
                    continue
                for a in parent.get("ancestors", []) or []:
                    if a.get("sim") in have:
                        continue
                    sim.setdefault("ancestors", []).append(json.loads(json.dumps(a)))
                    have.add(a.get("sim"))
                    changed = True


def seed_dynasties(sims: dict) -> list[dict]:
    """The dynasties the game defines (EP21 DynastySeed tuning).

    Membership uses the exact ``PremadeSimTemplate.dynasty`` field (seed +
    role), with the household-template tag as a fallback for the base
    Goth/Landgraab households. Ancestors come from ``TunablePremadeAncestor``.
    """
    from .templatedata import dynasty_tuning

    extracted = {d.get("name"): d for d in _load_premade_dynasties().get("dynasties", [])}
    by_norm = {}
    for key, sim in sims.items():
        n = re.sub(r"[^a-z0-9]", "", f"{sim.get('first', '')}{sim.get('last', '')}".lower())
        by_norm.setdefault(n, []).append(key)
    by_name = {}
    for key, sim in sims.items():
        d = sim.get("game_dynasty")
        if d:
            by_name.setdefault(d, []).append(key)

    out = []
    for d in dynasty_tuning():
        name = d.get("name") or ""
        exact = extracted.get(name) or {}
        members = set(by_name.get(name, []))
        roles = {}
        for m in exact.get("members", []):
            n = re.sub(r"[^a-z0-9]", "", (m.get("sim") or "").lower())
            keys = by_norm.get(n, [])
            if len(keys) == 1:
                members.add(keys[0])
                if m.get("role"):
                    roles[keys[0]] = m["role"]
        members = sorted(members)
        head = next((k for k in members if roles.get(k) == "head"), "")
        if not head:
            head = next((k for k in members if not any(
                (f.get("generation") or 0) > 0 for f in sims[k].get("family", []) or []
            )), members[0] if members else "")
        if head:
            for k in members:
                if k == head:
                    continue
                if not any(r.get("target") == k for r in sims[head].get("relationships", [])):
                    bit = {"id": f"dynasty:{name}", "label": name, "modded": False}
                    sims[head].setdefault("relationships", []).append({
                        "target": k, "label": f"Dynasty member: {name}",
                        "friendship": 0, "romance": 0, "bits": [bit],
                        "from_game": True, "source": "dynasty",
                    })
                    sims[k].setdefault("relationships", []).append({
                        "target": head, "label": f"Dynasty member: {name}",
                        "friendship": 0, "romance": 0, "bits": [bit],
                        "from_game": True, "source": "dynasty",
                    })
        out.append({
            "id": f"dynasty:{name.lower()}",
            "name": f"{name} dynasty",
            "description": d.get("description", ""),
            "head": head,
            "members": members,
            "roles": roles,
            "ancestors": exact.get("ancestors", []),
            "ideals": exact.get("ideals", []),
            "skills": exact.get("skills", []),
            "allies": exact.get("allies", []),
            "rivals": exact.get("rivals", []),
            "households": sorted({sims[k].get("household") or sims[k].get("last") for k in members}),
            "generations": 1,
            "from_game": True,
        })
    if not out:
        for name, members in by_name.items():
            out.append({"id": f"dynasty:{name.lower()}", "name": f"{name} dynasty", "description": "",
                        "head": members[0] if members else "", "members": members,
                        "households": [], "generations": 1, "from_game": True})
    return out


def sim_template_for(project: dict, key: str) -> dict | None:
    """Return the original game values for a sim, respecting the project origin.

    * clean_world -> the clean premade household template
    * save        -> the sim as it appears in that save (plus its Tray version)
    * tray        -> the sim's Tray household version
    """
    origin = project.get("origin") or {}
    mode = origin.get("mode", "clean_world")
    sim = (project.get("sims") or {}).get(key)
    if not sim:
        return None
    if mode == "clean_world" or mode == "empty":
        return next((s for s in seed_premade_world()["sims"] if s["key"] == key), None)
    if mode == "save":
        try:
            from . import saves as saves_mod
            parsed = saves_mod.parse_save(origin.get("file") or "")
            match = next((s for s in parsed.get("sims", [])
                          if s["first"] == sim.get("first") and s["last"] == sim.get("last")), None)
            if match:
                rich = enrich_save_sims(parsed.get("sims", []))
                overlay = rich.get((sim["first"].lower(), sim["last"].lower(),
                                    (sim.get("household") or sim["last"]).lower()))
                if overlay:
                    match = {**match, **{k: v for k, v in overlay.items() if v is not None}}
                match["key"] = key
                return match
        except Exception:
            pass
        return None
    if mode == "tray":
        ident = sim.get("source_ref")
        try:
            hh = get_household(ident) if ident else None
            if hh:
                return next(({**s, "key": key} for s in hh["sims"]
                             if s["first"] == sim.get("first") and s["last"] == sim.get("last")), None)
        except Exception:
            pass
    return None


def enrich_premade_project(project: dict) -> bool:
    """Upgrade older projects with corrected derived data (one-time migration)."""
    version = project.get("data_version", 0)
    if version >= 32:
        return False
    # Only clean-world projects are built from the premade household templates.
    mode = (project.get("origin") or {}).get("mode")
    if mode not in (None, "", "clean_world", "empty"):
        project["data_version"] = 32
        return False
    try:
        fresh = {s["key"]: s for s in seed_premade_world()["sims"]}
    except Exception:
        return False
    legacy_tray_milestones = project.get("data_version", 0) < 24
    sims = project.get("sims", {}) or {}
    for key, sim in sims.items():
        f = fresh.get(key)
        if not f:
            continue
        for field in ("likes", "dislikes", "career_track", "aspiration_track",
                      "household_image", "household_image_mask",
                      "household_description", "lot", "lot_description",
                      "game_dynasty", "degrees", "milestones", "ancestors", "secrets",
                      "pronouns", "pronoun_words", "frame"):
            if not sim.get(field) and f.get(field):
                sim[field] = f[field]
        if f.get("gender"):
            sim["gender"] = f["gender"]
        if f.get("aspiration_track"):
            sim["aspiration_track"] = f["aspiration_track"]
        if version < 32:
            # v29: the install only stores an aspiration track. Remove the
            # specific aspiration that older builds guessed from it.
            if f.get("aspiration_track") and not f.get("aspiration"):
                sim["aspiration"] = None
            # Refresh the trait list with the corrected catalog (Kleptomaniac,
            # Childish, reward traits, internal-trait filtering) and the age,
            # species and occult values from the rebuilt template data.
            sim["traits"] = json.loads(json.dumps(f.get("traits", [])))
            sim["age"] = f.get("age", sim.get("age"))
            sim["species"] = f.get("species", sim.get("species"))
            sim["occult"] = f.get("occult", sim.get("occult"))
        if not sim.get("aspiration") and f.get("aspiration"):
            sim["aspiration"] = f["aspiration"]
        # Dynasty membership is derived from the game's template names; refresh
        # it even when an older (looser) rule produced a value.
        sim["game_dynasty"] = f.get("game_dynasty")
        sim["household"] = f.get("household") or sim.get("household")
        # Re-derive the complete relationship/family graph (fixes earlier bugs).
        # Deep-copy so cached template lists are never shared between sims.
        sim["relationships"] = json.loads(json.dumps(f["relationships"]))
        sim["family"] = json.loads(json.dumps(f["family"]))
        sim["skills"] = json.loads(json.dumps(f.get("skills", [])))
        if legacy_tray_milestones:
            sim["milestones"] = []
            sim.pop("milestone_source", None)
        _add_icons(sim)
        # Ancestors and secrets are game-derived too; refresh them even if an
        # older build already wrote a partial list.
        sim["ancestors"] = json.loads(json.dumps(f.get("ancestors", [])))
        sim["secrets"] = json.loads(json.dumps(f.get("secrets", [])))
        if sim.get("traits"):
            sim["traits"] = [t for t in sim["traits"]
                             if not (t.get("tuning") or "").lower().startswith("trait_gender")]
        # Clean-save sims always use the game's own household picture; no Tray
        # name matching and no guessed per-sim crops.
        sim["image"] = f.get("image", "")
        sim["image_mask"] = f.get("image_mask", "")
        sim["image_kind"] = f.get("image_kind", "")
        sim.pop("portrait_crop", None)
        sim.pop("portrait_options", None)
    # Add any standard sims that were missing from older projects.
    for key, f in fresh.items():
        if key not in sims:
            sims[key] = json.loads(json.dumps(f))
    # Drop duplicate template copies (same sim in the same household) and
    # stale copies whose household/sim id changed between game data builds.
    fresh_names = {(f["first"], f["last"], f.get("household")) for f in fresh.values()}
    fresh_pairs = {(f["first"].lower(), f["last"].lower()) for f in fresh.values()}
    for key in [k for k in sims if k not in fresh]:
        s = sims[key]
        if s.get("source") not in (None, "premade"):
            continue
        pair = ((s.get("first") or "").lower(), (s.get("last") or "").lower())
        if (s.get("first"), s.get("last"), s.get("household")) in fresh_names or pair in fresh_pairs:
            sims.pop(key, None)
    try:
        _apply_premade_careers(sims.values())
    except Exception:
        pass
    project["sims"] = sims
    project["data_version"] = 32
    user_dynasties = [d for d in project.get("dynasties", []) if not d.get("from_game")]
    project["dynasties"] = seed_dynasties(sims) + user_dynasties
    if not project.get("origin"):
        project["origin"] = {"mode": "clean_world", "label": "clean new-save world", "file": None}
    return True


def seed_world_template(max_saves: int = 8):
    """Find the save that best represents the premade world and return its sims.

    The game places premades in a new save; the closest real-world snapshot is
    an existing save. We scan the newest saves, count known premade surnames,
    and use the richest one as the world template.
    """
    from . import saves as saves_mod

    candidates = [
        s
        for s in saves_mod.list_saves()
        if s.get("size", 0) > 1_000_000
    ][:max_saves]
    best = None
    best_score = -1
    for item in candidates:
        try:
            parsed = saves_mod.parse_save(item["file"])
        except Exception:
            continue
        sims = [s for s in parsed.get("sims", []) if (s.get("last") or "").lower() in PREMADE_NAMES]
        score = len({(s.get("last") or "").lower() for s in sims})
        if score > best_score:
            best = (item, sims)
            best_score = score
    if not best:
        return {"sims": [], "save": None, "households": 0}
    item, sims = best
    present = {(s.get("last") or "").lower() for s in sims}
    missing = PREMADE_NAMES - present
    filled = 0
    if missing:
        for tray_item in sorted(list_tray(), key=lambda x: x.get("modified", 0), reverse=True):
            name = (tray_item.get("household") or "").lower()
            if name not in missing:
                continue
            rich = get_household(tray_item["id"])
            if not rich or rich.get("quality") != "full" or not rich.get("sims"):
                continue
            sims.extend(rich["sims"])
            missing.discard(name)
            filled += 1
            if not missing:
                break
    return {
        "sims": sims,
        "save": item["file"],
        "save_label": item["slot"],
        "households": len({(s.get("household") or s.get("last") or "").lower() for s in sims}),
        "filled": filled,
    }


def enrich_save_sims(sims: list[dict]) -> dict[tuple[str, str, str], dict]:
    """Match save sims to Tray households that have the same name/household.

    Only candidate Tray households are parsed, so this stays fast.
    """
    if not sims:
        return {}
    wanted = {(s["first"].lower(), s["last"].lower(), (s.get("household") or s["last"]).lower()) for s in sims}
    wanted_names = {(s["first"].lower(), s["last"].lower()) for s in sims}
    households = {(s.get("household") or s["last"]).lower() for s in sims}
    index = {}
    for item in list_tray():
        names = {(s["first"].lower(), s["last"].lower()) for s in item["sims"]}
        hh = {s["last"].lower() for s in item["sims"]} | {item["household"].lower()}
        if not (names & wanted_names) or not (hh & households):
            continue
        rich = get_household(item["id"])
        if not rich or rich.get("quality") != "full":
            continue
        for sim in rich["sims"]:
            key = (sim["first"].lower(), sim["last"].lower(), sim["household"].lower())
            if key in wanted:
                index.setdefault(key, sim)
    return index
