import numpy as np
import sys
import os

def main():
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

    # Find the 60 true noise points
    noise_idx = np.where(true_labels == -1)[0]
    noise_coords = X[noise_idx]
    
    print("Analysis of 60 true noise points:")
    print("---------------------------------")
    
    # For each noise point, find its minimum Euclidean distance to any cluster center
    distances_to_centers = []
    for coord in noise_coords:
        dists = [np.linalg.norm(coord - c) for c in centers]
        distances_to_centers.append(min(dists))
        
    distances_to_centers = np.array(distances_to_centers)
    
    # Print the counts at various distance thresholds
    for thresh in [1.0, 1.5, 2.0, 3.0, 4.0, 5.0]:
        count = np.sum(distances_to_centers <= thresh)
        print(f"Noise points within distance {thresh:.1f} of any cluster center: {count} ({count/60*100:.1f}%)")
        
    # Also calculate the density (PDF) of the Gaussian mixtures at these noise points
    # to see if they are in high-density regions
    from scipy.stats import multivariate_normal
    pdfs = []
    for coord in noise_coords:
        pdf_val = 0
        for c in centers:
            # Gaussian std is 1.5, so covariance is 1.5^2 * I = 2.25 * I
            pdf_val += multivariate_normal.pdf(coord, mean=c, cov=2.25)
        # Normalization factor of the mixture
        pdfs.append(pdf_val * (135 / 600))
    
    pdfs = np.array(pdfs)
    
    # Find the density of the 5th percentile of the true cluster points
    cluster_coords = X[true_labels != -1]
    cluster_pdfs = []
    for coord in cluster_coords:
        pdf_val = 0
        for c in centers:
            pdf_val += multivariate_normal.pdf(coord, mean=c, cov=2.25)
        cluster_pdfs.append(pdf_val * (135 / 600))
    cluster_pdfs = np.array(cluster_pdfs)
    
    thresh_pdf = np.percentile(cluster_pdfs, 10) # 10th percentile of cluster density
    print(f"\n10th percentile density of true cluster points: {thresh_pdf:.6e}")
    
    noise_in_cluster_density = np.sum(pdfs >= thresh_pdf)
    print(f"Noise points with density >= 10th percentile of cluster points: {noise_in_cluster_density} ({noise_in_cluster_density/60*100:.1f}%)")
    
if __name__ == "__main__":
    main()
