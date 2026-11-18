"""Export a project as a new-save overhaul script mod (.ts4script)."""
from __future__ import annotations

import base64
import json
import re
import time
import zipfile
from pathlib import Path

from .settings import EXPORT_DIR

TEMPLATE = Path(__file__).resolve().parent / "templates" / "sim_overhaul.py"


def _safe(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip().replace(" ", "_")
    return cleaned or "SimOverhaul"


def export_config(project: dict) -> dict:
    sims = []
    for sim in project.get("sims", {}).values():
        entry = {
            "first": sim.get("first", ""),
            "last": sim.get("last", ""),
            "household": sim.get("household", ""),
        }
        if sim.get("traits"):
            entry["traits"] = [{"id": t.get("id"), "label": t.get("label")} for t in sim["traits"] if t.get("id")]
        if sim.get("remove_traits"):
            entry["remove_traits"] = [
                {"id": t.get("id"), "label": t.get("label")} for t in sim["remove_traits"] if t.get("id")
            ]
        if sim.get("skills"):
            entry["skills"] = [
                {"id": s.get("id"), "label": s.get("label"), "level": s.get("level", 1)}
                for s in sim["skills"]
                if s.get("id") and not s.get("level_unknown") and s.get("level") is not None
            ]
        if sim.get("career") and sim["career"].get("id"):
            entry["career"] = {
                "id": sim["career"]["id"],
                "label": sim["career"].get("label"),
                "level": sim["career"].get("level", 1),
            }
        if sim.get("career_track") and sim["career_track"].get("id"):
            entry["career_track"] = sim["career_track"]
        if sim.get("aspiration") and sim["aspiration"].get("id") and not sim["aspiration"].get("track"):
            entry["aspiration"] = {"id": sim["aspiration"]["id"], "label": sim["aspiration"].get("label")}
            if sim["aspiration"].get("track_id"):
                entry["aspiration"]["track_id"] = sim["aspiration"]["track_id"]
        if sim.get("funds") is not None:
            entry["funds"] = int(sim["funds"])
        if sim.get("occult"):
            entry["occult"] = sim["occult"]
        if sim.get("relationships"):
            entry["relationships"] = []
            for r in sim["relationships"]:
                if not r.get("target"):
                    continue
                target_sim = project.get("sims", {}).get(r["target"], {})
                entry["relationships"].append(
                    {
                        "target": f"{target_sim.get('first', '')}|{target_sim.get('last', '')}".strip("|")
                        or r["target"].split(":")[-1],
                        "target_household": target_sim.get("household", ""),
                        "friendship": r.get("friendship", 0),
                        "romance": r.get("romance", 0),
                        "bits": [{"id": b.get("id"), "label": b.get("label")} for b in r.get("bits", []) if b.get("id")],
                    }
                )
        if sim.get("family"):
            entry["family"] = []
            for f in sim["family"]:
                if not f.get("target"):
                    continue
                target_sim = project.get("sims", {}).get(f["target"], {})
                entry["family"].append(
                    {
                        "target": f"{target_sim.get('first', '')}|{target_sim.get('last', '')}".strip("|")
                        or f["target"].split(":")[-1],
                        "target_household": target_sim.get("household", ""),
                        "relation": f.get("relation"),
                    }
                )
        if sim.get("milestones"):
            entry["milestones"] = [{"id": m.get("id"), "label": m.get("label")} for m in sim["milestones"] if m.get("id")]
        if sim.get("degrees"):
            entry["degrees"] = [{"id": m.get("id"), "label": m.get("label")} for m in sim["degrees"] if m.get("id")]
        if sim.get("likes"):
            entry["likes"] = [{"id": m.get("id"), "label": m.get("label")} for m in sim["likes"] if m.get("id")]
        if sim.get("dislikes"):
            entry["dislikes"] = [{"id": m.get("id"), "label": m.get("label")} for m in sim["dislikes"] if m.get("id")]
        sims.append(entry)
    return {"name": project.get("name", "Sim Overhaul"), "sims": sims}


def export(project: dict) -> dict:
    config = export_config(project)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = _safe(project.get("name", "SimOverhaul"))
    folder = EXPORT_DIR / f"{safe}_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    config_json = json.dumps(config, indent=2, ensure_ascii=False)
    (folder / f"{safe}_config.json").write_text(config_json, encoding="utf-8")

    template = TEMPLATE.read_text(encoding="utf-8")
    encoded = base64.b64encode(config_json.encode("utf-8")).decode("ascii")
    script = template.replace("__CONFIG_B64__", encoded)
    script_path = folder / "sim_overhaul.py"
    script_path.write_text(script, encoding="utf-8")

    ts4script = folder / f"{safe}.ts4script"
    with zipfile.ZipFile(ts4script, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sim_overhaul.py", script)

    readme = f"""Sim Overhaul Studio - {project.get('name', 'Sim Overhaul')}
Generated {time.strftime('%d %b %Y %H:%M')}

INSTALL
-------
1. Copy "{safe}.ts4script" into:
   Documents\\Electronic Arts\\The Sims 4\\Mods
2. In game: Options > Game Options > Other > enable "Script Mods Allowed"
3. Start a NEW save (or load a save and run the console command below).
4. Load a household: the overhaul is applied once when the zone finishes loading.

The mod matches sims by first + last name. Sims that do not exist in the
save are skipped safely.

IN-GAME COMMANDS
----------------
Open the cheat console (Ctrl+Shift+C) and run:

    simoverhaul.apply     apply the overhaul immediately
    simoverhaul.report    write SimOverhaul_report.txt

A report is written to:
   Documents\\Electronic Arts\\The Sims 4\\SimOverhaul_report.txt

SIM COUNT: {len(config['sims'])}
"""
    (folder / "README.txt").write_text(readme, encoding="utf-8")

    return {
        "folder": str(folder),
        "ts4script": str(ts4script),
        "config": str(folder / f"{safe}_config.json"),
        "sims": len(config["sims"]),
    }
