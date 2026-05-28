from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


SCRATCH = Path(__file__).resolve().parent
BASE = SCRATCH.parent
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import nhl_cycle2_walkforward as wf  # noqa: E402


FROZEN_EDGE = 0.15
FROZEN_EV = 0.05
HAIRCUTS = (0.01, 0.02)
RANDOM_SEEDS = (7, 17, 29)
ODDS_BANDS = ("<1.50", "1.50-1.75", "1.75-2.00", "2.00-2.50", ">=2.50")
PREPLANNED_TEAM_ORDER = (
    "Winnipeg",
    "St.Louis",
    "Arizona",
    "NYIslanders",
    "Anaheim",
    "Vegas",
    "NYRangers",
    "Carolina",
    "Washington",
    "Minnesota",
)


@dataclass(frozen=True)
class SelectedUniverse:
    selected: list[dict[str, object]]
    side_rows: list[dict[str, object]]
    folds: list[dict[str, object]]
    cycle2_results: dict[str, object]


def read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def rounded(value: object) -> object:
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return round(value, 6)
    return value


def rounded_dict(row: dict[str, object]) -> dict[str, object]:
    return {key: rounded(value) for key, value in row.items()}


def bet_key(row: dict[str, object]) -> tuple[str, str]:
    return str(row["game_id"]), str(row["side"])


def reconstruct_selected_universe() -> SelectedUniverse:
    cycle2_path = SCRATCH / "nhl_cycle2_walkforward_results.json"
    cycle2_results = read_json(cycle2_path)
    config = wf.Config()
    games, _quarantine = wf.load_clean_games(config)
    side_rows, _manifest = wf.build_side_rows(games, config)
    folds, _seasons = wf.make_folds(games, side_rows, config)
    rows_by_season: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in side_rows:
        rows_by_season[str(row["season"])].append(dict(row))

    completed_artifact_folds = {
        int(fold["fold_id"]): fold
        for fold in cycle2_results.get("folds", [])  # type: ignore[union-attr]
        if isinstance(fold, dict) and fold.get("status") == "completed"
    }
    annotated_side_rows: list[dict[str, object]] = []
    selected: list[dict[str, object]] = []
    reconstructed_folds: list[dict[str, object]] = []
    for fold in folds:
        fold_id = int(fold["fold_id"])
        artifact_fold = completed_artifact_folds.get(fold_id)
        if artifact_fold is None:
            continue
        edge = float(artifact_fold["edge_threshold"])
        ev = float(artifact_fold["min_ev"])
        if abs(edge - FROZEN_EDGE) > 1e-12 or abs(ev - FROZEN_EV) > 1e-12:
            raise ValueError(f"completed fold {fold_id} is not on frozen thresholds: {edge}/{ev}")
        test_season = str(fold["test_season"])
        test_rows = [dict(row) for row in rows_by_season[test_season]]
        for row in test_rows:
            row["fold_id"] = fold_id
            row["test_window"] = test_season
            row["test_first_date"] = fold["test_first_date"]
            row["test_last_date"] = fold["test_last_date"]
            annotated_side_rows.append(row)
        fold_selected = wf.candidate_bets(test_rows, edge, ev)
        for row in fold_selected:
            row = dict(row)
            row["fold_id"] = fold_id
            row["test_window"] = test_season
            row["test_first_date"] = fold["test_first_date"]
            row["test_last_date"] = fold["test_last_date"]
            selected.append(row)
        reconstructed_folds.append(
            {
                "fold_id": fold_id,
                "test_season": test_season,
                "edge_threshold": edge,
                "min_ev": ev,
                "artifact_selected_bets": int(artifact_fold["test_selected_bets"]),
                "reconstructed_selected_bets": len(fold_selected),
            }
        )

    selected.sort(key=lambda row: (str(row["date"]), int(row.get("sequence", 0)), str(row["game_id"])))
    annotated_side_rows.sort(key=lambda row: (str(row["date"]), int(row.get("sequence", 0)), str(row["game_id"]), str(row["side"])))
    return SelectedUniverse(selected=selected, side_rows=annotated_side_rows, folds=reconstructed_folds, cycle2_results=cycle2_results)


def summarize_cohort(bets: Sequence[dict[str, object]], label: str) -> dict[str, object]:
    summary: dict[str, object] = {"label": label, "haircuts": {}}
    by_haircut: dict[str, dict[str, object]] = {}
    for haircut in HAIRCUTS:
        sim = wf.simulate_bankroll(bets, haircut=haircut, keep_records=False)
        by_haircut[str(haircut)] = rounded_dict(sim)
    summary["haircuts"] = by_haircut
    summary["profit_share_1pct"] = {
        "side": profit_contribution(bets, "side"),
        "odds_band": profit_contribution(bets, "odds_band"),
        "selected_team": profit_contribution(bets, "selected_team"),
        "season": profit_contribution(bets, "season"),
    }
    return summary


def metrics_at(summary: dict[str, object], haircut: float = 0.01) -> dict[str, object]:
    return summary["haircuts"][str(haircut)]  # type: ignore[index]


def verify_selected_identity(selected: Sequence[dict[str, object]]) -> dict[str, object]:
    one = metrics_at(summarize_cohort(selected, "identity"), 0.01)
    two = metrics_at(summarize_cohort(selected, "identity"), 0.02)
    actual = {
        "bets": int(one["bets"]),
        "wins": int(one["wins"]),
        "win_rate_pct": float(one["win_pct"]),
        "unit_yield_pct_1pct": float(one["unit_yield_pct"]),
        "unit_yield_pct_2pct": float(two["unit_yield_pct"]),
    }
    expected = {
        "bets": 325,
        "wins": 182,
        "win_rate_pct": 56.0,
        "unit_yield_pct_1pct": 6.72,
        "unit_yield_pct_2pct": 6.21,
    }
    checks = {
        "bets_exact": actual["bets"] == expected["bets"],
        "wins_exact": actual["wins"] == expected["wins"],
        "win_rate_within_0_005pp": abs(actual["win_rate_pct"] - expected["win_rate_pct"]) <= 0.005,
        "unit_yield_1pct_within_0_01pp": abs(actual["unit_yield_pct_1pct"] - expected["unit_yield_pct_1pct"]) <= 0.01,
        "unit_yield_2pct_within_0_01pp": abs(actual["unit_yield_pct_2pct"] - expected["unit_yield_pct_2pct"]) <= 0.01,
    }
    return {"expected": expected, "actual": rounded_dict(actual), "checks": checks, "passed": all(checks.values())}


def side_rows_by_game(rows: Sequence[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["game_id"])].append(dict(row))
    return grouped


def choose_same_game_side(game_rows: Sequence[dict[str, object]], selector: str) -> dict[str, object] | None:
    if not game_rows:
        return None
    if selector == "market_favorite":
        return min(game_rows, key=lambda row: float(row["odds"]))
    if selector == "market_underdog":
        return max(game_rows, key=lambda row: float(row["odds"]))
    if selector == "home_only":
        return next((row for row in game_rows if row["side"] == "home"), None)
    if selector == "away_only":
        return next((row for row in game_rows if row["side"] == "away"), None)
    raise ValueError(f"unknown selector {selector}")


def same_game_control(selected: Sequence[dict[str, object]], side_rows: Sequence[dict[str, object]], selector: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    grouped = side_rows_by_game(side_rows)
    controls: list[dict[str, object]] = []
    missing = 0
    odds_band_matches = 0
    for bet in selected:
        chosen = choose_same_game_side(grouped[str(bet["game_id"])], selector)
        if chosen is None:
            missing += 1
            continue
        control = dict(chosen)
        control["control_for_game_id"] = bet["game_id"]
        control["control_selector"] = selector
        control["selected_odds_band"] = bet["odds_band"]
        control["selected_side"] = bet["side"]
        odds_band_matches += int(str(control["odds_band"]) == str(bet["odds_band"]))
        controls.append(control)
    diagnostics = {
        "selector": selector,
        "selected_bets": len(selected),
        "control_bets": len(controls),
        "missing_controls": missing,
        "same_odds_band_matches": odds_band_matches,
        "same_odds_band_match_rate": odds_band_matches / len(controls) if controls else 0.0,
    }
    return controls, rounded_dict(diagnostics)


def parse_date(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def pool_for_relaxation(selected_bet: dict[str, object], rows: Sequence[dict[str, object]], label: str, selected_key: tuple[str, str]) -> list[dict[str, object]]:
    selected_band = str(selected_bet["odds_band"])
    selected_date = parse_date(str(selected_bet["date"]))
    selected_season = str(selected_bet["season"])
    selected_fold = selected_bet.get("fold_id")
    pool: list[dict[str, object]] = []
    for row in rows:
        if bet_key(row) == selected_key:
            continue
        if str(row["odds_band"]) != selected_band:
            continue
        row_date = parse_date(str(row["date"]))
        if label == "same_date_and_odds_band" and str(row["date"]) != str(selected_bet["date"]):
            continue
        if label == "same_week_and_odds_band" and abs((row_date - selected_date).days) > 7:
            continue
        if label == "same_season_and_odds_band" and str(row["season"]) != selected_season:
            continue
        if label == "same_test_window_and_odds_band" and row.get("fold_id") != selected_fold:
            continue
        pool.append(dict(row))
    return pool


def date_window_random_control(selected: Sequence[dict[str, object]], rows: Sequence[dict[str, object]], seed: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    rng = random.Random(seed)
    relaxation_order = (
        "same_date_and_odds_band",
        "same_week_and_odds_band",
        "same_season_and_odds_band",
        "same_test_window_and_odds_band",
        "global_same_odds_band",
    )
    controls: list[dict[str, object]] = []
    counts = Counter()
    missing = 0
    for bet in selected:
        chosen = None
        selected_key = bet_key(bet)
        for label in relaxation_order:
            pool = pool_for_relaxation(bet, rows, label, selected_key)
            if pool:
                chosen = dict(rng.choice(pool))
                chosen["control_relaxation"] = label
                counts[label] += 1
                break
        if chosen is None:
            missing += 1
            continue
        chosen["control_for_game_id"] = bet["game_id"]
        chosen["selected_odds_band"] = bet["odds_band"]
        chosen["selected_side"] = bet["side"]
        controls.append(chosen)
    diagnostics = {
        "seed": seed,
        "selected_bets": len(selected),
        "control_bets": len(controls),
        "missing_controls": missing,
        "relaxation_counts": dict(sorted(counts.items())),
        "relaxation_rates": {key: value / len(controls) for key, value in sorted(counts.items())} if controls else {},
    }
    return controls, diagnostics


def profit_contribution(bets: Sequence[dict[str, object]], key: str, haircut: float = 0.01) -> list[dict[str, object]]:
    sim = wf.simulate_bankroll(bets, haircut=haircut, keep_records=True)
    total_unit_profit = float(sim["unit_profit"])
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0.0, "wins": 0.0, "unit_profit": 0.0})
    for record in sim.get("records", []):
        group_key = str(record.get(key, "UNKNOWN"))
        grouped[group_key]["bets"] += 1.0
        grouped[group_key]["wins"] += int(bool(record["won"]))
        grouped[group_key]["unit_profit"] += float(record["unit_profit"])
    rows = []
    for group_key, values in grouped.items():
        unit_profit = values["unit_profit"]
        rows.append(
            {
                key: group_key,
                "bets": int(values["bets"]),
                "wins": int(values["wins"]),
                "unit_profit": round(unit_profit, 6),
                "unit_yield_pct": round(unit_profit / values["bets"] * 100.0, 6) if values["bets"] else 0.0,
                "profit_share_of_total_unit_profit": round(unit_profit / total_unit_profit, 6) if total_unit_profit > 0 else None,
            }
        )
    return sorted(rows, key=lambda row: float(row["unit_profit"]), reverse=True)


def side_odds_crosstab(bets: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for side in ("home", "away"):
        for band in ODDS_BANDS:
            cohort = [bet for bet in bets if str(bet["side"]) == side and str(bet["odds_band"]) == band]
            if not cohort:
                continue
            one = metrics_at(summarize_cohort(cohort, f"{side}|{band}"), 0.01)
            rows.append(
                {
                    "side": side,
                    "odds_band": band,
                    "bets": one["bets"],
                    "wins": one["wins"],
                    "win_pct": one["win_pct"],
                    "unit_yield_pct_1pct": one["unit_yield_pct"],
                    "max_drawdown_pct_1pct": one["max_drawdown_pct"],
                }
            )
    return rows


def ablation_summary(label: str, bets: Sequence[dict[str, object]], removed: dict[str, object]) -> dict[str, object]:
    summary = summarize_cohort(bets, label)
    summary["removed"] = removed
    return summary


def build_ablations(selected: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    ablations: dict[str, dict[str, object]] = {}
    ablations["remove_home"] = ablation_summary("remove_home", [bet for bet in selected if bet["side"] != "home"], {"side": "home"})
    ablations["remove_away"] = ablation_summary("remove_away", [bet for bet in selected if bet["side"] != "away"], {"side": "away"})
    for band in ODDS_BANDS:
        ablations[f"remove_odds_band_{band}"] = ablation_summary(
            f"remove_odds_band_{band}",
            [bet for bet in selected if str(bet["odds_band"]) != band],
            {"odds_band": band},
        )
    for team in PREPLANNED_TEAM_ORDER:
        ablations[f"remove_team_{team}"] = ablation_summary(
            f"remove_team_{team}",
            [bet for bet in selected if str(bet["selected_team"]) != team],
            {"selected_team": team},
        )
    positive_teams = [str(row["selected_team"]) for row in profit_contribution(selected, "selected_team") if float(row["unit_profit"]) > 0.0]
    for n in (1, 3, 5, 10):
        teams = positive_teams[:n]
        ablations[f"remove_cumulative_top_{n}_teams"] = ablation_summary(
            f"remove_cumulative_top_{n}_teams",
            [bet for bet in selected if str(bet["selected_team"]) not in set(teams)],
            {"selected_teams": teams},
        )
    return ablations


def build_controls(selected: Sequence[dict[str, object]], side_rows: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    controls: dict[str, dict[str, object]] = {}
    for selector in ("market_favorite", "market_underdog", "home_only", "away_only"):
        bets, diagnostics = same_game_control(selected, side_rows, selector)
        controls[selector] = {"summary": summarize_cohort(bets, selector), "matching": diagnostics}
    for seed in RANDOM_SEEDS:
        bets, diagnostics = date_window_random_control(selected, side_rows, seed)
        label = f"date_window_odds_band_random_seed_{seed}"
        controls[label] = {"summary": summarize_cohort(bets, label), "matching": rounded_dict(diagnostics)}
    random_yields = [float(metrics_at(row["summary"], 0.01)["unit_yield_pct"]) for key, row in controls.items() if key.startswith("date_window")]
    if random_yields:
        controls["date_window_odds_band_random_mean"] = {
            "summary": {
                "label": "date_window_odds_band_random_mean",
                "haircuts": {
                    "0.01": {
                        "unit_yield_pct": round(statistics.fmean(random_yields), 6),
                        "seeds": list(RANDOM_SEEDS),
                    }
                },
            },
            "matching": {"note": "mean of seed-level one-percent unit yields only"},
        }
    return controls


def selected_vs_controls(selected_summary: dict[str, object], controls: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    selected_one = metrics_at(selected_summary, 0.01)
    selected_two = metrics_at(selected_summary, 0.02)
    rows = []
    for label, payload in controls.items():
        if label.endswith("_mean"):
            continue
        summary = payload["summary"]
        one = metrics_at(summary, 0.01)
        two = metrics_at(summary, 0.02)
        rows.append(
            rounded_dict(
                {
                    "control": label,
                    "bets": one["bets"],
                    "wins": one["wins"],
                    "unit_yield_pct_1pct": float(one["unit_yield_pct"]),
                    "delta_vs_selected_unit_yield_1pct": float(selected_one["unit_yield_pct"]) - float(one["unit_yield_pct"]),
                    "unit_yield_pct_2pct": float(two["unit_yield_pct"]),
                    "delta_vs_selected_unit_yield_2pct": float(selected_two["unit_yield_pct"]) - float(two["unit_yield_pct"]),
                    "max_drawdown_pct_1pct": float(one["max_drawdown_pct"]),
                    "delta_vs_selected_drawdown_1pct": float(one["max_drawdown_pct"]) - float(selected_one["max_drawdown_pct"]),
                }
            )
        )
    return sorted(rows, key=lambda row: float(row["unit_yield_pct_1pct"]), reverse=True)


def stop_downgrade_rules(selected_summary: dict[str, object], ablations: dict[str, dict[str, object]], control_deltas: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    selected_one = metrics_at(selected_summary, 0.01)
    selected_yield = float(selected_one["unit_yield_pct"])
    selected_dd = float(selected_one["max_drawdown_pct"])
    triggered: list[dict[str, object]] = []
    key_ablations = {
        "remove_home": "one-percent yield collapsed to zero or negative after removing home selections",
        "remove_odds_band_1.75-2.00": "one-percent yield collapsed to zero or negative after removing 1.75-to-2.00 odds band",
        "remove_team_Winnipeg": "one-percent yield collapsed to zero or negative after removing Winnipeg",
        "remove_cumulative_top_1_teams": "one-percent yield collapsed to zero or negative after removing cumulative top one team",
        "remove_cumulative_top_3_teams": "one-percent yield collapsed to zero or negative after removing cumulative top three teams",
        "remove_cumulative_top_5_teams": "one-percent yield collapsed to zero or negative after removing cumulative top five teams",
        "remove_cumulative_top_10_teams": "one-percent yield collapsed to zero or negative after removing cumulative top ten teams",
    }
    for key, reason in key_ablations.items():
        row = ablations.get(key)
        if not row:
            continue
        one = metrics_at(row, 0.01)
        if float(one["unit_yield_pct"]) <= 0.0:
            triggered.append({"rule": key, "reason": reason, "unit_yield_pct_1pct": one["unit_yield_pct"], "bets": one["bets"]})
        elif int(one["bets"]) < 50:
            triggered.append({"rule": f"{key}_fewer_than_50_residual_bets", "reason": "survival depends on fewer than 50 residual bets", "bets": one["bets"]})
    for row in control_deltas:
        control_yield = float(row["unit_yield_pct_1pct"])
        control_dd = float(row["max_drawdown_pct_1pct"])
        if control_yield >= selected_yield - 1.0:
            triggered.append(
                {
                    "rule": "matched_control_equal_or_better_within_1pp",
                    "control": row["control"],
                    "selected_unit_yield_pct_1pct": round(selected_yield, 6),
                    "control_unit_yield_pct_1pct": row["unit_yield_pct_1pct"],
                }
            )
        if control_yield >= selected_yield and control_dd <= selected_dd - 2.0:
            triggered.append(
                {
                    "rule": "control_materially_better_drawdown_with_equal_or_better_yield",
                    "control": row["control"],
                    "selected_max_drawdown_pct_1pct": round(selected_dd, 6),
                    "control_max_drawdown_pct_1pct": row["max_drawdown_pct_1pct"],
                }
            )
    return triggered


def hypothesis_verdicts(ablations: dict[str, dict[str, object]], control_deltas: Sequence[dict[str, object]], concentration: dict[str, object], triggered_rules: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    remove_home_yield = float(metrics_at(ablations["remove_home"], 0.01)["unit_yield_pct"])
    remove_mid_yield = float(metrics_at(ablations["remove_odds_band_1.75-2.00"], 0.01)["unit_yield_pct"])
    remove_winnipeg_yield = float(metrics_at(ablations["remove_team_Winnipeg"], 0.01)["unit_yield_pct"])
    top_combo = concentration["side_odds_crosstab_top_unit_profit"]  # type: ignore[index]
    control_close = [row for row in control_deltas if float(row["unit_yield_pct_1pct"]) >= float(concentration["selected_unit_yield_pct_1pct"]) - 1.0]
    top_team_rules = [row for row in triggered_rules if str(row.get("rule", "")).startswith("remove_team") or "top_" in str(row.get("rule", ""))]
    return {
        "home_side_artifact": {
            "verdict": "confirmed" if remove_home_yield <= 0.0 else "plausible",
            "confidence": "high" if remove_home_yield <= 0.0 else "medium",
            "evidence": f"remove-home one-percent unit yield = {remove_home_yield:.2f}%",
        },
        "joint_side_plus_odds_artifact": {
            "verdict": "likely" if float(top_combo.get("profit_share_of_total_unit_profit") or 0.0) >= 0.50 else "plausible",
            "confidence": "medium",
            "evidence": f"top side×odds cell = {top_combo}",
        },
        "mid_odds_artifact": {
            "verdict": "confirmed" if remove_mid_yield <= 0.0 else "plausible",
            "confidence": "high" if remove_mid_yield <= 0.0 else "medium",
            "evidence": f"remove-1.75-to-2.00 one-percent unit yield = {remove_mid_yield:.2f}%",
        },
        "market_baseline_artifact": {
            "verdict": "confirmed" if control_close else "contradicted",
            "confidence": "high" if control_close else "medium",
            "evidence": f"controls within 1pp/equal-or-better tolerance = {[row['control'] for row in control_close]}",
        },
        "top_team_artifact": {
            "verdict": "confirmed" if remove_winnipeg_yield <= 0.0 or top_team_rules else "weak signal",
            "confidence": "high" if remove_winnipeg_yield <= 0.0 or top_team_rules else "low",
            "evidence": f"remove-Winnipeg one-percent unit yield = {remove_winnipeg_yield:.2f}%; triggered top-team rules = {top_team_rules}",
        },
        "residual_distributed_anomaly": {
            "verdict": "contradicted" if triggered_rules else "plausible",
            "confidence": "high" if triggered_rules else "low",
            "evidence": f"stop/downgrade rules triggered = {len(triggered_rules)}",
        },
    }


def concentration_summary(selected: Sequence[dict[str, object]], selected_summary: dict[str, object]) -> dict[str, object]:
    side = profit_contribution(selected, "side")
    odds = profit_contribution(selected, "odds_band")
    team = profit_contribution(selected, "selected_team")
    season = profit_contribution(selected, "season")
    cross = []
    for row in wf.simulate_bankroll(selected, haircut=0.01, keep_records=True).get("records", []):
        row = dict(row)
        row["side_odds"] = f"{row['side']}|{row['odds_band']}"
        cross.append(row)
    side_odds = profit_contribution(cross, "side_odds")
    return {
        "selected_unit_yield_pct_1pct": metrics_at(selected_summary, 0.01)["unit_yield_pct"],
        "side_profit": side,
        "odds_band_profit": odds,
        "team_profit": team,
        "season_profit": season,
        "side_odds_profit": side_odds,
        "side_odds_crosstab": side_odds_crosstab(selected),
        "side_odds_crosstab_top_unit_profit": side_odds[0] if side_odds else {},
    }


def compact_table(rows: Iterable[dict[str, object]], keys: Sequence[str], limit: int | None = None) -> list[dict[str, object]]:
    selected_rows = list(rows)
    if limit is not None:
        selected_rows = selected_rows[:limit]
    return [{key: row.get(key) for key in keys} for row in selected_rows]


def write_report(path: Path, results: dict[str, object]) -> None:
    selected = results["selected_summary"]  # type: ignore[index]
    identity = results["selected_identity"]  # type: ignore[index]
    ablations = results["ablations"]  # type: ignore[index]
    control_deltas = results["control_deltas"]  # type: ignore[index]
    concentration = results["concentration"]  # type: ignore[index]
    verdicts = results["hypothesis_verdicts"]  # type: ignore[index]
    lines = [
        "# Cycle 3 NHL diagnostic experiment report",
        "",
        "Historical quantitative research only; not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.",
        "",
        "## 1. Hypothesis tested",
        "",
        "The bounded diagnostic tested whether the Cycle 2 positive aggregate NHL selected-bet anomaly is explained by home-side exposure, mid-odds exposure, top-team contributors, joint side-plus-odds structure, or matched market controls.",
        "",
        "## 2. Experiment performed",
        "",
        "1. Wrote Cycle 3 preregistration artifacts before result artifacts.",
        "2. Reconstructed the frozen Cycle 2 selected universe from the Cycle 2 runner and authoritative Cycle 2 walk-forward artifact, without threshold retuning.",
        "3. Verified selected-universe identity against Cycle 2 aggregate metrics.",
        "4. Ran leave-slice ablations, side×odds diagnostics, same-game matched controls, and date/window-aware odds-band random controls.",
        "5. Applied the frozen stop/downgrade rules.",
        "",
        "## 3. Selected-universe identity check",
        "",
        f"- Passed: `{identity['passed']}`",
        f"- Actual: `{identity['actual']}`",
        f"- Checks: `{identity['checks']}`",
        "",
        "## 4. Selected aggregate metrics",
        "",
        f"- One-percent haircut: `{selected['haircuts']['0.01']}`",
        f"- Two-percent haircut: `{selected['haircuts']['0.02']}`",
        "",
        "## 5. Ablation table summary",
        "",
        "| ablation | bets | wins | 1% unit yield % | 2% unit yield % | 1% max DD % |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    priority_ablation_keys = [
        "remove_home",
        "remove_away",
        "remove_odds_band_1.75-2.00",
        "remove_odds_band_2.00-2.50",
        "remove_team_Winnipeg",
        "remove_cumulative_top_1_teams",
        "remove_cumulative_top_3_teams",
        "remove_cumulative_top_5_teams",
        "remove_cumulative_top_10_teams",
    ]
    for key in priority_ablation_keys:
        row = ablations[key]
        one = row["haircuts"]["0.01"]
        two = row["haircuts"]["0.02"]
        lines.append(f"| {key} | {one['bets']} | {one['wins']} | {one['unit_yield_pct']:.2f} | {two['unit_yield_pct']:.2f} | {one['max_drawdown_pct']:.2f} |")
    lines.extend(
        [
            "",
            "## 6. Matched-control table summary",
            "",
            "| control | bets | wins | 1% unit yield % | delta vs selected pp | 1% max DD % |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in control_deltas:
        lines.append(
            f"| {row['control']} | {row['bets']} | {row['wins']} | {row['unit_yield_pct_1pct']:.2f} | {row['delta_vs_selected_unit_yield_1pct']:.2f} | {row['max_drawdown_pct_1pct']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 7. Concentration summary",
            "",
            f"- Top side contribution: `{concentration['side_profit'][0] if concentration['side_profit'] else None}`",
            f"- Top odds-band contribution: `{concentration['odds_band_profit'][0] if concentration['odds_band_profit'] else None}`",
            f"- Top team contribution: `{concentration['team_profit'][0] if concentration['team_profit'] else None}`",
            f"- Top season contribution: `{concentration['season_profit'][0] if concentration['season_profit'] else None}`",
            f"- Top side×odds contribution: `{concentration['side_odds_crosstab_top_unit_profit']}`",
            "",
            "## 8. Stop/downgrade rule evaluation",
            "",
            f"- Decision: **{results['decision']}**",
            f"- Triggered rules: `{results['triggered_stop_downgrade_rules']}`",
            "",
            "## 9. Hypothesis verdicts",
            "",
        ]
    )
    for key, row in verdicts.items():
        lines.append(f"- {key}: **{row['verdict']}** confidence **{row['confidence']}**. Evidence: {row['evidence']}")
    lines.extend(
        [
            "",
            "## 10. Checks not run or limited",
            "",
            "- Raw-American impossible-pair validation remains blocked because the normalized source lacks raw American moneyline columns.",
            "- Archived odds timing, live availability, line movement, account constraints, and sportsbook executability remain outside Cycle 3.",
            "- Market-only EV calibration remains outside this cycle; same-game market favorite/underdog and side controls were used as practical matched controls.",
            "",
            "## 11. Recommended next action",
            "",
            "Hand off this evidence packet to `llm-result-critic`. The experiment-designer decision is stop/downgrade rather than upgrade to a deployable edge claim if any frozen stop/downgrade rule triggered.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_cycle3() -> dict[str, object]:
    prereg_md = SCRATCH / "nhl_cycle3_preregistration.md"
    prereg_json = SCRATCH / "nhl_cycle3_preregistration.json"
    if not prereg_md.exists() or not prereg_json.exists():
        raise FileNotFoundError("Cycle 3 preregistration artifacts must exist before running diagnostics")
    universe = reconstruct_selected_universe()
    identity = verify_selected_identity(universe.selected)
    selected_summary = summarize_cohort(universe.selected, "selected")
    ablations = build_ablations(universe.selected)
    controls = build_controls(universe.selected, universe.side_rows)
    control_deltas = selected_vs_controls(selected_summary, controls)
    concentration = concentration_summary(universe.selected, selected_summary)
    triggered = stop_downgrade_rules(selected_summary, ablations, control_deltas)
    verdicts = hypothesis_verdicts(ablations, control_deltas, concentration, triggered)
    results = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "responsible_use": "Historical quantitative research only; not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.",
        "inputs": {
            "authoritative_selected_universe": "scratch/nhl_cycle2_walkforward_results.json",
            "reconstruction_reference": "scratch/nhl_cycle2_walkforward.py",
            "preregistration_md": "scratch/nhl_cycle3_preregistration.md",
            "preregistration_json": "scratch/nhl_cycle3_preregistration.json",
        },
        "frozen_thresholds": {"edge_threshold": FROZEN_EDGE, "min_ev": FROZEN_EV, "retuned": False},
        "selected_identity": identity,
        "fold_reconstruction": universe.folds,
        "selected_summary": selected_summary,
        "ablations": ablations,
        "controls": controls,
        "control_deltas": control_deltas,
        "concentration": concentration,
        "triggered_stop_downgrade_rules": triggered,
        "hypothesis_verdicts": verdicts,
        "decision": "stop/downgrade" if triggered or not identity["passed"] else "potential_cycle4_seed",
        "handoff_target": "llm-result-critic",
    }
    if not identity["passed"]:
        results["decision"] = "blocked/inconclusive"
    write_json(SCRATCH / "nhl_cycle3_diagnostic_results.json", results)
    write_report(SCRATCH / "nhl_cycle3_experiment_report.md", results)
    return results


def main() -> None:
    results = run_cycle3()
    print(
        json.dumps(
            {
                "decision": results["decision"],
                "selected_identity": results["selected_identity"],
                "triggered_stop_downgrade_rules": results["triggered_stop_downgrade_rules"],
                "hypothesis_verdicts": results["hypothesis_verdicts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
