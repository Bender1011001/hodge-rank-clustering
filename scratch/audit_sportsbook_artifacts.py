from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def pct(value: float) -> str:
    return f"{value:.2f}%"


def load_json(rel: str) -> dict:
    with (BASE / rel).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def yield_pct(profit: float, staked: float) -> float:
    return profit / staked * 100.0 if staked else 0.0


def summarize_agent_artifacts() -> None:
    print("\n=== Real sportsbook agent artifacts ===")
    files = {
        "broad_default": "site/data/hodge_real_sportsbook_agent.json",
        "strict_all_sports": "site/data/hodge_real_sportsbook_agent_strict.json",
        "strict_nba_nhl": "site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json",
        "strict_nhl": "site/data/hodge_real_sportsbook_agent_nhl_strict.json",
        "strict_nba": "site/data/hodge_real_sportsbook_agent_nba_strict.json",
        "cfb_audit": "site/data/hodge_real_sportsbook_agent_cfb_audit.json",
    }
    for label, rel in files.items():
        data = load_json(rel)
        summary = data["agent"]["summary"]
        coverage = data.get("coverage", {})
        print(
            f"{label}: games={coverage.get('games')} dates={coverage.get('first_date')}..{coverage.get('last_date')} "
            f"bets={summary['bets']} wins={summary['wins']} win_pct={summary['win_pct']} "
            f"bankroll={summary['initial_bankroll']}->{summary['final_bankroll']} "
            f"roi={summary['roi_pct']} yield={summary['yield_on_stake_pct']} max_dd={summary['max_drawdown_pct']}"
        )
        print(f"  by_sport={summary.get('by_sport', {})}")
        print(f"  by_year={summary.get('by_year', {})}")
        print(f"  skipped={data['agent'].get('skipped', {})}")


def simulate_records(records: list[dict], flat_fraction: float, max_day_exposure: float = 0.05, initial: float = 1000.0) -> dict:
    by_date: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_date[str(record["date"])].append(record)
    bankroll = initial
    wins = 0
    total_staked = 0.0
    peak = initial
    max_dd = 0.0
    profit_by_year: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    for bet_date in sorted(by_date):
        day = by_date[bet_date]
        requested = [bankroll * flat_fraction for _ in day]
        total = sum(requested)
        scale = min(1.0, bankroll * max_day_exposure / total) if total > 0 else 0.0
        for record, requested_stake in zip(day, requested):
            stake = requested_stake * scale
            won = bool(record["won"])
            profit = stake * (float(record["odds"]) - 1.0) if won else -stake
            bankroll += profit
            wins += int(won)
            total_staked += stake
            year = str(record["date"])[:4]
            profit_by_year[year]["bets"] += 1
            profit_by_year[year]["wins"] += int(won)
            profit_by_year[year]["profit"] += profit
            profit_by_year[year]["staked"] += stake
            peak = max(peak, bankroll)
            max_dd = max(max_dd, (peak - bankroll) / max(peak, 1e-9) * 100.0)
    by_year = {
        year: {
            "bets": int(row["bets"]),
            "wins": int(row["wins"]),
            "profit": round(row["profit"], 2),
            "staked": round(row["staked"], 2),
            "yield_pct": round(yield_pct(row["profit"], row["staked"]), 2),
        }
        for year, row in sorted(profit_by_year.items())
    }
    return {
        "bets": len(records),
        "wins": wins,
        "final": round(bankroll, 2),
        "profit": round(bankroll - initial, 2),
        "total_staked": round(total_staked, 2),
        "yield_pct": round(yield_pct(bankroll - initial, total_staked), 2),
        "max_dd_pct": round(max_dd, 2),
        "by_year": by_year,
    }


def robustness_from_stored_bets() -> None:
    print("\n=== Robustness checks from stored bet records ===")
    for label, rel in {
        "strict_nhl_full": "site/data/hodge_real_sportsbook_agent_nhl_strict.json",
        "strict_nba_nhl_truncated_last_2000": "site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json",
    }.items():
        data = load_json(rel)
        records = data["agent"].get("bets", [])
        summary_bets = data["agent"]["summary"]["bets"]
        print(f"{label}: stored_records={len(records)} summary_bets={summary_bets} first_stored={records[0]['date'] if records else None} last_stored={records[-1]['date'] if records else None}")
        for frac in (0.005, 0.01, 0.02):
            sim = simulate_records(records, flat_fraction=frac, max_day_exposure=0.05)
            print(f"  replay_same_selections flat_fraction={frac}: {sim}")
        if records and all("edge" in record and "ev" in record for record in records):
            for edge, ev in ((0.15, 0.05), (0.18, 0.05), (0.20, 0.05), (0.20, 0.08), (0.25, 0.10)):
                subset = [record for record in records if float(record["edge"]) >= edge and float(record["ev"]) >= ev]
                if not subset:
                    print(f"  subfilter edge>={edge} ev>={ev}: no stored bets")
                    continue
                sim = simulate_records(subset, flat_fraction=0.01, max_day_exposure=0.05)
                print(f"  subfilter edge>={edge} ev>={ev}: {sim}")


def summarize_residual_artifacts() -> None:
    print("\n=== Market residual artifacts ===")
    files = {
        "all_sports": "site/data/hodge_market_residual_strategy.json",
        "nba_nhl": "site/data/hodge_market_residual_strategy_nba_nhl.json",
        "nhl": "site/data/hodge_market_residual_strategy_nhl.json",
        "nba": "site/data/hodge_market_residual_strategy_nba.json",
    }
    for label, rel in files.items():
        data = load_json(rel)
        cov = data["coverage"]
        split = data["split"]
        best = data["tune_threshold_selection"]["best"]
        test = data["test_result"]
        print(
            f"{label}: games={cov['games_loaded']} side_rows={cov['side_rows']} "
            f"train/tune/test rows={cov['train_rows']}/{cov['tune_rows']}/{cov['test_rows']} "
            f"dates={cov['first_date']}..{cov['last_date']}"
        )
        print(f"  split={split}")
        print(f"  tune_best=edge {best['edge_threshold']} min_ev {best['min_ev']} bets {best['bets']} yield {best['yield_pct']} max_dd {best['max_drawdown_pct']} by_sport={best.get('by_sport')}")
        print(f"  test=bets {test['bets']} wins {test['wins']} win_pct {test['win_pct']} final {test['final_bankroll']} yield {test['yield_pct']} max_dd {test['max_drawdown_pct']} by_sport={test.get('by_sport')}")
        print(f"  accuracy={data.get('accuracy')}")


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
    if not math.isfinite(value):
        return None
    return value


def audit_games_csv() -> None:
    print("\n=== Historical sportsbook games CSV audit ===")
    rel = "site/data/historical_sportsbook_games.csv"
    path = BASE / rel
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []
    print(f"fields={fields}")
    print(f"rows={len(rows)}")
    if not rows:
        return
    sport_col = "sport" if "sport" in fields else fields[0]
    season_col = "season" if "season" in fields else None
    date_col = "game_date" if "game_date" in fields else ("date" if "date" in fields else None)
    odds_cols = [field for field in fields if "odds" in field.lower()]
    score_cols = [field for field in fields if "score" in field.lower()]
    print(f"odds_cols={odds_cols} score_cols={score_cols}")
    by_sport: dict[str, int] = defaultdict(int)
    by_sport_season: dict[tuple[str, str], int] = defaultdict(int)
    date_min = None
    date_max = None
    missing_by_sport_col: dict[tuple[str, str], int] = defaultdict(int)
    invalid_by_sport_col: dict[tuple[str, str], int] = defaultdict(int)
    overrounds: dict[str, list[float]] = defaultdict(list)
    overround_flags: dict[str, dict[str, int]] = defaultdict(lambda: {"under_1": 0, "over_1_10": 0, "over_1_20": 0})
    draws_by_sport: dict[str, int] = defaultdict(int)
    for row in rows:
        sport = row.get(sport_col, "UNKNOWN")
        by_sport[sport] += 1
        if season_col:
            by_sport_season[(sport, row.get(season_col, ""))] += 1
        if date_col:
            d = row.get(date_col)
            if d:
                date_min = d if date_min is None or d < date_min else date_min
                date_max = d if date_max is None or d > date_max else date_max
        valid_odds = []
        for col in odds_cols:
            value = parse_float(row.get(col))
            if value is None:
                missing_by_sport_col[(sport, col)] += 1
            elif value <= 1.0:
                invalid_by_sport_col[(sport, col)] += 1
            else:
                valid_odds.append(value)
        if valid_odds:
            overround = sum(1.0 / value for value in valid_odds)
            overrounds[sport].append(overround)
            if overround < 1.0:
                overround_flags[sport]["under_1"] += 1
            if overround > 1.10:
                overround_flags[sport]["over_1_10"] += 1
            if overround > 1.20:
                overround_flags[sport]["over_1_20"] += 1
        away_score = parse_float(row.get("away_score"))
        home_score = parse_float(row.get("home_score"))
        if away_score is not None and home_score is not None and away_score == home_score:
            draws_by_sport[sport] += 1
    print(f"date_range={date_min}..{date_max}")
    print(f"by_sport={dict(sorted(by_sport.items()))}")
    print("by_sport_season=")
    for key, count in sorted(by_sport_season.items()):
        print(f"  {key}: {count}")
    print(f"draws_by_sport={dict(sorted(draws_by_sport.items()))}")
    print("missing_odds_by_sport_col=")
    for key, count in sorted(missing_by_sport_col.items()):
        if count:
            print(f"  {key}: {count}")
    print("invalid_odds_by_sport_col=")
    for key, count in sorted(invalid_by_sport_col.items()):
        if count:
            print(f"  {key}: {count}")
    print("overround_by_sport=")
    for sport, values in sorted(overrounds.items()):
        if values:
            values_sorted = sorted(values)
            mean = sum(values) / len(values)
            p05 = values_sorted[int(len(values_sorted) * 0.05)]
            p95 = values_sorted[min(len(values_sorted) - 1, int(len(values_sorted) * 0.95))]
            print(f"  {sport}: n={len(values)} mean={mean:.4f} min={values_sorted[0]:.4f} p05={p05:.4f} p95={p95:.4f} max={values_sorted[-1]:.4f}")
    print(f"overround_flags={dict(sorted(overround_flags.items()))}")
    sources = load_json("site/data/historical_sportsbook_sources.json")
    print("sources_summary=")
    print(json.dumps(sources, indent=2)[:6000])


def main() -> None:
    audit_games_csv()
    summarize_agent_artifacts()
    robustness_from_stored_bets()
    summarize_residual_artifacts()


if __name__ == "__main__":
    main()
