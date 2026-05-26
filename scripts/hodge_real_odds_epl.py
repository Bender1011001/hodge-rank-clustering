"""
Hodge vs REAL Pinnacle Closing Odds (EPL)
==========================================
Downloads actual bookmaker odds from football-data.co.uk and tests whether
Hodge decomposition can identify value bets against Pinnacle closing lines.

This is the HONEST test: Pinnacle is the sharpest bookmaker in the world.
If Hodge can beat Pinnacle closing odds, it's genuinely remarkable.
If it can't, the Elo-based backtest numbers are optimistic.

Usage: python hodge_real_odds_epl.py
"""

import csv, io, json, urllib.request, numpy as np, scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from scipy.optimize import minimize_scalar
from datetime import date, timedelta
from collections import Counter
import os, time

# ======================================================================
# HODGE ENGINE (same as betting backtest)
# ======================================================================

def weighted_hodge(games, teams, margin_cap=4):
    n = len(teams)
    ti = {t: i for i, t in enumerate(teams)}
    hfa = np.mean([g["home_score"] - g["away_score"] for g in games]) if games else 0

    pair_margins = {}
    for g in games:
        hi, ai = ti[g["home_team"]], ti[g["away_team"]]
        corrected = g["home_score"] - g["away_score"] - hfa
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

    return {"phi": phi, "hfa": hfa, "ti": ti, "teams": teams}


def calibrate_logistic_scale(hodge, train_games):
    phi, hfa_h, ti = hodge["phi"], hodge["hfa"], hodge["ti"]
    preds, outcomes = [], []
    for g in train_games:
        hi, ai = ti.get(g["home_team"]), ti.get(g["away_team"])
        if hi is None or ai is None: continue
        if g["home_score"] == g["away_score"]: continue
        pred = (phi[ai] - phi[hi]) + hfa_h
        preds.append(pred)
        outcomes.append(1.0 if g["home_score"] > g["away_score"] else 0.0)
    if not preds: return 1.0
    preds = np.array(preds)
    outcomes = np.array(outcomes)
    def neg_ll(k):
        p = 1.0 / (1.0 + np.exp(-k * preds))
        p = np.clip(p, 1e-8, 1-1e-8)
        return -np.mean(outcomes * np.log(p) + (1-outcomes) * np.log(1-p))
    result = minimize_scalar(neg_ll, bounds=(0.01, 10.0), method='bounded')
    return result.x


def hodge_prob(phi, home_idx, away_idx, hfa, scale):
    diff = (phi[away_idx] - phi[home_idx]) + hfa
    return 1.0 / (1.0 + np.exp(-scale * diff))


# ======================================================================
# DOWNLOAD REAL ODDS FROM FOOTBALL-DATA.CO.UK
# ======================================================================

# Team name mapping: football-data.co.uk uses different names than ESPN
NAME_MAP = {
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    "Nottingham": "Nottingham Forest",
    "Wolves": "Wolverhampton Wanderers",
    "Sheffield United": "Sheffield United",
    "Sheffield Utd": "Sheffield United",
    "West Ham": "West Ham United",
    "Newcastle": "Newcastle United",
    "Tottenham": "Tottenham Hotspur",
    "Leeds": "Leeds United",
    "Leicester": "Leicester City",
    "Norwich": "Norwich City",
    "Brighton": "Brighton & Hove Albion",
    "West Brom": "West Bromwich Albion",
    "Bournemouth": "AFC Bournemouth",
    "Ipswich": "Ipswich Town",
    "Luton": "Luton Town",
}

def normalize_team(name):
    """Map football-data.co.uk team name to ESPN display name."""
    return NAME_MAP.get(name, name)


def download_epl_odds(season_code):
    """Download EPL odds CSV from football-data.co.uk.
    season_code: e.g. '2324' for 2023-24, '2425' for 2024-25
    """
    url = f"https://www.football-data.co.uk/mmz4281/{season_code}/E0.csv"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    Failed to download {url}: {e}")
        return []

    reader = csv.DictReader(io.StringIO(raw))
    games = []
    for row in reader:
        try:
            ht = normalize_team(row.get("HomeTeam", ""))
            at = normalize_team(row.get("AwayTeam", ""))
            hg = int(row.get("FTHG", 0))
            ag = int(row.get("FTAG", 0))

            # Pinnacle odds (sharpest book)
            psh = float(row.get("PSH", 0))
            psd = float(row.get("PSD", 0))
            psa = float(row.get("PSA", 0))

            # Max odds (best available across all books)
            maxh = float(row.get("MaxH", 0) or 0)
            maxd = float(row.get("MaxD", 0) or 0)
            maxa = float(row.get("MaxA", 0) or 0)

            # Bet365 odds
            b365h = float(row.get("B365H", 0) or 0)
            b365d = float(row.get("B365D", 0) or 0)
            b365a = float(row.get("B365A", 0) or 0)

            if psh <= 0 or psa <= 0: continue

            # Parse date
            date_str = row.get("Date", "")

            games.append({
                "home_team": ht, "away_team": at,
                "home_score": hg, "away_score": ag,
                "date": date_str,
                "pinnacle_home": psh, "pinnacle_draw": psd, "pinnacle_away": psa,
                "max_home": maxh, "max_draw": maxd, "max_away": maxa,
                "b365_home": b365h, "b365_draw": b365d, "b365_away": b365a,
                "_ord": len(games),
            })
        except (ValueError, KeyError):
            continue

    return games


# ======================================================================
# BETTING SIMULATION WITH REAL ODDS
# ======================================================================

def run_real_odds_backtest(games, label, split=0.70, edge_threshold=0.03):
    """Run Hodge backtest against actual Pinnacle closing odds."""
    if len(games) < 30:
        print(f"  {label}: only {len(games)} games, skipping")
        return None

    teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))
    si = int(len(games) * split)
    train, test = games[:si], games[si:]

    # Train Hodge
    hodge = weighted_hodge(train, teams, margin_cap=4)
    scale = calibrate_logistic_scale(hodge, train)
    phi, hfa_h, ti = hodge["phi"], hodge["hfa"], hodge["ti"]

    print(f"  {label}: {len(teams)} teams, {len(games)} games "
          f"(train {len(train)}, test {len(test)}), scale={scale:.3f}")

    # Track betting against multiple bookmaker price sources
    results = {}
    for odds_source, oh_key, oa_key in [
        ("Pinnacle", "pinnacle_home", "pinnacle_away"),
        ("Max", "max_home", "max_away"),
        ("Bet365", "b365_home", "b365_away"),
    ]:
        bankroll = 100.0
        bets = []

        for g in test:
            hi = ti.get(g["home_team"])
            ai = ti.get(g["away_team"])
            if hi is None or ai is None: continue

            # Skip draws (can't bet on them with our model)
            if g["home_score"] == g["away_score"]: continue
            home_won = g["home_score"] > g["away_score"]

            # Hodge win probability
            p_hodge_home = hodge_prob(phi, hi, ai, hfa_h, scale)
            p_hodge_away = 1.0 - p_hodge_home

            # Real bookmaker decimal odds
            odds_h = g.get(oh_key, 0)
            odds_a = g.get(oa_key, 0)
            if odds_h <= 1.0 or odds_a <= 1.0: continue

            # Implied probabilities from bookmaker odds
            imp_h = 1.0 / odds_h
            imp_a = 1.0 / odds_a
            # Note: imp_h + imp_d + imp_a > 1 (the overround)

            # Expected value: EV = p_model * payout - (1-p_model) * stake
            # For home bet: EV = p_hodge_home * (odds_h - 1) - (1 - p_hodge_home)
            #             = p_hodge_home * odds_h - 1
            ev_home = p_hodge_home * odds_h - 1.0
            ev_away = p_hodge_away * odds_a - 1.0

            # Hodge edge = how much Hodge disagrees with the market price
            edge_home = p_hodge_home - imp_h  # positive = Hodge thinks home is underpriced
            edge_away = p_hodge_away - imp_a

            # Bet on the side with highest positive EV
            bet_side = None
            ev = 0
            odds = 0
            edge = 0

            if ev_home > ev_away and ev_home > 0 and edge_home >= edge_threshold:
                bet_side = "home"
                ev = ev_home
                odds = odds_h
                edge = edge_home
            elif ev_away > 0 and edge_away >= edge_threshold:
                bet_side = "away"
                ev = ev_away
                odds = odds_a
                edge = edge_away

            if bet_side is not None:
                won = (bet_side == "home" and home_won) or (bet_side == "away" and not home_won)
                stake = bankroll * 0.03  # 3% flat
                if won:
                    profit = stake * (odds - 1.0)
                else:
                    profit = -stake
                bankroll += profit

                bets.append({
                    "game": f"{g['away_team']} @ {g['home_team']}",
                    "side": bet_side, "won": won,
                    "p_hodge": round(p_hodge_home if bet_side=="home" else p_hodge_away, 3),
                    "implied": round(imp_h if bet_side=="home" else imp_a, 3),
                    "edge": round(edge, 3),
                    "odds": round(odds, 3), "ev": round(ev, 3),
                    "profit": round(profit, 2),
                    "bankroll": round(bankroll, 2),
                })

        n_bets = len(bets)
        wins = sum(1 for b in bets if b["won"])
        wp = wins/n_bets*100 if n_bets else 0
        roi = (bankroll - 100.0) / 100.0 * 100

        results[odds_source] = {
            "n_bets": n_bets, "wins": wins, "win_pct": wp,
            "bankroll": bankroll, "roi": roi, "bets": bets,
        }

    return results


# ======================================================================
# ALSO RUN AGAINST ELO FOR COMPARISON
# ======================================================================

def run_elo_comparison(games, label, split=0.70, edge_threshold=0.03, overround=0.042):
    """Run the same backtest but with Elo as market for comparison."""
    from scripts.hodge_betting_backtest import elo_ratings, elo_prob

    if len(games) < 30: return None

    teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))
    si = int(len(games) * split)
    train, test = games[:si], games[si:]

    hodge = weighted_hodge(train, teams, margin_cap=4)
    scale = calibrate_logistic_scale(hodge, train)
    phi, hfa_h, ti = hodge["phi"], hodge["hfa"], hodge["ti"]

    elo = elo_ratings(train, teams, K=20, hfa=30)

    bankroll = 100.0
    bets = []

    for g in test:
        hi = ti.get(g["home_team"])
        ai = ti.get(g["away_team"])
        if hi is None or ai is None: continue
        if g["home_score"] == g["away_score"]: continue

        home_won = g["home_score"] > g["away_score"]
        p_hodge_home = hodge_prob(phi, hi, ai, hfa_h, scale)

        he = elo.get(g["home_team"], 1500)
        ae = elo.get(g["away_team"], 1500)
        p_mkt = elo_prob(he, ae, 30)

        imp_h = p_mkt * (1 + overround)
        imp_a = (1 - p_mkt) * (1 + overround)
        odds_h = 1.0 / imp_h if imp_h < 1 else 1.01
        odds_a = 1.0 / imp_a if imp_a < 1 else 1.01

        ev_home = p_hodge_home * odds_h - 1.0
        ev_away = (1 - p_hodge_home) * odds_a - 1.0
        edge_home = p_hodge_home - imp_h
        edge_away = (1 - p_hodge_home) - imp_a

        bet_side = None
        if ev_home > ev_away and ev_home > 0 and edge_home >= edge_threshold:
            bet_side = "home"
            odds = odds_h; edge = edge_home
        elif ev_away > 0 and edge_away >= edge_threshold:
            bet_side = "away"
            odds = odds_a; edge = edge_away

        if bet_side:
            won = (bet_side == "home" and home_won) or (bet_side == "away" and not home_won)
            stake = bankroll * 0.03
            profit = stake * (odds - 1.0) if won else -stake
            bankroll += profit
            bets.append({"won": won})

    n = len(bets)
    w = sum(1 for b in bets if b["won"])
    return {"n_bets": n, "wins": w, "win_pct": w/n*100 if n else 0,
            "bankroll": bankroll, "roi": (bankroll-100)/100*100}


# ======================================================================
# MAIN
# ======================================================================

def main():
    season_configs = [
        ("EPL 2021", "2021"),
        ("EPL 2022", "2122"),
        ("EPL 2023", "2223"),
        ("EPL 2024", "2324"),
        ("EPL 2025", "2425"),
    ]

    print("="*70)
    print("HODGE vs REAL PINNACLE CLOSING ODDS (EPL, 5 seasons)")
    print("="*70)
    print("\nDownloading actual bookmaker odds from football-data.co.uk...")
    print("Pinnacle = sharpest book. If Hodge beats Pinnacle, it's real.")
    print()

    all_results = {}
    cum_bankroll = {"Pinnacle": 100.0, "Max": 100.0, "Bet365": 100.0}
    cum_bets = {"Pinnacle": 0, "Max": 0, "Bet365": 0}
    cum_wins = {"Pinnacle": 0, "Max": 0, "Bet365": 0}

    for label, code in season_configs:
        print(f"\n--- {label} ---")
        games = download_epl_odds(code)
        if not games:
            print(f"  No data for {label}")
            continue

        print(f"  Downloaded {len(games)} games with odds")

        results = run_real_odds_backtest(games, label, split=0.70, edge_threshold=0.03)
        if not results: continue

        for source in ["Pinnacle", "Max", "Bet365"]:
            r = results.get(source, {})
            n = r.get("n_bets", 0)
            w = r.get("wins", 0)

            # Update cumulative (scale the season's result by the cumulative bankroll)
            if n > 0:
                # Replay this season's bets starting from cumulative bankroll
                bankroll = cum_bankroll[source]
                for bet in r.get("bets", []):
                    stake = bankroll * 0.03
                    if bet["won"]:
                        bankroll += stake * (bet["odds"] - 1.0)
                    else:
                        bankroll -= stake
                cum_bankroll[source] = bankroll
                cum_bets[source] += n
                cum_wins[source] += w

            wp = w/n*100 if n else 0
            season_roi = r.get("roi", 0)
            print(f"    vs {source:>8s}: {n:>3d} bets, {w:>3d} wins ({wp:.1f}%), "
                  f"season $100->${r.get('bankroll',100):.2f} ({season_roi:+.1f}%)")

        all_results[label] = results

    # ==================== AGGREGATE ====================
    print(f"\n{'='*70}")
    print(f"AGGREGATE: 5 EPL SEASONS, $100 CUMULATIVE BANKROLL")
    print(f"{'='*70}")
    print(f"\n  {'Market':>10s} {'Bets':>6s} {'Wins':>6s} {'Win%':>7s} {'Final$':>10s} {'ROI':>8s}")
    print(f"  {'-'*50}")

    for source in ["Pinnacle", "Max", "Bet365"]:
        n = cum_bets[source]
        w = cum_wins[source]
        wp = w/n*100 if n else 0
        bank = cum_bankroll[source]
        roi = (bank - 100) / 100 * 100
        verdict = "PROFIT" if roi > 0 else "LOSS"
        print(f"  {source:>10s} {n:>6d} {w:>6d} {wp:>6.1f}% ${bank:>9.2f} {roi:>+7.1f}% {verdict}")

    print(f"\n  For comparison, the Elo-based backtest showed EPL at +233.6% ROI")
    print(f"  The difference shows how much harder real books are than Elo")

    # Honest assessment
    pin_roi = (cum_bankroll["Pinnacle"] - 100) / 100 * 100
    if pin_roi > 0:
        print(f"\n  >>> HODGE BEATS PINNACLE: {pin_roi:+.1f}% ROI against the sharpest book")
        print(f"  >>> This suggests genuine predictive alpha from Hodge decomposition")
    elif pin_roi > -10:
        print(f"\n  >>> HODGE ROUGHLY BREAKS EVEN vs Pinnacle: {pin_roi:+.1f}% ROI")
        print(f"  >>> Edge exists but doesn't survive the vig at Pinnacle")
        max_roi = (cum_bankroll["Max"] - 100) / 100 * 100
        if max_roi > 0:
            print(f"  >>> BUT profitable at best available odds: {max_roi:+.1f}% ROI")
    else:
        print(f"\n  >>> HODGE LOSES vs Pinnacle: {pin_roi:+.1f}% ROI")
        print(f"  >>> The Elo-based backtest was optimistic -- real books are too sharp")

    # Save
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "site", "data", "hodge_real_odds_epl.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Clean for JSON
    save_data = {
        "aggregate": {
            source: {"bets": cum_bets[source], "wins": cum_wins[source],
                     "bankroll": round(cum_bankroll[source], 2),
                     "roi": round((cum_bankroll[source]-100)/100*100, 1)}
            for source in ["Pinnacle", "Max", "Bet365"]
        },
    }
    with open(out, "w") as f:
        json.dump(save_data, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
