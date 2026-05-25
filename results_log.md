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
