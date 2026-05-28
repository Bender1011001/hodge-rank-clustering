# Cycle 2 NHL Rolling Walk-Forward Pre-Registration

Generated before running Cycle 2 walk-forward results.

## Objective

Test whether the historically positive strict NHL Hodge-vs-market pocket survives frozen rules, NHL odds quarantine, conservative decimal-odds return haircuts, and identical-game market baselines. This is historical quantitative validation only; it is not live betting, account automation, or betting advice.

## Population

- Source: `site/data/historical_sportsbook_games.csv`.
- Sport: NHL only.
- Market: two-way moneyline, away and home sides only.
- Evaluation unit: completed NHL game after quarantine and after enough prior NHL history exists.

## Quarantine rules

Rows are excluded before feature generation if any of the following hold:

1. Missing away team or home team.
2. Missing away score or home score.
3. Missing away or home moneyline decimal odds.
4. Non-finite prices.
5. Decimal odds less than or equal to 1.0.
6. Impossible two-positive moneyline pair in original American odds columns when those columns are available.
7. Duplicate `(date, away_team, home_team)` key.
8. Two-way market overround outside `[0.98, 1.06]`.

Rows with overround above `1.05` but at or below `1.06` are flagged for reporting, not separately excluded unless another malformed condition applies.

## Hodge/replay rules

- Minimum prior NHL games before evaluated prediction: 300.
- Primary training window: the previous 760 clean NHL games.
- Feature generation is chronological and uses no future games.
- Same-date games are predicted from models fit before that date's slate and are added to history only after the slate is evaluated.
- Hodge side probability follows existing sportsbook-agent conventions from `scripts/hodge_real_sportsbook_agent.py`:
  - weighted Hodge potential from capped margins;
  - NHL margin cap of 5 goals;
  - home-ice correction from prior non-neutral games;
  - binary logistic scale calibration using only the rolling training window.
- Side-level feature conventions follow `scripts/hodge_market_residual_strategy.py` where applicable:
  - market implied probability;
  - normalized market probability;
  - Hodge probability;
  - Hodge edge versus raw market implied probability;
  - Hodge-vs-market disagreement metadata;
  - side labels and home/away indicators.

## Threshold grid and selection

Frozen threshold grid:

- Hodge edge thresholds: `0.15`, `0.18`, `0.20`, `0.25`.
- EV thresholds: `0.05`, `0.08`, `0.10`.

For each rolling fold:

1. Evaluate every threshold pair on the tune window.
2. Select the pair with highest tune flat one-unit yield among candidates with at least 50 tune bets.
3. Break ties by higher tune profit, then more tune bets, then lower Hodge edge threshold, then lower EV threshold.
4. If no pair reaches 50 tune bets, mark the fold inconclusive and do not lower thresholds.
5. Apply the selected threshold pair once to the immediately following test season with no threshold or feature changes inside that season.

## Window schedule

- Tune window: previous two completed NHL seasons when both are available and there are enough clean rows after warmup to produce threshold candidates; otherwise previous one completed NHL season.
- Test window: the immediately following completed NHL season.
- At least three eligible test seasons are required; otherwise Cycle 2 is inconclusive.
- Completed seasons are inferred from the season labels present in the quarantined source data and ordered by first game date.

## Staking and slippage

- Primary stake simulation: flat 1% of start-of-day bankroll per selected bet.
- Maximum same-day exposure: 5% of start-of-day bankroll. If same-day selections exceed this, stakes are scaled proportionally for that day.
- Also compute flat one-unit yield independent of bankroll compounding.
- Decimal-odds return haircuts: `0%`, `1%`, `2%`, `3%` applied to the winning return component only by reducing decimal odds to `1 + (odds - 1) * (1 - haircut)`.
- Primary judgment uses `1%` and `2%`; `0%` is descriptive only.

## Baselines

Compute on identical eligible test games when feasible:

- Same-game market favorite.
- Same-game market underdog.
- Home side.
- Away side.
- Hodge-only side before thresholds.
- Contrarian side against the Hodge-only side.
- Market-only expected-value calibration if feasible.
- Odds-band matched random controls with fixed seeds.

## Metrics

Report:

- Bets.
- Win rate.
- Yield.
- Final bankroll/return.
- Max drawdown.
- Profit factor.
- Average closing-implied probability.
- Odds-band contribution.
- Season contribution.
- Team-cluster contribution.
- Baseline deltas.

## Success rule

Cycle 2 succeeds only if all primary conditions hold:

1. Aggregate selected-strategy yield is positive after `1%` haircut and non-negative after `2%` haircut.
2. Selected strategy beats market-only and odds-band matched controls in a majority of untouched test windows.
3. At least three eligible test windows exist.
4. At least two test windows are positive after `1%` haircut.
5. No single season contributes more than 60% of total profit.
6. No single odds band, side, or team cluster explains the whole result.
7. Max drawdown is not worse than the best same-game market baseline by more than 10 percentage points.

## Failure rule

Cycle 2 fails if any primary failure condition holds:

1. `1%` haircut aggregate yield is less than or equal to zero.
2. Selected strategy loses to market-only or odds-band matched controls in most windows.
3. Only the `0%` haircut is positive.
4. Positive aggregate performance is dominated by one season, side, odds band, or team cluster.
5. Tune-selected thresholds collapse to too few test bets.

## Inconclusive rule

Cycle 2 is inconclusive if fewer than three eligible test windows exist, if data quarantine prevents faithful replay, if feature generation cannot be completed from the available scratch-only implementation, or if no fold has a threshold pair with at least 50 tune bets.
