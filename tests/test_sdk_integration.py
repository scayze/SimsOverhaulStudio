import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend import catalog, exporter, gameicons, gamedata, premade_art, skillcurve, tray, templatedata
from sims4_sdk.catalog.models import Aspiration, AspirationObjective, AspirationTrack, Catalog, StatisticDefinition
from sims4_sdk.skill_discovery import SkillCurveDiscovery
from sims4_sdk.skills import SkillCurve
from sims4_sdk.save.tray import TrayListing, TrayListingGroup
from sims4_sdk.save.tray_summary import TrayHouseholdSummary, TraySimSummary


class SDKIntegrationTests(unittest.TestCase):
    def test_missing_indexed_icon_does_not_scan_packages(self):
        installation = SimpleNamespace(find_image_entry=lambda group, instance: None)
        workspace = SimpleNamespace(installation=installation, icon_for=lambda key: self.fail("unexpected package scan"))
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(gameicons, "CACHE_DIR", Path(directory)), \
                patch.object(gameicons, "_READY", True), \
                patch.object(gameicons.sdk, "workspace", return_value=workspace):
            self.assertIsNone(gameicons.icon_path("2f7d0004:00000000:0000000000000001"))

    def test_nonstandard_icon_type_keeps_sdk_fallback(self):
        workspace = SimpleNamespace(installation=SimpleNamespace(find_image_entry=lambda group, instance: None),
                                    icon_for=Mock(return_value=None))
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(gameicons, "CACHE_DIR", Path(directory)), \
                patch.object(gameicons, "_READY", True), \
                patch.object(gameicons.sdk, "workspace", return_value=workspace):
            gameicons.icon_path("3453cf95:00000000:0000000000000001")
        workspace.icon_for.assert_called_once()

    def test_aspiration_age_categories_expand_to_life_stages(self):
        for category, expected in (("Teen Or Older", ["Teen", "Young Adult", "Adult", "Elder"]),
                                   ("Teen Only", ["Teen"]), ("Child Only", ["Child"])):
            with self.subTest(category=category):
                self.assertEqual(gamedata.compatible_ages({"ages": [category], "age_hint": category}, "aspirations"), expected)

    def test_aspiration_track_names_resolve_without_guessing(self):
        tracks = [AspirationTrack(1, "Track_Love_A", "Soulmate", None),
                  AspirationTrack(2, "Track_Nature_A", "Freelance Botanist", None),
                  AspirationTrack(3, "Track_Test_A", "First", None),
                  AspirationTrack(4, "Track_Test_A", "Second", None),
                  AspirationTrack(5, "Track_Missing_A", "0x1234ABCD", None)]
        buckets = catalog._reset_buckets()
        data = Catalog(aspiration_tracks={track.id: track for track in tracks})
        with patch.object(catalog.sdk, "catalog", return_value=data):
            catalog._build_from_sdk(buckets, lambda item: buckets[item["kind"]].update({item["id"]: item}), None)
        payload = gamedata.build_payload({"aspiration_tracks": list(buckets["aspiration_tracks"].values())})
        self.assertEqual(payload["aspiration_tracks_by_id"]["1"], "Soulmate")
        self.assertEqual(payload["aspiration_tracks_by_label"]["Love A"], "Soulmate")
        self.assertEqual(payload["aspiration_tracks_by_label"]["Nature A"], "Freelance Botanist")
        self.assertNotIn("Test A", payload["aspiration_tracks_by_label"])
        self.assertNotIn("Missing A", payload["aspiration_tracks_by_label"])

    def test_premade_cache_rebuilds_when_pack_list_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "premades.json"
            path.write_text('{"meta":{"ownership_filter":1,"scenario_filter":1,"installed_packs":["EP02"]}}')
            with patch.object(templatedata, "COMPLETE_FILE", path), \
                    patch.object(templatedata.sdk, "installed_packs", return_value=["EP06"]), \
                    patch.object(templatedata.sdk, "reset") as reset, \
                    patch.object(templatedata, "build_complete_dataset", return_value={"households": []}) as build:
                self.assertEqual(templatedata.load_complete_dataset(), {"households": []})
                reset.assert_called_once()
                build.assert_called_once()

    def test_premade_builder_filters_owned_scenario_only_sims(self):
        owned = SimpleNamespace(id=1, first_name="Owned", last_name="Sim", dynasty={}, pack_id="BASE")
        unowned = SimpleNamespace(id=2, first_name="Unowned", last_name="Sim", dynasty={}, pack_id="EP02")
        scenario = SimpleNamespace(id=3, first_name="Scenario", last_name="Sim", dynasty={}, pack_id="BASE")
        both = SimpleNamespace(id=4, first_name="Both", last_name="Sim", dynasty={}, pack_id="BASE")
        members = [SimpleNamespace(sim_template_id=i, tag=str(i)) for i in (1, 2, 3, 4)]
        hh = SimpleNamespace(id=10, name="premadeHouseholdTemplate_Family", members=members,
                             lot_id=None, funds=0, relationships=[])
        bundle = SimpleNamespace(sims=[owned, unowned, scenario, both], households=[hh], lots=[], premade_relationships=[])
        static = SimpleNamespace(catalog=SimpleNamespace(), premades=bundle, world=None)
        def find_sims(*, origin=None):
            return {None: [owned, unowned, scenario, both], "scenario": [scenario, both], "normal": [both]}[origin]
        workspace = SimpleNamespace(find_sims=find_sims)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(templatedata, "COMPLETE_FILE", Path(directory) / "data.json"), \
                patch.object(templatedata.sdk, "installed_packs", return_value=[]), \
                patch.object(templatedata.sdk, "workspace", return_value=workspace), \
                patch.object(templatedata.sdk, "static_data", return_value=static), \
                patch.object(templatedata, "dynasty_tuning", return_value=[]), \
                patch.object(templatedata, "_build_sim", side_effect=lambda catalog, sim, *args: ({"first": sim.first_name, "last": "Sim"}, sim.id)), \
                patch.object(templatedata, "_ancestor_rows", return_value=[]):
            result = templatedata.build_complete_dataset()
        self.assertEqual([s["first"] for h in result["households"] for s in h["sims"]], ["Owned", "Both"])

    def test_old_premade_cache_is_rebuilt_for_scenario_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "premades.json"
            path.write_text('{"meta":{"ownership_filter":1,"installed_packs":[]}}')
            with patch.object(templatedata, "COMPLETE_FILE", path), \
                    patch.object(templatedata.sdk, "installed_packs", return_value=[]), \
                    patch.object(templatedata.sdk, "reset"), \
                    patch.object(templatedata, "build_complete_dataset", return_value={}) as build:
                templatedata.load_complete_dataset()
                build.assert_called_once()

    def test_skill_uses_discovered_curve_then_falls_back_when_unknown(self):
        definition = StatisticDefinition(10, "skill_test", "Skill", True, skill_level_type="MAJOR")
        data = Catalog(statistics={10: definition}).finalize()
        discovery = SkillCurveDiscovery(curves={"MAJOR": SkillCurve("MAJOR", (100, 1540, 4000), "test")})
        with patch.object(skillcurve, "level_for_xp", return_value=9) as fallback, \
                patch("backend.sdk.skill_curves", return_value=discovery):
            self.assertEqual(skillcurve.level_for_skill(1540, 10, "skill_test", data), 2)
            fallback.assert_not_called()
            self.assertEqual(skillcurve.level_for_skill(1540, 11, "unknown", data), 9)
            fallback.assert_called_once()

    def test_sdk_explicit_skills_enter_catalog(self):
        definition = StatisticDefinition(10, "skill_test", "Skill", True, display_name="Test Skill")
        other = StatisticDefinition(11, "statistic_unknown", "Statistic", None)
        data = Catalog(statistics={10: definition, 11: other})
        buckets = catalog._reset_buckets()
        with patch.object(catalog.sdk, "catalog", return_value=data):
            catalog._build_from_sdk(buckets, lambda item: buckets[item["kind"]].update({item["id"]: item}), None)
        self.assertEqual(buckets["skills"][10]["label"], "Test Skill")
        self.assertNotIn(11, buckets["skills"])

    def test_aspirations_require_resolved_track_and_category(self):
        data = Catalog(
            aspirations={1: Aspiration(1, "aspiration_Test_A1", "Test", None, objective_ids=[30]),
                         2: Aspiration(2, "aspiration_Utility", "Utility", None),
                         3: Aspiration(3, "aspiration_NoCategory", "No category", None),
                         4: Aspiration(4, "aspiration_Test_A2", "Later stage", None, objective_ids=[31])},
            aspiration_tracks={10: AspirationTrack(10, "track_Test", "Test", None, 20, [1, 4]),
                               11: AspirationTrack(11, "track_Incomplete", "Incomplete", None, None, [3])},
            aspiration_objectives={30: AspirationObjective(30, "first", display_text="Plant something"),
                                   31: AspirationObjective(31, "second", display_text="Reach level {1.Number}", skill_id=40, skill_level=4)},
            statistics={40: StatisticDefinition(40, "skill_Gardening", "Skill", True, display_name="Gardening")},
        ).finalize()
        buckets = catalog._reset_buckets()
        with patch.object(catalog.sdk, "catalog", return_value=data):
            catalog._build_from_sdk(buckets, lambda item: buckets[item["kind"]].update({item["id"]: item}), None)
        self.assertEqual(set(buckets["aspirations"]), {10})
        stages = buckets["aspirations"][10]["aspiration_stages"]
        self.assertEqual([stage["name"] for stage in stages], ["Test", "Later stage"])
        self.assertEqual(stages[1]["objectives"][0]["skill"], "Gardening")
        self.assertEqual(stages[1]["objectives"][0]["skill_level"], 4)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "xml.json"
            path.write_text('{"items":[{"kind":"aspirations","tuning":"aspiration_Utility","label":"Utility"}]}')
            with patch.object(catalog, "XML_ITEMS_FILE", path):
                merged = catalog._merge_xml_items({"catalog": {"aspirations": list(buckets["aspirations"].values())}})
        self.assertEqual([item["id"] for item in merged["catalog"]["aspirations"]], [10])

    def test_shared_aspiration_stages_keep_tracks_names_and_icons(self):
        first = Aspiration(1, "aspiration_Love_A1", "Amore Amateur", None)
        tracks = [AspirationTrack(10, "Track_Love_A", "Soulmate", None, 20, [1], icon="2f7d0004:00000000:4af7e32a19824921"),
                  AspirationTrack(11, "Track_Love_B", "Serial Romantic", None, 20, [1], icon="2f7d0004:00000000:4af7e32a19824922"),
                  AspirationTrack(12, "Track_Love_C", "Paragon Partner", None, 20, [1])]
        data = Catalog(aspirations={1: first}, aspiration_tracks={t.id: t for t in tracks}).finalize()
        buckets = catalog._reset_buckets()
        with patch.object(catalog.sdk, "catalog", return_value=data):
            catalog._build_from_sdk(buckets, lambda item: buckets[item["kind"]].update({item["id"]: item}), None)
        rows = buckets["aspirations"]
        self.assertEqual([rows[i]["label"] for i in (10, 11, 12)], ["Soulmate", "Serial Romantic", "Paragon Partner"])
        self.assertEqual([rows[i]["aspiration_id"] for i in (10, 11)], [1, 1])
        self.assertNotEqual(rows[10]["icon_key"], rows[11]["icon_key"])

    def test_export_preserves_and_applies_selected_aspiration_track(self):
        selected = {"id": 1, "track_id": 11, "label": "Serial Romantic"}
        config = exporter.export_config({"sims": {"sim": {"aspiration": selected}}})
        self.assertEqual(config["sims"][0]["aspiration"], selected)
        source = exporter.TEMPLATE.read_text(encoding="utf-8")
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_apply_aspiration")
        track = object()
        namespace = {"Types": SimpleNamespace(ASPIRATION_TRACK="track", ASPIRATION="aspiration"),
                     "_get_instance": lambda kind, identifier: track if (kind, identifier) == ("track", 11) else None,
                     "_log": lambda message: None}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(exporter.TEMPLATE), "exec"), namespace)
        sim = SimpleNamespace(_primary_aspiration=None)
        namespace["_apply_aspiration"](sim, selected)
        self.assertIs(sim._primary_aspiration, track)

    def test_tray_aspiration_preserves_selected_track(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.trayitem"
            path.write_bytes(b"Bella\x00Serial Romantic\x00")
            sims = [{"key": "bella", "first": "Bella", "aspiration": None}]
            item = {"id": 11, "aspiration_id": 1, "label": "Serial Romantic"}
            with patch.object(tray, "load_catalog", return_value={"catalog": {"aspirations": [item]}}):
                tray._apply_trayitem_aspirations(path, sims)
        self.assertEqual(sims[0]["aspiration"]["id"], 1)
        self.assertEqual(sims[0]["aspiration"]["track_id"], 11)

    def test_tray_listing_uses_sdk_groups_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "0x00000001!0x123.householdbinary"
            path.touch()
            summary = TrayHouseholdSummary(path, "Family", [TraySimSummary(12, "Bella", "Goth")])
            listing = TrayListing(groups=[TrayListingGroup("0x123", household_files=[path], summary=summary, modified=123)])
            tray._GROUPS.clear()
            tray._CACHE.clear()
            with patch.object(tray.paths, "tray", Path(directory)), \
                    patch("sims4_sdk.save.tray.list_tray_households", return_value=listing), \
                    patch.object(tray, "has_image", return_value=False):
                rows = tray.list_tray(force=True)
            self.assertEqual(rows[0]["sims"][0]["first"], "Bella")
            self.assertEqual(rows[0]["id"], "0x123")
            tray._GROUPS.clear()
            tray._CACHE.clear()

    def test_portrait_uses_sdk_selected_composite(self):
        image = SimpleNamespace(artwork=SimpleNamespace(jpeg=b"jpeg"))
        result = SimpleNamespace(largest=lambda identifier: image if identifier == 10 else None)
        with patch.object(premade_art, "_CHECKED", {"done": False}), \
                patch("backend.sdk.installation", return_value=object()), \
                patch("sims4_sdk.premade_artwork.PremadeCompositeIndex") as index:
            index.return_value.read.return_value = result
            self.assertEqual(premade_art.find_portraits({10, 11}), {10: b"jpeg"})
            index.return_value.read.assert_called_once_with({10, 11})


if __name__ == "__main__":
    unittest.main()
