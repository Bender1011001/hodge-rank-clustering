# Discrete Hodge Rank Clustering & Rank-Based Linkage

Topological clustering of directed graphs and asymmetric pairwise distance matrices via:
1. **Discrete Hodge Decomposition** on asymmetric flows (hierarchy/potential fields).
2. **Rank-Based Linkage (RBL)** via comparator-based *in-sway* simplicial complexes.

Standard spectral methods (Louvain, spectral clustering, HDBSCAN) force you to symmetrize your adjacency or distance matrix before clustering. This throws away directional information. This codebase provides topological tools working directly on asymmetric, non-metric pairwise data.

## How Hodge Rank Clustering Works

Given a directed graph (or an asymmetric distance/preference matrix), the algorithm:

1. **Prunes noise via local density estimation**: Prunes the sparsest $100 - \text{pct\_density}$% of nodes.
2. **Builds a mutual K-NN graph** and applies k-core pruning (filtering periphery).
3. **Constructs boundary matrices** B_1 (vertex-edge incidence) and B_2 (edge-triangle incidence mapping edges to 2-simplices).
4. **Solves the Hodge decomposition** via LSQR:
   - **Gradient flow** ($F_{\text{grad}}$): hierarchical structure explainable by a global potential $\Phi$.
   - **Curl flow** ($F_{\text{curl}}$): local cyclic flow around triangles (rock-paper-scissors).
   - **Harmonic flow** ($F_{\text{harm}}$): global topological circulations.
5. **Clusters via persistence-based topological simplification** on potential $\Phi$ (watershed Union-Find).
6. **Reintegrates noise nodes** using local cluster percentile distance thresholds (`pct`).

The decomposition is exact: $F = F_{\text{grad}} + $F_{\text{curl}} + $F_{\text{harm}}$, and the three components are mutually orthogonal.

## How Rank-Based Linkage (RBL) Works

Rank-Based Linkage is a comparison-based clustering algorithm introduced by Darling, Grilliette, and Logan (2025) — see references below. RBL constructs a $K$-nearest neighbor digraph from ordinal Comparators (triplet comparisons), builds a 2D abstract oriented simplicial complex on the line graph of mutual neighbors, and calculates **in-sway** ($\sigma(\{x, y\})$) for "mutual friends" to form a linkage graph. It clusters by thresholding in-sway. It is a stable functor, unlike optimization-based clustering.

We provide a mathematically exact Python port in `rbl_clustering.py`.

## Installation

```bash
pip install numpy scipy scikit-learn
```

Then install the requirements:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Hodge Rank Clustering

```python
import numpy as np
from hodge_rank import TrueHodgeRankClustering

# Generate asymmetric distance matrix
n = 200
X = np.random.randn(n, 2)
D = np.zeros((n, n))
for i in range(n):
    diff = X - X[i]
    dist = np.linalg.norm(diff, axis=1)
    asym = 1.0 + 0.5 * np.sin(X[i, 0] * X[:, 1] - X[i, 1] * X[:, 0])
    D[i, :] = dist * asym
    D[i, i] = np.inf

# Cluster with optimized defaults
model = TrueHodgeRankClustering()
labels = model.fit_predict(D=D)
```

### 2. Rank-Based Linkage (RBL)

```python
from rbl_clustering import RankBasedLinkageClustering

# Cluster with sub-critical threshold selection
rbl = RankBasedLinkageClustering(k=15)
rbl_labels = rbl.fit_predict(D=D)
```

## Parameters (Hodge Clustering)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `k` | 44 | Number of nearest neighbors for mutual K-NN graph construction |
| `min_core` | 5 | Minimum degree for k-core pruning |
| `tau` | 0.22 | Topological simplification (persistence) threshold relative to potential range |
| `pct` | 93.2 | Percentile threshold of distances for noise reintegration |
| `k_d` | 5 | Neighborhood size to estimate density for density-based pruning |
| `pct_density` | 80.0 | Percentile density threshold below which nodes are pruned as noise |
| `flow_type` | 0 | Flow type: `0` (rank diff), `1` (log-rank diff), `2` (normalized diff), `3` (power-scaled diff) |
| `beta` | 1.0 | Power scale parameter for flow type 3 |
| `saddle_type` | 0 | Saddle merge style: `0` (absolute threshold), `1` (relative threshold) |

## Benchmark & Comparison

Run the comparison script to evaluate HDBSCAN, the default Hodge Clustering configuration, our optimized Hodge configuration, and RBL on the asymmetric benchmark:

```bash
python scripts/compare_rbl_hodge.py
```

### Asymmetric Benchmark Results (600 samples)

| Algorithm | Parameters | Adjusted Rand Index (ARI) | Cluster Count | Noise Count |
| :--- | :--- | :--- | :--- | :--- |
| **Hodge Optimized** | $k=44$, $\tau=0.22$, $\text{pct}=93.2\%$, $\text{pct\_density}=80\%$ | **0.8750** | 4 | 19 |
| **Rank-Based Linkage** | $K=50$, $m=150$ | **0.8536** | 7 | 13 |
| **HDBSCAN** | $\text{min\_size}=15$, precomputed symmetric | **0.8457** | 4 | 31 |
| **Hodge Default** | $k=15$, $\tau=0.1$ | **0.1268** | 52 (over-segmented) | 0 |

## References

1. Jiang, Lim, Yao & Ye (2011). "Statistical Ranking and Combinatorial Hodge Theory." *Mathematical Programming*, 127(1), 203–244.
2. Darling, Grilliette, and Logan (2025). "Rank-based linkage I: triplet comparisons and oriented simplicial complexes." *Compositionality*, Volume 8, Issue 2. https://arxiv.org/abs/2302.02200

## License

MIT
