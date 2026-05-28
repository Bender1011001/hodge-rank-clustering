# Cycle 2 final report: NHL rolling walk-forward sportsbook validation

## Executive verdict

Cycle 2 **failed** the frozen pre-registered success rule. The selected historical NHL pocket stayed positive in aggregate after conservative return haircuts, but the result is too concentrated and drawdown-fragile to support any claim that the system can beat sportsbooks.

The useful finding is narrower: Cycle 2 produced a historically positive, concentration-failed anomaly worth one bounded diagnostic Cycle 3. The next cycle should test whether the signal survives after isolating home-side, mid-odds, and top-team artifacts.

## 1. Cycle objective

The objective was to test whether the historically positive strict NHL Hodge-vs-market pocket survived frozen chronological validation, NHL odds quarantine, conservative decimal-odds return haircuts, and identical-game market baselines. The pre-registration explicitly framed the work as historical quantitative validation, not live betting, account automation, or betting advice. Source: [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:5).

## 2. What was done and what was frozen

What was done:

1. Confirmed that the frozen Cycle 2 pre-registration artifacts existed before the result summary: [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:1) and [`scratch/nhl_cycle2_preregistration.json`](scratch/nhl_cycle2_preregistration.json:1).
2. Summarized the existing walk-forward runner, tests, results, baselines, slippage outputs, and concentration outputs.
3. Recorded the critic verdict as a frozen-rule failure, not a sportsbook-edge proof.
4. Converted the highest-value follow-up into one bounded Cycle 3 seed.

Frozen before evaluation:

| Area | Frozen rule | Evidence |
|---|---|---|
| Population | NHL-only, two-way moneyline, completed games after quarantine and sufficient prior history. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:9) |
| Quarantine | Exclude malformed teams, scores, prices, duplicates, impossible raw-American pairs when raw columns exist, and overround outside the frozen range. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:16) |
| Replay | Chronological no-future feature generation, 300-game warmup, 760-game rolling training window, same-date games added only after slate prediction. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:31) |
| Threshold grid | Hodge edge thresholds 0.15, 0.18, 0.20, 0.25 and EV thresholds 0.05, 0.08, 0.10. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:50) |
| Selection | Select thresholds on prior tune seasons only, require at least 50 tune bets, then apply once to the next untouched test season. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:57) |
| Staking and haircuts | Flat start-of-day bankroll staking with same-day exposure cap; evaluate zero, one, two, and three percent return haircuts. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:72) |
| Baselines | Same-game market favorite, underdog, home, away, Hodge-only, contrarian, market-only calibration if feasible, and odds-band matched random controls. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:80) |
| Success gates | Positive one-percent yield, non-negative two-percent yield, majority baseline wins, enough windows, at least two positive windows, no excessive concentration, and acceptable drawdown versus market baseline. | [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:109) |

## 3. Files changed or inspected

Written in this report cycle:

- [`scratch/nhl_cycle2_final_report.md`](scratch/nhl_cycle2_final_report.md)

Primary artifacts inspected and summarized:

- [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md)
- [`scratch/nhl_cycle2_preregistration.json`](scratch/nhl_cycle2_preregistration.json)
- [`scratch/nhl_cycle2_walkforward.py`](scratch/nhl_cycle2_walkforward.py)
- [`scratch/test_nhl_cycle2_walkforward.py`](scratch/test_nhl_cycle2_walkforward.py)
- [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json)
- [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md)
- [`scratch/nhl_cycle2_concentration.json`](scratch/nhl_cycle2_concentration.json)
- [`scratch/nhl_cycle2_baselines.csv`](scratch/nhl_cycle2_baselines.csv)
- [`scratch/nhl_cycle2_slippage.csv`](scratch/nhl_cycle2_slippage.csv)
- [`context.md`](context.md:89)

## 4. Commands and checks run

The report-writing pass did not rerun the walk-forward experiment. It summarized the existing evidence packet and its recorded checks:

| Check | Recorded command/action | Evidence |
|---|---|---|
| Red test before implementation | Python test runner against [`scratch/test_nhl_cycle2_walkforward.py`](scratch/test_nhl_cycle2_walkforward.py) failed with missing module, confirming the expected red state. | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:21) |
| Post-implementation unit check | Python test runner against [`scratch/test_nhl_cycle2_walkforward.py`](scratch/test_nhl_cycle2_walkforward.py) after implementation. | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:22) |
| Walk-forward run | Python runner against [`scratch/nhl_cycle2_walkforward.py`](scratch/nhl_cycle2_walkforward.py). | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:23) |
| Compile check | Python compile check over [`scratch/nhl_cycle2_walkforward.py`](scratch/nhl_cycle2_walkforward.py) and [`scratch/test_nhl_cycle2_walkforward.py`](scratch/test_nhl_cycle2_walkforward.py). | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:24) |

## 5. Evidence summary

### Aggregate slippage results

| Return haircut | Bets | Wins | Win rate | Unit yield | Max drawdown | Source |
|---:|---:|---:|---:|---:|---:|---|
| Zero percent | 325 | 182 | 56.00% | 7.23% | 11.91% | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:52) |
| One percent | 325 | 182 | 56.00% | 6.72% | 12.28% | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:53) |
| Two percent | 325 | 182 | 56.00% | 6.21% | 12.66% | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:54) |
| Three percent | 325 | 182 | 56.00% | 5.70% | 13.03% | [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:55) |

### Window and baseline summary

| Metric | Result | Evidence |
|---|---:|---|
| Completed windows | 7 | [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1825) |
| Positive windows after one-percent haircut | 5 | [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1827) |
| Beat best market baseline windows | 4 of 7 | [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1817) |
| Beat odds-band random-control mean windows | 6 of 7 | [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1817) |
| Selected threshold pair | Edge 0.15 and EV 0.05 in all completed windows | [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1821) |

### Concentration summary

| Slice | Top contributor | Profit share | Interpretation | Evidence |
|---|---|---:|---|---|
| Season | NHL 2021 | 41.25% | Below the frozen 60% single-season failure threshold, but still a large regime contribution. | [`scratch/nhl_cycle2_concentration.json`](scratch/nhl_cycle2_concentration.json:4) |
| Odds band | 1.75 to 2.00 | 61.44% | Strong mid-odds dependence; below the 80% concentration gate but central to Cycle 3. | [`scratch/nhl_cycle2_concentration.json`](scratch/nhl_cycle2_concentration.json:69) |
| Side | Home | 80.679% | Fails the frozen concentration gate. | [`scratch/nhl_cycle2_concentration.json`](scratch/nhl_cycle2_concentration.json:114) |
| Team | Winnipeg | 41.40% | Not a gate failure alone, but too large to ignore. | [`scratch/nhl_cycle2_concentration.json`](scratch/nhl_cycle2_concentration.json:136) |

### Frozen rule evaluation

The positive gates passed: enough eligible windows, enough positive windows, positive one-percent aggregate yield, non-negative two-percent aggregate yield, and majority wins versus both best market baseline and random-control mean. Source: [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1824).

The failure gates also triggered: the no-dominant-slice gate failed, and the selected max drawdown comparison against the best market baseline failed. Source: [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1833).

Final label: **failure** with **medium** confidence. Source: [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1837).

## 6. Why Cycle 2 failed despite positive aggregate returns

Cycle 2 failed because the frozen success rule required both profitability and robustness. The aggregate returns were positive after one-percent and two-percent return haircuts, but robustness failed in two material ways.

First, the profit was overly concentrated. Home-side selections accounted for 80.679% of the one-percent haircut profit, which violated the frozen concentration rule. The mid-odds and Winnipeg pockets were not standalone gate failures, but they increase the likelihood that the result is a structural artifact rather than a stable edge.

Second, the selected strategy did not pass the frozen drawdown comparison against the best same-game market baseline. A strategy that is profitable only after taking worse drawdown than simple market baselines by the frozen tolerance does not qualify as a validated sportsbook edge.

The threshold behavior also weakens the interpretation. Every completed fold selected the same lowest threshold pair, edge 0.15 and EV 0.05. That is not invalid by itself, but it suggests Cycle 3 should test whether the apparent signal is merely the broadest available exposure to home and mid-odds slices.

## 7. Allowed and disallowed claims

### Allowed claims

- Cycle 2 had frozen pre-registration artifacts before evaluation: [`scratch/nhl_cycle2_preregistration.md`](scratch/nhl_cycle2_preregistration.md:1) and [`scratch/nhl_cycle2_preregistration.json`](scratch/nhl_cycle2_preregistration.json:1).
- The historical selected NHL bets were positive in aggregate after one-percent and two-percent return haircuts: [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:48).
- The frozen Cycle 2 success criteria failed because of concentration and drawdown gates: [`scratch/nhl_cycle2_walkforward_results.json`](scratch/nhl_cycle2_walkforward_results.json:1833).
- The result is a historically positive, concentration-failed anomaly worth one bounded diagnostic cycle.

### Disallowed claims

- Do not claim this proves the system can beat sportsbooks.
- Do not claim the strategy is live-tradable, executable at archived odds, or suitable for automated betting.
- Do not claim the raw-American impossible-pair quarantine was fully validated; the normalized source lacked raw American columns for that check.
- Do not claim market-only expected-value calibration was completed; it was skipped as not feasible from closing odds alone in this artifact set. Source: [`scratch/nhl_cycle2_experiment_report.md`](scratch/nhl_cycle2_experiment_report.md:76).
- Do not use the excluded incomplete 2022 to 2023 season as validation support.
- Do not market the result as betting advice, a guaranteed edge, or a deployable bot.

## 8. Responsible-use caveats

This is historical research, not financial advice or betting advice. The odds archive does not prove prices were timestamped, available, or executable at decision time. The evidence does not address live bet limits, line movement, account restrictions, latency, legal restrictions, sportsbook terms, or responsible gambling risks. Any future work should remain framed as quantitative validation and risk analysis unless live-executable evidence is separately collected.

## 9. Decision: retest

Decision: **retest**. Continue only to one bounded diagnostic Cycle 3. Do not proceed toward deployment, monetization as a profitable betting system, or live wagering.

## 10. Confidence: medium

Confidence: **medium**. The artifacts are sufficient to support the failure label and the bounded next diagnostic. Confidence is not high because archived timing and raw-American source checks remain unresolved, and Cycle 3 is needed to determine whether the positive aggregate collapses under slice ablations and matched controls.

## 11. Next-cycle seed objective

Cycle 3 seed objective: isolate whether the Cycle 2 positive aggregate is a home-side, mid-odds, or top-team artifact by running leave-slice ablations and side-plus-odds matched controls on the identical selected-game universe.

Minimum Cycle 3 design:

1. Freeze the diagnostic plan before running new metrics.
2. Recompute Cycle 2 selected-bet performance after removing home selections, away selections, each major odds band, and top team contributors, starting with Winnipeg.
3. Build side-plus-odds matched controls that preserve home or away status and odds-band exposure on the same dates and games when possible.
4. Compare the selected strategy against matched market favorite, matched market underdog, home-side-only, away-side-only, and random controls.
5. Stop or downgrade further if positive yield collapses outside home or mid-odds slices, or if matched controls explain the result.

## 12. Handoff to LLM Loop Coordinator

Handoff target: LLM Loop Coordinator.

Continue, but pivot the next cycle from validation toward anomaly isolation. The coordinator should seed Cycle 3 with the objective above and keep the stopping threshold strict: if leave-slice ablations or side-plus-odds matched controls explain the profit, end the sportsbook-edge loop with a negative deployability conclusion.
