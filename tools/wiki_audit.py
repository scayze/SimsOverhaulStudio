import sys
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
from backend import project
from backend.catalog import ASPIRATION_NAMES, load_catalog

CAT = load_catalog()["catalog"]

API = "https://sims.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def norm(text):
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"''+", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    value = re.sub(r"[^a-z0-9]", "", text.lower())
    return value


ASP_BY_LABEL = {norm(a["label"]): a for a in CAT.get("aspirations", [])}
ASP_TRACK_BY_LABEL = {norm(t["label"]): t for t in CAT.get("aspiration_tracks", [])}


ASP_FAMILY_BY_LABEL = {}
for tuning, name in ASPIRATION_NAMES.items():
    parts = tuning.split("_")
    if len(parts) >= 2:
        ASP_FAMILY_BY_LABEL[norm(name)] = parts[1].lower()


def _family_from_tuning(tuning):
    match = re.match(r"aspiration_([A-Za-z]+?)_[A-D]\d", tuning or "")
    if match:
        return match.group(1).lower()
    match = re.match(r"aspiration_([A-Za-z]+?)_", tuning or "")
    return match.group(1).lower() if match else ""


def aspiration_family(label):
    key = norm(label)
    if key in ASP_FAMILY_BY_LABEL:
        return ASP_FAMILY_BY_LABEL[key]
    item = ASP_BY_LABEL.get(key)
    if item:
        return _family_from_tuning(item.get("tuning", ""))
    # Newer aspirations often have a prefixed game label (e.g. the wiki says
    # "Critter Hunter" while the tuning is Nature Critter Hunter).
    for candidate_key, candidate in ASP_BY_LABEL.items():
        if key and (key in candidate_key or candidate_key in key):
            return _family_from_tuning(candidate.get("tuning", ""))
    return ""


def shares_significant_word(a, b):
    words_a = {w for w in re.findall(r"[a-z]{4,}", (a or "").lower())}
    words_b = {w for w in re.findall(r"[a-z]{4,}", (b or "").lower())}
    return bool(words_a & words_b)


def track_family(label):
    item = ASP_TRACK_BY_LABEL.get(norm(label))
    tuning = item.get("tuning", "") if item else label
    match = re.match(r"Track_([A-Za-z]+?)(?:_[A-D]|_|$)", tuning or "")
    if not match:
        return ""
    family = match.group(1).lower()
    if family == "mental":
        return "child"
    return family


def career_key(text):
    value = norm(text)
    for prefix in ("adultparttime", "parttime", "teen", "adult"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return {
        "politics": "politician",
        "activist": "politician",
        "politician": "politician",
        "simsfluencersidehustle": "simfluencer",
        "simsfluencer": "simfluencer",
        "athlete": "athletic",
        "athletic": "athletic",
        "undertaker": "mortician",
        "mortician": "mortician",
    }.get(value, value)


SKILL_ALIASES = {
    "cooking": "homestylecooking",
    "mixology": "bartending",
    "videogames": "videogaming",
    "horseriding": "equestrianskill",
    "naturalliving": "nls",
    "creativity": "childcreativity",
    "mental": "childmental",
    "motor": "childmotor",
    "social": "childsocial",
    "communication": "toddlercommunication",
    "movement": "toddlermovement",
    "thinking": "toddlerthinking",
    "agility": "horseagility",
    "endurance": "horseendurance",
    "jumping": "horsejumping",
    "temperament": "horsetemperament",
    "hiddenvampirelore": "vampirelore",
    "ranchnectar": "nectarmaking",
    "dogtraining": "pettraining",
    "toddlerpotty": "potty",
    "divingboard": "diving",
    "researchanddebate": "researchdebate",
}
TRAIT_ALIASES = {
    "domestic": "familysim",
    "insane": "erratic",
    "childoftheislands": "islandancestors",
    "infected": "strangervilleinfected",
    "reborn": "movingonreincarnated",
    "fairyinfluence": "fairystoriesinitiationfayimpresser",
    "noncommittal": "commitmentissues",
    "toddlercharmer": "charmer",
    "toddlerclingy": "clingy",
    "infantwiggly": "wiggly",
    "infantsunny": "sunny",
    "childofthesea": "childoftheocean",
    "toddlerangelic": "angelic",
    "occultwerewolfwerewolfally": "werewolfally",
}
CAREER_ALIASES = {
    "athlete": "athletic",
    "politician": "activist",
    "undertaker": "mortician",
}


def alias(mapping, value):
    return mapping.get(value, value)


def clean(text):
    text = text or ""
    # Keep templates that contain wiki links ({{Relative|[[Name]]}}, etc.).
    text = re.sub(r"\{\{(?![^{}]*\[\[)[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"''+", "", text)
    return text.strip()


def brace_block(text, start):
    depth = 0
    i = start
    while i < len(text) - 1:
        if text[i:i + 2] == "{{":
            depth += 1
            i += 2
        elif text[i:i + 2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start:i]
        else:
            i += 1
    return text[start:]


def infobox_fields(text):
    start = text.find("{{Infobox Sim4")
    if start < 0:
        return {}
    block = brace_block(text, start)
    fields = {}
    for line in block.splitlines():
        m = re.match(r"\s*\|\s*([A-Za-z0-9_]+)\s*=\s*(.*)", line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        if key in fields:
            continue
        # Keep the raw value; link extraction needs the [[...]] markup. The
        # comparison helpers call norm()/clean() as needed.
        fields[key] = m.group(2).strip()
    return fields


def skill_levels(text):
    levels = {}
    for m in re.finditer(r"\{\{SkillTable3", text):
        block = brace_block(text, m.start())
        for line in block.splitlines():
            sm = re.match(r"\s*\|\s*([A-Za-z0-9_' -]+)\s*=\s*(\d+)", line)
            if not sm:
                continue
            name = norm(sm.group(1))
            level = int(sm.group(2))
            if name:
                levels[name] = max(levels.get(name, 0), level)
    return levels


def fetch(titles):
    out = {}
    for i in range(0, len(titles), 10):
        chunk = titles[i:i + 10]
        params = {
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "redirects": "1",
        }
        url = API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=UA)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                break
            except Exception as exc:
                if attempt == 2:
                    print("fetch failed", exc)
                    data = {}
                else:
                    time.sleep(1 + attempt)
        pages = (data.get("query") or {}).get("pages", {}) if isinstance(data, dict) else {}
        redirects = {r["from"]: r["to"] for r in (data.get("query") or {}).get("redirects", [])} if isinstance(data, dict) else {}
        by_title = {}
        for page in pages.values():
            title = page.get("title", "")
            by_title[title] = page
        for original in chunk:
            title = redirects.get(original, original)
            page = by_title.get(title) or by_title.get(title.replace("_", " "))
            if not page or "missing" in page:
                # try the normalized title with spaces
                page = by_title.get(original.replace("_", " "))
            if not page or "missing" in page:
                continue
            rev = (page.get("revisions") or [{}])[0]
            text = ((rev.get("slots") or {}).get("main") or {}).get("*", "")
            if text:
                out[original] = text
        time.sleep(0.3)
    return out


p = project.load()
sims = list(p["sims"].values())
titles = []
for s in sims:
    title = f"{s['first']}_{s['last']}".replace(" ", "_")
    titles.append(title)
texts = fetch(titles)
print("fetched", len(texts), "of", len(titles))

def relation_names(value):
    names = []
    for match in re.finditer(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", value or ""):
        name = clean(match.group(1)).strip()
        if not name or name.lower() in ("the sims 4",):
            continue
        if name.startswith(("File:", "Category:", "Image:")) or "deceased" in name.lower():
            continue
        names.append(name)
    return names


sim_by_key = {s["key"]: s for s in sims}
report = []
skill_rows = []
for s in sims:
    title = f"{s['first']}_{s['last']}".replace(" ", "_")
    text = texts.get(title)
    if not text:
        continue
    fields = infobox_fields(text)
    wiki_skills = {alias(SKILL_ALIASES, k): v for k, v in skill_levels(text).items()}
    tool_skills = {alias(SKILL_ALIASES, norm(x.get("label", ""))): int(x.get("level") or 0) for x in s.get("skills", [])}
    diffs = []
    for name, level in sorted(wiki_skills.items()):
        if name not in tool_skills:
            # A skill at level 1 is stored as the template's 100 XP baseline;
            # the studio only lists skills with real progress.
            kind = "skill_level1_unlisted" if level <= 1 else "skill_missing_tool"
            diffs.append({"kind": kind, "skill": name, "wiki": level})
        elif tool_skills[name] != level:
            diffs.append({"kind": "skill_level", "skill": name, "wiki": level, "tool": tool_skills[name]})
    for name, level in sorted(tool_skills.items()):
        if name not in wiki_skills:
            diffs.append({"kind": "skill_extra_tool", "skill": name, "tool": level})
    if fields:
        wiki_gender = norm(fields.get("sex", ""))
        tool_gender = norm(s.get("gender", ""))
        if wiki_gender and tool_gender and wiki_gender != tool_gender:
            diffs.append({"kind": "gender", "wiki": fields.get("sex"), "tool": s.get("gender")})
        wiki_age = norm(fields.get("age", ""))
        tool_age = norm(s.get("age", ""))
        if wiki_age and tool_age and wiki_age != tool_age:
            diffs.append({"kind": "age", "wiki": fields.get("age"), "tool": s.get("age")})
        wiki_career = career_key(fields.get("career", ""))
        tool_career = career_key((s.get("career") or {}).get("label", ""))
        if wiki_career and tool_career and wiki_career != tool_career:
            diffs.append({"kind": "career", "wiki": fields.get("career"), "tool": (s.get("career") or {}).get("label")})
        wiki_asp = fields.get("asp", "")
        tool_asp = (s.get("aspiration") or {}).get("label", "")
        track = s.get("aspiration_track", "")
        if wiki_asp and not tool_asp:
            if track and (
                aspiration_family(wiki_asp) == track_family(track)
                or shares_significant_word(wiki_asp, track)
            ):
                diffs.append({"kind": "aspiration_track_only", "wiki": wiki_asp, "track": track})
            else:
                diffs.append({"kind": "aspiration", "wiki": wiki_asp, "track": track})
        elif wiki_asp and tool_asp and norm(wiki_asp) != norm(tool_asp):
            if aspiration_family(wiki_asp) and aspiration_family(wiki_asp) == aspiration_family(tool_asp):
                diffs.append({"kind": "aspiration_specific", "wiki": wiki_asp, "tool": tool_asp})
            else:
                diffs.append({"kind": "aspiration", "wiki": wiki_asp, "tool": tool_asp})
        wiki_traits = [alias(TRAIT_ALIASES, norm(fields.get(k, ""))) for k in ("trait1", "trait2", "trait3", "trait4", "trait5", "trait6", "trait7", "trait8")]
        wiki_traits = [x for x in wiki_traits if x]
        tool_traits_all = [alias(TRAIT_ALIASES, norm(t.get("label", ""))) for t in s.get("traits", [])]
        # The infobox lists personality traits. Reward/aspiration traits are
        # real but are not part of that list, so do not count them as extra.
        tool_traits = [
            alias(TRAIT_ALIASES, norm(t.get("label", "")))
            for t in s.get("traits", [])
            if (t.get("trait_type") or "").upper() in ("", "PERSONALITY")
        ]
        def trait_matches(tool, wiki):
            if tool == wiki:
                return True
            if len(wiki) >= 6 and tool.endswith(wiki):
                return True
            if len(tool) >= 6 and wiki.endswith(tool):
                return True
            return False

        tool_set = set(tool_traits_all)
        wiki_set = set(wiki_traits)
        for tr in wiki_traits:
            if not any(trait_matches(tool, tr) for tool in tool_set):
                diffs.append({"kind": "trait_missing_tool", "trait": tr})
        for tr in tool_traits:
            if not any(trait_matches(tr, wiki) for wiki in wiki_set):
                diffs.append({"kind": "trait_extra_tool", "trait": tr})

        wiki_family = []
        for key in ("parents", "siblings", "spouse", "children"):
            for name in relation_names(fields.get(key, "")):
                wiki_family.append((key, name))
        tool_family = []
        for link in s.get("family", []) or []:
            target = sim_by_key.get(link.get("target"))
            if target:
                tool_family.append((link.get("relation") or "Relative", f"{target['first']} {target['last']}"))
        tool_relationships = []
        for link in s.get("relationships", []) or []:
            target = sim_by_key.get(link.get("target"))
            if target:
                tool_relationships.append((link.get("label") or "Relationship", f"{target['first']} {target['last']}"))
        tool_names = {norm(name) for _, name in tool_family + tool_relationships}
        wiki_names = {norm(name): (kind, name) for kind, name in wiki_family}
        for key, name in wiki_family:
            if norm(name) not in tool_names:
                diffs.append({"kind": "family_missing_link", "relation": key, "name": name})
        for relation, name in tool_family:
            if norm(name) not in wiki_names:
                diffs.append({"kind": "family_extra_link", "relation": relation, "name": name})
    skill_rows.append({
        "first": s["first"], "last": s["last"], "age": s.get("age"),
        "wiki_skills": wiki_skills, "tool_skills": tool_skills,
    })
    if diffs:
        report.append({"first": s["first"], "last": s["last"], "household": s.get("household"), "title": title, "diffs": diffs, "wiki_skills": wiki_skills, "tool_skills": tool_skills})

Path("data/wiki_audit.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
Path("data/wiki_skill_pairs.json").write_text(json.dumps(skill_rows, indent=1), encoding="utf-8")
print("sims with discrepancies", len(report), "of", len(texts))
counts = {}
for row in report:
    for d in row["diffs"]:
        counts[d["kind"]] = counts.get(d["kind"], 0) + 1
print("counts", counts)
for row in report[:80]:
    print(row["first"], row["last"], row["household"], row["diffs"][:6])
