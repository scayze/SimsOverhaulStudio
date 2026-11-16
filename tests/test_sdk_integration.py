import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import catalog, premade_art, skillcurve, tray, templatedata
from sims4_sdk.catalog.models import Catalog, StatisticDefinition
from sims4_sdk.skill_discovery import SkillCurveDiscovery
from sims4_sdk.skills import SkillCurve
from sims4_sdk.save.tray import TrayListing, TrayListingGroup
from sims4_sdk.save.tray_summary import TrayHouseholdSummary, TraySimSummary


class SDKIntegrationTests(unittest.TestCase):
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
        owned = SimpleNamespace(id=1, first_name="Owned", last_name="Sim", dynasty={})
        unowned = SimpleNamespace(id=2, first_name="Unowned", last_name="Sim", dynasty={})
        scenario = SimpleNamespace(id=3, first_name="Scenario", last_name="Sim", dynasty={})
        both = SimpleNamespace(id=4, first_name="Both", last_name="Sim", dynasty={})
        members = [SimpleNamespace(sim_template_id=i, tag=str(i)) for i in (1, 2, 3, 4)]
        hh = SimpleNamespace(id=10, name="premadeHouseholdTemplate_Family", members=members,
                             lot_id=None, funds=0, relationships=[])
        bundle = SimpleNamespace(sims=[owned, unowned, scenario, both], households=[hh], lots=[], premade_relationships=[])
        static = SimpleNamespace(catalog=SimpleNamespace(), premades=bundle, world=None)
        def find_sims(*, ownership, origin=None):
            assert ownership == "owned"
            return {None: [owned, scenario, both], "scenario": [scenario, both], "normal": [both]}[origin]
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
