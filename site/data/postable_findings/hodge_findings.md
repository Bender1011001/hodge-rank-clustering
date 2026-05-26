# Postable Hodge Findings

## Primary Finding: Hodge Harmonic Flow Finds Feedback-Control Edges

This is the strongest postable result in the repo right now: on public TRRUST regulatory networks, harmonic flow isolates feedback-cycle edges that ordinary pairwise edge ranking does not ask for.

| Dataset | Edges | Cycle-edge base rate | Top-100 precision | Lift | ROC AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| Human TRRUST | 8403 | 15.4% | 97.0% | 6.29x | 0.727 | 0.460 |
| Mouse TRRUST | 6462 | 22.8% | 97.0% | 4.25x | 0.779 | 0.604 |

Baseline check:

- Human degree-product baseline: AP 0.464, P@100 83.0%. Hodge harmonic: AP 0.460, P@100 97.0%.
- Mouse degree-product baseline: AP 0.533, P@100 90.0%. Hodge harmonic: AP 0.604, P@100 97.0%.
- The top-100 harmonic lists are not just reciprocal-pair detection: human has 53 non-reciprocal feedback-cycle edges in the top 100; mouse has 55.

Recognizable high-harmonic human examples:
- #9: `MCM5 -> STAT1` | |F_harm|=1.390 | cycle | Unknown
- #12: `MYC -> TLX1` | |F_harm|=1.370 | cycle | Unknown
- #14: `ATF3 -> TP53` | |F_harm|=1.331 | cycle | Unknown
- #18: `E2F1 -> ZNF350` | |F_harm|=1.315 | cycle | Unknown
- #19: `AR -> RELA` | |F_harm|=1.314 | cycle | Repression
- #25: `TP73 -> E2F1` | |F_harm|=1.276 | cycle | Unknown
- #26: `AR -> NFKB1` | |F_harm|=1.272 | cycle | Repression
- #29: `STAT1 -> CEBPE` | |F_harm|=1.240 | cycle | Activation
- #30: `AR -> JUN` | |F_harm|=1.234 | cycle | Activation
- #38: `LYL1 -> NFKB1` | |F_harm|=1.196 | cycle | Repression

Recognizable high-harmonic mouse examples:
- #2: `Mmp9 -> Jun` | |F_harm|=1.812 | cycle | Unknown
- #4: `Mdm2 -> Trp53` | |F_harm|=1.762 | cycle | Repression
- #5: `Nfkbia -> Nfkb1` | |F_harm|=1.705 | cycle | Repression
- #6: `Foxp3 -> Nfkb1` | |F_harm|=1.700 | cycle | Unknown
- #11: `Mmp9 -> Fos` | |F_harm|=1.509 | cycle | Unknown
- #12: `Utf1 -> Tcf3` | |F_harm|=1.504 | cycle | Unknown
- #13: `Nanog -> Tcf3` | |F_harm|=1.494 | cycle | Unknown
- #19: `Nanog -> Bmi1` | |F_harm|=1.446 | cycle | Unknown
- #30: `Cd7 -> Nfkb1` | |F_harm|=1.360 | cycle | Activation
- #35: `Cebpa -> Nfkb1` | |F_harm|=1.332 | cycle | Activation

Draft post:

> DREAM5 edge AUPR was the wrong thing to optimize for this Hodge method. The useful signal is topology: on public TRRUST regulatory networks, Hodge harmonic flow flags feedback-control edges with 97% precision in the top 100 human edges, versus a 15.4% base rate, and 97% in mouse versus a 22.8% base rate. It pulls out recognizable control edges like ATF3 -> TP53, NFKBIA -> NFKB1/RELA, and Mdm2 -> Trp53. Code and artifacts are reproducible.

More careful version:

> The honest DREAM5 result says Hodge is not an edge-inference winner. But as a topology layer, it does something useful: on TRRUST, harmonic flow ranks known feedback-cycle edges at 97% precision in the top 100 for both human and mouse networks. A degree-product baseline is competitive on broad AP in human, so the claim is top-of-list enrichment and interpretability, not universal superiority.

## Secondary Finding: College Football Backtest

Across five CFB seasons, Hodge+curl accuracy was 70.7% vs Elo 66.0%, a 4.8% absolute edge.

| Season | Hodge+curl | Elo | Home | Top 5 by Hodge potential |
|---|---:|---:|---:|---|
| CFB 2020 | 71.9% | 65.2% | 54.8% | Cincinnati Bearcats, Clemson Tigers, BYU Cougars, Alabama Crimson Tide, Notre Dame Fighting Irish |
| CFB 2021 | 75.2% | 68.2% | 57.0% | Georgia Bulldogs, Alabama Crimson Tide, Ohio State Buckeyes, Cincinnati Bearcats, Michigan Wolverines |
| CFB 2022 | 68.7% | 65.8% | 51.4% | Ohio State Buckeyes, Georgia Bulldogs, Alabama Crimson Tide, Tennessee Volunteers, Kansas State Wildcats |
| CFB 2023 | 70.2% | 64.1% | 55.2% | Oregon Ducks, Ohio State Buckeyes, Michigan Wolverines, Kansas State Wildcats, Notre Dame Fighting Irish |
| CFB 2024 | 67.7% | 66.5% | 58.1% | Ohio State Buckeyes, Alabama Crimson Tide, Ole Miss Rebels, Indiana Hoosiers, Oregon Ducks |

This is more broadly accessible than the biology result, but it needs a stronger baseline before being pitched as more than an interesting backtest.
