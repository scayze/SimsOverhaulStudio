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
    from sims4_sdk.skills import (ADULT_CURVE, CHILD_CURVE, TODDLER_CURVE,
                                  VAMPIRE_LORE_CURVE, convert_skill_xp)
    curve = {"adult": ADULT_CURVE, "child": CHILD_CURVE,
             "toddler": TODDLER_CURVE, "vampire": VAMPIRE_LORE_CURVE}.get(level_type, ADULT_CURVE)
    return convert_skill_xp(max(0, float(xp or 0)), curve).level or 1


def level_for_skill(xp: float, skill_id: int, name: str, catalog=None) -> int:
    """Prefer the SDK's explicit tuning and curve, then the legacy estimate."""
    from . import sdk
    from sims4_sdk.skills import convert_skill_xp
    definition = catalog.statistic(skill_id) if catalog and hasattr(catalog, "statistic") else None
    if definition is not None and definition.is_skill is True and definition.skill_level_type:
        discovery = sdk.skill_curves()
        curve = discovery.for_skill(definition) if discovery is not None else None
        if curve is not None:
            level = convert_skill_xp(float(xp), curve).level
            if level is not None:
                return level
    return level_for_xp(xp, level_type_for_tuning(name))
