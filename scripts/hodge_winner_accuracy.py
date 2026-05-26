"""
Straight-up winner accuracy for the Hodge sports predictor.

This removes betting, bankrolls, EV thresholds, and staking. It uses the same
real historical odds/results loaders as the sportsbook agent, replays games
chronologically, and compares:
  * Hodge raw margin-sign pick
  * Hodge calibrated probability pick
  * market favorite from closing odds
  * incremental Elo baseline
  * home/listed-home baseline

Usage:
    python scripts/hodge_winner_accuracy.py
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from hodge_real_sportsbook_agent import (
    RealOddsGame,
    fit_sport_model,
    hodge_signal,
    load_games,
    probabilities_for_signal,
)


ELO_K = {
    "NFL": 20.0,
    "CFB": 15.0,
    "NBA": 15.0,
    "NHL": 15.0,
    "MLB": 8.0,
    "EPL": 20.0,
}

ELO_HFA = {
    "NFL": 48.0,
    "CFB": 40.0,
    "NBA": 30.0,
    "NHL": 20.0,
    "MLB": 15.0,
    "EPL": 30.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sports", default="NFL,NBA,NHL,MLB,CFB,EPL")
    parser.add_argument("--seasons", type=int, default=10)
    parser.add_argument("--training-window", type=int, default=760)
    parser.add_argument("--warmup-games", type=int, default=300)
    parser.add_argument("--margin-cap", type=float, default=35.0)
    parser.add_argument("--keep-records", type=int, default=2000)
    parser.add_argument(
        "--output",
        default=os.path.join("site", "data", "hodge_winner_accuracy.json"),
    )
    return parser.parse_args()


def empty_stat() -> Dict[str, float]:
    return {"correct": 0, "total": 0}


def add_stat(stats: Dict[str, Dict[str, float]], key: str, correct: bool) -> None:
    stats[key]["total"] += 1
    stats[key]["correct"] += int(correct)


def accuracy(stat: Dict[str, float]) -> float:
    return float(stat["correct"] / stat["total"] * 100.0) if stat["total"] else 0.0


def market_pick(game: RealOddsGame) -> str:
    return min(game.odds.items(), key=lambda item: item[1])[0]


def hodge_signal_pick(signal: float) -> str:
    return "home" if signal > 0 else "away"


def hodge_calibrated_pick(probabilities: Dict[str, float]) -> str:
    return max(probabilities.items(), key=lambda item: item[1])[0]


def elo_pick(game: RealOddsGame, ratings: Dict[str, float]) -> str:
    home = ratings.get(game.home_team, 1500.0)
    away = ratings.get(game.away_team, 1500.0)
    hfa = 0.0 if game.neutral else ELO_HFA.get(game.sport, 0.0)
    return "home" if home + hfa >= away else "away"


def update_elo(game: RealOddsGame, ratings: Dict[str, float]) -> None:
    home = ratings.setdefault(game.home_team, 1500.0)
    away = ratings.setdefault(game.away_team, 1500.0)
    hfa = 0.0 if game.neutral else ELO_HFA.get(game.sport, 0.0)
    expected_home = 1.0 / (1.0 + 10.0 ** ((away - home - hfa) / 400.0))
    if game.outcome == "home":
        score_home = 1.0
    elif game.outcome == "away":
        score_home = 0.0
    else:
        score_home = 0.5
    k = ELO_K.get(game.sport, 15.0)
    ratings[game.home_team] = home + k * (score_home - expected_home)
    ratings[game.away_team] = away + k * ((1.0 - score_home) - (1.0 - expected_home))


def summarize_method(stats: Dict[str, Dict[str, Dict[str, float]]], method: str) -> Dict[str, object]:
    by_sport = {}
    correct = 0
    total = 0
    for sport, method_stats in sorted(stats.items()):
        row = method_stats[method]
        by_sport[sport] = {
            "correct": int(row["correct"]),
            "total": int(row["total"]),
            "accuracy_pct": round(accuracy(row), 2),
        }
        correct += int(row["correct"])
        total += int(row["total"])
    return {
        "correct": correct,
        "total": total,
        "accuracy_pct": round(correct / total * 100.0, 2) if total else 0.0,
        "by_sport": by_sport,
    }


def run_accuracy(games: Sequence[RealOddsGame], args: argparse.Namespace) -> Dict[str, object]:
    methods = ["hodge_signal", "hodge_calibrated", "market_favorite", "elo", "home"]
    stats: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(empty_stat))
    history_by_sport: Dict[str, List[RealOddsGame]] = defaultdict(list)
    elo_by_sport: Dict[str, Dict[str, float]] = defaultdict(dict)
    records: List[Dict[str, object]] = []
    skipped = defaultdict(int)

    games_by_date: Dict[str, List[RealOddsGame]] = defaultdict(list)
    for game in games:
        games_by_date[game.game_date].append(game)

    for game_date in sorted(games_by_date):
        slate = games_by_date[game_date]
        models = {
            sport: fit_sport_model(sport, history_by_sport[sport], args)
            for sport in sorted({game.sport for game in slate})
        }

        for game in slate:
            # There is no winner in a non-EPL draw. Skip rare NFL-style ties.
            if game.outcome == "draw" and game.sport != "EPL":
                skipped[f"{game.sport}:draw"] += 1
                continue

            model = models.get(game.sport)
            if model is None:
                skipped[f"{game.sport}:warmup"] += 1
                continue

            signal = hodge_signal(model["hodge"], game)  # type: ignore[arg-type]
            if signal is None:
                skipped[f"{game.sport}:unknown_team"] += 1
                continue
            probabilities = probabilities_for_signal(signal, model["calibrator"], game.sport)  # type: ignore[arg-type]

            picks = {
                "hodge_signal": hodge_signal_pick(signal),
                "hodge_calibrated": hodge_calibrated_pick(probabilities),
                "market_favorite": market_pick(game),
                "elo": elo_pick(game, elo_by_sport[game.sport]),
                "home": "home",
            }

            for method, pick in picks.items():
                add_stat(stats[game.sport], method, pick == game.outcome)

            if args.keep_records == 0 or len(records) < args.keep_records:
                records.append(
                    {
                        "date": game.game_date,
                        "sport": game.sport,
                        "season": game.season,
                        "matchup": game.matchup,
                        "actual": game.outcome,
                        "score": f"{game.away_score}-{game.home_score}",
                        "odds": {key: round(value, 4) for key, value in game.odds.items()},
                        "probabilities": {key: round(value, 5) for key, value in probabilities.items()},
                        "picks": picks,
                    }
                )

        for game in slate:
            update_elo(game, elo_by_sport[game.sport])
            history_by_sport[game.sport].append(game)

    summary = {method: summarize_method(stats, method) for method in methods}
    best_by_sport = {}
    for sport in sorted(stats):
        ranked = sorted(
            (
                {
                    "method": method,
                    "correct": int(stats[sport][method]["correct"]),
                    "total": int(stats[sport][method]["total"]),
                    "accuracy_pct": round(accuracy(stats[sport][method]), 2),
                }
                for method in methods
            ),
            key=lambda row: (row["accuracy_pct"], row["correct"]),
            reverse=True,
        )
        best_by_sport[sport] = ranked

    return {
        "summary": summary,
        "best_by_sport": best_by_sport,
        "skipped": dict(sorted(skipped.items())),
        "records": records,
    }


def write_json(path: str, payload: Dict[str, object]) -> str:
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return abs_path


def main() -> None:
    args = parse_args()
    sports = [sport.strip().upper() for sport in args.sports.split(",") if sport.strip()]
    print("Loading historical real odds/results for straight-up accuracy:")
    games, sources = load_games(sports, args.seasons)
    result = run_accuracy(games, args)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "sports": sports,
            "seasons_per_sport": args.seasons,
            "training_window": args.training_window,
            "warmup_games": args.warmup_games,
            "markets": "moneyline favorite for US sports; 1X2 favorite for EPL",
            "note": "No betting, no EV threshold, no bankroll. All methods evaluated on games where Hodge had enough prior sport history.",
        },
        "sources": sources,
        "coverage": {
            "games_loaded": len(games),
            "first_date": games[0].game_date if games else None,
            "last_date": games[-1].game_date if games else None,
        },
        **result,
    }
    out = write_json(args.output, payload)

    print()
    print("Straight-up accuracy")
    for method, row in sorted(payload["summary"].items(), key=lambda item: item[1]["accuracy_pct"], reverse=True):
        print(f"  {method:17s} {row['accuracy_pct']:6.2f}% ({row['correct']}/{row['total']})")
    print()
    print("Best by sport")
    for sport, ranked in payload["best_by_sport"].items():
        best = ranked[0]
        print(f"  {sport}: {best['method']} {best['accuracy_pct']:.2f}% ({best['correct']}/{best['total']})")
    print(f"Saved artifact: {out}")


if __name__ == "__main__":
    main()
