from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


BASE = Path(__file__).resolve().parents[1]
CSV_PATH = BASE / "site/data/historical_sportsbook_games.csv"
STRICT_PATH = BASE / "site/data/hodge_real_sportsbook_agent_nhl_strict.json"
SPLIT_PATHS = {
    "split50_25": BASE / "scratch/hodge_market_residual_strategy_nhl_split50_25.json",
    "split70_15": BASE / "scratch/hodge_market_residual_strategy_nhl_split70_15.json",
    "canonical_site_split": BASE / "site/data/hodge_market_residual_strategy_nhl.json",
}
OUT_JSON = BASE / "scratch/nhl_edge_supplemental_audit.json"
OUT_MD = BASE / "scratch/nhl_edge_supplemental_audit.md"


def as_float(raw: object) -> float | None:
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


def pct(numerator: float, denominator: float) -> float:
    return numerator / denominator * 100.0 if denominator else 0.0


def yield_pct(profit: float, staked: float) -> float:
    return pct(profit, staked)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_nhl_rows() -> list[dict]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("sport") == "NHL"]


def odds_quarantine(rows: list[dict]) -> dict:
    overrounds: list[float] = []
    duplicate_keys: Counter[tuple[str, str, str]] = Counter()
    counts = Counter()
    by_season = Counter(row.get("season", "") for row in rows)
    by_source = Counter(row.get("source", "") for row in rows)

    for row in rows:
        duplicate_keys[(row.get("date", ""), row.get("away_team", ""), row.get("home_team", ""))] += 1
        away_odds = as_float(row.get("away_odds_decimal"))
        home_odds = as_float(row.get("home_odds_decimal"))
        draw_odds = as_float(row.get("draw_odds_decimal"))
        away_score = as_float(row.get("away_score"))
        home_score = as_float(row.get("home_score"))
        outcome = row.get("outcome")
        if away_odds is None:
            counts["missing_away_odds"] += 1
        if home_odds is None:
            counts["missing_home_odds"] += 1
        if away_odds is not None and away_odds <= 1.0:
            counts["invalid_away_odds_le_1"] += 1
        if home_odds is not None and home_odds <= 1.0:
            counts["invalid_home_odds_le_1"] += 1
        if draw_odds is not None:
            counts["draw_odds_present"] += 1
        if away_score is not None and home_score is not None:
            expected = "away" if away_score > home_score else "home" if home_score > away_score else "draw"
            if outcome != expected:
                counts["outcome_score_mismatch"] += 1
            if expected == "draw":
                counts["draw_score_rows"] += 1
        if away_odds is not None and home_odds is not None and away_odds > 1.0 and home_odds > 1.0:
            overround = 1.0 / away_odds + 1.0 / home_odds
            overrounds.append(overround)
            if overround < 1.0:
                counts["overround_under_1_00"] += 1
            if overround > 1.05:
                counts["overround_over_1_05"] += 1
            if overround > 1.08:
                counts["overround_over_1_08"] += 1
            if overround > 1.10:
                counts["overround_over_1_10"] += 1

    duplicate_game_keys = {"|".join(key): value for key, value in duplicate_keys.items() if value > 1}
    overrounds_sorted = sorted(overrounds)
    summary = {
        "rows": len(rows),
        "seasons": dict(sorted(by_season.items())),
        "sources": dict(sorted(by_source.items())),
        "counts": dict(sorted(counts.items())),
        "duplicate_date_away_home_count": len(duplicate_game_keys),
        "duplicate_date_away_home_examples": dict(list(sorted(duplicate_game_keys.items()))[:10]),
    }
    if overrounds_sorted:
        summary["overround"] = {
            "n": len(overrounds_sorted),
            "mean": round(mean(overrounds_sorted), 6),
            "median": round(median(overrounds_sorted), 6),
            "min": round(overrounds_sorted[0], 6),
            "p05": round(overrounds_sorted[int(len(overrounds_sorted) * 0.05)], 6),
            "p95": round(overrounds_sorted[min(len(overrounds_sorted) - 1, int(len(overrounds_sorted) * 0.95))], 6),
            "max": round(overrounds_sorted[-1], 6),
        }
    return summary


def group_by_date(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[str(record["date"])].append(record)
    return dict(grouped)


def replay_records(
    records: list[dict],
    *,
    side_getter,
    odds_getter,
    haircut: float = 0.0,
    initial: float = 1000.0,
    flat_fraction: float = 0.01,
    max_day_exposure: float = 0.05,
) -> dict:
    bankroll = initial
    peak = initial
    wins = 0
    total_staked = 0.0
    max_dd = 0.0
    profit_by_year: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    profit_by_season: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})

    for bet_date, day in sorted(group_by_date(records).items()):
        active = [record for record in day if side_getter(record) in {"home", "away"} and odds_getter(record) is not None]
        if not active:
            continue
        requested_stakes = [bankroll * flat_fraction for _ in active]
        total_requested = sum(requested_stakes)
        scale = min(1.0, bankroll * max_day_exposure / total_requested) if total_requested > 0 else 0.0
        for record, requested_stake in zip(active, requested_stakes):
            side = side_getter(record)
            odds_raw = float(odds_getter(record))
            odds = max(1.000001, odds_raw * (1.0 - haircut))
            stake = requested_stake * scale
            won = record["actual"] == side
            profit = stake * (odds - 1.0) if won else -stake
            bankroll += profit
            total_staked += stake
            wins += int(won)
            year = str(record["date"])[:4]
            season = str(record.get("season", ""))
            for bucket, key in ((profit_by_year, year), (profit_by_season, season)):
                bucket[key]["bets"] += 1
                bucket[key]["wins"] += int(won)
                bucket[key]["profit"] += profit
                bucket[key]["staked"] += stake
            peak = max(peak, bankroll)
            max_dd = max(max_dd, (peak - bankroll) / max(peak, 1e-9) * 100.0)

    bets = sum(int(row["bets"]) for row in profit_by_year.values())
    return {
        "bets": bets,
        "wins": wins,
        "win_pct": round(pct(wins, bets), 2),
        "initial_bankroll": round(initial, 2),
        "final_bankroll": round(bankroll, 2),
        "profit": round(bankroll - initial, 2),
        "roi_pct": round(pct(bankroll - initial, initial), 2),
        "total_staked": round(total_staked, 2),
        "yield_pct": round(yield_pct(bankroll - initial, total_staked), 2),
        "max_drawdown_pct": round(max_dd, 2),
        "by_year": summarize_bucket(profit_by_year),
        "by_season": summarize_bucket(profit_by_season),
    }


def summarize_bucket(bucket: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out = {}
    for key, row in sorted(bucket.items()):
        bets = int(row["bets"])
        wins = int(row["wins"])
        profit = float(row["profit"])
        staked = float(row["staked"])
        out[key] = {
            "bets": bets,
            "wins": wins,
            "win_pct": round(pct(wins, bets), 2),
            "profit": round(profit, 2),
            "staked": round(staked, 2),
            "yield_pct": round(yield_pct(profit, staked), 2),
        }
    return out


def parse_matchup(matchup: str) -> tuple[str, str] | None:
    if " @ " not in matchup:
        return None
    away, home = matchup.split(" @ ", 1)
    return away, home


def attach_csv_odds(records: list[dict], rows: list[dict]) -> tuple[list[dict], dict]:
    lookup: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        lookup[(row["date"], row["away_team"], row["home_team"])] = row
    enriched = []
    misses = []
    for record in records:
        teams = parse_matchup(str(record.get("matchup", "")))
        if teams is None:
            misses.append(record.get("matchup", ""))
            continue
        key = (str(record["date"]), teams[0], teams[1])
        row = lookup.get(key)
        if row is None:
            misses.append("|".join(key))
            continue
        copy = dict(record)
        copy["away_team"] = teams[0]
        copy["home_team"] = teams[1]
        copy["csv_away_odds"] = as_float(row.get("away_odds_decimal"))
        copy["csv_home_odds"] = as_float(row.get("home_odds_decimal"))
        enriched.append(copy)
    return enriched, {"input_records": len(records), "matched": len(enriched), "misses": len(misses), "miss_examples": misses[:10]}


def market_side(record: dict, kind: str) -> str:
    away = record.get("csv_away_odds")
    home = record.get("csv_home_odds")
    if away is None or home is None:
        return ""
    if kind == "home":
        return "home"
    if kind == "away":
        return "away"
    if kind == "favorite":
        return "away" if away < home else "home"
    if kind == "underdog":
        return "away" if away > home else "home"
    raise ValueError(kind)


def odds_for_side(record: dict, side: str) -> float | None:
    if side == "home":
        return record.get("csv_home_odds")
    if side == "away":
        return record.get("csv_away_odds")
    return None


def exposure_summary(records: list[dict]) -> dict:
    by_side = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    by_favdog = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    by_band = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    by_edge_band = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})

    def add(bucket, key, record):
        bucket[key]["bets"] += 1
        bucket[key]["wins"] += int(bool(record["won"]))
        bucket[key]["profit"] += float(record["profit"])
        bucket[key]["staked"] += float(record["stake"])

    for record in records:
        side = str(record["side"])
        add(by_side, side, record)
        selected_odds = float(record["odds"])
        other_odds = record.get("csv_home_odds") if side == "away" else record.get("csv_away_odds")
        if other_odds is not None:
            if selected_odds < float(other_odds):
                favdog = "favorite"
            elif selected_odds > float(other_odds):
                favdog = "underdog"
            else:
                favdog = "pickem"
            add(by_favdog, favdog, record)
        if selected_odds < 1.50:
            odds_band = "lt_1.50"
        elif selected_odds < 1.75:
            odds_band = "1.50_to_1.75"
        elif selected_odds < 2.00:
            odds_band = "1.75_to_2.00"
        else:
            odds_band = "ge_2.00"
        add(by_band, odds_band, record)
        edge = float(record.get("edge", 0.0))
        if edge < 0.18:
            edge_band = "0.15_to_0.18"
        elif edge < 0.22:
            edge_band = "0.18_to_0.22"
        elif edge < 0.30:
            edge_band = "0.22_to_0.30"
        else:
            edge_band = "ge_0.30"
        add(by_edge_band, edge_band, record)

    return {
        "by_side": summarize_bucket(by_side),
        "by_favorite_underdog": summarize_bucket(by_favdog),
        "by_selected_odds_band": summarize_bucket(by_band),
        "by_model_edge_band": summarize_bucket(by_edge_band),
    }


def era_summary(by_year: dict[str, dict]) -> dict:
    eras = {
        "early_2013_2016": ["2013", "2014", "2015", "2016"],
        "middle_2017_2019": ["2017", "2018", "2019"],
        "late_2020_2022": ["2020", "2021", "2022"],
    }
    out = {}
    for era, years in eras.items():
        bets = wins = 0
        profit = staked = 0.0
        for year in years:
            row = by_year.get(year)
            if not row:
                continue
            bets += int(row["bets"])
            wins += int(row["wins"])
            profit += float(row["profit"])
            staked += float(row["staked"])
        out[era] = {
            "bets": bets,
            "wins": wins,
            "win_pct": round(pct(wins, bets), 2),
            "profit": round(profit, 2),
            "staked": round(staked, 2),
            "yield_pct": round(yield_pct(profit, staked), 2),
        }
    return out


def residual_split_summary() -> dict:
    out = {}
    for label, path in SPLIT_PATHS.items():
        data = load_json(path)
        best = data["tune_threshold_selection"]["best"]
        test = data["test_result"]
        out[label] = {
            "config": data.get("config", {}),
            "coverage": data.get("coverage", {}),
            "split": data.get("split", {}),
            "tune_best": {key: best.get(key) for key in ["edge_threshold", "min_ev", "bets", "wins", "win_pct", "yield_pct", "max_drawdown_pct", "final_bankroll"]},
            "test_result": {key: test.get(key) for key in ["edge_threshold", "min_ev", "bets", "wins", "win_pct", "yield_pct", "max_drawdown_pct", "final_bankroll", "roi_pct"]},
            "accuracy": data.get("accuracy", {}),
        }
    return out


def make_markdown(report: dict) -> str:
    residual = report["residual_splits"]
    slippage = report["strict_nhl_slippage_dynamic_replay"]
    baselines = report["same_window_baselines"]
    exposure = report["strict_nhl_exposure"]
    lines = [
        "# NHL strict edge supplemental audit",
        "",
        "Scratch-only evidence generated from existing artifacts. No site/data artifacts were modified.",
        "",
        "## Residual split smoke tests",
        "",
        "| split | train_frac | tune_frac | tune bets | tune yield % | selected edge | selected min_ev | test bets | test win % | test yield % | test max DD % | test date window |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, row in residual.items():
        cfg = row["config"]
        split = row["split"]["test"]
        tune = row["tune_best"]
        test = row["test_result"]
        lines.append(
            f"| {label} | {cfg.get('train_frac')} | {cfg.get('tune_frac')} | {tune['bets']} | {tune['yield_pct']} | {tune['edge_threshold']} | {tune['min_ev']} | {test['bets']} | {test['win_pct']} | {test['yield_pct']} | {test['max_drawdown_pct']} | {split.get('first')}..{split.get('last')} |"
        )

    lines += [
        "",
        "## Odds quarantine counts",
        "",
        json.dumps(report["odds_quarantine"], indent=2),
        "",
        "## Strict NHL slippage replay",
        "",
        "Dynamic replay uses the same stored selections, 1% flat staking, 5% max same-day exposure, and reduced decimal odds.",
        "",
        "| haircut | bets | wins | win % | final bankroll | yield % | max DD % |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in slippage.items():
        lines.append(f"| {label} | {row['bets']} | {row['wins']} | {row['win_pct']} | {row['final_bankroll']} | {row['yield_pct']} | {row['max_drawdown_pct']} |")

    lines += [
        "",
        "## Season and era contribution",
        "",
        "| era | bets | wins | win % | profit | staked | yield % |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for era, row in report["strict_nhl_era_summary"].items():
        lines.append(f"| {era} | {row['bets']} | {row['wins']} | {row['win_pct']} | {row['profit']} | {row['staked']} | {row['yield_pct']} |")

    lines += [
        "",
        "## Same-window baselines on strict bet games",
        "",
        "| strategy | matched bets | wins | win % | final bankroll | yield % | max DD % |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in baselines.items():
        lines.append(f"| {label} | {row['bets']} | {row['wins']} | {row['win_pct']} | {row['final_bankroll']} | {row['yield_pct']} | {row['max_drawdown_pct']} |")

    lines += [
        "",
        "## Strict NHL exposure decomposition",
        "",
        "### By side",
        "",
        json.dumps(exposure["by_side"], indent=2),
        "",
        "### By favorite/underdog",
        "",
        json.dumps(exposure["by_favorite_underdog"], indent=2),
        "",
        "### By selected odds band",
        "",
        json.dumps(exposure["by_selected_odds_band"], indent=2),
        "",
        "### By model edge band",
        "",
        json.dumps(exposure["by_model_edge_band"], indent=2),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    nhl_rows = load_nhl_rows()
    strict = load_json(STRICT_PATH)
    strict_records = strict["agent"]["bets"]
    matched_records, match_quality = attach_csv_odds(strict_records, nhl_rows)

    slippage = {}
    for haircut in (0.0, 0.01, 0.02, 0.03):
        key = f"{int(haircut * 100)}pct"
        slippage[key] = replay_records(
            strict_records,
            side_getter=lambda record: str(record["side"]),
            odds_getter=lambda record: float(record["odds"]),
            haircut=haircut,
            initial=float(strict["config"]["initial_bankroll"]),
            flat_fraction=float(strict["config"]["max_bet_fraction"]),
            max_day_exposure=float(strict["config"]["max_day_exposure"]),
        )

    same_window_baselines = {
        "stored_strict_hodge_selection": slippage["0pct"],
    }
    for kind in ("home", "away", "favorite", "underdog"):
        same_window_baselines[f"same_games_{kind}"] = replay_records(
            matched_records,
            side_getter=lambda record, kind=kind: market_side(record, kind),
            odds_getter=lambda record, kind=kind: odds_for_side(record, market_side(record, kind)),
            initial=float(strict["config"]["initial_bankroll"]),
            flat_fraction=float(strict["config"]["max_bet_fraction"]),
            max_day_exposure=float(strict["config"]["max_day_exposure"]),
        )

    report = {
        "inputs": {
            "historical_csv": str(CSV_PATH.relative_to(BASE)).replace("\\", "/"),
            "strict_nhl_artifact": str(STRICT_PATH.relative_to(BASE)).replace("\\", "/"),
            "residual_artifacts": {key: str(path.relative_to(BASE)).replace("\\", "/") for key, path in SPLIT_PATHS.items()},
        },
        "residual_splits": residual_split_summary(),
        "odds_quarantine": odds_quarantine(nhl_rows),
        "strict_nhl_match_quality": match_quality,
        "strict_nhl_summary_source": strict["agent"]["summary"],
        "strict_nhl_slippage_dynamic_replay": slippage,
        "strict_nhl_era_summary": era_summary(slippage["0pct"]["by_year"]),
        "same_window_baselines": same_window_baselines,
        "strict_nhl_exposure": exposure_summary(matched_records),
    }

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_MD.write_text(make_markdown(report), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(BASE)}")
    print(f"Wrote {OUT_MD.relative_to(BASE)}")


if __name__ == "__main__":
    main()
