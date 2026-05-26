"""
Sports Hodge Prediction Test (Corrected)
==========================================
Weighted Hodge decomposition on head-to-head game graphs,
with home-field correction, margin capping, and curl-aware prediction.

Tests: NFL, NBA, NHL, MLB, EPL, College Football.

Math fixes vs first version:
  1. Weighted least squares (w_e = number of games on edge)
  2. Home-field advantage removed before decomposition
  3. Margin capped to reduce blowout noise
  4. Variance ratios (squared norms) for decomposition percentages
  5. Curl-aware prediction (potential + matchup adjustment)
  6. Home advantage included in prediction formula
"""

import json
import urllib.request
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from datetime import date, timedelta
import sys
import os
import time


# ==========================================================================
# WEIGHTED HODGE DECOMPOSITION (corrected)
# ==========================================================================

def weighted_hodge(games, teams, margin_cap=None):
    """
    Weighted Hodge decomposition on the game-result graph.

    Implements Jiang et al. 2011 eq. 3.1:
      min_phi  sum_{(i,j) in E} w_ij * (Y_ij - phi_j + phi_i)^2

    Args:
        games: list of dicts with home_team, away_team, home_score, away_score
        teams: sorted list of team names
        margin_cap: cap |margin| at this value (None = no cap)

    Returns dict with potential, F_grad, F_curl, F_harm, edges, norms, etc.
    """
    n = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}

    # Estimate home-field advantage from all games
    home_margins = [g["home_score"] - g["away_score"] for g in games]
    hfa = np.mean(home_margins)

    # Accumulate venue-corrected, capped margins per matchup
    pair_margins = {}  # (i, j) with i<j -> list of corrected margins
    for g in games:
        hi = team_idx[g["home_team"]]
        ai = team_idx[g["away_team"]]
        raw_margin = g["home_score"] - g["away_score"]

        # Remove home-field advantage
        corrected = raw_margin - hfa

        # Cap margin
        if margin_cap is not None:
            corrected = np.clip(corrected, -margin_cap, margin_cap)

        i, j = min(hi, ai), max(hi, ai)
        sign = 1.0 if hi == i else -1.0  # orient so positive = i beat j
        if (i, j) not in pair_margins:
            pair_margins[(i, j)] = []
        pair_margins[(i, j)].append(sign * corrected)

    # Build edges, flows, and weights
    edges = sorted(pair_margins.keys())
    m = len(edges)
    edge_to_idx = {e: idx for idx, e in enumerate(edges)}

    F = np.zeros(m)       # average margin on each edge
    W = np.zeros(m)       # weight = number of games
    for idx, (i, j) in enumerate(edges):
        vals = pair_margins[(i, j)]
        F[idx] = np.mean(vals)
        W[idx] = len(vals)

    W_sqrt = np.sqrt(W)

    # B1: vertex-edge incidence (n x m)
    rows, cols, vals = [], [], []
    for idx, (i, j) in enumerate(edges):
        rows.extend([i, j])
        cols.extend([idx, idx])
        vals.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((vals, (rows, cols)), shape=(n, m))

    # WEIGHTED gradient solve: min sum w_e (F_e - (B1^T phi)_e)^2
    # Equivalent to: lsqr(diag(W_sqrt) @ B1^T, W_sqrt * F)
    W_diag = sp.diags(W_sqrt)
    potential = lsqr(W_diag @ B1.T, W_sqrt * F, atol=1e-12, btol=1e-12)[0]
    F_grad = B1.T @ potential

    F_residual = F - F_grad

    # Triangle enumeration
    adj = {i: set() for i in range(n)}
    for (i, j) in edges:
        adj[i].add(j)
        adj[j].add(i)

    triangles = []
    for i in range(n):
        for j in adj[i]:
            if j > i:
                for k in adj[i] & adj[j]:
                    if k > j:
                        triangles.append((i, j, k))

    # B2: edge-triangle incidence (m x t)
    if len(triangles) > 0:
        t = len(triangles)
        rows2, cols2, vals2 = [], [], []
        for tidx, (a, b, c) in enumerate(triangles):
            for e, s in [((a, b), 1.0), ((a, c), -1.0), ((b, c), 1.0)]:
                if e in edge_to_idx:
                    rows2.append(edge_to_idx[e])
                    cols2.append(tidx)
                    vals2.append(s)
        B2 = sp.csr_matrix((vals2, (rows2, cols2)), shape=(m, t))

        # WEIGHTED curl solve
        curl_coeffs = lsqr(W_diag @ B2, W_sqrt * F_residual,
                           atol=1e-12, btol=1e-12)[0]
        F_curl = B2 @ curl_coeffs
        F_harm = F_residual - F_curl
    else:
        F_curl = np.zeros(m)
        F_harm = F_residual

    # Variance ratios (squared norms sum to ||F||^2 due to orthogonality)
    var_total = np.sum(W * F**2)
    var_grad = np.sum(W * F_grad**2)
    var_curl = np.sum(W * F_curl**2)
    var_harm = np.sum(W * F_harm**2)

    # Verify orthogonality
    ortho_check = abs(var_grad + var_curl + var_harm - var_total) / max(var_total, 1e-10)

    return {
        "potential": potential,
        "F_grad": F_grad,
        "F_curl": F_curl,
        "F_harm": F_harm,
        "F": F,
        "W": W,
        "edges": edges,
        "edge_to_idx": edge_to_idx,
        "triangles": triangles,
        "hfa": hfa,
        "teams": teams,
        "team_idx": team_idx,
        "norms": {
            "total": float(np.sqrt(var_total)),
            "gradient": float(np.sqrt(var_grad)),
            "curl": float(np.sqrt(var_curl)),
            "harmonic": float(np.sqrt(var_harm)),
        },
        "variance_pct": {
            "gradient": float(var_grad / max(var_total, 1e-10) * 100),
            "curl": float(var_curl / max(var_total, 1e-10) * 100),
            "harmonic": float(var_harm / max(var_total, 1e-10) * 100),
        },
        "ortho_error": float(ortho_check),
        "n_teams": n,
        "n_edges": m,
        "n_triangles": len(triangles),
    }


def predict_game(hodge, home_team, away_team, use_curl=False, curl_weight=0.5):
    """
    Predict a single game using Hodge decomposition.

    Returns predicted home margin (positive = home wins).
    """
    phi = hodge["potential"]
    hfa = hodge["hfa"]
    ti = hodge["team_idx"]

    hi = ti.get(home_team)
    ai = ti.get(away_team)
    if hi is None or ai is None:
        return 0.0  # unknown team, no prediction

    # Base: venue-neutral strength diff + home advantage
    pred = (phi[ai] - phi[hi]) + hfa

    if use_curl:
        # Curl adjustment for this specific matchup
        e2i = hodge["edge_to_idx"]
        i, j = min(hi, ai), max(hi, ai)
        if (i, j) in e2i:
            eidx = e2i[(i, j)]
            curl_val = hodge["F_curl"][eidx]
            # curl_val positive means i tends to beat j beyond what hierarchy predicts
            # If home team is i: curl helps home
            # If home team is j: curl hurts home
            if hi == i:
                pred += curl_weight * curl_val
            else:
                pred -= curl_weight * curl_val

    return pred


def elo_ratings(games, teams, K=20, home_advantage=0):
    """Elo rating system with configurable home advantage."""
    ratings = {t: 1500.0 for t in teams}
    for g in sorted(games, key=lambda x: x.get("week", 0) * 10000 + x.get("day_idx", 0)):
        home, away = g["home_team"], g["away_team"]
        rh = ratings[home] + home_advantage
        ra = ratings[away]
        eh = 1.0 / (1.0 + 10 ** ((ra - rh) / 400))
        if g["home_score"] > g["away_score"]:
            sh = 1.0
        elif g["home_score"] < g["away_score"]:
            sh = 0.0
        else:
            sh = 0.5
        ratings[home] += K * (sh - eh)
        ratings[away] += K * ((1 - sh) - (1 - eh))
    return ratings


def evaluate_predictions(test_games, hodge, elo_dict, hfa_raw):
    """Evaluate multiple prediction methods on test games."""
    methods = {}
    for name in ["hodge", "hodge+curl", "elo", "elo+hfa", "home_always"]:
        methods[name] = {"correct": 0, "total": 0, "margins": [], "actuals": []}

    for g in test_games:
        hs, aws = g["home_score"], g["away_score"]
        if hs == aws:
            continue
        actual_home_wins = hs > aws
        actual_margin = hs - aws

        # Hodge (potential only)
        pred_margin = predict_game(hodge, g["home_team"], g["away_team"], use_curl=False)
        methods["hodge"]["total"] += 1
        methods["hodge"]["margins"].append(pred_margin)
        methods["hodge"]["actuals"].append(actual_margin)
        if (pred_margin > 0) == actual_home_wins:
            methods["hodge"]["correct"] += 1

        # Hodge + curl
        pred_curl = predict_game(hodge, g["home_team"], g["away_team"], use_curl=True)
        methods["hodge+curl"]["total"] += 1
        methods["hodge+curl"]["margins"].append(pred_curl)
        methods["hodge+curl"]["actuals"].append(actual_margin)
        if (pred_curl > 0) == actual_home_wins:
            methods["hodge+curl"]["correct"] += 1

        # Elo (no HFA)
        home_elo = elo_dict.get(g["home_team"], 1500)
        away_elo = elo_dict.get(g["away_team"], 1500)
        methods["elo"]["total"] += 1
        if (home_elo > away_elo) == actual_home_wins:
            methods["elo"]["correct"] += 1

        # Elo + HFA
        methods["elo+hfa"]["total"] += 1
        if (home_elo + hfa_raw * 10 > away_elo) == actual_home_wins:
            methods["elo+hfa"]["correct"] += 1

        # Home always
        methods["home_always"]["total"] += 1
        if actual_home_wins:
            methods["home_always"]["correct"] += 1

    # Compute margin prediction metrics for Hodge methods
    for name in ["hodge", "hodge+curl"]:
        m = methods[name]
        if m["margins"]:
            preds = np.array(m["margins"])
            acts = np.array(m["actuals"])
            m["mae"] = float(np.mean(np.abs(preds - acts)))
            m["rmse"] = float(np.sqrt(np.mean((preds - acts)**2)))
            corr = np.corrcoef(preds, acts)[0, 1] if len(preds) > 2 else 0
            m["correlation"] = float(corr)

    return methods


# ==========================================================================
# DATA FETCHERS
# ==========================================================================

def _espn_fetch(url, timeout=8):
    """Fetch JSON from ESPN API with retry."""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            if attempt == 0:
                time.sleep(0.3)
    return None


def _parse_espn_event(event):
    """Parse a single ESPN event into a game dict."""
    comps = event.get("competitions", [{}])
    if not comps:
        return None
    comp = comps[0]
    competitors = comp.get("competitors", [])
    if len(competitors) != 2:
        return None

    home = away = None
    for c in competitors:
        team_name = c.get("team", {}).get("displayName", "Unknown")
        score_str = c.get("score", "0")
        try:
            score = int(score_str)
        except (ValueError, TypeError):
            return None
        is_home = c.get("homeAway", "") == "home"
        entry = {"team": team_name, "score": score}
        if is_home:
            home = entry
        else:
            away = entry

    if home and away and (home["score"] + away["score"]) > 0:
        return {
            "home_team": home["team"],
            "home_score": home["score"],
            "away_team": away["team"],
            "away_score": away["score"],
        }
    return None


def fetch_nfl(year=2024):
    """Fetch NFL regular season games."""
    print(f"  Fetching NFL {year}...")
    games = []
    for week in range(1, 19):
        url = (f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
               f"scoreboard?dates={year}&seasontype=2&week={week}")
        data = _espn_fetch(url)
        if not data:
            continue
        week_games = 0
        for event in data.get("events", []):
            g = _parse_espn_event(event)
            if g:
                g["week"] = week
                games.append(g)
                week_games += 1
        if week % 6 == 0:
            print(f"    ...week {week}: {week_games} games (total: {len(games)})")
    print(f"    NFL total: {len(games)} games")
    return games


def fetch_daily_sport(sport, league, start_date, end_date, label, season_year=None):
    """Fetch games for a daily-schedule sport by iterating dates."""
    print(f"  Fetching {label}...")
    games = []
    d = start_date
    day_idx = 0
    while d <= end_date:
        ds = d.strftime("%Y%m%d")
        url = (f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/"
               f"scoreboard?dates={ds}")
        data = _espn_fetch(url, timeout=5)
        if data:
            for event in data.get("events", []):
                g = _parse_espn_event(event)
                if g:
                    g["day_idx"] = day_idx
                    # Approximate week from day index
                    g["week"] = day_idx // 7
                    games.append(g)
        day_idx += 1
        d += timedelta(days=1)
        if day_idx % 30 == 0:
            print(f"    ...day {day_idx}: {len(games)} games so far")
    print(f"    {label} total: {len(games)} games")
    return games


def fetch_nba(season_end_year=2025):
    return fetch_daily_sport(
        "basketball", "nba",
        date(2024, 10, 22), date(2025, 4, 13),
        f"NBA {season_end_year}"
    )


def fetch_nhl(season_end_year=2025):
    return fetch_daily_sport(
        "hockey", "nhl",
        date(2024, 10, 4), date(2025, 4, 17),
        f"NHL {season_end_year}"
    )


def fetch_mlb(year=2024):
    return fetch_daily_sport(
        "baseball", "mlb",
        date(2024, 3, 28), date(2024, 9, 29),
        f"MLB {year}"
    )


def fetch_epl(season_end_year=2025):
    return fetch_daily_sport(
        "soccer", "eng.1",
        date(2024, 8, 17), date(2025, 5, 25),
        f"EPL {season_end_year}"
    )


def fetch_college_football(year=2024):
    """Fetch college football (FBS) regular season."""
    print(f"  Fetching CFB {year}...")
    games = []
    for week in range(0, 16):
        url = (f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/"
               f"scoreboard?dates={year}&seasontype=2&week={week}&limit=500&groups=80")
        data = _espn_fetch(url)
        if not data:
            continue
        week_games = 0
        for event in data.get("events", []):
            g = _parse_espn_event(event)
            if g:
                g["week"] = week
                games.append(g)
                week_games += 1
        if week % 5 == 0:
            print(f"    ...week {week}: {week_games} games (total: {len(games)})")
    print(f"    CFB total: {len(games)} games")
    return games


# ==========================================================================
# ANALYSIS
# ==========================================================================

SPORT_CONFIG = {
    "NFL": {"margin_cap": 28, "elo_K": 20, "elo_hfa": 48, "split": 0.67},
    "NBA": {"margin_cap": 25, "elo_K": 15, "elo_hfa": 30, "split": 0.75},
    "NHL": {"margin_cap": 5,  "elo_K": 15, "elo_hfa": 20, "split": 0.75},
    "MLB": {"margin_cap": 8,  "elo_K": 8,  "elo_hfa": 15, "split": 0.75},
    "EPL": {"margin_cap": 4,  "elo_K": 20, "elo_hfa": 30, "split": 0.70},
    "CFB": {"margin_cap": 35, "elo_K": 15, "elo_hfa": 40, "split": 0.67},
}


def analyze_sport(sport_name, games, config):
    """Run full Hodge analysis for one sport."""
    if len(games) < 30:
        print(f"\n  {sport_name}: Only {len(games)} games, skipping.")
        return None

    teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))

    # Sort games chronologically
    games.sort(key=lambda g: g.get("week", 0) * 10000 + g.get("day_idx", 0))

    # Train/test split
    split_idx = int(len(games) * config["split"])
    train = games[:split_idx]
    test = games[split_idx:]

    print(f"\n{'='*70}")
    print(f"  {sport_name}")
    print(f"{'='*70}")
    print(f"  Teams: {len(teams)}, Games: {len(games)}")
    print(f"  Train: {len(train)}, Test: {len(test)}")

    # Hodge decomposition on training data
    train_teams = sorted(set([g["home_team"] for g in train] + [g["away_team"] for g in train]))
    hodge = weighted_hodge(train, train_teams, margin_cap=config["margin_cap"])

    print(f"\n  Hodge decomposition ({hodge['n_edges']} edges, {hodge['n_triangles']} triangles):")
    print(f"    Home-field advantage (estimated): {hodge['hfa']:.2f} points")
    vp = hodge["variance_pct"]
    print(f"    Gradient (hierarchy):  {vp['gradient']:5.1f}%  of variance")
    print(f"    Curl (matchups/RPS):   {vp['curl']:5.1f}%  of variance")
    print(f"    Harmonic (paradoxes):  {vp['harmonic']:5.1f}%  of variance")
    print(f"    Sum:                   {vp['gradient']+vp['curl']+vp['harmonic']:5.1f}%  (orthogonality error: {hodge['ortho_error']:.2e})")

    # Print top/bottom rankings
    phi = hodge["potential"]
    ranked = sorted(range(len(train_teams)), key=lambda i: phi[i])
    show_n = min(8, len(train_teams) // 4)
    print(f"\n  Top {show_n} (strongest):")
    for r in range(show_n):
        i = ranked[r]
        print(f"    {r+1:3d}. {train_teams[i]:35s}  phi={phi[i]:+8.3f}")
    print(f"  Bottom {show_n} (weakest):")
    for r in range(show_n):
        i = ranked[-(show_n - r)]
        print(f"    {len(train_teams) - show_n + r + 1:3d}. {train_teams[i]:35s}  phi={phi[i]:+8.3f}")

    # Elo baselines
    elo_plain = elo_ratings(train, train_teams, K=config["elo_K"], home_advantage=0)
    elo_hfa = elo_ratings(train, train_teams, K=config["elo_K"],
                          home_advantage=config["elo_hfa"])

    # Evaluate on test set
    results = evaluate_predictions(test, hodge, elo_hfa, hodge["hfa"])

    print(f"\n  --- Prediction Results ({len(test)} test games) ---")
    print(f"  {'Method':<20s} {'Acc':>7s} {'MAE':>8s} {'RMSE':>8s} {'Corr':>7s}")
    print(f"  {'-'*55}")

    for method_name in ["hodge", "hodge+curl", "elo+hfa", "elo", "home_always"]:
        r = results[method_name]
        acc = r["correct"] / max(r["total"], 1)
        mae = r.get("mae", "")
        rmse = r.get("rmse", "")
        corr = r.get("correlation", "")
        mae_s = f"{mae:8.2f}" if isinstance(mae, float) else f"{'':>8s}"
        rmse_s = f"{rmse:8.2f}" if isinstance(rmse, float) else f"{'':>8s}"
        corr_s = f"{corr:7.3f}" if isinstance(corr, float) else f"{'':>7s}"
        print(f"  {method_name:<20s} {acc:6.1%} {mae_s} {rmse_s} {corr_s}")

    # Betting viability
    breakeven = 0.524
    hodge_acc = results["hodge+curl"]["correct"] / max(results["hodge+curl"]["total"], 1)
    elo_acc = results["elo+hfa"]["correct"] / max(results["elo+hfa"]["total"], 1)
    edge = hodge_acc - breakeven

    print(f"\n  Betting edge (Hodge+curl vs {breakeven:.1%} breakeven): {edge:+.1%}")
    if edge > 0:
        roi = (hodge_acc * 1.909 - 1) * 100
        print(f"  Estimated ROI at -110: {roi:+.1f}%")
    print(f"  Hodge vs Elo+HFA: {hodge_acc - elo_acc:+.1%}")

    # Top curl matchups
    F_curl = hodge["F_curl"]
    edges_list = hodge["edges"]
    curl_ranked = sorted(range(len(edges_list)),
                         key=lambda idx: abs(F_curl[idx]), reverse=True)
    print(f"\n  Top 5 curl matchups (strongest rock-paper-scissors):")
    for r in range(min(5, len(curl_ranked))):
        idx = curl_ranked[r]
        i, j = edges_list[idx]
        c = F_curl[idx]
        upset_team = train_teams[i] if c > 0 else train_teams[j]
        other_team = train_teams[j] if c > 0 else train_teams[i]
        print(f"    {abs(c):.3f}  {upset_team} over {other_team}")

    return {
        "sport": sport_name,
        "n_teams": len(train_teams),
        "n_games_train": len(train),
        "n_games_test": len(test),
        "hfa": hodge["hfa"],
        "variance_pct": vp,
        "results": {k: {"accuracy": v["correct"]/max(v["total"],1), **v}
                   for k, v in results.items()},
    }


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    sport_arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    fetchers = {
        "NFL":  lambda: fetch_nfl(2024),
        "NBA":  lambda: fetch_nba(2025),
        "NHL":  lambda: fetch_nhl(2025),
        "MLB":  lambda: fetch_mlb(2024),
        "EPL":  lambda: fetch_epl(2025),
        "CFB":  lambda: fetch_college_football(2024),
    }

    if sport_arg != "all":
        sport_arg = sport_arg.upper()
        if sport_arg not in fetchers:
            print(f"Unknown sport: {sport_arg}. Options: {list(fetchers.keys())}")
            return
        fetchers = {sport_arg: fetchers[sport_arg]}

    all_results = {}

    for sport_name, fetcher in fetchers.items():
        try:
            games = fetcher()
            config = SPORT_CONFIG[sport_name]
            result = analyze_sport(sport_name, games, config)
            if result:
                all_results[sport_name] = result
        except Exception as e:
            print(f"\n  {sport_name}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    # Summary table
    if len(all_results) > 1:
        print(f"\n\n{'='*80}")
        print("CROSS-SPORT SUMMARY")
        print(f"{'='*80}")
        print(f"{'Sport':<8s} {'Teams':>5s} {'HFA':>6s} "
              f"{'Grad%':>6s} {'Curl%':>6s} {'Harm%':>6s} "
              f"{'Hodge':>7s} {'H+Curl':>7s} {'Elo':>7s} {'Home':>7s}")
        print("-" * 80)
        for sport, r in all_results.items():
            res = r["results"]
            vp = r["variance_pct"]
            print(f"{sport:<8s} {r['n_teams']:>5d} {r['hfa']:>+5.1f} "
                  f"{vp['gradient']:>5.1f}% {vp['curl']:>5.1f}% {vp['harmonic']:>5.1f}% "
                  f"{res['hodge']['accuracy']:>6.1%} "
                  f"{res['hodge+curl']['accuracy']:>6.1%} "
                  f"{res['elo+hfa']['accuracy']:>6.1%} "
                  f"{res['home_always']['accuracy']:>6.1%}")

        print(f"\nBreakeven at -110 vig: 52.4%")
        print(f"\nKey:")
        print(f"  Grad% = hierarchical (clear pecking order)")
        print(f"  Curl% = rock-paper-scissors matchups")
        print(f"  Harm% = unresolvable global paradoxes")
        print(f"  Lower Curl% = more predictable sport")

    # Save
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "site", "data", "sports_hodge_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    serializable = {}
    for k, v in all_results.items():
        sv = dict(v)
        for mk, mv in sv.get("results", {}).items():
            for field in ["margins", "actuals"]:
                if field in mv:
                    del mv[field]
        serializable[k] = sv

    with open(out_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
