"""
Out-of-time market-residual strategy using Hodge as a feature.

This script tests the most direct path to monetization: stop using Hodge as the
final probability, and instead learn when Hodge adds information beyond the
closing market.

Workflow:
  1. Download/load the same real odds and results used by the bankroll agent.
  2. Replay games chronologically and generate no-future features:
       market probability, Hodge probability, Hodge-market disagreement, Elo.
  3. Split by date into train / tune / test.
  4. Fit a logistic side-win model on train.
  5. Select EV/edge thresholds on tune only.
  6. Report the final bankroll on the untouched test period.

Usage:
    python scripts/hodge_market_residual_strategy.py
    python scripts/hodge_market_residual_strategy.py --sports NHL,NBA
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from hodge_real_sportsbook_agent import (
    RealOddsGame,
    fit_sport_model,
    hodge_signal,
    load_games,
    probabilities_for_signal,
)
from hodge_winner_accuracy import ELO_HFA, ELO_K, update_elo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sports", default="NFL,NBA,NHL,MLB,CFB,EPL")
    parser.add_argument("--seasons", type=int, default=10)
    parser.add_argument("--training-window", type=int, default=760)
    parser.add_argument("--warmup-games", type=int, default=300)
    parser.add_argument("--margin-cap", type=float, default=35.0)
    parser.add_argument("--train-frac", type=float, default=0.60)
    parser.add_argument("--tune-frac", type=float, default=0.20)
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--flat-fraction", type=float, default=0.01)
    parser.add_argument("--max-day-exposure", type=float, default=0.05)
    parser.add_argument("--min-tune-bets", type=int, default=100)
    parser.add_argument("--keep-bets", type=int, default=2000)
    parser.add_argument(
        "--output",
        default=os.path.join("site", "data", "hodge_market_residual_strategy.json"),
    )
    return parser.parse_args()


def elo_home_probability(game: RealOddsGame, ratings: Dict[str, float]) -> float:
    home = ratings.get(game.home_team, 1500.0)
    away = ratings.get(game.away_team, 1500.0)
    hfa = 0.0 if game.neutral else ELO_HFA.get(game.sport, 0.0)
    return 1.0 / (1.0 + 10.0 ** ((away - home - hfa) / 400.0))


def normalized_market_probs(game: RealOddsGame) -> Dict[str, float]:
    raw = {side: 1.0 / odds for side, odds in game.odds.items()}
    total = sum(raw.values())
    return {side: value / total for side, value in raw.items()}


def elo_side_probability(game: RealOddsGame, side: str, home_prob: float) -> float:
    if side == "home":
        return home_prob
    if side == "away":
        return 1.0 - home_prob
    return 0.0


def side_signal(signal: float, side: str) -> float:
    if side == "home":
        return signal
    if side == "away":
        return -signal
    return -abs(signal)


def build_side_rows(games: Sequence[RealOddsGame], args: argparse.Namespace) -> Tuple[pd.DataFrame, Dict[str, object]]:
    history_by_sport: Dict[str, List[RealOddsGame]] = defaultdict(list)
    elo_by_sport: Dict[str, Dict[str, float]] = defaultdict(dict)
    rows: List[Dict[str, object]] = []
    skipped = defaultdict(int)

    by_date: Dict[str, List[RealOddsGame]] = defaultdict(list)
    for game in games:
        by_date[game.game_date].append(game)

    for game_date in sorted(by_date):
        slate = by_date[game_date]
        models = {
            sport: fit_sport_model(sport, history_by_sport[sport], args)
            for sport in sorted({game.sport for game in slate})
        }

        for game in slate:
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

            hodge_probs = probabilities_for_signal(signal, model["calibrator"], game.sport)  # type: ignore[arg-type]
            market_norm = normalized_market_probs(game)
            elo_home = elo_home_probability(game, elo_by_sport[game.sport])
            market_rank = {
                side: rank + 1
                for rank, side in enumerate(sorted(market_norm, key=lambda side: market_norm[side], reverse=True))
            }
            hodge_rank = {
                side: rank + 1
                for rank, side in enumerate(sorted(hodge_probs, key=lambda side: hodge_probs[side], reverse=True))
            }
            favorite_side = max(market_norm, key=lambda side: market_norm[side])
            hodge_pick = max(hodge_probs, key=lambda side: hodge_probs[side])

            for side, odds in game.odds.items():
                hodge_prob = hodge_probs.get(side)
                if hodge_prob is None:
                    continue
                implied_raw = 1.0 / odds
                implied_norm = market_norm[side]
                elo_prob = elo_side_probability(game, side, elo_home)
                rows.append(
                    {
                        "game_id": f"{game.sport}|{game.game_date}|{game.sequence}|{game.away_team}|{game.home_team}",
                        "date": game.game_date,
                        "year": int(game.game_date[:4]),
                        "sport": game.sport,
                        "season": game.season,
                        "matchup": game.matchup,
                        "side": side,
                        "actual": game.outcome,
                        "won": int(side == game.outcome),
                        "odds": float(odds),
                        "implied_raw": implied_raw,
                        "implied_norm": implied_norm,
                        "market_overround": sum(1.0 / value for value in game.odds.values()),
                        "market_rank": market_rank[side],
                        "market_favorite": int(side == favorite_side),
                        "hodge_prob": hodge_prob,
                        "hodge_edge_raw": hodge_prob - implied_raw,
                        "hodge_edge_norm": hodge_prob - implied_norm,
                        "hodge_rank": hodge_rank.get(side, 99),
                        "hodge_pick": int(side == hodge_pick),
                        "hodge_market_disagree": int(hodge_pick != favorite_side),
                        "signal": signal,
                        "abs_signal": abs(signal),
                        "side_signal": side_signal(signal, side),
                        "elo_prob": elo_prob,
                        "elo_edge_norm": elo_prob - implied_norm,
                        "neutral": int(game.neutral),
                        "home_side": int(side == "home"),
                        "away_side": int(side == "away"),
                        "draw_side": int(side == "draw"),
                    }
                )

        for game in slate:
            update_elo(game, elo_by_sport[game.sport])
            history_by_sport[game.sport].append(game)

    return pd.DataFrame(rows), {"skipped": dict(sorted(skipped.items()))}


NUMERIC_FEATURES = [
    "odds",
    "implied_raw",
    "implied_norm",
    "market_overround",
    "market_rank",
    "market_favorite",
    "hodge_prob",
    "hodge_edge_raw",
    "hodge_edge_norm",
    "hodge_rank",
    "hodge_pick",
    "hodge_market_disagree",
    "signal",
    "abs_signal",
    "side_signal",
    "elo_prob",
    "elo_edge_norm",
    "neutral",
    "home_side",
    "away_side",
    "draw_side",
]

CATEGORICAL_FEATURES = ["sport", "side"]


def make_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    C=0.5,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def split_by_date(df: pd.DataFrame, train_frac: float, tune_frac: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    dates = sorted(df["date"].unique())
    train_end = max(1, int(len(dates) * train_frac))
    tune_end = max(train_end + 1, int(len(dates) * (train_frac + tune_frac)))
    tune_end = min(tune_end, len(dates) - 1)
    train_dates = set(dates[:train_end])
    tune_dates = set(dates[train_end:tune_end])
    test_dates = set(dates[tune_end:])
    meta = {
        "train": {"first": min(train_dates), "last": max(train_dates), "dates": len(train_dates)},
        "tune": {"first": min(tune_dates), "last": max(tune_dates), "dates": len(tune_dates)},
        "test": {"first": min(test_dates), "last": max(test_dates), "dates": len(test_dates)},
    }
    return (
        df[df["date"].isin(train_dates)].copy(),
        df[df["date"].isin(tune_dates)].copy(),
        df[df["date"].isin(test_dates)].copy(),
        meta,
    )


def add_model_outputs(model: Pipeline, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["model_prob"] = model.predict_proba(out[NUMERIC_FEATURES + CATEGORICAL_FEATURES])[:, 1]
    out["model_edge_raw"] = out["model_prob"] - out["implied_raw"]
    out["model_edge_norm"] = out["model_prob"] - out["implied_norm"]
    out["model_ev"] = out["model_prob"] * out["odds"] - 1.0
    return out


def candidate_bets(df: pd.DataFrame, edge_threshold: float, min_ev: float) -> pd.DataFrame:
    candidates = df[(df["model_edge_raw"] >= edge_threshold) & (df["model_ev"] >= min_ev)].copy()
    if candidates.empty:
        return candidates
    candidates = candidates.sort_values(["date", "game_id", "model_ev"], ascending=[True, True, False])
    return candidates.groupby("game_id", as_index=False).head(1).copy()


def simulate_flat(df: pd.DataFrame, edge_threshold: float, min_ev: float, initial_bankroll: float, flat_fraction: float, max_day_exposure: float) -> Dict[str, object]:
    bets = candidate_bets(df, edge_threshold=edge_threshold, min_ev=min_ev)
    bankroll = initial_bankroll
    records: List[Dict[str, object]] = []

    if not bets.empty:
        for bet_date, day in bets.groupby("date", sort=True):
            requested = [bankroll * flat_fraction for _ in range(len(day))]
            total = sum(requested)
            max_total = bankroll * max_day_exposure
            scale = min(1.0, max_total / total) if total > 0 else 0.0
            for (_, row), requested_stake in zip(day.iterrows(), requested):
                stake = requested_stake * scale
                won = bool(row["won"])
                profit = stake * (float(row["odds"]) - 1.0) if won else -stake
                bankroll += profit
                records.append(
                    {
                        "date": bet_date,
                        "sport": row["sport"],
                        "season": row["season"],
                        "matchup": row["matchup"],
                        "side": row["side"],
                        "actual": row["actual"],
                        "won": won,
                        "odds": round(float(row["odds"]), 4),
                        "model_prob": round(float(row["model_prob"]), 5),
                        "implied_raw": round(float(row["implied_raw"]), 5),
                        "model_edge_raw": round(float(row["model_edge_raw"]), 5),
                        "model_ev": round(float(row["model_ev"]), 5),
                        "hodge_prob": round(float(row["hodge_prob"]), 5),
                        "hodge_edge_raw": round(float(row["hodge_edge_raw"]), 5),
                        "stake": round(stake, 4),
                        "profit": round(profit, 4),
                        "bankroll": round(bankroll, 4),
                    }
                )

    wins = sum(1 for record in records if record["won"])
    total_staked = sum(float(record["stake"]) for record in records)
    profit = bankroll - initial_bankroll
    by_sport = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    peak = initial_bankroll
    max_dd = 0.0
    for record in records:
        row = by_sport[str(record["sport"])]
        row["bets"] += 1
        row["wins"] += int(bool(record["won"]))
        row["profit"] += float(record["profit"])
        row["staked"] += float(record["stake"])
        peak = max(peak, float(record["bankroll"]))
        max_dd = max(max_dd, (peak - float(record["bankroll"])) / max(peak, 1e-9) * 100.0)

    cleaned = {}
    for sport, row in sorted(by_sport.items()):
        cleaned[sport] = {
            "bets": row["bets"],
            "wins": row["wins"],
            "win_pct": round(row["wins"] / row["bets"] * 100.0, 2) if row["bets"] else 0.0,
            "profit": round(row["profit"], 2),
            "staked": round(row["staked"], 2),
            "yield_pct": round(row["profit"] / row["staked"] * 100.0, 2) if row["staked"] else 0.0,
        }

    return {
        "edge_threshold": edge_threshold,
        "min_ev": min_ev,
        "bets": len(records),
        "wins": wins,
        "win_pct": round(wins / len(records) * 100.0, 2) if records else 0.0,
        "final_bankroll": round(bankroll, 2),
        "profit": round(profit, 2),
        "roi_pct": round(profit / initial_bankroll * 100.0, 2) if initial_bankroll else 0.0,
        "total_staked": round(total_staked, 2),
        "yield_pct": round(profit / total_staked * 100.0, 2) if total_staked else 0.0,
        "max_drawdown_pct": round(max_dd, 2),
        "by_sport": cleaned,
        "records": records,
    }


def choose_threshold(tune: pd.DataFrame, args: argparse.Namespace) -> Dict[str, object]:
    edge_grid = [round(value, 3) for value in np.linspace(0.00, 0.20, 11)]
    ev_grid = [round(value, 3) for value in np.linspace(0.00, 0.25, 11)]
    results = []
    for edge in edge_grid:
        for ev in ev_grid:
            result = simulate_flat(
                tune,
                edge_threshold=edge,
                min_ev=ev,
                initial_bankroll=args.initial_bankroll,
                flat_fraction=args.flat_fraction,
                max_day_exposure=args.max_day_exposure,
            )
            result_without_records = {key: value for key, value in result.items() if key != "records"}
            results.append(result_without_records)

    eligible = [row for row in results if row["bets"] >= args.min_tune_bets]
    if not eligible:
        eligible = results
    best = max(eligible, key=lambda row: (row["yield_pct"], row["roi_pct"], row["bets"]))
    return {"best": best, "grid": sorted(results, key=lambda row: row["yield_pct"], reverse=True)[:20]}


def method_accuracy(df: pd.DataFrame) -> Dict[str, object]:
    if df.empty:
        return {}
    game_rows = df.sort_values(["game_id", "model_prob"], ascending=[True, False]).groupby("game_id").head(1)
    correct = int(game_rows["won"].sum())
    total = int(len(game_rows))
    return {
        "model_pick_accuracy_pct": round(correct / total * 100.0, 2) if total else 0.0,
        "model_pick_correct": correct,
        "model_pick_total": total,
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
    print("Loading games and building no-future Hodge/market features:")
    games, sources = load_games(sports, args.seasons)
    features, build_meta = build_side_rows(games, args)
    train, tune, test, split_meta = split_by_date(features, args.train_frac, args.tune_frac)

    model = make_model()
    model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train["won"])
    tune_scored = add_model_outputs(model, tune)
    test_scored = add_model_outputs(model, test)
    threshold = choose_threshold(tune_scored, args)
    best = threshold["best"]
    test_result = simulate_flat(
        test_scored,
        edge_threshold=float(best["edge_threshold"]),
        min_ev=float(best["min_ev"]),
        initial_bankroll=args.initial_bankroll,
        flat_fraction=args.flat_fraction,
        max_day_exposure=args.max_day_exposure,
    )

    keep_bets = args.keep_bets
    saved_test = {key: value for key, value in test_result.items() if key != "records"}
    saved_test["records"] = test_result["records"][-keep_bets:] if keep_bets else test_result["records"]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "sports": sports,
            "seasons": args.seasons,
            "train_frac": args.train_frac,
            "tune_frac": args.tune_frac,
            "initial_bankroll": args.initial_bankroll,
            "flat_fraction": args.flat_fraction,
            "max_day_exposure": args.max_day_exposure,
            "min_tune_bets": args.min_tune_bets,
            "note": "Thresholds are selected on tune only, then applied once to the untouched test period.",
        },
        "sources": sources,
        "coverage": {
            "games_loaded": len(games),
            "side_rows": int(len(features)),
            "train_rows": int(len(train)),
            "tune_rows": int(len(tune)),
            "test_rows": int(len(test)),
            "first_date": features["date"].min() if not features.empty else None,
            "last_date": features["date"].max() if not features.empty else None,
            **build_meta,
        },
        "split": split_meta,
        "tune_threshold_selection": threshold,
        "accuracy": {
            "tune": method_accuracy(tune_scored),
            "test": method_accuracy(test_scored),
        },
        "test_result": saved_test,
    }
    out = write_json(args.output, payload)
    print()
    print("Market-residual strategy")
    print(f"  Tune selected edge={best['edge_threshold']} min_ev={best['min_ev']} from {best['bets']} tune bets, yield {best['yield_pct']}%")
    print(
        f"  Test: ${args.initial_bankroll:.2f} -> ${test_result['final_bankroll']:.2f}, "
        f"{test_result['bets']} bets, yield {test_result['yield_pct']}%, max DD {test_result['max_drawdown_pct']}%"
    )
    print(f"  Test by sport: {test_result['by_sport']}")
    print(f"Saved artifact: {out}")


if __name__ == "__main__":
    main()
