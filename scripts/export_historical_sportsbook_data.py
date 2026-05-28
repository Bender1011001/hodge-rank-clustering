"""
Export normalized historical sportsbook odds/results to local files.

This uses the same verified loaders as the validation scripts and writes:
  * site/data/historical_sportsbook_games.csv
  * site/data/historical_sportsbook_games.jsonl
  * site/data/historical_sportsbook_sources.json

Usage:
    python scripts/export_historical_sportsbook_data.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from hodge_real_sportsbook_agent import RealOddsGame, load_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sports", default="NFL,NBA,NHL,MLB,CFB,EPL")
    parser.add_argument("--seasons", type=int, default=10)
    parser.add_argument("--out-dir", default=os.path.join("site", "data"))
    return parser.parse_args()


def row_from_game(game: RealOddsGame) -> Dict[str, object]:
    return {
        "sport": game.sport,
        "season": game.season,
        "date": game.game_date,
        "sequence": game.sequence,
        "away_team": game.away_team,
        "home_team": game.home_team,
        "away_score": game.away_score,
        "home_score": game.home_score,
        "outcome": game.outcome,
        "neutral": game.neutral,
        "away_odds_decimal": game.odds.get("away"),
        "home_odds_decimal": game.odds.get("home"),
        "draw_odds_decimal": game.odds.get("draw"),
        "source": game.source,
    }


def write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "sport",
        "season",
        "date",
        "sequence",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
        "outcome",
        "neutral",
        "away_odds_decimal",
        "home_odds_decimal",
        "draw_odds_decimal",
        "source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: str, rows: List[Dict[str, object]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    args = parse_args()
    sports = [sport.strip().upper() for sport in args.sports.split(",") if sport.strip()]
    os.makedirs(args.out_dir, exist_ok=True)

    print("Downloading and normalizing historical sportsbook data:")
    games, sources = load_games(sports, args.seasons)
    rows = [row_from_game(game) for game in games]

    csv_path = os.path.abspath(os.path.join(args.out_dir, "historical_sportsbook_games.csv"))
    jsonl_path = os.path.abspath(os.path.join(args.out_dir, "historical_sportsbook_games.jsonl"))
    sources_path = os.path.abspath(os.path.join(args.out_dir, "historical_sportsbook_sources.json"))

    write_csv(csv_path, rows)
    write_jsonl(jsonl_path, rows)
    with open(sources_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "sports": sports,
                "seasons_per_sport": args.seasons,
                "games": len(rows),
                "first_date": rows[0]["date"] if rows else None,
                "last_date": rows[-1]["date"] if rows else None,
                "sources": sources,
            },
            handle,
            indent=2,
        )

    print(f"Wrote {len(rows)} games")
    print(f"CSV:    {csv_path}")
    print(f"JSONL:  {jsonl_path}")
    print(f"Source: {sources_path}")


if __name__ == "__main__":
    main()
