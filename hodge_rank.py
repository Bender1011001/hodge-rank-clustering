"""
Discrete Hodge Rank Clustering
===============================
Topological clustering of directed graphs via Discrete Hodge Decomposition
on asymmetric rank flows.

Algorithm overview:
    1. Build a mutual K-NN graph from pairwise data (features or distance matrix).
    2. Apply k-core pruning to remove dangling periphery.
    3. Construct boundary matrices B1 (vertex-edge) and B2 (edge-triangle).
    4. Solve the least-squares Hodge decomposition:
         F = F_grad + F_curl + F_harm
       where F_grad = B1^T * Phi captures hierarchy,
             F_curl captures local triangle loops,
             F_harm captures global topological circulations.
    5. Cluster via steepest-ascent on the potential field Phi.

Reference:
    Jiang, Lim, Yao & Ye (2011). "Statistical Ranking and Combinatorial
    Hodge Theory." Mathematical Programming, 127(1), 203-244.

Dependencies:
    numpy, scipy, scikit-learn
"""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from sklearn.neighbors import NearestNeighbors


class TrueHodgeRankClustering:
    """
    Topological clustering via Discrete Hodge Decomposition on asymmetric
    rank flows.

    Parameters
    ----------
    k : int, default=15
        Number of nearest neighbors for mutual K-NN graph construction.
    min_core : int, default=2
        Minimum degree for k-core pruning. Nodes with fewer mutual edges
        are iteratively removed before decomposition.

    Attributes (available after fit_predict)
    -----------------------------------------
    potential : ndarray of shape (n_core_nodes,)
        Hodge potential Phi for each core node. Higher values indicate
        topological sinks (receivers); lower values indicate sources.
    F_grad : ndarray of shape (n_edges,)
        Gradient component of edge flow (hierarchical structure).
    F_curl : ndarray of shape (n_edges,)
        Curl component of edge flow (local triangle loops).
    F_harm : ndarray of shape (n_edges,)
        Harmonic component of edge flow (global topological cycles).
    core_nodes : ndarray
        Indices of nodes that survived k-core pruning.
    edges : list of (int, int)
        Mutual edges in the core graph (u < v convention).
    num_triangles : int
        Number of 2-simplices (triangles) enumerated for B2.
    """

    def __init__(self, k=15, min_core=2):
        self.k = k
        self.min_core = min_core

    def fit_predict(self, X=None, D=None):
        """
        Compute Hodge decomposition and return cluster labels.

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_features), optional
            Feature matrix. Mutual K-NN is built from Euclidean distances.
        D : ndarray of shape (n_samples, n_samples), optional
            Precomputed asymmetric distance/preference matrix.
            D[i,j] need not equal D[j,i].

        Returns
        -------
        labels : ndarray of shape (n_samples,)
            Cluster label for each sample. -1 indicates unassigned noise.

        Notes
        -----
        Exactly one of X or D must be provided.
        """
        if X is None and D is None:
            raise ValueError("Provide either X (feature matrix) or D (distance matrix).")
        if X is not None and D is not None:
            raise ValueError("Provide only one of X or D, not both.")

        indices = None  # KNN indices, used for noise reintegration when X is provided

        if D is not None:
            n = D.shape[0]
            ranks = {}
            for i in range(n):
                sorted_idx = np.argsort(D[i, :])
                sorted_idx = sorted_idx[sorted_idx != i]
                for rank, j in enumerate(sorted_idx[:self.k]):
                    ranks[(i, j)] = rank + 1
        else:
            n = X.shape[0]
            nbrs = NearestNeighbors(n_neighbors=self.k + 1).fit(X)
            _, indices = nbrs.kneighbors(X)
            ranks = {}
            for i in range(n):
                for rank, j in enumerate(indices[i, 1:]):
                    ranks[(i, j)] = rank + 1

        # --- Step 1: Extract mutual edges and apply k-core pruning ---
        deg = np.zeros(n, dtype=int)
        adj = {i: set() for i in range(n)}
        for (i, j) in ranks.keys():
            if i < j and (j, i) in ranks:
                adj[i].add(j)
                adj[j].add(i)
                deg[i] += 1
                deg[j] += 1

        active = np.ones(n, dtype=bool)
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

        # --- Step 2: Build 1-form flow vector F and boundary matrix B1 ---
        F = np.zeros(num_e)
        r1, c1, d1 = [], [], []

        for e_idx, (u, v) in enumerate(edges):
            F[e_idx] = ranks[(v, u)] - ranks[(u, v)]
            u_loc, v_loc = local_idx[u], local_idx[v]
            r1.extend([u_loc, v_loc])
            c1.extend([e_idx, e_idx])
            d1.extend([-1.0, 1.0])

        B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))

        # --- Step 3: Enumerate triangles (2-simplices) for B2 ---
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
                        r2.extend([edge_to_idx[(v, w)],
                                   edge_to_idx[(u, w)],
                                   edge_to_idx[(u, v)]])
                        c2.extend([t_idx, t_idx, t_idx])
                        d2.extend([1.0, -1.0, 1.0])
                        t_idx += 1

        B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

        # --- Step 4: Hodge decomposition via LSQR ---
        p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
        self.F_grad = B1.T.dot(p_raw)
        F_res = F - self.F_grad

        if B2 is not None:
            c = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]
            self.F_curl = B2.dot(c)
        else:
            self.F_curl = np.zeros(num_e)

        self.F_harm = F_res - self.F_curl

        self.potential = p_raw
        self.core_nodes = core_nodes
        self.local_idx = local_idx
        self.edges = edges
        self.num_triangles = t_idx

        # --- Step 5: Steepest-ascent clustering on the potential field ---
        adj_loc = {i: [] for i in range(num_v)}
        for u_loc, v_loc in [(local_idx[u], local_idx[v]) for u, v in edges]:
            adj_loc[u_loc].append(v_loc)
            adj_loc[v_loc].append(u_loc)

        flow_target = np.arange(num_v)
        for i in range(num_v):
            best_target, best_p = i, p_raw[i]
            for neighbor in adj_loc[i]:
                if p_raw[neighbor] > best_p:
                    best_p, best_target = p_raw[neighbor], neighbor
            flow_target[i] = best_target

        cluster_labels_local = np.full(num_v, -1)
        current_cluster_id = 0
        for i in range(num_v):
            if cluster_labels_local[i] != -1:
                continue
            curr = i
            path = []
            visited = set()
            while (flow_target[curr] != curr
                   and cluster_labels_local[curr] == -1
                   and curr not in visited):
                path.append(curr)
                visited.add(curr)
                curr = flow_target[curr]

            if cluster_labels_local[curr] == -1:
                cluster_labels_local[curr] = current_cluster_id
                current_cluster_id += 1

            sink_id = cluster_labels_local[curr]
            for node in path:
                cluster_labels_local[node] = sink_id

        # --- Step 6: Reintegrate noise (non-core) nodes ---
        labels = np.full(n, -1)
        for local_id, global_id in enumerate(core_nodes):
            labels[global_id] = cluster_labels_local[local_id]

        noise_idx = np.where(labels == -1)[0]
        core_set = set(core_nodes)

        for i in noise_idx:
            if D is not None:
                sorted_targets = np.argsort(D[i, :])
                sorted_targets = sorted_targets[sorted_targets != i]
                for target in sorted_targets:
                    if target in core_set:
                        labels[i] = labels[target]
                        break
            else:
                for target in indices[i, 1:]:
                    if target in core_set:
                        labels[i] = labels[target]
                        break

        return labels
