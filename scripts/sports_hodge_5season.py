"""
5-Season Hodge Sports Backtest
================================
Runs weighted Hodge decomposition across 5 seasons for a single sport,
with All-Star/international game filtering, home-field correction,
margin capping, and curl-aware prediction.

Usage: python sports_hodge_5season.py <SPORT>
  SPORT: NFL | NBA | NHL | MLB | EPL | CFB
"""

import json, urllib.request, numpy as np, scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from datetime import date, timedelta
import sys, os, time

# ======================================================================
# HODGE ENGINE (weighted, corrected)
# ======================================================================

def weighted_hodge(games, teams, margin_cap=None):
    n = len(teams)
    ti = {t: i for i, t in enumerate(teams)}
    hfa = np.mean([g["home_score"] - g["away_score"] for g in games]) if games else 0

    pair_margins = {}
    for g in games:
        hi, ai = ti[g["home_team"]], ti[g["away_team"]]
        corrected = np.clip(g["home_score"] - g["away_score"] - hfa,
                           -margin_cap, margin_cap) if margin_cap else (g["home_score"] - g["away_score"] - hfa)
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


def elo_ratings(games, teams, K=20, hfa=0):
    r = {t: 1500.0 for t in teams}
    for g in sorted(games, key=lambda x: x.get("_ord", 0)):
        h, a = g["home_team"], g["away_team"]
        eh = 1.0 / (1.0 + 10 ** ((r[a] - r[h] - hfa) / 400))
        s = 1.0 if g["home_score"] > g["away_score"] else (0.0 if g["home_score"] < g["away_score"] else 0.5)
        r[h] += K * (s - eh); r[a] += K * ((1-s) - (1-eh))
    return r


def evaluate(test, hodge, elo_dict):
    phi, hfa_h, ti, e2i, Fc = hodge["phi"], hodge["hfa"], hodge["ti"], hodge["e2i"], hodge["Fc"]
    res = {m: [0, 0] for m in ["hodge", "hodge+curl", "elo", "home"]}  # [correct, total]

    for g in test:
        hs, aws = g["home_score"], g["away_score"]
        if hs == aws: continue
        hw = hs > aws
        hi, ai = ti.get(g["home_team"]), ti.get(g["away_team"])
        if hi is None or ai is None: continue

        # Hodge potential + HFA
        pred = (phi[ai] - phi[hi]) + hfa_h
        res["hodge"][1] += 1
        if (pred > 0) == hw: res["hodge"][0] += 1

        # Hodge + curl
        curl_adj = 0
        i, j = min(hi, ai), max(hi, ai)
        if (i, j) in e2i:
            cv = Fc[e2i[(i, j)]]
            curl_adj = cv if hi == i else -cv
        pred_c = pred + 0.5 * curl_adj
        res["hodge+curl"][1] += 1
        if (pred_c > 0) == hw: res["hodge+curl"][0] += 1

        # Elo + HFA
        he = elo_dict.get(g["home_team"], 1500)
        ae = elo_dict.get(g["away_team"], 1500)
        res["elo"][1] += 1
        if (he > ae) == hw: res["elo"][0] += 1

        # Home always
        res["home"][1] += 1
        if hw: res["home"][0] += 1

    return {k: v[0]/max(v[1],1) for k, v in res.items()}


# ======================================================================
# FETCHERS
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
                    games.append(g)
        idx += 1; d += timedelta(days=1)
    return games


# ======================================================================
# SEASON CONFIGS
# ======================================================================

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

def cfb_seasons():
    return [{"label": f"CFB {y}",
             "fetch": lambda y=y: fetch_weekly("football", "college-football", y, 16, 500, "80")}
            for y in [2020, 2021, 2022, 2023, 2024]]


SPORTS = {
    "NFL": {"seasons": nfl_seasons, "cap": 28, "elo_K": 20, "elo_hfa": 48, "split": 0.67, "min_gp": 10},
    "NBA": {"seasons": nba_seasons, "cap": 25, "elo_K": 15, "elo_hfa": 30, "split": 0.75, "min_gp": 40},
    "NHL": {"seasons": nhl_seasons, "cap": 5,  "elo_K": 15, "elo_hfa": 20, "split": 0.75, "min_gp": 40},
    "MLB": {"seasons": mlb_seasons, "cap": 8,  "elo_K": 8,  "elo_hfa": 15, "split": 0.75, "min_gp": 50},
    "EPL": {"seasons": epl_seasons, "cap": 4,  "elo_K": 20, "elo_hfa": 30, "split": 0.70, "min_gp": 15},
    "CFB": {"seasons": cfb_seasons, "cap": 35, "elo_K": 15, "elo_hfa": 40, "split": 0.67, "min_gp": 6},
}


# ======================================================================
# MAIN
# ======================================================================

def filter_games(games, min_gp):
    """Remove teams with fewer than min_gp games (filters All-Star/international)."""
    from collections import Counter
    ct = Counter()
    for g in games:
        ct[g["home_team"]] += 1; ct[g["away_team"]] += 1
    valid = {t for t, c in ct.items() if c >= min_gp}
    return [g for g in games if g["home_team"] in valid and g["away_team"] in valid]


def run_sport(sport_name):
    cfg = SPORTS[sport_name]
    seasons = cfg["seasons"]()

    print(f"\n{'#'*70}")
    print(f"# {sport_name} - 5 SEASON BACKTEST")
    print(f"{'#'*70}")

    all_accs = {m: [] for m in ["hodge", "hodge+curl", "elo", "home"]}
    all_vpct = {"g": [], "c": [], "h": []}
    all_hfa = []
    season_rows = []

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
            print(f"    Only {len(games)} games after filtering, skipping")
            continue

        teams = sorted(set([g["home_team"] for g in games] + [g["away_team"] for g in games]))
        games.sort(key=lambda g: g.get("_ord", 0))
        si = int(len(games) * cfg["split"])
        train, test = games[:si], games[si:]

        print(f"    {len(teams)} teams, {len(games)} games (train {len(train)}, test {len(test)})")

        # Hodge
        hodge = weighted_hodge(train, teams, margin_cap=cfg["cap"])
        print(f"    Hodge: {hodge['vpct']['g']:.1f}% grad, {hodge['vpct']['c']:.1f}% curl, "
              f"{hodge['vpct']['h']:.1f}% harm | HFA={hodge['hfa']:+.2f} | "
              f"edges={len(hodge['edges'])}, tri={hodge['n_tri']}")

        # Elo
        elo = elo_ratings(train, teams, K=cfg["elo_K"], hfa=cfg["elo_hfa"])

        # Evaluate
        accs = evaluate(test, hodge, elo)
        for m in accs:
            all_accs[m].append(accs[m])
        all_vpct["g"].append(hodge["vpct"]["g"])
        all_vpct["c"].append(hodge["vpct"]["c"])
        all_vpct["h"].append(hodge["vpct"]["h"])
        all_hfa.append(hodge["hfa"])

        print(f"    Results: Hodge={accs['hodge']:.1%}  H+Curl={accs['hodge+curl']:.1%}  "
              f"Elo={accs['elo']:.1%}  Home={accs['home']:.1%}")

        # Top 5 rankings
        phi = hodge["phi"]
        ranked = sorted(range(len(teams)), key=lambda i: phi[i])
        top5 = [teams[ranked[r]] for r in range(min(5, len(ranked)))]
        print(f"    Top 5: {', '.join(top5)}")

        season_rows.append({
            "label": label, "teams": len(teams), "games": len(games),
            "train": len(train), "test": len(test),
            "accs": accs, "vpct": dict(hodge["vpct"]), "hfa": hodge["hfa"],
            "top5": top5,
        })

    if not all_accs["hodge"]:
        print(f"\n  No valid seasons for {sport_name}")
        return None

    # Aggregate
    n_seasons = len(all_accs["hodge"])
    print(f"\n  {'='*60}")
    print(f"  {sport_name} AGGREGATE ({n_seasons} seasons)")
    print(f"  {'='*60}")

    print(f"\n  {'Season':<15s} {'Hodge':>7s} {'H+Curl':>7s} {'Elo':>7s} {'Home':>7s} {'Grad%':>6s} {'Curl%':>6s}")
    print(f"  {'-'*57}")
    for row in season_rows:
        a = row["accs"]; v = row["vpct"]
        print(f"  {row['label']:<15s} {a['hodge']:>6.1%} {a['hodge+curl']:>6.1%} "
              f"{a['elo']:>6.1%} {a['home']:>6.1%} {v['g']:>5.1f}% {v['c']:>5.1f}%")

    print(f"  {'-'*57}")
    means = {m: np.mean(all_accs[m]) for m in all_accs}
    stds = {m: np.std(all_accs[m]) for m in all_accs}
    mg, mc, mh = np.mean(all_vpct["g"]), np.mean(all_vpct["c"]), np.mean(all_vpct["h"])

    print(f"  {'MEAN':<15s} {means['hodge']:>6.1%} {means['hodge+curl']:>6.1%} "
          f"{means['elo']:>6.1%} {means['home']:>6.1%} {mg:>5.1f}% {mc:>5.1f}%")
    print(f"  {'STD':<15s} {stds['hodge']:>6.1%} {stds['hodge+curl']:>6.1%} "
          f"{stds['elo']:>6.1%} {stds['home']:>6.1%}")

    edge_vs_elo = means["hodge"] - means["elo"]
    print(f"\n  Hodge vs Elo: {edge_vs_elo:+.1%} (mean across {n_seasons} seasons)")
    print(f"  Hodge+Curl vs Elo: {means['hodge+curl'] - means['elo']:+.1%}")
    print(f"  Mean HFA: {np.mean(all_hfa):+.2f} | Mean Grad: {mg:.1f}% | Mean Curl: {mc:.1f}%")

    return {
        "sport": sport_name, "n_seasons": n_seasons,
        "means": {k: float(v) for k, v in means.items()},
        "stds": {k: float(v) for k, v in stds.items()},
        "mean_vpct": {"g": float(mg), "c": float(mc), "h": float(mh)},
        "mean_hfa": float(np.mean(all_hfa)),
        "edge_vs_elo": float(edge_vs_elo),
        "seasons": season_rows,
    }


def main():
    sport = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"

    if sport == "ALL":
        # Run all sports sequentially (caller should run per-sport in parallel)
        results = {}
        for s in SPORTS:
            r = run_sport(s)
            if r: results[s] = r
    elif sport in SPORTS:
        results = {sport: run_sport(sport)}
    else:
        print(f"Unknown: {sport}. Options: {list(SPORTS.keys())}")
        return

    # Save
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "site", "data", f"hodge_5season_{sport.lower()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Make serializable
    for s in results.values():
        for row in s.get("seasons", []):
            row["accs"] = {k: float(v) for k, v in row["accs"].items()}
            row["vpct"] = {k: float(v) for k, v in row["vpct"].items()}
            row["hfa"] = float(row["hfa"])

    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
