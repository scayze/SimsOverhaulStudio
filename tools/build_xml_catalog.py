"""Extract aspiration/career/trait/skill tunings that exist only as XML.

Some newer game tunings (for example several aspiration branches and the
base Career tunings such as ``careers_Adult_CorporateWorker``) are not present
in the compiled SimData resources the scanner normally reads. They are stored
as CombinedTuning XML resources instead. This script reads those resources and
writes ``data/xml_tuning_items.json`` so the catalog can merge them in.

Run from the project root:
    python tools/build_xml_catalog.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.catalog import ASPIRATION_NAMES, _classify, _display_label, fnv1_32
from backend.dbpf import DBPF
from backend.settings import paths
from combinedtuning import decode_combined_tuning

COMBINED = 0x62E94D38
WANT_CLASSES = {
    "Aspiration": "aspirations",
    "Career": "careers",
    "Trait": "traits",
    "Skill": "skills",
    "Statistic": "skills",
    "TunableCareerTrack": "career_tracks",
}
NODE_RE = re.compile(
    r'<I c="([A-Za-z]+)"[^>]*?n="([^"]+)"(?:[^>]*?\bs="(\d+)")?[^>]*>(.*?)</I>',
    re.S,
)
TRAIT_TYPE_RE = re.compile(r'<[ET] n="trait_type">([^<]+)</[ET]>')

items = {}
packages = []
for p in paths.game.rglob("*.package"):
    if p.name.lower() in ("simulationfullbuild0.package", "simulationdeltabuild0.package", "simulationpreload0.package", "simulationpreload.package"):
        packages.append(p)

for p in sorted(packages):
    try:
        db = DBPF(p)
    except Exception:
        continue
    for entry in db.entries:
        if entry.type != COMBINED:
            continue
        try:
            raw = db.read_entry(entry)
        except Exception:
            continue
        if not any(f'c="{c}"'.encode() in raw for c in WANT_CLASSES):
            continue
        if raw.startswith(b"<"):
            text = raw.decode("utf-8", "replace")
        else:
            try:
                text = decode_combined_tuning(raw)
            except Exception:
                continue
        shared_values = {
            m.group(2): m.group(3).strip()
            for m in re.finditer(r'<([TE]) x="(\d+)">([^<]*)</\1>', text)
        }
        for match in NODE_RE.finditer(text):
            cls, name, inst, body = match.groups()
            kind = _classify(name, cls)
            if kind not in ("aspirations", "careers", "career_tracks", "traits", "skills"):
                continue
            low = name.lower()
            if kind == "aspirations" and not low.startswith("aspiration_"):
                continue
            if kind == "careers" and not (low.startswith("career_") or low.startswith("careers_")):
                continue
            if kind == "traits" and not low.startswith("trait_"):
                continue
            if kind == "career_tracks" and not low.startswith(("career_track", "careertrack", "careertracks")):
                continue
            key = (kind, name)
            if key in items:
                continue
            item = {
                "kind": kind,
                "id": int(inst) if inst else fnv1_32(name.lower()),
                "tuning": name,
                "class": cls,
                "label": _display_label(kind, name),
                "pack": "",
                "pack_label": "",
                "modded": False,
                "source": str(p),
                "age_hint": None,
                "species_hint": None,
                "occult_hint": None,
                "npc": kind == "careers" and "_npc_" in low,
            }
            if kind == "traits":
                tm = TRAIT_TYPE_RE.search(body or "")
                trait_type = tm.group(1).strip() if tm else ""
                if not trait_type:
                    rm = re.search(r'<r n="trait_type" x="(\d+)"', body or "")
                    if rm:
                        trait_type = shared_values.get(rm.group(1), "")
                if trait_type:
                    item["trait_type"] = trait_type
            items[key] = item
    print("scanned", p.name, "items", len(items))

# The base-game aspiration names are known from the game's own tier-1
# tunings. Add any that the compiled catalog does not expose, so the picker
# and the validator can find every base aspiration.
for tuning, label in ASPIRATION_NAMES.items():
    key = ("aspirations", tuning)
    if key in items:
        continue
    items[key] = {
        "kind": "aspirations",
        "id": fnv1_32(tuning.lower()),
        "tuning": tuning,
        "class": "Aspiration",
        "label": label,
        "pack": "Base",
        "pack_label": "Base Game",
        "modded": False,
        "source": "base aspiration map",
        "age_hint": None,
        "species_hint": None,
        "occult_hint": None,
        "npc": False,
    }

payload = {"items": sorted(items.values(), key=lambda i: (i["kind"], i["label"].lower()))}
Path("data/xml_tuning_items.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("items", len(payload["items"]))
for kind in sorted(WANT_CLASSES.values()):
    print(kind, sum(1 for i in payload["items"] if i["kind"] == kind))
