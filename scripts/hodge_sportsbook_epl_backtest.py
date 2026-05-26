"""
Walk-forward Hodge sportsbook backtest for EPL 1X2 markets.

Downloads real bookmaker odds from football-data.co.uk, trains the Hodge
ranking model only on matches available before each fixture, converts the
Hodge margin signal into home/draw/away probabilities, and simulates flat and
capped Kelly staking against closing odds where available.

This script is intentionally stricter than the earlier EPL real-odds check:
draws are modeled explicitly, and a home/away bet loses when the match is
drawn. No match result is inspected before deciding whether to bet.

Usage:
    python scripts/hodge_sportsbook_epl_backtest.py
    python scripts/hodge_sportsbook_epl_backtest.py --edge-threshold 0.04
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import scipy.sparse as sp
from scipy.optimize import minimize
from scipy.sparse.linalg import lsqr
from scipy.special import logsumexp


OUTCOMES = ("home", "draw", "away")

DEFAULT_SEASONS: Tuple[Tuple[str, str], ...] = (
    ("EPL 2016-17", "1617"),
    ("EPL 2017-18", "1718"),
    ("EPL 2018-19", "1819"),
    ("EPL 2019-20", "1920"),
    ("EPL 2020-21", "2021"),
    ("EPL 2021-22", "2122"),
    ("EPL 2022-23", "2223"),
    ("EPL 2023-24", "2324"),
    ("EPL 2024-25", "2425"),
    ("EPL 2025-26", "2526"),
)

MARKET_COLUMNS: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    "Pinnacle": (("PSCH", "PSCD", "PSCA"), ("PSH", "PSD", "PSA")),
    "Bet365": (("B365CH", "B365CD", "B365CA"), ("B365H", "B365D", "B365A")),
    "BestAvailable": (("MaxCH", "MaxCD", "MaxCA"), ("MaxH", "MaxD", "MaxA")),
    "MarketAverage": (("AvgCH", "AvgCD", "AvgCA"), ("AvgH", "AvgD", "AvgA")),
}


@dataclass(frozen=True)
class Match:
    season_label: str
    season_code: str
    season_index: int
    match_index: int
    date_text: str
    sort_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    odds: Dict[str, Dict[str, object]]

    @property
    def outcome(self) -> str:
        if self.home_score > self.away_score:
            return "home"
        if self.home_score < self.away_score:
            return "away"
        return "draw"

    @property
    def result_label(self) -> str:
        return f"{self.home_score}-{self.away_score}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season-codes",
        default=",".join(code for _, code in DEFAULT_SEASONS),
        help="Comma-separated football-data season codes. Default is EPL 2016-17 through 2025-26.",
    )
    parser.add_argument(
        "--warmup-matches",
        type=int,
        default=760,
        help="Number of chronological matches used only for warmup before betting starts.",
    )
    parser.add_argument(
        "--training-window-matches",
        type=int,
        default=760,
        help="Rolling number of prior matches used for each Hodge fit and probability calibration.",
    )
    parser.add_argument("--margin-cap", type=float, default=4.0, help="Absolute goal-margin cap.")
    parser.add_argument("--curl-weight", type=float, default=0.0, help="Curl adjustment weight in the margin signal.")
    parser.add_argument("--edge-threshold", type=float, default=0.03, help="Minimum model probability edge over implied odds.")
    parser.add_argument("--min-ev", type=float, default=0.0, help="Minimum expected return per unit staked.")
    parser.add_argument("--flat-fraction", type=float, default=0.01, help="Flat stake fraction of bankroll.")
    parser.add_argument("--kelly-multiplier", type=float, default=0.25, help="Fraction of full Kelly to stake.")
    parser.add_argument("--max-kelly", type=float, default=0.03, help="Maximum Kelly stake fraction of bankroll.")
    parser.add_argument("--initial-bankroll", type=float, default=100.0, help="Starting bankroll per market and strategy.")
    parser.add_argument(
        "--output",
        default=os.path.join("site", "data", "hodge_sportsbook_epl_10yr.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def parse_float(raw: object) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 1.0:
        return None
    return value


def parse_int(raw: object) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_match_date(date_text: str, season_index: int, match_index: int) -> str:
    text = date_text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return f"{season_index:02d}-{match_index:04d}"


def pick_market_odds(row: Dict[str, str], market: str) -> Optional[Dict[str, object]]:
    for home_col, draw_col, away_col in MARKET_COLUMNS[market]:
        home = parse_float(row.get(home_col))
        draw = parse_float(row.get(draw_col))
        away = parse_float(row.get(away_col))
        if home is not None and draw is not None and away is not None:
            return {
                "home": home,
                "draw": draw,
                "away": away,
                "columns": [home_col, draw_col, away_col],
            }
    return None


def download_season(label: str, code: str, season_index: int) -> List[Match]:
    url = f"https://www.football-data.co.uk/mmz4281/{code}/E0.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(raw))
    matches: List[Match] = []
    for row in reader:
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        home_score = parse_int(row.get("FTHG"))
        away_score = parse_int(row.get("FTAG"))
        if not home or not away or home_score is None or away_score is None:
            continue

        odds: Dict[str, Dict[str, object]] = {}
        for market in MARKET_COLUMNS:
            market_odds = pick_market_odds(row, market)
            if market_odds is not None:
                odds[market] = market_odds

        if not odds:
            continue

        match_index = len(matches)
        date_text = (row.get("Date") or "").strip()
        matches.append(
            Match(
                season_label=label,
                season_code=code,
                season_index=season_index,
                match_index=match_index,
                date_text=date_text,
                sort_date=parse_match_date(date_text, season_index, match_index),
                home_team=home,
                away_team=away,
                home_score=home_score,
                away_score=away_score,
                odds=odds,
            )
        )
    return matches


def resolve_season_specs(codes: str) -> List[Tuple[str, str]]:
    default_by_code = {code: label for label, code in DEFAULT_SEASONS}
    specs = []
    for raw_code in codes.split(","):
        code = raw_code.strip()
        if not code:
            continue
        specs.append((default_by_code.get(code, f"EPL {code}"), code))
    if not specs:
        raise ValueError("No season codes supplied.")
    return specs


def weighted_hodge(games: Sequence[Match], teams: Sequence[str], margin_cap: float) -> Dict[str, object]:
    n = len(teams)
    team_index = {team: idx for idx, team in enumerate(teams)}
    if n == 0 or not games:
        return {
            "phi": np.zeros(0),
            "fc": np.zeros(0),
            "e2i": {},
            "hfa": 0.0,
            "team_index": team_index,
            "n_edges": 0,
            "n_triangles": 0,
        }

    hfa = float(np.mean([g.home_score - g.away_score for g in games]))
    pair_margins: Dict[Tuple[int, int], List[float]] = {}

    for game in games:
        home_idx = team_index[game.home_team]
        away_idx = team_index[game.away_team]
        corrected = float(game.home_score - game.away_score) - hfa
        corrected = float(np.clip(corrected, -margin_cap, margin_cap))
        i, j = min(home_idx, away_idx), max(home_idx, away_idx)
        sign = 1.0 if home_idx == i else -1.0
        pair_margins.setdefault((i, j), []).append(sign * corrected)

    edges = sorted(pair_margins)
    m = len(edges)
    edge_index = {edge: idx for idx, edge in enumerate(edges)}
    if m == 0:
        return {
            "phi": np.zeros(n),
            "fc": np.zeros(0),
            "e2i": edge_index,
            "hfa": hfa,
            "team_index": team_index,
            "n_edges": 0,
            "n_triangles": 0,
        }

    flow = np.zeros(m)
    weights = np.zeros(m)
    for idx, edge in enumerate(edges):
        values = pair_margins[edge]
        flow[idx] = np.mean(values)
        weights[idx] = len(values)

    rows: List[int] = []
    cols: List[int] = []
    vals: List[float] = []
    for edge_idx, (i, j) in enumerate(edges):
        rows.extend([i, j])
        cols.extend([edge_idx, edge_idx])
        vals.extend([-1.0, 1.0])
    b1 = sp.csr_matrix((vals, (rows, cols)), shape=(n, m))
    weight_diag = sp.diags(np.sqrt(weights))
    phi = lsqr(weight_diag @ b1.T, np.sqrt(weights) * flow, atol=1e-12, btol=1e-12)[0]
    grad = b1.T @ phi
    residual = flow - grad

    adjacency = {i: set() for i in range(n)}
    for i, j in edges:
        adjacency[i].add(j)
        adjacency[j].add(i)

    triangles: List[Tuple[int, int, int]] = []
    for i in range(n):
        for j in adjacency[i]:
            if j <= i:
                continue
            for k in adjacency[i] & adjacency[j]:
                if k > j:
                    triangles.append((i, j, k))

    if triangles:
        tri_rows: List[int] = []
        tri_cols: List[int] = []
        tri_vals: List[float] = []
        for tri_idx, (a, b, c) in enumerate(triangles):
            for edge, sign in (((a, b), 1.0), ((a, c), -1.0), ((b, c), 1.0)):
                edge_idx = edge_index.get(edge)
                if edge_idx is not None:
                    tri_rows.append(edge_idx)
                    tri_cols.append(tri_idx)
                    tri_vals.append(sign)
        b2 = sp.csr_matrix((tri_vals, (tri_rows, tri_cols)), shape=(m, len(triangles)))
        curl_coeffs = lsqr(weight_diag @ b2, np.sqrt(weights) * residual, atol=1e-12, btol=1e-12)[0]
        curl = b2 @ curl_coeffs
    else:
        curl = np.zeros(m)

    return {
        "phi": phi,
        "fc": curl,
        "e2i": edge_index,
        "hfa": hfa,
        "team_index": team_index,
        "n_edges": m,
        "n_triangles": len(triangles),
    }


def hodge_signal(hodge: Dict[str, object], home_team: str, away_team: str, curl_weight: float) -> Optional[float]:
    team_index: Dict[str, int] = hodge["team_index"]  # type: ignore[assignment]
    home_idx = team_index.get(home_team)
    away_idx = team_index.get(away_team)
    if home_idx is None or away_idx is None:
        return None

    phi: np.ndarray = hodge["phi"]  # type: ignore[assignment]
    signal = float(phi[away_idx] - phi[home_idx] + hodge["hfa"])

    if curl_weight:
        edge_index: Dict[Tuple[int, int], int] = hodge["e2i"]  # type: ignore[assignment]
        curl: np.ndarray = hodge["fc"]  # type: ignore[assignment]
        i, j = min(home_idx, away_idx), max(home_idx, away_idx)
        edge_idx = edge_index.get((i, j))
        if edge_idx is not None:
            curl_value = float(curl[edge_idx])
            signal += curl_weight * (curl_value if home_idx == i else -curl_value)
    return signal


def outcome_index(outcome: str) -> int:
    return OUTCOMES.index(outcome)


def fit_calibrator(signals: Sequence[float], outcomes: Sequence[int]) -> Dict[str, object]:
    x = np.asarray(signals, dtype=float)
    y = np.asarray(outcomes, dtype=int)
    if len(x) < 50:
        return {"k": 0.5, "draw_intercept": -0.4, "draw_slope": 0.1, "n": int(len(x)), "nll": None}

    counts = np.bincount(y, minlength=3).astype(float) + 1.0
    base = counts / counts.sum()
    draw_intercept = math.log(max(base[1], 1e-6) / max(math.sqrt(base[0] * base[2]), 1e-6))
    initial = np.array([math.log(0.5), float(np.clip(draw_intercept, -3.0, 3.0)), math.log(0.1)])

    def objective(theta: np.ndarray) -> float:
        k = math.exp(float(theta[0]))
        d0 = float(theta[1])
        d1 = math.exp(float(theta[2]))
        logits = np.column_stack((k * x, d0 - d1 * np.abs(x), -k * x))
        log_probs = logits - logsumexp(logits, axis=1, keepdims=True)
        return float(-np.mean(log_probs[np.arange(len(y)), y]))

    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        bounds=((-7.0, 3.0), (-5.0, 5.0), (-7.0, 3.0)),
    )
    theta = result.x if result.success and np.all(np.isfinite(result.x)) else initial
    nll = objective(theta)
    return {
        "k": float(math.exp(float(theta[0]))),
        "draw_intercept": float(theta[1]),
        "draw_slope": float(math.exp(float(theta[2]))),
        "n": int(len(x)),
        "nll": float(nll),
        "base_rates": {OUTCOMES[i]: float((counts[i] - 1.0) / max(len(y), 1)) for i in range(3)},
    }


def predict_probabilities(signal: float, calibrator: Dict[str, object]) -> Dict[str, float]:
    k = float(calibrator["k"])
    draw_intercept = float(calibrator["draw_intercept"])
    draw_slope = float(calibrator["draw_slope"])
    logits = np.array([k * signal, draw_intercept - draw_slope * abs(signal), -k * signal], dtype=float)
    probs = np.exp(logits - logsumexp(logits))
    return {OUTCOMES[i]: float(probs[i]) for i in range(3)}


def select_bet(
    probabilities: Dict[str, float],
    odds: Dict[str, object],
    edge_threshold: float,
    min_ev: float,
) -> Optional[Dict[str, float | str]]:
    best: Optional[Dict[str, float | str]] = None
    for side in OUTCOMES:
        decimal_odds = float(odds[side])
        implied = 1.0 / decimal_odds
        probability = probabilities[side]
        edge = probability - implied
        ev = probability * decimal_odds - 1.0
        if edge < edge_threshold or ev < min_ev:
            continue
        if best is None or ev > float(best["ev"]):
            best = {
                "side": side,
                "probability": probability,
                "odds": decimal_odds,
                "implied": implied,
                "edge": edge,
                "ev": ev,
            }
    return best


def kelly_fraction(probability: float, decimal_odds: float) -> float:
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (probability * decimal_odds - 1.0) / b)


def new_strategy_state(initial_bankroll: float) -> Dict[str, object]:
    return {
        "bankroll": float(initial_bankroll),
        "peak_bankroll": float(initial_bankroll),
        "max_drawdown_pct": 0.0,
        "bets": [],
        "total_staked": 0.0,
        "profit": 0.0,
    }


def record_bet(
    state: Dict[str, object],
    match: Match,
    selection: Dict[str, float | str],
    stake_fraction: float,
    strategy_name: str,
    signal: float,
    probabilities: Dict[str, float],
) -> None:
    bankroll = float(state["bankroll"])
    stake = bankroll * stake_fraction
    if stake <= 0:
        return

    side = str(selection["side"])
    odds = float(selection["odds"])
    won = match.outcome == side
    profit = stake * (odds - 1.0) if won else -stake
    bankroll += profit

    state["bankroll"] = bankroll
    state["total_staked"] = float(state["total_staked"]) + stake
    state["profit"] = float(state["profit"]) + profit
    state["peak_bankroll"] = max(float(state["peak_bankroll"]), bankroll)
    peak = max(float(state["peak_bankroll"]), 1e-9)
    drawdown_pct = max(0.0, (peak - bankroll) / peak * 100.0)
    state["max_drawdown_pct"] = max(float(state["max_drawdown_pct"]), drawdown_pct)

    bets: List[Dict[str, object]] = state["bets"]  # type: ignore[assignment]
    bets.append(
        {
            "strategy": strategy_name,
            "season": match.season_label,
            "date": match.sort_date,
            "match": f"{match.away_team} @ {match.home_team}",
            "score": match.result_label,
            "actual": match.outcome,
            "side": side,
            "won": won,
            "odds": round(odds, 4),
            "probability": round(float(selection["probability"]), 5),
            "implied_probability": round(float(selection["implied"]), 5),
            "edge": round(float(selection["edge"]), 5),
            "ev": round(float(selection["ev"]), 5),
            "signal": round(signal, 5),
            "prob_home": round(probabilities["home"], 5),
            "prob_draw": round(probabilities["draw"], 5),
            "prob_away": round(probabilities["away"], 5),
            "stake": round(stake, 4),
            "profit": round(profit, 4),
            "bankroll": round(bankroll, 4),
        }
    )


def summarize_strategy(state: Dict[str, object], initial_bankroll: float) -> Dict[str, object]:
    bets: List[Dict[str, object]] = state["bets"]  # type: ignore[assignment]
    total_bets = len(bets)
    wins = sum(1 for bet in bets if bet["won"])
    bankroll = float(state["bankroll"])
    profit = bankroll - initial_bankroll
    total_staked = float(state["total_staked"])
    by_side = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0})
    by_season = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0})
    edge_values = []
    ev_values = []
    odds_values = []

    for bet in bets:
        side = str(bet["side"])
        season = str(bet["season"])
        by_side[side]["bets"] += 1
        by_side[side]["wins"] += int(bool(bet["won"]))
        by_side[side]["profit"] += float(bet["profit"])
        by_season[season]["bets"] += 1
        by_season[season]["wins"] += int(bool(bet["won"]))
        by_season[season]["profit"] += float(bet["profit"])
        edge_values.append(float(bet["edge"]))
        ev_values.append(float(bet["ev"]))
        odds_values.append(float(bet["odds"]))

    def clean_group(group: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        cleaned = {}
        for key, values in sorted(group.items()):
            bets_n = int(values["bets"])
            wins_n = int(values["wins"])
            cleaned[key] = {
                "bets": bets_n,
                "wins": wins_n,
                "win_pct": round(wins_n / bets_n * 100.0, 2) if bets_n else 0.0,
                "profit": round(float(values["profit"]), 2),
            }
        return cleaned

    return {
        "total_bets": total_bets,
        "wins": wins,
        "win_pct": round(wins / total_bets * 100.0, 2) if total_bets else 0.0,
        "initial_bankroll": round(initial_bankroll, 2),
        "final_bankroll": round(bankroll, 2),
        "profit": round(profit, 2),
        "roi_pct": round(profit / initial_bankroll * 100.0, 2) if initial_bankroll else 0.0,
        "total_staked": round(total_staked, 2),
        "yield_on_stake_pct": round(profit / total_staked * 100.0, 2) if total_staked else 0.0,
        "max_drawdown_pct": round(float(state["max_drawdown_pct"]), 2),
        "avg_edge": round(float(np.mean(edge_values)), 5) if edge_values else 0.0,
        "avg_ev": round(float(np.mean(ev_values)), 5) if ev_values else 0.0,
        "avg_odds": round(float(np.mean(odds_values)), 4) if odds_values else 0.0,
        "by_side": clean_group(by_side),
        "by_season": clean_group(by_season),
        "bets": bets,
    }


def market_coverage(matches: Sequence[Match]) -> Dict[str, Dict[str, object]]:
    coverage: Dict[str, Dict[str, object]] = {}
    for market in MARKET_COLUMNS:
        count = sum(1 for match in matches if market in match.odds)
        columns = sorted(
            {
                tuple(match.odds[market]["columns"])  # type: ignore[index]
                for match in matches
                if market in match.odds
            }
        )
        coverage[market] = {
            "matches": count,
            "coverage_pct": round(count / max(len(matches), 1) * 100.0, 2),
            "column_sets": [list(cols) for cols in columns],
        }
    return coverage


def collect_teams(games: Iterable[Match]) -> List[str]:
    teams = set()
    for game in games:
        teams.add(game.home_team)
        teams.add(game.away_team)
    return sorted(teams)


def run_backtest(args: argparse.Namespace) -> Dict[str, object]:
    season_specs = resolve_season_specs(args.season_codes)
    all_matches: List[Match] = []
    source_urls: Dict[str, str] = {}

    print("Downloading EPL sportsbook data from football-data.co.uk")
    for season_index, (label, code) in enumerate(season_specs):
        matches = download_season(label, code, season_index)
        source_urls[code] = f"https://www.football-data.co.uk/mmz4281/{code}/E0.csv"
        print(f"  {label}: {len(matches)} matches")
        all_matches.extend(matches)
        time.sleep(0.1)

    all_matches.sort(key=lambda match: (match.sort_date, match.season_index, match.match_index))
    if not all_matches:
        raise RuntimeError("No matches downloaded.")

    markets = {
        market: {
            "flat": new_strategy_state(args.initial_bankroll),
            "kelly": new_strategy_state(args.initial_bankroll),
        }
        for market in MARKET_COLUMNS
    }

    skipped_unknown_team = 0
    evaluated_matches = 0
    placed_events = 0
    last_progress_season = None
    latest_calibrator: Optional[Dict[str, object]] = None

    for match_index, match in enumerate(all_matches):
        if match_index < args.warmup_matches:
            continue

        window_start = max(0, match_index - args.training_window_matches)
        history = all_matches[window_start:match_index]
        if len(history) < 50:
            continue

        if last_progress_season != match.season_label:
            print(f"Backtesting {match.season_label} from {match.sort_date}...")
            last_progress_season = match.season_label

        teams = collect_teams(history)
        hodge = weighted_hodge(history, teams, margin_cap=args.margin_cap)
        signal = hodge_signal(hodge, match.home_team, match.away_team, curl_weight=args.curl_weight)
        if signal is None:
            skipped_unknown_team += 1
            continue

        calibration_signals: List[float] = []
        calibration_outcomes: List[int] = []
        for historical_match in history:
            historical_signal = hodge_signal(
                hodge,
                historical_match.home_team,
                historical_match.away_team,
                curl_weight=args.curl_weight,
            )
            if historical_signal is None:
                continue
            calibration_signals.append(historical_signal)
            calibration_outcomes.append(outcome_index(historical_match.outcome))
        latest_calibrator = fit_calibrator(calibration_signals, calibration_outcomes)
        probabilities = predict_probabilities(signal, latest_calibrator)
        evaluated_matches += 1

        event_had_bet = False
        for market, strategy_states in markets.items():
            odds = match.odds.get(market)
            if odds is None:
                continue
            selection = select_bet(probabilities, odds, edge_threshold=args.edge_threshold, min_ev=args.min_ev)
            if selection is None:
                continue

            record_bet(
                strategy_states["flat"],
                match,
                selection,
                args.flat_fraction,
                "flat",
                signal,
                probabilities,
            )

            raw_kelly = kelly_fraction(float(selection["probability"]), float(selection["odds"]))
            kelly_stake_fraction = min(args.max_kelly, args.kelly_multiplier * raw_kelly)
            if kelly_stake_fraction > 0.0001:
                record_bet(
                    strategy_states["kelly"],
                    match,
                    selection,
                    kelly_stake_fraction,
                    "kelly",
                    signal,
                    probabilities,
                )
            event_had_bet = True
        if event_had_bet:
            placed_events += 1

    output_markets = {
        market: {
            "flat": summarize_strategy(strategy_states["flat"], args.initial_bankroll),
            "kelly": summarize_strategy(strategy_states["kelly"], args.initial_bankroll),
        }
        for market, strategy_states in markets.items()
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "football-data.co.uk EPL CSV odds/results",
            "urls": source_urls,
            "markets": {
                "Pinnacle": "Pinnacle 1X2, closing columns when present",
                "Bet365": "Bet365 1X2, closing columns when present",
                "BestAvailable": "Max available 1X2 price across listed books, closing columns when present",
                "MarketAverage": "Average listed 1X2 price, closing columns when present",
            },
        },
        "config": {
            "season_codes": [code for _, code in season_specs],
            "warmup_matches": args.warmup_matches,
            "training_window_matches": args.training_window_matches,
            "margin_cap": args.margin_cap,
            "curl_weight": args.curl_weight,
            "edge_threshold": args.edge_threshold,
            "min_ev": args.min_ev,
            "flat_fraction": args.flat_fraction,
            "kelly_multiplier": args.kelly_multiplier,
            "max_kelly": args.max_kelly,
            "initial_bankroll": args.initial_bankroll,
            "draw_handling": "home/draw/away probabilities; non-winning 1X2 selections lose, including home/away selections on draws",
        },
        "coverage": {
            "total_matches": len(all_matches),
            "evaluated_matches": evaluated_matches,
            "events_with_any_bet": placed_events,
            "skipped_unknown_team": skipped_unknown_team,
            "first_match_date": all_matches[0].sort_date,
            "last_match_date": all_matches[-1].sort_date,
            "market_coverage": market_coverage(all_matches),
        },
        "latest_calibrator": latest_calibrator,
        "markets": output_markets,
    }


def write_json(path: str, payload: Dict[str, object]) -> str:
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return abs_path


def print_summary(payload: Dict[str, object]) -> None:
    coverage = payload["coverage"]  # type: ignore[index]
    print()
    print("EPL 10-season sportsbook backtest")
    print(f"  Matches downloaded: {coverage['total_matches']}")
    print(f"  Matches evaluated after warmup: {coverage['evaluated_matches']}")
    print(f"  Events with any bet: {coverage['events_with_any_bet']}")
    print()
    print(f"{'Market':<15} {'Strategy':<8} {'Bets':>5} {'Wins':>5} {'Win%':>7} {'Final$':>9} {'ROI':>8} {'Yield':>8} {'MaxDD':>8}")
    print("-" * 84)
    markets = payload["markets"]  # type: ignore[index]
    for market in MARKET_COLUMNS:
        for strategy in ("flat", "kelly"):
            summary = markets[market][strategy]
            print(
                f"{market:<15} {strategy:<8} "
                f"{summary['total_bets']:>5} {summary['wins']:>5} "
                f"{summary['win_pct']:>6.2f}% "
                f"{summary['final_bankroll']:>9.2f} "
                f"{summary['roi_pct']:>7.2f}% "
                f"{summary['yield_on_stake_pct']:>7.2f}% "
                f"{summary['max_drawdown_pct']:>7.2f}%"
            )


def main() -> None:
    args = parse_args()
    payload = run_backtest(args)
    output_path = write_json(args.output, payload)
    print_summary(payload)
    print()
    print(f"Saved artifact: {output_path}")


if __name__ == "__main__":
    main()
