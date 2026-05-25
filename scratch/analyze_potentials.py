import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
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
tau = 0.22
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
edges = [(u, v) for u in core_nodes for v in adj[u] if u < v]
num_v, num_e = len(core_nodes), len(edges)

F = np.zeros(num_e)
r1, c1, d1 = [], [], []
for e_idx, (u, v) in enumerate(edges):
    F[e_idx] = ranks[(v, u)] - ranks[(u, v)]
    u_loc, v_loc = local_idx[u], local_idx[v]
    r1.extend([u_loc, v_loc])
    c1.extend([e_idx, e_idx])
    d1.extend([-1.0, 1.0])

B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))
p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]

# Print average potential for each true cluster
print("Core nodes potential field statistics by True Cluster:")
for tc in [0, 1, 2, 3]:
    # Find which core nodes belong to this true cluster
    tc_nodes = [node for node in core_nodes if true_labels[node] == tc]
    tc_potentials = [p_raw[local_idx[node]] for node in tc_nodes]
    print(f"Cluster {tc} (N={len(tc_nodes)}):")
    print(f"  Mean:   {np.mean(tc_potentials):.4f}")
    print(f"  Min:    {np.min(tc_potentials):.4f}")
    print(f"  Max:    {np.max(tc_potentials):.4f}")
    print(f"  Std:    {np.std(tc_potentials):.4f}")
