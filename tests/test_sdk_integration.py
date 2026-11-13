import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import catalog, premade_art, skillcurve, tray
from sims4_sdk.catalog.models import Catalog, StatisticDefinition
from sims4_sdk.skill_discovery import SkillCurveDiscovery
from sims4_sdk.skills import SkillCurve
from sims4_sdk.save.tray import TrayListing, TrayListingGroup
from sims4_sdk.save.tray_summary import TrayHouseholdSummary, TraySimSummary


class SDKIntegrationTests(unittest.TestCase):
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
