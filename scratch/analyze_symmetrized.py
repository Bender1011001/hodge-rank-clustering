import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from sklearn.metrics import adjusted_rand_score
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
    # We use D_sym for density estimation
    sorted_idx_sym = np.argsort(D_sym[i, :])
    sorted_idx_sym = sorted_idx_sym[sorted_idx_sym != i]
    core_dists[i] = D_sym[i, sorted_idx_sym[k_d - 1]]

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
edge_to_idx = {e: i for i, e in enumerate(edges)}
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
p_min, p_max = np.min(p_raw), np.max(p_raw)
p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

adj_loc = {i: [] for i in range(num_v)}
for u_loc, v_loc in [(local_idx[u], local_idx[v]) for u, v in edges]:
    adj_loc[u_loc].append(v_loc)
    adj_loc[v_loc].append(u_loc)

parent = np.arange(num_v)
sink_potential = p_norm.copy()
def find(i):
    if parent[i] == i: return i
    parent[i] = find(parent[i])
    return parent[i]

sorted_nodes = np.argsort(-p_norm)
visited = np.zeros(num_v, dtype=bool)
for u in sorted_nodes:
    visited[u] = True
    for v in adj_loc[u]:
        if visited[v]:
            root_u, root_v = find(u), find(v)
            if root_u != root_v:
                p_saddle = p_norm[u]
                low, high = (root_u, root_v) if sink_potential[root_u] < sink_potential[root_v] else (root_v, root_u)
                if (sink_potential[low] - p_saddle) < tau:
                    parent[low] = high

cluster_labels_local = np.full(num_v, -1)
unique_roots = {}
cluster_id = 0
for i in range(num_v):
    root = find(i)
    if root not in unique_roots:
        unique_roots[root] = cluster_id
        cluster_id += 1
    cluster_labels_local[i] = unique_roots[root]

core_labels = np.full(n, -1)
for local_id, global_id in enumerate(core_nodes):
    core_labels[global_id] = cluster_labels_local[local_id]

noise_idx = np.where(core_labels == -1)[0]
core_set = set(core_nodes)

# Separate the noise nodes into true cluster vs true noise
true_cluster_noise = [i for i in noise_idx if true_labels[i] != -1]
true_noise_noise = [i for i in noise_idx if true_labels[i] == -1]

dist_true_cluster = []
dist_true_noise = []

# Map using D_sym
for i in true_cluster_noise:
    sorted_targets = np.argsort(D_sym[i, :])
    for target in sorted_targets[sorted_targets != i]:
        if target in core_set:
            dist_true_cluster.append(D_sym[i, target])
            break

for i in true_noise_noise:
    sorted_targets = np.argsort(D_sym[i, :])
    for target in sorted_targets[sorted_targets != i]:
        if target in core_set:
            dist_true_noise.append(D_sym[i, target])
            break

print("Symmetrized distance to nearest core node statistics:")
print(f"True cluster points (N={len(dist_true_cluster)}):")
print(f"  Min:    {np.min(dist_true_cluster):.4f}")
print(f"  25th %: {np.percentile(dist_true_cluster, 25):.4f}")
print(f"  50th %: {np.percentile(dist_true_cluster, 50):.4f}")
print(f"  75th %: {np.percentile(dist_true_cluster, 75):.4f}")
print(f"  90th %: {np.percentile(dist_true_cluster, 90):.4f}")
print(f"  95th %: {np.percentile(dist_true_cluster, 95):.4f}")
print(f"  Max:    {np.max(dist_true_cluster):.4f}")

print(f"\nTrue noise points (N={len(dist_true_noise)}):")
print(f"  Min:    {np.min(dist_true_noise):.4f}")
print(f"  25th %: {np.percentile(dist_true_noise, 25):.4f}")
print(f"  50th %: {np.percentile(dist_true_noise, 50):.4f}")
print(f"  75th %: {np.percentile(dist_true_noise, 75):.4f}")
print(f"  90th %: {np.percentile(dist_true_noise, 90):.4f}")
print(f"  95th %: {np.percentile(dist_true_noise, 95):.4f}")
print(f"  Max:    {np.max(dist_true_noise):.4f}")
