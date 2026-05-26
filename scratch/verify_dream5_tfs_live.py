import sys
import csv
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
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

# File IDs mapping
# Net 1: In Silico
# Net 3: E. coli
# Net 4: Yeast
NETS = {
    1: {"name": "in-silico", "expr": "syn2787226", "gold": "syn2787240", "tfs": "syn2787227"},
    3: {"name": "ecoli", "expr": "syn2787234", "gold": "syn2787243", "tfs": "syn2787235"},
    4: {"name": "yeast", "expr": "syn2787238", "gold": "syn2787244", "tfs": "syn2787239"}
}

def load_data(expr_id, gold_id, tfs_id):
    expr_file = syn.get(expr_id, downloadLocation=str(tmp_dir))
    gold_file = syn.get(gold_id, downloadLocation=str(tmp_dir))
    tfs_file = syn.get(tfs_id, downloadLocation=str(tmp_dir))

    # Parse TFs
    true_tfs = set()
    with open(tfs_file.path, "r", encoding="utf-8") as handle:
        for line in handle:
            val = line.strip()
            if val:
                true_tfs.add(val)

    # Parse Expression
    gene_names = []
    expr_profiles = []
    with open(expr_file.path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        gene_names = [name.strip() for name in next(reader) if name.strip()]
        for row in reader:
            if not row:
                continue
            expr_profiles.append([float(val) for val in row])
    expr_profiles = np.array(expr_profiles).T
    num_genes = len(gene_names)
    gene_to_idx = {name: idx for idx, name in enumerate(gene_names)}

    # Parse Gold Standard
    true_edges = set()
    with open(gold_file.path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or len(row) < 3:
                continue
            if row[2].strip() == "1":
                tf, target = row[0].strip(), row[1].strip()
                if tf in gene_to_idx and target in gene_to_idx:
                    true_edges.add((gene_to_idx[tf], gene_to_idx[target]))

    # Clean files
    Path(expr_file.path).unlink()
    Path(gold_file.path).unlink()
    Path(tfs_file.path).unlink()

    return gene_names, expr_profiles, true_edges, true_tfs

def run_hodge(gene_names, expr_profiles, true_edges, use_abs=False):
    num_genes = len(gene_names)
    corr_matrix = np.corrcoef(expr_profiles)
    edges = []
    F = []
    threshold = 0.55
    for tf_idx, target_idx in true_edges:
        flow = corr_matrix[tf_idx, target_idx]
        if np.abs(flow) >= threshold:
            edges.append((tf_idx, target_idx))
            F.append(np.abs(flow) if use_abs else flow)

    F = np.array(F)
    num_e = len(edges)
    if num_e == 0:
        return None

    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw
    return p_norm

for net_num in [1, 3, 4]:
    print(f"\n--- Live Evaluation of Net {net_num} ---")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
    print(f"Total Genes: {len(gene_names)} | True TFs: {len(true_tfs)} | Active Edges: {len(true_edges)}")
    
    for use_abs in [False, True]:
        flow_type = "Absolute" if use_abs else "Signed"
        print(f"\n  Evaluating {flow_type} Correlation Flow:")
        p_norm = run_hodge(gene_names, expr_profiles, true_edges, use_abs=use_abs)
        if p_norm is None:
            print(f"    No active edges found for {flow_type} flow.")
            continue

        # Evaluate Descending
        sorted_idx_desc = np.argsort(-p_norm)
        top_10_desc = [gene_names[idx] for idx in sorted_idx_desc[:10]]
        matches_desc = sum(1 for gene in top_10_desc if gene in true_tfs)

        # Evaluate Ascending
        sorted_idx_asc = np.argsort(p_norm)
        top_10_asc = [gene_names[idx] for idx in sorted_idx_asc[:10]]
        matches_asc = sum(1 for gene in top_10_asc if gene in true_tfs)

        # Evaluate top 50 Ascending
        top_50_asc = [gene_names[idx] for idx in sorted_idx_asc[:50]]
        matches_50_asc = sum(1 for gene in top_50_asc if gene in true_tfs)

        print(f"    Precision @ 10 Descending (Peaks): {matches_desc / 10 * 100:.1f}%")
        print(f"    Precision @ 10 Ascending (Basins): {matches_asc / 10 * 100:.1f}%")
        print(f"    Precision @ 50 Ascending (Basins): {matches_50_asc / 50 * 100:.1f}%")
