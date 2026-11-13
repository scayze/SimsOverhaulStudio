"""Extract the starting life milestones the game seeds for premade sims.

The source is ``SimInfoFixup`` with a ``developmental_milestone_ops_fixup_action``
referenced from ``PremadeSimTemplate._fixups``. These are install-file seeds, not
Tray/save data.

Run from the project root:
    python tools/build_premade_milestones.py
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
from backend.catalog import load_catalog
from backend.templatedata import stbl_index
from combinedtuning import decode_combined_tuning

TOKEN = "developmental_milestone_ops_fixup_action"
STBL = stbl_index()
MILESTONES = {m["id"]: m for m in load_catalog()["catalog"]["milestones"]}


def stbl_text(value):
    if not value:
        return ""
    value = value.strip()
    try:
        key = int(value, 16) if value.lower().startswith("0x") else int(value)
    except ValueError:
        return ""
    return STBL.get(key) or ""


def resolve(node, shared, depth=0):
    if depth > 8 or node is None:
        return None
    if node.tag == "r":
        return resolve(shared.get(node.get("x")), shared, depth + 1)
    if node.tag in ("T", "E"):
        return node.text.strip() if node.text else None
    if node.tag == "V":
        return resolve(node[0], shared, depth + 1) if len(node) else None
    if node.tag == "U":
        return {c.get("n"): resolve(c, shared, depth + 1) for c in node if c.get("n")}
    return None


def display_from_template(name):
    body = (name or "").split("_")[-1]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", body).strip()


def collect_milestones(node, shared, out, depth=0):
    if depth > 8 or node is None:
        return
    if node.tag == "r":
        ref = shared.get(node.get("x"))
        if ref is None:
            return
        if ref.tag == "T" and ref.text and ref.text.strip().isdigit():
            out.append(int(ref.text.strip()))
        else:
            collect_milestones(ref, shared, out, depth + 1)
        return
    if node.tag == "T":
        if node.text and node.text.strip().isdigit():
            out.append(int(node.text.strip()))
        return
    for child in node:
        collect_milestones(child, shared, out, depth + 1)


sims = {}
seen = set()
files = list(paths.game.rglob("*FullBuild0.package")) + list(paths.game.rglob("*DeltaBuild0.package"))
for p in dict.fromkeys(files):
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
        if TOKEN.encode() not in raw:
            continue
        key = (str(p), e.instance)
        if key in seen:
            continue
        seen.add(key)
        try:
            xml = decode_combined_tuning(raw)
        except Exception:
            continue
        if TOKEN not in xml:
            continue
        try:
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}

        owner_by_fixup = {}
        sim_info = {}
        for sim_el in root.iter("I"):
            if sim_el.get("c") != "PremadeSimTemplate":
                continue
            name = sim_el.get("n") or ""
            first = last = ""
            for child in sim_el:
                if child.tag == "U" and child.get("n") == "_sim_creation_info":
                    for sub in child:
                        if sub.tag == "T" and sub.get("n") == "first_name":
                            first = stbl_text(sub.text)
                        elif sub.tag == "T" and sub.get("n") == "last_name":
                            last = stbl_text(sub.text)
                        elif sub.tag == "r" and sub.get("n") == "first_name":
                            first = stbl_text(resolve(sub, shared))
                        elif sub.tag == "r" and sub.get("n") == "last_name":
                            last = stbl_text(resolve(sub, shared))
                        elif sub.tag == "V" and sub.get("n") == "last_name":
                            for ss in sub.iter():
                                if ss.tag == "T" and ss.get("n") == "specify_last_name":
                                    last = stbl_text(ss.text)
                elif child.get("n") == "_fixups":
                    for sub in child.iter():
                        value = None
                        if sub.tag == "T" and sub.text and sub.text.strip().isdigit():
                            value = sub.text.strip()
                        elif sub.tag == "r":
                            ref = shared.get(sub.get("x"))
                            if ref is not None and ref.tag == "T" and ref.text and ref.text.strip().isdigit():
                                value = ref.text.strip()
                        if value:
                            owner_by_fixup[value] = name
            sim_info[name] = (first, last)

        for el in root.iter("I"):
            if el.get("c") != "SimInfoFixup":
                continue
            actions = []
            for sub in el.iter("V"):
                if sub.get("t") == TOKEN:
                    actions.append(sub)
            if not actions:
                continue
            owner_template = owner_by_fixup.get(el.get("s"))
            if not owner_template:
                continue
            ids = []
            for action in actions:
                collect_milestones(action, shared, ids)
            ids = list(dict.fromkeys(ids))
            if not ids:
                continue
            first, last = sim_info.get(owner_template, ("", ""))
            name = f"{first} {last}".strip() or display_from_template(owner_template)
            entry = sims.setdefault(owner_template, {
                "template": owner_template,
                "name": name,
                "first": first,
                "last": last,
                "milestones": [],
            })
            for mid in ids:
                item = MILESTONES.get(mid)
                if not item:
                    continue
                if not any(m["id"] == mid for m in entry["milestones"]):
                    entry["milestones"].append({
                        "id": mid,
                        "label": item["label"],
                        "modded": item.get("modded", False),
                        "pack": item.get("pack_label", ""),
                    })

payload = {
    "source": "SimInfoFixup.developmental_milestone_ops_fixup_action",
    "sims": sorted(sims.values(), key=lambda s: (s["name"], s["template"])),
}
Path("data/premade_milestones.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("sims with seeded milestones", len(payload["sims"]))
for s in payload["sims"][:20]:
    print(s["name"], len(s["milestones"]), [m["label"] for m in s["milestones"][:4]])
