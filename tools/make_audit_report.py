import json
import collections
from pathlib import Path

rows = json.loads(Path("data/wiki_audit.json").read_text(encoding="utf-8"))
non_action = {"aspiration_track_only", "family_extra_link", "skill_level1_unlisted"}
kinds = collections.Counter()
sims_by_kind = collections.defaultdict(set)
actionable = []
nonact = collections.Counter()
for row in rows:
    act = []
    for diff in row["diffs"]:
        kinds[diff["kind"]] += 1
        sims_by_kind[diff["kind"]].add((row["first"], row["last"]))
        if diff["kind"] in non_action:
            nonact[diff["kind"]] += 1
        else:
            act.append(diff)
    if act:
        actionable.append((row, act))

lines = ["# Sim Overhaul Studio - wiki audit", ""]
lines.append(f"Fetched 390 wiki pages; {len(rows)} sims have at least one flag against the install-derived project.")
lines.append("")
lines.append("## Flag counts")
lines.append("")
lines.append("| Kind | Diffs | Sims |")
lines.append("|---|---:|---:|")
for kind, count in kinds.most_common():
    lines.append(f"| {kind} | {count} | {len(sims_by_kind[kind])} |")
lines.append("")
lines.append("## Actionable discrepancies (install vs wiki)")
lines.append("")
lines.append("These exclude track-only aspirations, level-1 baseline skills and extended family links that the infobox does not list.")
lines.append("")
for row, act in actionable:
    parts = []
    for diff in act:
        kind = diff["kind"]
        if kind == "skill_level":
            parts.append(f"skill {diff['skill']} wiki {diff['wiki']} tool {diff['tool']}")
        elif kind == "skill_missing_tool":
            parts.append(f"skill missing {diff['skill']} (wiki {diff['wiki']})")
        elif kind == "skill_extra_tool":
            parts.append(f"skill extra {diff['skill']} (tool {diff['tool']})")
        elif kind == "trait_missing_tool":
            parts.append(f"trait missing {diff['trait']}")
        elif kind == "trait_extra_tool":
            parts.append(f"trait extra {diff['trait']}")
        elif kind == "career":
            parts.append(f"career wiki {diff['wiki']} tool {diff['tool']}")
        elif kind == "gender":
            parts.append(f"gender wiki {diff['wiki']} tool {diff['tool']}")
        elif kind == "age":
            parts.append(f"age wiki {diff['wiki']} tool {diff['tool']}")
        elif kind == "family_missing_link":
            parts.append(f"family missing {diff['relation']} {diff['name']}")
        elif kind == "aspiration":
            parts.append(f"aspiration wiki {diff['wiki']} track {diff.get('track', '')}")
        else:
            parts.append(str(diff))
    lines.append(f"- **{row['first']} {row['last']}** ({row.get('household') or ''}): " + "; ".join(parts))
lines.append("")
lines.append("## Not actionable / source limitations")
lines.append("")
lines.append(f"- Aspiration track only (install does not store the specific aspiration): {nonact['aspiration_track_only']} flags.")
lines.append(f"- Level-1 baseline skills (stored as 100 XP; not shown by the studio): {nonact['skill_level1_unlisted']} flags.")
lines.append(f"- Extended/derived family links not listed in the wiki infobox: {nonact['family_extra_link']} flags.")
Path("data/audit_report.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote audit_report.md", len(lines), "lines")
