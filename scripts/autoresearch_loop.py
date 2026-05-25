import sys
import os
import time
import random
import re
import numpy as np
from sklearn.metrics import adjusted_rand_score
from sklearn.cluster import HDBSCAN

# Import the class from the local directory
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
from hodge_clustering import TrueHodgeRankClustering

def run_benchmark_with_params(k, min_core, tau, pct, k_d, pct_density, flow_type, beta, saddle_type, D, true_labels):
    """Instantiates the clustering class with given parameters and returns the ARI."""
    try:
        hodge = TrueHodgeRankClustering(
            k=int(k),
            min_core=int(min_core),
            tau=float(tau),
            pct=float(pct),
            k_d=int(k_d),
            pct_density=float(pct_density),
            flow_type=int(flow_type),
            beta=float(beta),
            saddle_type=int(saddle_type)
        )
        hodge_labels = hodge.fit_predict(D=D)
        
        # If all nodes are noise, return 0.0
        if np.all(hodge_labels == -1):
            return 0.0
            
        score = adjusted_rand_score(true_labels, hodge_labels)
        return score
    except Exception as e:
        # Prevent search from crashing on invalid parameter combinations
        return 0.0

def update_hodge_clustering_file(k, min_core, tau, pct, k_d, pct_density, flow_type, beta, saddle_type):
    """Updates hodge_clustering.py with the new best defaults and benchmark parameters."""
    filepath = "hodge_clustering.py"
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex for constructor __init__ signature
    init_pattern = r"def __init__\([^)]*\):"
    new_init = (
        f"def __init__(self, k={int(k)}, min_core={int(min_core)}, tau={tau:.4f}, "
        f"pct={pct:.4f}, k_d={int(k_d)}, pct_density={pct_density:.4f}, "
        f"flow_type={int(flow_type)}, beta={beta:.4f}, saddle_type={int(saddle_type)}):"
    )
    content = re.sub(init_pattern, new_init, content)

    # Regex for benchmark instantiation
    bench_pattern = r"hodge = TrueHodgeRankClustering\([^)]*\)"
    new_bench = (
        f"hodge = TrueHodgeRankClustering(k={int(k)}, min_core={int(min_core)}, tau={tau:.4f}, "
        f"pct={pct:.4f}, k_d={int(k_d)}, pct_density={pct_density:.4f}, "
        f"flow_type={int(flow_type)}, beta={beta:.4f}, saddle_type={int(saddle_type)})"
    )
    content = re.sub(bench_pattern, new_bench, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Successfully wrote new best parameters to {filepath}")

def update_results_log(iteration, desc, score, outcome, best_score):
    """Logs the iteration details to results_log.md."""
    filepath = "results_log.md"
    if not os.path.exists(filepath):
        # Create file if missing
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Hodge Rank Clustering Optimization Results Log\n\n")
            f.write("| Iteration | Parameters/Logic Changed | Score | Outcome | Best Score |\n")
            f.write("|---|---|---|---|---|\n")

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Filter out empty lines at the end to clean up formatting
    while lines and lines[-1].strip() == "":
        lines.pop()

    new_row = f"| {iteration} | {desc} | {score:.4f} | {outcome} | {best_score:.4f} |\n"
    lines.append(new_row)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)
        f.write("\n")
    print(f"Logged iteration {iteration} to {filepath}")

def get_next_iteration_num():
    """Reads results_log.md and determines the next iteration number."""
    filepath = "results_log.md"
    if not os.path.exists(filepath):
        return 8 # Default fallback
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find all iteration numbers in the markdown table
    matches = re.findall(r"\|\s*(\d+)\s*\|", content)
    if matches:
        return max(int(m) for m in matches) + 1
    return 8

def main():
    # Setup execution duration (default to 110 minutes if not specified)
    duration_minutes = 110.0
    if len(sys.argv) > 1:
        try:
            duration_minutes = float(sys.argv[1])
        except ValueError:
            pass

    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    print(f"Starting Hodge Rank Clustering Optimization Loop...")
    print(f"Will run for {duration_minutes:.1f} minutes, ending around {time.strftime('%I:%M:%S %p', time.localtime(end_time))}")

    # Generate benchmark dataset (as in hodge_clustering.py)
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

    # Initialize baseline
    best_score = 0.8750
    best_params = {
        'k': 44, 'min_core': 5, 'tau': 0.22, 'pct': 93.2, 'k_d': 5, 'pct_density': 80.0,
        'flow_type': 0, 'beta': 1.0, 'saddle_type': 0
    }
    
    # Verify current best parameters yield baseline score
    current_ari = run_benchmark_with_params(**best_params, D=D, true_labels=true_labels)
    print(f"Current verification score: {current_ari:.4f} (expected baseline >= 0.8750)")
    if current_ari > best_score:
        best_score = current_ari

    iteration = get_next_iteration_num()
    trials_run = 0

    # Define hyperparameter search ranges
    # We sample randomly from these ranges
    while time.time() < end_time:
        # Sample parameters
        k = random.choice([20, 25, 30, 35, 40, 42, 44, 46, 48, 50, 55, 60, 70, 80])
        min_core = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15])
        tau = random.uniform(0.001, 0.6)
        pct = random.uniform(50.0, 100.0)
        k_d = random.choice([2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20])
        pct_density = random.uniform(50.0, 100.0)
        flow_type = random.choice([0, 1, 2, 3])
        beta = random.uniform(0.1, 3.0)
        saddle_type = random.choice([0, 1])

        score = run_benchmark_with_params(
            k, min_core, tau, pct, k_d, pct_density, flow_type, beta, saddle_type, D, true_labels
        )
        trials_run += 1

        if score > best_score:
            print(f"\n[Trial {trials_run}] Found improvement: {score:.5f} > {best_score:.5f}")
            print(f"Parameters: k={k}, min_core={min_core}, tau={tau:.4f}, pct={pct:.4f}, k_d={k_d}, pct_density={pct_density:.4f}, flow_type={flow_type}, beta={beta:.4f}, saddle_type={saddle_type}")
            
            # Initiate Hill Climbing / Coordinate Ascent to locate the local optimum
            hc_params = {
                'k': k, 'min_core': min_core, 'tau': tau, 'pct': pct, 'k_d': k_d, 
                'pct_density': pct_density, 'flow_type': flow_type, 'beta': beta, 'saddle_type': saddle_type
            }
            hc_score = score
            improved = True
            
            while improved:
                improved = False
                # Define neighbors to check
                neighbors = []
                
                # Check perturbations on each dimension
                for p_name in ['k', 'min_core', 'tau', 'pct', 'k_d', 'pct_density', 'beta']:
                    temp_params = hc_params.copy()
                    
                    if p_name == 'k':
                        for delta in [-5, -2, -1, 1, 2, 5]:
                            new_val = max(5, min(100, temp_params['k'] + delta))
                            temp_params['k'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'min_core':
                        for delta in [-2, -1, 1, 2]:
                            new_val = max(1, min(30, temp_params['min_core'] + delta))
                            temp_params['min_core'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'k_d':
                        for delta in [-2, -1, 1, 2]:
                            new_val = max(1, min(30, temp_params['k_d'] + delta))
                            temp_params['k_d'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'tau':
                        for delta in [-0.05, -0.01, 0.01, 0.05]:
                            new_val = max(0.001, min(1.0, temp_params['tau'] + delta))
                            temp_params['tau'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'pct':
                        for delta in [-5.0, -1.0, 1.0, 5.0]:
                            new_val = max(30.0, min(100.0, temp_params['pct'] + delta))
                            temp_params['pct'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'pct_density':
                        for delta in [-5.0, -2.0, 2.0, 5.0]:
                            new_val = max(30.0, min(100.0, temp_params['pct_density'] + delta))
                            temp_params['pct_density'] = new_val
                            neighbors.append((temp_params.copy(), p_name))
                    elif p_name == 'beta':
                        for delta in [-0.2, -0.05, 0.05, 0.2]:
                            new_val = max(0.01, min(5.0, temp_params['beta'] + delta))
                            temp_params['beta'] = new_val
                            neighbors.append((temp_params.copy(), p_name))

                # Evaluate all neighbors
                for neighbor_params, p_name in neighbors:
                    n_score = run_benchmark_with_params(**neighbor_params, D=D, true_labels=true_labels)
                    trials_run += 1
                    if n_score > hc_score:
                        hc_score = n_score
                        hc_params = neighbor_params
                        improved = True
                        print(f"  [HC - {p_name}] Improved score to {hc_score:.5f}")
                        break # Greedy choice: take the first improvement and start next coordinate step
            
            # Save the best parameters found by random search + hill climbing
            best_score = hc_score
            best_params = hc_params
            
            # Format the change description
            desc = (
                f"Optimized parameters: k={best_params['k']}, min_core={best_params['min_core']}, "
                f"tau={best_params['tau']:.4f}, pct={best_params['pct']:.4f}, k_d={best_params['k_d']}, "
                f"pct_density={best_params['pct_density']:.4f}, flow_type={best_params['flow_type']}, "
                f"beta={best_params['beta']:.4f}, saddle_type={best_params['saddle_type']}"
            )
            
            # Update source code file
            update_hodge_clustering_file(**best_params)
            
            # Log to results_log.md
            update_results_log(
                iteration=iteration,
                desc=desc,
                score=best_score,
                outcome="Improved",
                best_score=best_score
            )
            iteration += 1

        # Periodically output heartbeat to prevent stdout buffer or process silence issues
        if trials_run % 200 == 0:
            elapsed = time.time() - start_time
            print(f"Heartbeat: {trials_run} trials evaluated. Elapsed: {elapsed/60:.1f} mins. Current Best Score: {best_score:.5f}")
            sys.stdout.flush()

    print(f"\nOptimization loop finished. Evaluated {trials_run} trials total.")
    print(f"Final Best Score: {best_score:.5f}")
    print(f"Final Parameters: {best_params}")

if __name__ == "__main__":
    main()
