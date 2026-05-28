# Cycle 3 Final Report: NHL Anomaly Isolation

Historical quantitative research only; not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.

## 1. Cycle objective

Cycle 3 tested whether the positive NHL selected-bet aggregate carried forward from Cycle 2 was a distributed residual anomaly or a concentrated artifact explainable by side, odds-band, team, side-plus-odds structure, or matched controls. The scope was diagnostic anomaly isolation, not confirmatory validation. The frozen scope used the Cycle 2 selected-bet universe as authoritative, preserved frozen thresholds, and prohibited retuning before applying preregistered stop/downgrade rules.

## 2. Executive verdict

**Decision: stop/downgrade.** Do not continue to Cycle 4. Do not deploy, monetize as profitable betting, or use for live wagering.

The selected aggregate remains historically positive, but it is not a distributed residual anomaly under the frozen Cycle 3 diagnostics. Cumulative top-team removals triggered the frozen stop rule: removing the cumulative top five positive team contributors collapsed one-percent haircut unit yield to **-2.758464%**, and removing the cumulative top ten collapsed it to **-11.542911%**, with residual bet counts still above the weak-signal floor. Top-team concentration explains the positive aggregate enough to stop/downgrade under the frozen rules.

Matched controls did not match or beat the selected yield within the frozen one-percentage-point tolerance in this diagnostic run. That matched-control contradiction is **medium confidence**, not high confidence, because same-game controls only matched odds bands imperfectly and the random-control check used three seeds. Home-side, mid-odds, and joint side-plus-odds artifacts remain plausible contributors rather than disproven explanations.

## 3. What was done

1. Confirmed the Cycle 3 planning and preregistration packet existed before result artifacts.
2. Reconstructed the frozen selected universe from Cycle 2 outputs without threshold retuning.
3. Verified the selected-universe identity against Cycle 2 aggregate metrics.
4. Ran leave-slice ablations for side, odds band, team, cumulative top teams, and side-plus-odds concentration.
5. Ran matched controls: same-game side controls, same-game market favorite/underdog controls, and date/window-aware odds-band random controls.
6. Applied the frozen stop/downgrade rules.
7. Accepted the result-critic wording constraints: stop/downgrade, no deployable sportsbook-edge claim, and no Cycle 4 seed.

## 4. Files changed or inspected

### Written or updated in this reporting step

- [`scratch/nhl_cycle3_final_report.md`](scratch/nhl_cycle3_final_report.md)
- [`context.md`](../context.md)

### Cycle 3 evidence inspected or relied on

- [`scratch/nhl_cycle3_planning_packet.md`](nhl_cycle3_planning_packet.md)
- [`scratch/nhl_cycle3_preregistration.md`](nhl_cycle3_preregistration.md)
- [`scratch/nhl_cycle3_preregistration.json`](nhl_cycle3_preregistration.json)
- [`scratch/nhl_cycle3_diagnostics.py`](nhl_cycle3_diagnostics.py)
- [`scratch/test_nhl_cycle3_diagnostics.py`](test_nhl_cycle3_diagnostics.py)
- [`scratch/nhl_cycle3_diagnostic_results.json`](nhl_cycle3_diagnostic_results.json)
- [`scratch/nhl_cycle3_experiment_report.md`](nhl_cycle3_experiment_report.md)
- [`context.md`](../context.md)

## 5. Commands/checks run

Reported by the experiment-designer and critic:

| Check | Status | Notes |
|---|---:|---|
| `python scratch/test_nhl_cycle3_diagnostics.py` | Passed | 4 tests passed. |
| `python scratch/nhl_cycle3_diagnostics.py` | Passed | Generated diagnostic result and experiment report artifacts. |
| `python -m compileall scratch/nhl_cycle3_diagnostics.py scratch/test_nhl_cycle3_diagnostics.py` | Passed | Compile check passed. |
| `git status` inspection | Completed | Noted unrelated or pre-existing untracked and modified artifacts. |
| Result-critic artifact extraction and timestamp checks | Completed | Read-only review; no full rerun. |

## 6. Selected-universe identity check

| Metric | Expected | Actual | Result |
|---|---:|---:|---:|
| Bets | 325 | 325 | Pass |
| Wins | 182 | 182 | Pass |
| Win rate | 56.00% | 56.00% | Pass |
| One-percent haircut unit yield | 6.72% | 6.722272% | Pass within tolerance |
| Two-percent haircut unit yield | 6.21% | 6.209926% | Pass within tolerance |

Selected aggregate under one-percent haircut: 325 bets, 182 wins, 56.00% win rate, +6.722272% unit yield, +22.637933% bankroll return, 12.284308% max drawdown. Under two-percent haircut: +6.209926% unit yield and +20.630917% bankroll return.

## 7. Ablation results

| Ablation | Bets | Wins | 1% unit yield | 2% unit yield | 1% max drawdown | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Selected universe | 325 | 182 | +6.72% | +6.21% | 12.28% | Positive aggregate identity confirmed. |
| Remove home selections | 171 | 87 | +1.71% | +1.19% | 15.74% | Home-side artifact plausible, but not sufficient alone to collapse yield. |
| Remove away selections | 154 | 95 | +12.29% | +11.78% | 4.27% | Positive result concentrated more heavily on home selections. |
| Remove odds band 1.75-2.00 | 234 | 126 | +4.04% | +3.53% | 13.89% | Mid-odds artifact plausible, not individually decisive. |
| Remove odds band 2.00-2.50 | 236 | 135 | +3.97% | +3.50% | 6.52% | Mid-odds structure plausible, not individually decisive. |
| Remove Winnipeg | 308 | 168 | +4.33% | +3.83% | 12.90% | Top-team artifact begins to reduce yield. |
| Remove cumulative top 1 team | 308 | 168 | +4.33% | +3.83% | 12.90% | Still positive. |
| Remove cumulative top 3 teams | 294 | 155 | +0.60% | +0.11% | 14.99% | Weak residual. |
| Remove cumulative top 5 teams | 269 | 138 | -2.76% | -3.22% | 14.69% | Frozen stop/downgrade trigger fired. |
| Remove cumulative top 10 teams | 181 | 84 | -11.54% | -11.97% | 23.13% | Frozen stop/downgrade trigger fired. |

## 8. Matched-control results

| Control | Bets | Wins | 1% unit yield | Delta vs selected | 1% max drawdown | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Home only | 325 | 179 | +0.05% | 6.67 pp | 11.85% | Did not match selected within 1 pp. |
| Market favorite | 325 | 188 | -2.04% | 8.76 pp | 28.47% | Did not match selected within 1 pp. |
| Date/window odds-band random seed 7 | 325 | 164 | -2.57% | 9.29 pp | 19.95% | Did not match selected within 1 pp. |
| Market underdog | 325 | 136 | -5.74% | 12.46 pp | 29.34% | Did not match selected within 1 pp. |
| Date/window odds-band random seed 17 | 325 | 157 | -5.84% | 12.56 pp | 29.18% | Did not match selected within 1 pp. |
| Away only | 325 | 146 | -7.23% | 13.95 pp | 30.41% | Did not match selected within 1 pp. |
| Date/window odds-band random seed 29 | 325 | 148 | -12.57% | 19.29 pp | 38.21% | Did not match selected within 1 pp. |

Matched controls did not explain the selected yield in this frozen diagnostic pass. Confidence is **medium** because same-game controls only approximately matched selected odds bands and the random-control sample used three seeds.

## 9. Concentration and hypothesis verdicts

### Concentration summary

| Slice | Top contributor | Bets | Wins | Unit yield | Profit share |
|---|---|---:|---:|---:|---:|
| Side | Home | 154 | 95 | +12.290444% | 86.6341% |
| Odds band | 2.00-2.50 | 89 | 47 | +14.022135% | 57.1222% |
| Team | Winnipeg | 17 | 14 | +49.990160% | 38.8986% |
| Season | NHL 2017-18 | 68 | 40 | +13.223488% | 41.1581% |
| Side × odds | Home × 1.75-2.00 | 45 | 29 | +19.397155% | 39.9532% |

### Hypothesis verdicts

| Hypothesis | Verdict | Confidence | Evidence summary |
|---|---|---|---|
| Home-side artifact | Plausible | Medium | Removing home selections reduced one-percent unit yield to +1.71%, but did not collapse it. |
| Joint side-plus-odds artifact | Plausible | Medium | Top side-plus-odds cell, home 1.75-2.00, carried 45 bets, 29 wins, +19.397155% unit yield, and 39.9532% profit share. |
| Mid-odds artifact | Plausible | Medium | Removing 1.75-2.00 left +4.04%; removing 2.00-2.50 left +3.97%. |
| Market-baseline artifact | Contradicted in this diagnostic run | Medium | No matched control equaled or beat selected within the frozen one-percentage-point tolerance; caveats apply. |
| Top-team artifact | Confirmed | High | Cumulative top-five and top-ten team removals triggered frozen stop/downgrade rules. |
| Residual distributed anomaly | Contradicted within Cycle 3 scope | High | Positive aggregate collapses under cumulative top-team removal while residual counts remain above the weak-signal floor. |

## 10. Evidence summary

### Confirmed

- Cycle 3 planning, preregistration, runner, tests, diagnostic JSON, and experiment report exist in `scratch/`.
- Selected-universe identity passed: 325 bets, 182 wins, 56.00% win rate, +6.722272% one-percent unit yield, +6.209926% two-percent unit yield.
- Frozen thresholds were preserved at edge threshold 0.15 and minimum EV 0.05; no retuning is indicated by the artifacts.
- Frozen top-team stop/downgrade trigger fired after cumulative top-five and top-ten team removals.
- Result critic accepted the stop/downgrade decision with wording revisions.

### Likely

- Matched controls did not explain selected yield within tolerance in this diagnostic run, but the evidence quality is medium due to control-construction caveats.

### Plausible

- Home-side artifact, mid-odds artifact, and joint side-plus-odds artifact are plausible contributors, not individually decisive and not disproven.

### Contradicted

- The claim that the selected aggregate is a distributed residual anomaly is contradicted within Cycle 3 scope by frozen ablation results.

### Blocked or out of scope

- Raw-American impossible-pair validation remains blocked because normalized data lacks raw moneyline columns.
- Archived odds timing, live availability, line movement, account constraints, sportsbook executability, and market-only EV calibration remain outside Cycle 3.

## 11. Allowed and disallowed claims

### Allowed

- Cycle 3 was a diagnostic anomaly-isolation pass over a frozen historical selected-bet universe.
- The selected historical NHL aggregate was positive before ablation.
- Frozen top-team cumulative removal collapsed the positive aggregate enough to trigger stop/downgrade.
- Matched controls did not match or beat selected within the frozen one-percentage-point tolerance in this run, with medium-confidence caveats.
- The result is best described as a concentrated historical anomaly, not a distributed residual sportsbook edge.

### Disallowed

- Do not claim a deployable sportsbook edge.
- Do not claim this is betting advice or financial advice.
- Do not claim the archived prices were available or executable live.
- Do not claim the model should be used for live wagering, monetized as profitable betting, or deployed as a betting bot.
- Do not claim home-side or mid-odds artifacts were disproven.
- Do not claim the anomaly is impossible; the correct claim is that the distributed residual-anomaly interpretation is contradicted by frozen Cycle 3 ablation results.

## 12. Decision

**Decision:** stop/downgrade.

**Confidence:** high for stop/downgrade under frozen diagnostic rules; medium for matched-control contradiction.

**Rationale:** The positive selected-bet aggregate does not survive cumulative top-team ablation. The frozen top-five and top-ten team removal rules fired, and those rules were preregistered as sufficient to stop/downgrade. Matched controls did not explain the selected yield, but the stronger decision driver is the top-team concentration collapse, not the controls.

## 13. Next-cycle seed objective

No Cycle 4 seed. The loop should stop unless the user explicitly requests a different non-betting objective.

## 14. Handoff to LLM Loop Coordinator

Return control to `llm-loop-coordinator` with no next-cycle seed. The sportsbook-edge loop should stop. The durable conclusion is: Cycle 3 stop/downgrade; no deployment, no live wagering, no monetization as profitable betting, and no deployable sportsbook-edge claim. Any future work should be a separately requested non-betting research objective or a broader data-quality/executability audit framed as historical quantitative research only.
