import numpy as np
from sklearn.metrics import adjusted_rand_score, confusion_matrix
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
from hodge_clustering import TrueHodgeRankClustering

def main():
    # Generate benchmark dataset
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

    # Instantiate model with baseline parameters
    hodge = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_labels = hodge.fit_predict(D=D)

    ari = adjusted_rand_score(true_labels, hodge_labels)
    print(f"Current Hodge ARI: {ari:.6f}")
    
    # 1. Look at confusion/contingency matrix
    # Let's count how many points of each true class mapped to each predicted class
    pred_classes = sorted(list(set(hodge_labels)))
    true_classes = [-1, 0, 1, 2, 3]
    
    print("\nContingency Table (Rows: True label, Cols: Predicted label):")
    header = "True \\ Pred | " + " | ".join(f"{c:4d}" for c in pred_classes)
    print(header)
    print("-" * len(header))
    for tc in true_classes:
        row_str = f"{tc:11d} | "
        counts = []
        for pc in pred_classes:
            cnt = np.sum((true_labels == tc) & (hodge_labels == pc))
            counts.append(f"{cnt:4d}")
        print(row_str + " | ".join(counts))

    # 2. Check coordinates of misclassified points
    # Let's identify the points that are:
    # - True noise (-1) classified as a cluster (0, 1, 2, 3)
    # - True cluster points classified as noise (-1)
    # - True cluster points classified as the wrong cluster
    noise_as_cluster = np.where((true_labels == -1) & (hodge_labels != -1))[0]
    cluster_as_noise = np.where((true_labels != -1) & (hodge_labels == -1))[0]
    
    wrong_cluster = []
    for tc in [0, 1, 2, 3]:
        for pc in [0, 1, 2, 3]:
            if tc != pc:
                idx = np.where((true_labels == tc) & (hodge_labels == pc))[0]
                if len(idx) > 0:
                    wrong_cluster.extend(list(idx))

    print(f"\nNumber of True Noise classified as Cluster: {len(noise_as_cluster)}")
    print(f"Number of True Cluster classified as Noise: {len(cluster_as_noise)}")
    print(f"Number of Cluster points in wrong Cluster: {len(wrong_cluster)}")

    if len(cluster_as_noise) > 0:
        print("\nExamples of True Cluster points classified as Noise:")
        for idx in cluster_as_noise[:10]:
            print(f"  ID {idx:3d}: True Class {true_labels[idx]}, Coordinates: ({X[idx, 0]:.2f}, {X[idx, 1]:.2f})")
            
    if len(noise_as_cluster) > 0:
        print("\nExamples of True Noise classified as Cluster:")
        for idx in noise_as_cluster[:10]:
            print(f"  ID {idx:3d}: Predicted Class {hodge_labels[idx]}, Coordinates: ({X[idx, 0]:.2f}, {X[idx, 1]:.2f})")

if __name__ == "__main__":
    main()
