import numpy as np
import scipy.sparse as sp
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

# Symmetrized D
D_sym = 0.5 * (D + D.T)

# Parameters
k = 44
min_core = 5
pct_density = 80.0
k_d = 5

n = D.shape[0]
ranks = {}
core_dists_sym = np.zeros(n)
for i in range(n):
    sorted_idx = np.argsort(D[i, :])
    sorted_idx = sorted_idx[sorted_idx != i]
    for rank, j in enumerate(sorted_idx[:k]):
        ranks[(i, j)] = rank + 1
    
    # Calculate core_dists_sym using D_sym
    sorted_idx_sym = np.argsort(D_sym[i, :])
    sorted_idx_sym = sorted_idx_sym[sorted_idx_sym != i]
    core_dists_sym[i] = D_sym[i, sorted_idx_sym[k_d - 1]]

density_thresh = np.percentile(core_dists_sym, pct_density)
dense_mask = core_dists_sym <= density_thresh

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
noise_idx = np.where(~active)[0]

true_cluster_noise = [i for i in noise_idx if true_labels[i] != -1]
true_noise_noise = [i for i in noise_idx if true_labels[i] == -1]

cd_true_cluster = core_dists_sym[true_cluster_noise]
cd_true_noise = core_dists_sym[true_noise_noise]

print("core_dists_sym (symmetrized density) statistics for noise nodes:")
print(f"True cluster points in noise (N={len(cd_true_cluster)}):")
print(f"  Min:    {np.min(cd_true_cluster):.4f}")
print(f"  25th %: {np.percentile(cd_true_cluster, 25):.4f}")
print(f"  50th %: {np.percentile(cd_true_cluster, 50):.4f}")
print(f"  75th %: {np.percentile(cd_true_cluster, 75):.4f}")
print(f"  90th %: {np.percentile(cd_true_cluster, 90):.4f}")
print(f"  95th %: {np.percentile(cd_true_cluster, 95):.4f}")
print(f"  Max:    {np.max(cd_true_cluster):.4f}")

print(f"\nTrue noise points in noise (N={len(cd_true_noise)}):")
print(f"  Min:    {np.min(cd_true_noise):.4f}")
print(f"  25th %: {np.percentile(cd_true_noise, 25):.4f}")
print(f"  50th %: {np.percentile(cd_true_noise, 50):.4f}")
print(f"  75th %: {np.percentile(cd_true_noise, 75):.4f}")
print(f"  90th %: {np.percentile(cd_true_noise, 90):.4f}")
print(f"  95th %: {np.percentile(cd_true_noise, 95):.4f}")
print(f"  Max:    {np.max(cd_true_noise):.4f}")
