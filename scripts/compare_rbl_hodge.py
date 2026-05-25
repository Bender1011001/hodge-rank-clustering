import sys
import os
import numpy as np
from sklearn.metrics import adjusted_rand_score
from sklearn.cluster import HDBSCAN

# Add root directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
from hodge_clustering import TrueHodgeRankClustering
from rbl_clustering import RankBasedLinkageClustering

def main():
    print("Generating asymmetric benchmark dataset (600 samples)...")
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

    # --- 1. Evaluate HDBSCAN ---
    print("\nRunning HDBSCAN...")
    hdbscan = HDBSCAN(min_cluster_size=15, metric="precomputed")
    hdbscan_labels = hdbscan.fit_predict(np.maximum(D, D.T))
    hdbscan_ari = adjusted_rand_score(true_labels, hdbscan_labels)
    hdbscan_n_clusters = len(set(hdbscan_labels) - {-1})
    hdbscan_n_noise = np.sum(hdbscan_labels == -1)
    print(f"HDBSCAN ARI:   {hdbscan_ari:.4f} | Clusters: {hdbscan_n_clusters} | Noise: {hdbscan_n_noise}")

    # --- 2. Evaluate Hodge Rank Clustering ---
    print("\nRunning TrueHodgeRankClustering (with constructor defaults)...")
    hodge_def = TrueHodgeRankClustering()
    hodge_def_labels = hodge_def.fit_predict(D=D)
    hodge_def_ari = adjusted_rand_score(true_labels, hodge_def_labels)
    print(f"Hodge Default ARI:   {hodge_def_ari:.4f} | Clusters: {len(set(hodge_def_labels) - {-1})} | Noise: {np.sum(hodge_def_labels == -1)}")

    print("\nRunning TrueHodgeRankClustering (with optimized hyperparameters)...")
    hodge_opt = TrueHodgeRankClustering(k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0)
    hodge_opt_labels = hodge_opt.fit_predict(D=D)
    hodge_opt_ari = adjusted_rand_score(true_labels, hodge_opt_labels)
    hodge_opt_n_clusters = len(set(hodge_opt_labels) - {-1})
    hodge_opt_n_noise = np.sum(hodge_opt_labels == -1)
    print(f"Hodge Optimized ARI: {hodge_opt_ari:.4f} | Clusters: {hodge_opt_n_clusters} | Noise: {hodge_opt_n_noise}")
    print(f"  Parameters: k={hodge_opt.k}, min_core={hodge_opt.min_core}, tau={hodge_opt.tau:.4f}, pct={hodge_opt.pct:.4f}, k_d={hodge_opt.k_d}, pct_density={hodge_opt.pct_density:.4f}")

    # --- 3. Evaluate Rank-Based Linkage (RBL) ---
    print("\nEvaluating Rank-Based Linkage (RBL) over parameter grid...")
    best_rbl_score = -1.0
    best_rbl_params = {}
    best_rbl_labels = None
    
    k_values = [5, 8, 10, 12, 15, 20, 25, 30, 40, 50]
    max_cluster_values = [None, 50, 100, 135, 150, 200]
    
    results = []
    
    for k in k_values:
        for m in max_cluster_values:
            rbl = RankBasedLinkageClustering(k=k, max_cluster=m)
            rbl_labels = rbl.fit_predict(D)
            score = adjusted_rand_score(true_labels, rbl_labels)
            
            n_clusters = len(set(rbl_labels) - {-1})
            n_noise = np.sum(rbl_labels == -1)
            
            results.append((k, m, score, n_clusters, n_noise))
            
            if score > best_rbl_score:
                best_rbl_score = score
                best_rbl_params = {'k': k, 'max_cluster': m, 'threshold': rbl.selected_threshold, 'max_insway': rbl.max_insway}
                best_rbl_labels = rbl_labels

    # Sort results by score descending
    results.sort(key=lambda x: x[2], reverse=True)

    print("\nTop 10 RBL Parameter Configurations:")
    print(f"{'K':<5} | {'Max Cluster':<12} | {'ARI':<8} | {'Clusters':<8} | {'Noise':<5}")
    print("-" * 50)
    for k, m, score, n_clust, n_noise in results[:10]:
        m_str = str(m) if m is not None else "Sub-critical"
        print(f"{k:<5} | {m_str:<12} | {score:.4f} | {n_clust:<8} | {n_noise:<5}")

    print("\nBest RBL Configuration Details:")
    print(f"  Best ARI: {best_rbl_score:.4f}")
    print(f"  Parameters: k={best_rbl_params['k']}, max_cluster={best_rbl_params['max_cluster']}")
    print(f"  Selected threshold: {best_rbl_params['threshold']} (out of max in-sway {best_rbl_params['max_insway']})")

    # --- 4. Comparison Summary ---
    print("\n" + "="*50)
    print("COMPARISON SUMMARY")
    print("="*50)
    print(f"HDBSCAN ARI:                  {hdbscan_ari:.4f}")
    print(f"Hodge Default ARI:            {hodge_def_ari:.4f}")
    print(f"Hodge Optimized ARI:          {hodge_opt_ari:.4f}")
    print(f"Rank-Based Linkage (RBL) ARI: {best_rbl_score:.4f}")
    print("="*50)
    
    comparison_file = "rbl_vs_hodge_comparison.txt"
    with open(comparison_file, "w") as f:
        f.write("Rank-Based Linkage vs Hodge Rank Clustering Comparison\n")
        f.write("=====================================================\n\n")
        f.write(f"HDBSCAN ARI:                  {hdbscan_ari:.4f}\n")
        f.write(f"Hodge Default ARI:            {hodge_def_ari:.4f}\n")
        f.write(f"Hodge Optimized ARI:          {hodge_opt_ari:.4f}\n")
        f.write(f"Rank-Based Linkage (RBL) ARI: {best_rbl_score:.4f}\n\n")
        f.write(f"Best RBL Parameters: k={best_rbl_params['k']}, max_cluster={best_rbl_params['max_cluster']}\n")
        f.write(f"Best Hodge Parameters: k={hodge_opt.k}, min_core={hodge_opt.min_core}, tau={hodge_opt.tau:.4f}, pct={hodge_opt.pct:.4f}, k_d={hodge_opt.k_d}, pct_density={hodge_opt.pct_density:.4f}\n")

        
    print(f"Saved textual summary to {comparison_file}")

if __name__ == "__main__":
    main()
