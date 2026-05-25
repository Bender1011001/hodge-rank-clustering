import numpy as np
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
from hodge_clustering import TrueHodgeRankClustering

def main():
    # Rebuild benchmark dataset
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

    from rbl_clustering import RankBasedLinkageClustering

    # Models
    hodge = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_labels = hodge.fit_predict(D=D)

    rbl = RankBasedLinkageClustering(k=50, max_cluster=150)
    rbl_labels = rbl.fit_predict(D)

    # Format the data for JSON
    data = []
    for i in range(n_samples):
        data.append({
            "id": i,
            "x": float(X[i, 0]),
            "y": float(X[i, 1]),
            "trueLabel": int(true_labels[i]),
            "predLabel": int(hodge_labels[i]),
            "rblLabel": int(rbl_labels[i])
        })
        
    output_path = "site/data/benchmark.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully dumped {n_samples} benchmark points to {output_path}")

if __name__ == "__main__":
    main()
