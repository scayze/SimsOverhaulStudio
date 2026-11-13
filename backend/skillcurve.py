"""The game's skill XP-to-level curves.

The binary household template stores XP, not a level. The install files do not
store the XP thresholds directly; they are global per skill level type (adult,
child, toddler). These tables are calibrated against the game's own seeded XP
values (e.g. 1540 -> 2, 7300 -> 4, 19780 -> 6, 29290 -> 7, 43360 -> 8,
60460 -> 9) and the child/toddler seed values (e.g. 7749 -> child 5,
10899 -> child 6, 299 -> toddler 2, 579 -> toddler 3).
"""
from __future__ import annotations

# index = level; two leading zeros so a present skill with 0 XP is level 1.
ADULT_THRESHOLDS = [0, 0, 1000, 3000, 5000, 9000, 15000, 25000, 40000, 60000, 80000]
CHILD_THRESHOLDS = [0, 0, 1000, 2000, 5000, 7500, 10000, 14000, 18000, 21000, 25000]
# Toddler fundamentals have five levels, not ten.
TODDLER_THRESHOLDS = [0, 0, 200, 500, 800, 1100]
# Vampire Lore has 15 levels.
VAMPIRE_THRESHOLDS = [0, 0, 300, 1000, 2000, 3500, 5500, 8000, 11000, 15000, 20000, 26000, 33000, 41000, 50000, 60000]

# Backwards-compatible alias for the adult curve.
SKILL_THRESHOLDS = ADULT_THRESHOLDS


def level_type_for_tuning(tuning: str | None) -> str:
    low = (tuning or "").lower()
    if "vampirelore" in low:
        return "vampire"
    if "toddler" in low or "infant" in low:
        return "toddler"
    if "child" in low:
        return "child"
    return "adult"


def thresholds_for(level_type: str = "adult") -> list[int]:
    if level_type == "vampire":
        return VAMPIRE_THRESHOLDS
    if level_type == "toddler":
        return TODDLER_THRESHOLDS
    if level_type == "child":
        return CHILD_THRESHOLDS
    return ADULT_THRESHOLDS


def level_for_xp(xp: float, level_type: str = "adult") -> int:
    if xp is None or xp <= 0:
        return 1
    thresholds = thresholds_for(level_type)
    level = 0
    for index, threshold in enumerate(thresholds):
        if xp >= threshold:
            level = index
    return max(1, min(len(thresholds) - 1, level))
