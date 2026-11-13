"""Extract the EP21 NPC relationship seeds (loot_WorldEP21_NPC_*).

These are the game's cross-household social/family seeds for the Bellacorde
premades: exact friendship/romance values plus sentiments and family/romance
tropes (e.g. Tybalt/Juliette -90 with a bitter grudge, Consort/Juliette
difficult family trope, Cordelia/Mara romance 80 with Enamored).

Run from the project root:
    python tools/build_npc_relations.py
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
from combinedtuning import decode_combined_tuning

# instance -> tuning name
names = {}
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
            names[e.instance] = toks[-1]

TRACKS = {16650: "friendship", 16651: "romance"}
pairs = {}

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
        if b"loot_WorldEP21_NPC_" not in raw:
            continue
        try:
            xml = decode_combined_tuning(raw)
            if "loot_WorldEP21_NPC_" not in xml:
                continue
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}

        def resolve(node, depth=0):
            if depth > 8 or node is None:
                return None
            if node.tag == "r":
                return resolve(shared.get(node.get("x")), depth + 1)
            if node.tag in ("T", "E"):
                return node.text.strip() if node.text else None
            if node.tag == "U":
                return {c.get("n"): resolve(c, depth + 1) for c in node if c.get("n")}
            if node.tag == "V":
                return resolve(node[0], depth + 1) if len(node) else None
            if node.tag == "L":
                return [resolve(c, depth + 1) for c in node]
            return None

        def tuning_name(value):
            if value is None:
                return ""
            value = str(value)
            if value.isdigit() and int(value) in names:
                return names[int(value)]
            return value

        for el in root.iter("I"):
            lname = el.get("n") or ""
            if not lname.startswith("loot_WorldEP21_NPC_"):
                continue
            tokens = lname[len("loot_WorldEP21_NPC_"):].split("_")
            if len(tokens) < 2:
                continue
            data = {"tokens": tokens, "friendship": None, "romance": None, "bits": []}
            for sub in el.iter("V"):
                t = sub.get("t")
                if t == "statistics":
                    stats = next((u for u in sub if u.tag == "V" and u.get("n") == "statistics"), None)
                    if stats is None:
                        continue
                    typ = stats.get("t")
                    fields = {}
                    for c in stats.iter():
                        if c.tag == "r" and c.get("n"):
                            fields[c.get("n")] = resolve(c)
                    try:
                        track = int(fields.get("track"))
                    except (TypeError, ValueError):
                        track = None
                    if typ == "relationship_set" and track in TRACKS:
                        try:
                            val = int(fields.get("value"))
                        except (TypeError, ValueError):
                            val = 0
                        data[TRACKS[track]] = val
                elif t == "relationship_bits_loot":
                    # has_met (15803) is applied to these pairs
                    data["bits"].append("has_met")
            for sub in el.iter("r"):
                if sub.get("n") is not None:
                    continue
                nm = tuning_name(resolve(sub))
                if nm.startswith(("loot_Sentiment", "loot_FamilyTrope", "loot_RomanceTrope")):
                    data["bits"].append(nm)
            data["bits"] = list(dict.fromkeys(data["bits"]))
            if data["friendship"] is None and data["romance"] is None and not data["bits"]:
                continue
            pairs[tuple(tokens)] = data

payload = {"source": "loot_WorldEP21_NPC_* (EP21 Bellacorde NPC relationship seeds)",
           "pairs": [{**v, "tokens": list(k)} for k, v in sorted(pairs.items())]}
Path("data/premade_npc_relations.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("pairs", len(pairs), "written data/premade_npc_relations.json")
for p in payload["pairs"]:
    print(p["tokens"], p["friendship"], p["romance"], p["bits"])
