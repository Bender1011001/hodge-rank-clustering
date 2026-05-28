from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Sequence


BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from hodge_real_sportsbook_agent import (  # noqa: E402
    RealOddsGame,
    fit_sport_model,
    hodge_signal,
    probabilities_for_signal,
)


EDGE_GRID = [0.15, 0.18, 0.20, 0.25]
EV_GRID = [0.05, 0.08, 0.10]
HAIRCUTS = [0.0, 0.01, 0.02, 0.03]
RANDOM_SEEDS = [7, 17, 29]


@dataclass(frozen=True)
class Config:
    source_csv: str = "site/data/historical_sportsbook_games.csv"
    sport: str = "NHL"
    warmup_games: int = 300
    training_window_games: int = 760
    margin_cap: float = 35.0
    min_tune_bets: int = 50
    initial_bankroll: float = 1000.0
    flat_fraction: float = 0.01
    max_day_exposure: float = 0.05
    min_completed_season_games: int = 700


def parse_float(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_int(raw: object) -> int | None:
    value = parse_float(raw)
    if value is None:
        return None
    return int(value)


def parse_bool(raw: object) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y"}


def clean_nhl_games_from_rows(rows: Sequence[dict[str, object]]) -> tuple[list[RealOddsGame], dict[str, object]]:
    games: list[RealOddsGame] = []
    excluded = Counter()
    seen: set[tuple[str, str, str]] = set()
    raw_rows = len(rows)
    nhl_rows = 0
    flagged_high_overround = 0
    overrounds: list[float] = []
    american_columns_present = False
    impossible_pairs_checked = 0

    for index, row in enumerate(rows):
        if str(row.get("sport", "")).strip().upper() != "NHL":
            continue
        nhl_rows += 1
        game_date = str(row.get("date", "") or row.get("game_date", "")).strip()
        away_team = str(row.get("away_team", "")).strip()
        home_team = str(row.get("home_team", "")).strip()
        if not game_date or not away_team or not home_team:
            excluded["missing_teams_or_date"] += 1
            continue
        key = (game_date, away_team, home_team)
        if key in seen:
            excluded["duplicate_key"] += 1
            continue
        seen.add(key)

        away_score = parse_int(row.get("away_score"))
        home_score = parse_int(row.get("home_score"))
        if away_score is None or home_score is None:
            excluded["missing_scores"] += 1
            continue

        away_odds = parse_float(row.get("away_odds_decimal"))
        home_odds = parse_float(row.get("home_odds_decimal"))
        if away_odds is None or home_odds is None:
            excluded["missing_moneyline_odds"] += 1
            continue
        if not math.isfinite(away_odds) or not math.isfinite(home_odds):
            excluded["non_finite_prices"] += 1
            continue
        if away_odds <= 1.0 or home_odds <= 1.0:
            excluded["decimal_odds_lte_1"] += 1
            continue

        away_american = row.get("away_moneyline") or row.get("away_ml") or row.get("away_odds_american")
        home_american = row.get("home_moneyline") or row.get("home_ml") or row.get("home_odds_american")
        if away_american is not None and home_american is not None:
            american_columns_present = True
            away_number = parse_float(away_american)
            home_number = parse_float(home_american)
            if away_number is not None and home_number is not None:
                impossible_pairs_checked += 1
                if away_number > 0 and home_number > 0:
                    excluded["impossible_two_positive_moneyline_pair"] += 1
                    continue

        overround = 1.0 / away_odds + 1.0 / home_odds
        if overround < 0.98 or overround > 1.06:
            excluded["overround_outside_0.98_1.06"] += 1
            continue
        if overround > 1.05:
            flagged_high_overround += 1
        overrounds.append(overround)

        games.append(
            RealOddsGame(
                sport="NHL",
                season=str(row.get("season", "")).strip() or "UNKNOWN",
                game_date=game_date,
                sequence=parse_int(row.get("sequence")) if parse_int(row.get("sequence")) is not None else index,
                away_team=away_team,
                home_team=home_team,
                away_score=away_score,
                home_score=home_score,
                neutral=parse_bool(row.get("neutral")),
                odds={"away": float(away_odds), "home": float(home_odds)},
                source=str(row.get("source", "")),
            )
        )

    games.sort(key=lambda game: (game.game_date, game.sequence, game.away_team, game.home_team))
    by_season = Counter(game.season for game in games)
    overround_summary = {
        "count": len(overrounds),
        "mean": round(statistics.fmean(overrounds), 6) if overrounds else None,
        "median": round(statistics.median(overrounds), 6) if overrounds else None,
        "min": round(min(overrounds), 6) if overrounds else None,
        "max": round(max(overrounds), 6) if overrounds else None,
        "p95": round(sorted(overrounds)[min(len(overrounds) - 1, int(0.95 * len(overrounds)))], 6) if overrounds else None,
    }
    manifest = {
        "source_rows_total": raw_rows,
        "nhl_rows": nhl_rows,
        "included_rows": len(games),
        "excluded_rows": sum(excluded.values()),
        "excluded_reasons": dict(sorted(excluded.items())),
        "flagged_overround_gt_1.05_lte_1.06": flagged_high_overround,
        "overround_summary": overround_summary,
        "american_moneyline_pair_check": {
            "columns_present": american_columns_present,
            "pairs_checked": impossible_pairs_checked,
            "note": "historical_sportsbook_games.csv does not include raw American prices, so this check is reported unavailable when columns are absent",
        },
        "first_date": games[0].game_date if games else None,
        "last_date": games[-1].game_date if games else None,
        "included_by_season": dict(sorted(by_season.items())),
    }
    return games, manifest


def load_clean_games(config: Config) -> tuple[list[RealOddsGame], dict[str, object]]:
    path = BASE / config.source_csv
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return clean_nhl_games_from_rows(rows)


def odds_band(odds: float) -> str:
    if odds < 1.50:
        return "<1.50"
    if odds < 1.75:
        return "1.50-1.75"
    if odds < 2.00:
        return "1.75-2.00"
    if odds < 2.50:
        return "2.00-2.50"
    return ">=2.50"


def selected_team(row: dict[str, object]) -> str:
    return str(row["home_team"] if row["side"] == "home" else row["away_team"])


def build_side_rows(games: Sequence[RealOddsGame], config: Config) -> tuple[list[dict[str, object]], dict[str, object]]:
    args = SimpleNamespace(
        warmup_games=config.warmup_games,
        training_window=config.training_window_games,
        margin_cap=config.margin_cap,
    )
    history: list[RealOddsGame] = []
    rows: list[dict[str, object]] = []
    skipped = Counter()
    by_date: dict[str, list[RealOddsGame]] = defaultdict(list)
    for game in games:
        by_date[game.game_date].append(game)

    for game_date in sorted(by_date):
        slate = by_date[game_date]
        model = fit_sport_model("NHL", history, args)
        for game in slate:
            if model is None:
                skipped["warmup"] += 1
                continue
            signal = hodge_signal(model["hodge"], game)  # type: ignore[arg-type]
            if signal is None:
                skipped["unknown_team"] += 1
                continue
            hodge_probs = probabilities_for_signal(signal, model["calibrator"], "NHL")  # type: ignore[arg-type]
            market_raw = {side: 1.0 / odds for side, odds in game.odds.items()}
            market_total = sum(market_raw.values())
            market_norm = {side: value / market_total for side, value in market_raw.items()}
            market_favorite = max(market_raw, key=market_raw.get)
            hodge_pick = max(hodge_probs, key=hodge_probs.get)
            game_id = f"{game.game_date}|{game.sequence}|{game.away_team}|{game.home_team}"
            for side, price in game.odds.items():
                hodge_prob = float(hodge_probs[side])
                implied_raw = float(market_raw[side])
                rows.append(
                    {
                        "game_id": game_id,
                        "date": game.game_date,
                        "season": game.season,
                        "sequence": game.sequence,
                        "away_team": game.away_team,
                        "home_team": game.home_team,
                        "matchup": game.matchup,
                        "side": side,
                        "actual": game.outcome,
                        "won": side == game.outcome,
                        "odds": float(price),
                        "implied_raw": implied_raw,
                        "implied_norm": float(market_norm[side]),
                        "market_overround": market_total,
                        "market_favorite": side == market_favorite,
                        "market_underdog": side != market_favorite,
                        "hodge_prob": hodge_prob,
                        "hodge_edge_raw": hodge_prob - implied_raw,
                        "hodge_edge_norm": hodge_prob - float(market_norm[side]),
                        "hodge_ev": hodge_prob * float(price) - 1.0,
                        "hodge_pick": side == hodge_pick,
                        "hodge_market_disagree": hodge_pick != market_favorite,
                        "signal": float(signal),
                        "side_signal": float(signal) if side == "home" else -float(signal),
                        "home_side": side == "home",
                        "away_side": side == "away",
                        "odds_band": odds_band(float(price)),
                        "selected_team": game.home_team if side == "home" else game.away_team,
                        "opponent_team": game.away_team if side == "home" else game.home_team,
                    }
                )
        history.extend(slate)

    feature_names = [
        "odds",
        "implied_raw",
        "implied_norm",
        "market_overround",
        "market_favorite",
        "market_underdog",
        "hodge_prob",
        "hodge_edge_raw",
        "hodge_edge_norm",
        "hodge_ev",
        "hodge_pick",
        "hodge_market_disagree",
        "signal",
        "side_signal",
        "home_side",
        "away_side",
        "odds_band",
    ]
    by_season = Counter(str(row["season"]) for row in rows)
    manifest = {
        "side_rows": len(rows),
        "eligible_games": len({row["game_id"] for row in rows}),
        "skipped_games": dict(sorted(skipped.items())),
        "first_feature_date": min((str(row["date"]) for row in rows), default=None),
        "last_feature_date": max((str(row["date"]) for row in rows), default=None),
        "side_rows_by_season": dict(sorted(by_season.items())),
        "feature_names": feature_names,
        "no_future_rule": "features for a date are generated before that date's games are appended to history",
        "model_reference": "scripts/hodge_real_sportsbook_agent.py",
        "side_feature_reference": "scripts/hodge_market_residual_strategy.py",
        "warmup_games": config.warmup_games,
        "training_window_games": config.training_window_games,
    }
    return rows, manifest


def candidate_bets(rows: Sequence[dict[str, object]], edge_threshold: float, min_ev: float) -> list[dict[str, object]]:
    by_game: dict[str, dict[str, object]] = {}
    for row in rows:
        if float(row["hodge_edge_raw"]) < edge_threshold or float(row["hodge_ev"]) < min_ev:
            continue
        game_id = str(row["game_id"])
        current = by_game.get(game_id)
        if current is None or float(row["hodge_ev"]) > float(current["hodge_ev"]):
            by_game[game_id] = dict(row)
    return sorted(by_game.values(), key=lambda row: (str(row["date"]), int(row.get("sequence", 0)), str(row["game_id"])))


def effective_odds(odds: float, haircut: float) -> float:
    return 1.0 + (odds - 1.0) * (1.0 - haircut)


def simulate_bankroll(
    bets: Sequence[dict[str, object]],
    haircut: float = 0.0,
    initial_bankroll: float = 1000.0,
    flat_fraction: float = 0.01,
    max_day_exposure: float = 0.05,
    keep_records: bool = False,
) -> dict[str, object]:
    bankroll = initial_bankroll
    peak = initial_bankroll
    max_drawdown = 0.0
    unit_profit = 0.0
    wins = 0
    total_staked = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    records: list[dict[str, object]] = []
    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for bet in bets:
        by_date[str(bet["date"])].append(dict(bet))

    for bet_date in sorted(by_date):
        day = by_date[bet_date]
        requested_stake = bankroll * flat_fraction
        requested_total = requested_stake * len(day)
        max_total = bankroll * max_day_exposure
        scale = min(1.0, max_total / requested_total) if requested_total > 0 else 0.0
        for bet in day:
            stake = requested_stake * scale
            odds = float(bet["odds"])
            adjusted_odds = effective_odds(odds, haircut)
            won = bool(bet["won"])
            profit = stake * (adjusted_odds - 1.0) if won else -stake
            unit = (adjusted_odds - 1.0) if won else -1.0
            bankroll += profit
            peak = max(peak, bankroll)
            max_drawdown = max(max_drawdown, (peak - bankroll) / max(peak, 1e-9) * 100.0)
            total_staked += stake
            unit_profit += unit
            wins += int(won)
            if profit >= 0:
                gross_profit += profit
            else:
                gross_loss += abs(profit)
            if keep_records:
                record = dict(bet)
                record.update(
                    {
                        "haircut": haircut,
                        "effective_odds": adjusted_odds,
                        "stake": stake,
                        "profit": profit,
                        "bankroll_after": bankroll,
                        "unit_profit": unit,
                    }
                )
                records.append(record)

    bets_count = len(bets)
    result: dict[str, object] = {
        "haircut": haircut,
        "bets": bets_count,
        "wins": wins,
        "win_pct": wins / bets_count * 100.0 if bets_count else 0.0,
        "initial_bankroll": initial_bankroll,
        "final_bankroll": bankroll,
        "bankroll_profit": bankroll - initial_bankroll,
        "bankroll_return_pct": (bankroll - initial_bankroll) / initial_bankroll * 100.0 if initial_bankroll else 0.0,
        "total_staked": total_staked,
        "yield_pct": (bankroll - initial_bankroll) / total_staked * 100.0 if total_staked else 0.0,
        "unit_profit": unit_profit,
        "unit_staked": float(bets_count),
        "unit_yield_pct": unit_profit / bets_count * 100.0 if bets_count else 0.0,
        "max_drawdown_pct": max_drawdown,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit > 0 else 0.0),
        "avg_implied_probability": statistics.fmean(1.0 / float(bet["odds"]) for bet in bets) if bets else 0.0,
    }
    if keep_records:
        result["records"] = records
    return result


def rounded_metrics(metrics: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in metrics.items():
        if key == "records":
            continue
        if isinstance(value, float):
            out[key] = "inf" if math.isinf(value) else round(value, 6)
        else:
            out[key] = value
    return out


def choose_threshold(
    rows: Sequence[dict[str, object]],
    edge_grid: Sequence[float] = EDGE_GRID,
    ev_grid: Sequence[float] = EV_GRID,
    min_tune_bets: int = 50,
) -> dict[str, object]:
    grid: list[dict[str, object]] = []
    for edge in edge_grid:
        for ev in ev_grid:
            bets = candidate_bets(rows, edge, ev)
            sim = simulate_bankroll(bets, haircut=0.0)
            grid.append(
                {
                    "edge_threshold": edge,
                    "min_ev": ev,
                    "bets": int(sim["bets"]),
                    "wins": int(sim["wins"]),
                    "unit_profit": float(sim["unit_profit"]),
                    "unit_yield_pct": float(sim["unit_yield_pct"]),
                    "bankroll_profit": float(sim["bankroll_profit"]),
                    "yield_pct": float(sim["yield_pct"]),
                    "max_drawdown_pct": float(sim["max_drawdown_pct"]),
                }
            )
    eligible = [row for row in grid if int(row["bets"]) >= min_tune_bets]
    if not eligible:
        return {
            "inconclusive": True,
            "reason": f"no threshold pair reached {min_tune_bets} tune bets",
            "grid": sorted(grid, key=lambda row: float(row["unit_yield_pct"]), reverse=True),
        }
    best = max(
        eligible,
        key=lambda row: (
            float(row["unit_yield_pct"]),
            float(row["unit_profit"]),
            int(row["bets"]),
            -float(row["edge_threshold"]),
            -float(row["min_ev"]),
        ),
    )
    result = dict(best)
    result["inconclusive"] = False
    result["grid"] = sorted(grid, key=lambda row: float(row["unit_yield_pct"]), reverse=True)
    return result


def season_order(games: Sequence[RealOddsGame]) -> list[dict[str, object]]:
    grouped: dict[str, list[RealOddsGame]] = defaultdict(list)
    for game in games:
        grouped[game.season].append(game)
    rows = []
    for season, season_games in grouped.items():
        rows.append(
            {
                "season": season,
                "games": len(season_games),
                "first_date": min(game.game_date for game in season_games),
                "last_date": max(game.game_date for game in season_games),
            }
        )
    return sorted(rows, key=lambda row: str(row["first_date"]))


def make_folds(games: Sequence[RealOddsGame], rows: Sequence[dict[str, object]], config: Config) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    seasons = season_order(games)
    feature_counts = Counter(str(row["season"]) for row in rows)
    for season in seasons:
        season["side_rows_after_warmup"] = feature_counts[str(season["season"])]
        season["completed_for_schedule"] = int(season["games"]) >= config.min_completed_season_games
    completed = [season for season in seasons if bool(season["completed_for_schedule"])]
    folds: list[dict[str, object]] = []
    for index in range(1, len(completed)):
        test_season = str(completed[index]["season"])
        previous_two = completed[max(0, index - 2) : index]
        usable_previous_two = len(previous_two) == 2 and all(int(season["side_rows_after_warmup"]) > 0 for season in previous_two)
        tune_seasons = [str(season["season"]) for season in (previous_two if usable_previous_two else [completed[index - 1]])]
        folds.append(
            {
                "fold_id": len(folds) + 1,
                "tune_seasons": tune_seasons,
                "test_season": test_season,
                "test_first_date": completed[index]["first_date"],
                "test_last_date": completed[index]["last_date"],
            }
        )
    return folds, seasons


def rows_for_seasons(rows: Sequence[dict[str, object]], seasons: Iterable[str]) -> list[dict[str, object]]:
    season_set = set(seasons)
    return [row for row in rows if str(row["season"]) in season_set]


def side_for_game(game_rows: Sequence[dict[str, object]], selector: str) -> dict[str, object] | None:
    if not game_rows:
        return None
    if selector == "market_favorite":
        return min(game_rows, key=lambda row: float(row["odds"]))
    if selector == "market_underdog":
        return max(game_rows, key=lambda row: float(row["odds"]))
    if selector == "home_side":
        return next((row for row in game_rows if row["side"] == "home"), None)
    if selector == "away_side":
        return next((row for row in game_rows if row["side"] == "away"), None)
    if selector == "hodge_only_side":
        return max(game_rows, key=lambda row: float(row["hodge_prob"]))
    if selector == "contrarian_side":
        hodge = max(game_rows, key=lambda row: float(row["hodge_prob"]))
        return next((row for row in game_rows if row["side"] != hodge["side"]), None)
    raise ValueError(f"unknown selector {selector}")


def baseline_bets(selected: Sequence[dict[str, object]], test_rows: Sequence[dict[str, object]], selector: str) -> list[dict[str, object]]:
    by_game: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in test_rows:
        by_game[str(row["game_id"])].append(row)
    output = []
    for selected_bet in selected:
        chosen = side_for_game(by_game[str(selected_bet["game_id"])], selector)
        if chosen is not None:
            output.append(dict(chosen))
    return output


def random_control_bets(selected: Sequence[dict[str, object]], test_rows: Sequence[dict[str, object]], seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    pools: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in test_rows:
        pools[str(row["odds_band"])].append(row)
    all_rows = list(test_rows)
    output = []
    for selected_bet in selected:
        pool = pools.get(str(selected_bet["odds_band"])) or all_rows
        if not pool:
            continue
        output.append(dict(rng.choice(pool)))
    return output


def evaluate_baselines(fold_id: int, selected: Sequence[dict[str, object]], test_rows: Sequence[dict[str, object]], config: Config) -> list[dict[str, object]]:
    baseline_rows: list[dict[str, object]] = []
    selectors = ["market_favorite", "market_underdog", "home_side", "away_side", "hodge_only_side", "contrarian_side"]
    for selector in selectors:
        bets = baseline_bets(selected, test_rows, selector)
        sim = simulate_bankroll(bets, haircut=0.01, initial_bankroll=config.initial_bankroll, flat_fraction=config.flat_fraction, max_day_exposure=config.max_day_exposure)
        row = {"fold_id": fold_id, "strategy": selector, "haircut": 0.01, "status": "completed"}
        row.update(rounded_metrics(sim))
        baseline_rows.append(row)
    for seed in RANDOM_SEEDS:
        bets = random_control_bets(selected, test_rows, seed)
        sim = simulate_bankroll(bets, haircut=0.01, initial_bankroll=config.initial_bankroll, flat_fraction=config.flat_fraction, max_day_exposure=config.max_day_exposure)
        row = {"fold_id": fold_id, "strategy": f"odds_band_random_seed_{seed}", "haircut": 0.01, "status": "completed"}
        row.update(rounded_metrics(sim))
        baseline_rows.append(row)
    baseline_rows.append(
        {
            "fold_id": fold_id,
            "strategy": "market_only_expected_value_calibration",
            "haircut": 0.01,
            "status": "skipped",
            "skip_reason": "not feasible from closing odds alone because normalized market probabilities produce non-positive raw EV after overround",
            "bets": 0,
            "unit_yield_pct": 0.0,
            "yield_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }
    )
    return baseline_rows


def contribution(records: Sequence[dict[str, object]], key: str, total_profit: float) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0.0, "wins": 0.0, "profit": 0.0, "staked": 0.0})
    for record in records:
        group_key = str(record[key])
        grouped[group_key]["bets"] += 1
        grouped[group_key]["wins"] += int(bool(record["won"]))
        grouped[group_key]["profit"] += float(record["profit"])
        grouped[group_key]["staked"] += float(record["stake"])
    rows = []
    for group_key, row in grouped.items():
        profit = row["profit"]
        rows.append(
            {
                key: group_key,
                "bets": int(row["bets"]),
                "wins": int(row["wins"]),
                "profit": round(profit, 6),
                "staked": round(row["staked"], 6),
                "yield_pct": round(profit / row["staked"] * 100.0, 6) if row["staked"] else 0.0,
                "profit_share_of_total": round(profit / total_profit, 6) if total_profit > 0 else None,
            }
        )
    return sorted(rows, key=lambda row: float(row["profit"]), reverse=True)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_thresholds(fold_results: Sequence[dict[str, object]]) -> dict[str, int]:
    counts = Counter()
    for fold in fold_results:
        if fold.get("status") == "completed":
            counts[f"edge={fold['edge_threshold']}|ev={fold['min_ev']}"] += 1
    return dict(sorted(counts.items()))


def write_report(path: Path, results: dict[str, object]) -> None:
    aggregate = results["aggregate_by_haircut"]  # type: ignore[index]
    h1 = aggregate["0.01"]  # type: ignore[index]
    h2 = aggregate["0.02"]  # type: ignore[index]
    quarantine = results["quarantine"]  # type: ignore[index]
    folds = results["folds"]  # type: ignore[index]
    concentration = results["concentration"]  # type: ignore[index]
    lines = [
        "# Cycle 2 NHL rolling walk-forward experiment report",
        "",
        "## Hypothesis tested",
        "",
        "The frozen test asks whether the historically positive strict NHL Hodge-vs-market pocket survives chronological walk-forward threshold selection, odds quarantine, same-game baselines, and 1%-2% decimal-odds return haircuts.",
        "",
        "## Experiment performed",
        "",
        "1. Wrote pre-registration artifacts before evaluating Cycle 2 results.",
        "2. Quarantined NHL rows from `site/data/historical_sportsbook_games.csv` using the frozen rules.",
        "3. Generated chronological no-future Hodge side rows with 300-game warmup and 760-game rolling training window.",
        "4. For each eligible test season, selected Hodge edge/EV thresholds on the preceding tune season(s) only, then applied them once to the untouched test season.",
        "5. Simulated selected bets under 0%, 1%, 2%, and 3% return haircuts and computed same-game baselines plus odds-band random controls.",
        "",
        "## Files changed",
        "",
        "All result artifacts were written under `scratch/`, with a concise `context.md` update planned after completion.",
        "",
        "## Commands/checks run",
        "",
        "- `python scratch\\test_nhl_cycle2_walkforward.py` before implementation: failed with `ModuleNotFoundError`, confirming the red test state.",
        "- `python scratch\\test_nhl_cycle2_walkforward.py` after implementation.",
        "- `python scratch\\nhl_cycle2_walkforward.py`.",
        "- `python -m compileall scratch\\nhl_cycle2_walkforward.py scratch\\test_nhl_cycle2_walkforward.py`.",
        "",
        "## Quarantine counts",
        "",
        f"- NHL rows: {quarantine['nhl_rows']}",
        f"- Included rows: {quarantine['included_rows']}",
        f"- Excluded rows: {quarantine['excluded_rows']}",
        f"- Excluded reasons: `{quarantine['excluded_reasons']}`",
        f"- Overround >1.05 and <=1.06 flags: {quarantine['flagged_overround_gt_1.05_lte_1.06']}",
        f"- Overround summary: `{quarantine['overround_summary']}`",
        "",
        "## Fold-level results at 1% haircut",
        "",
        "| fold | tune seasons | test season | status | threshold | tune bets | test bets | win % | unit yield % | bankroll yield % | max DD % |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in folds:  # type: ignore[assignment]
        if fold.get("status") != "completed":
            lines.append(
                f"| {fold['fold_id']} | {', '.join(fold['tune_seasons'])} | {fold['test_season']} | {fold['status']} | n/a | {fold.get('tune_rows', 0)} | 0 | 0.00 | 0.00 | 0.00 | 0.00 |"
            )
            continue
        primary = fold["test_by_haircut"]["0.01"]
        lines.append(
            f"| {fold['fold_id']} | {', '.join(fold['tune_seasons'])} | {fold['test_season']} | completed | {fold['edge_threshold']}/{fold['min_ev']} | {fold['tune_selected_bets']} | {primary['bets']} | {primary['win_pct']:.2f} | {primary['unit_yield_pct']:.2f} | {primary['yield_pct']:.2f} | {primary['max_drawdown_pct']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate slippage results",
            "",
            "| haircut | bets | wins | win % | unit yield % | final bankroll | bankroll yield % | max DD % | profit factor |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in aggregate.items():  # type: ignore[union-attr]
        lines.append(
            f"| {float(label) * 100:.0f}% | {row['bets']} | {row['wins']} | {row['win_pct']:.2f} | {row['unit_yield_pct']:.2f} | {row['final_bankroll']:.2f} | {row['yield_pct']:.2f} | {row['max_drawdown_pct']:.2f} | {row['profit_factor']} |"
        )
    lines.extend(
        [
            "",
            "## Baseline and concentration findings",
            "",
            f"- 1% haircut aggregate unit yield: {h1['unit_yield_pct']:.2f}%.",
            f"- 2% haircut aggregate unit yield: {h2['unit_yield_pct']:.2f}%.",
            f"- Threshold selections: `{results['threshold_selection_counts']}`.",
            f"- Baseline window wins versus best market baseline: {results['baseline_comparison']['beats_best_market_baseline_windows']} of {results['baseline_comparison']['completed_windows']} completed windows.",
            f"- Baseline window wins versus random-control mean: {results['baseline_comparison']['beats_random_control_mean_windows']} of {results['baseline_comparison']['completed_windows']} completed windows.",
            f"- Concentration flags: `{concentration['flags']}`.",
            f"- Top season contribution: `{concentration['season_contribution'][0] if concentration['season_contribution'] else None}`.",
            f"- Top odds-band contribution: `{concentration['odds_band_contribution'][0] if concentration['odds_band_contribution'] else None}`.",
            f"- Top side contribution: `{concentration['side_contribution'][0] if concentration['side_contribution'] else None}`.",
            f"- Top team-cluster contribution: `{concentration['team_cluster_contribution'][0] if concentration['team_cluster_contribution'] else None}`.",
            "",
            "## Result label",
            "",
            f"- Label: **{results['result_label']}**.",
            f"- Confidence: **{results['confidence']}**.",
            f"- Rule evaluation: `{results['rule_evaluation']}`.",
            "",
            "## Checks not run or limited",
            "",
            "- Market-only EV calibration was marked skipped because closing odds alone imply non-positive raw EV once overround is included; favorite/underdog baselines were run instead.",
            "- Archived odds timing/executability remains unresolved because the local archive lacks timestamped price snapshots.",
            "- Team-cluster concentration is represented by selected-team clusters, not external roster/style clusters.",
            "",
            "## Recommended next action",
            "",
            "Hand off this evidence packet to `llm-result-critic` for skeptical review of the frozen-rule implementation choices, the incomplete 2022-23 exclusion, and whether the failure/inconclusive criteria were applied appropriately.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(config: Config) -> dict[str, object]:
    games, quarantine = load_clean_games(config)
    side_rows, feature_manifest = build_side_rows(games, config)
    folds, season_manifest = make_folds(games, side_rows, config)
    fold_results: list[dict[str, object]] = []
    fold_csv_rows: list[dict[str, object]] = []
    slippage_rows: list[dict[str, object]] = []
    baseline_rows: list[dict[str, object]] = []
    all_selected: list[dict[str, object]] = []
    baseline_comparison = {
        "completed_windows": 0,
        "beats_best_market_baseline_windows": 0,
        "beats_random_control_mean_windows": 0,
    }

    for fold in folds:
        tune_rows = rows_for_seasons(side_rows, fold["tune_seasons"])
        test_rows = rows_for_seasons(side_rows, [str(fold["test_season"])])
        threshold = choose_threshold(tune_rows, min_tune_bets=config.min_tune_bets)
        fold_row = dict(fold)
        fold_row["tune_rows"] = len(tune_rows)
        fold_row["test_rows"] = len(test_rows)
        if bool(threshold["inconclusive"]):
            fold_row.update({"status": "inconclusive", "reason": threshold["reason"], "threshold_grid_top": threshold["grid"][:5]})
            fold_results.append(fold_row)
            fold_csv_rows.append({k: v for k, v in fold_row.items() if k != "threshold_grid_top"})
            continue
        edge = float(threshold["edge_threshold"])
        ev = float(threshold["min_ev"])
        selected = candidate_bets(test_rows, edge, ev)
        all_selected.extend(selected)
        test_by_haircut: dict[str, dict[str, object]] = {}
        for haircut in HAIRCUTS:
            sim = simulate_bankroll(
                selected,
                haircut=haircut,
                initial_bankroll=config.initial_bankroll,
                flat_fraction=config.flat_fraction,
                max_day_exposure=config.max_day_exposure,
                keep_records=False,
            )
            rounded = rounded_metrics(sim)
            test_by_haircut[str(haircut)] = rounded
            slippage_row = {"fold_id": fold["fold_id"], "test_season": fold["test_season"], "haircut": haircut}
            slippage_row.update(rounded)
            slippage_rows.append(slippage_row)
        baseline_fold_rows = evaluate_baselines(int(fold["fold_id"]), selected, test_rows, config)
        baseline_rows.extend(baseline_fold_rows)
        primary = test_by_haircut["0.01"]
        market_completed = [row for row in baseline_fold_rows if row["strategy"] in {"market_favorite", "market_underdog"}]
        random_completed = [row for row in baseline_fold_rows if str(row["strategy"]).startswith("odds_band_random")]
        best_market_yield = max((float(row["unit_yield_pct"]) for row in market_completed), default=-math.inf)
        random_mean_yield = statistics.fmean(float(row["unit_yield_pct"]) for row in random_completed) if random_completed else -math.inf
        baseline_comparison["completed_windows"] += 1
        baseline_comparison["beats_best_market_baseline_windows"] += int(float(primary["unit_yield_pct"]) > best_market_yield)
        baseline_comparison["beats_random_control_mean_windows"] += int(float(primary["unit_yield_pct"]) > random_mean_yield)
        fold_row.update(
            {
                "status": "completed",
                "edge_threshold": edge,
                "min_ev": ev,
                "tune_selected_bets": int(threshold["bets"]),
                "tune_unit_yield_pct": float(threshold["unit_yield_pct"]),
                "threshold_grid_top": threshold["grid"][:5],
                "test_selected_bets": len(selected),
                "test_by_haircut": test_by_haircut,
                "beats_best_market_baseline_1pct": float(primary["unit_yield_pct"]) > best_market_yield,
                "best_market_baseline_unit_yield_pct": best_market_yield,
                "beats_random_control_mean_1pct": float(primary["unit_yield_pct"]) > random_mean_yield,
                "random_control_mean_unit_yield_pct": random_mean_yield,
            }
        )
        fold_results.append(fold_row)
        csv_row = {
            "fold_id": fold_row["fold_id"],
            "tune_seasons": ";".join(fold_row["tune_seasons"]),
            "test_season": fold_row["test_season"],
            "status": fold_row["status"],
            "edge_threshold": edge,
            "min_ev": ev,
            "tune_rows": len(tune_rows),
            "tune_selected_bets": int(threshold["bets"]),
            "tune_unit_yield_pct": round(float(threshold["unit_yield_pct"]), 6),
            "test_rows": len(test_rows),
            "test_selected_bets": len(selected),
            "test_unit_yield_pct_1pct": primary["unit_yield_pct"],
            "test_bankroll_yield_pct_1pct": primary["yield_pct"],
            "test_max_drawdown_pct_1pct": primary["max_drawdown_pct"],
            "beats_best_market_baseline_1pct": fold_row["beats_best_market_baseline_1pct"],
            "beats_random_control_mean_1pct": fold_row["beats_random_control_mean_1pct"],
        }
        fold_csv_rows.append(csv_row)

    aggregate_by_haircut: dict[str, dict[str, object]] = {}
    aggregate_records_1pct: list[dict[str, object]] = []
    for haircut in HAIRCUTS:
        sim = simulate_bankroll(
            all_selected,
            haircut=haircut,
            initial_bankroll=config.initial_bankroll,
            flat_fraction=config.flat_fraction,
            max_day_exposure=config.max_day_exposure,
            keep_records=haircut == 0.01,
        )
        aggregate_by_haircut[str(haircut)] = rounded_metrics(sim)
        if haircut == 0.01:
            aggregate_records_1pct = sim.get("records", [])  # type: ignore[assignment]
        slippage_row = {"fold_id": "aggregate", "test_season": "aggregate", "haircut": haircut}
        slippage_row.update(rounded_metrics(sim))
        slippage_rows.append(slippage_row)

    total_profit_1pct = float(aggregate_by_haircut["0.01"]["bankroll_profit"])
    season_contrib = contribution(aggregate_records_1pct, "season", total_profit_1pct)
    odds_contrib = contribution(aggregate_records_1pct, "odds_band", total_profit_1pct)
    side_contrib = contribution(aggregate_records_1pct, "side", total_profit_1pct)
    team_contrib = contribution(aggregate_records_1pct, "selected_team", total_profit_1pct)
    top_season_share = float(season_contrib[0]["profit_share_of_total"] or 0.0) if season_contrib else 0.0
    top_odds_share = float(odds_contrib[0]["profit_share_of_total"] or 0.0) if odds_contrib else 0.0
    top_side_share = float(side_contrib[0]["profit_share_of_total"] or 0.0) if side_contrib else 0.0
    top_team_share = float(team_contrib[0]["profit_share_of_total"] or 0.0) if team_contrib else 0.0
    concentration = {
        "season_contribution": season_contrib,
        "odds_band_contribution": odds_contrib,
        "side_contribution": side_contrib,
        "team_cluster_contribution": team_contrib,
        "flags": {
            "single_season_gt_60pct_total_profit": total_profit_1pct > 0 and top_season_share > 0.60,
            "single_odds_band_gt_80pct_total_profit": total_profit_1pct > 0 and top_odds_share > 0.80,
            "single_side_gt_80pct_total_profit": total_profit_1pct > 0 and top_side_share > 0.80,
            "single_team_cluster_gt_80pct_total_profit": total_profit_1pct > 0 and top_team_share > 0.80,
        },
    }

    completed_windows = [fold for fold in fold_results if fold.get("status") == "completed"]
    positive_1pct_windows = sum(1 for fold in completed_windows if float(fold["test_by_haircut"]["0.01"]["unit_yield_pct"]) > 0.0)
    best_market_by_yield = [row for row in baseline_rows if row.get("strategy") in {"market_favorite", "market_underdog"}]
    best_market_max_dd = min((float(row.get("max_drawdown_pct", 0.0)) for row in best_market_by_yield), default=math.inf)
    selected_max_dd = float(aggregate_by_haircut["0.01"]["max_drawdown_pct"])
    beats_market_majority = baseline_comparison["beats_best_market_baseline_windows"] > baseline_comparison["completed_windows"] / 2
    beats_random_majority = baseline_comparison["beats_random_control_mean_windows"] > baseline_comparison["completed_windows"] / 2
    rule_evaluation = {
        "eligible_test_windows": len(completed_windows),
        "minimum_3_eligible_test_windows": len(completed_windows) >= 3,
        "positive_windows_after_1pct": positive_1pct_windows,
        "minimum_2_positive_windows_after_1pct": positive_1pct_windows >= 2,
        "aggregate_1pct_unit_yield_positive": float(aggregate_by_haircut["0.01"]["unit_yield_pct"]) > 0.0,
        "aggregate_2pct_unit_yield_non_negative": float(aggregate_by_haircut["0.02"]["unit_yield_pct"]) >= 0.0,
        "beats_best_market_baseline_majority": beats_market_majority,
        "beats_random_control_mean_majority": beats_random_majority,
        "no_single_season_gt_60pct_total_profit": not concentration["flags"]["single_season_gt_60pct_total_profit"],
        "no_single_odds_band_side_or_team_cluster_gt_80pct_total_profit": not any(
            concentration["flags"][key]
            for key in (
                "single_odds_band_gt_80pct_total_profit",
                "single_side_gt_80pct_total_profit",
                "single_team_cluster_gt_80pct_total_profit",
            )
        ),
        "selected_max_drawdown_not_worse_than_best_market_by_10pp": selected_max_dd <= best_market_max_dd + 10.0,
    }
    if len(completed_windows) < 3:
        result_label = "inconclusive"
    elif float(aggregate_by_haircut["0.01"]["unit_yield_pct"]) <= 0.0:
        result_label = "failure"
    elif not beats_market_majority or not beats_random_majority:
        result_label = "failure"
    elif float(aggregate_by_haircut["0.02"]["unit_yield_pct"]) < 0.0:
        result_label = "failure"
    elif concentration["flags"]["single_season_gt_60pct_total_profit"] or any(
        concentration["flags"][key]
        for key in (
            "single_odds_band_gt_80pct_total_profit",
            "single_side_gt_80pct_total_profit",
            "single_team_cluster_gt_80pct_total_profit",
        )
    ):
        result_label = "failure"
    elif positive_1pct_windows < 2:
        result_label = "failure"
    elif selected_max_dd > best_market_max_dd + 10.0:
        result_label = "failure"
    else:
        result_label = "success"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "quarantine": quarantine,
        "feature_manifest": feature_manifest,
        "season_manifest": season_manifest,
        "folds": fold_results,
        "fold_csv_rows": fold_csv_rows,
        "baseline_rows": baseline_rows,
        "slippage_rows": slippage_rows,
        "aggregate_by_haircut": aggregate_by_haircut,
        "concentration": concentration,
        "baseline_comparison": baseline_comparison,
        "threshold_selection_counts": summarize_thresholds(fold_results),
        "rule_evaluation": rule_evaluation,
        "result_label": result_label,
        "confidence": "medium" if len(completed_windows) >= 3 else "low",
        "selected_bets_1pct_records_kept": len(aggregate_records_1pct),
    }


def main() -> None:
    config = Config()
    results = run(config)
    scratch = BASE / "scratch"
    write_json(scratch / "nhl_cycle2_data_quarantine.json", results["quarantine"])
    write_json(scratch / "nhl_cycle2_feature_manifest.json", results["feature_manifest"])
    walkforward_payload = {
        key: value
        for key, value in results.items()
        if key not in {"fold_csv_rows", "baseline_rows", "slippage_rows"}
    }
    write_json(scratch / "nhl_cycle2_walkforward_results.json", walkforward_payload)
    write_csv(scratch / "nhl_cycle2_walkforward_folds.csv", results["fold_csv_rows"])  # type: ignore[arg-type]
    write_csv(scratch / "nhl_cycle2_baselines.csv", results["baseline_rows"])  # type: ignore[arg-type]
    write_csv(scratch / "nhl_cycle2_slippage.csv", results["slippage_rows"])  # type: ignore[arg-type]
    write_json(scratch / "nhl_cycle2_concentration.json", results["concentration"])
    write_report(scratch / "nhl_cycle2_experiment_report.md", walkforward_payload)
    print(json.dumps({"result_label": results["result_label"], "aggregate_by_haircut": results["aggregate_by_haircut"], "rule_evaluation": results["rule_evaluation"]}, indent=2))


if __name__ == "__main__":
    main()
