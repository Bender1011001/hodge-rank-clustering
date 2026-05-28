# Cycle 3 NHL diagnostic preregistration

Generated before running Cycle 3 diagnostic metrics or writing Cycle 3 result artifacts.

## Objective

Isolate whether the Cycle 2 positive aggregate NHL selected-bet anomaly is explained by home-side exposure, mid-odds exposure, top-team contributors, joint side-plus-odds structure, or matched market controls. This is anomaly isolation only: historical quantitative research, not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.

## Frozen selected universe

- Authoritative input artifact: `scratch/nhl_cycle2_walkforward_results.json`.
- Reconstruction reference if row-level selections are not present: `scratch/nhl_cycle2_walkforward.py`.
- Frozen threshold pair for verdict diagnostics: raw Hodge edge `0.15`, EV `0.05`.
- No retuning, grid expansion, or alternate threshold selection is allowed for the frozen Cycle 3 verdict.
- Required identity check before interpreting diagnostics: 325 selected bets, 182 wins, 56.00% win rate, one-percent haircut unit yield approximately +6.72%, two-percent haircut unit yield approximately +6.21%.
- Tolerances for identity check: exact bet and win counts; win rate within 0.005 percentage points; one-percent and two-percent unit yields within 0.01 percentage points of the rounded Cycle 2 report values.

## Frozen diagnostics, in priority order

1. Leave-home ablation; home-only and favorite controls.
2. Side by odds-band cross-tab; odds-band-stratified home/away controls; date/window-aware random controls.
3. Remove 1.75-to-2.00 odds band; inspect/remove adjacent 2.00-to-2.50 odds band as secondary; odds-band random controls.
4. Matched market favorite, matched market underdog, home-only, away-only, and date/window-aware odds-band random controls.
5. Remove Winnipeg; remove cumulative top one/top three/top five/top ten positive contributors.
6. Assess residual distributed anomaly only if the diagnostics above survive.

## Metrics to compute

For selected, ablated, and control cohorts:

- Bets, wins, and win rate.
- Unit profit and unit yield under one-percent and two-percent return haircuts.
- Bankroll yield and max drawdown using the chronological selected-bet order when reconstructable; otherwise mark unavailable rather than substituting an unordered proxy.
- Profit share by side, odds band, team, and season.
- Selected-vs-control deltas for one-percent and two-percent unit yield and max drawdown.
- Matching relaxation rates for date/window-aware random or matched controls.

## Control construction

- Matched market favorite: for each selected game, choose the same-game market favorite side when available.
- Matched market underdog: for each selected game, choose the same-game market underdog side when available.
- Home-only control: for each selected game, choose the same-game home side when available.
- Away-only control: for each selected game, choose the same-game away side when available.
- Date/window-aware odds-band random controls: for each selected bet, first try eligible rows from the same date and selected odds band; then relax to same week, same season, same walk-forward test window, and finally same odds band globally. Report relaxation counts and rates.
- Odds-band-stratified home/away controls: choose same-game home/away sides and report odds-band distribution drift versus selected; if a same-game side falls outside the selected odds band, report it rather than hiding the mismatch.

## Stop/downgrade rules

- Stop or downgrade if one-percent haircut yield collapses to zero or negative after removing home selections.
- Stop or downgrade if one-percent haircut yield collapses to zero or negative after removing the 1.75-to-2.00 odds band.
- Stop or downgrade if one-percent haircut yield collapses after removing Winnipeg or cumulative top-team sets.
- Stop or downgrade if any matched control equals or beats selected within a 1.0 percentage-point one-percent unit-yield tolerance.
- Stop or downgrade if controls have materially better drawdown by more than 2.0 percentage points while yield is equal or better.
- Stop or downgrade if survival depends on fewer than 50 residual bets or a cherry-picked subset.

## Hypothesis labels to assign after diagnostics

- Home-side artifact.
- Joint side-plus-odds artifact.
- Mid-odds artifact.
- Market-baseline artifact.
- Top-team artifact.
- Residual distributed anomaly.

Use result labels: confirmed, likely, plausible, weak signal, contradicted, blocked, or skipped. Use confidence levels: high, medium, low, or unknown.

## Planned output artifacts

- `scratch/nhl_cycle3_diagnostics.py`.
- `scratch/test_nhl_cycle3_diagnostics.py`.
- `scratch/nhl_cycle3_diagnostic_results.json`.
- `scratch/nhl_cycle3_experiment_report.md`.

## Planned verification commands

- `python scratch/test_nhl_cycle3_diagnostics.py`.
- `python scratch/nhl_cycle3_diagnostics.py`.
- `python -m compileall scratch/nhl_cycle3_diagnostics.py scratch/test_nhl_cycle3_diagnostics.py`.
