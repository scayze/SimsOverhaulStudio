"""Extract the premade scandal secrets the game seeds in `SimInfoFixup` tunings.

EP21 seeds five secrets that connect premade sims (Celeste Capp / Dante Monty,
Cordelia Thebe V / Mara Acosta, Adekoya Darong / Aghata Ananou, plus two
single-sim secrets). The owner comes from the sim template's `_fixups` list;
the other party is the `complicit_premade_sim` (a living sim or an ancestor).

Run from the project root:
    python tools/build_premade_secrets.py
"""
import sys
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.settings import paths
from backend.dbpf import DBPF
from backend.catalog import SIMDATA_TYPE, TOKEN_RE
from backend.templatedata import load_complete_dataset, stbl_index
from combinedtuning import decode_combined_tuning

STBL = stbl_index()

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


def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


dataset = load_complete_dataset()
sims = []
for household in dataset.get("households", []):
    for sim in household.get("sims", []):
        sims.append({**sim, "household": sim.get("household") or household.get("name")})

by_full = {}
by_house_first = {}
for sim in sims:
    full = norm(sim["first"] + sim["last"])
    by_full.setdefault(full, []).append(sim)
    by_house_first.setdefault((norm(sim.get("household")), norm(sim["first"])), []).append(sim)


def unique(rows):
    seen = {(s["first"], s["last"], s.get("household")): s for s in rows}
    return list(seen.values())[0] if len(seen) == 1 else None


def display_template(template):
    if not template:
        return ""
    body = template.split("_")[-1]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", body).strip()


def resolve_template(template):
    if not template or not template.startswith("premadeSimTemplate_"):
        return None
    parts = [p for p in template.split("_") if p]
    if not parts:
        return None
    # Exact full-name match on the trailing name token.
    for candidate in (parts[-1], "".join(parts[2:])):
        hit = unique(by_full.get(norm(candidate), []))
        if hit:
            return hit
    # Fall back to first name inside the household token (EP21_Capp_CelesteCapp,
    # EP21_Thebe_CordeliaThebeTheV).
    if len(parts) >= 2:
        house = norm(parts[-2])
        body = parts[-1]
        for i in range(1, len(body) + 1):
            hit = unique(by_house_first.get((house, norm(body[:i])), []))
            if hit:
                return hit
    return None


def humanize(secret):
    tail = secret.split("secret_ScandalSecret_", 1)[-1]
    if tail.startswith("EP21World_"):
        tail = tail[len("EP21World_"):]
        tail = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", tail).replace("_", " ").strip()
        return f"{tail}'s secret"
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", tail).replace("_", " ").strip()
    lower = words.lower()
    if lower == "has secret child":
        return "Has a secret child"
    if lower == "is info broker":
        return "Information broker"
    if lower == "secret lovers":
        return "Secret lovers"
    if lower == "dynasty forbidden friends":
        return "Forbidden friends (dynasty)"
    return words


def resolve_node(node, shared, depth=0):
    if depth > 8 or node is None:
        return None
    if node.tag == "r":
        return resolve_node(shared.get(node.get("x")), shared, depth + 1)
    if node.tag in ("T", "E"):
        return node.text.strip() if node.text else None
    if node.tag == "V":
        return resolve_node(node[0], shared, depth + 1) if len(node) else None
    return None


ancestors_by_s = {}
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
        if b"TunablePremadeAncestor" not in raw:
            continue
        try:
            xml = decode_combined_tuning(raw)
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}
        for el in root.iter("I"):
            if el.get("c") != "TunablePremadeAncestor":
                continue
            full = ""
            for child in el:
                if child.get("n") == "full_name":
                    value = resolve_node(child, shared)
                    try:
                        key = int(value, 16) if value and value.lower().startswith("0x") else int(value)
                    except (TypeError, ValueError):
                        continue
                    full = STBL.get(key) or ""
            if full and el.get("s"):
                ancestors_by_s[el.get("s")] = full

secrets = {}
seen = set()
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
        if b"secrets_fixup_action" not in raw:
            continue
        try:
            xml = decode_combined_tuning(raw)
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}
        owner_by_fixup = {}
        for sim_el in root.iter("I"):
            if sim_el.get("c") != "PremadeSimTemplate":
                continue
            for child in sim_el:
                if child.get("n") != "_fixups":
                    continue
                for sub in child.iter():
                    value = None
                    if sub.tag == "T" and sub.text and sub.text.strip().isdigit():
                        value = sub.text.strip()
                    elif sub.tag == "r":
                        ref = shared.get(sub.get("x"))
                        if ref is not None and ref.tag == "T" and ref.text and ref.text.strip().isdigit():
                            value = ref.text.strip()
                    if value:
                        owner_by_fixup[value] = sim_el.get("n")
        for el in root.iter("I"):
            if el.get("c") != "SimInfoFixup":
                continue
            for act in el.iter("V"):
                if act.get("t") != "secrets_fixup_action":
                    continue
                fields = {}
                for child in act.iter():
                    if child.tag == "r" and child.get("n"):
                        fields[child.get("n")] = resolve_node(child, shared)
                    elif child.tag == "T" and child.get("n") and child.text:
                        fields[child.get("n")] = child.text.strip()
                secret_id = fields.get("secret")
                owner_template = owner_by_fixup.get(el.get("s"))
                if not secret_id or not owner_template:
                    continue
                secret_name = names.get(int(secret_id), str(secret_id))
                complicit = fields.get("complicit_premade_sim") or fields.get("enabled")
                if complicit and str(complicit).isdigit():
                    complicit = names.get(int(complicit), str(complicit))
                target_sim = resolve_template(complicit)
                target_ancestor = ancestors_by_s.get(str(complicit)) if complicit else None
                key = (owner_template, secret_name, complicit)
                if key in seen:
                    continue
                seen.add(key)
                owner_sim = resolve_template(owner_template)
                target_name = (f"{target_sim['first']} {target_sim['last']}" if target_sim
                               else (target_ancestor or (display_template(complicit) if complicit else "")))
                secrets[key] = {
                    "owner_template": owner_template,
                    "owner": {"first": owner_sim["first"], "last": owner_sim["last"]} if owner_sim else None,
                    "owner_name": f"{owner_sim['first']} {owner_sim['last']}" if owner_sim else display_template(owner_template),
                    "secret": secret_name,
                    "label": humanize(secret_name),
                    "target_template": complicit,
                    "target_name": target_name,
                    "target": ({"first": target_sim["first"], "last": target_sim["last"]} if target_sim
                              else ({"name": target_ancestor} if target_ancestor else None)),
                }

payload = {
    "source": "SimInfoFixup.secrets_fixup_action (premade scandal secrets)",
    "secrets": sorted(secrets.values(), key=lambda s: (s["owner_template"], s["secret"])),
}
Path("data/premade_secrets.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("secrets", len(payload["secrets"]), "written data/premade_secrets.json")
for s in payload["secrets"]:
    print(s["owner"], s["label"], "->", s["target"])
