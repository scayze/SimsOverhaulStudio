"""Project storage for Sim Overhaul Studio."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .settings import PROJECT_DIR

ACTIVE_FILE = PROJECT_DIR / "active_project.json"


def new_project(name: str = "My Sim Overhaul") -> dict:
    now = time.time()
    return {
        "name": name,
        "created": now,
        "updated": now,
        "sims": {},
        "dynasties": [],
        "data_version": 32,
        "origin": {"mode": "empty", "label": "empty project", "file": None},
    }


def load() -> dict:
    if ACTIVE_FILE.exists():
        try:
            data = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
            data.setdefault("sims", {})
            return data
        except (OSError, ValueError):
            pass
    project = new_project()
    save(project)
    return project


def save(project: dict) -> dict:
    project["updated"] = time.time()
    ACTIVE_FILE.write_text(json.dumps(project, indent=2), encoding="utf-8")
    return project


def blank_sim(first: str, last: str, household: str | None = None, source: str = "manual") -> dict:
    return {
        "key": f"{first}|{last}",
        "first": first,
        "last": last,
        "household": household or last,
        "household_key": household or last,
        "source": source,
        "source_ref": None,
        "age": "Adult",
        "gender": "Female",
        "species": "Human",
        "occult": "Human",
        "traits": [],
        "remove_traits": [],
        "skills": [],
        "career": None,
        "career_history": [],
        "aspiration": None,
        "funds": None,
        "relationships": [],
        "family": [],
        "degrees": [],
        "milestones": [],
        "likes": [],
        "dislikes": [],
        "notes": "",
        "data_quality": "manual",
    }


def upsert_sim(project: dict, sim: dict) -> dict:
    key = sim.get("key") or f"{sim.get('first','')}|{sim.get('last','')}"
    sim["key"] = key
    existing = project["sims"].get(key)
    if existing:
        existing.update({k: v for k, v in sim.items() if v not in (None, "", [], {})})
        return existing
    merged = blank_sim(sim.get("first", ""), sim.get("last", ""), sim.get("household"))
    merged.update(sim)
    merged["key"] = key
    project["sims"][key] = merged
    return merged


def add_sims(project: dict, sims: list[dict], source_ref: str | None = None) -> list[dict]:
    added = []
    for sim in sims:
        payload = dict(sim)
        payload.setdefault("household", payload.get("last"))
        # Keep a per-sim source_ref (e.g. the premade template id) when present;
        # only fill it in for entries that don't carry one.
        payload.setdefault("source_ref", source_ref)
        added.append(upsert_sim(project, payload))
    save(project)
    return added


def remove_sim(project: dict, key: str) -> None:
    project["sims"].pop(key, None)
    for sim in project["sims"].values():
        sim["relationships"] = [r for r in sim.get("relationships", []) if r.get("target") != key]
        sim["family"] = [f for f in sim.get("family", []) if f.get("target") != key]
    save(project)


def remove_household(project: dict, household_key: str) -> list[str]:
    keys = [k for k, sim in project.get("sims", {}).items() if sim.get("household_key") == household_key]
    if not keys:
        keys = [
            k
            for k, sim in project.get("sims", {}).items()
            if (sim.get("household") or sim.get("last")) == household_key
        ]
    for key in keys:
        project["sims"].pop(key, None)
    for sim in project["sims"].values():
        sim["relationships"] = [r for r in sim.get("relationships", []) if r.get("target") not in keys]
        sim["family"] = [f for f in sim.get("family", []) if f.get("target") not in keys]
    save(project)
    return keys
