import os
import json
import sys
from pathlib import Path

# Add scripts directory to path to import pipelines
sys.path.append(os.path.dirname(__file__))
from benchmark_pipelines import run_elliptic_hodge, run_amlsim_hodge

def main():
    print("Running Financial Benchmarks on Hodge Decomposition...")
    
    # 1. Elliptic Bitcoin Benchmark
    elliptic_classes = r"e:\code.projects\hodge-rank-clustering\.tmp\elliptic\elliptic_txs_classes.csv"
    elliptic_edges = r"e:\code.projects\hodge-rank-clustering\.tmp\elliptic\elliptic_txs_edgelist.csv"
    
    elliptic_results = None
    if os.path.exists(elliptic_classes) and os.path.exists(elliptic_edges):
        try:
            elliptic_results = run_elliptic_hodge(elliptic_classes, elliptic_edges)
            print("\nElliptic Bitcoin Benchmark Results:")
            print(json.dumps(elliptic_results, indent=2))
        except Exception as e:
            print(f"Error running Elliptic Bitcoin benchmark: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Elliptic Bitcoin files not found!")
        
    # 2. IBM AMLSim Benchmark
    amlsim_transactions = r"e:\code.projects\hodge-rank-clustering\.tmp\amlsim\transactions.csv"
    
    amlsim_results = None
    if os.path.exists(amlsim_transactions):
        try:
            amlsim_results = run_amlsim_hodge(amlsim_transactions)
            print("\nIBM AMLSim Benchmark Results:")
            print(json.dumps(amlsim_results, indent=2))
        except Exception as e:
            print(f"Error running IBM AMLSim benchmark: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("IBM AMLSim transactions file not found!")
        
    # Save the combined results
    out_dir = r"e:\code.projects\hodge-rank-clustering\site\data\financial"
    os.makedirs(out_dir, exist_ok=True)
    
    combined = {
        "elliptic": elliptic_results,
        "amlsim": amlsim_results
    }
    
    out_path = os.path.join(out_dir, "summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print(f"\nSaved combined results to {out_path}")

if __name__ == "__main__":
    main()
