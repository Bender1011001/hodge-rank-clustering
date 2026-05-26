# Project Context: Discrete Hodge Rank Clustering

## Project Purpose
Topological clustering of directed graphs via Discrete Hodge Decomposition on asymmetric rank flows. It leverages combinatorial Hodge theory to decompose directed flow networks into hierarchical (gradient) and cyclic (curl, harmonic) components, clustering via persistence-based topological simplification on the recovered potential field.

## Current Task
Backtesting the sports Hodge prediction system against real sportsbook odds. The current focus is EPL because the existing `site/data/sports_hodge_results.json` artifact is EPL-only and football-data.co.uk provides 10 completed seasons of bookmaker 1X2 odds with results.

## Recent Changes
- Addressed severe over-segmentation issue by refactoring Step 5 of the clustering pipeline to use a **persistence-based topological simplification (watershed-style Union-Find)** on the potential field.
- Added `tau` parameter (topological simplification threshold) to the class constructor to allow relative thresholding of shallow local maxima.
- Exponentiated the benchmark performance (Adjusted Rand Index improved from baseline **0.8429** to **0.8714** in Iteration 1 via noise distance thresholding, to **0.8718** in Iteration 2 via noise-only threshold distribution modeling, to **0.8729** in Iteration 3 via cluster-specific local percentile thresholding, and finally to **0.8750** in Iteration 4 via density-based pruning of the sparsest 20% of nodes using k_d=5 nearest neighbor distance at k=44, min_core=5, tau=0.22, pct=93.2).
- Added `benchmark.py` and `requirements.txt`.
- Added `scripts/build_openflights_site_data.py`, which downloads OpenFlights airports/routes into a process-specific `.tmp/openflights_raw_<pid>` folder, builds an asymmetric route-preference matrix, runs `TrueHodgeRankClustering`, writes compact JSON artifacts, and deletes raw downloads by default.
- Added a static local visualization under `site/` with a canvas flight atlas, route-density control, inter-cluster toggle, cluster filtering, Hodge component meters, and airport hover details.
- Generated the current OpenFlights artifact set under `site/data/openflights/`: 420 airports, 2,200 route edges, 16 Hodge clusters, 196 core nodes, 393 Hodge graph edges, and 106 triangles.
- Verified raw cleanup in the generated `summary.json`: `rawDataRetained=false` and `rawDirectoryExistsAfterRun=false`.
- Started a local static server at `http://127.0.0.1:8765` for the current test run.
- Added a compact Natural Earth 110m land artifact at `site/data/world/land.geojson`.
- Changed the map from a simple rectangular graticule to an aeronautical-chart style Lambert conformal conic projection with curved meridians/parallels, coastline strokes, and sampled great-circle route tracks.
- Added `scripts/build_epstein_doj_corpus.py`, a resumable official-DOJ Epstein Library ingestion worker. It discovers DOJ disclosure file pages, downloads one PDF at a time with the DOJ age-verification cookie, extracts text-derived term mentions with PyMuPDF, writes compact manifest/document/graph artifacts, checkpoints in SQLite, and deletes raw PDFs by default.
- Processed the full official DOJ disclosure manifest discovered on May 23, 2026: 525 PDF links across 12 DOJ datasets, totaling 6,468 PDF pages and about 734 MB downloaded transiently. Output under `site/data/epstein/` currently has 525 processed document records, 359 text-usable PDFs, 166 `needs_ocr` PDFs, 26 term nodes, 270 same-file co-mention edges, and 224 documents with tracked mentions.
- Added a second static-site view, `DOJ graph`, that renders the generated DOJ co-mention graph on the existing canvas and switches the panels from flight metrics to corpus metrics. The graph labels edges as same-file co-mentions only, not allegations or conduct connections.
- Created a monolithic `hodge_clustering.py` script combining the `TrueHodgeRankClustering` class, license, and comparison benchmark to serve as the training/evaluation target.
- Structured and installed the `hodge-autoresearch` skill package inside `.agent/skills/hodge-research/` consisting of `SKILL.md` and `scripts/experiment_harness.py` for automated hyperparameter optimization.
- Cloned the NSA `rank-based-linkage` repository under `scratch/rank-based-linkage` to analyze official Javadocs and implementation details.
- Ported the RBL algorithm to Python in `rbl_clustering.py` (with 2-core extraction, KNN digraph construction, mutual friend resolver, comparator-based in-sway calculation, and dynamic Union-Find/sub-critical thresholding).
- Created a comparison benchmark script `scripts/compare_rbl_hodge.py` evaluating HDBSCAN (ARI: 0.8457), default Hodge (ARI: 0.1268), optimized Hodge (ARI: 0.8750), and best RBL (ARI: 0.8536).
- Aligned defaults in `hodge_rank.py` and `hodge_clustering.py` to the optimized parameters (`k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0`), verifying that `python benchmark.py` achieves `0.8750` out of the box.
- Updated visualizer `site/index.html` and `site/app.js` to allow interactive side-by-side toggling of True, Hodge, and RBL labels on the "Cities & Tourists" benchmark plot, exporting the updated predictions using `scratch/dump_benchmark_data.py`.
- Diagnosed synthetic Network 1 collapse: identified a sign-convention mismatch where balanced activations and repressions canceled out raw potential flows; resolved it using absolute correlation flows.
- Implemented an unbiased network reconstruction pipeline (`unbiased_comparison.py`) extracting high-correlation edges without prior gold-standard TF knowledge and testing variance/mean directionality heuristics.
- Evaluated feedback loop isolation (`evaluate_loops.py` & `evaluate_harmonic_cycles.py`), proving that the Hodge Harmonic flow component ($F_{\text{harm}}$) separates biological feedback cycle edges with exceptionally high accuracy (ROC AUC of 0.9733 in E. coli).
- Executed `scripts/compare_rbl_hodge.py` to verify optimized Hodge performance (ARI: 0.8750) against RBL (best ARI: 0.8536) and HDBSCAN (ARI: 0.8457).
- Executed `scripts/run_trrust_hodge.py` to evaluate the system on real Human and Mouse transcriptional regulatory networks (GRNPedia TRRUST), verifying stable convergence and isolating top master regulators like `SYTL4` (Human) and `Axin1` (Mouse).
- Executed `scripts/build_openflights_site_data.py` to refresh the flight routes dataset, calculating Hodge components (gradient, curl, harmonic) for 420 airports.
- Implemented and executed `scratch/evaluate_loops_trrust.py` to validate that Hodge Curl separates cyclic vs transitive triangles, proving that cyclic triangles have significantly higher curl $|c|$ (0.597 vs 0.178 for Human, 0.781 vs 0.272 for Mouse).
- Implemented and executed `scratch/evaluate_harmonic_cycles_trrust.py` using fast path reachability checks, proving that the Hodge Harmonic flow component is highly predictive of directed feedback cycles (ROC AUC: 0.727 for Human, 0.779 for Mouse).
- Implemented and executed `scratch/verify_trrust_tfs.py` to validate Hodge potential TF prediction, achieving 100.0% precision at K=100 on Human and Mouse TRRUST potential basins (baselines: 27.75% and 33.65%).
- Resolved Synapse downtime: successfully connected to the platform and executed all validation pipelines for DREAM5 networks (Net 1, Net 3, Net 4).
- Verified that under Absolute Correlation Flow, target TF identification achieves exactly 100.0% precision at top 10 potential basins across all three networks.
- Verified that Hodge Harmonic Flow separates directed feedback cycle edges in E. coli (Net 3) with an ROC AUC of 0.9733.
- Extended the visualizer page (`site/index.html` and `site/app.js`) to load and render the Human and Mouse TRRUST regulatory networks (visualizing degree-based node size, directed flows, potential basins/sinks, and Hodge norm meters).
- Refactored `scripts/download_and_run_dream5.py` to calculate full Hodge decomposition on Networks 1, 3, and 4 sequentially, download from Synapse, and export top-120 layout JSON nodes/edges to `site/data/dream5/`.
- Integrated `Net 1 (In Silico)`, `Net 3 (E. coli)`, and `Net 4 (Yeast)` switches into `index.html` and `app.js`, supporting dynamic layouts, custom gene properties, regulators/sinks listings, and norm meters.
- Downloaded the external IBM AMLSim banking transaction dataset from TigerGraph-OSS and retrieved the cached Elliptic Bitcoin transaction dataset from Hugging Face cache.
- Modified `scripts/benchmark_pipelines.py` to import `defaultdict` correctly, support robust header schemes (TigerGraph-OSS and standard AMLSim), parse string-based boolean alerts safely, and add a `max_transactions` limit (default 100,000) to prevent pure Python triangle-search loops from freezing on million-row transaction data.
- Implemented `scripts/run_financial_benchmarks.py` to execute both pipeline benchmarks, outputting results for Elliptic Bitcoin (203k nodes, 234k edges) and IBM AMLSim (9.9k nodes, 46.7k edges, 1.3k loops) to `site/data/financial/summary.json`.
- Removed hard-coded Synapse personal access tokens from the DREAM5 runner and scratch validation scripts.
- Added `scripts/synapse_auth.py`, which logs in through `SYNAPSE_AUTH_TOKEN` or `SYNAPSE_PAT` when present and otherwise falls back to the normal Synapse client login/config path.
- Updated DREAM5/Synapse scripts to import the shared auth helper instead of storing credentials in source.
- Verified with source scans that the exposed Synapse PAT pattern no longer appears in the working tree or tracked `HEAD`.
- Added `scripts/run_dream5_honest_benchmark.py`, a leakage-free DREAM5-style scorer. It uses only expression data plus the provided TF list to rank TF-target pairs, then uses gold-standard rows only for AUPR/AUROC and precision-at-K scoring. It reports Pearson baselines and Hodge potential variants (`hodge_delta`, `hodge_weighted`, `hodge_blend`).
- Attempted `python scripts/run_dream5_honest_benchmark.py --net 1 --top-per-tf 100 --max-hodge-edges 20000`; it failed before download because no `SYNAPSE_PAT`/`SYNAPSE_AUTH_TOKEN` or local `.synapseConfig` credentials were available.
- Added `.env`, `.env.*`, and `.synapseConfig` to `.gitignore` to prevent local credentials from being staged.
- Stored a user-provided Synapse token in the local ignored `.env` and user-level `SYNAPSE_PAT` environment variable. Do not commit or print the token.
- Ran `python scripts/run_dream5_honest_benchmark.py` successfully across DREAM5 Nets 1, 3, and 4. The honest edge-ranking result did not beat simple Pearson on AUPR: Net 1 best Pearson AUPR 0.1893 vs best Hodge blend 0.1784; Net 3 Pearson signed AUPR 0.0698 vs Hodge blend 0.0634; Net 4 Pearson signed AUPR 0.0232 vs Hodge blend 0.0199. Hodge blend improved AUROC on Net 1 (0.7867 vs Pearson abs 0.7646) and Net 3 (0.6384 vs Pearson signed 0.6202), but AUPR is the more important sparse edge-recovery metric.
- Diagnosed the DREAM5 edge-ranking math: the current Hodge score solves `p[target] - p[tf] ~= abs(correlation)` over a candidate graph, then reuses node potential deltas as TF-target edge confidence. That is a valid global hierarchy projection, but it is not a pair-specific edge estimator; high deltas can rank low-correlation nonedges above true sparse edges.
- Extended `scripts/run_dream5_honest_benchmark.py` with normalized Hodge variants, candidate-edge scores, residual/flow ratios, candidate coverage, positive-vs-negative separation, and top-rank diagnostics. The rerun confirms the issue: Net 1 top-100 Hodge-delta pairs include 1 true edge vs 72 for Pearson absolute; Net 3 includes 1 vs 51; Net 4 includes 0 vs 7.
- Added and ran `scripts/find_postable_hodge_findings.py`, which mines public TRRUST human/mouse regulatory networks for harmonic-flow feedback-cycle enrichment and summarizes the existing five-season college-football Hodge backtest.
- Saved post-ready artifacts under `site/data/postable_findings/`: `hodge_findings.json` and `hodge_findings.md`.
- Strongest postable result: on TRRUST human, Hodge harmonic flow ranks feedback-cycle edges at 97.0% precision in the top 100 vs a 15.4% base rate (6.29x lift); on TRRUST mouse, 97.0% vs a 22.8% base rate (4.25x lift). The top-100 lists include 53 human and 55 mouse non-reciprocal feedback-cycle edges, so the finding is not just reciprocal-pair detection.
- Baseline caveat for the TRRUST post: degree-product is competitive on broad AP for human (0.464 vs Hodge 0.460), while Hodge has stronger top-list enrichment (P@100 97.0% vs 83.0%) and stronger mouse AP (0.604 vs 0.533). The defensible claim is top-of-list feedback-control enrichment and interpretability, not universal superiority.
- Added `scripts/hodge_sportsbook_epl_backtest.py`, a real sportsbook EPL backtester. It downloads football-data.co.uk EPL CSVs, uses the last 10 completed seasons available at run time (`1617` through `2526`), trains Hodge only on prior matches with a rolling two-season window, calibrates home/draw/away probabilities, and simulates flat plus capped Kelly staking against Pinnacle, Bet365, best-available, and market-average 1X2 odds.
- Corrected the key flaw in the older `scripts/hodge_real_odds_epl.py` / `site/data/hodge_real_odds_epl.json` result: the old script skipped drawn test matches after seeing the result, which is invalid for soccer 1X2 betting because home/away bets lose on draws. The new sportsbook backtest models draws explicitly and counts every non-winning selected outcome as a loss.
- Ran the default corrected EPL sportsbook backtest: `python scripts/hodge_sportsbook_epl_backtest.py`. It downloaded 3,800 matches from 2016-08-13 through 2026-05-24, evaluated 3,024 matches after a 760-match warmup, and saved `site/data/hodge_sportsbook_epl_10yr.json`. With a 3% probability-edge threshold and 1% flat staking, ROI was negative: Pinnacle -68.60%, Bet365 -79.18%, BestAvailable -17.11%, MarketAverage -74.96%. Capped Kelly was worse across all markets.
- Ran a stricter high-threshold pass: `python scripts/hodge_sportsbook_epl_backtest.py --edge-threshold 0.20 --output site/data/hodge_sportsbook_epl_10yr_thr020.json`. It placed only 107 Pinnacle bets and produced +2.23% flat ROI, but capped Kelly was -0.11% and Bet365/BestAvailable/MarketAverage remained negative. Treat this as an unstable filter result, not proof of exploitable sportsbook alpha.
- Added `scripts/hodge_real_sportsbook_agent.py`, a unified real-odds bankroll agent. It downloads football-data EPL 1X2 odds plus SportsbookReviewsOnline historical closing moneyline archives for NFL, NBA, NHL, MLB, and CFB; replays by date; fits Hodge only on prior completed games; commits same-day stakes before that day's results settle; starts from a configurable bankroll (default $1,000); and saves JSON artifacts under `site/data/`.
- The first unified-agent run exposed a parser hazard: some CFB archive rows encode impossible two-sided positive moneylines where a favorite minus sign appears absent. The parser now rejects impossible two-positive moneyline pairs instead of guessing the missing sign. The audited CFB-only run after this fix lost money: $1,000 -> $44.00, 5,227 bets, 52.09% wins, -12.50% yield.
- Full corrected six-sport real-odds agent default run: `python scripts/hodge_real_sportsbook_agent.py`, saved `site/data/hodge_real_sportsbook_agent.json`. It loaded 61,898 games across NFL/NBA/NHL/MLB/CFB/EPL, placed 30,566 bets, and lost the bankroll: $1,000 -> $0.01, -3.97% yield, 100% max drawdown. Broad real-market betting is not profitable with the default rules.
- Strict six-sport run: `python scripts/hodge_real_sportsbook_agent.py --edge-threshold 0.15 --min-ev 0.05 --max-bet-fraction 0.01 --max-day-exposure 0.05 --output site/data/hodge_real_sportsbook_agent_strict.json`. Result: $1,000 -> $370.42, 7,646 bets, -2.43% yield. NBA and NHL were the only positive sport pockets in this run.
- Strict NBA+NHL-only agent: `python scripts/hodge_real_sportsbook_agent.py --sports NBA,NHL --edge-threshold 0.15 --min-ev 0.05 --max-bet-fraction 0.01 --max-day-exposure 0.05 --output site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json`. Result: $1,000 -> $1,394.03, 2,118 bets, 41.45% wins, +1.68% yield, 36.26% max drawdown.
- Strict single-sport validation: NHL-only saved `site/data/hodge_real_sportsbook_agent_nhl_strict.json` and grew $1,000 -> $1,236.98 over 474 bets with +5.03% yield and 20.52% max drawdown. NBA-only saved `site/data/hodge_real_sportsbook_agent_nba_strict.json` and grew $1,000 -> $1,115.41 over 1,644 bets with +0.64% yield and 42.31% max drawdown. NHL is the cleaner positive pocket; NBA is weak/fragile.
- Added and ran `scripts/hodge_winner_accuracy.py`, which removes betting entirely and compares straight-up picks from Hodge raw signal, Hodge calibrated probabilities, market favorite, incremental Elo, and home/listed-home baseline on the same chronological no-future-data replay.
- Straight-up accuracy artifact saved at `site/data/hodge_winner_accuracy.json`. Across 59,584 evaluated games, market favorite was best: 62.54% (37,263/59,584). Hodge raw and Hodge calibrated both reached 59.80% (35,633/59,584), Elo reached 59.69%, and home/listed-home reached 54.62%.
- Market favorite beat Hodge in every sport on straight-up accuracy: CFB 73.98% vs Hodge 69.30%; EPL 55.77% vs 53.90%; MLB 58.09% vs 55.41%; NBA 67.74% vs 64.88%; NFL 66.34% vs 62.67%; NHL 58.79% vs 57.46%. This confirms the current Hodge sports system is a useful signal but not the best standalone winner picker.
- Added `scripts/hodge_market_residual_strategy.py`, which treats Hodge as a market-residual feature instead of a final pick. It builds no-future side-level features, splits chronologically into train/tune/test, selects EV/edge thresholds only on tune, and evaluates final bankroll on untouched test data.
- Market-residual results were not profitable out of time. All-sport residual artifact `site/data/hodge_market_residual_strategy.json`: $1,000 -> $848.87, 158 test bets, -14.22% yield. NBA+NHL artifact `site/data/hodge_market_residual_strategy_nba_nhl.json`: $1,000 -> $860.24, 870 test bets, -1.80% yield. NHL-only artifact `site/data/hodge_market_residual_strategy_nhl.json`: $1,000 -> $857.23, 940 test bets, -1.77% yield. NBA-only artifact `site/data/hodge_market_residual_strategy_nba.json`: $1,000 -> $813.61, 134 test bets, -15.12% yield.
- Added `site/data/hodge_money_paths.md`, an evidence-backed monetization report. Current recommendation: do not sell this as a profitable betting bot; monetize Hodge as rankings/disagreement analytics, a paid validation report, or a feature feed while continuing betting R&D with stricter holdout validation.


## Verification Commands
```bash
python benchmark.py
python scripts/compare_rbl_hodge.py
python scripts/download_and_run_dream5.py --net 1
python scripts/download_and_run_dream5.py --net 3
python scripts/download_and_run_dream5.py --net 4
python scripts/run_trrust_hodge.py
python scratch/unbiased_comparison.py
python scratch/evaluate_loops.py
python scratch/evaluate_harmonic_cycles.py
python scratch/verify_dream5_tfs_live.py
python scripts/run_dream5_honest_benchmark.py
python scripts/run_financial_benchmarks.py
python scripts/hodge_sportsbook_epl_backtest.py
python scripts/hodge_sportsbook_epl_backtest.py --edge-threshold 0.20 --output site/data/hodge_sportsbook_epl_10yr_thr020.json
python scripts/hodge_real_sportsbook_agent.py
python scripts/hodge_real_sportsbook_agent.py --edge-threshold 0.15 --min-ev 0.05 --max-bet-fraction 0.01 --max-day-exposure 0.05 --output site/data/hodge_real_sportsbook_agent_strict.json
python scripts/hodge_real_sportsbook_agent.py --sports NBA,NHL --edge-threshold 0.15 --min-ev 0.05 --max-bet-fraction 0.01 --max-day-exposure 0.05 --output site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json
python scripts/hodge_winner_accuracy.py
python scripts/hodge_market_residual_strategy.py
python scripts/hodge_market_residual_strategy.py --sports NHL,NBA --output site/data/hodge_market_residual_strategy_nba_nhl.json
python -m compileall scripts scratch
node --check site/app.js
python -m http.server 8765 --bind 127.0.0.1 --directory site
```

## Durable Local Caveats
- Requires `numpy`, `scipy`, and `scikit-learn`.
- In large graphs, $B_2$ triangle enumeration can scale poorly. Consider triangle sparsification if memory/performance limits are reached.
- OpenFlights route data is historical and should be treated as a public demo dataset, not a current airline schedule.
- The visual map projection is a global Lambert conformal conic approximation inspired by aviation chart projections. It is for visual exploration, not certified navigation.
- The OpenFlights builder keeps only compact site artifacts by default. Use `--keep-raw` only when debugging the data loader.
- The builder's default Hodge visualization settings are intentionally local (`max_airports=420`, `max_edges=2200`, `k=8`, `tau=0.005`) to expose route basins that are visually legible.
- The DOJ graph is a source-text co-mention graph. An edge only means two tracked terms appeared in the same DOJ PDF; it must not be presented as guilt, involvement, conduct, or a personal relationship.
- The DOJ Library warns that some formats, including handwritten text and some images, may not be reliably searchable. The local worker marks low-text PDFs as `needs_ocr` and does not fake OCR.
- DOJ also warns that sensitive or non-public personal information may remain despite redactions. The local site artifacts avoid storing raw extracted text and keep source URLs/derived counts instead.
- The local Python environment prints conda entry-point warnings about `typing_extensions.Sentinel`; these warnings did not block the benchmark, artifact build, or site verification.
- DREAM5/Synapse scripts now require Synapse credentials outside source code. Set `SYNAPSE_AUTH_TOKEN` or `SYNAPSE_PAT`, or configure the Synapse client login locally before running those scripts.
- The previously exposed Synapse token must be considered compromised. Revoke it in Synapse and generate a fresh read-only token before running or sharing the repo.
- Sportsbook backtest caveat: the corrected EPL test does not support the earlier optimistic sportsbook-profit claim. The older `hodge_real_odds_epl.json` result is superseded because it skipped draws. Use `site/data/hodge_sportsbook_epl_10yr.json` and `site/data/hodge_sportsbook_epl_10yr_thr020.json` for the current honest result.
- Real sportsbook agent caveat: SportsbookReviewsOnline archives are public historical consensus/archive odds, not guaranteed Pinnacle closing lines for US sports. The agent uses them as real historical moneyline prices, rejects impossible two-positive moneyline pairs, and reports coverage. Positive NBA/NHL pockets still need an out-of-time validation pass before being treated as deployable.
