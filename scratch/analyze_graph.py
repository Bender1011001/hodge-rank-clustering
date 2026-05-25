import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
import sys
import os

# Let's rebuild the benchmark dataset
np.random.seed(42)
n_samples = 600
X = np.random.randn(n_samples, 2)
true_labels = np.zeros(n_samples, dtype=int)
centers = np.array([[5, 5], [-5, 5], [5, -5], [-5, -5]])
ppc = 135

for i, c in enumerate(centers):
    X[i * ppc:(i + 1) * ppc] = c + np.random.randn(ppc, 2) * 1.5
    true_labels[i * ppc:(i + 1) * ppc] = i
X[4 * ppc:] = np.random.uniform(-8, 8, size=(n_samples - 4 * ppc, 2))
true_labels[4 * ppc:] = -1

D = np.zeros((n_samples, n_samples))
for i in range(n_samples):
    diff = X - X[i]
    dist = np.linalg.norm(diff, axis=1)
    asym = 1.0 + 0.8 * np.sin(X[i, 0] * X[:, 1] - X[i, 1] * X[:, 0])
    D[i, :] = dist * asym
    D[i, i] = np.inf

# Parameters
k = 44
min_core = 5
pct_density = 80.0
k_d = 5

n = D.shape[0]
ranks = {}
core_dists = np.zeros(n)
for i in range(n):
    sorted_idx = np.argsort(D[i, :])
    sorted_idx = sorted_idx[sorted_idx != i]
    for rank, j in enumerate(sorted_idx[:k]):
        ranks[(i, j)] = rank + 1
    core_dists[i] = D[i, sorted_idx[k_d - 1]]

density_thresh = np.percentile(core_dists, pct_density)
dense_mask = core_dists <= density_thresh

deg = np.zeros(n, dtype=int)
adj = {i: set() for i in range(n)}
for (i, j) in ranks.keys():
    if dense_mask[i] and dense_mask[j]:
        if i < j and (j, i) in ranks:
            adj[i].add(j)
            adj[j].add(i)
            deg[i] += 1
            deg[j] += 1

active = np.ones(n, dtype=bool)
active[~dense_mask] = False
while True:
    to_remove = (deg < min_core) & active
    if not np.any(to_remove):
        break
    for u in np.where(to_remove)[0]:
        active[u] = False
        for v in adj[u]:
            if active[v]:
                deg[v] -= 1
                adj[v].remove(u)

core_nodes = np.where(active)[0]
local_idx = {global_id: loc for loc, global_id in enumerate(core_nodes)}

# Build adjacency matrix of the core graph
num_v = len(core_nodes)
adj_matrix = np.zeros((num_v, num_v))
for u_idx, u in enumerate(core_nodes):
    for v in adj[u]:
        if v in local_idx:
            adj_matrix[u_idx, local_idx[v]] = 1

n_components, labels = connected_components(csgraph=sp.csr_matrix(adj_matrix), directed=False, return_labels=True)
print(f"Number of connected components in the core graph: {n_components}")

# Print component sizes and the distribution of true labels in each component
for comp_id in range(n_components):
    comp_nodes = core_nodes[labels == comp_id]
    true_lbls = true_labels[comp_nodes]
    print(f"Component {comp_id} (Size={len(comp_nodes)}):")
    for tl in [-1, 0, 1, 2, 3]:
        count = np.sum(true_lbls == tl)
        if count > 0:
            print(f"  True Label {tl}: {count}")
