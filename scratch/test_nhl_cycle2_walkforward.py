from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRATCH = Path(__file__).resolve().parent
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import nhl_cycle2_walkforward as wf


def row(
    date: str,
    away: str,
    home: str,
    away_odds: float,
    home_odds: float,
    away_score: int = 3,
    home_score: int = 2,
    season: str = "NHL 2099-00",
) -> dict[str, object]:
    return {
        "sport": "NHL",
        "season": season,
        "date": date,
        "sequence": "0",
        "away_team": away,
        "home_team": home,
        "away_score": str(away_score),
        "home_score": str(home_score),
        "outcome": "away" if away_score > home_score else "home",
        "neutral": "False",
        "away_odds_decimal": str(away_odds),
        "home_odds_decimal": str(home_odds),
        "draw_odds_decimal": "",
        "source": "unit-test",
    }


class Cycle2WalkForwardTests(unittest.TestCase):
    def test_quarantine_excludes_duplicate_and_bad_overround_while_flagging_high_valid_overround(self) -> None:
        rows = [
            row("2099-01-01", "A", "B", 2.0, 2.0),
            row("2099-01-01", "A", "B", 2.0, 2.0),
            row("2099-01-02", "C", "D", 1.85, 1.85),
            row("2099-01-03", "E", "F", 2.0, 1.8),
            row("2099-01-04", "G", "H", 1.0, 2.0),
        ]

        games, manifest = wf.clean_nhl_games_from_rows(rows)

        self.assertEqual(len(games), 2)
        self.assertEqual(manifest["excluded_reasons"]["duplicate_key"], 1)
        self.assertEqual(manifest["excluded_reasons"]["overround_outside_0.98_1.06"], 1)
        self.assertEqual(manifest["excluded_reasons"]["decimal_odds_lte_1"], 1)
        self.assertEqual(manifest["flagged_overround_gt_1.05_lte_1.06"], 1)

    def test_choose_threshold_requires_minimum_tune_bets_instead_of_chasing_sparse_winner(self) -> None:
        rows: list[dict[str, object]] = []
        for idx in range(60):
            rows.append(
                {
                    "game_id": f"eligible-{idx}",
                    "date": f"2099-01-{idx % 28 + 1:02d}",
                    "side": "home",
                    "odds": 2.0,
                    "won": idx % 2 == 0,
                    "hodge_edge_raw": 0.16,
                    "hodge_ev": 0.06,
                }
            )
        for idx in range(10):
            rows.append(
                {
                    "game_id": f"sparse-{idx}",
                    "date": f"2099-02-{idx + 1:02d}",
                    "side": "home",
                    "odds": 2.0,
                    "won": True,
                    "hodge_edge_raw": 0.26,
                    "hodge_ev": 0.11,
                }
            )

        choice = wf.choose_threshold(
            rows,
            edge_grid=[0.15, 0.25],
            ev_grid=[0.05, 0.10],
            min_tune_bets=50,
        )

        self.assertFalse(choice["inconclusive"])
        self.assertEqual(choice["edge_threshold"], 0.15)
        self.assertEqual(choice["min_ev"], 0.05)
        self.assertEqual(choice["bets"], 70)

    def test_return_haircut_reduces_winning_payout_but_not_losing_stake(self) -> None:
        bets = [
            {"date": "2099-01-01", "odds": 2.0, "won": True},
            {"date": "2099-01-02", "odds": 2.0, "won": False},
        ]

        no_haircut = wf.simulate_bankroll(bets, haircut=0.0)
        ten_pct_haircut = wf.simulate_bankroll(bets, haircut=0.10)

        self.assertAlmostEqual(no_haircut["unit_profit"], 0.0, places=7)
        self.assertAlmostEqual(ten_pct_haircut["unit_profit"], -0.10, places=7)
        self.assertLess(ten_pct_haircut["final_bankroll"], no_haircut["final_bankroll"])


if __name__ == "__main__":
    unittest.main()
