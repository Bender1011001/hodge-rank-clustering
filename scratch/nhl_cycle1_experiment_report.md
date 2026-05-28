# Cycle 1 NHL strict sportsbook edge experiment report

## Scope

Cycle 1 tested whether the strict NHL historical sportsbook edge remains defensible as a Hodge-vs-market signal or is better treated as a post-hoc/fragile artifact. All new experiment outputs were written under `scratch/`; generated `site/data/` artifacts were read but not overwritten.

## Hypothesis tested

Primary smoke tests targeted the ranked hypotheses from the cycle handoff:

1. H2: post-hoc threshold and multiple-testing artifact.
2. H4: season/regime dependence.
3. H5: favorite/underdog/home-away/odds-band exposure artifact.
4. H6: slippage/archive timing fragility.
5. H3: data-quality/source artifact.
6. H7: calibration/model-spec mismatch.
7. H1: stable residual signal.

## Experiment performed

1. Ran the requested alternate NHL market-residual chronological split smoke tests:
   - `python scripts\hodge_market_residual_strategy.py --sports NHL --train-frac 0.50 --tune-frac 0.25 --output scratch\hodge_market_residual_strategy_nhl_split50_25.json`
   - `python scripts\hodge_market_residual_strategy.py --sports NHL --train-frac 0.70 --tune-frac 0.15 --output scratch\hodge_market_residual_strategy_nhl_split70_15.json`
2. Added and ran a scratch-only supplemental audit script that reads existing NHL CSV odds, strict NHL stored bets, and residual artifacts:
   - `python scratch\nhl_edge_supplemental_audit.py`
   - `python -m compileall scratch\nhl_edge_supplemental_audit.py`

## Files changed or created

- Created `scratch/hodge_market_residual_strategy_nhl_split50_25.json`.
- Created `scratch/hodge_market_residual_strategy_nhl_split70_15.json`.
- Created `scratch/nhl_edge_supplemental_audit.py`.
- Created `scratch/nhl_edge_supplemental_audit.json`.
- Created `scratch/nhl_edge_supplemental_audit.md`.
- Created `scratch/nhl_cycle1_experiment_report.md`.
- Updated `context.md` with a short project log entry.

## Commands/checks run

1. `python scripts\hodge_market_residual_strategy.py --sports NHL --train-frac 0.50 --tune-frac 0.25 --output scratch\hodge_market_residual_strategy_nhl_split50_25.json && python scripts\hodge_market_residual_strategy.py --sports NHL --train-frac 0.70 --tune-frac 0.15 --output scratch\hodge_market_residual_strategy_nhl_split70_15.json`
2. `python scratch\nhl_edge_supplemental_audit.py && python -m compileall scratch\nhl_edge_supplemental_audit.py`

## Raw or summarized results

### Residual split smoke tests

| artifact | train_frac | tune_frac | tune bets | tune yield % | selected edge | selected min_ev | test window | test bets | test win % | test yield % | test max DD % |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `scratch/hodge_market_residual_strategy_nhl_split50_25.json` | 0.50 | 0.25 | 657 | -1.43 | 0.0 | 0.0 | 2019-04-10..2022-11-27 | 1185 | 55.44 | -4.03 | 34.91 |
| `scratch/hodge_market_residual_strategy_nhl_split70_15.json` | 0.70 | 0.15 | 630 | -6.43 | 0.0 | 0.0 | 2020-01-03..2022-11-27 | 717 | 54.25 | -1.76 | 26.08 |
| `site/data/hodge_market_residual_strategy_nhl.json` | 0.60 | 0.20 | 582 | -3.56 | 0.0 | 0.0 | 2019-09-25..2022-11-27 | 940 | 57.45 | -1.77 | 27.72 |

Observed fact: all three chronological residual validations chose the degenerate lowest thresholds, `edge_threshold=0.0` and `min_ev=0.0`, because tune performance was negative under eligible thresholds. All three untouched tests lost money on yield.

### Odds quarantine and matching

- NHL CSV rows: 11,303.
- Overround: mean 1.032936, median 1.033375, p95 1.047079, max 1.050215.
- Quarantine count: one row over 1.05 overround; no rows over 1.08/1.10, no underround rows, no missing or invalid NHL home/away odds were counted.
- Duplicate `(date, away_team, home_team)` keys: 0.
- Strict NHL stored bet to CSV match quality: 474/474 matched, 0 misses.

### Strict NHL stored-bet slippage haircuts

Same stored selections replayed with 1% flat staking, 5% max same-day exposure, and decimal odds haircuts:

| haircut | bets | wins | win % | final bankroll | yield % | max DD % |
|---:|---:|---:|---:|---:|---:|---:|
| 0% | 474 | 264 | 55.70 | 1236.99 | 5.03 | 20.52 |
| 1% | 474 | 264 | 55.70 | 1177.59 | 3.86 | 21.70 |
| 2% | 474 | 264 | 55.70 | 1121.04 | 2.70 | 22.85 |
| 3% | 474 | 264 | 55.70 | 1067.19 | 1.53 | 23.99 |

Observed fact: simple 1%-3% odds haircuts reduce but do not erase the stored strict NHL profit. This does not resolve archive timing or executability.

### Season and era contribution

| era | bets | wins | win % | profit | staked | yield % |
|---|---:|---:|---:|---:|---:|---:|
| early_2013_2016 | 199 | 103 | 51.76 | -144.80 | 1857.24 | -7.80 |
| middle_2017_2019 | 180 | 105 | 58.33 | 235.14 | 1753.95 | 13.41 |
| late_2020_2022 | 95 | 56 | 58.95 | 146.64 | 1098.55 | 13.35 |

Observed fact: the strict NHL stored-bet profit is concentrated after the early 2013-2016 period.

### Same-window simple baselines on strict bet games

On the same 474 matched strict-bet games:

| strategy | bets | wins | win % | final bankroll | yield % | max DD % |
|---|---:|---:|---:|---:|---:|---:|
| stored strict Hodge selection | 474 | 264 | 55.70 | 1236.99 | 5.03 | 20.52 |
| always home | 474 | 264 | 55.70 | 1017.34 | 0.35 | 15.61 |
| always away | 474 | 210 | 44.30 | 684.15 | -8.78 | 36.05 |
| market favorite | 474 | 273 | 57.59 | 843.70 | -3.45 | 26.64 |
| market underdog | 474 | 202 | 42.62 | 839.56 | -3.97 | 30.58 |

Observed fact: the same-window baselines did not reproduce the stored strict Hodge yield. Market favorite had higher win rate but lost on prices.

### Exposure decomposition

- By side: away 232 bets, 50.00% wins, +0.49% yield; home 242 bets, 61.16% wins, +9.31% yield.
- Favorite/underdog: favorite 270 bets, 61.85% wins, +3.89% yield; underdog 204 bets, 47.55% wins, +6.53% yield.
- Selected odds bands: below 1.50 yielded -4.31%; 1.50-1.75 yielded -1.06%; 1.75-2.00 yielded +10.13%; 2.00+ yielded +8.32%.
- Model-edge bands: 0.15-0.18 yielded +7.20%; 0.18-0.22 yielded -0.78%; 0.22-0.30 yielded +10.07%; 0.30+ yielded +8.08% on only 13 bets.

## Result label by hypothesis

| hypothesis | status | evidence |
|---|---|---|
| H2: post-hoc threshold/multiple-testing artifact | likely | Strict historical NHL is positive, but all residual split validations are negative and select the lowest thresholds after tune weakness. |
| H4: season/regime dependence | likely | Early 2013-2016 period is negative while middle/late eras drive the total profit. |
| H5: exposure artifact | plausible | Profit is not a trivial same-window home/favorite baseline, but it is materially concentrated in home bets and mid/high odds bands. |
| H6: slippage/archive timing fragility | weak signal / partially contradicted | 1%-3% decimal-odds haircuts reduce yield from +5.03% to +1.53% but do not erase it. True archive timing/executability remains unknown. |
| H3: data-quality/source artifact | weakly contradicted | NHL odds quarantine found mostly normal overrounds, zero duplicate keys, and 474/474 strict bets matched to CSV. |
| H7: calibration/model-spec mismatch | plausible | Residual Hodge+market split performance is negative despite acceptable straight-up accuracy; full market-only vs Hodge+market calibration by fold was not run. |
| H1: stable residual signal | contradicted | Alternate chronological residual splits and canonical residual split are all negative on untouched tests. |

## Checks not run

- Full rolling walk-forward threshold grid: skipped due to scope/time; residual split smoke tests already provided high-information negative evidence.
- Leave-era-out refit: skipped; era contribution was computed from stored bet records only.
- Market-only vs Hodge+market calibration metrics by fold: skipped; would require model instrumentation beyond scratch-only summary.
- Archive timing/executability proof: blocked by lack of timestamped odds snapshots and no live sportsbook access by design.

## Confidence level

Medium. The alternate residual split evidence is direct and negative. Supplemental slippage/quarantine/baseline checks are smoke tests from stored artifacts, useful for triage but not exhaustive validation.

## Recommended next action

Hand off to `llm-result-critic` with the evidence packet. The critic should decide whether the strict NHL pocket should be downgraded from candidate edge to historically interesting but non-defensible betting artifact unless a pre-registered walk-forward/leave-era-out validation produces positive untouched windows.
