# Cycle 1 final report: NHL moneyline Hodge-vs-market edge validation

## 1. Cycle objective

Validate whether the historically positive strict NHL moneyline artifact is evidence of a deployable Hodge-vs-market sportsbook edge, or whether it should be downgraded as a post-hoc/regime-dependent research pocket.

## 2. Executive verdict

The current evidence does **not** support using this system to beat sportsbooks today. The stored strict NHL artifact remains historically positive, but three chronological market-residual validations are negative, including the canonical residual artifact and two new alternate split tests. The best current explanation is that the strict NHL result is a historically interesting, post-hoc/regime-dependent pocket rather than a stable deployable edge.

Decision: **downgrade and report**. Do **not** claim a live betting bot, sportsbook-beating system, or deployable edge from the current artifacts.

## 3. What was done

- Reviewed the stored strict NHL artifact, which reports 474 bets, 55.70% wins, +5.03% yield, and 20.52% max drawdown in [`site/data/hodge_real_sportsbook_agent_nhl_strict.json`](site/data/hodge_real_sportsbook_agent_nhl_strict.json:45).
- Reviewed the canonical NHL market-residual validation, which selected thresholds only on tune and then lost on untouched test: tune -3.56% and test -1.77% in [`site/data/hodge_market_residual_strategy_nhl.json`](site/data/hodge_market_residual_strategy_nhl.json:64) and [`site/data/hodge_market_residual_strategy_nhl.json`](site/data/hodge_market_residual_strategy_nhl.json:383).
- Reviewed two new alternate NHL residual split smoke tests, both negative on untouched tests: [`scratch/hodge_market_residual_strategy_nhl_split50_25.json`](scratch/hodge_market_residual_strategy_nhl_split50_25.json:383) and [`scratch/hodge_market_residual_strategy_nhl_split70_15.json`](scratch/hodge_market_residual_strategy_nhl_split70_15.json:410).
- Reviewed scratch-only data-integrity, slippage, era-contribution, and same-window baseline checks in [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md:5).
- Reviewed the experiment report and result-critic verdict preserved in [`scratch/nhl_cycle1_experiment_report.md`](scratch/nhl_cycle1_experiment_report.md:107) and [`context.md`](context.md:84).

## 4. Commands/checks run

Commands run during the experiment cycle, as recorded in [`scratch/nhl_cycle1_experiment_report.md`](nhl_cycle1_experiment_report.md:38):

| Purpose | Command or check | Output artifact |
|---|---|---|
| Alternate residual split smoke test | python [`scripts/hodge_market_residual_strategy.py`](scripts/hodge_market_residual_strategy.py) --sports NHL --train-frac 0.50 --tune-frac 0.25 --output [`scratch/hodge_market_residual_strategy_nhl_split50_25.json`](scratch/hodge_market_residual_strategy_nhl_split50_25.json) | [`scratch/hodge_market_residual_strategy_nhl_split50_25.json`](scratch/hodge_market_residual_strategy_nhl_split50_25.json) |
| Alternate residual split smoke test | python [`scripts/hodge_market_residual_strategy.py`](scripts/hodge_market_residual_strategy.py) --sports NHL --train-frac 0.70 --tune-frac 0.15 --output [`scratch/hodge_market_residual_strategy_nhl_split70_15.json`](scratch/hodge_market_residual_strategy_nhl_split70_15.json) | [`scratch/hodge_market_residual_strategy_nhl_split70_15.json`](scratch/hodge_market_residual_strategy_nhl_split70_15.json) |
| Supplemental audit | python [`scratch/nhl_edge_supplemental_audit.py`](scratch/nhl_edge_supplemental_audit.py) | [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md), [`scratch/nhl_edge_supplemental_audit.json`](scratch/nhl_edge_supplemental_audit.json) |
| Syntax check | python -m compileall [`scratch/nhl_edge_supplemental_audit.py`](scratch/nhl_edge_supplemental_audit.py) | Completed per [`scratch/nhl_cycle1_experiment_report.md`](scratch/nhl_cycle1_experiment_report.md:40) |

No live sportsbook execution, live line scrape, or timestamped odds replay was run.

## 5. Key results table

| Evidence item | Artifact | Result | Interpretation |
|---|---|---|---|
| Stored strict NHL historical strategy | [`site/data/hodge_real_sportsbook_agent_nhl_strict.json`](site/data/hodge_real_sportsbook_agent_nhl_strict.json:45) | 474 bets, 55.70% wins, +5.03% yield, 20.52% max drawdown | Confirmed positive historical pocket. Not enough by itself because thresholds/selection were discovered post hoc. |
| Canonical residual validation | [`site/data/hodge_market_residual_strategy_nhl.json`](site/data/hodge_market_residual_strategy_nhl.json:383) | Tune -3.56%; untouched test 940 bets, -1.77% yield, 27.72% max drawdown | Contradicts a stable out-of-time residual edge. |
| Alternate split 50/25 | [`scratch/hodge_market_residual_strategy_nhl_split50_25.json`](scratch/hodge_market_residual_strategy_nhl_split50_25.json:383) | Tune 657 bets, -1.43%; untouched test 1,185 bets, -4.03% yield, 34.91% max drawdown | Strong negative replication under another chronological split. |
| Alternate split 70/15 | [`scratch/hodge_market_residual_strategy_nhl_split70_15.json`](scratch/hodge_market_residual_strategy_nhl_split70_15.json:410) | Tune 630 bets, -6.43%; untouched test 717 bets, -1.76% yield, 26.08% max drawdown | Negative replication; no split rescue. |
| Odds quarantine and bet matching | [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md:13) | 11,303 NHL rows; zero duplicate date/team keys; 474/474 strict bets matched | Data integrity looks mostly clean; does not explain away the positive stored result. |
| Slippage haircuts | [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md:57) | Stored strict yield falls from +5.03% to +3.86%, +2.70%, +1.53% under 1%, 2%, 3% odds haircuts | Slippage weakens but does not erase stored profit; executability remains unresolved. |
| Era contribution | [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md:68) | 2013-2016 -7.80%; 2017-2019 +13.41%; 2020-2022 +13.35% | Profit is regime-concentrated after the early period. |
| Same-window baselines | [`scratch/nhl_edge_supplemental_audit.md`](scratch/nhl_edge_supplemental_audit.md:76) | Market favorite -3.45%; market underdog -3.97%; always home +0.35%; stored Hodge +5.03% | Simple baselines on the same games do not reproduce the stored profit. |

## 6. Hypothesis verdicts H1-H7

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1: Stable residual Hodge-vs-market edge | Contradicted | The canonical residual split and two alternate chronological residual splits are all negative on untouched tests. |
| H2: Post-hoc threshold/multiple-testing artifact | Likely | Strict NHL is positive, but out-of-time residual validations select the lowest thresholds after weak/negative tune performance and then lose on test. |
| H3: Data-quality/source artifact | Weakly contradicted | Odds quarantine found normal-ish overround distribution, zero duplicate date/team keys, and 474/474 strict-bet odds matches. |
| H4: Season/regime dependence | Likely | Early 2013-2016 is negative while 2017-2019 and 2020-2022 drive the stored profit. |
| H5: Favorite/underdog/home-away/odds-band exposure artifact | Plausible | Simple same-window baselines do not explain the profit, but exposure is concentrated in home selections and mid/high odds bands. |
| H6: Slippage/archive timing fragility | Weak signal / unresolved | 1%-3% haircuts reduce but do not erase stored profit. Archived odds timing and real executability remain unknown. |
| H7: Calibration/model-spec mismatch | Plausible | The residual Hodge+market model loses out of time despite historical Hodge signal. Market-only versus Hodge+market calibration by fold was not completed. |

## 7. Evidence summary

Confirmed evidence supports three statements at medium confidence:

1. The strict NHL historical artifact is genuinely positive in the stored replay.
2. The cleaner chronological residual validations are consistently negative.
3. The positive strict result is not explained by obvious duplicate-key data errors or trivial home/favorite baselines, but it is concentrated by era and is not yet executable evidence.

Interpretation: Hodge may still be a useful disagreement/ranking feature, but the current sportsbook edge claim fails the required out-of-time validation bar.

## 8. Responsible-use caveats

- This is historical research, not financial advice or betting advice.
- The current artifacts should not be used to automate live wagering, market sportsbooks, or claim guaranteed sportsbook alpha.
- SportsbookReviewsOnline archives are historical consensus/archive moneyline data, not proof of available executable prices at decision time.
- Odds timing, limits, account restrictions, transaction costs, and rule changes are unresolved.
- A single positive post-hoc historical pocket is insufficient for deployment when stricter untouched chronological validations are negative.

## 9. Decision

Decision: **downgrade and report**.

Status: **proceed to report; no live betting, no bot, no deployable edge claim**.

Rationale: expected value of claiming/deploying is negative under current evidence because stable residual edge is contradicted and archive executability is unknown. The downside of overstating the finding is high; the useful path is to preserve it as a research lead and design a stricter next validation.

## 10. Confidence

Confidence: **medium**.

The negative residual validations are direct and repeated across three chronological splits. Supplemental audits are useful smoke tests but not exhaustive. The archived-odds timing/executability question is still unresolved, so confidence should not be upgraded to high.

## 11. Skipped, blocked, or unresolved checks

- Full pre-registered rolling walk-forward threshold validation was not run.
- Leave-era-out refit was not run.
- Market-only versus Hodge+market calibration and incremental lift by fold were not run.
- Timestamped archived odds availability and live execution realism remain blocked/unknown.
- The report did not overwrite generated [`site/data/`](site/data/) strategy artifacts.

## 12. Next-cycle seed objective

Run a **pre-registered rolling walk-forward NHL validation** that freezes the threshold grid, feature set, bankroll rules, market-only baselines, quarantine rules, and success criteria before evaluation. The next cycle should answer one question: does Hodge add positive out-of-time lift over market-only baselines across multiple rolling NHL windows after odds quarantine and conservative slippage assumptions?

Minimum next-cycle acceptance gates:

- Multiple untouched rolling windows, not one aggregate test.
- Market-only, market-favorite, same-window home/away, and Hodge+market comparisons on identical games.
- Conservative odds haircut/slippage variants included before looking at outcomes.
- Leave-era-out or era-holdout refit to test regime dependence.
- Explicit stop rule: if Hodge+market does not beat market-only on yield and drawdown-adjusted metrics across windows, keep the sportsbook claim downgraded.

## 13. Handoff to LLM Loop Coordinator

Handoff target: LLM Loop Coordinator.

Continue/pivot/stop: **continue, but pivot from edge promotion to pre-registered validation**.

Coordinator seed: Start Cycle 2 by planning the pre-registered rolling walk-forward NHL validation described above. Do not route to implementation of a live betting bot or public edge claim unless Cycle 2 produces positive pre-registered out-of-time evidence.
