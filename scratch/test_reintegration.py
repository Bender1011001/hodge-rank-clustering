import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import HDBSCAN
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

# Let's run Step 1-4 of TrueHodgeRankClustering (core clustering) to get core labels
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

# Now, we test different reintegration strategies on the noise nodes!
noise_idx = np.where(core_labels == -1)[0]
core_set = set(core_nodes)

print(f"Number of core nodes: {len(core_nodes)}")
print(f"Number of noise nodes: {len(noise_idx)}")

# Let's map each noise point to its nearest core point, recording the distance
noise_to_core = {}
for i in noise_idx:
    sorted_targets = np.argsort(D[i, :])
    for target in sorted_targets[sorted_targets != i]:
        if target in core_set:
            lbl = core_labels[target]
            dist = D[i, target]
            noise_to_core[i] = (target, lbl, dist)
            break

# Baseline method: pct percentile of noise-to-core distances
def evaluate_baseline(pct_val):
    cluster_dists = {}
    for i, (target, lbl, dist) in noise_to_core.items():
        if lbl not in cluster_dists:
            cluster_dists[lbl] = []
        cluster_dists[lbl].append(dist)
    
    thresholds = {}
    for lbl, dists_list in cluster_dists.items():
        thresholds[lbl] = np.percentile(dists_list, pct_val)
        
    labels = core_labels.copy()
    for i in noise_idx:
        if i in noise_to_core:
            target, lbl, dist = noise_to_core[i]
            if dist <= thresholds[lbl]:
                labels[i] = lbl
    return adjusted_rand_score(true_labels, labels), labels

# New proposed method: percentile of internal core distances
def evaluate_core_internal(multiplier, pct_val=None):
    # Compute internal core distances:
    # For each cluster, get all its core nodes.
    # Compute pairwise distances within the cluster core nodes, find the distance to nearest core neighbor in the same cluster.
    thresholds = {}
    for lbl in set(cluster_labels_local):
        cluster_nodes = core_nodes[cluster_labels_local == lbl]
        if len(cluster_nodes) < 2:
            thresholds[lbl] = 0.0
            continue
        
        # Compute nearest neighbor distance for each core node in the cluster
        internal_dists = []
        for u in cluster_nodes:
            # Find closest other core node in the same cluster
            other_nodes = cluster_nodes[cluster_nodes != u]
            dists_to_others = D[u, other_nodes]
            internal_dists.append(np.min(dists_to_others))
            
        if pct_val is not None:
            thresholds[lbl] = np.percentile(internal_dists, pct_val) * multiplier
        else:
            thresholds[lbl] = np.median(internal_dists) * multiplier
            
    labels = core_labels.copy()
    for i in noise_idx:
        if i in noise_to_core:
            target, lbl, dist = noise_to_core[i]
            if dist <= thresholds.get(lbl, 0.0):
                labels[i] = lbl
    return adjusted_rand_score(true_labels, labels), labels

print("\n--- BASELINE METRICS ---")
score, _ = evaluate_baseline(93.2)
print(f"Baseline (pct=93.2): {score:.6f}")

print("\n--- CORE INTERNAL DISTANCE METRICS ---")
for mult in [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]:
    score_med, _ = evaluate_core_internal(mult, pct_val=None)
    print(f"Internal (Median * {mult:.1f}): {score_med:.6f}")

for pct_val in [80.0, 90.0, 95.0, 98.0, 100.0]:
    for mult in [1.0, 1.2, 1.5, 2.0]:
        score_pct, _ = evaluate_core_internal(mult, pct_val=pct_val)
        print(f"Internal ({pct_val}th percentile * {mult:.1f}): {score_pct:.6f}")
