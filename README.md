# Discrete Hodge Rank Clustering

Topological clustering of directed graphs via Discrete Hodge Decomposition on asymmetric rank flows.

Standard spectral methods (Louvain, spectral clustering, HDBSCAN) force you to symmetrize your adjacency or distance matrix before clustering. This throws away directional information. Hodge Rank Clustering works directly on asymmetric pairwise data by decomposing edge flows into three orthogonal components using the combinatorial Hodge decomposition, then clustering via steepest ascent on the recovered potential field.

## How it works

Given a directed graph (or an asymmetric distance/preference matrix), the algorithm:

1. **Builds a mutual K-NN graph** from the pairwise data and applies k-core pruning to remove dangling periphery.
2. **Constructs boundary matrices** B_1 (vertex-edge incidence, with -1 at the tail and +1 at the head) and B_2 (edge-triangle incidence mapping edges to 2-simplices).
3. **Solves the Hodge decomposition** via LSQR:
   - **Gradient flow** (F_grad): the component explainable by a global vertex potential Φ. This is the hierarchical structure — "who ranks above whom."
   - **Curl flow** (F_curl): local cyclic flow around triangles. Rock-paper-scissors patterns.
   - **Harmonic flow** (F_harm): global topological cycles not captured by gradient or curl. Genuinely ambiguous circular structure.
4. **Clusters via persistence-based topological simplification** on the potential field Φ. Local maxima (sinks) are identified, and shallow basins of attraction are merged into deeper ones using a relative persistence threshold $\tau$. Nodes are assigned to the remaining persistent sinks.
5. **Reintegrates noise nodes** (those pruned by k-core) by assigning them to the cluster of their nearest core neighbor.

The decomposition is exact: F = F_grad + F_curl + F_harm, and the three components are mutually orthogonal.

## Installation

```bash
pip install numpy scipy scikit-learn
```

Then clone this repo:

```bash
git clone https://github.com/Bender1011001/hodge-rank-clustering.git
cd hodge-rank-clustering
```

Or install dependencies from the requirements file:

```bash
pip install -r requirements.txt
```

## Quick start

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

# Cluster
model = TrueHodgeRankClustering(k=15, min_core=2)
labels = model.fit_predict(D=D)

# Inspect decomposition
print(f"Clusters found: {len(set(labels) - {-1})}")
print(f"Core nodes: {len(model.core_nodes)}")
print(f"Triangles enumerated: {model.num_triangles}")
print(f"|F_grad|={np.linalg.norm(model.F_grad):.2f}  "
      f"|F_curl|={np.linalg.norm(model.F_curl):.2f}  "
      f"|F_harm|={np.linalg.norm(model.F_harm):.2f}")
```

You can also pass a feature matrix directly — the algorithm builds the K-NN graph internally:

```python
labels = model.fit_predict(X=X)
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `k` | 15 | Number of nearest neighbors for mutual K-NN graph construction |
| `min_core` | 2 | Minimum degree for k-core pruning. Nodes with fewer mutual edges are iteratively removed before decomposition |
| `tau` | 0.1 | Topological simplification (persistence) threshold relative to potential range. Merges shallow basins of attraction. |

## Attributes (after `fit_predict`)

| Attribute | Description |
|-----------|-------------|
| `potential` | Hodge potential Φ for each core node. Higher = sink, lower = source |
| `F_grad` | Gradient component of edge flow (hierarchy) |
| `F_curl` | Curl component (local triangle loops) |
| `F_harm` | Harmonic component (global topological cycles) |
| `core_nodes` | Indices of nodes surviving k-core pruning |
| `edges` | Mutual edges in the core graph |
| `num_triangles` | Number of 2-simplices enumerated for B_2 |

## Benchmark

The included `benchmark.py` runs TrueHodgeRankClustering against HDBSCAN on a synthetic dataset with four dense clusters, ambient noise, and deliberately warped asymmetric distances (D(x,y) ≠ D(y,x)).

```bash
python benchmark.py
```

## Reference

Jiang, Lim, Yao & Ye (2011). "Statistical Ranking and Combinatorial Hodge Theory." *Mathematical Programming*, 127(1), 203–244.

## License

MIT
