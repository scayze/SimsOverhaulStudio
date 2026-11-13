"""Extract the exact premade careers and aspiration tracks.

The combined ``PremadeSimTemplate.career_level`` points at a career-level tuning
(e.g. ``career_Writer_Journalist_Level1``) which encodes both the career/track
and the starting level. ``primary_aspiration`` points at an aspiration-track
tuning (e.g. ``Track_Popularity_B``) — the install does not store a specific
aspiration, so the tool must not invent one.

Run from the project root:
    python tools/build_premade_careers.py
"""
import sys
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.settings import paths
from backend.dbpf import DBPF
from backend.catalog import SIMDATA_TYPE, TOKEN_RE, load_catalog
from backend.templatedata import stbl_index
from combinedtuning import decode_combined_tuning

STBL = stbl_index()
CAT = load_catalog()["catalog"]
CAREERS = {c["label"].lower(): c for c in CAT["careers"]}
TRACKS = {t["label"].lower(): t for t in CAT["career_tracks"]}
ASP_TRACKS = {t["label"].lower(): t for t in CAT["aspiration_tracks"]}
ASP_TRACK_BY_TUNING = {t["tuning"]: t for t in CAT["aspiration_tracks"]}
CAREER_BY_TUNING = {c["tuning"].lower(): c for c in CAT["careers"]}
TRACK_BY_TUNING = {t["tuning"].lower(): t for t in CAT["career_tracks"]}
TRAIT_LABELS = {}
for _kind in ("traits", "identity", "preferences", "degrees", "occults"):
    for _item in CAT.get(_kind, []):
        TRAIT_LABELS.setdefault(_item["id"], _item)

# Tracker entries that are identity, gender options, hidden flags, ranks or
# preferences rather than a personality/reward trait.
TEMPLATE_TRAIT_BLOCK = (
    "trait_hidden", "trait_genderoptions", "trait_reputation", "trait_simreputation",
    "trait_sim_reputation", "trait_relexpectations", "trait_sexualorientation",
    "trait_handedness", "trait_walkstyle", "trait_iscustomgender", "trait_umbrella",
    "trait_lifestyles", "trait_cas_", "trait_natethel0ser", "trait_species",
    "trait_occult_", "trait_gender_", "trait_human_", "trait_npc", "trait_service",
    "trait_debug", "trait_simpreference", "trait_noblefavor", "trait_noblecareer_exrank",
    "trait_masteryperk", "trait_magic_fixups", "trait_ghost", "trait_isburglar",
    "trait_isrobinhood", "trait_ispremadepo", "trait_isschoolghost",
    "trait_introtovampire", "trait_werewolfpack", "trait_gradeschool", "trait_hsexit",
    "trait_dynasty", "trait_witchoccultperk", "trait_occultmermaid",
    "trait_occultfairytyae", "trait_occultwerewolfhad", "trait_occultwerewolfimmortal",
    "trait_occultwerewolfnatural", "trait_occultwerewolftemperament",
    "trait_occultwerewolfinitiation",
)


MISSING_WIKI_TRAITS = set()
_audit_path = Path("data/wiki_audit.json")
if _audit_path.exists():
    try:
        for _row in json.loads(_audit_path.read_text(encoding="utf-8")):
            for _diff in _row.get("diffs", []):
                if _diff.get("kind") == "trait_missing_tool" and _diff.get("trait"):
                    MISSING_WIKI_TRAITS.add(_diff["trait"])
    except (OSError, ValueError):
        MISSING_WIKI_TRAITS = set()


def template_trait_name(tid):
    item = TRAIT_LABELS.get(tid)
    tuning = (item or {}).get("tuning") or names.get(tid, "")
    low = tuning.lower()
    if not low.startswith("trait_"):
        return None
    if low in (
        "trait_adult", "trait_teen", "trait_youngadult", "trait_child",
        "trait_toddler", "trait_infant", "trait_baby", "trait_elder",
    ):
        return None
    if any(low.startswith(prefix) for prefix in TEMPLATE_TRAIT_BLOCK):
        return None
    label = (item or {}).get("label") or humanize(tuning.replace("trait_", ""))
    # Only bring in a template trait when the wiki audit says it is missing.
    # This keeps hidden NPC/perk/attraction traits out of the personality list
    # while still recovering traits that really are in the install template.
    if MISSING_WIKI_TRAITS:
        norm_label = re.sub(r"[^a-z0-9]", "", label.lower())
        if not any(key in norm_label for key in MISSING_WIKI_TRAITS):
            return None
    return {"id": tid, "label": label, "tuning": tuning}

# The game's UI labels for these careers are shorter/different from the tuning
# name. These are the names EA's career screen uses.
CAREER_LABEL_OVERRIDES = {
    "activereaper": "Reaper",
    "corporateworker": "Salaryperson",
    "activist": "Politician",
    "naturopathic": "Naturopath",
    "teensimsfluencersidehustle": "Simsfluencer",
}

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
name_to_instance = {v: k for k, v in names.items()}

SIMINFO_TYPE = 0x025ED6F4
siminfo = {}
for p in paths.game.rglob("*.package"):
    if "thumbnails" in p.name.lower() or "Strings" in p.name:
        continue
    try:
        db = DBPF(p)
    except Exception:
        continue
    for e in db.entries:
        if e.type != SIMINFO_TYPE:
            continue
        try:
            data = db.read_entry(e)
        except Exception:
            continue
        previous = siminfo.get(e.instance)
        # Build layers can contain both an older and a newer resource with the
        # same instance. Prefer the layer that actually carries pronoun data.
        if previous is None or (b"self" in data and b"self" not in previous):
            siminfo[e.instance] = data


def pronoun_block(data):
    """Return the five custom pronoun strings stored in a SimInfo resource."""
    # Custom pronouns can be standard (herself/himself/themself) or a
    # neopronoun (e.g. xirself), so match any reflexive-looking word.
    for match in re.finditer(rb"[a-z]{2,14}sel(?:f|ves)", data):
        reflexive = match.group()
        idx = match.start()
        # The block is: count (u32), then count length-prefixed strings.
        # Scan the small window before the reflexive pronoun for the count.
        for start in range(max(0, idx - 160), idx):
            count = struct.unpack_from("<I", data, start)[0]
            if not 2 <= count <= 10:
                continue
            pos = start + 4
            words = []
            for _ in range(count):
                if pos + 4 > len(data):
                    break
                size = struct.unpack_from("<I", data, pos)[0]
                if size <= 0 or size > 40 or pos + 4 + size > len(data):
                    break
                words.append(data[pos + 4:pos + 4 + size].decode("utf-8", "replace"))
                pos += 4 + size
            last = words[-1].lower().encode("utf-8") if words else b""
            if (
                len(words) == count
                and reflexive in last
                and idx + len(reflexive) <= pos <= idx + 40
            ):
                return words
    return None


def pronouns_for(instance):
    data = siminfo.get(instance)
    if not data:
        return None, None, None
    words = pronoun_block(data)
    if not words:
        return None, None, None
    reflex = words[-1].lower()
    if reflex == "herself":
        identity = "Female"
    elif reflex == "himself":
        identity = "Male"
    else:
        # they/them, neopronouns and any other custom set are non-binary.
        identity = "Non-binary"
    label = "/".join(words[:2])
    return identity, label, words


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
    return None


def display_from_template(name):
    body = (name or "").split("_")[-1]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", body).strip()


def humanize(text):
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text or "").strip()
    return re.sub(r"\s+", " ", text).strip()


def display_words(text):
    words = []
    for word in humanize(text).split():
        if word.lower() in ("politican", "politician"):
            word = "Politician"
        words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def _career_tokens(value):
    """Canonical tokens for comparing career/level tuning names."""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value or "")
    tokens = [t for t in re.split(r"[_\s]+", value.lower()) if t]
    out = []
    for token in tokens:
        if token in ("adult", "teen", "child", "youngadult"):
            continue
        if token == "adultparttime":
            out.extend(["parttime"])
        else:
            out.append(token)
    return out


def _career_match(base_tokens):
    """Find the catalog career whose canonical tuning is the longest prefix."""
    best = None
    best_len = 0
    for career in CAT["careers"]:
        tuning = re.sub(r"^careers?_", "", career["tuning"], flags=re.I)
        tokens = _career_tokens(tuning)
        if not tokens or base_tokens[: len(tokens)] != tokens:
            continue
        if len(tokens) > best_len:
            best = career
            best_len = len(tokens)
    return best, best_len


def _track_match(tokens, career_tokens):
    if not tokens:
        return None
    wanted = ["politician" if t in ("politican", "politician") else t for t in tokens]
    best = None
    best_score = 0
    for track in CAT["career_tracks"]:
        ctokens = _career_tokens(track["tuning"])
        if "npc" in ctokens and "npc" not in wanted:
            continue
        score = 0
        if career_tokens and all(t in ctokens for t in career_tokens):
            score += len(career_tokens)
        if all(t in ctokens for t in wanted):
            score += len(wanted) * 2
        if score > best_score:
            best = track
            best_score = score
    return best


def parse_career_level(tuning):
    if not tuning:
        return None
    m = re.search(r"_Level0?(\d+)$", tuning, re.I)
    if not m:
        return None
    level = int(m.group(1))
    base = tuning[: m.start()]
    base = re.sub(r"^careers?_", "", base, flags=re.I)
    base = re.sub(r"^careerlevels?_", "", base, flags=re.I)
    base_tokens = _career_tokens(base)
    if not base_tokens:
        return None

    career, used = _career_match(base_tokens)
    leftover = base_tokens[used:]
    if career:
        career_tokens = _career_tokens(re.sub(r"^careers?_", "", career["tuning"], flags=re.I))
        label = CAREER_LABEL_OVERRIDES.get("".join(career_tokens), career["label"])
        career_id = career["id"]
        icon_tuning = career["tuning"]
        career_tuning = career["tuning"]
    else:
        # Newer careers such as Naturopath do not always ship a base Career
        # tuning; the level tuning still gives the display name.
        career_tokens = []
        fallback = " ".join(base_tokens)
        label = (
            CAREER_LABEL_OVERRIDES.get("".join(base_tokens))
            or CAREER_LABEL_OVERRIDES.get("".join(base_tokens[:1]))
            or humanize(fallback)
        )
        if label:
            label = label[0].upper() + label[1:]
        career_id = 0
        icon_tuning = ""
        career_tuning = ""
        # If a track tuning starts with the same first token as the level
        # name (Naturopathic_Track2_HerbalMedicine), that token is the career
        # and the rest is the branch. Otherwise the whole name is the career
        # (e.g. Noble) and there is no branch.
        leftover = []
        for candidate in CAT["career_tracks"]:
            ctokens = _career_tokens(re.sub(r"^careers?_", "", candidate["tuning"], flags=re.I))
            if ctokens and ctokens[0] == base_tokens[0] and len(ctokens) > 1:
                leftover = base_tokens[1:]
                break

    if not leftover and not career:
        # A base-less career (e.g. Noble) should not be mistaken for a track.
        track = None
    else:
        track = _track_match(leftover, career_tokens)
    if track:
        # Prefer the short branch name shown in-game (Journalist, Music, Chef).
        track_label = display_words(" ".join(leftover)) if leftover else ""
        if not track_label:
            branch = re.search(r"Track\d+_?(.*)$", track["tuning"], re.I)
            track_label = display_words(branch.group(1)) if branch and branch.group(1) else track["label"]
        track_id = track["id"]
    else:
        track_label = humanize(" ".join(leftover))
        track_id = 0

    return {
        "career": label,
        "career_id": career_id,
        "career_icon_tuning": icon_tuning,
        "career_tuning": career_tuning,
        "track": track_label,
        "track_id": track_id,
        "level": level,
    }


def parse_aspiration_track(tuning):
    if not tuning:
        return None
    track = ASP_TRACK_BY_TUNING.get(tuning)
    if track:
        return {"id": track["id"], "label": track["label"], "tuning": tuning}
    if tuning.startswith("Track_"):
        return {"id": 0, "label": tuning.replace("Track_", "").replace("_", " "), "tuning": tuning}
    return None


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
        if b"PremadeSimTemplate" not in raw:
            continue
        key = (str(p), e.instance)
        if key in seen:
            continue
        seen.add(key)
        try:
            xml = decode_combined_tuning(raw)
        except Exception:
            continue
        if "PremadeSimTemplate" not in xml:
            continue
        try:
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception:
            continue
        shared = {el.get("x"): el for el in root.iter() if el.get("x") and el.tag != "r"}
        for el in root.iter("I"):
            if el.get("c") != "PremadeSimTemplate":
                continue
            name = el.get("n") or ""
            first = last = resource_key = ""
            for child in el:
                if child.tag == "U" and child.get("n") == "_sim_creation_info":
                    for sub in child:
                        if sub.tag == "T" and sub.get("n") == "first_name":
                            first = stbl_text(sub.text)
                        elif sub.tag == "T" and sub.get("n") == "last_name":
                            last = stbl_text(sub.text)
                        elif sub.tag == "T" and sub.get("n") == "resource_key":
                            resource_key = (sub.text or "").strip()
                        elif sub.tag == "r" and sub.get("n") == "resource_key":
                            resource_key = (resolve(sub, shared) or "").strip()
                        elif sub.tag == "r" and sub.get("n") == "first_name":
                            first = stbl_text(resolve(sub, shared))
                        elif sub.tag == "r" and sub.get("n") == "last_name":
                            last = stbl_text(resolve(sub, shared))
                        elif sub.tag == "V" and sub.get("n") == "last_name":
                            for ss in sub.iter():
                                if ss.tag == "T" and ss.get("n") == "specify_last_name":
                                    last = stbl_text(ss.text)
            template_traits = []
            seen_traits = set()
            for child in el:
                if child.tag == "U" and child.get("n") == "_traits":
                    for entry_node in child.iter():
                        if entry_node.tag != "L" or entry_node.get("n") != "explicit":
                            continue
                        for ref in entry_node:
                            if ref.tag != "r" or not ref.get("x"):
                                continue
                            raw_id = resolve(ref, shared)
                            try:
                                trait_id = int(raw_id)
                            except (TypeError, ValueError):
                                continue
                            item = template_trait_name(trait_id)
                            if not item or item["tuning"] in seen_traits:
                                continue
                            seen_traits.add(item["tuning"])
                            template_traits.append(item)

            career_id = aspiration_id = None
            for child in el:
                if child.get("n") == "career_level":
                    value = resolve(child, shared)
                    try:
                        career_id = int(value)
                    except (TypeError, ValueError):
                        pass
                elif child.get("n") == "primary_aspiration":
                    value = resolve(child, shared)
                    try:
                        aspiration_id = int(value)
                    except (TypeError, ValueError):
                        pass
            career = parse_career_level(names.get(career_id)) if career_id else None
            aspiration = parse_aspiration_track(names.get(aspiration_id)) if aspiration_id else None
            siminfo_id = 0
            if resource_key:
                try:
                    siminfo_id = int(resource_key.rsplit(":", 1)[-1], 16)
                except ValueError:
                    siminfo_id = 0
            gender_identity, pronouns_label, pronouns = pronouns_for(siminfo_id)
            if not career and not aspiration and not gender_identity:
                continue
            entry = {
                "template": name,
                "name": f"{first} {last}".strip() or display_from_template(name),
                "first": first,
                "last": last,
                "career": career,
                "career_level_tuning": names.get(career_id, "") if career_id else "",
                "aspiration_track": aspiration,
                "aspiration_track_tuning": names.get(aspiration_id, "") if aspiration_id else "",
                "siminfo": resource_key,
                "gender_identity": gender_identity,
                "pronouns": pronouns_label,
                "pronoun_words": pronouns,
                "template_traits": template_traits,
            }
            old = sims.get(name)
            if old is None:
                sims[name] = entry
            else:
                # The same template can appear in more than one build layer;
                # keep the richest version (resource key, pronouns, traits).
                for key_name, value in entry.items():
                    if value and not old.get(key_name):
                        old[key_name] = value
                if entry.get("template_traits"):
                    old["template_traits"] = entry["template_traits"]

payload = {
    "source": "PremadeSimTemplate.career_level / primary_aspiration",
    "sims": sorted(sims.values(), key=lambda s: (s["name"], s["template"])),
}
Path("data/premade_careers.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("sims", len(payload["sims"]))
for s in payload["sims"][:20]:
    print(s["name"], s["career"], s["aspiration_track"])
