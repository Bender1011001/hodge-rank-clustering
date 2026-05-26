import sys
import json
import synapseclient
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.synapse_auth import login_synapse
print("Logging in to Synapse...")
syn = login_synapse()

tmp_dir = ROOT / ".tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

# TF File IDs:
# Net 1: syn2787227
# Net 3: syn2787235
# Net 4: syn2787239
TF_IDS = {1: "syn2787227", 3: "syn2787235", 4: "syn2787239"}

def load_true_tfs(tf_file_id):
    f = syn.get(tf_file_id, downloadLocation=str(tmp_dir))
    true_tfs = set()
    with open(f.path, "r", encoding="utf-8") as handle:
        for line in handle:
            val = line.strip()
            if val:
                true_tfs.add(val)
    # Clean up file
    Path(f.path).unlink()
    return true_tfs

for net_num in [1, 3, 4]:
    print(f"\n--- Evaluating Network {net_num} ---")
    summary_path = ROOT / "site" / "data" / "dream5" / f"summary_net{net_num}.json"
    if not summary_path.exists():
        # Fallback to summary.json for Net 1
        summary_path = ROOT / "site" / "data" / "dream5" / "summary.json"
        
    if not summary_path.exists():
        print(f"Summary file not found for net {net_num}")
        continue
        
    with summary_path.open("r", encoding="utf-8") as f:
        summary = json.load(f)
        
    predicted_tfs_desc = summary["top_regulators"] # Descending
    true_tfs = load_true_tfs(TF_IDS[net_num])
    
    # We load p_norm and sort ascending to check the opposite direction
    # Wait, we can just load the raw potentials from summary.json if available
    # But since we saved the top_regulators in descending order, let's reverse them
    # to see if the tail contains the actual regulators!
    # Let's inspect the summary file keys. The summary has "top_targets" as well!
    # Let's see if the top_targets (which are the lowest potentials/sinks) are the TFs.
    predicted_tfs_asc = summary.get("top_targets", [])
    
    print(f"Total True TFs in benchmark: {len(true_tfs)}")
    
    print("Evaluating Descending Potential (Highest Potential Peaks):")
    matches_desc = sum(1 for p_tf in predicted_tfs_desc if p_tf in true_tfs)
    print(f"  Matches: {matches_desc}/10 ({matches_desc * 10.0:.1f}%)")
    
    print("Evaluating Ascending Potential (Lowest Potential Basins / Sinks):")
    matches_asc = sum(1 for p_tf in predicted_tfs_asc if p_tf["gene"] in true_tfs)
    print(f"  Matches: {matches_asc}/10 ({matches_asc * 10.0:.1f}%)")

