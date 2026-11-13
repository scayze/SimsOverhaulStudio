import sys
import json
import xml.etree.ElementTree as ET
sys.path.insert(0, ".")
from backend.settings import paths
from backend.dbpf import DBPF
from backend.catalog import SIMDATA_TYPE, TOKEN_RE
from combinedtuning import decode_combined_tuning

# 1. instance -> tuning name (so action ids become readable names)
inst_names = {}
for p in paths.game.rglob("*.package"):
    if "Client" in p.name or "thumbnails" in p.name.lower():
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
            inst_names[e.instance] = toks[-1]

setups = {}
for p in paths.game.rglob("*.package"):
    if "Client" in p.name or "thumbnails" in p.name.lower():
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
        if b"PremadesSetup" not in raw:
            continue
        # Skip the very large base-game combined tuning; the setup tunings live
        # in the pack combined tunings.
        if len(raw) > 12_000_000:
            continue
        try:
            xml = decode_combined_tuning(raw)
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}

        def action_ids(elem, depth=0):
            out = []
            if depth > 4:
                return out
            for child in list(elem):
                if child.tag == "r":
                    ref = shared.get(child.get("x"))
                    if ref is not None:
                        out.extend(action_ids(ref, depth + 1))
                elif child.tag == "V" and child.get("t") == "actions":
                    for sub in child:
                        if sub.tag == "T" and sub.get("n") == "actions" and sub.text:
                            out.append(int(sub.text))
                else:
                    out.extend(action_ids(child, depth + 1))
            return out

        for elem in root.iter("I"):
            name = elem.get("n") or ""
            if "PremadesSetup" not in name:
                continue
            actions = set()
            for child in elem:
                target = None
                if child.tag == "L" and child.get("n") == "loot_actions":
                    target = child
                elif child.tag == "r" and child.get("n") == "loot_actions":
                    target = shared.get(child.get("x"))
                if target is not None:
                    for aid in action_ids(target):
                        actions.add(inst_names.get(aid, str(aid)))
            old = setups.get(name)
            if old is None or len(actions) > len(old):
                tail = name.split("PremadesSetup_", 1)[-1]
                parts = [x for x in tail.split("_") if x]
                setups[name] = sorted(actions)

payload = {
    "source": "loot_PremadesSetup_* tuning (new-save world setup)",
    "setups": [{"name": n, "tokens": n.split("PremadesSetup_", 1)[-1].split("_"), "actions": a}
               for n, a in sorted(setups.items())],
}
with open("data/premade_setups.json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=1)
print("setups", len(setups), "written data/premade_setups.json")
for n, a in sorted(setups.items()):
    print(f"  {n:55} {a}")
