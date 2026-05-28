# Cycle 3 NHL diagnostic experiment report

Historical quantitative research only; not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.

## 1. Hypothesis tested

The bounded diagnostic tested whether the Cycle 2 positive aggregate NHL selected-bet anomaly is explained by home-side exposure, mid-odds exposure, top-team contributors, joint side-plus-odds structure, or matched market controls.

## 2. Experiment performed

1. Wrote Cycle 3 preregistration artifacts before result artifacts.
2. Reconstructed the frozen Cycle 2 selected universe from the Cycle 2 runner and authoritative Cycle 2 walk-forward artifact, without threshold retuning.
3. Verified selected-universe identity against Cycle 2 aggregate metrics.
4. Ran leave-slice ablations, side×odds diagnostics, same-game matched controls, and date/window-aware odds-band random controls.
5. Applied the frozen stop/downgrade rules.

## 3. Selected-universe identity check

- Passed: `True`
- Actual: `{'bets': 325, 'wins': 182, 'win_rate_pct': 56.0, 'unit_yield_pct_1pct': 6.722272, 'unit_yield_pct_2pct': 6.209926}`
- Checks: `{'bets_exact': True, 'wins_exact': True, 'win_rate_within_0_005pp': True, 'unit_yield_1pct_within_0_01pp': True, 'unit_yield_2pct_within_0_01pp': True}`

## 4. Selected aggregate metrics

- One-percent haircut: `{'haircut': 0.01, 'bets': 325, 'wins': 182, 'win_pct': 56.0, 'initial_bankroll': 1000.0, 'final_bankroll': 1226.379331, 'bankroll_profit': 226.379331, 'bankroll_return_pct': 22.637933, 'total_staked': 3285.199517, 'yield_pct': 6.890885, 'unit_profit': 21.847386, 'unit_staked': 325.0, 'unit_yield_pct': 6.722272, 'max_drawdown_pct': 12.284308, 'profit_factor': 1.156874, 'avg_implied_probability': 0.523347}`
- Two-percent haircut: `{'haircut': 0.02, 'bets': 325, 'wins': 182, 'win_pct': 56.0, 'initial_bankroll': 1000.0, 'final_bankroll': 1206.309171, 'bankroll_profit': 206.309171, 'bankroll_return_pct': 20.630917, 'total_staked': 3258.868898, 'yield_pct': 6.330699, 'unit_profit': 20.18226, 'unit_staked': 325.0, 'unit_yield_pct': 6.209926, 'max_drawdown_pct': 12.655793, 'profit_factor': 1.144056, 'avg_implied_probability': 0.523347}`

## 5. Ablation table summary

| ablation | bets | wins | 1% unit yield % | 2% unit yield % | 1% max DD % |
|---|---:|---:|---:|---:|---:|
| remove_home | 171 | 87 | 1.71 | 1.19 | 15.74 |
| remove_away | 154 | 95 | 12.29 | 11.78 | 4.27 |
| remove_odds_band_1.75-2.00 | 234 | 126 | 4.04 | 3.53 | 13.89 |
| remove_odds_band_2.00-2.50 | 236 | 135 | 3.97 | 3.50 | 6.52 |
| remove_team_Winnipeg | 308 | 168 | 4.33 | 3.83 | 12.90 |
| remove_cumulative_top_1_teams | 308 | 168 | 4.33 | 3.83 | 12.90 |
| remove_cumulative_top_3_teams | 294 | 155 | 0.60 | 0.11 | 14.99 |
| remove_cumulative_top_5_teams | 269 | 138 | -2.76 | -3.22 | 14.69 |
| remove_cumulative_top_10_teams | 181 | 84 | -11.54 | -11.97 | 23.13 |

## 6. Matched-control table summary

| control | bets | wins | 1% unit yield % | delta vs selected pp | 1% max DD % |
|---|---:|---:|---:|---:|---:|
| home_only | 325 | 179 | 0.05 | 6.67 | 11.85 |
| market_favorite | 325 | 188 | -2.04 | 8.76 | 28.47 |
| date_window_odds_band_random_seed_7 | 325 | 164 | -2.57 | 9.29 | 19.95 |
| market_underdog | 325 | 136 | -5.74 | 12.46 | 29.34 |
| date_window_odds_band_random_seed_17 | 325 | 157 | -5.84 | 12.56 | 29.18 |
| away_only | 325 | 146 | -7.23 | 13.95 | 30.41 |
| date_window_odds_band_random_seed_29 | 325 | 148 | -12.57 | 19.29 | 38.21 |

## 7. Concentration summary

- Top side contribution: `{'side': 'home', 'bets': 154, 'wins': 95, 'unit_profit': 18.927283, 'unit_yield_pct': 12.290444, 'profit_share_of_total_unit_profit': 0.866341}`
- Top odds-band contribution: `{'odds_band': '2.00-2.50', 'bets': 89, 'wins': 47, 'unit_profit': 12.4797, 'unit_yield_pct': 14.022135, 'profit_share_of_total_unit_profit': 0.571222}`
- Top team contribution: `{'selected_team': 'Winnipeg', 'bets': 17, 'wins': 14, 'unit_profit': 8.498327, 'unit_yield_pct': 49.99016, 'profit_share_of_total_unit_profit': 0.388986}`
- Top season contribution: `{'season': 'NHL 2017-18', 'bets': 68, 'wins': 40, 'unit_profit': 8.991972, 'unit_yield_pct': 13.223488, 'profit_share_of_total_unit_profit': 0.411581}`
- Top side×odds contribution: `{'side_odds': 'home|1.75-2.00', 'bets': 45, 'wins': 29, 'unit_profit': 8.72872, 'unit_yield_pct': 19.397155, 'profit_share_of_total_unit_profit': 0.399532}`

## 8. Stop/downgrade rule evaluation

- Decision: **stop/downgrade**
- Triggered rules: `[{'rule': 'remove_cumulative_top_5_teams', 'reason': 'one-percent yield collapsed to zero or negative after removing cumulative top five teams', 'unit_yield_pct_1pct': -2.758464, 'bets': 269}, {'rule': 'remove_cumulative_top_10_teams', 'reason': 'one-percent yield collapsed to zero or negative after removing cumulative top ten teams', 'unit_yield_pct_1pct': -11.542911, 'bets': 181}]`

## 9. Hypothesis verdicts

- home_side_artifact: **plausible** confidence **medium**. Evidence: remove-home one-percent unit yield = 1.71%
- joint_side_plus_odds_artifact: **plausible** confidence **medium**. Evidence: top side×odds cell = {'side_odds': 'home|1.75-2.00', 'bets': 45, 'wins': 29, 'unit_profit': 8.72872, 'unit_yield_pct': 19.397155, 'profit_share_of_total_unit_profit': 0.399532}
- mid_odds_artifact: **plausible** confidence **medium**. Evidence: remove-1.75-to-2.00 one-percent unit yield = 4.04%
- market_baseline_artifact: **contradicted** confidence **medium**. Evidence: controls within 1pp/equal-or-better tolerance = []
- top_team_artifact: **confirmed** confidence **high**. Evidence: remove-Winnipeg one-percent unit yield = 4.33%; triggered top-team rules = [{'rule': 'remove_cumulative_top_5_teams', 'reason': 'one-percent yield collapsed to zero or negative after removing cumulative top five teams', 'unit_yield_pct_1pct': -2.758464, 'bets': 269}, {'rule': 'remove_cumulative_top_10_teams', 'reason': 'one-percent yield collapsed to zero or negative after removing cumulative top ten teams', 'unit_yield_pct_1pct': -11.542911, 'bets': 181}]
- residual_distributed_anomaly: **contradicted** confidence **high**. Evidence: stop/downgrade rules triggered = 2

## 10. Checks not run or limited

- Raw-American impossible-pair validation remains blocked because the normalized source lacks raw American moneyline columns.
- Archived odds timing, live availability, line movement, account constraints, and sportsbook executability remain outside Cycle 3.
- Market-only EV calibration remains outside this cycle; same-game market favorite/underdog and side controls were used as practical matched controls.

## 11. Recommended next action

Hand off this evidence packet to `llm-result-critic`. The experiment-designer decision is stop/downgrade rather than upgrade to a deployable edge claim if any frozen stop/downgrade rule triggered.
