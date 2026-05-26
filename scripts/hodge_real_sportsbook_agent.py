"""
Real-odds Hodge betting validator and bankroll agent.

The script downloads historical sportsbook closing odds from public archives,
replays games chronologically, trains only on games already completed before
each slate, and simulates a bankroll agent starting from $1,000 by default.

Data sources:
  * EPL: football-data.co.uk 1X2 closing odds.
  * NFL/NBA/NHL/MLB/CFB: SportsbookReviewsOnline historical moneyline archives.

The agent is deliberately constrained:
  * no future games are used for model fitting or calibration;
  * all bets on the same date are staked from the bankroll available before
    that date's games settle;
  * for EPL, draws are modeled as an explicit third outcome;
  * if an odds source is unavailable or malformed, the sport is marked with
    lower coverage instead of filling fake prices.

Usage:
    python scripts/hodge_real_sportsbook_agent.py
    python scripts/hodge_real_sportsbook_agent.py --sports NFL,NBA,NHL,MLB,CFB,EPL
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import scipy.sparse as sp
from bs4 import BeautifulSoup
from scipy.optimize import minimize, minimize_scalar
from scipy.sparse.linalg import lsqr
from scipy.special import logsumexp


SBR_ARCHIVE_BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives"
FOOTBALL_DATA_BASE = "https://www.football-data.co.uk/mmz4281"

EPL_SEASONS: Tuple[Tuple[str, str], ...] = (
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

SBR_SPORTS = {
    "NFL": {
        "archive": f"{SBR_ARCHIVE_BASE}/nfl/nfloddsarchives.htm",
        "slug_prefix": "nfl-odds-",
        "start_month": 8,
        "latest": 2021,
        "table_type": "spread_ml",
    },
    "NBA": {
        "archive": f"{SBR_ARCHIVE_BASE}/nba/nbaoddsarchives.htm",
        "slug_prefix": "nba-odds-",
        "start_month": 8,
        "latest": 2022,
        "table_type": "spread_ml",
    },
    "NHL": {
        "archive": f"{SBR_ARCHIVE_BASE}/nhl/nhloddsarchives.htm",
        "slug_prefix": "nhl-odds-",
        "start_month": 8,
        "latest": 2022,
        "table_type": "nhl_ml",
    },
    "CFB": {
        "archive": f"{SBR_ARCHIVE_BASE}/ncaafootball/ncaafootballoddsarchives.htm",
        "slug_prefix": "ncaa-football-",
        "start_month": 7,
        "latest": 2022,
        "table_type": "spread_ml",
    },
    "MLB": {
        "archive": f"{SBR_ARCHIVE_BASE}/mlb/mlboddsarchives.htm",
        "slug_prefix": "mlb-odds-",
        "start_month": 1,
        "latest": 2021,
        "table_type": "mlb_xlsx",
    },
}


@dataclass(frozen=True)
class RealOddsGame:
    sport: str
    season: str
    game_date: str
    sequence: int
    away_team: str
    home_team: str
    away_score: int
    home_score: int
    neutral: bool
    odds: Dict[str, float]
    source: str

    @property
    def outcome(self) -> str:
        if self.home_score > self.away_score:
            return "home"
        if self.away_score > self.home_score:
            return "away"
        return "draw"

    @property
    def margin(self) -> float:
        return float(self.home_score - self.away_score)

    @property
    def matchup(self) -> str:
        return f"{self.away_team} @ {self.home_team}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sports",
        default="NFL,NBA,NHL,MLB,CFB,EPL",
        help="Comma-separated sports from NFL,NBA,NHL,MLB,CFB,EPL.",
    )
    parser.add_argument("--seasons", type=int, default=10, help="Seasons per sport where available.")
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--training-window", type=int, default=760, help="Prior games used for each sport fit.")
    parser.add_argument("--warmup-games", type=int, default=300, help="Minimum prior games before a sport can bet.")
    parser.add_argument("--margin-cap", type=float, default=35.0, help="Default margin cap.")
    parser.add_argument("--edge-threshold", type=float, default=0.05, help="Minimum model probability edge over implied probability.")
    parser.add_argument("--min-ev", type=float, default=0.02, help="Minimum expected return per dollar staked.")
    parser.add_argument("--kelly-fraction", type=float, default=0.25, help="Fractional Kelly multiplier.")
    parser.add_argument("--max-bet-fraction", type=float, default=0.02, help="Max bankroll fraction per bet.")
    parser.add_argument("--max-day-exposure", type=float, default=0.12, help="Max bankroll fraction risked on one date.")
    parser.add_argument(
        "--output",
        default=os.path.join("site", "data", "hodge_real_sportsbook_agent.json"),
        help="Output JSON path.",
    )
    parser.add_argument("--keep-bets", type=int, default=2000, help="Maximum bet records stored in JSON.")
    return parser.parse_args()


def request_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def request_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def american_to_decimal(raw: object) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace("+", "")
    if not text or text.upper() in {"NL", "N/A", "PK", "PK'", "EV"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value == 0:
        return None
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def american_number(raw: object) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace("+", "")
    if not text or text.upper() in {"NL", "N/A", "PK", "PK'", "EV"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value == 0:
        return None
    return value


def valid_two_way_moneyline_pair(away_raw: object, home_raw: object) -> bool:
    away = american_number(away_raw)
    home = american_number(home_raw)
    if away is None or home is None:
        return False
    # Two positive American prices imply an arbitrage and usually indicate
    # SBR dropped a minus sign on one side. Skip instead of guessing.
    if away > 0 and home > 0:
        return False
    return True


def decimal_odds(raw: object) -> Optional[float]:
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 1.0:
        return None
    return value


def parse_score(raw: object) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_mmdd(raw: object, start_year: int, start_month: int) -> Optional[str]:
    text = str(raw).strip()
    if not text or not re.fullmatch(r"\d{3,4}", text):
        return None
    text = text.zfill(4)
    month = int(text[:2])
    day = int(text[2:])
    year = start_year if month >= start_month else start_year + 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def season_start_from_code(code: str) -> int:
    match = re.search(r"(\d{4})-(\d{2})", code)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{4})", code)
    if match:
        return int(match.group(1))
    raise ValueError(f"Cannot parse season start from {code}")


def discover_sbr_urls(sport: str, limit: int) -> List[Tuple[str, str]]:
    cfg = SBR_SPORTS[sport]
    html = request_text(cfg["archive"])
    links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    prefix = cfg["slug_prefix"]
    found: Dict[int, Tuple[str, str]] = {}
    for link in links:
        href = urljoin(cfg["archive"], link)
        if prefix not in href:
            continue
        if "preseason" in href.lower():
            continue
        match = re.search(r"(\d{4})(?:-(\d{2}))?(?:\.xlsx)?/?$", href)
        if not match:
            continue
        start = int(match.group(1))
        label = f"{sport} {start}-{str(start + 1)[-2:]}" if match.group(2) else f"{sport} {start}"
        found[start] = (label, href.rstrip("/"))

    if sport == "MLB":
        # MLB archive links are direct xlsx files and already carry one season per file.
        found = {start: (f"MLB {start}", url) for start, (label, url) in found.items()}

    selected = sorted(found.items(), reverse=True)[:limit]
    return [item for _, item in reversed(selected)]


def table_rows_from_html(url: str) -> List[Dict[str, str]]:
    html = request_text(url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"No odds table found at {url}")
    rows = table.find_all("tr")
    if not rows:
        return []
    headers = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
    output = []
    for row in rows[1:]:
        values = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(values) < 8:
            continue
        item: Dict[str, str] = {}
        for idx, value in enumerate(values):
            key = headers[idx] if idx < len(headers) else f"extra_{idx}"
            item[key] = value
        output.append(item)
    return output


def parse_sbr_html_sport(sport: str, label: str, url: str, start_year: int) -> List[RealOddsGame]:
    cfg = SBR_SPORTS[sport]
    rows = table_rows_from_html(url)
    games: List[RealOddsGame] = []
    pair: List[Dict[str, str]] = []
    for row in rows:
        if not row.get("Team"):
            continue
        pair.append(row)
        if len(pair) < 2:
            continue
        away_row, home_row = pair[0], pair[1]
        pair = []
        game_date = parse_mmdd(away_row.get("Date"), start_year, cfg["start_month"])
        if game_date is None:
            continue
        away_score = parse_score(away_row.get("Final"))
        home_score = parse_score(home_row.get("Final"))
        if away_score is None or home_score is None:
            continue
        if cfg["table_type"] == "nhl_ml":
            away_raw = away_row.get("Close")
            home_raw = home_row.get("Close")
        else:
            away_raw = away_row.get("ML")
            home_raw = home_row.get("ML")
        if not valid_two_way_moneyline_pair(away_raw, home_raw):
            continue
        away_odds = american_to_decimal(away_raw)
        home_odds = american_to_decimal(home_raw)
        if away_odds is None or home_odds is None:
            continue
        games.append(
            RealOddsGame(
                sport=sport,
                season=label,
                game_date=game_date,
                sequence=len(games),
                away_team=away_row["Team"].replace(" ", ""),
                home_team=home_row["Team"].replace(" ", ""),
                away_score=away_score,
                home_score=home_score,
                neutral=(away_row.get("VH") == "N" or home_row.get("VH") == "N"),
                odds={"away": away_odds, "home": home_odds},
                source=url,
            )
        )
    return games


def parse_mlb_xlsx(label: str, url: str, start_year: int) -> List[RealOddsGame]:
    raw = request_bytes(url)
    data = pd.read_excel(io.BytesIO(raw))
    games: List[RealOddsGame] = []
    pair: List[Dict[str, object]] = []
    for _, row_obj in data.iterrows():
        row = row_obj.to_dict()
        if not row.get("Team"):
            continue
        pair.append(row)
        if len(pair) < 2:
            continue
        away_row, home_row = pair[0], pair[1]
        pair = []
        game_date = parse_mmdd(away_row.get("Date"), start_year, 1)
        away_score = parse_score(away_row.get("Final"))
        home_score = parse_score(home_row.get("Final"))
        if not valid_two_way_moneyline_pair(away_row.get("Close"), home_row.get("Close")):
            continue
        away_odds = american_to_decimal(away_row.get("Close"))
        home_odds = american_to_decimal(home_row.get("Close"))
        if game_date is None or away_score is None or home_score is None or away_odds is None or home_odds is None:
            continue
        games.append(
            RealOddsGame(
                sport="MLB",
                season=label,
                game_date=game_date,
                sequence=len(games),
                away_team=str(away_row["Team"]).replace(" ", ""),
                home_team=str(home_row["Team"]).replace(" ", ""),
                away_score=away_score,
                home_score=home_score,
                neutral=False,
                odds={"away": away_odds, "home": home_odds},
                source=url,
            )
        )
    return games


EPL_NAME_MAP = {
    "Man City": "ManchesterCity",
    "Man United": "ManchesterUnited",
    "Nott'm Forest": "NottinghamForest",
    "Nottingham": "NottinghamForest",
    "Wolves": "Wolverhampton",
    "West Ham": "WestHam",
    "Newcastle": "Newcastle",
    "Tottenham": "Tottenham",
    "Leeds": "Leeds",
    "Leicester": "Leicester",
    "Norwich": "Norwich",
    "Brighton": "Brighton",
    "West Brom": "WestBrom",
    "Bournemouth": "Bournemouth",
    "Ipswich": "Ipswich",
    "Luton": "Luton",
}


def normalize_epl_team(name: str) -> str:
    return EPL_NAME_MAP.get(name, name).replace(" ", "").replace("&", "And")


def parse_epl_date(raw: str, season_index: int, row_index: int) -> str:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return f"19{season_index:02d}-{row_index:04d}"


def parse_epl_season(label: str, code: str, season_index: int) -> List[RealOddsGame]:
    url = f"{FOOTBALL_DATA_BASE}/{code}/E0.csv"
    text = request_text(url)
    reader = csv.DictReader(io.StringIO(text))
    games: List[RealOddsGame] = []
    for row_index, row in enumerate(reader):
        home = row.get("HomeTeam", "").strip()
        away = row.get("AwayTeam", "").strip()
        home_score = parse_score(row.get("FTHG"))
        away_score = parse_score(row.get("FTAG"))
        if not home or not away or home_score is None or away_score is None:
            continue
        odds_home = decimal_odds(row.get("PSCH") or row.get("PSH"))
        odds_draw = decimal_odds(row.get("PSCD") or row.get("PSD"))
        odds_away = decimal_odds(row.get("PSCA") or row.get("PSA"))
        if odds_home is None or odds_draw is None or odds_away is None:
            continue
        games.append(
            RealOddsGame(
                sport="EPL",
                season=label,
                game_date=parse_epl_date(row.get("Date", ""), season_index, row_index),
                sequence=len(games),
                away_team=normalize_epl_team(away),
                home_team=normalize_epl_team(home),
                away_score=away_score,
                home_score=home_score,
                neutral=False,
                odds={"home": odds_home, "draw": odds_draw, "away": odds_away},
                source=url,
            )
        )
    return games


def load_games(sports: Sequence[str], season_limit: int) -> Tuple[List[RealOddsGame], Dict[str, object]]:
    all_games: List[RealOddsGame] = []
    metadata: Dict[str, object] = {}

    for sport in sports:
        if sport == "EPL":
            selected = EPL_SEASONS[-season_limit:]
            sport_games: List[RealOddsGame] = []
            for idx, (label, code) in enumerate(selected):
                games = parse_epl_season(label, code, idx)
                print(f"  EPL {code}: {len(games)} matches")
                sport_games.extend(games)
                time.sleep(0.05)
            metadata[sport] = {"seasons": [code for _, code in selected], "games": len(sport_games), "source": "football-data.co.uk"}
            all_games.extend(sport_games)
            continue

        if sport not in SBR_SPORTS:
            metadata[sport] = {"error": "unsupported sport"}
            continue

        sport_games = []
        selected_urls = discover_sbr_urls(sport, season_limit)
        for label, url in selected_urls:
            start_year = season_start_from_code(url)
            if SBR_SPORTS[sport]["table_type"] == "mlb_xlsx":
                games = parse_mlb_xlsx(label, url, start_year)
            else:
                games = parse_sbr_html_sport(sport, label, url, start_year)
            print(f"  {label}: {len(games)} games")
            sport_games.extend(games)
            time.sleep(0.05)
        metadata[sport] = {
            "seasons": [label for label, _ in selected_urls],
            "games": len(sport_games),
            "source": "SportsbookReviewsOnline historical closing moneyline archive",
        }
        all_games.extend(sport_games)

    all_games.sort(key=lambda game: (game.game_date, game.sport, game.sequence))
    return all_games, metadata


def sport_margin_cap(sport: str, default_cap: float) -> float:
    return {
        "NFL": 28.0,
        "CFB": 35.0,
        "NBA": 25.0,
        "NHL": 5.0,
        "MLB": 8.0,
        "EPL": 4.0,
    }.get(sport, default_cap)


def weighted_hodge(games: Sequence[RealOddsGame], teams: Sequence[str], margin_cap: float) -> Dict[str, object]:
    team_index = {team: idx for idx, team in enumerate(teams)}
    n = len(teams)
    if not games or n == 0:
        return {"phi": np.zeros(n), "hfa": 0.0, "team_index": team_index, "edges": 0, "triangles": 0}

    non_neutral_margins = [game.margin for game in games if not game.neutral]
    hfa = float(np.mean(non_neutral_margins)) if non_neutral_margins else 0.0
    pair_margins: Dict[Tuple[int, int], List[float]] = defaultdict(list)
    for game in games:
        home_idx = team_index[game.home_team]
        away_idx = team_index[game.away_team]
        corrected = game.margin - (0.0 if game.neutral else hfa)
        corrected = float(np.clip(corrected, -margin_cap, margin_cap))
        i, j = min(home_idx, away_idx), max(home_idx, away_idx)
        sign = 1.0 if home_idx == i else -1.0
        pair_margins[(i, j)].append(sign * corrected)

    edges = sorted(pair_margins)
    m = len(edges)
    if m == 0:
        return {"phi": np.zeros(n), "hfa": hfa, "team_index": team_index, "edges": 0, "triangles": 0}

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
    phi = lsqr(weight_diag @ b1.T, np.sqrt(weights) * flow, atol=1e-10, btol=1e-10)[0]

    # Triangle count is diagnostic only. Avoid building B2 here because the
    # betting signal uses the gradient hierarchy and must be cheap to refit.
    adjacency = {i: set() for i in range(n)}
    for i, j in edges:
        adjacency[i].add(j)
        adjacency[j].add(i)
    triangles = 0
    for i in range(n):
        for j in adjacency[i]:
            if j <= i:
                continue
            triangles += sum(1 for k in adjacency[i] & adjacency[j] if k > j)

    return {"phi": phi, "hfa": hfa, "team_index": team_index, "edges": m, "triangles": triangles}


def hodge_signal(hodge: Dict[str, object], game: RealOddsGame) -> Optional[float]:
    team_index: Dict[str, int] = hodge["team_index"]  # type: ignore[assignment]
    home_idx = team_index.get(game.home_team)
    away_idx = team_index.get(game.away_team)
    if home_idx is None or away_idx is None:
        return None
    phi: np.ndarray = hodge["phi"]  # type: ignore[assignment]
    hfa = 0.0 if game.neutral else float(hodge["hfa"])
    return float(phi[away_idx] - phi[home_idx] + hfa)


def fit_binary_scale(signals: Sequence[float], outcomes: Sequence[int]) -> Dict[str, object]:
    x = np.asarray(signals, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if len(x) < 30 or len(set(y.tolist())) < 2:
        return {"type": "binary", "scale": 0.1, "n": int(len(x)), "nll": None}

    def objective(k: float) -> float:
        probs = 1.0 / (1.0 + np.exp(-k * x))
        probs = np.clip(probs, 1e-8, 1 - 1e-8)
        return float(-np.mean(y * np.log(probs) + (1.0 - y) * np.log(1.0 - probs)))

    result = minimize_scalar(objective, bounds=(0.001, 5.0), method="bounded")
    scale = float(result.x) if result.success else 0.1
    return {"type": "binary", "scale": scale, "n": int(len(x)), "nll": objective(scale)}


def fit_epl_calibrator(signals: Sequence[float], outcomes: Sequence[int]) -> Dict[str, object]:
    x = np.asarray(signals, dtype=float)
    y = np.asarray(outcomes, dtype=int)
    if len(x) < 50:
        return {"type": "three_way", "k": 0.5, "draw_intercept": -0.4, "draw_slope": 0.1, "n": int(len(x)), "nll": None}
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

    result = minimize(objective, initial, method="L-BFGS-B", bounds=((-7.0, 3.0), (-5.0, 5.0), (-7.0, 3.0)))
    theta = result.x if result.success else initial
    return {
        "type": "three_way",
        "k": float(math.exp(float(theta[0]))),
        "draw_intercept": float(theta[1]),
        "draw_slope": float(math.exp(float(theta[2]))),
        "n": int(len(x)),
        "nll": objective(theta),
    }


def probabilities_for_signal(signal: float, calibrator: Dict[str, object], sport: str) -> Dict[str, float]:
    if sport == "EPL":
        k = float(calibrator["k"])
        d0 = float(calibrator["draw_intercept"])
        d1 = float(calibrator["draw_slope"])
        logits = np.array([k * signal, d0 - d1 * abs(signal), -k * signal])
        probs = np.exp(logits - logsumexp(logits))
        return {"home": float(probs[0]), "draw": float(probs[1]), "away": float(probs[2])}
    scale = float(calibrator["scale"])
    home = float(1.0 / (1.0 + np.exp(-scale * signal)))
    return {"home": home, "away": 1.0 - home}


def outcome_index(game: RealOddsGame) -> Optional[int]:
    if game.sport == "EPL":
        return {"home": 0, "draw": 1, "away": 2}[game.outcome]
    if game.outcome == "draw":
        return None
    return 1 if game.outcome == "home" else 0


def teams_from_games(games: Iterable[RealOddsGame]) -> List[str]:
    teams = set()
    for game in games:
        teams.add(game.home_team)
        teams.add(game.away_team)
    return sorted(teams)


def fit_sport_model(sport: str, history: Sequence[RealOddsGame], args: argparse.Namespace) -> Optional[Dict[str, object]]:
    if len(history) < args.warmup_games:
        return None
    window = history[-args.training_window :]
    teams = teams_from_games(window)
    if len(teams) < 2:
        return None
    hodge = weighted_hodge(window, teams, margin_cap=sport_margin_cap(sport, args.margin_cap))
    signals: List[float] = []
    outcomes: List[int] = []
    for game in window:
        signal = hodge_signal(hodge, game)
        index = outcome_index(game)
        if signal is None or index is None:
            continue
        signals.append(signal)
        outcomes.append(index)
    calibrator = fit_epl_calibrator(signals, outcomes) if sport == "EPL" else fit_binary_scale(signals, outcomes)
    return {"hodge": hodge, "calibrator": calibrator, "history_games": len(window)}


def select_game_bet(game: RealOddsGame, model: Dict[str, object], args: argparse.Namespace) -> Optional[Dict[str, object]]:
    signal = hodge_signal(model["hodge"], game)  # type: ignore[arg-type]
    if signal is None:
        return None
    probabilities = probabilities_for_signal(signal, model["calibrator"], game.sport)  # type: ignore[arg-type]
    best: Optional[Dict[str, object]] = None
    for side, odds in game.odds.items():
        probability = probabilities.get(side)
        if probability is None:
            continue
        implied = 1.0 / odds
        edge = probability - implied
        ev = probability * odds - 1.0
        if edge < args.edge_threshold or ev < args.min_ev:
            continue
        kelly = max(0.0, ev / max(odds - 1.0, 1e-9))
        stake_fraction = min(args.max_bet_fraction, args.kelly_fraction * kelly)
        if stake_fraction <= 0:
            continue
        candidate = {
            "sport": game.sport,
            "date": game.game_date,
            "season": game.season,
            "matchup": game.matchup,
            "side": side,
            "odds": odds,
            "probability": probability,
            "implied_probability": implied,
            "edge": edge,
            "ev": ev,
            "stake_fraction": stake_fraction,
            "signal": signal,
            "probabilities": probabilities,
        }
        if best is None or ev > float(best["ev"]):
            best = candidate
    return best


def settle_day(bankroll: float, selections: Sequence[Tuple[RealOddsGame, Dict[str, object]]], max_day_exposure: float) -> Tuple[float, List[Dict[str, object]]]:
    if not selections:
        return bankroll, []
    requested = [bankroll * float(selection["stake_fraction"]) for _, selection in selections]
    max_total = bankroll * max_day_exposure
    total_requested = sum(requested)
    scale = min(1.0, max_total / total_requested) if total_requested > 0 else 0.0

    records = []
    for (game, selection), requested_stake in zip(selections, requested):
        stake = requested_stake * scale
        won = game.outcome == selection["side"]
        profit = stake * (float(selection["odds"]) - 1.0) if won else -stake
        bankroll += profit
        records.append(
            {
                "date": game.game_date,
                "sport": game.sport,
                "season": game.season,
                "matchup": game.matchup,
                "side": selection["side"],
                "actual": game.outcome,
                "won": won,
                "score": f"{game.away_score}-{game.home_score}",
                "odds": round(float(selection["odds"]), 4),
                "probability": round(float(selection["probability"]), 5),
                "implied_probability": round(float(selection["implied_probability"]), 5),
                "edge": round(float(selection["edge"]), 5),
                "ev": round(float(selection["ev"]), 5),
                "stake": round(stake, 4),
                "profit": round(profit, 4),
                "bankroll_after": round(bankroll, 4),
            }
        )
    return bankroll, records


def summarize_bets(records: Sequence[Dict[str, object]], initial_bankroll: float, final_bankroll: float) -> Dict[str, object]:
    wins = sum(1 for bet in records if bet["won"])
    total_staked = sum(float(bet["stake"]) for bet in records)
    profit = final_bankroll - initial_bankroll
    by_sport = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    by_year = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    by_side = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
    peak = initial_bankroll
    max_dd = 0.0

    for bet in records:
        sport = str(bet["sport"])
        year = str(bet["date"])[:4]
        side_key = f"{sport}:{bet['side']}"
        for group, key in ((by_sport, sport), (by_year, year), (by_side, side_key)):
            group[key]["bets"] += 1
            group[key]["wins"] += int(bool(bet["won"]))
            group[key]["profit"] += float(bet["profit"])
            group[key]["staked"] += float(bet["stake"])
        bank = float(bet["bankroll_after"])
        peak = max(peak, bank)
        max_dd = max(max_dd, (peak - bank) / max(peak, 1e-9) * 100.0)

    def clean(group: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, object]]:
        output: Dict[str, Dict[str, object]] = {}
        for key, row in sorted(group.items()):
            bets = int(row["bets"])
            output[key] = {
                "bets": bets,
                "wins": int(row["wins"]),
                "win_pct": round(row["wins"] / bets * 100.0, 2) if bets else 0.0,
                "profit": round(row["profit"], 2),
                "staked": round(row["staked"], 2),
                "yield_pct": round(row["profit"] / row["staked"] * 100.0, 2) if row["staked"] else 0.0,
            }
        return output

    return {
        "bets": len(records),
        "wins": wins,
        "win_pct": round(wins / len(records) * 100.0, 2) if records else 0.0,
        "initial_bankroll": round(initial_bankroll, 2),
        "final_bankroll": round(final_bankroll, 2),
        "profit": round(profit, 2),
        "roi_pct": round(profit / initial_bankroll * 100.0, 2) if initial_bankroll else 0.0,
        "total_staked": round(total_staked, 2),
        "yield_on_stake_pct": round(profit / total_staked * 100.0, 2) if total_staked else 0.0,
        "max_drawdown_pct": round(max_dd, 2),
        "by_sport": clean(by_sport),
        "by_year": clean(by_year),
        "by_side": clean(by_side),
    }


def run_agent(games: Sequence[RealOddsGame], args: argparse.Namespace) -> Dict[str, object]:
    by_sport_history: Dict[str, List[RealOddsGame]] = defaultdict(list)
    bankroll = args.initial_bankroll
    records: List[Dict[str, object]] = []
    skipped = defaultdict(int)

    by_date: Dict[str, List[RealOddsGame]] = defaultdict(list)
    for game in games:
        by_date[game.game_date].append(game)

    for game_date in sorted(by_date):
        slate = by_date[game_date]
        models: Dict[str, Optional[Dict[str, object]]] = {}
        day_selections: List[Tuple[RealOddsGame, Dict[str, object]]] = []

        for sport in sorted({game.sport for game in slate}):
            models[sport] = fit_sport_model(sport, by_sport_history[sport], args)

        for game in slate:
            model = models.get(game.sport)
            if model is None:
                skipped[f"{game.sport}:warmup"] += 1
                continue
            selection = select_game_bet(game, model, args)
            if selection is None:
                skipped[f"{game.sport}:no_edge"] += 1
                continue
            day_selections.append((game, selection))

        bankroll, day_records = settle_day(bankroll, day_selections, args.max_day_exposure)
        records.extend(day_records)

        for game in slate:
            by_sport_history[game.sport].append(game)

    return {
        "summary": summarize_bets(records, args.initial_bankroll, bankroll),
        "skipped": dict(sorted(skipped.items())),
        "bets": records[-args.keep_bets :] if args.keep_bets else records,
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
    print("Downloading real sportsbook odds/results:")
    games, source_metadata = load_games(sports, args.seasons)
    print(f"Loaded {len(games)} games across {len(set(game.sport for game in games))} sports.")
    agent = run_agent(games, args)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "sports": sports,
            "seasons_per_sport": args.seasons,
            "initial_bankroll": args.initial_bankroll,
            "training_window": args.training_window,
            "warmup_games": args.warmup_games,
            "edge_threshold": args.edge_threshold,
            "min_ev": args.min_ev,
            "kelly_fraction": args.kelly_fraction,
            "max_bet_fraction": args.max_bet_fraction,
            "max_day_exposure": args.max_day_exposure,
            "same_day_rule": "stakes are committed from start-of-date bankroll before that date's games settle",
            "markets": "moneyline for SBR US sports; 1X2 home/draw/away for EPL",
        },
        "sources": source_metadata,
        "coverage": {
            "games": len(games),
            "first_date": games[0].game_date if games else None,
            "last_date": games[-1].game_date if games else None,
            "games_by_sport": dict(sorted({sport: sum(1 for game in games if game.sport == sport) for sport in set(game.sport for game in games)}.items())),
        },
        "agent": agent,
    }
    out = write_json(args.output, payload)
    summary = agent["summary"]
    print()
    print("Real sportsbook bankroll agent")
    print(f"  Bets: {summary['bets']} | Wins: {summary['wins']} ({summary['win_pct']}%)")
    print(f"  Bankroll: ${summary['initial_bankroll']} -> ${summary['final_bankroll']} ({summary['roi_pct']}%)")
    print(f"  Yield on stake: {summary['yield_on_stake_pct']}% | Max drawdown: {summary['max_drawdown_pct']}%")
    print("  By sport:")
    for sport, row in summary["by_sport"].items():
        print(
            f"    {sport}: {row['bets']} bets, {row['wins']} wins ({row['win_pct']}%), "
            f"profit ${row['profit']}, yield {row['yield_pct']}%"
        )
    print(f"Saved artifact: {out}")


if __name__ == "__main__":
    main()
