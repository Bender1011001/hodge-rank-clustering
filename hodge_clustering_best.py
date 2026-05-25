"""
Discrete Hodge Rank Clustering: Monolithic Edition
=================================================
Topological clustering of directed graphs via Discrete Hodge Decomposition.

PROJECT CONTEXT:
Topological clustering of directed graphs via Discrete Hodge Decomposition on 
asymmetric rank flows. It leverages combinatorial Hodge theory to decompose 
directed flow networks into hierarchical (gradient) and cyclic components.

LICENSE: MIT
Copyright (c) 2026
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
(See full LICENSE text for details)
"""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score

class TrueHodgeRankClustering:
    """
    Topological clustering via Discrete Hodge Decomposition on asymmetric
    rank flows.
    """
    def __init__(self, k=15, min_core=2, tau=0.1, pct=100.0, k_d=5, pct_density=100.0):
        self.k = k
        self.min_core = min_core
        self.tau = tau
        self.pct = pct
        self.k_d = k_d
        self.pct_density = pct_density

    def fit_predict(self, X=None, D=None):
        """
        Compute Hodge decomposition and return cluster labels.
        Exactly one of X (features) or D (distance matrix) must be provided.
        """
        if X is None and D is None:
            raise ValueError("Provide either X or D.")
        
        # --- Graph Construction & k-core Pruning ---
        # Extracts mutual edges and iteratively removes nodes with degree < min_core.
        if D is not None:
            n = D.shape[0]
            ranks = {}
            core_dists = np.zeros(n)
            for i in range(n):
                sorted_idx = np.argsort(D[i, :])
                sorted_idx = sorted_idx[sorted_idx != i]
                for rank, j in enumerate(sorted_idx[:self.k]):
                    ranks[(i, j)] = rank + 1
                core_dists[i] = D[i, sorted_idx[self.k_d - 1]]
        else:
            n = X.shape[0]
            max_neighbors = max(self.k, self.k_d)
            nbrs = NearestNeighbors(n_neighbors=max_neighbors + 1).fit(X)
            dists, indices = nbrs.kneighbors(X)
            ranks = {}
            for i in range(n):
                for rank, j in enumerate(indices[i, 1:self.k+1]):
                    ranks[(i, j)] = rank + 1
            core_dists = dists[:, self.k_d]

        if self.pct_density < 100.0:
            density_thresh = np.percentile(core_dists, self.pct_density)
            dense_mask = core_dists <= density_thresh
        else:
            dense_mask = np.ones(n, dtype=bool)

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
            to_remove = (deg < self.min_core) & active
            if not np.any(to_remove):
                break
            for u in np.where(to_remove)[0]:
                active[u] = False
                for v in adj[u]:
                    if active[v]:
                        deg[v] -= 1
                        adj[v].remove(u)

        core_nodes = np.where(active)[0]
        if len(core_nodes) == 0:
            return np.full(n, -1)

        local_idx = {global_id: loc for loc, global_id in enumerate(core_nodes)}
        edges = [(u, v) for u in core_nodes for v in adj[u] if u < v]
        edge_to_idx = {e: i for i, e in enumerate(edges)}
        num_v, num_e = len(core_nodes), len(edges)

        # --- Hodge Decomposition ---
        # F = F_grad + F_curl + F_harm
        F = np.zeros(num_e)
        r1, c1, d1 = [], [], []
        for e_idx, (u, v) in enumerate(edges):
            F[e_idx] = ranks[(v, u)] - ranks[(u, v)]
            u_loc, v_loc = local_idx[u], local_idx[v]
            r1.extend([u_loc, v_loc])
            c1.extend([e_idx, e_idx])
            d1.extend([-1.0, 1.0])

        B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))
        
        # B2 Triangle Enumeration
        r2, c2, d2 = [], [], []
        t_idx = 0
        nodes = sorted(list(core_nodes))
        for u in nodes:
            neighbors_u = sorted([v for v in adj[u] if v > u and active[v]])
            for i in range(len(neighbors_u)):
                v = neighbors_u[i]
                for j in range(i + 1, len(neighbors_u)):
                    w = neighbors_u[j]
                    if w in adj[v]:
                        r2.extend([edge_to_idx[(v, w)], edge_to_idx[(u, w)], edge_to_idx[(u, v)]])
                        c2.extend([t_idx, t_idx, t_idx])
                        d2.extend([1.0, -1.0, 1.0])
                        t_idx += 1
        B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

        p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
        self.F_grad = B1.T.dot(p_raw)
        F_res = F - self.F_grad
        if B2 is not None:
            c = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]
            self.F_curl = B2.dot(c)
        else:
            self.F_curl = np.zeros(num_e)
        self.F_harm = F_res - self.F_curl

        # --- Persistence-based Clustering ---
        # Uses watershed-style Union-Find on the potential field Phi.
        adj_loc = {i: [] for i in range(num_v)}
        for u_loc, v_loc in [(local_idx[u], local_idx[v]) for u, v in edges]:
            adj_loc[u_loc].append(v_loc)
            adj_loc[v_loc].append(u_loc)

        p_min, p_max = np.min(p_raw), np.max(p_raw)
        p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

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
                        if (sink_potential[low] - p_saddle) < self.tau:
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

        # --- Noise Reintegration ---
        labels = np.full(n, -1)
        for local_id, global_id in enumerate(core_nodes):
            labels[global_id] = cluster_labels_local[local_id]
        
        noise_idx = np.where(labels == -1)[0]
        core_set = set(core_nodes)
        
        # Calculate cluster-specific thresholds if self.pct < 100
        noise_to_core = {}
        cluster_dists = {}
        
        for i in noise_idx:
            if D is not None:
                sorted_targets = np.argsort(D[i, :])
                for target in sorted_targets[sorted_targets != i]:
                    if target in core_set:
                        lbl = labels[target]
                        dist = D[i, target]
                        noise_to_core[i] = (target, lbl, dist)
                        if lbl not in cluster_dists:
                            cluster_dists[lbl] = []
                        cluster_dists[lbl].append(dist)
                        break
            else:
                for idx, target in enumerate(indices[i, 1:]):
                    if target in core_set:
                        lbl = labels[target]
                        dist = dists[i, 1 + idx]
                        noise_to_core[i] = (target, lbl, dist)
                        if lbl not in cluster_dists:
                            cluster_dists[lbl] = []
                        cluster_dists[lbl].append(dist)
                        break
                        
        thresholds = {}
        for lbl, dists_list in cluster_dists.items():
            if self.pct < 100.0 and len(dists_list) > 0:
                thresholds[lbl] = np.percentile(dists_list, self.pct)
            else:
                thresholds[lbl] = np.inf

        for i in noise_idx:
            if i in noise_to_core:
                target, lbl, dist = noise_to_core[i]
                thresh = thresholds.get(lbl, np.inf)
                if dist <= thresh:
                    labels[i] = lbl
        
        self.core_nodes, self.edges, self.num_triangles = core_nodes, edges, t_idx
        return labels

def run_benchmark():
    """Reproduces the comparison against HDBSCAN on asymmetric data."""
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

    hodge = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_labels = hodge.fit_predict(D=D)

    hdbscan = HDBSCAN(min_cluster_size=15, metric="precomputed")
    hdbscan_labels = hdbscan.fit_predict(np.maximum(D, D.T))

    print(f"Hodge ARI:   {adjusted_rand_score(true_labels, hodge_labels):.4f}")
    print(f"HDBSCAN ARI: {adjusted_rand_score(true_labels, hdbscan_labels):.4f}")
    print(f"Clusters: Hodge={len(set(hodge_labels)-{-1})}, HDBSCAN={len(set(hdbscan_labels)-{-1})}")

if __name__ == "__main__":
    run_benchmark()
