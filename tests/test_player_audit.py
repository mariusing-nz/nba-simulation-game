import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class PlayerAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = json.loads((DATA / "current-players.json").read_text())
        cls.alltime = json.loads((DATA / "all-time-players.json").read_text())
        cls.players = cls.current + cls.alltime
        reference = json.loads((DATA / "player-season-reference.json").read_text())
        cls.reference = {row["playerId"]: row for row in reference["players"]}

    def test_counts_and_unique_ids(self):
        self.assertEqual((len(self.current), len(self.alltime)), (300, 300))
        self.assertEqual(len({p["id"] for p in self.players}), 600)

    def test_seasons_are_calendar_valid(self):
        for player in self.players:
            match = re.fullmatch(r"(\d{4})-(\d{2})", player["season"])
            self.assertIsNotNone(match, player["id"])
            self.assertEqual((int(match.group(1)) + 1) % 100, int(match.group(2)), player["id"])

    def test_verified_rows_match_reference(self):
        documented_overrides = {
            "current-lal-luka-doncic-1", "alltime-cle-lebron-james-3",
            "alltime-lal-magic-johnson-1", "alltime-okc-kevin-durant-3",
        }
        for player in self.players:
            if player["factVerification"]["status"] != "verified-secondary": continue
            record = self.reference[player["id"]]
            selected = record["selectedSeason"]
            self.assertEqual(player["season"], selected["season"], player["id"])
            self.assertEqual(player["positions"][0], selected["positions"][0], player["id"])
            supported = {position for row in record["seasons"]
                         if abs(row["seasonEndYear"] - selected["seasonEndYear"]) <= 2
                         for position in row["positions"]}
            if player["id"] not in documented_overrides:
                self.assertTrue(set(player["positions"]) <= supported, player["id"])
            self.assertLessEqual(len(player["positions"]), 3, player["id"])

    def test_high_ratings_are_not_falsely_high_confidence(self):
        for player in self.players:
            if player["overall"] >= 95:
                self.assertEqual(player["ratingConfidence"], "low", player["id"])
                self.assertIn("manual-review", player["ratingMethod"], player["id"])

    def test_manual_records_have_notes(self):
        for player in self.players:
            if player["factVerification"]["status"] == "manual-review-required":
                self.assertTrue(player["factVerification"]["notes"], player["id"])


if __name__ == "__main__": unittest.main()
