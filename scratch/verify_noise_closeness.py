import numpy as np
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

    # Model
    hodge = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_labels = hodge.fit_predict(D=D)

    noise_idx = np.where(true_labels == -1)[0]
    
    # Split noise points into misclassified (assigned to a cluster) vs correctly classified (assigned to -1)
    misclassified = [i for i in noise_idx if hodge_labels[i] != -1]
    correctly_classified = [i for i in noise_idx if hodge_labels[i] == -1]
    
    print(f"Number of misclassified noise points: {len(misclassified)}")
    print(f"Number of correctly classified noise points: {len(correctly_classified)}")
    
    # Calculate min distance to cluster centers
    dists_misclassified = [min(np.linalg.norm(X[i] - c) for c in centers) for i in misclassified]
    dists_correct = [min(np.linalg.norm(X[i] - c) for c in centers) for i in correctly_classified]
    
    print("\nDistance to nearest cluster center:")
    print("Misclassified Noise (predicted as cluster):")
    print(f"  Mean: {np.mean(dists_misclassified):.4f}")
    print(f"  Min:  {np.min(dists_misclassified):.4f}")
    print(f"  Max:  {np.max(dists_misclassified):.4f}")
    print(f"  75%:  {np.percentile(dists_misclassified, 75):.4f}")
    
    print("\nCorrectly Classified Noise (predicted as noise):")
    print(f"  Mean: {np.mean(dists_correct):.4f}")
    print(f"  Min:  {np.min(dists_correct):.4f}")
    print(f"  Max:  {np.max(dists_correct):.4f}")
    print(f"  25%:  {np.percentile(dists_correct, 25):.4f}")

if __name__ == "__main__":
    main()
