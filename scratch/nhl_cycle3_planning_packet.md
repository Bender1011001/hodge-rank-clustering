# Cycle 3 diagnostic research planning packet: NHL anomaly isolation

## Planning status

This packet freezes the Cycle 3 diagnostic scope before any new ablations, controls, scripts, or performance metrics are run. It is a research plan for the next loop roles, not a validation result.

## 1. Cycle objective

Cycle objective: isolate whether the Cycle 2 positive aggregate NHL selected-bet anomaly is primarily a home-side artifact, a mid-odds artifact, or a top-team contributor artifact, using the identical selected-game universe from [scratch/nhl_cycle2_walkforward_results.json](scratch/nhl_cycle2_walkforward_results.json:1).

Cycle question: On the frozen Cycle 2 selected-game universe, does the one-percent haircut positive yield survive leave-slice ablations and side-plus-odds matched controls strongly enough to remain a distributed anomaly rather than a home, mid-odds, or Winnipeg/top-team concentration artifact?

Non-goals:

- Do not re-run threshold selection to choose a better Cycle 3 strategy.
- Do not change the Cycle 2 selected-bet threshold pair except in explicitly labeled exploratory output that is excluded from the frozen verdict.
- Do not evaluate live execution, line shopping, account limits, latency, sportsbook terms, or deployability.
- Do not make any betting-advice, profitable-bot, or live sportsbook-edge claim.
- Do not use the incomplete 2022 to 2023 season as support beyond preserving whatever frozen Cycle 2 artifact already contains; secondary season-pocket diagnostics must not convert it into validation evidence.

## 2. Current assumptions

- Confirmed: Cycle 2 failed its frozen success rule despite positive aggregate selected-bet returns. The final label is failure with medium confidence in [scratch/nhl_cycle2_final_report.md](scratch/nhl_cycle2_final_report.md:95).
- Confirmed: aggregate selected bets were 325 bets, 182 wins, 56.00 percent win rate, plus 6.72 percent unit yield at a one-percent return haircut and plus 6.21 percent at a two-percent haircut in [scratch/nhl_cycle2_final_report.md](scratch/nhl_cycle2_final_report.md:67).
- Confirmed: robustness gates failed because home-side profit share was 80.679 percent and selected max drawdown failed the comparison against the best market baseline in [scratch/nhl_cycle2_final_report.md](scratch/nhl_cycle2_final_report.md:86) and [scratch/nhl_cycle2_final_report.md](scratch/nhl_cycle2_final_report.md:95).
- Confirmed: the dominant Cycle 2 concentration candidates are home side, the 1.75 to 2.00 odds band, and Winnipeg/top-team contributors in [scratch/nhl_cycle2_walkforward_results.json](scratch/nhl_cycle2_walkforward_results.json:1461) and [scratch/nhl_cycle2_walkforward_results.json](scratch/nhl_cycle2_walkforward_results.json:1508).
- Likely: the lowest threshold pair, edge 0.15 and EV 0.05, selected in all seven completed windows may indicate broad exposure rather than a robust residual edge.
- Plausible: side-plus-odds matched controls may explain most or all of the apparent positive selected yield.
- Unknown: raw-American impossible-pair validation remains unavailable because the normalized source lacks raw American odds columns.
- Unknown: archived odds timing, live availability, account limits, and closing/opening line movement remain outside this cycle.

## 3. Files and areas likely involved

Authoritative selected-game universe:

- [scratch/nhl_cycle2_walkforward_results.json](scratch/nhl_cycle2_walkforward_results.json:1): the frozen Cycle 2 results object and only authoritative source for the Cycle 3 selected-game universe. The universe is the 325 selected bets recorded by Cycle 2 under the frozen edge 0.15 and EV 0.05 threshold pair.

Evidence and context to inspect:

- [scratch/nhl_cycle2_final_report.md](scratch/nhl_cycle2_final_report.md:1): final Cycle 2 interpretation, allowed claims, disallowed claims, and Cycle 3 seed.
- [scratch/nhl_cycle2_preregistration.md](scratch/nhl_cycle2_preregistration.md:1): frozen Cycle 2 population, replay, thresholds, staking, baselines, and success gates.
- [scratch/nhl_cycle2_preregistration.json](scratch/nhl_cycle2_preregistration.json:1): machine-readable Cycle 2 preregistration.
- [scratch/nhl_cycle2_walkforward.py](scratch/nhl_cycle2_walkforward.py:1): deterministic reconstruction reference if later roles need to recover selected-bet rows, side rows, or per-game controls from the frozen configuration.
- [scratch/test_nhl_cycle2_walkforward.py](scratch/test_nhl_cycle2_walkforward.py:1): existing test reference for Cycle 2 runner behavior.
- [scratch/nhl_cycle2_concentration.json](scratch/nhl_cycle2_concentration.json:1): existing concentration evidence to seed expected ablation slices, not a substitute for Cycle 3 ablation results.
- [scratch/nhl_cycle2_baselines.csv](scratch/nhl_cycle2_baselines.csv:1): existing baseline output for comparison definitions.
- [scratch/nhl_cycle2_slippage.csv](scratch/nhl_cycle2_slippage.csv:1): existing haircut output for aggregate reference.
- [context.md](context.md:89): durable project memory for Cycle 2 handoff and caveats.

Artifacts later modes should create or update:

- [scratch/nhl_cycle3_preregistration.md](scratch/nhl_cycle3_preregistration.md:1): frozen diagnostic preregistration written before running metrics.
- [scratch/nhl_cycle3_preregistration.json](scratch/nhl_cycle3_preregistration.json:1): machine-readable diagnostic plan.
- Suggested later evidence artifacts, if implemented by the experiment designer: [scratch/nhl_cycle3_diagnostics.py](scratch/nhl_cycle3_diagnostics.py:1), [scratch/test_nhl_cycle3_diagnostics.py](scratch/test_nhl_cycle3_diagnostics.py:1), [scratch/nhl_cycle3_diagnostic_results.json](scratch/nhl_cycle3_diagnostic_results.json:1), and [scratch/nhl_cycle3_experiment_report.md](scratch/nhl_cycle3_experiment_report.md:1).

## 4. Candidate checks or commands

Planner-mode instruction: do not run these checks now. They are candidate checks for later hypothesis and experiment modes.

Minimum later-mode verification checks:

1. Preregistration presence check: verify [scratch/nhl_cycle3_preregistration.md](scratch/nhl_cycle3_preregistration.md:1) and [scratch/nhl_cycle3_preregistration.json](scratch/nhl_cycle3_preregistration.json:1) exist before any diagnostic result artifact is written.
2. Selected-universe identity check: reconstruct or load exactly the 325 Cycle 2 selected bets, verify the 325 bet count, 182 wins, one-percent haircut unit yield near 6.72 percent, and two-percent haircut unit yield near 6.21 percent before running any slice metrics.
3. No-retuning check: assert every frozen verdict diagnostic uses the Cycle 2 selected threshold pair edge 0.15 and EV 0.05 and does not select new thresholds.
4. Leave-slice ablation checks: compute selected performance after removing each frozen slice listed below.
5. Matched-control checks: compute side-plus-odds controls preserving selected-game universe/date/window exposure as closely as possible.
6. Report check: write a concise diagnostic report that separates confirmed results from likely, plausible, weak, contradicted, blocked, and exploratory findings.

Target runtime budget for later-mode checks: normally 10 minutes or less on the existing local artifact set.

## 5. Realistic success threshold

Frozen comparison metrics for every selected, ablated, and control cohort:

- Bets.
- Wins.
- Win rate.
- Unit profit and unit yield under at least one-percent and two-percent return haircuts.
- Max drawdown, if reconstructable from selected bet order; if not reconstructable, mark unavailable rather than substituting an unordered proxy.
- Profit share by side, odds band, selected team, and season.
- Selected-vs-control deltas for unit yield and drawdown under one-percent and two-percent haircuts.

Leave-slice ablations to freeze:

- Remove all home selections and recompute on away selections only.
- Remove all away selections and recompute on home selections only.
- Remove each major odds band separately, including the 1.75 to 2.00 odds band. At minimum include less than 1.50, 1.50 to 1.75, 1.75 to 2.00, 2.00 to 2.50, and at least 2.50.
- Remove top team contributors starting with Winnipeg, then the next largest positive-profit team contributors from Cycle 2: St.Louis, Arizona, NYIslanders, Anaheim, Vegas, NYRangers, Carolina, Washington, and Minnesota, subject to available rows.
- Remove cumulative top-team sets as secondary diagnostics: top one, top three, top five, and top ten positive-profit contributors.
- Optionally remove season pockets only as secondary diagnostics: especially NHL 2021, NHL 2017-18, NHL 2019-20, NHL 2018-19, and NHL 2016-17. These must not become the primary Cycle 3 verdict unless side/odds/team diagnostics are inconclusive.

Side-plus-odds matched controls to freeze:

- Matched market favorite: choose the market favorite side from the same selected-game universe where available, preserving date/window and odds band exposure as closely as possible.
- Matched market underdog: choose the market underdog side from the same selected-game universe where available, preserving date/window and odds band exposure as closely as possible.
- Home-only control: choose home sides from the selected-game universe, then stratify or weight by the selected odds-band distribution where possible.
- Away-only control: choose away sides from the selected-game universe, then stratify or weight by the selected odds-band distribution where possible.
- Date/window-aware odds-band random controls: randomize eligible sides within the same date or same walk-forward test window and odds band where possible; if same-date matching is sparse, relax in order to same week, same season, then same completed test window while reporting the relaxation rate.
- All controls should preserve selected-game universe exposure first, then date/window exposure, then side distribution, then odds band. Any failure to preserve a dimension must be reported as a confounder.

Continue threshold for the anomaly-isolation loop:

- Continue only if the one-percent and two-percent haircut selected yield remains positive after removing the home-side slice, after removing the 1.75 to 2.00 odds band, and after removing Winnipeg/top-team slices.
- Continue only if positive yield is not dominated by one side, one odds band, one team cluster, or one season pocket under the same practical concentration logic that failed Cycle 2.
- Continue only if selected cohorts beat matched-control unit yield and are not materially worse on max drawdown within the practical tolerance below.

Practical tolerance:

- Treat a control as effectively equal if its one-percent unit yield is within 1.0 percentage point of the selected cohort or its max drawdown is no more than 2.0 percentage points worse than selected while yield is similar.
- Treat a selected advantage as practically meaningful only if it exceeds matched controls by more than 1.0 percentage point one-percent unit yield and does not take more than 2.0 percentage points worse max drawdown.
- These tolerances are engineering diagnostics, not proof thresholds.

Stop or downgrade rules:

- Stop or downgrade if positive one-percent haircut yield collapses to zero or negative after removing home selections.
- Stop or downgrade if positive one-percent haircut yield collapses to zero or negative after removing the 1.75 to 2.00 odds band.
- Stop or downgrade if positive one-percent haircut yield collapses to zero or negative after removing Winnipeg alone or after removing cumulative top-team contributor sets.
- Stop or downgrade if matched market favorite, matched market underdog, home-only, away-only, or date/window-aware random controls equal or beat selected yield within the 1.0 percentage-point tolerance.
- Stop or downgrade if controls have materially better drawdown by more than 2.0 percentage points while yield is equal or better.
- Stop or downgrade if selected yield survives only in a small or cherry-picked residual subset with too few bets to interpret; use fewer than 50 bets as a weak-signal threshold unless explicitly marked exploratory.
- Continue to Cycle 4 only if positive yield remains distributed across sides, odds bands, and teams, survives the frozen ablations, beats matched controls outside tolerance, and the next question is calibration or executability rather than artifact isolation.

Success, failure, and inconclusive criteria:

- Success for Cycle 3 diagnostic survival: selected one-percent and two-percent haircut yields stay positive after key ablations, matched controls do not equal or beat selected results within tolerance, max drawdown is not materially worse than controls, and no single side, odds band, or team remains the apparent explanation.
- Failure or downgrade: any key artifact slice explains the positive yield, or matched controls equal or beat selected yield/drawdown within tolerance.
- Inconclusive: selected rows, bet order, or matched-control construction cannot be reconstructed closely enough to preserve the 325-bet Cycle 2 universe; in that case, report blocked/inconclusive and do not upgrade the sportsbook claim.

## 6. Main risks and confounders

- Selected-bet rows may need deterministic reconstruction from [scratch/nhl_cycle2_walkforward.py](scratch/nhl_cycle2_walkforward.py:1) because [scratch/nhl_cycle2_walkforward_results.json](scratch/nhl_cycle2_walkforward_results.json:1839) records the selected-bet count but may not include full selected-bet row details in the top-level summary.
- Controls may be sparse when preserving same date, same side, and same odds band simultaneously.
- Home advantage, market favorite status, and mid-odds bands may be correlated; side-only or odds-only ablations can misattribute a joint artifact.
- Team names and aliases must be normalized consistently with Cycle 2 outputs.
- Max drawdown requires chronological selected-bet order and same-day staking reconstruction; if order is unavailable, do not fake drawdown.
- Raw-American impossible-pair checking remains blocked by source columns and should not be treated as resolved.
- Market-only EV calibration and archived odds executability remain outside the Cycle 3 diagnostic plan.
- The Cycle 3 design is intentionally diagnostic, not confirmatory validation for live betting.

## 7. Handoff to Hypothesis Generator

Handoff target: llm-hypothesis-generator.

Generate ranked hypotheses explaining the Cycle 2 positive aggregate using only this frozen Cycle 3 diagnostic scope. The hypotheses should be directly testable by later leave-slice ablations and side-plus-odds matched controls without re-tuning thresholds.

Required hypothesis families:

1. Home-side artifact: the aggregate positive yield is mainly home exposure or home-plus-market structure.
2. Mid-odds artifact: the aggregate positive yield is mainly 1.75 to 2.00 or adjacent odds-band exposure.
3. Top-team artifact: the aggregate positive yield is mainly Winnipeg or cumulative top positive team contributors.
4. Joint side-plus-odds artifact: home and mid-odds exposure jointly explain the result even if either slice alone does not.
5. Market-baseline artifact: matched market favorite, matched market underdog, home-only, away-only, or odds-band random controls explain the selected return.
6. Residual distributed anomaly: the result survives key ablations and controls, which would justify a Cycle 4 calibration/executability question but still not a deployment claim.

The hypothesis generator should produce a ranked hypothesis packet for llm-experiment-designer with explicit predicted ablation/control outcomes, required fields, and failure signatures. It should not run metrics.

Responsible-use wording to preserve in downstream artifacts: this is historical quantitative research only, not betting advice, not financial advice, not a deployable sportsbook-edge claim, and not evidence that archived prices were available or executable live.
