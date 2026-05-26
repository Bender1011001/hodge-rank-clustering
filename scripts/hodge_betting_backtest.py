"""
Hodge Rank Betting Backtest
============================
Rolling Hodge decomposition vs market (Elo + standard vig) with $100 bankroll.

Tests whether Hodge's demonstrated edge over Elo survives the bookmaker's vig.
Uses calibrated logistic probability transform and selective betting.

This is a CONSERVATIVE test: real sportsbooks are sharper than Elo.
If Hodge can't beat Elo+vig, it can't beat real markets either.

Usage: python hodge_betting_backtest.py [SPORT] [--vig 0.045] [--threshold 0.05]
  SPORT: NHL | CFB | NFL | NBA | MLB | EPL | ALL  (default: ALL for CFB+NHL)
"""

import json, urllib.request, numpy as np, scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from datetime import date, timedelta
from collections import Counter
from scipy.optimize import minimize_scalar
import sys, os, time

# ======================================================================
# HODGE ENGINE (weighted, home-field corrected, margin capped)
# ======================================================================

def weighted_hodge(games, teams, margin_cap=None):
    n = len(teams)
    ti = {t: i for i, t in enumerate(teams)}
    hfa = np.mean([g["home_score"] - g["away_score"] for g in games]) if games else 0

    pair_margins = {}
    for g in games:
        hi, ai = ti[g["home_team"]], ti[g["away_team"]]
        corrected = g["home_score"] - g["away_score"] - hfa
        if margin_cap:
            corrected = np.clip(corrected, -margin_cap, margin_cap)
        i, j = min(hi, ai), max(hi, ai)
        sign = 1.0 if hi == i else -1.0
        pair_margins.setdefault((i, j), []).append(sign * corrected)

    edges = sorted(pair_margins.keys())
    m = len(edges)
    e2i = {e: idx for idx, e in enumerate(edges)}
    F = np.zeros(m)
    W = np.zeros(m)
    for idx, (i, j) in enumerate(edges):
        v = pair_margins[(i, j)]
        F[idx] = np.mean(v)
        W[idx] = len(v)

    Ws = np.sqrt(W)
    rows, cols, vals = [], [], []
    for idx, (i, j) in enumerate(edges):
        rows.extend([i, j]); cols.extend([idx, idx]); vals.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((vals, (rows, cols)), shape=(n, m))

    Wd = sp.diags(Ws)
    phi = lsqr(Wd @ B1.T, Ws * F, atol=1e-12, btol=1e-12)[0]
    Fg = B1.T @ phi
    Fr = F - Fg

    adj = {i: set() for i in range(n)}
    for (i, j) in edges:
        adj[i].add(j); adj[j].add(i)
    tris = []
    for i in range(n):
        for j in adj[i]:
            if j > i:
                for k in adj[i] & adj[j]:
                    if k > j:
                        tris.append((i, j, k))

    if tris:
        r2, c2, v2 = [], [], []
        for ti2, (a, b, c) in enumerate(tris):
            for e, s in [((a,b),1.0),((a,c),-1.0),((b,c),1.0)]:
                if e in e2i:
                    r2.append(e2i[e]); c2.append(ti2); v2.append(s)
        B2 = sp.csr_matrix((v2, (r2, c2)), shape=(m, len(tris)))
        cc = lsqr(Wd @ B2, Ws * Fr, atol=1e-12, btol=1e-12)[0]
        Fc = B2 @ cc
        Fh = Fr - Fc
    else:
        Fc = np.zeros(m); Fh = Fr

    vt = np.sum(W * F**2)
    vg = np.sum(W * Fg**2)
    vc = np.sum(W * Fc**2)
    vh = np.sum(W * Fh**2)

    return {
        "phi": phi, "Fg": Fg, "Fc": Fc, "Fh": Fh, "F": F, "W": W,
        "edges": edges, "e2i": e2i, "hfa": hfa, "teams": teams,
        "ti": ti, "n_tri": len(tris),
        "vpct": {"g": vg/max(vt,1e-10)*100, "c": vc/max(vt,1e-10)*100, "h": vh/max(vt,1e-10)*100},
    }


# ======================================================================
# ELO ENGINE
# ======================================================================

def elo_ratings(games, teams, K=20, hfa=0):
    r = {t: 1500.0 for t in teams}
    for g in sorted(games, key=lambda x: x.get("_ord", 0)):
        h, a = g["home_team"], g["away_team"]
        eh = 1.0 / (1.0 + 10 ** ((r[a] - r[h] - hfa) / 400))
        s = 1.0 if g["home_score"] > g["away_score"] else (0.0 if g["home_score"] < g["away_score"] else 0.5)
        r[h] += K * (s - eh); r[a] += K * ((1-s) - (1-eh))
    return r


# ======================================================================
# PROBABILITY CALIBRATION
# ======================================================================

def calibrate_logistic_scale(hodge, train_games):
    """Find the optimal logistic scale parameter k such that
    P(home_win) = 1 / (1 + exp(-k * pred)) best fits training data.
    pred = (phi[away] - phi[home]) + hfa  (positive = home advantage)
    """
    phi, hfa_h, ti = hodge["phi"], hodge["hfa"], hodge["ti"]

    preds, outcomes = [], []
    for g in train_games:
        hi, ai = ti.get(g["home_team"]), ti.get(g["away_team"])
        if hi is None or ai is None: continue
        if g["home_score"] == g["away_score"]: continue
        pred = (phi[ai] - phi[hi]) + hfa_h
        preds.append(pred)
        outcomes.append(1.0 if g["home_score"] > g["away_score"] else 0.0)

    if not preds:
        return 1.0

    preds = np.array(preds)
    outcomes = np.array(outcomes)

    # Negative log-likelihood
    def neg_ll(k):
        p = 1.0 / (1.0 + np.exp(-k * preds))
        p = np.clip(p, 1e-8, 1-1e-8)
        return -np.mean(outcomes * np.log(p) + (1-outcomes) * np.log(1-p))

    result = minimize_scalar(neg_ll, bounds=(0.01, 10.0), method='bounded')
    return result.x


def hodge_prob(phi, home_idx, away_idx, hfa, scale):
    """Hodge potential difference -> calibrated win probability."""
    diff = (phi[away_idx] - phi[home_idx]) + hfa
    return 1.0 / (1.0 + np.exp(-scale * diff))


def elo_prob(elo_home, elo_away, hfa_elo=0):
    """Standard Elo win probability for home team."""
    return 1.0 / (1.0 + 10 ** ((elo_away - elo_home - hfa_elo) / 400))


# ======================================================================
# BETTING ENGINE
# ======================================================================

def implied_odds(prob, overround=0.045):
    """Convert fair probability to decimal odds with bookmaker overround.
    Uses multiplicative model: implied_prob = fair_prob * (1 + overround).
    Decimal odds = 1 / implied_prob.
    """
    implied = prob * (1 + overround)
    if implied >= 1.0:
        return 1.01  # massive favorite, barely any return
    return 1.0 / implied


def kelly_fraction(p_model, decimal_odds):
    """Full Kelly criterion: f = (p*b - q) / b  where b = odds-1, q = 1-p.
    Returns fraction of bankroll to bet. Negative = don't bet.
    """
    b = decimal_odds - 1.0
    if b <= 0: return 0.0
    q = 1.0 - p_model
    f = (p_model * b - q) / b
    return max(0.0, f)


def simulate_bets(test_games, hodge, elo_dict, scale, cfg):
    """Simulate betting on test games. Returns bet history and final bankroll."""
    phi, hfa_h, ti = hodge["phi"], hodge["hfa"], hodge["ti"]
    overround = cfg.get("overround", 0.045)
    edge_threshold = cfg.get("edge_threshold", 0.05)
    flat_pct = cfg.get("flat_pct", 0.03)
    max_kelly = cfg.get("max_kelly", 0.05)
    elo_hfa = cfg.get("elo_hfa", 0)
    initial_bankroll = cfg.get("initial_bankroll", 100.0)

    bankroll_flat = initial_bankroll
    bankroll_kelly = initial_bankroll
    bankroll_all = initial_bankroll  # bet every game, no threshold

    bets_flat = []
    bets_kelly = []
    bets_all = []

    for g in test_games:
        hi = ti.get(g["home_team"])
        ai = ti.get(g["away_team"])
        if hi is None or ai is None: continue
        if g["home_score"] == g["away_score"]: continue

        home_won = g["home_score"] > g["away_score"]

        # Hodge probability for home team
        p_hodge = hodge_prob(phi, hi, ai, hfa_h, scale)

        # Market (Elo) probability for home team
        he = elo_dict.get(g["home_team"], 1500)
        ae = elo_dict.get(g["away_team"], 1500)
        p_market = elo_prob(he, ae, elo_hfa)

        # Market odds (with vig)
        odds_home = implied_odds(p_market, overround)
        odds_away = implied_odds(1.0 - p_market, overround)

        # Check edge for home side
        edge_home = p_hodge - p_market * (1 + overround)
        # Check edge for away side
        edge_away = (1 - p_hodge) - (1 - p_market) * (1 + overround)

        # Determine bet side
        bet_side = None
        p_model = None
        dec_odds = None

        if edge_home > edge_away and edge_home > 0:
            bet_side = "home"
            p_model = p_hodge
            dec_odds = odds_home
        elif edge_away > 0:
            bet_side = "away"
            p_model = 1 - p_hodge
            dec_odds = odds_away

        # --- All-in strategy (bet every game with any positive edge) ---
        if bet_side is not None:
            won = (bet_side == "home" and home_won) or (bet_side == "away" and not home_won)
            stake_all = bankroll_all * flat_pct
            if won:
                profit_all = stake_all * (dec_odds - 1)
            else:
                profit_all = -stake_all
            bankroll_all += profit_all
            bets_all.append({
                "game": f"{g['away_team']} @ {g['home_team']}",
                "side": bet_side, "won": won,
                "p_hodge": round(p_hodge, 3), "p_market": round(p_market, 3),
                "edge": round(max(edge_home, edge_away), 3),
                "odds": round(dec_odds, 3),
                "stake": round(stake_all, 2), "profit": round(profit_all, 2),
                "bankroll": round(bankroll_all, 2),
            })

        # --- Flat strategy (threshold edge) ---
        if bet_side is not None and max(edge_home, edge_away) >= edge_threshold:
            won = (bet_side == "home" and home_won) or (bet_side == "away" and not home_won)
            stake_flat = bankroll_flat * flat_pct
            if won:
                profit_flat = stake_flat * (dec_odds - 1)
            else:
                profit_flat = -stake_flat
            bankroll_flat += profit_flat
            bets_flat.append({
                "game": f"{g['away_team']} @ {g['home_team']}",
                "side": bet_side, "won": won,
                "p_hodge": round(p_hodge, 3), "p_market": round(p_market, 3),
                "edge": round(max(edge_home, edge_away), 3),
                "odds": round(dec_odds, 3),
                "stake": round(stake_flat, 2), "profit": round(profit_flat, 2),
                "bankroll": round(bankroll_flat, 2),
            })

        # --- Kelly strategy (threshold edge, Kelly sizing) ---
        if bet_side is not None and max(edge_home, edge_away) >= edge_threshold:
            won = (bet_side == "home" and home_won) or (bet_side == "away" and not home_won)
            kf = kelly_fraction(p_model, dec_odds)
            kf = min(kf, max_kelly)  # cap at max_kelly
            if kf > 0.001:
                stake_kelly = bankroll_kelly * kf
                if won:
                    profit_kelly = stake_kelly * (dec_odds - 1)
                else:
                    profit_kelly = -stake_kelly
                bankroll_kelly += profit_kelly
                bets_kelly.append({
                    "game": f"{g['away_team']} @ {g['home_team']}",
                    "side": bet_side, "won": won,
                    "kelly_frac": round(kf, 4),
                    "p_hodge": round(p_hodge, 3), "p_market": round(p_market, 3),
                    "edge": round(max(edge_home, edge_away), 3),
                    "odds": round(dec_odds, 3),
                    "stake": round(stake_kelly, 2), "profit": round(profit_kelly, 2),
                    "bankroll": round(bankroll_kelly, 2),
                })

    return {
        "flat": {"bankroll": bankroll_flat, "bets": bets_flat,
                 "n_bets": len(bets_flat),
                 "wins": sum(1 for b in bets_flat if b["won"]),
                 "roi": (bankroll_flat - initial_bankroll) / initial_bankroll},
        "kelly": {"bankroll": bankroll_kelly, "bets": bets_kelly,
                  "n_bets": len(bets_kelly),
                  "wins": sum(1 for b in bets_kelly if b["won"]),
                  "roi": (bankroll_kelly - initial_bankroll) / initial_bankroll},
        "all_positive_ev": {"bankroll": bankroll_all, "bets": bets_all,
                            "n_bets": len(bets_all),
                            "wins": sum(1 for b in bets_all if b["won"]),
                            "roi": (bankroll_all - initial_bankroll) / initial_bankroll},
    }


# ======================================================================
# FETCHERS (from 5-season script)
# ======================================================================

def _fetch(url, timeout=5):
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except: time.sleep(0.2)
    return None

def _parse(event):
    comps = event.get("competitions", [{}])
    if not comps: return None
    cs = comps[0].get("competitors", [])
    if len(cs) != 2: return None
    h = a = None
    for c in cs:
        nm = c.get("team", {}).get("displayName", "?")
        try: sc = int(c.get("score", 0))
        except: return None
        if c.get("homeAway") == "home": h = (nm, sc)
        else: a = (nm, sc)
    if h and a and (h[1]+a[1]) > 0:
        return {"home_team": h[0], "home_score": h[1], "away_team": a[0], "away_score": a[1]}
    return None

def fetch_weekly(sport, league, year, max_week=19, limit=100, groups=None):
    games = []
    for wk in range(0, max_week):
        url = (f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/"
               f"scoreboard?dates={year}&seasontype=2&week={wk}&limit={limit}")
        if groups: url += f"&groups={groups}"
        data = _fetch(url)
        if not data: continue
        for ev in data.get("events", []):
            g = _parse(ev)
            if g:
                g["_ord"] = wk * 1000
                g["_week"] = wk
                games.append(g)
    return games

def fetch_daily(sport, league, start, end):
    games = []
    d, idx = start, 0
    while d <= end:
        url = (f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/"
               f"scoreboard?dates={d.strftime('%Y%m%d')}")
        data = _fetch(url, timeout=4)
        if data:
            for ev in data.get("events", []):
                g = _parse(ev)
                if g:
                    g["_ord"] = idx
                    g["_day"] = d.isoformat()
                    games.append(g)
        idx += 1; d += timedelta(days=1)
    return games

def filter_games(games, min_gp):
    ct = Counter()
    for g in games:
        ct[g["home_team"]] += 1; ct[g["away_team"]] += 1
    valid = {t for t, c in ct.items() if c >= min_gp}
    return [g for g in games if g["home_team"] in valid and g["away_team"] in valid]


# ======================================================================
# SEASON CONFIGS
# ======================================================================

def nhl_seasons():
    configs = [
        (2021, date(2021,1,10), date(2021,5,20)),
        (2022, date(2021,10,8), date(2022,5,2)),
        (2023, date(2022,10,5), date(2023,4,18)),
        (2024, date(2023,10,8), date(2024,4,20)),
        (2025, date(2024,10,1), date(2025,4,20)),
    ]
    return [{"label": f"NHL {y}", "fetch": lambda s=s, e=e: fetch_daily("hockey", "nhl", s, e)}
            for y, s, e in configs]

def cfb_seasons():
    return [{"label": f"CFB {y}",
             "fetch": lambda y=y: fetch_weekly("football", "college-football", y, 16, 500, "80")}
            for y in [2020, 2021, 2022, 2023, 2024]]

def nfl_seasons():
    return [{"label": f"NFL {y}", "fetch": lambda y=y: fetch_weekly("football", "nfl", y, 19)}
            for y in [2020, 2021, 2022, 2023, 2024]]

def nba_seasons():
    configs = [
        (2021, date(2020,12,20), date(2021,5,20)),
        (2022, date(2021,10,15), date(2022,4,15)),
        (2023, date(2022,10,15), date(2023,4,15)),
        (2024, date(2023,10,20), date(2024,4,18)),
        (2025, date(2024,10,18), date(2025,4,18)),
    ]
    return [{"label": f"NBA {y}", "fetch": lambda s=s, e=e: fetch_daily("basketball", "nba", s, e)}
            for y, s, e in configs]

def mlb_seasons():
    configs = [
        (2020, date(2020,7,20), date(2020,9,30)),
        (2021, date(2021,3,28), date(2021,10,5)),
        (2022, date(2022,4,5), date(2022,10,8)),
        (2023, date(2023,3,28), date(2023,10,3)),
        (2024, date(2024,3,25), date(2024,10,2)),
    ]
    return [{"label": f"MLB {y}", "fetch": lambda s=s, e=e: fetch_daily("baseball", "mlb", s, e)}
            for y, s, e in configs]

def epl_seasons():
    configs = [
        (2021, date(2020,9,10), date(2021,5,25)),
        (2022, date(2021,8,10), date(2022,5,25)),
        (2023, date(2022,8,3), date(2023,5,30)),
        (2024, date(2023,8,8), date(2024,5,22)),
        (2025, date(2024,8,15), date(2025,5,28)),
    ]
    return [{"label": f"EPL {y}", "fetch": lambda s=s, e=e: fetch_daily("soccer", "eng.1", s, e)}
            for y, s, e in configs]


SPORTS = {
    "NHL": {"seasons": nhl_seasons, "cap": 5,  "elo_K": 15, "elo_hfa": 20,
            "split": 0.75, "min_gp": 40, "overround": 0.043},
    "CFB": {"seasons": cfb_seasons, "cap": 35, "elo_K": 15, "elo_hfa": 40,
            "split": 0.67, "min_gp": 6, "overround": 0.048},
    "NFL": {"seasons": nfl_seasons, "cap": 28, "elo_K": 20, "elo_hfa": 48,
            "split": 0.67, "min_gp": 10, "overround": 0.038},
    "NBA": {"seasons": nba_seasons, "cap": 25, "elo_K": 15, "elo_hfa": 30,
            "split": 0.75, "min_gp": 40, "overround": 0.040},
    "MLB": {"seasons": mlb_seasons, "cap": 8,  "elo_K": 8,  "elo_hfa": 15,
            "split": 0.75, "min_gp": 50, "overround": 0.038},
    "EPL": {"seasons": epl_seasons, "cap": 4,  "elo_K": 20, "elo_hfa": 30,
            "split": 0.70, "min_gp": 15, "overround": 0.042},
}


# ======================================================================
# MAIN BACKTEST
# ======================================================================

def run_backtest(sport_name, edge_threshold=0.05, flat_pct=0.03, max_kelly=0.05,
                 initial_bankroll=100.0, overround_override=None):
    cfg = SPORTS[sport_name]
    seasons = cfg["seasons"]()
    overround = overround_override or cfg["overround"]

    print(f"\n{'#'*70}")
    print(f"# {sport_name} BETTING BACKTEST ($100 bankroll)")
    print(f"# Overround: {overround:.1%}  |  Edge threshold: {edge_threshold:.1%}")
    print(f"# Flat bet: {flat_pct:.1%} of bankroll  |  Max Kelly: {max_kelly:.1%}")
    print(f"{'#'*70}")

    # Track cumulative bankroll across seasons
    cum_flat = initial_bankroll
    cum_kelly = initial_bankroll
    cum_all = initial_bankroll

    all_season_results = []
    total_bets_flat = 0
    total_wins_flat = 0
    total_bets_kelly = 0
    total_wins_kelly = 0
    total_bets_all = 0
    total_wins_all = 0

    for season in seasons:
        label = season["label"]
        print(f"\n  --- {label} ---")
        try:
            games = season["fetch"]()
        except Exception as e:
            print(f"    FETCH ERROR: {e}")
            continue

        games = filter_games(games, cfg["min_gp"])
        if len(games) < 30:
            print(f"    Only {len(games)} games, skipping")
            continue

        teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))
        games.sort(key=lambda g: g.get("_ord", 0))
        si = int(len(games) * cfg["split"])
        train, test = games[:si], games[si:]

        print(f"    {len(teams)} teams | {len(games)} games (train {len(train)}, test {len(test)})")

        # Train Hodge
        hodge = weighted_hodge(train, teams, margin_cap=cfg["cap"])
        print(f"    Hodge: {hodge['vpct']['g']:.1f}% grad, {hodge['vpct']['c']:.1f}% curl, "
              f"{hodge['vpct']['h']:.1f}% harm")

        # Calibrate logistic scale
        scale = calibrate_logistic_scale(hodge, train)
        print(f"    Calibrated logistic scale: k={scale:.3f}")

        # Train Elo
        elo = elo_ratings(train, teams, K=cfg["elo_K"], hfa=cfg["elo_hfa"])

        # Simulate betting (each season uses cumulative bankroll)
        bet_cfg = {
            "overround": overround,
            "edge_threshold": edge_threshold,
            "flat_pct": flat_pct,
            "max_kelly": max_kelly,
            "elo_hfa": cfg["elo_hfa"],
            "initial_bankroll": cum_flat,  # carry over from last season
        }
        # Need to run three separate simulations with different starting bankrolls
        # Flat
        bet_cfg["initial_bankroll"] = cum_flat
        results = simulate_bets(test, hodge, elo, scale, bet_cfg)
        cum_flat = results["flat"]["bankroll"]

        # Reset and run for Kelly
        bet_cfg["initial_bankroll"] = cum_kelly
        results_k = simulate_bets(test, hodge, elo, scale, bet_cfg)
        cum_kelly = results_k["kelly"]["bankroll"]

        # Reset and run for all-positive-EV
        bet_cfg["initial_bankroll"] = cum_all
        results_a = simulate_bets(test, hodge, elo, scale, bet_cfg)
        cum_all = results_a["all_positive_ev"]["bankroll"]

        # Stats
        nf = results["flat"]["n_bets"]
        wf = results["flat"]["wins"]
        nk = results_k["kelly"]["n_bets"]
        wk = results_k["kelly"]["wins"]
        na = results_a["all_positive_ev"]["n_bets"]
        wa = results_a["all_positive_ev"]["wins"]

        total_bets_flat += nf; total_wins_flat += wf
        total_bets_kelly += nk; total_wins_kelly += wk
        total_bets_all += na; total_wins_all += wa

        pct_f = wf/nf*100 if nf else 0
        pct_k = wk/nk*100 if nk else 0
        pct_a = wa/na*100 if na else 0

        # Average edge on bets taken
        avg_edge_f = np.mean([b["edge"] for b in results["flat"]["bets"]]) if results["flat"]["bets"] else 0
        avg_edge_a = np.mean([b["edge"] for b in results_a["all_positive_ev"]["bets"]]) if results_a["all_positive_ev"]["bets"] else 0

        print(f"    Flat 3%:  {nf:>3d} bets, {wf:>3d} wins ({pct_f:.1f}%), "
              f"bankroll ${cum_flat:.2f}, avg edge {avg_edge_f:.1%}")
        print(f"    Kelly:   {nk:>3d} bets, {wk:>3d} wins ({pct_k:.1f}%), "
              f"bankroll ${cum_kelly:.2f}")
        print(f"    Any +EV: {na:>3d} bets, {wa:>3d} wins ({pct_a:.1f}%), "
              f"bankroll ${cum_all:.2f}, avg edge {avg_edge_a:.1%}")

        all_season_results.append({
            "label": label,
            "flat": {"n": nf, "w": wf, "pct": pct_f, "bankroll": cum_flat},
            "kelly": {"n": nk, "w": wk, "pct": pct_k, "bankroll": cum_kelly},
            "all": {"n": na, "w": wa, "pct": pct_a, "bankroll": cum_all},
            "scale": scale,
        })

    # ===================== AGGREGATE RESULTS =====================
    print(f"\n  {'='*65}")
    print(f"  {sport_name} BETTING BACKTEST RESULTS (5 seasons, ${initial_bankroll:.0f} start)")
    print(f"  {'='*65}")

    print(f"\n  Strategy          Bets   Wins   Win%   Final $   ROI")
    print(f"  {'-'*60}")

    # Flat
    pf = total_wins_flat/total_bets_flat*100 if total_bets_flat else 0
    roi_f = (cum_flat - initial_bankroll) / initial_bankroll * 100
    print(f"  Flat 3%:         {total_bets_flat:>5d}  {total_wins_flat:>5d}  {pf:>5.1f}%  "
          f"${cum_flat:>8.2f}  {roi_f:>+7.1f}%")

    # Kelly
    pk = total_wins_kelly/total_bets_kelly*100 if total_bets_kelly else 0
    roi_k = (cum_kelly - initial_bankroll) / initial_bankroll * 100
    print(f"  Kelly (capped):  {total_bets_kelly:>5d}  {total_wins_kelly:>5d}  {pk:>5.1f}%  "
          f"${cum_kelly:>8.2f}  {roi_k:>+7.1f}%")

    # All +EV
    pa = total_wins_all/total_bets_all*100 if total_bets_all else 0
    roi_a = (cum_all - initial_bankroll) / initial_bankroll * 100
    print(f"  Any +EV (3%):    {total_bets_all:>5d}  {total_wins_all:>5d}  {pa:>5.1f}%  "
          f"${cum_all:>8.2f}  {roi_a:>+7.1f}%")

    print(f"\n  Break-even with {overround:.1%} vig = {0.5*(1+overround):.1%} win rate needed")
    print(f"  Market model: Elo (K={cfg['elo_K']}, HFA={cfg['elo_hfa']})")
    print(f"  NOTE: Real sportsbooks are sharper than Elo.")
    if roi_f > 0:
        print(f"  >>> Hodge shows +ROI vs Elo+vig -- promising but needs real odds verification")
    else:
        print(f"  >>> Hodge cannot beat Elo+vig -- unlikely to beat real markets")

    return {
        "sport": sport_name,
        "initial_bankroll": initial_bankroll,
        "overround": overround,
        "edge_threshold": edge_threshold,
        "flat": {"total_bets": total_bets_flat, "total_wins": total_wins_flat,
                 "win_pct": pf, "final_bankroll": cum_flat, "roi": roi_f},
        "kelly": {"total_bets": total_bets_kelly, "total_wins": total_wins_kelly,
                  "win_pct": pk, "final_bankroll": cum_kelly, "roi": roi_k},
        "all_positive_ev": {"total_bets": total_bets_all, "total_wins": total_wins_all,
                            "win_pct": pa, "final_bankroll": cum_all, "roi": roi_a},
        "seasons": all_season_results,
    }


# ======================================================================
# SENSITIVITY ANALYSIS
# ======================================================================

def sensitivity_sweep(sport_name, initial_bankroll=100.0):
    """Run backtest across different edge thresholds to find optimal."""
    print(f"\n{'='*70}")
    print(f"SENSITIVITY: {sport_name} -- Sweeping edge thresholds")
    print(f"{'='*70}")

    thresholds = [0.00, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15]
    results = []

    # First, fetch all data once
    cfg = SPORTS[sport_name]
    seasons = cfg["seasons"]()
    overround = cfg["overround"]

    all_season_data = []
    for season in seasons:
        label = season["label"]
        try:
            games = season["fetch"]()
        except:
            continue
        games = filter_games(games, cfg["min_gp"])
        if len(games) < 30: continue
        teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))
        games.sort(key=lambda g: g.get("_ord", 0))
        si = int(len(games) * cfg["split"])
        train, test = games[:si], games[si:]

        hodge = weighted_hodge(train, teams, margin_cap=cfg["cap"])
        scale = calibrate_logistic_scale(hodge, train)
        elo = elo_ratings(train, teams, K=cfg["elo_K"], hfa=cfg["elo_hfa"])

        all_season_data.append({
            "label": label, "test": test, "hodge": hodge,
            "elo": elo, "scale": scale,
        })

    print(f"\n  {'Threshold':>10s} {'Bets':>6s} {'Wins':>6s} {'Win%':>7s} {'Final$':>10s} {'ROI':>8s}")
    print(f"  {'-'*52}")

    for thr in thresholds:
        bankroll = initial_bankroll
        total_bets = 0
        total_wins = 0

        for sd in all_season_data:
            bet_cfg = {
                "overround": overround,
                "edge_threshold": thr,
                "flat_pct": 0.03,
                "max_kelly": 0.05,
                "elo_hfa": cfg["elo_hfa"],
                "initial_bankroll": bankroll,
            }
            r = simulate_bets(sd["test"], sd["hodge"], sd["elo"], sd["scale"], bet_cfg)
            bankroll = r["flat"]["bankroll"]
            total_bets += r["flat"]["n_bets"]
            total_wins += r["flat"]["wins"]

        wp = total_wins/total_bets*100 if total_bets else 0
        roi = (bankroll - initial_bankroll) / initial_bankroll * 100
        print(f"  {thr:>9.1%} {total_bets:>6d} {total_wins:>6d} {wp:>6.1f}% ${bankroll:>9.2f} {roi:>+7.1f}%")
        results.append({"threshold": thr, "bets": total_bets, "wins": total_wins,
                        "win_pct": wp, "bankroll": bankroll, "roi": roi})

    return results


# ======================================================================
# ENTRY POINT
# ======================================================================

def main():
    sport = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    edge_threshold = 0.05
    overround = None

    # Parse optional args
    for i, arg in enumerate(sys.argv):
        if arg == "--vig" and i+1 < len(sys.argv):
            overround = float(sys.argv[i+1])
        if arg == "--threshold" and i+1 < len(sys.argv):
            edge_threshold = float(sys.argv[i+1])

    all_results = {}

    if sport == "ALL":
        # Run the two best sports: CFB and NHL
        for s in ["CFB", "NHL"]:
            r = run_backtest(s, edge_threshold=edge_threshold,
                            overround_override=overround)
            if r: all_results[s] = r
    elif sport == "SWEEP":
        # Sensitivity analysis on CFB and NHL
        for s in ["CFB", "NHL"]:
            sensitivity_sweep(s)
        return
    elif sport in SPORTS:
        r = run_backtest(sport, edge_threshold=edge_threshold,
                        overround_override=overround)
        if r: all_results[sport] = r
    else:
        print(f"Unknown: {sport}. Options: {list(SPORTS.keys())} or ALL or SWEEP")
        return

    # Cross-sport summary
    if len(all_results) > 1:
        print(f"\n{'='*70}")
        print(f"CROSS-SPORT BETTING SUMMARY (5 seasons each, $100 start)")
        print(f"{'='*70}")

        print(f"\n  {'Sport':<8s} {'Bets':>6s} {'Wins':>6s} {'Win%':>7s} {'Final$':>10s} "
              f"{'ROI':>8s} {'Verdict'}")
        print(f"  {'-'*65}")

        for s, r in all_results.items():
            f = r["flat"]
            verdict = "PROFITABLE" if f["roi"] > 0 else "NOT PROFITABLE"
            print(f"  {s:<8s} {f['total_bets']:>6d} {f['total_wins']:>6d} "
                  f"{f['win_pct']:>6.1f}% ${f['final_bankroll']:>9.2f} "
                  f"{f['roi']:>+7.1f}% {verdict}")

    # Save
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "site", "data", f"hodge_betting_{sport.lower()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Make serializable
    def clean(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return obj

    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=clean)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
