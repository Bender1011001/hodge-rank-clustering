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
syn = login_synapse()

tmp_dir = ROOT / ".tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

NETS = {
    1: {"name": "in-silico", "expr": "syn2787226", "gold": "syn2787240", "tfs": "syn2787227"},
    3: {"name": "ecoli", "expr": "syn2787234", "gold": "syn2787243", "tfs": "syn2787235"},
    4: {"name": "yeast", "expr": "syn2787238", "gold": "syn2787244", "tfs": "syn2787239"}
}

def load_data(expr_id, gold_id, tfs_id):
    expr_file = syn.get(expr_id, downloadLocation=str(tmp_dir))
    gold_file = syn.get(gold_id, downloadLocation=str(tmp_dir))
    tfs_file = syn.get(tfs_id, downloadLocation=str(tmp_dir))

    true_tfs = set()
    with open(tfs_file.path, "r", encoding="utf-8") as handle:
        for line in handle:
            val = line.strip()
            if val:
                true_tfs.add(val)

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
    gene_to_idx = {name: idx for idx, name in enumerate(gene_names)}

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

    Path(expr_file.path).unlink()
    Path(gold_file.path).unlink()
    Path(tfs_file.path).unlink()

    return gene_names, expr_profiles, true_edges, true_tfs

def run_evaluation(flow_type="raw"):
    for net_num in [1, 3, 4]:
        info = NETS[net_num]
        gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
        
        num_genes = len(gene_names)
        corr_matrix = np.corrcoef(expr_profiles)
        edges = []
        F = []
        threshold = 0.55
        
        num_pos = 0
        num_neg = 0
        
        for tf_idx, target_idx in true_edges:
            corr_val = corr_matrix[tf_idx, target_idx]
            if np.abs(corr_val) >= threshold:
                edges.append((tf_idx, target_idx))
                if corr_val >= 0:
                    num_pos += 1
                else:
                    num_neg += 1
                    
                if flow_type == "raw":
                    F.append(corr_val)
                elif flow_type == "abs":
                    F.append(np.abs(corr_val))
                elif flow_type == "const":
                    F.append(1.0)

        F = np.array(F)
        num_e = len(edges)
        if num_e == 0:
            print(f"Net {net_num}: No active edges")
            continue

        r1, c1, d1 = [], [], []
        for idx, (u, v) in enumerate(edges):
            r1.extend([u, v])
            c1.extend([idx, idx])
            d1.extend([-1.0, 1.0])
        B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

        p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
        
        # We evaluate ascending potential (lowest first)
        sorted_nodes = np.argsort(p_raw)
        
        top_10 = [gene_names[idx] for idx in sorted_nodes[:10]]
        top_50 = [gene_names[idx] for idx in sorted_nodes[:50]]
        
        p_10 = sum(1 for gene in top_10 if gene in true_tfs) / 10
        p_50 = sum(1 for gene in top_50 if gene in true_tfs) / 50
        
        print(f"Net {net_num} ({flow_type} flow): Active Edges = {num_e} (Pos: {num_pos}, Neg: {num_neg}) | Prec@10 = {p_10*100:.1f}% | Prec@50 = {p_50*100:.1f}%")

print("--- Running Evaluation with Raw Correlations ---")
run_evaluation("raw")
print("\n--- Running Evaluation with Absolute Correlations ---")
run_evaluation("abs")
print("\n--- Running Evaluation with Constant Flow (1.0) ---")
run_evaluation("const")
