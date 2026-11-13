"""Derived & curated game data for Sim Overhaul Studio.

Turns the raw catalog (built from the game's SimData + your Mods XML tuning)
into the structures the UI shows: short trait condition labels, accurate
compatibility filters, grouped careers/degrees, resolved aspirations and
genealogy relation semantics. Read-only, stdlib only.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. Trait conditions — short and specific
# ---------------------------------------------------------------------------
# Ordered: the most specific icon-path marker must come first.
CONDITION_MARKERS: list[tuple[str, str]] = [
    ("/Reward Traits/Aspiration Reward/", "aspiration_reward"),
    ("/Reward Traits/Career Reward/", "career_reward"),
    ("/Reward Traits/Reward Store/", "reward_store"),
    ("/Reward Traits/Food Mastery/", "food_mastery"),
    ("/Reward Traits/Getaway/", "getaway_reward"),
    ("/Reward Traits/Mountaineer/", "mountaineer_reward"),
    ("/Reward Traits/", "reward"),
    ("/Bonus Traits/", "bonus"),
    ("/Toddler Traits/Toddler Quirks/", "toddler_quirk"),
    ("/Toddler Traits/Toddler Skill Rewards/", "toddler_skill_reward"),
    ("/Toddler Traits/", "toddler"),
    ("/Infants/Infant Quirks/", "infant_quirk"),
    ("/Infants/Infant Reward Traits/", "infant_reward"),
    ("/Infants/", "infant"),
    ("/Child and Teen/Character Values/", "character_value"),
    ("/Child and Teen/Child Aspiration Rewards/", "child_aspiration_reward"),
    ("/Child and Teen/Childhood phases/", "childhood_phase"),
    ("/Child and Teen/Formative Moments/", "formative_moment"),
    ("/Child and Teen/Confidence/", "confidence"),
    ("/Child and Teen/High school + Teen/", "teen"),
    ("/Child and Teen/", "child_teen"),
    ("/Pet Traits/", "pet"),
    ("/Fears/", "fear"),
    ("/Misc Traits/Ghost Types/", "ghost_type"),
    ("/Misc Traits/Grief Types/", "grief_type"),
    ("/Misc Traits/Inherited Traits/", "inherited"),
    ("/Misc Traits/Life States/", "life_state"),
    ("/Misc Traits/", "special"),
    ("/Attraction/", "attraction"),
    ("/Lifestyles/", "lifestyle"),
    ("/Perk Trees/", "perk"),
    ("/Kuttoe Traits Icons/", "modded"),
    ("/Relationship Bits/", "relationship_bit"),
    ("/Sentiments/", "sentiment"),
    ("/Main Traits/", "cas_personality"),
]

# category -> (short label, where it comes from, one specific sentence)
CONDITIONS: dict[str, tuple[str, str, str]] = {
    "cas_personality": ("CAS personality trait", "Create-a-Sim", "Picked in CAS (three slots, teens and older); conflicts with its opposite trait."),
    "reward_store": ("Reward Store trait", "Satisfaction points", "Bought in the Rewards Store with Satisfaction Points, not chosen in CAS."),
    "aspiration_reward": ("Aspiration reward trait", "Aspiration completion", "Granted automatically when the matching aspiration is completed."),
    "career_reward": ("Career reward trait", "Career milestone", "Earned at the top of a specific career."),
    "bonus": ("Bonus trait", "Gameplay / life state", "Added by the game for an occult state, lot, event or aspiration — not a CAS choice."),
    "reward": ("Reward trait", "Gameplay reward", "Earned through gameplay (skills, events, challenges), not selectable in CAS."),
    "food_mastery": ("Food mastery reward", "Food challenges", "Earned by mastering food-related challenges."),
    "getaway_reward": ("Getaway reward trait", "Getaway events", "Earned from retreat / getaway competitions (Adventure Awaits)."),
    "mountaineer_reward": ("Mountaineer reward trait", "Mountain climbing", "Earned through mountain-climbing excursions (Snowy Escape)."),
    "toddler": ("Toddler trait", "Create-a-Sim", "Toddlers only; one personality trait."),
    "toddler_quirk": ("Toddler quirk", "Toddler care", "Developed from how a toddler is raised."),
    "toddler_skill_reward": ("Toddler skill reward", "Maxed toddler skills", "Granted when all toddler skills are maxed."),
    "infant": ("Infant trait", "Create-a-Sim", "Infants only."),
    "infant_quirk": ("Infant quirk", "Infant care", "Developed during the infant stage."),
    "infant_reward": ("Infant reward trait", "Infant milestones", "Earned from infant development."),
    "child_teen": ("Child / teen trait", "Parenthood / High School Years", "Age-specific trait gained through upbringing or school."),
    "character_value": ("Character value trait", "Parenthood", "Earned by raising a character value to an extreme."),
    "child_aspiration_reward": ("Child aspiration reward", "Child aspiration", "Granted for completing a childhood aspiration."),
    "childhood_phase": ("Childhood phase", "Growing Together", "A temporary phase a child goes through."),
    "formative_moment": ("Formative moment", "Growing Together", "A lasting trait from a childhood event."),
    "confidence": ("Confidence trait", "Growing Together", "Earned through childhood confidence milestones."),
    "teen": ("Teen trait", "High School Years", "Teens only; often tied to high school reputation or phases."),
    "pet": ("Pet trait", "Create-a-Sim / pet", "Only for the matching cat, dog or horse species."),
    "fear": ("Fear", "Wants & Fears", "A temporary fear developed after a bad experience; clears when confronted."),
    "ghost_type": ("Ghost trait", "Death type", "Set by how a sim died; only meaningful for ghosts."),
    "grief_type": ("Grief trait", "Life & Death", "A temporary bereavement state after a loss."),
    "inherited": ("Inherited trait", "Family line", "Passed down from a sim's family."),
    "life_state": ("Life-state trait", "Occult life state", "Marks an occult type; needs the matching Occult setting."),
    "special": ("Special trait", "Gameplay systems", "Internal or system-specific trait (luck, ailments, werewolf quirks…)."),
    "attraction": ("Attraction trait", "Lovestruck / CAS", "Turn-ons, romance styles and ways of life, managed in the Attraction panel."),
    "lifestyle": ("Lifestyle trait", "Lifestyles", "Earned through repeated habits; can be lost again."),
    "perk": ("Occult perk", "Perk trees", "Bought with perk points in an occult perk tree."),
    "modded": ("Modded trait", "Your Mods folder", "Custom trait added by a mod; requires that mod installed."),
    "relationship_bit": ("Relationship bit", "Relationships", "A flag on the relationship between two sims."),
    "sentiment": ("Sentiment", "Shared events", "A temporary feeling one sim has about another."),
    "generic_trait": ("Trait", "Game files", "A trait tuning from the game or a mod."),
}

CONDITION_GUIDE_ORDER = [
    "cas_personality", "reward_store", "aspiration_reward", "career_reward",
    "bonus", "lifestyle", "fear", "toddler", "infant", "child_teen", "pet",
    "attraction", "perk", "modded",
]


def condition_category(item: dict) -> str:
    url = (item.get("icon_pack") or item.get("icon") or "").replace("%20", " ")
    for marker, category in CONDITION_MARKERS:
        if marker in url:
            return category
    tuning = (item.get("tuning") or "").lower()
    if "reward" in tuning:
        return "reward"
    if "bonus" in tuning:
        return "bonus"
    return "generic_trait"


def condition_info(item: dict) -> dict:
    category = condition_category(item)
    label, source, detail = CONDITIONS.get(category, CONDITIONS["generic_trait"])
    restrictions = []
    if item.get("species_hint") and item["species_hint"] != "Human":
        restrictions.append(f"{item['species_hint']} only")
    if item.get("occult_hint"):
        restrictions.append(f"{item['occult_hint']} only")
    if item.get("npc"):
        restrictions.append("NPC / service role")
    if item.get("modded"):
        restrictions.append("Requires the mod")
    return {
        "label": label, "source": source, "detail": detail,
        "assignable": "Restricted" if restrictions else "Always assignable",
        "restrictions": restrictions,
    }


def condition_guide() -> list[dict]:
    return [
        {"id": c, "label": CONDITIONS[c][0], "detail": CONDITIONS[c][2]}
        for c in CONDITION_GUIDE_ORDER
    ]


# ---------------------------------------------------------------------------
# 2. Compatibility filters (age / species / occult)
# ---------------------------------------------------------------------------
ALL_AGES = ["Baby", "Toddler", "Child", "Teen", "Young Adult", "Adult", "Elder"]
TEEN_UP = ["Teen", "Young Adult", "Adult", "Elder"]
ADULT_UP = ["Young Adult", "Adult", "Elder"]


def _icon(item) -> str:
    # ``icon_pack`` keeps the icon-pack path used for condition/age hints even
    # when ``icon`` points at the SDK-extracted game icon endpoint.
    return (item.get("icon_pack") or item.get("icon") or "").replace("%20", " ")


def compatible_ages(item: dict, kind: str) -> list[str] | None:
    """Return the life stages this item can be assigned to, or None for any."""
    url = _icon(item)
    tuning = (item.get("tuning") or "").lower()
    hint = item.get("age_hint")
    if hint and hint in ALL_AGES:
        return [hint]
    # The SDK catalog carries the tuning's real age list; use it before the
    # icon-folder heuristics.
    listed = [age for age in (item.get("ages") or []) if age in ALL_AGES]
    if listed and len(listed) < len(ALL_AGES):
        return listed

    if kind == "traits":
        if "/Infants/" in url:
            return ["Infant"]
        if "/Toddler Traits/" in url:
            return ["Toddler"]
        if "/Child and Teen/High school + Teen/" in url:
            return ["Teen"]
        if "/Child and Teen/" in url:
            return ["Child", "Teen"]
        if "/Main Traits/" in url:
            return TEEN_UP
        if "/Attraction/" in url:
            return ADULT_UP
        if "/Fears/" in url or "/Lifestyles/" in url or "/Perk Trees/" in url:
            return TEEN_UP
        if "/Reward Traits/" in url or "/Bonus Traits/" in url or "/Misc Traits/" in url:
            return ALL_AGES
        for word, ages in (("toddler", ["Toddler"]), ("infant", ["Infant"]),
                           ("child", ["Child"]), ("teen", ["Teen"])):
            if re.search(rf"\b{word}\b", tuning):
                return ages
    elif kind == "skills":
        for word, ages in (("infant", ["Infant"]), ("toddler", ["Toddler"]),
                           ("child", ["Child"]), ("teen", ["Teen"])):
            if word in tuning:
                return ages
        return TEEN_UP
    elif kind == "careers":
        if "career_teen" in tuning or "highschool" in tuning or "_teen_" in tuning:
            return ["Teen"]
        if "career_child" in tuning or "gradeschool" in tuning:
            return ["Child"]
        return ADULT_UP
    elif kind == "aspirations":
        if hint:
            return [hint]
        if "child" in tuning:
            return ["Child"]
        if "teen" in tuning:
            return ["Teen"]
        return TEEN_UP
    elif kind == "milestones":
        if "infant" in tuning:
            return ["Infant"]
        if "toddler" in tuning:
            return ["Toddler"]
        if "child" in tuning:
            return ["Child"]
        return ALL_AGES
    return None


def age_label(ages: list[str] | None) -> str:
    if not ages or len(ages) == len(ALL_AGES):
        return ""
    if ages == TEEN_UP:
        return "Teen+"
    if ages == ADULT_UP:
        return "Young Adult+"
    return " / ".join(ages)


def species_from_icon(item: dict) -> str | None:
    url = _icon(item)
    if "/Pet Traits/Cats/" in url or "/Horse Skills/" in url:
        return "Horse" if "/Horse Skills/" in url else "Cat"
    if "/Pet Traits/Dogs/" in url:
        return "Dog"
    if "/Pet Traits/Horses/" in url:
        return "Horse"
    if "/Pet Traits/" in url:
        return item.get("species_hint")
    return item.get("species_hint")


def occult_from_icon(item: dict) -> str | None:
    url = _icon(item)
    for folder, name in (("Vampires", "Vampire"), ("Spellcasters", "Spellcaster"),
                         ("Werewolves", "Werewolf"), ("Ghosts", "Ghost"),
                         ("Fairies", "Fairy")):
        if f"/Perk Trees/{folder}/" in url:
            return name
    return item.get("occult_hint")


# ---------------------------------------------------------------------------
# 3. Careers & degrees
# ---------------------------------------------------------------------------
CAREER_GROUPS: list[dict] = [
    {"id": "full_time", "label": "Full-time careers", "hint": "Standard careers with promotion levels and specialisations."},
    {"id": "active", "label": "Active careers", "hint": "Follow your sim to work."},
    {"id": "university", "label": "University & education jobs", "hint": "Discover University careers and campus roles."},
    {"id": "part_time", "label": "Part-time jobs", "hint": "Shorter shifts, can be combined with school."},
    {"id": "teen_child", "label": "Teen & child jobs / school", "hint": "Grade school, high school and teen work."},
    {"id": "afterschool", "label": "After-school & volunteering", "hint": "Scouts, drama club, sports teams."},
    {"id": "freelance", "label": "Freelance & odd jobs", "hint": "Gig-based self-employment."},
    {"id": "npc", "label": "NPC & service jobs", "hint": "Roles the game assigns to townies."},
    {"id": "quest", "label": "Quests & special assignments", "hint": "Story/quest careers."},
    {"id": "retired", "label": "Retired & unemployed", "hint": "Placeholder career states."},
    {"id": "mod", "label": "Modded careers", "hint": "Custom careers from your Mods folder."},
    {"id": "other", "label": "Other careers", "hint": "Anything else in the game files."},
]

UNIVERSITY_WORDS = ("education", "professor", "law", "engineer", "highereducation", "university")


def career_group(item: dict) -> str:
    tuning = (item.get("tuning") or "").lower()
    label = (item.get("label") or "").lower()
    if any(w in tuning or w in label for w in UNIVERSITY_WORDS):
        return "university"
    if item.get("modded"):
        return "mod"
    if item.get("npc") or "_npc_" in tuning or label.startswith("npc "):
        return "npc"
    if "retired" in tuning or "unemployed" in tuning or "stayathome" in tuning:
        return "retired"
    if "quest" in tuning or "scenario" in tuning:
        return "quest"
    if "active" in tuning or "detective" in label or "reaper" in label:
        return "active"
    if "freelancer" in tuning or "oddjob" in tuning or "odd job" in label:
        return "freelance"
    if "parttime" in tuning or "part time" in label:
        return "part_time"
    if tuning.startswith("career_teen") or tuning.startswith("career_child") or "highschool" in tuning or "high school" in label:
        return "teen_child"
    if "volunteer" in tuning or "hsteam" in tuning or "afterschool" in tuning:
        return "afterschool"
    if tuning.startswith("career_adult") or "career" in tuning:
        return "full_time"
    return "other"


def career_family(tuning: str) -> str:
    t = tuning or ""
    low = t.lower()
    for prefix in ("careertracks_", "careertrack_", "tunablecareertrack_", "careertracks", "careertrack", "career_"):
        if low.startswith(prefix):
            t = t[len(prefix):]
            break
    t = re.split(r"[_\s]*track\d*", t, flags=re.I)[0]
    t = re.split(r"[_\s]*level\d*", t, flags=re.I)[0]
    t = t.replace("_", " ")
    t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", t)
    t = re.sub(r"\s*(main|basic|npc)\s*", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return t.title() if t else "Career"


MAJORS: list[dict] = [
    {"id": "Art History", "skill": "Painting, Writing", "careers": ["Painter", "Writer", "Style Influencer"]},
    {"id": "Biology", "skill": "Gardening, Fishing", "careers": ["Doctor (Active)", "Scientist (Active)", "Conservationist"]},
    {"id": "Communications", "skill": "Charisma, Writing", "careers": ["Business", "Politician", "Entertainer", "Social Media"]},
    {"id": "Computer Science", "skill": "Programming, Logic", "careers": ["Tech Guru", "Engineer", "Computer Engineer"]},
    {"id": "Culinary Arts", "skill": "Cooking, Gourmet Cooking, Mixology", "careers": ["Culinary", "Chef", "Mixologist"]},
    {"id": "Drama", "skill": "Acting, Charisma", "careers": ["Actor", "Entertainer"]},
    {"id": "Economics", "skill": "Logic, Charisma", "careers": ["Business", "Investor", "Law"]},
    {"id": "Fine Art", "skill": "Painting", "careers": ["Painter", "Style Influencer", "Interior Decorator"]},
    {"id": "History", "skill": "Writing, Logic, Research & Debate", "careers": ["Writer", "Professor", "Law"]},
    {"id": "Language and Literature", "skill": "Writing, Charisma", "careers": ["Writer", "Journalist", "Professor"]},
    {"id": "Physics", "skill": "Logic, Rocket Science", "careers": ["Astronaut", "Scientist (Active)", "Engineer"]},
    {"id": "Psychology", "skill": "Charisma, Logic", "careers": ["Doctor (Active)", "Romance Consultant", "Professor"]},
    {"id": "Villainy", "skill": "Mischief, Logic", "careers": ["Criminal", "Secret Agent (Villain)"]},
]


def major_for_degree(label: str) -> dict | None:
    probe = (label or "").lower().replace("and", "").replace(" ", "")
    for major in MAJORS:
        if major["id"].lower().replace("and", "").replace(" ", "") in probe:
            return major
    return None


def career_branches(catalog: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for track in catalog.get("career_tracks", []):
        tuning = track.get("tuning", "")
        # NPC/service tracks are not playable career branches.
        if "npc" in tuning.lower():
            continue
        family = career_family(tuning)
        family = CAREER_FAMILY_ALIASES.get(family, family)
        out.setdefault(family, []).append({
            "id": track["id"], "label": track["label"],
            "tuning": tuning, "pack": track.get("pack_label", ""),
            "main": is_main_track(tuning, track.get("label", "")),
        })
    # Keep only careers that actually define a shared track plus branch tracks.
    out = {
        family: tracks
        for family, tracks in out.items()
        if any(t["main"] for t in tracks) and any(not t["main"] for t in tracks)
    }
    for t in UNIVERSITY_COURSE_TRACKS:
        out.setdefault("University student", []).append(
            {**t, "pack": "Discover University", "main": False}
        )
    return out


# ---------------------------------------------------------------------------
# 3b. University student (active)
# ---------------------------------------------------------------------------
# Discover University enrolment is a real career tuning, but its name does not
# start with "career_", so the generic scanner drops it. Ship it explicitly.
UNIVERSITY_CAREER = {
    "id": 0x369D2, "label": "University student (active)",
    "tuning": "University_BaseCareer", "class": "UniversityCourseCareerSlot",
    "pack": "EP08", "pack_label": "Discover University", "modded": False,
    "source": "game", "age_hint": "", "species_hint": "", "occult_hint": "",
    "npc": False, "group": "university", "university_student": True,
    "icon": "/icons/College.ico",
}
UNIVERSITY_COURSE_TRACKS = [
    {"id": 0x3343C, "label": "Course slot A", "tuning": "university_CourseTrack_A", "family": "University student"},
    {"id": 0x33447, "label": "Course slot B", "tuning": "university_CourseTrack_B", "family": "University student"},
    {"id": 0x33448, "label": "Course slot C", "tuning": "university_CourseTrack_C", "family": "University student"},
    {"id": 0x33449, "label": "Course slot D", "tuning": "university_CourseTrack_D", "family": "University student"},
]

# ---------------------------------------------------------------------------
# 3c. Reward-trait effects
# ---------------------------------------------------------------------------
# A career/aspiration reward trait only makes sense with the matching (ex-)
# career or aspiration. When one is granted, the studio also applies these.
CAREER_REWARD_HINTS = {
    "grim": "reaper", "scouting": "scouting", "gamer": "tech guru",
    "sea": "conservationist", "healer": "doctor", "doctor": "doctor",
    "repairer": "handy", "engineer": "engineer", "noble": "noble",
    "blood": "noble", "hustler": "noble", "stamina": "athletic",
    "speaker": "politician", "crooner": "entertainer", "critic": "critic",
    "connected": "critic", "romancer": "noble", "magister": "scientist",
    "sickness": "doctor", "people": "politician", "master of the sea": "conservationist",
}
ASPIRATION_REWARD_SKILLS = {
    "professional": ["Charisma"], "handy": ["Handiness"], "fresh chef": ["Cooking"],
    "master mixer": ["Mixology"], "poetic": ["Writing"], "webmaster": ["Programming"],
    "player": ["Romance"], "sleight of hand": ["Mischief"], "high education": ["Logic"],
    "higher education": ["Logic"], "treasure hunter": ["Archaeology"],
    "animal whisperer": ["Pet Training"], "world renowned actor": ["Acting"],
}


def reward_effects(item: dict, catalog: dict) -> dict:
    """Suggest the career / aspiration / skills a reward trait belongs to."""
    cat = condition_category(item)
    if cat not in ("career_reward", "aspiration_reward"):
        return {}
    label = (item.get("label") or "").lower()
    out = {"category": cat, "career": None, "aspiration": None, "skills": []}
    asp = [a for a in catalog.get("aspirations", []) if a["label"].lower() == label]
    if asp:
        out["aspiration"] = asp[0]
    else:
        for a in catalog.get("aspirations", []):
            al = a["label"].lower()
            if len(al) > 4 and (al in label or label in al):
                out["aspiration"] = a
                break
    careers = catalog.get("careers", [])
    for word, target in CAREER_REWARD_HINTS.items():
        if word in label:
            hit = next((c for c in careers if target in c["label"].lower()), None)
            if hit:
                out["career"] = hit
                break
    skills = catalog.get("skills", [])
    for word, names in ASPIRATION_REWARD_SKILLS.items():
        if word in label:
            for name in names:
                hit = next((s for s in skills if s["label"].lower() == name.lower()), None)
                if hit:
                    out["skills"].append(hit)
    return out


# Career level at which each career family branches, read from the game's
# ``careerLevels_*`` tunings. The main (shared) track defines levels 1..N and
# each branch track defines levels N+1..10, so the branch unlocks at N + 1.
CAREER_BRANCH_LEVELS = {
    "Activist": 5, "Astronaut": 8, "Athletic": 5, "Business": 7,
    "Civil Designer": 4, "Conservationist": 7, "Corporate Worker": 5,
    "Critic": 4, "Criminal": 6, "Culinary": 6, "Education Career": 6,
    "Engineer": 7, "Entertainer": 5, "Gardener Career": 5, "Law": 8,
    "Military": 6, "Mortician": 5, "Naturopathic": 6, "Painter": 7,
    "Park Worker": 8, "Romance Consultant": 8, "Secret Agent": 8,
    "Social Media": 4, "Style Influencer": 6, "Tech Guru": 7, "Writer": 6,
}
BRANCH_LEVEL = 5

# Some careers name their branch tracks without a ``Track2/Track3`` segment
# (Military Officer/Covert, Critic Arts/Food, ...). Map those track families
# onto their one real career so the branches are grouped correctly.
CAREER_FAMILY_ALIASES = {
    "Critic Arts": "Critic",
    "Critic Food": "Critic",
    "Education Career Administrator": "Education Career",
    "Education Career Professor": "Education Career",
    "Military Covert": "Military",
    "Military Officer": "Military",
    "Park Worker Park Counselor": "Park Worker",
    "Park Worker Park Ranger": "Park Worker",
}


def is_main_track(tuning: str, label: str = "") -> bool:
    """True for a career's shared (pre-branch) track."""
    text = f"{tuning} {label}".lower()
    return bool(
        re.search(
            r"(?:^|[_\s])track1(?:[_\s]|$)|(?:^|[_\s])(?:main|basic)(?:[_\s]|$)",
            text,
        )
    )


# ---------------------------------------------------------------------------
# 4. Aspiration tracks
# ---------------------------------------------------------------------------
ASPIRATION_FAMILIES = {
    "Popularity": {"A": "Friend of the World", "B": "Party Animal", "C": "Neighborhood Confidante"},
    "Knowledge": {"A": "Renaissance Sim", "B": "Computer Whiz", "C": "Nerd Brain"},
    "Fortune": {"A": "Fabulously Wealthy", "B": "Mansion Baron", "C": "Business Savvy"},
    "Family": {"A": "Successful Lineage", "B": "Big Happy Family", "C": "Super Parent"},
    "Love": {"A": "Soulmate", "B": "Serial Romantic", "C": "Player"},
    "Romance": {"A": "Soulmate", "B": "Serial Romantic", "C": "Player"},
    "Creativity": {"A": "Painter Extraordinaire", "B": "Bestselling Author", "C": "Musical Genius"},
    "Athletic": {"A": "Bodybuilder", "B": "Fitness Nut"},
    "Nature": {"A": "Freelance Botanist", "B": "The Curator", "C": "Angling Ace"},
    "Food": {"A": "Master Chef", "B": "Master Mixologist"},
    "Deviance": {"A": "Public Enemy", "B": "Chief of Mischief", "C": "Sleight of Hand"},
}


def resolve_aspiration(track_label: str, aspirations: list[dict]) -> dict | None:
    if not track_label:
        return None
    by_label = {a["label"].lower(): a for a in aspirations}
    by_tuning = {a.get("tuning", "").lower(): a for a in aspirations}
    label = track_label.strip()
    parts = label.split()
    if len(parts) >= 2 and parts[1] in ("A", "B", "C", "D"):
        family, letter = parts[0].title(), parts[1]
        name = ASPIRATION_FAMILIES.get(family, {}).get(letter)
        item = None
        if name:
            item = by_tuning.get(f"aspiration_{family}_{letter}1".lower()) or by_label.get(name.lower())
        if item is None:
            family_aspirations = [a for a in aspirations if a.get("tuning", "").lower().startswith(f"aspiration_{family.lower()}_")]
            known = set(ASPIRATION_FAMILIES.get(family, {}).values())
            item = next((a for a in family_aspirations if a["label"] in known), None)
            if item is None:
                item = next((a for a in family_aspirations if re.search(r"_[a-d]1$", a["tuning"], re.I)), None)
            if item is None and family_aspirations:
                item = family_aspirations[0]
        if item:
            return item
    item = by_label.get(label.lower())
    if item:
        return item
    norm = re.sub(r"[^a-z0-9]", "", label.lower())
    for a in aspirations:
        if re.sub(r"[^a-z0-9]", "", a["label"].lower()) == norm:
            return a
    return None


# ---------------------------------------------------------------------------
# 5. Genealogy relation semantics
# ---------------------------------------------------------------------------
RELATION_INFO: dict[str, tuple[str, str, int, str]] = {
    "Mother": ("Mother", "Child", 1, "parent"),
    "Father": ("Father", "Child", 1, "parent"),
    "Parent": ("Parent", "Child", 1, "parent"),
    "Sibling": ("Sibling", "Sibling", 0, "sibling"),
    "Half-Sibling": ("Half-Sibling", "Half-Sibling", 0, "sibling"),
    "Brother": ("Brother", "Sibling", 0, "sibling"),
    "Sister": ("Sister", "Sibling", 0, "sibling"),
    "Spouse": ("Spouse", "Spouse", 0, "partner"),
    "Partner": ("Partner", "Partner", 0, "partner"),
    "Fiancé(e)": ("Fiancé(e)", "Fiancé(e)", 0, "partner"),
    "Steady": ("Steady", "Steady", 0, "partner"),
    "Son": ("Son", "Parent", -1, "child"),
    "Daughter": ("Daughter", "Parent", -1, "child"),
    "Child": ("Child", "Parent", -1, "child"),
    "Descendant": ("Child", "Parent", -1, "child"),
    "Grandparent": ("Grandparent", "Grandchild", 2, "grandparent"),
    "Grandchild": ("Grandchild", "Grandparent", -2, "grandchild"),
    "Mother's Mother": ("Grandmother (maternal)", "Grandchild", 2, "grandparent"),
    "Mother's Father": ("Grandfather (maternal)", "Grandchild", 2, "grandparent"),
    "Father's Mother": ("Grandmother (paternal)", "Grandchild", 2, "grandparent"),
    "Father's Father": ("Grandfather (paternal)", "Grandchild", 2, "grandparent"),
    "Great Grandparent": ("Great-Grandparent", "Great-Grandchild", 3, "great_grandparent"),
    "Great Grandchild": ("Great-Grandchild", "Great-Grandparent", -3, "great_grandchild"),
    "Sibling's Child": ("Niece / Nephew", "Aunt / Uncle", -1, "collateral"),
    "Parent's Sibling": ("Aunt / Uncle", "Niece / Nephew", 1, "collateral"),
    "Cousin": ("Cousin", "Cousin", 0, "cousin"),
    "First Cousin Once Removed": ("Cousin (once removed)", "Cousin (once removed)", 0, "cousin"),
    "Grandparent's Sibling": ("Great-Aunt / Great-Uncle", "Great-Niece / Great-Nephew", 2, "collateral"),
    "Great Grandparent's Sibling": ("Great-Great-Aunt / Uncle", "Great-Great-Niece / Nephew", 3, "collateral"),
    "Sibling's Grandchild": ("Grand-Niece / Grand-Nephew", "Great-Aunt / Great-Uncle", -2, "collateral"),
    "Sibling's Great Grandchild": ("Great-Grand-Niece / Nephew", "Great-Great-Aunt / Uncle", -3, "collateral"),
    "Distant Relative": ("Distant Relative", "Distant Relative", 0, "relative"),
    "Relative": ("Relative", "Relative", 0, "relative"),
}


def relation_info(relation: str) -> dict:
    display, inverse, gen, category = RELATION_INFO.get(relation, (relation, "Relative", 0, "relative"))
    return {"label": display, "inverse": inverse, "generation": gen, "category": category}


# ---------------------------------------------------------------------------
# 5b. Milestone & relationship-bit explanations
# ---------------------------------------------------------------------------
def milestone_hint(item: dict) -> str:
    tuning = (item.get("tuning") or "").lower()
    if tuning.startswith("infantmilestones_"):
        return "Infant milestone — recorded during the infant stage when the baby does this (e.g. first word, first food, first bath)."
    if "dynasty_" in tuning:
        return "Dynasty milestone (Royalty & Legacy) — recorded when this dynasty event happens."
    if "earneddegree_" in tuning:
        return "Earned by graduating from university with this degree."
    if "became" in tuning and ("occult" in tuning or "vampire" in tuning or "mermaid" in tuning or "spellcaster" in tuning or "werewolf" in tuning or "fairy" in tuning or "plantsim" in tuning):
        return "Earned when the sim becomes this occult type."
    if "birthday" in tuning or "ageup" in tuning or "aged" in tuning:
        return "Earned when the sim ages up."
    if "died" in tuning or "death" in tuning:
        return "Earned when the sim dies."
    if "adopt" in tuning:
        return "Earned when the sim adopts a child or pet."
    if tuning.startswith("milestone_") or "toddler" in tuning:
        return "Toddler milestone — recorded during the toddler stage."
    if "career" in tuning:
        return "Earned by reaching a career milestone."
    if "relationship" in tuning or "romance" in tuning:
        return "Earned through a relationship event."
    return "Earned through normal gameplay when the matching event happens."


def relationship_bit_hint(item: dict) -> str:
    tuning = (item.get("tuning") or "").lower()
    label = (item.get("label") or "").lower()
    if "sentiment" in tuning or "sentiment" in label:
        return "Sentiment — a temporary feeling one sim has about another, created by shared events and shown in the relationship panel."
    if any(w in tuning for w in ("parent", "mother", "father", "sibling", "child", "grand", "cousin", "aunt", "uncle")):
        return "Family relationship bit — defines the family connection between two sims."
    if any(w in tuning or w in label for w in ("spouse", "married", "fiance", "partner", "romance", "lover", "crush")):
        return "Romantic relationship bit — defines a romantic connection between two sims."
    if any(w in tuning or w in label for w in ("enemy", "hate", "dislike", "rival")):
        return "Negative relationship bit — set by hostile interactions."
    if any(w in tuning or w in label for w in ("friend", "best", "bff", "acquaintance")):
        return "Friendship relationship bit — set by friendly interactions."
    if any(w in tuning or w in label for w in ("coworker", "boss", "employee", "classmate", "neighbor")):
        return "Role relationship bit — set by a shared job, school or neighbourhood."
    return "Relationship bit — a flag on the relationship between two sims that gates interactions."


# ---------------------------------------------------------------------------
# 6. Frontend payload
# ---------------------------------------------------------------------------
def build_payload(catalog: dict) -> dict:
    return {
        "condition_guide": condition_guide(),
        "career_groups": CAREER_GROUPS,
        "majors": MAJORS,
        "career_branches": career_branches(catalog),
        "relations": {k: relation_info(k) for k in RELATION_INFO},
        "branch_level": BRANCH_LEVEL,
        "branch_levels": CAREER_BRANCH_LEVELS,
        "university_career": UNIVERSITY_CAREER,
    }
