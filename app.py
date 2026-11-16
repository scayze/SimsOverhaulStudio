"""Sim Overhaul Studio - local desktop app (stdlib HTTP server + web UI)."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from backend import catalog as catalog_mod
from backend import exporter, gameicons, gamedata, images, premade_art, project as project_mod, saves, sdk, tray
from backend.icons import icon_for, icon_for_strict
from backend.settings import APP_DIR, paths

UI_DIR = APP_DIR / "ui"

SCAN_STATE = {"running": False, "message": "Not scanned yet", "current": 0, "total": 0, "done": False}
_SCAN_LOCK = threading.Lock()


# --------------------------------------------------------------------- helpers
def _json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if not length:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _run_scan() -> None:
    global SCAN_STATE
    try:
        def progress(message, current, total):
            SCAN_STATE.update(
                {"message": message, "current": current, "total": max(total, 1)}
            )

        SCAN_STATE.update({"running": True, "done": False, "current": 0, "total": 1, "message": "Starting scan"})
        # Rebuild the SDK snapshot first so newly installed packs/mods are seen.
        try:
            sdk.refresh(lambda message: SCAN_STATE.update({"message": message}))
        except Exception:
            pass
        payload = catalog_mod.build_catalog(progress)
        # Household composites and the full household-template dataset live in
        # client packages the catalog does not scan. Refresh them here too.
        try:
            from backend import templatedata
            SCAN_STATE["templates"] = templatedata.build_complete_dataset()["meta"]
            premade_art._CHECKED["done"] = False
            art = premade_art.ensure_premade_images()
            SCAN_STATE["premade_images"] = art
            premade_art.build_crops(force=True)
            gameicons.warm()
        except Exception:
            pass
        SCAN_STATE.update(
            {
                "running": False,
                "done": True,
                "message": "Scan complete",
                "current": 1,
                "total": 1,
                "counts": payload["meta"]["counts"],
                "seconds": payload["meta"]["seconds"],
            }
        )
    except Exception as exc:  # pragma: no cover
        SCAN_STATE.update({"running": False, "done": False, "message": f"Scan failed: {exc}"})


def _tray_household_count() -> int:
    if not paths.tray or not paths.tray.is_dir():
        return 0
    try:
        return sum(1 for p in paths.tray.iterdir() if p.name.lower().endswith(".householdbinary"))
    except OSError:
        return 0


def _catalog_payload(kind: str, query: str, source: str, include_batuu: bool = False, include_npc: bool = False, age: str = "", species: str = "", occult: str = "") -> dict:
    payload = catalog_mod.load_catalog()
    raw = list(payload["catalog"].get(kind, []))
    # Discover University enrolment is a real career that the generic scanner
    # drops (its tuning is not named career_*). Expose it explicitly.
    if kind == "careers":
        raw.append(dict(gamedata.UNIVERSITY_CAREER))
    elif kind == "career_tracks":
        raw.extend(dict(t) for t in gamedata.UNIVERSITY_COURSE_TRACKS)

    # Resolve icons first: the icon pack folder is the most reliable source of
    # age / species / occult compatibility, so filters must run afterwards.
    items = []
    for i in raw:
        item = dict(i)
        pack_icon = i.get("icon") or (
            icon_for_strict(kind, i.get("label", ""), i.get("tuning", ""))
            if kind == "traits" and not i.get("modded")
            else icon_for(kind, i.get("label", ""), i.get("tuning", ""))
        )
        item["icon_pack"] = pack_icon
        icon_key = i.get("icon_key")
        item["icon"] = gameicons.icon_url(icon_key, pack_icon) if icon_key else pack_icon
        if kind == "traits":
            item["species_hint"] = gamedata.species_from_icon(item) or "Human"
            item["occult_hint"] = gamedata.occult_from_icon(item)
            item["ages"] = gamedata.compatible_ages(item, kind)
            item["age_hint"] = gamedata.age_label(item["ages"])
            item["condition"] = gamedata.condition_info(item)
            item["icon_group"] = item["condition"]["label"]
            effects = gamedata.reward_effects(item, payload["catalog"])
            if effects:
                item["reward_effects"] = {
                    "category": effects["category"],
                    "career": effects["career"]["label"] if effects.get("career") else None,
                    "career_id": effects["career"]["id"] if effects.get("career") else None,
                    "aspiration": effects["aspiration"]["label"] if effects.get("aspiration") else None,
                    "aspiration_id": effects["aspiration"]["id"] if effects.get("aspiration") else None,
                    "skills": [{"id": s["id"], "label": s["label"]} for s in effects.get("skills", [])],
                }
        else:
            item["ages"] = gamedata.compatible_ages(item, kind)
            item["age_hint"] = gamedata.age_label(item["ages"])
        if kind == "careers":
            item["group"] = gamedata.career_group(item)
        elif kind == "career_tracks":
            fam = gamedata.career_family(item.get("tuning", ""))
            item["family"] = gamedata.CAREER_FAMILY_ALIASES.get(fam, fam)
            item["main"] = gamedata.is_main_track(item.get("tuning", ""), item.get("label", ""))
        elif kind == "degrees":
            major = gamedata.major_for_degree(item.get("label", ""))
            item["major"] = major["id"] if major else "Other"
        elif kind == "milestones":
            item["hint"] = gamedata.milestone_hint(item)
            # Drop the redundant "Life Milestone" / "Infant Milestones" prefix.
            item["label"] = re.sub(
                r"^(?:Life Milestone|Infant Milestones|Toddler Milestones|Milestone)\s+",
                "", item.get("label", ""),
            )
        elif kind == "relationship_bits":
            item["hint"] = gamedata.relationship_bit_hint(item)
        items.append(item)

    if kind == "traits":
        items = [i for i in items if i["icon"] or i.get("modded")]
    if kind == "degrees":
        items = [
            i for i in items
            if i.get("major") != "Other"
            and not i.get("label", "").startswith("Degree Traits")
            and i.get("label") not in ("Bartender", "Higher Education")
        ]
    if not include_batuu:
        items = [i for i in items if i.get("pack") != "GP09"]
    if not include_npc:
        items = [i for i in items if not i.get("npc")]
    if age:
        items = [i for i in items if not i.get("ages") or age in i["ages"]]
    if species and kind == "traits":
        items = [i for i in items if i.get("species_hint") == species]
    if occult and kind == "traits":
        items = [i for i in items if not i.get("occult_hint") or i["occult_hint"] == occult]
    if source == "ea":
        items = [i for i in items if not i.get("modded")]
    elif source == "mod":
        items = [i for i in items if i.get("modded")]
    if query:
        q = query.lower()
        items = [i for i in items if q in i.get("label", "").lower() or q in i.get("tuning", "").lower()]
    return {"items": items, "meta": payload["meta"]}


# ---------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "SimOverhaulStudio/1.0"

    def log_message(self, fmt, *args):  # quiet
        pass

    # ------------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route == "/" or route == "/index.html":
            return self._file(UI_DIR / "index.html")
        if route.startswith("/ui/"):
            safe = unquote(route.replace("/ui/", "", 1))
            target = (UI_DIR / safe).resolve()
            if UI_DIR.resolve() not in target.parents:
                return _json(self, {"error": "forbidden"}, 403)
            return self._file(target)

        if route.startswith("/icons/"):
            safe = unquote(route.replace("/icons/", "", 1))
            icons_dir = (APP_DIR / "sims icons").resolve()
            target = (icons_dir / safe).resolve()
            if not target.is_file():
                for sub in ("sims 2", "sims 4", "sims 4/_pack"):
                    cand = (icons_dir / sub / safe).resolve()
                    if cand.is_file():
                        target = cand
                        break
            if icons_dir not in target.parents:
                return _json(self, {"error": "forbidden"}, 403)
            return self._file(target)

        if route == "/api/icon":
            key = (qs.get("key") or [""])[0]
            fallback = (qs.get("fallback") or [""])[0]
            target = gameicons.icon_path(key)
            if target is not None:
                return self._file(target)
            if fallback.startswith("/"):
                self.send_response(302)
                self.send_header("Location", fallback)
                self.end_headers()
                return
            return self._file(gameicons.placeholder_path())

        if route == "/api/status":
            cache_exists = catalog_mod.CACHE_FILE.exists()
            meta = {}
            if cache_exists:
                try:
                    meta = json.loads(catalog_mod.CACHE_FILE.read_text(encoding="utf-8")).get("meta", {})
                except (OSError, ValueError):
                    meta = {}
            project = project_mod.load()
            return _json(
                self,
                {
                    "paths": paths.as_dict(),
                    "catalog": {"cached": cache_exists, "meta": meta, "scan": SCAN_STATE},
                    "saves": saves.list_saves(),
                    "tray_count": _tray_household_count(),
                    "project": {
                        "name": project.get("name"),
                        "sims": len(project.get("sims", {})),
                        "updated": project.get("updated"),
                    },
                },
            )

        if route == "/api/catalog":
            kind = (qs.get("kind") or ["traits"])[0]
            query = (qs.get("q") or [""])[0]
            source = (qs.get("source") or ["all"])[0]
            include_batuu = (qs.get("batuu") or ["0"])[0] == "1"
            include_npc = (qs.get("npc") or ["0"])[0] == "1"
            age = (qs.get("age") or [""])[0]
            species = (qs.get("species") or [""])[0]
            occult = (qs.get("occult") or [""])[0]
            try:
                return _json(self, _catalog_payload(kind, query, source, include_batuu, include_npc, age, species, occult))
            except Exception as exc:
                return _json(self, {"error": str(exc)}, 500)

        if route == "/api/catalog/status":
            return _json(self, SCAN_STATE)

        if route == "/api/gamedata":
            payload = catalog_mod.load_catalog()
            return _json(self, gamedata.build_payload(payload["catalog"]))

        if route == "/api/premade/images":
            return _json(self, premade_art.ensure_premade_images())

        if route == "/api/project/sim_template":
            key = (qs.get("key") or [""])[0]
            project = project_mod.load()
            try:
                sim = tray.sim_template_for(project, key)
            except Exception:
                sim = None
            return _json(self, {"sim": sim, "origin": project.get("origin")})

        if route == "/api/premade/refresh":
            return _json(self, {"crops": len(premade_art.build_crops(force=True))})

        if route == "/api/saves":
            return _json(self, {"saves": saves.list_saves()})

        if route == "/api/save":
            filename = (qs.get("file") or [""])[0]
            try:
                return _json(self, saves.parse_save(filename))
            except Exception as exc:
                return _json(self, {"error": str(exc)}, 404)

        if route == "/api/tray":
            return _json(self, {"households": tray.list_tray()})

        if route == "/api/tray/household":
            ident = (qs.get("id") or [""])[0]
            item = tray.get_household(ident)
            if item is None:
                return _json(self, {"error": "not found"}, 404)
            return _json(self, item)

        if route == "/api/tray/image":
            instance = (qs.get("instance") or [""])[0]
            kind = (qs.get("kind") or ["sim"])[0]
            kind = kind if kind == "sim" else "household"
            target = images.png_path(instance, kind) if (qs.get("format") or [""])[0] == "png" else None
            target = target or images.image_path(instance, kind)
            if target is None:
                return _json(self, {"error": "not found"}, 404)
            return self._file(target)

        if route == "/api/tray/image_mask":
            instance = (qs.get("instance") or [""])[0]
            kind = (qs.get("kind") or ["sim"])[0]
            target = images.mask_path(instance, kind if kind == "sim" else "household")
            if target is None:
                return _json(self, {"error": "not found"}, 404)
            return self._file(target)

        if route == "/api/premade/image":
            template = (qs.get("template") or [""])[0].lower().removeprefix("0x").zfill(16)
            if not all(c in "0123456789abcdef" for c in template):
                return _json(self, {"error": "bad template"}, 400)
            target = images.premade_png_path(template) if (qs.get("format") or [""])[0] == "png" else None
            target = (target or (APP_DIR / "data" / "premade_images" / f"{template}.jpg")).resolve()
            images_dir = (APP_DIR / "data" / "premade_images").resolve()
            if images_dir not in target.parents or not target.is_file():
                return _json(self, {"error": "not found"}, 404)
            return self._file(target)

        if route == "/api/premade/mask":
            template = (qs.get("template") or [""])[0]
            target = images.premade_mask_path(template)
            if target is None:
                return _json(self, {"error": "not found"}, 404)
            return self._file(target)

        if route == "/api/project":
            project = project_mod.load()
            try:
                if tray.enrich_premade_project(project):
                    project_mod.save(project)
            except Exception:
                pass
            return _json(self, project)

        return _json(self, {"error": "not found"}, 404)

    # ------------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802
        route = urlparse(self.path).path
        body = _read_body(self)

        if route == "/api/catalog/scan":
            with _SCAN_LOCK:
                if SCAN_STATE["running"]:
                    return _json(self, SCAN_STATE)
                thread = threading.Thread(target=_run_scan, daemon=True)
                thread.start()
            return _json(self, {"started": True})

        if route == "/api/project/save":
            data = body.get("project") or body
            if not isinstance(data, dict) or "sims" not in data:
                return _json(self, {"error": "invalid project"}, 400)
            project_mod.save(data)
            return _json(self, {"ok": True, "project": data})

        if route == "/api/project/reset":
            project = project_mod.new_project(body.get("name") or "My Sim Overhaul")
            project_mod.save(project)
            return _json(self, {"ok": True, "project": project})

        if route == "/api/project/add_sims":
            project = project_mod.load()
            sims = body.get("sims") or []
            if body.get("origin"):
                project["origin"] = body["origin"]
            added = project_mod.add_sims(project, sims, body.get("source_ref"))
            return _json(self, {"ok": True, "added": added, "project": project})

        if route == "/api/project/seed_tray_premades":
            project = project_mod.load()
            households = tray.seed_tray_premades()
            all_sims = []
            for hh in households:
                all_sims.extend(hh.get("sims", []))
            added = project_mod.add_sims(project, all_sims, "tray-premades")
            project["origin"] = {"mode": "tray", "label": "Tray library", "file": None}
            project_mod.save(project)
            return _json(self, {"ok": True, "added": added, "project": project, "households": len(households)})

        if route == "/api/project/seed_world_template":
            project = project_mod.load()
            world = tray.seed_premade_world()
            added = project_mod.add_sims(project, world.get("sims", []), "game-premades")
            project["dynasties"] = tray.seed_dynasties(project.get("sims", {}))
            project["data_version"] = 32
            project["origin"] = {"mode": "clean_world", "label": "clean new-save world", "file": None}
            project_mod.save(project)
            return _json(
                self,
                {
                    "ok": True,
                    "added": added,
                    "project": project,
                    "households": world.get("households", 0),
                    "save": None,
                    "save_label": "game premades",
                },
            )

        if route == "/api/project/remove_sim":
            project = project_mod.load()
            project_mod.remove_sim(project, body.get("key", ""))
            return _json(self, {"ok": True, "project": project})

        if route == "/api/project/remove_household":
            project = project_mod.load()
            removed = project_mod.remove_household(project, body.get("household_key", ""))
            return _json(self, {"ok": True, "removed": removed, "project": project})

        if route == "/api/project/from_save":
            project = project_mod.load()
            key = body.get("key", "")
            filename = body.get("file", "")
            sim = project.get("sims", {}).get(key)
            if not sim:
                return _json(self, {"error": "Sim not found."}, 404)
            try:
                parsed = saves.parse_save(filename)
                # The SDK save reader already returns traits, skills, careers,
                # likes and family links, so the save itself is the primary
                # source.  A Tray overlay is only used when it is richer.
                match = next(
                    (
                        row
                        for row in parsed.get("sims", [])
                        if row.get("first") == sim.get("first") and row.get("last") == sim.get("last")
                    ),
                    None,
                )
                rich = tray.enrich_save_sims(parsed.get("sims", []))
                overlay = rich.get((sim["first"].lower(), sim["last"].lower(), (sim.get("household") or sim["last"]).lower()))
                if overlay:
                    match = {**(match or {}), **{k: v for k, v in overlay.items() if v is not None}}
            except Exception as exc:
                return _json(self, {"error": str(exc)}, 404)
            if not match:
                return _json(self, {"error": "This sim could not be read from that save."}, 404)
            for field in ("age", "gender", "occult", "species", "traits", "likes", "dislikes",
                          "degrees", "skills", "career", "career_history", "career_track",
                          "aspiration", "milestones", "image", "image_mask", "image_kind",
                          "household_image", "household_image_mask"):
                if field in match and match[field] is not None:
                    sim[field] = match[field]
            sim["data_quality"] = "save_overlay"
            project_mod.save(project)
            return _json(self, {"ok": True, "project": project})

        if route == "/api/project/refresh_templates":
            try:
                from backend import templatedata
                meta = templatedata.build_complete_dataset()["meta"]
                premade_art.build_crops(force=True)
                return _json(self, {"ok": True, "meta": meta})
            except Exception as exc:
                return _json(self, {"error": str(exc)}, 500)

        if route == "/api/export":
            project = project_mod.load()
            if not project.get("sims"):
                return _json(self, {"error": "Add at least one sim before exporting."}, 400)
            try:
                result = exporter.export(project)
                return _json(self, {"ok": True, "result": result})
            except Exception as exc:
                return _json(self, {"error": str(exc)}, 500)

        return _json(self, {"error": "not found"}, 404)

    # ------------------------------------------------------------------ files
    def _file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return _json(self, {"error": "not found"}, 404)
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _open_window(url: str) -> None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
    ]
    for exe in candidates:
        if exe.exists():
            try:
                subprocess.Popen(
                    [
                        str(exe),
                        f"--app={url}",
                        "--window-size=1600,900",
                        "--disable-features=Translate",
                    ],
                    close_fds=True,
                )
                return
            except OSError:
                continue
    webbrowser.open(url)


def main() -> None:
    port = int(os.environ.get("SIMSTUDIO_PORT", "8765"))
    url = f"http://127.0.0.1:{port}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print("Sim Overhaul Studio")
        print(f"  Could not start on port {port}: {exc}")
        print("  The studio may already be running. Opening it instead...")
        _open_window(url)
        return
    server.daemon_threads = True
    print("Sim Overhaul Studio")
    print(f"  UI:   {url}")
    print(f"  Game: {paths.game}")
    print(f"  Docs: {paths.docs}")
    print("")
    print("  KEEP THIS WINDOW OPEN while you use the studio.")
    print("  Closing this window stops the studio.")
    # Warm the SDK image index in the background; catalog icons otherwise pay
    # this one-time package-index scan on their first request.
    threading.Thread(target=gameicons.warm, daemon=True).start()
    if os.environ.get("SIMSTUDIO_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: _open_window(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
