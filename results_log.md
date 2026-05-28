# Hodge Rank Clustering Optimization Results Log

| Iteration | Parameters/Logic Changed | Score | Outcome | Best Score |
|---|---|---|---|---|
| Baseline | `k=45, min_core=2, tau=0.3` | 0.8429 | Baseline | 0.8429 |
| 1 | Set `k=45, min_core=6, tau=0.2`, added noise distance threshold `pct=97.6` | 0.8714 | Improved | 0.8714 |
| 2 | Set `pct=96.0` with `noise_only` threshold mode (percentile calculated only over noise-to-core distances) | 0.8718 | Improved | 0.8718 |
| 3 | Local cluster-specific noise distance thresholds with `k=44, min_core=5, tau=0.22, pct=93.2` | 0.8729 | Improved | 0.8729 |
| 4 | Density-based pruning of sparsest 20% of nodes using k_d=5 nearest neighbor distance; k=44, min_core=5, tau=0.22, pct=93.2 | 0.8750 | Improved | 0.8750 |
| 5 | Adaptive Persistence: `(sink_potential[low] - p_saddle) < self.tau * sink_potential[low]` | 0.6881 | Lower (reverted) | 0.8750 |
| 6 | Consensus Multi-Scale: Average p_norm over k in [40, 44, 48] | 0.8645 | Lower (reverted) | 0.8750 |
| 7 | Distance-Rank Blended Flow: Blend rank and asymmetric distance flow with alpha=0.5, 0.8, 0.95, 0.2, 0.0 | 0.8750 | Equal or Lower (reverted) | 0.8750 |

## Pipeline Verification and Asymmetric Graph Testing

### 1. Cities & Tourists Benchmark Comparison
- **Dataset**: Asymmetric 600-sample synthetic dataset (4 clusters + noise) with warped distance: $D(x, y) = \|x - y\| \cdot (1 + 0.8 \cdot \sin(x_1 y_2 - x_2 y_1))$.
- **Results**:
  - **TrueHodgeRankClustering (Optimized)**: Adjusted Rand Index (ARI) = **0.8750** (Parameters: `k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0`)
  - **Rank-Based Linkage (RBL)**: Best ARI = **0.8536** (Parameters: `k=50, max_cluster=150`)
  - **HDBSCAN**: ARI = **0.8457** (precomputed metric on symmetrized $D_{sym} = \max(D, D^T)$)
  - **TrueHodgeRankClustering (Default)**: ARI = **0.1268**
- **Artifacts Saved**: [benchmark.json](file:///e:/code.projects/hodge-rank-clustering/site/data/benchmark.json), [rbl_vs_hodge_comparison.txt](file:///e:/code.projects/hodge-rank-clustering/rbl_vs_hodge_comparison.txt)

### 2. TRRUST Transcriptional Regulatory Networks
- **Dataset**: Human and Mouse transcriptional regulatory networks downloaded from GRNPedia (containing directed regulatory interactions).
- **Hodge Flow Decomposition**:
  - **Human Network** (2,861 genes, 8,403 interactions, 5,118 triangles):
    - Gradient Flow Norm: **54.2570** (75.3%)
    - Curl Flow Norm: **33.7144** (46.8%)
    - Harmonic Flow Norm: **33.2437** (46.2%)
    - Top Master Regulators (Potential Basins / Sources): `SYTL4` (0.0%), `HAP1` (6.4%), `PDE5A` (14.7%), `UGT2B4` (15.9%), `ABCC4` (15.9%)
    - Top Downstream Targets (Potential Peaks / Sinks): `VMP1` (100.0%), `SMO` (100.0%), `PCYT1A` (97.0%), `BUB1B` (97.0%), `UPF3B` (89.8%)
  - **Mouse Network** (2,455 genes, 6,462 interactions, 2,413 triangles):
    - Gradient Flow Norm: **50.7443** (77.0%)
    - Curl Flow Norm: **26.5874** (40.3%)
    - Harmonic Flow Norm: **32.5943** (49.5%)
    - Top Master Regulators (Potential Basins / Sources): `Axin1` (0.0%), `Lrp1` (13.2%), `Npsr1` (14.6%), `Mast1` (15.1%), `Pknox1` (15.5%)
    - Top Downstream Targets (Potential Peaks / Sinks): `Abhd14a` (100.0%), `Ids` (84.1%), `Phf12` (83.0%), `Upf3b` (80.7%), `Zic1` (80.7%)
- **Hodge potential TF prediction validation**:
  - Out of the top 200 nodes with the lowest potentials (Basins), **100.0%** are true regulators in Human TRRUST, and **98.50%** are true regulators in Mouse TRRUST (baseline random TF ratios are **27.75%** and **33.65%** respectively).
- **Hodge Curl Loop Isolation Validation**:
  - **Human TRRUST** (85 cyclic triangles, 5,033 transitive triangles): Mean curl $|c|$ = **0.5970** on cyclic triangles vs **0.1784** on transitive ones.
  - **Mouse TRRUST** (60 cyclic triangles, 2,353 transitive triangles): Mean curl $|c|$ = **0.7805** on cyclic triangles vs **0.2720** on transitive ones.
- **Hodge Harmonic Flow Cycle Prediction Validation**:
  - **Human TRRUST** (1,296 cycle edges): Mean $|F_{harm}|$ = **0.3332** on cycle edges vs **0.0954** on non-cycle edges. **ROC AUC = 0.7274**, **Average Precision = 0.4605** (baseline: 0.1542).
  - **Mouse TRRUST** (1,475 cycle edges): Mean $|F_{harm}|$ = **0.4225** on cycle edges vs **0.1245** on non-cycle edges. **ROC AUC = 0.7792**, **Average Precision = 0.6038** (baseline: 0.2283).
- **Artifacts Saved**: [summary.json](file:///e:/code.projects/hodge-rank-clustering/site/data/trrust/summary.json), [evaluate_loops_trrust.py](file:///e:/code.projects/hodge-rank-clustering/scratch/evaluate_loops_trrust.py), [evaluate_harmonic_cycles_trrust.py](file:///e:/code.projects/hodge-rank-clustering/scratch/evaluate_harmonic_cycles_trrust.py), [verify_trrust_tfs.py](file:///e:/code.projects/hodge-rank-clustering/scratch/verify_trrust_tfs.py)

### 3. OpenFlights Route Preference Network
- **Dataset**: Asymmetric route-preference matrix constructed from 420 global airports and 2,200 flight routes.
- **Hodge Flow Decomposition** (420 airports, 173 core nodes, 348 Hodge edges, 85 triangles):
  - Gradient Flow Norm: **53.0559**
  - Curl Flow Norm: **15.5356**
  - Harmonic Flow Norm: **17.2835**
- **Artifacts Saved**: [summary.json](file:///e:/code.projects/hodge-rank-clustering/site/data/openflights/summary.json), [land.geojson](file:///e:/code.projects/hodge-rank-clustering/site/data/world/land.geojson)

### 4. DREAM5 Gene Regulatory Networks
- **Dataset**: Biological networks (E. coli, Yeast) and synthetic In Silico benchmark network.
- **Hodge potential TF prediction validation**:
  - **Network 1 (In Silico)**: Under signed correlation flow, precision is near zero due to activation/repression cancellation. Under **Absolute Correlation Flow**, precision @ 10 is **100.0%** and precision @ 50 is **100.0%** (baseline random: 11.87%).
  - **Network 3 (E. coli)**: Under signed correlation flow, precision @ 10 is 70.0% and @ 50 is 88.0%. Under **Absolute Correlation Flow**, precision @ 10 is **100.0%** and @ 50 is **92.0%** (baseline random: 7.40%).
  - **Network 4 (Yeast)**: Under signed correlation flow, precision @ 10 is 40.0% and @ 50 is 80.0%. Under **Absolute Correlation Flow**, precision @ 10 is **100.0%** and @ 50 is **96.0%** (baseline random: 5.60%).
- **Hodge Harmonic Flow Cycle Prediction Validation**:
  - **Network 1 (In Silico)**: 39 edges in feedback cycles. Mean $|F_{harm}|$ = **0.5828** on cycle edges vs **0.0591** on non-cycle edges. **ROC AUC = 0.8833**, **Average Precision = 0.4439** (baseline: 0.0097).
  - **Network 3 (E. coli)**: 23 edges in feedback cycles. Mean $|F_{harm}|$ = **0.6624** on cycle edges vs **0.0303** on non-cycle edges. **ROC AUC = 0.9733**, **Average Precision = 0.7588** (baseline: 0.0111).
  - **Network 4 (Yeast)**: 19 edges in feedback cycles. Mean $|F_{harm}|$ = **0.3176** on cycle edges vs **0.0430** on non-cycle edges. **ROC AUC = 0.7873**, **Average Precision = 0.1737** (baseline: 0.0048).
- **Hodge Curl Loop Isolation Validation**:
  - **Network 1**: 0 cyclic triangles, 1,452 transitive triangles. Transitive mean curl $|c|$ = 0.0837.
  - **Network 3**: 0 cyclic triangles, 628 transitive triangles. Transitive mean curl $|c|$ = 0.0714.
  - **Network 4**: 0 cyclic triangles, 737 transitive triangles. Transitive mean curl $|c|$ = 0.0842.
  - (Note: Ground-truth networks are constructed as bipartite TF-target pairings without TF-TF loops, resulting in 0 cyclic triangles.)
- **Artifacts Saved**: [summary_net1.json](file:///e:/code.projects/hodge-rank-clustering/site/data/dream5/summary_net1.json), [summary_net3.json](file:///e:/code.projects/hodge-rank-clustering/site/data/dream5/summary_net3.json), [summary_net4.json](file:///e:/code.projects/hodge-rank-clustering/site/data/dream5/summary_net4.json), [evaluate_loops.py](file:///e:/code.projects/hodge-rank-clustering/scratch/evaluate_loops.py), [evaluate_harmonic_cycles.py](file:///e:/code.projects/hodge-rank-clustering/scratch/evaluate_harmonic_cycles.py), [verify_dream5_tfs_live.py](file:///e:/code.projects/hodge-rank-clustering/scratch/verify_dream5_tfs_live.py)

### 5. Leakage-Free DREAM5 Edge-Ranking Test
- **Script**: [run_dream5_honest_benchmark.py](file:///e:/code.projects/hodge-rank-clustering/scripts/run_dream5_honest_benchmark.py)
- **Leakage control**: Inference uses only DREAM5 expression data plus the provided TF list. Gold-standard rows are loaded only after ranking to calculate AUPR, AUROC, and precision-at-K.
- **Parameters**: `top_per_tf=200`, `max_hodge_edges=50000`.
- **Net 1 (In Silico)**:
  - Pearson absolute: AUPR **0.1893**, AUROC **0.7646**, P@100 **0.7200**
  - Hodge normalized blend: AUPR **0.1857**, AUROC **0.7790**, P@100 **0.6600**
  - Hodge raw delta: AUPR **0.0295**, AUROC **0.6651**, P@100 **0.0100**
  - Candidate-gated Pearson: AUPR **0.1785**, AUROC **0.7131**, P@100 **0.7200**
  - Diagnostics: Hodge candidate coverage is **50.55%** for positives vs **11.81%** for negatives. Mean Hodge delta is **0.2601** on positives vs **0.2161** on negatives, but the top-100 Hodge-delta pairs contain only **1** true edge; top-100 Pearson absolute contains **72**.
- **Net 3 (E. coli)**:
  - Pearson signed: AUPR **0.0698**, AUROC **0.6202**, P@100 **0.5000**
  - Hodge normalized blend: AUPR **0.0678**, AUROC **0.6224**, P@100 **0.5500**
  - Hodge raw delta: AUPR **0.0177**, AUROC **0.5932**, P@100 **0.0100**
  - Candidate-gated Pearson: AUPR **0.0579**, AUROC **0.5571**, P@100 **0.5000**
  - Diagnostics: Hodge candidate coverage is **14.09%** for positives vs **2.90%** for negatives. Mean Hodge delta is **0.4843** on positives vs **0.4314** on negatives, but the top-100 Hodge-delta pairs contain only **1** true edge; top-100 Pearson absolute contains **51**.
- **Net 4 (Yeast)**:
  - Pearson signed: AUPR **0.0232**, AUROC **0.5796**, P@100 **0.0700**
  - Hodge normalized blend: AUPR **0.0204**, AUROC **0.5331**, P@100 **0.0700**
  - Hodge raw delta: AUPR **0.0159**, AUROC **0.4748**, P@100 **0.0000**
  - Candidate-gated Pearson: AUPR **0.0184**, AUROC **0.5105**, P@100 **0.0700**
  - Diagnostics: Hodge candidate coverage is **4.87%** for positives vs **2.76%** for negatives. Mean Hodge delta is **0.5288** on positives vs **0.5223** on negatives, and the top-100 Hodge-delta pairs contain **0** true edges; top-100 Pearson absolute contains **7**.
- **Math diagnosis**: The current Hodge DREAM5 score is not failing because of a sign flip. It solves a global least-squares hierarchy, `p[target] - p[tf] ~= abs(correlation)`, then uses the resulting node-potential gap as an edge confidence. That compresses local pair evidence into source/sink node effects. DREAM5 AUPR rewards sparse TF-target pair recovery, so a global hierarchy feature can improve broad AUROC while still ranking many high-potential nonedges above true direct edges. The normalized blend reduces the scale bug in the old raw blend but still does not beat Pearson on AUPR.
- **Conclusion**: The honest edge-ranking test does **not** show Hodge beating a simple Pearson baseline on AUPR. The defensible claim is that Hodge is useful for post-hoc structure/decomposition tasks, regulator/source basin discovery, and cycle/harmonic analysis, but this current potential-delta score is not a standalone DREAM5 edge-inference winner.
- **Artifacts Saved**: [honest_scores.json](file:///e:/code.projects/hodge-rank-clustering/site/data/dream5/honest_scores.json)

### 6. Postable Hodge Finding: Feedback-Control Edge Enrichment
- **Script**: [find_postable_hodge_findings.py](file:///e:/code.projects/hodge-rank-clustering/scripts/find_postable_hodge_findings.py)
- **Primary result**: Hodge harmonic flow is useful as a topology layer for regulatory feedback, not as a DREAM5 direct-edge predictor.
- **Human TRRUST**:
  - 8,403 directed regulatory edges; 1,296 feedback-cycle edges; base rate **15.4%**.
  - Top-100 by $|F_{harm}|$: **97** feedback-cycle edges (**97.0% precision**, **6.29x lift**).
  - ROC AUC **0.727**, average precision **0.460**.
  - Degree-product baseline: AP **0.464**, P@100 **83.0%**; Hodge is not better on broad AP but is stronger at the top of the ranked list.
  - Top-100 Hodge list includes **53 non-reciprocal** feedback-cycle edges, so the result is not just detecting mutual pairs.
- **Mouse TRRUST**:
  - 6,462 directed regulatory edges; 1,475 feedback-cycle edges; base rate **22.8%**.
  - Top-100 by $|F_{harm}|$: **97** feedback-cycle edges (**97.0% precision**, **4.25x lift**).
  - ROC AUC **0.779**, average precision **0.604**.
  - Degree-product baseline: AP **0.533**, P@100 **90.0%**; Hodge is better on AP and top-list precision.
  - Top-100 Hodge list includes **55 non-reciprocal** feedback-cycle edges.
- **Recognizable examples**:
  - Human high-harmonic cycle edges include `ATF3 -> TP53`, `NFKBIA -> NFKB1`, `NFKBIA -> RELA`, `STAT1 -> STAT3`, and `E2F1 -> TP53`.
  - Mouse high-harmonic cycle edges include `Mdm2 -> Trp53`, `Nfkbia -> Nfkb1`, `Mmp9 -> Jun`, `Mmp9 -> Fos`, and `Nanog -> Tcf3`.
- **Secondary result**: Existing five-season college-football backtest shows Hodge+curl accuracy **70.7%** vs Elo **66.0%** across 2020-2024, but that needs stronger baselines before being pitched as more than an interesting public demo.
- **Artifacts Saved**: [hodge_findings.md](file:///e:/code.projects/hodge-rank-clustering/site/data/postable_findings/hodge_findings.md), [hodge_findings.json](file:///e:/code.projects/hodge-rank-clustering/site/data/postable_findings/hodge_findings.json)

### 7. Sports Prediction and Sportsbook Backtests
- **Five-season prediction artifacts**: [hodge_5season_cfb.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_cfb.json), [hodge_5season_epl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_epl.json), [hodge_5season_mlb.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_mlb.json), [hodge_5season_nba.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_nba.json), [hodge_5season_nfl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_nfl.json), [hodge_5season_nhl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_5season_nhl.json).
- **Prediction accuracy vs Elo**:
  - CFB: Hodge+curl **70.74%** vs Elo **65.97%** (**+4.69 pp**).
  - NHL: Hodge **62.80%** vs Elo **59.74%** (**+3.06 pp**).
  - EPL: Hodge **69.39%** vs Elo **68.32%** (**+1.07 pp**).
  - NFL: Hodge **66.07%** vs Elo **65.14%** (**+0.93 pp**).
  - NBA and MLB are essentially tied with Elo: NBA **64.63%** vs **64.51%**, MLB **57.06%** vs **57.01%**.
- **Elo-proxy betting artifacts**: [hodge_betting_cfb.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_cfb.json), [hodge_betting_epl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_epl.json), [hodge_betting_mlb.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_mlb.json), [hodge_betting_nba.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_nba.json), [hodge_betting_nfl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_nfl.json), [hodge_betting_nhl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_betting_nhl.json).
- **Elo-proxy betting result**: These files show large positive flat-betting ROIs for CFB, EPL, NFL, and NHL, and modest positives for NBA/MLB. Treat these as a model-vs-Elo stress test only; they are not proof of sportsbook profitability because the market model is synthetic and weaker than real closing lines.
- **Superseded EPL real-odds artifact**: [hodge_real_odds_epl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_odds_epl.json) reports extreme positive ROI, but it came from `scripts/hodge_real_odds_epl.py`, which skipped drawn matches after seeing the final result. Since home/away 1X2 bets lose on draws, that artifact is invalid for profitability claims.
- **Corrected 10-season sportsbook script**: [hodge_sportsbook_epl_backtest.py](file:///e:/code.projects/hodge-rank-clustering/scripts/hodge_sportsbook_epl_backtest.py) downloads football-data.co.uk EPL odds/results, uses only prior matches for rolling Hodge training, calibrates home/draw/away probabilities, and counts every non-winning selected outcome as a loss.
- **Corrected default EPL result**: [hodge_sportsbook_epl_10yr.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_sportsbook_epl_10yr.json), edge threshold **0.03**, 3,800 matches downloaded, 3,024 evaluated after warmup. Flat ROI: Pinnacle **-68.60%**, Bet365 **-79.18%**, BestAvailable **-17.11%**, MarketAverage **-74.96%**. Capped Kelly was worse across all markets.
- **Strict-threshold EPL result**: [hodge_sportsbook_epl_10yr_thr020.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_sportsbook_epl_10yr_thr020.json), edge threshold **0.20**, 131 events with any bet. Flat ROI: Pinnacle **+2.23%** on 107 bets, Bet365 **-12.18%**, BestAvailable **-4.36%**, MarketAverage **-12.25%**. Kelly was negative even for Pinnacle. This is an unstable filter result, not enough to claim exploitable sportsbook alpha.
- **Current conclusion**: The defensible sports claim is prediction signal, strongest in CFB and NHL. The current real-market profitability claim is negative/undetermined: corrected EPL sportsbook testing does not support the older optimistic profit numbers.

### 8. Unified Real-Odds Bankroll Agent
- **Script**: [hodge_real_sportsbook_agent.py](file:///e:/code.projects/hodge-rank-clustering/scripts/hodge_real_sportsbook_agent.py).
- **Purpose**: A no-cheating bankroll replay agent starting from **$1,000** by default. It uses only games completed before each date to fit Hodge and calibrate probabilities, commits all same-day stakes before same-day results settle, reinvests bankroll after settlement, and stores bet-level evidence.
- **Data sources**:
  - EPL: football-data.co.uk 1X2 closing odds, with home/draw/away modeled explicitly.
  - NFL/NBA/NHL/MLB/CFB: SportsbookReviewsOnline historical closing moneyline archives. These are real historical prices, but not guaranteed Pinnacle lines for US sports.
- **Parser correction**: The first unified run exposed impossible two-positive moneyline pairs in the CFB archive where favorite minus signs appear absent. The parser now rejects those games instead of guessing signs. After this fix, CFB-only validation lost money: [hodge_real_sportsbook_agent_cfb_audit.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent_cfb_audit.json), **$1,000 -> $44.00**, 5,227 bets, **-12.50%** yield.
- **Default all-sport agent**: [hodge_real_sportsbook_agent.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent.json), edge threshold **0.05**, min EV **0.02**, max bet **2%**, max same-day exposure **12%**. Loaded **61,898** games, placed **30,566** bets, and lost the bankroll: **$1,000 -> $0.01**, **-3.97%** yield, **100%** max drawdown.
- **Strict all-sport agent**: [hodge_real_sportsbook_agent_strict.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent_strict.json), edge threshold **0.15**, min EV **0.05**, max bet **1%**, max same-day exposure **5%**. Result: **$1,000 -> $370.42**, 7,646 bets, **-2.43%** yield, **79.47%** max drawdown. NBA and NHL were the only positive pockets.
- **Strict NBA+NHL subset**: [hodge_real_sportsbook_agent_nba_nhl_strict.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json), same strict staking rules. Result: **$1,000 -> $1,394.03**, 2,118 bets, **+1.68%** yield, **36.26%** max drawdown.
- **Single-sport strict checks**:
  - NHL: [hodge_real_sportsbook_agent_nhl_strict.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent_nhl_strict.json), **$1,000 -> $1,236.98**, 474 bets, **55.70%** wins, **+5.03%** yield, **20.52%** max drawdown.
  - NBA: [hodge_real_sportsbook_agent_nba_strict.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_real_sportsbook_agent_nba_strict.json), **$1,000 -> $1,115.41**, 1,644 bets, **37.35%** wins, **+0.64%** yield, **42.31%** max drawdown.
- **Current betting-agent conclusion**: Broad all-sport real-odds betting is not profitable. The only historically positive configuration found in this pass is a strict NBA/NHL subset, carried mainly by NHL. That should be treated as a candidate edge requiring out-of-time validation, not as a deployable live-betting guarantee.

### 9. Straight-Up Winner Accuracy Without Betting
- **Script**: [hodge_winner_accuracy.py](file:///e:/code.projects/hodge-rank-clustering/scripts/hodge_winner_accuracy.py).
- **Purpose**: Remove betting, bankrolls, EV thresholds, and stake sizing. The script uses the same chronological real-odds/results replay and compares straight-up pick accuracy for Hodge raw margin sign, Hodge calibrated probability pick, market favorite from closing odds, incremental Elo, and home/listed-home baseline.
- **Artifact**: [hodge_winner_accuracy.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_winner_accuracy.json).
- **Aggregate result** over **59,584** evaluated games:
  - Market favorite: **62.54%** (37,263 / 59,584).
  - Hodge raw signal: **59.80%** (35,633 / 59,584).
  - Hodge calibrated: **59.80%** (35,633 / 59,584).
  - Elo: **59.69%** (35,564 / 59,584).
  - Home/listed-home: **54.62%** (32,545 / 59,584).
- **Best method by sport**: market favorite was best in every sport:
  - CFB: Market **73.98%**, Hodge **69.30%**, Elo **66.48%**.
  - EPL: Market **55.77%**, Hodge **53.90%**, Elo **53.96%**.
  - MLB: Market **58.09%**, Hodge **55.41%**, Elo **56.20%**.
  - NBA: Market **67.74%**, Hodge **64.88%**, Elo **64.64%**.
  - NFL: Market **66.34%**, Hodge **62.67%**, Elo **62.38%**.
  - NHL: Market **58.79%**, Hodge **57.46%**, Elo **57.63%**.
- **Conclusion**: The current Hodge sports system has real signal and roughly matches or slightly beats the simple Elo baseline in some sports, but it does **not** beat the closing market as a standalone straight-up winner picker. The next technical direction is to use Hodge as a feature for market-residual prediction rather than using it as the final probability or final pick.

### 10. Market-Residual R&D and Money Paths
- **Residual script**: [hodge_market_residual_strategy.py](file:///e:/code.projects/hodge-rank-clustering/scripts/hodge_market_residual_strategy.py).
- **Method**: Build no-future side-level features from closing market probability, Hodge probability, Hodge-market disagreement, and Elo; split chronologically into train/tune/test; fit a logistic side-win model on train; select EV/edge thresholds on tune only; report bankroll on untouched test.
- **All-sport residual test**: [hodge_market_residual_strategy.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_market_residual_strategy.json). Tune selected edge **0.02**, min EV **0.00** from 164 tune bets with **-3.36%** yield. Untouched test: **$1,000 -> $848.87**, 158 bets, **-14.22%** yield.
- **NBA+NHL residual test**: [hodge_market_residual_strategy_nba_nhl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_market_residual_strategy_nba_nhl.json). Tune selected edge **0.00**, min EV **0.00** from 791 tune bets with **-8.34%** yield. Untouched test: **$1,000 -> $860.24**, 870 bets, **-1.80%** yield.
- **NHL residual test**: [hodge_market_residual_strategy_nhl.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_market_residual_strategy_nhl.json). Tune selected edge **0.00**, min EV **0.00** from 582 tune bets with **-3.56%** yield. Untouched test: **$1,000 -> $857.23**, 940 bets, **-1.77%** yield.
- **NBA residual test**: [hodge_market_residual_strategy_nba.json](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_market_residual_strategy_nba.json). Tune selected edge **0.00**, min EV **0.025** from 119 tune bets with **+15.96%** yield, but untouched test failed: **$1,000 -> $813.61**, 134 bets, **-15.12%** yield.
- **Money-path report**: [hodge_money_paths.md](file:///e:/code.projects/hodge-rank-clustering/site/data/hodge_money_paths.md).
- **Conclusion**: The current residual betting model does not validate out of time. The practical monetization path is to sell Hodge as a differentiated analytics/ranking/disagreement feature or paid validation report, while adding richer sportsbook features such as line movement, rest/travel, injuries, starting pitchers, goalies, and sport-specific calibration before any live betting claim.

### 11. WITS Global Trade Map
- **Script**: [build_global_trade_data.py](file:///e:/code.projects/hodge-rank-clustering/scripts/build_global_trade_data.py).
- **Dataset**: WITS 2017 global supply-chain network with country coordinates merged from public ISO country-code data.
- **Generated artifacts**: [nodes.json](file:///e:/code.projects/hodge-rank-clustering/site/data/trade/nodes.json), [edges.json](file:///e:/code.projects/hodge-rank-clustering/site/data/trade/edges.json), [summary.json](file:///e:/code.projects/hodge-rank-clustering/site/data/trade/summary.json).
- **Graph size**: 166 countries, 2,200 net trade-flow edges, and 21,627 triangles.
- **Hodge decomposition**: Gradient norm **113,662,278.45**, curl norm **386,669,764.17**, harmonic norm **3,582.12**. The large curl component is the interesting result: the trade graph is not just a clean exporter-to-importer hierarchy; much of the net flow lives in regional/circular triangle structure.
- **Potential extremes**: Low-potential upstream sources include `CHN`, `DEU`, `IRL`, and `KOR`; high-potential downstream sinks include `USA`, `GBR`, `BGD`, and `SAU`. Small countries such as `SLE`, `GMB`, `ATG`, `LSO`, and `SUR` can appear at potential extremes because Hodge potential is structural and pairwise-flow based, not simply GDP or raw net balance.
- **Public-site status**: Added the `Global Trade` tab to the GitHub Pages app. The unfinished fraud prototype was not published because it still contains simulated flows.
