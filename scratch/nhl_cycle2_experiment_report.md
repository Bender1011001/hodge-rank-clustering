# Cycle 2 NHL rolling walk-forward experiment report

## Hypothesis tested

The frozen test asks whether the historically positive strict NHL Hodge-vs-market pocket survives chronological walk-forward threshold selection, odds quarantine, same-game baselines, and 1%-2% decimal-odds return haircuts.

## Experiment performed

1. Wrote pre-registration artifacts before evaluating Cycle 2 results.
2. Quarantined NHL rows from `site/data/historical_sportsbook_games.csv` using the frozen rules.
3. Generated chronological no-future Hodge side rows with 300-game warmup and 760-game rolling training window.
4. For each eligible test season, selected Hodge edge/EV thresholds on the preceding tune season(s) only, then applied them once to the untouched test season.
5. Simulated selected bets under 0%, 1%, 2%, and 3% return haircuts and computed same-game baselines plus odds-band random controls.

## Files changed

All result artifacts were written under `scratch/`, with a concise `context.md` update planned after completion.

## Commands/checks run

- `python scratch\test_nhl_cycle2_walkforward.py` before implementation: failed with `ModuleNotFoundError`, confirming the red test state.
- `python scratch\test_nhl_cycle2_walkforward.py` after implementation.
- `python scratch\nhl_cycle2_walkforward.py`.
- `python -m compileall scratch\nhl_cycle2_walkforward.py scratch\test_nhl_cycle2_walkforward.py`.

## Quarantine counts

- NHL rows: 11303
- Included rows: 11303
- Excluded rows: 0
- Excluded reasons: `{}`
- Overround >1.05 and <=1.06 flags: 1
- Overround summary: `{'count': 11303, 'mean': 1.032936, 'median': 1.033375, 'min': 1.002439, 'max': 1.050215, 'p95': 1.047079}`

## Fold-level results at 1% haircut

| fold | tune seasons | test season | status | threshold | tune bets | test bets | win % | unit yield % | bankroll yield % | max DD % |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | NHL 2012-13 | NHL 2013-14 | inconclusive | n/a | 1012 | 0 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2 | NHL 2012-13, NHL 2013-14 | NHL 2014-15 | completed | 0.15/0.05 | 88 | 32 | 40.62 | -25.10 | -25.47 | 8.51 |
| 3 | NHL 2013-14, NHL 2014-15 | NHL 2015-16 | completed | 0.15/0.05 | 85 | 65 | 53.85 | -0.36 | -0.84 | 7.05 |
| 4 | NHL 2014-15, NHL 2015-16 | NHL 2016-17 | completed | 0.15/0.05 | 97 | 41 | 58.54 | 9.82 | 9.54 | 4.27 |
| 5 | NHL 2015-16, NHL 2016-17 | NHL 2017-18 | completed | 0.15/0.05 | 106 | 68 | 58.82 | 13.22 | 13.11 | 5.08 |
| 6 | NHL 2016-17, NHL 2017-18 | NHL 2018-19 | completed | 0.15/0.05 | 109 | 43 | 55.81 | 9.04 | 8.47 | 5.00 |
| 7 | NHL 2017-18, NHL 2018-19 | NHL 2019-20 | completed | 0.15/0.05 | 111 | 45 | 55.56 | 11.47 | 10.86 | 3.57 |
| 8 | NHL 2018-19, NHL 2019-20 | NHL 2021 | completed | 0.15/0.05 | 88 | 31 | 67.74 | 25.95 | 25.41 | 1.99 |

## Aggregate slippage results

| haircut | bets | wins | win % | unit yield % | final bankroll | bankroll yield % | max DD % | profit factor |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0% | 325 | 182 | 56.00 | 7.23 | 1246.78 | 7.45 | 11.91 | 1.169713 |
| 1% | 325 | 182 | 56.00 | 6.72 | 1226.38 | 6.89 | 12.28 | 1.156874 |
| 2% | 325 | 182 | 56.00 | 6.21 | 1206.31 | 6.33 | 12.66 | 1.144056 |
| 3% | 325 | 182 | 56.00 | 5.70 | 1186.57 | 5.77 | 13.03 | 1.13126 |

## Baseline and concentration findings

- 1% haircut aggregate unit yield: 6.72%.
- 2% haircut aggregate unit yield: 6.21%.
- Threshold selections: `{'edge=0.15|ev=0.05': 7}`.
- Baseline window wins versus best market baseline: 4 of 7 completed windows.
- Baseline window wins versus random-control mean: 6 of 7 completed windows.
- Concentration flags: `{'single_season_gt_60pct_total_profit': False, 'single_odds_band_gt_80pct_total_profit': False, 'single_side_gt_80pct_total_profit': True, 'single_team_cluster_gt_80pct_total_profit': False}`.
- Top season contribution: `{'season': 'NHL 2021', 'bets': 31, 'wins': 21, 'profit': 93.379474, 'staked': 367.482387, 'yield_pct': 25.410599, 'profit_share_of_total': 0.412491}`.
- Top odds-band contribution: `{'odds_band': '1.75-2.00', 'bets': 91, 'wins': 56, 'profit': 139.093061, 'staked': 917.171, 'yield_pct': 15.165445, 'profit_share_of_total': 0.614425}`.
- Top side contribution: `{'side': 'home', 'bets': 154, 'wins': 95, 'profit': 182.640495, 'staked': 1564.487399, 'yield_pct': 11.674143, 'profit_share_of_total': 0.80679}`.
- Top team-cluster contribution: `{'selected_team': 'Winnipeg', 'bets': 17, 'wins': 14, 'profit': 93.716628, 'staked': 184.898467, 'yield_pct': 50.685454, 'profit_share_of_total': 0.41398}`.

## Result label

- Label: **failure**.
- Confidence: **medium**.
- Rule evaluation: `{'eligible_test_windows': 7, 'minimum_3_eligible_test_windows': True, 'positive_windows_after_1pct': 5, 'minimum_2_positive_windows_after_1pct': True, 'aggregate_1pct_unit_yield_positive': True, 'aggregate_2pct_unit_yield_non_negative': True, 'beats_best_market_baseline_majority': True, 'beats_random_control_mean_majority': True, 'no_single_season_gt_60pct_total_profit': True, 'no_single_odds_band_side_or_team_cluster_gt_80pct_total_profit': False, 'selected_max_drawdown_not_worse_than_best_market_by_10pp': False}`.

## Checks not run or limited

- Market-only EV calibration was marked skipped because closing odds alone imply non-positive raw EV once overround is included; favorite/underdog baselines were run instead.
- Archived odds timing/executability remains unresolved because the local archive lacks timestamped price snapshots.
- Team-cluster concentration is represented by selected-team clusters, not external roster/style clusters.

## Recommended next action

Hand off this evidence packet to `llm-result-critic` for skeptical review of the frozen-rule implementation choices, the incomplete 2022-23 exclusion, and whether the failure/inconclusive criteria were applied appropriately.
