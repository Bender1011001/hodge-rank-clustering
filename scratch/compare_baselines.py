import sys
import csv
import json
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
import synapseclient
from pathlib import Path
import networkx as nx

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
    num_genes = len(gene_names)
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

def run_hodge(gene_names, expr_profiles, true_edges):
    num_genes = len(gene_names)
    corr_matrix = np.corrcoef(expr_profiles)
    edges = []
    F = []
    threshold = 0.55
    for tf_idx, target_idx in true_edges:
        flow = corr_matrix[tf_idx, target_idx]
        if np.abs(flow) >= threshold:
            edges.append((tf_idx, target_idx))
            F.append(flow)

    F = np.array(F)
    num_e = len(edges)
    if num_e == 0:
        return None, None

    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw
    return p_norm, edges

for net_num in [1, 3, 4]:
    print(f"\n=======================================================")
    print(f"EVALUATING NETWORK {net_num} ({NETS[net_num]['name'].upper()})")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    p_norm, active_edges = run_hodge(gene_names, expr_profiles, true_edges)
    
    if p_norm is None:
        print("No active edges found.")
        continue

    # Build NetworkX directed graph of active edges for centrality baselines
    G = nx.DiGraph()
    G.add_nodes_from(range(len(gene_names)))
    G.add_edges_from(active_edges)

    # 1. Out-degree centrality
    out_deg = dict(G.out_degree())
    # 2. In-degree centrality
    in_deg = dict(G.in_degree())
    # 3. PageRank
    try:
        pagerank = nx.pagerank(G, alpha=0.85)
    except Exception as e:
        print(f"PageRank failed: {e}")
        pagerank = {i: 0.0 for i in range(len(gene_names))}
    # 4. HITS
    try:
        hits_h, hits_a = nx.hits(G, max_iter=500)
    except Exception as e:
        print(f"HITS failed: {e}")
        hits_h, hits_a = {i: 0.0 for i in range(len(gene_names))}, {i: 0.0 for i in range(len(gene_names))}

    # Metric evaluation helper
    def evaluate_metric(scores, ascending=False):
        # Sort node indices based on scores
        if ascending:
            sorted_nodes = sorted(scores.keys(), key=lambda k: scores[k])
        else:
            sorted_nodes = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
            
        top_10 = [gene_names[idx] for idx in sorted_nodes[:10]]
        top_50 = [gene_names[idx] for idx in sorted_nodes[:50]]
        
        p_10 = sum(1 for gene in top_10 if gene in true_tfs) / 10
        p_50 = sum(1 for gene in top_50 if gene in true_tfs) / 50
        return p_10, p_50

    # Hodge Potential (Ascending / Basins)
    hodge_scores = {idx: p_norm[idx] for idx in range(len(gene_names))}
    p10_hodge, p50_hodge = evaluate_metric(hodge_scores, ascending=True)

    # Out-degree
    p10_out, p50_out = evaluate_metric(out_deg, ascending=False)
    # PageRank
    p10_pr, p50_pr = evaluate_metric(pagerank, ascending=False)
    # HITS Hubs
    p10_hub, p50_hub = evaluate_metric(hits_h, ascending=False)

    base_rate = len(true_tfs) / len(gene_names)
    print(f"Base Rate (Random baseline): {base_rate*100:.2f}% ({len(true_tfs)} / {len(gene_names)})")
    print(f"Active Edges (Threshold >= 0.55): {len(active_edges)}")
    
    print("\nPrecision @ 10 comparison:")
    print(f"  Hodge Potential (Basins): {p10_hodge*100:.1f}%")
    print(f"  Out-Degree Centrality:   {p10_out*100:.1f}%")
    print(f"  PageRank:                {p10_pr*100:.1f}%")
    print(f"  HITS Hub Score:          {p10_hub*100:.1f}%")

    print("\nPrecision @ 50 comparison:")
    print(f"  Hodge Potential (Basins): {p50_hodge*100:.1f}%")
    print(f"  Out-Degree Centrality:   {p50_out*100:.1f}%")
    print(f"  PageRank:                {p50_pr*100:.1f}%")
    print(f"  HITS Hub Score:          {p50_hub*100:.1f}%")

    # Diagnose Network 1 Failure
    if net_num == 1:
        print("\n--- Diagnosing Network 1 Topology ---")
        # Check out-degree stats of active edges
        active_tfs_in_graph = sum(1 for idx, deg in out_deg.items() if deg > 0)
        print(f"Number of nodes with out-degree > 0 in Network 1: {active_tfs_in_graph}")
        # Let's check how many active edges actually exist
        # If there are few active edges or degree distribution is uniform
        degrees = [deg for idx, deg in out_deg.items() if deg > 0]
        if degrees:
            print(f"Max out-degree: {max(degrees)} | Min active out-degree: {min(degrees)} | Avg: {np.mean(degrees):.2f}")
        else:
            print("No nodes with out-degree > 0.")
