# NHL strict edge supplemental audit

Scratch-only evidence generated from existing artifacts. No site/data artifacts were modified.

## Residual split smoke tests

| split | train_frac | tune_frac | tune bets | tune yield % | selected edge | selected min_ev | test bets | test win % | test yield % | test max DD % | test date window |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| split50_25 | 0.5 | 0.25 | 657 | -1.43 | 0.0 | 0.0 | 1185 | 55.44 | -4.03 | 34.91 | 2019-04-10..2022-11-27 |
| split70_15 | 0.7 | 0.15 | 630 | -6.43 | 0.0 | 0.0 | 717 | 54.25 | -1.76 | 26.08 | 2020-01-03..2022-11-27 |
| canonical_site_split | 0.6 | 0.2 | 582 | -3.56 | 0.0 | 0.0 | 940 | 57.45 | -1.77 | 27.72 | 2019-09-25..2022-11-27 |

## Odds quarantine counts

{
  "rows": 11303,
  "seasons": {
    "NHL 2012-13": 806,
    "NHL 2013-14": 1322,
    "NHL 2014-15": 1319,
    "NHL 2015-16": 1321,
    "NHL 2016-17": 1317,
    "NHL 2017-18": 1355,
    "NHL 2018-19": 1358,
    "NHL 2019-20": 1212,
    "NHL 2021": 951,
    "NHL 2022-23": 342
  },
  "sources": {
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2012-13": 806,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2013-14": 1322,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2014-15": 1319,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2015-16": 1321,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2016-17": 1317,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2017-18": 1355,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2018-19": 1358,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2019-20": 1212,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2021": 951,
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2022-23": 342
  },
  "counts": {
    "overround_over_1_05": 1
  },
  "duplicate_date_away_home_count": 0,
  "duplicate_date_away_home_examples": {},
  "overround": {
    "n": 11303,
    "mean": 1.032936,
    "median": 1.033375,
    "min": 1.002439,
    "p05": 1.019763,
    "p95": 1.047079,
    "max": 1.050215
  }
}

## Strict NHL slippage replay

Dynamic replay uses the same stored selections, 1% flat staking, 5% max same-day exposure, and reduced decimal odds.

| haircut | bets | wins | win % | final bankroll | yield % | max DD % |
|---:|---:|---:|---:|---:|---:|---:|
| 0pct | 474 | 264 | 55.7 | 1236.99 | 5.03 | 20.52 |
| 1pct | 474 | 264 | 55.7 | 1177.59 | 3.86 | 21.7 |
| 2pct | 474 | 264 | 55.7 | 1121.04 | 2.7 | 22.85 |
| 3pct | 474 | 264 | 55.7 | 1067.19 | 1.53 | 23.99 |

## Season and era contribution

| era | bets | wins | win % | profit | staked | yield % |
|---|---:|---:|---:|---:|---:|---:|
| early_2013_2016 | 199 | 103 | 51.76 | -144.8 | 1857.24 | -7.8 |
| middle_2017_2019 | 180 | 105 | 58.33 | 235.14 | 1753.95 | 13.41 |
| late_2020_2022 | 95 | 56 | 58.95 | 146.64 | 1098.55 | 13.35 |

## Same-window baselines on strict bet games

| strategy | matched bets | wins | win % | final bankroll | yield % | max DD % |
|---|---:|---:|---:|---:|---:|---:|
| stored_strict_hodge_selection | 474 | 264 | 55.7 | 1236.99 | 5.03 | 20.52 |
| same_games_home | 474 | 264 | 55.7 | 1017.34 | 0.35 | 15.61 |
| same_games_away | 474 | 210 | 44.3 | 684.15 | -8.78 | 36.05 |
| same_games_favorite | 474 | 273 | 57.59 | 843.7 | -3.45 | 26.64 |
| same_games_underdog | 474 | 202 | 42.62 | 839.56 | -3.97 | 30.58 |

## Strict NHL exposure decomposition

### By side

{
  "away": {
    "bets": 232,
    "wins": 116,
    "win_pct": 50.0,
    "profit": 11.13,
    "staked": 2284.97,
    "yield_pct": 0.49
  },
  "home": {
    "bets": 242,
    "wins": 148,
    "win_pct": 61.16,
    "profit": 225.85,
    "staked": 2424.74,
    "yield_pct": 9.31
  }
}

### By favorite/underdog

{
  "favorite": {
    "bets": 270,
    "wins": 167,
    "win_pct": 61.85,
    "profit": 104.02,
    "staked": 2674.69,
    "yield_pct": 3.89
  },
  "underdog": {
    "bets": 204,
    "wins": 97,
    "win_pct": 47.55,
    "profit": 132.96,
    "staked": 2035.02,
    "yield_pct": 6.53
  }
}

### By selected odds band

{
  "1.50_to_1.75": {
    "bets": 159,
    "wins": 97,
    "win_pct": 61.01,
    "profit": -16.69,
    "staked": 1577.16,
    "yield_pct": -1.06
  },
  "1.75_to_2.00": {
    "bets": 119,
    "wins": 70,
    "win_pct": 58.82,
    "profit": 117.9,
    "staked": 1163.59,
    "yield_pct": 10.13
  },
  "ge_2.00": {
    "bets": 174,
    "wins": 82,
    "win_pct": 47.13,
    "profit": 145.35,
    "staked": 1746.92,
    "yield_pct": 8.32
  },
  "lt_1.50": {
    "bets": 22,
    "wins": 15,
    "win_pct": 68.18,
    "profit": -9.58,
    "staked": 222.05,
    "yield_pct": -4.31
  }
}

### By model edge band

{
  "0.15_to_0.18": {
    "bets": 251,
    "wins": 145,
    "win_pct": 57.77,
    "profit": 176.81,
    "staked": 2455.53,
    "yield_pct": 7.2
  },
  "0.18_to_0.22": {
    "bets": 153,
    "wins": 79,
    "win_pct": 51.63,
    "profit": -11.8,
    "staked": 1512.87,
    "yield_pct": -0.78
  },
  "0.22_to_0.30": {
    "bets": 57,
    "wins": 33,
    "win_pct": 57.89,
    "profit": 61.02,
    "staked": 605.89,
    "yield_pct": 10.07
  },
  "ge_0.30": {
    "bets": 13,
    "wins": 7,
    "win_pct": 53.85,
    "profit": 10.95,
    "staked": 135.43,
    "yield_pct": 8.08
  }
}
