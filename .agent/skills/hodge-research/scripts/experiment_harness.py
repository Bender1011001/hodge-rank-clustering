import subprocess
import re
import sys

def run_trial():
    """Executes the monolithic clustering file and extracts the ARI."""
    try:
        # Run the monolithic file (which includes the benchmark)
        result = subprocess.run(
            ['python', 'hodge_clustering.py'], 
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            print(f"ERROR: Execution failed.\n{result.stderr}")
            return None

        # Extract ARI using regex (looking for "Hodge ARI: 0.XXXX")
        match = re.search(r"Hodge ARI:\s+([0-9.]+)", result.stdout)
        if match:
            ari = float(match.group(1))
            return ari
        else:
            print("ERROR: Could not find ARI in output.")
            return None

    except subprocess.TimeoutExpired:
        print("ERROR: Experiment timed out (5-minute budget exceeded).")
        return None

if __name__ == "__main__":
    score = run_trial()
    if score is not None:
        print(f"RESULT_SCORE: {score}")
        sys.exit(0)
    sys.exit(1)
