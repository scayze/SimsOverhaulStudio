"""Extract the game's dynasty membership, roles and premade ancestors.

Sources:
* ``PremadeSimTemplate.dynasty`` -> exact dynasty seed + is_head/is_heir/
  is_black_sheep.
* ``DynastySeed`` -> name, description, ideals, skills, allies, rivals, perks.
* ``TunablePremadeAncestor`` -> the deceased ancestors shown in the family-tree
  tapestry (name, gender, death type, title, region, thumbnail).

Run from the project root:
    python tools/build_premade_dynasties.py
"""
import sys
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.settings import paths
from backend.dbpf import DBPF
from backend.catalog import SIMDATA_TYPE, TOKEN_RE
from backend.templatedata import stbl_index
from combinedtuning import decode_combined_tuning

stbl = stbl_index()

# instance -> tuning name (for death traits, ideals/skills, perks)
tuning_names = {}
for p in paths.game.rglob("*.package"):
    if "thumbnails" in p.name.lower() or "Strings" in p.name:
        continue
    try:
        db = DBPF(p)
    except Exception:
        continue
    for e, data in db.iter_type(SIMDATA_TYPE):
        if not data:
            continue
        toks = [t.decode("ascii", "replace") for t in TOKEN_RE.findall(data)]
        if toks:
            tuning_names[e.instance] = toks[-1]


def stbl_text(value):
    if not value:
        return ""
    value = value.strip()
    try:
        key = int(value, 16) if value.lower().startswith("0x") else int(value)
    except ValueError:
        return ""
    return stbl.get(key) or ""


def resolve(node, shared, depth=0):
    if depth > 8 or node is None:
        return None
    if node.tag == "r":
        return resolve(shared.get(node.get("x")), shared, depth + 1)
    if node.tag in ("T", "E"):
        return node.text.strip() if node.text else None
    if node.tag == "U":
        return {c.get("n"): resolve(c, shared, depth + 1) for c in node if c.get("n")}
    if node.tag == "V":
        return resolve(node[0], shared, depth + 1) if len(node) else None
    return None


def humanize(name):
    if not name:
        return ""
    for prefix in ("dynastyValue_Ideal_", "dynastyValue_Skill_", "dynastyValue_",
                   "ghost_", "trait_Death_", "trait_", "loot_", "buff_",
                   "careerRewards_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if name.lower().startswith("ghost"):
        name = name[5:].lstrip("_ ")
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ").strip()


ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def family_surname(name):
    """The family name of an ancestor, ignoring trailing regnal numerals."""
    parts = [p for p in (name or "").split() if p]
    while parts and parts[-1].strip(".").lower() in ROMAN:
        parts.pop()
    return parts[-1] if parts else ""


def tuning_name_from(value):
    try:
        key = int(value)
    except (TypeError, ValueError):
        return ""
    return tuning_names.get(key, str(key))


dynasties = {}
members = {}
ancestors = {}

for p in paths.game.rglob("*.package"):
    if "thumbnails" in p.name.lower() or "Strings" in p.name:
        continue
    try:
        db = DBPF(p)
    except Exception:
        continue
    for e in db.entries:
        if e.type != 0x62E94D38:
            continue
        try:
            raw = db.read_entry(e)
        except Exception:
            continue
        if not any(k in raw for k in (b"DynastySeed", b"TunablePremadeAncestor")):
            continue
        if len(raw) > 20_000_000:
            continue
        try:
            xml = decode_combined_tuning(raw)
            if not any(k in xml for k in ("DynastySeed", "TunablePremadeAncestor")):
                continue
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}

        # dynasty seeds
        for el in root.iter("I"):
            if el.get("c") != "DynastySeed":
                continue
            sid = el.get("s")
            name = desc = ""
            ideals, skills, allies, rivals, perks = [], [], [], [], []
            for child in el:
                key = child.get("n")
                if key == "name":
                    name = stbl_text(child.text)
                elif key == "dynasty_description":
                    desc = stbl_text(child.text)
                elif key in ("dynasty_ideals", "dynasty_skills", "unlocked_perks", "allies", "rivals"):
                    vals = []
                    for sub in child:
                        v = resolve(sub, shared)
                        if isinstance(v, str) and v.isdigit():
                            vals.append(int(v))
                    if key == "dynasty_ideals":
                        ideals = [humanize(tuning_name_from(v)) for v in vals]
                    elif key == "dynasty_skills":
                        skills = [humanize(tuning_name_from(v)) for v in vals]
                    elif key == "unlocked_perks":
                        perks = [humanize(tuning_name_from(v)) for v in vals]
                    elif key == "allies":
                        allies = vals
                    elif key == "rivals":
                        rivals = vals
            if name:
                dynasties[int(sid)] = {
                    "id": int(sid), "name": name, "description": desc,
                    "ideals": ideals, "skills": skills, "perks": perks,
                    "allies": allies, "rivals": rivals,
                }

        # exact dynasty members + roles
        for el in root.iter("I"):
            if el.get("c") != "PremadeSimTemplate":
                continue
            fname = lname = None
            dynasty_val = None
            for child in el:
                if child.tag == "U" and child.get("n") == "_sim_creation_info":
                    for sub in child:
                        if sub.tag == "T" and sub.get("n") == "first_name" and sub.text:
                            fname = stbl_text(sub.text)
                        elif sub.tag == "T" and sub.get("n") == "last_name" and sub.text:
                            lname = stbl_text(sub.text)
                        elif sub.tag == "r" and sub.get("n") == "first_name":
                            fname = stbl_text(resolve(sub, shared))
                        elif sub.tag == "r" and sub.get("n") == "last_name":
                            lname = stbl_text(resolve(sub, shared))
                        elif sub.tag == "V" and sub.get("n") == "last_name":
                            for ss in sub.iter():
                                if ss.tag == "T" and ss.get("n") == "specify_last_name" and ss.text:
                                    lname = stbl_text(ss.text)
                elif child.get("n") == "dynasty":
                    dynasty_val = resolve(child, shared)
            if not fname or not lname or not isinstance(dynasty_val, dict):
                continue
            seed = dynasty_val.get("seed")
            try:
                seed = int(seed)
            except (TypeError, ValueError):
                continue
            role = ""
            if dynasty_val.get("is_head") == "True":
                role = "head"
            elif dynasty_val.get("is_heir") == "True":
                role = "heir"
            elif dynasty_val.get("is_black_sheep") == "True":
                role = "black sheep"
            key = (fname + lname, seed)
            if key not in members or (role and not members[key]):
                members[key] = role

        # premade ancestors
        for el in root.iter("I"):
            if el.get("c") != "TunablePremadeAncestor":
                continue
            name = gender = title = region = death = ""
            for child in el:
                key = child.get("n")
                v = resolve(child, shared)
                if key == "full_name":
                    name = stbl_text(v)
                elif key == "gender":
                    gender = v or ""
                elif key == "death_trait":
                    death = humanize(tuning_name_from(v))
                elif key == "kingdom_data" and isinstance(v, dict):
                    title = stbl_text(v.get("localized_title"))
                    region = stbl_text(v.get("region_name"))
            if name:
                key = (name, el.get("s"))
                ancestors[key] = {
                    "sim": name, "surname": family_surname(name),
                    "gender": gender, "death": death,
                    "title": title, "region": region, "template": el.get("n"),
                }

# resolve allies/rivals to dynasty names
names = {d["id"]: d["name"] for d in dynasties.values()}
for d in dynasties.values():
    d["allies"] = [names.get(v, str(v)) for v in d.get("allies", [])]
    d["rivals"] = [names.get(v, str(v)) for v in d.get("rivals", [])]

# attach members/ancestors to dynasties
members_list = [{"sim": k[0], "seed": k[1], "role": v} for k, v in members.items()]
anc_list = list(ancestors.values())
for d in dynasties.values():
    d["members"] = [m for m in members_list if m["seed"] == d["id"]]
    d["ancestors"] = [a for a in anc_list if d["name"].lower() in a["sim"].lower().replace(" ", "")]

payload = {"source": "PremadeSimTemplate.dynasty / DynastySeed / TunablePremadeAncestor",
           "dynasties": sorted(dynasties.values(), key=lambda d: d["name"]),
           "ancestors": anc_list}
Path("data/premade_dynasties.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("dynasties", len(dynasties), "members", len(members_list), "ancestors", len(anc_list))
for d in payload["dynasties"]:
    print(d["name"], "members", [(m["sim"], m["role"]) for m in d["members"]],
          "ancestors", [a["sim"] for a in d["ancestors"]])
