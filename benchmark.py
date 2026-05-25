"""
Benchmark: TrueHodgeRankClustering vs HDBSCAN on asymmetric data.

4 dense clusters + ambient noise with deliberately warped asymmetric
distances: D(x, y) = ||x - y|| * (1 + 0.8 * sin(x cross y)).
HDBSCAN must symmetrize; Hodge works on the raw asymmetric matrix.
"""

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score
from hodge_rank import TrueHodgeRankClustering


def main():
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

    # Instantiating the optimized hyperparameters
    hodge = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_labels = hodge.fit_predict(D=D)

    D_sym = np.maximum(D, D.T)
    hdbscan = HDBSCAN(min_cluster_size=15, metric="precomputed")
    hdbscan_labels = hdbscan.fit_predict(D_sym)

    print(f"Hodge ARI:   {adjusted_rand_score(true_labels, hodge_labels):.4f}")
    print(f"HDBSCAN ARI: {adjusted_rand_score(true_labels, hdbscan_labels):.4f}")
    print(f"Hodge clusters: {len(set(hodge_labels) - {-1})}")
    print(f"HDBSCAN clusters: {len(set(hdbscan_labels) - {-1})}")
    print(f"Core nodes: {len(hodge.core_nodes)}, Edges: {len(hodge.edges)}, Triangles: {hodge.num_triangles}")
    print(f"|F_grad|: {np.linalg.norm(hodge.F_grad):.2f}, "
      f"|F_curl|: {np.linalg.norm(hodge.F_curl):.2f}, "
      f"|F_harm|: {np.linalg.norm(hodge.F_harm):.2f}")


if __name__ == "__main__":
    main()
