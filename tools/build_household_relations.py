"""Extract the household-level relationship bits from PremadeHouseholdTemplate.

The binary household templates (0xB3C438F0) only carry genealogy and
spouse/fiance fields. The *specific* relationship between household members
(roommate, lovers, lovebirds, disliked, ...) is stored in the
``PremadeHouseholdTemplate`` tuning's ``_household_relationship`` list.

Run from the project root:
    python tools/build_household_relations.py
"""
import sys
import json
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

# relationship bit instance -> tuning name
bit_names = {}
for p in paths.game.rglob("*.package"):
    if "thumbnails" in p.name.lower():
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
            bit_names[e.instance] = toks[-1]
print("tuning names", len(bit_names))

pack_filter = sys.argv[1].lower() if len(sys.argv) > 1 else ""
households = {}
clubs = {}
club_names = {}
for p in paths.game.rglob("*.package"):
    if pack_filter and pack_filter not in str(p).lower():
        continue
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
        if b"PremadeHouseholdTemplate" not in raw:
            continue
        if len(raw) > 40_000_000:
            print("skip huge", p.name, len(raw))
            continue
        try:
            xml = decode_combined_tuning(raw)
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception as exc:
            print("decode fail", p.name, type(exc).__name__, exc, flush=True)
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}

        # sim template instance -> display name (first+last, resolved through
        # the English STBL) with the tuning name as fallback.
        sim_templates = {}

        def _stbl_name(text):
            if not text:
                return None
            text = text.strip()
            try:
                key = int(text, 16) if text.lower().startswith("0x") else int(text)
            except ValueError:
                return None
            return stbl.get(key)

        for el in root.iter("I"):
            if el.get("c") != "PremadeSimTemplate":
                continue
            n = el.get("n") or ""
            short = n.split("simTemplate_", 1)[-1]
            short = short.split("_", 1)[-1] if short.lower().startswith("ep") else short
            first = last = None
            for child in el:
                if child.tag != "U" or child.get("n") != "_sim_creation_info":
                    continue
                for sub in child:
                    if sub.tag == "T" and sub.get("n") == "first_name" and sub.text:
                        first = _stbl_name(sub.text)
                    elif sub.tag == "T" and sub.get("n") == "last_name" and sub.text:
                        last = _stbl_name(sub.text)
                    elif sub.tag == "V" and sub.get("n") == "last_name":
                        for ss in sub.iter():
                            if ss.tag == "T" and ss.get("n") == "specify_last_name" and ss.text:
                                last = _stbl_name(ss.text)
            sim_templates[el.get("s")] = (first + last) if (first and last) else short
            sim_templates[el.get("n")] = (first + last) if (first and last) else short

        def resolve_ref(node):
            return shared.get(node.get("x")) if node.tag == "r" else node

        def collect(node, bits, tags, enums, depth=0):
            if depth > 5:
                return
            for child in node:
                if child.tag == "T" and child.text:
                    text = child.text.strip()
                    if text.isdigit() and int(text) in bit_names:
                        bits.append(int(text))
                elif child.tag == "E" and child.text:
                    text = child.text.strip()
                    if text.startswith("household_member_"):
                        tags.append(text)
                    elif text:
                        enums.append(text)
                elif child.tag == "r":
                    ref = shared.get(child.get("x"))
                    if ref is not None:
                        if ref.tag == "T" and ref.text:
                            text = ref.text.strip()
                            if text.isdigit():
                                if int(text) in bit_names:
                                    bits.append(int(text))
                            elif text.startswith("household_member_"):
                                tags.append(text)
                        elif ref.tag == "E" and ref.text:
                            text = ref.text.strip()
                            if text.startswith("household_member_"):
                                tags.append(text)
                            elif text:
                                enums.append(text)
                        else:
                            collect(ref, bits, tags, enums, depth + 1)
                elif child.tag in ("L", "U"):
                    collect(child, bits, tags, enums, depth + 1)

        for el in root.iter("I"):
            if el.get("c") != "PremadeHouseholdTemplate":
                continue
            name = el.get("n") or ""
            members = {}
            for child in el:
                if child.tag == "L" and child.get("n") == "_household_members":
                    for sub in child:
                        tag = st = None
                        for x in sub:
                            if x.tag == "r" and x.get("n") == "household_member_tag":
                                ref = shared.get(x.get("x"))
                                if ref is not None and ref.text:
                                    tag = ref.text.strip()
                            elif x.tag == "T" and x.get("n") == "sim_template" and x.text:
                                st = x.text.strip()
                            elif x.tag == "r" and x.get("n") == "sim_template":
                                ref = shared.get(x.get("x"))
                                if ref is not None and ref.tag == "T" and ref.text:
                                    st = ref.text.strip()
                        if tag and st:
                            members[tag] = sim_templates.get(st, st)
            rels = []
            rel_nodes = [child for child in el if child.get("n") == "_household_relationship"]

            def expand(node, depth=0):
                if depth > 5 or node is None:
                    return []
                if node.tag == "r":
                    return expand(shared.get(node.get("x")), depth + 1)
                if node.tag == "U":
                    return [node]
                out = []
                for sub in node:
                    out += expand(sub, depth + 1)
                return out

            for rel_node in rel_nodes:
                top = shared.get(rel_node.get("x")) if rel_node.tag == "r" else rel_node
                for entry in expand(top):
                    bits, tags, enums = [], [], []
                    collect(entry, bits, tags, enums)
                    tags = list(dict.fromkeys(tags))
                    if len(tags) >= 2 and (bits or enums):
                        payload_rel = {
                            "a": tags[0],
                            "b": tags[1],
                            "bits": list(dict.fromkeys(bit_names[b] for b in bits)),
                        }
                        fam = next((e for e in enums if e.lower() in (
                            "father", "mother", "sibling", "brother", "sister",
                            "son", "daughter", "aunt", "uncle", "niece", "nephew",
                            "grandfather", "grandmother", "grandparent",
                            "cousin", "husband", "wife",
                        )), None)
                        if fam:
                            payload_rel["family"] = fam
                        rels.append(payload_rel)
            if members:
                print("  found", name, "members", len(members), "rels", len(rels), flush=True)
            if members and rels:
                households[name] = {"members": members, "relationships": rels}

        # --- club memberships (PremadeSimTemplate.clubs) ---
        for el in root.iter("I"):
            if el.get("c") != "ClubSeed":
                continue
            sid = el.get("s")
            for child in el:
                if child.tag == "T" and child.get("n") == "name" and child.text:
                    try:
                        key = int(child.text, 16) if child.text.startswith("0x") else int(child.text)
                    except ValueError:
                        continue
                    club_names[int(sid)] = stbl.get(key) or ""

        def seeds(node, depth=0):
            out = []
            if depth > 5 or node is None:
                return out
            if node.tag == "r":
                return seeds(shared.get(node.get("x")), depth + 1)
            if node.tag == "T" and node.text:
                text = node.text.strip()
                if text.isdigit() and int(text) in club_names:
                    out.append(int(text))
            for sub in node:
                out += seeds(sub, depth + 1)
            return out

        for el in root.iter("I"):
            if el.get("c") != "PremadeSimTemplate":
                continue
            n = el.get("n") or ""
            short = n.split("simTemplate_", 1)[-1]
            if short.lower().startswith(("ep", "gp", "sp", "hs")):
                short = short.split("_", 1)[-1]
            for child in el:
                if child.get("n") == "clubs":
                    for seed in seeds(child):
                        clubs.setdefault(seed, {"name": club_names.get(seed, ""), "members": []})["members"].append(short)

payload = {"source": "PremadeHouseholdTemplate._household_relationship", "households": households}
Path("data/premade_household_relations.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("households", len(households), "written data/premade_household_relations.json")
for name, info in list(households.items())[:20]:
    print(" ", name, info)

club_list = []
for seed, info in clubs.items():
    members = list(dict.fromkeys(info["members"]))
    if info.get("name") and len(members) >= 2:
        club_list.append({"seed": seed, "name": info["name"], "members": members})
Path("data/premade_clubs.json").write_text(
    json.dumps({"source": "PremadeSimTemplate.clubs", "clubs": club_list}, indent=1),
    encoding="utf-8",
)
print("clubs", len(club_list), "written data/premade_clubs.json")
for club in club_list[:20]:
    print(" ", club)
