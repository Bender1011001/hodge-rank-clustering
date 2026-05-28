from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRATCH = Path(__file__).resolve().parent
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import nhl_cycle3_diagnostics as d3


def toy_bet(game_id: str, date: str, odds: float, won: bool, side: str = "home", band: str = "1.75-2.00") -> dict[str, object]:
    return {
        "game_id": game_id,
        "date": date,
        "season": "NHL TEST",
        "fold_id": 99,
        "side": side,
        "odds": odds,
        "won": won,
        "odds_band": band,
        "selected_team": f"Team-{game_id}",
    }


class Cycle3DiagnosticsTests(unittest.TestCase):
    def test_summarize_cohort_applies_return_haircut_to_wins_only(self) -> None:
        summary = d3.summarize_cohort(
            [toy_bet("win", "2099-01-01", 2.0, True), toy_bet("loss", "2099-01-02", 2.0, False)],
            label="toy",
        )

        self.assertEqual(summary["label"], "toy")
        self.assertEqual(summary["haircuts"]["0.01"]["bets"], 2)
        self.assertEqual(summary["haircuts"]["0.01"]["wins"], 1)
        self.assertAlmostEqual(summary["haircuts"]["0.01"]["unit_profit"], -0.01, places=7)
        self.assertAlmostEqual(summary["haircuts"]["0.01"]["unit_yield_pct"], -0.5, places=7)

    def test_summarize_cohort_includes_profit_share_breakdowns_for_required_dimensions(self) -> None:
        summary = d3.summarize_cohort(
            [
                toy_bet("win", "2099-01-01", 2.0, True, side="home"),
                toy_bet("loss", "2099-01-02", 2.0, False, side="away", band="2.00-2.50"),
            ],
            label="toy",
        )

        self.assertIn("profit_share_1pct", summary)
        self.assertEqual(set(summary["profit_share_1pct"]), {"side", "odds_band", "selected_team", "season"})
        self.assertEqual(summary["profit_share_1pct"]["side"][0]["side"], "home")

    def test_date_window_random_control_reports_matching_relaxation(self) -> None:
        selected = [toy_bet("selected", "2099-01-01", 1.9, True)]
        rows = [
            toy_bet("selected", "2099-01-01", 1.9, True),
            toy_bet("same-week", "2099-01-03", 1.95, False),
            toy_bet("other-band", "2099-01-01", 2.4, True, band="2.00-2.50"),
        ]

        controls, diagnostics = d3.date_window_random_control(selected, rows, seed=7)

        self.assertEqual([row["game_id"] for row in controls], ["same-week"])
        self.assertEqual(diagnostics["relaxation_counts"], {"same_week_and_odds_band": 1})
        self.assertEqual(diagnostics["control_bets"], 1)

    def test_reconstructed_cycle2_selected_universe_matches_frozen_identity(self) -> None:
        universe = d3.reconstruct_selected_universe()
        identity = d3.verify_selected_identity(universe.selected)

        self.assertTrue(identity["passed"], identity)
        self.assertEqual(identity["actual"]["bets"], 325)
        self.assertEqual(identity["actual"]["wins"], 182)
        self.assertAlmostEqual(identity["actual"]["unit_yield_pct_1pct"], 6.72, delta=0.01)
        self.assertAlmostEqual(identity["actual"]["unit_yield_pct_2pct"], 6.21, delta=0.01)


if __name__ == "__main__":
    unittest.main()
