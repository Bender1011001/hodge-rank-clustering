import sys
import csv
import json
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
import synapseclient
from pathlib import Path
import networkx as nx
import random

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

def evaluate_metric(scores, gene_names, true_tfs, ascending=False):
    if ascending:
        sorted_nodes = sorted(scores.keys(), key=lambda k: scores[k])
    else:
        sorted_nodes = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        
    top_10 = [gene_names[idx] for idx in sorted_nodes[:10]]
    top_50 = [gene_names[idx] for idx in sorted_nodes[:50]]
    
    p_10 = sum(1 for gene in top_10 if gene in true_tfs) / 10
    p_50 = sum(1 for gene in top_50 if gene in true_tfs) / 50
    return p_10, p_50

for net_num in [1, 3, 4]:
    print(f"\n=======================================================")
    print(f"UNBIASED RECONSTRUCTION: NETWORK {net_num} ({NETS[net_num]['name'].upper()})")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
    num_genes = len(gene_names)
    base_rate = len(true_tfs) / num_genes
    print(f"Base Rate (Random baseline): {base_rate*100:.2f}% ({len(true_tfs)} / {num_genes})")
    
    # Calculate expression stats
    vars_val = np.var(expr_profiles, axis=1)
    means_val = np.mean(expr_profiles, axis=1)
    
    # Compute correlation matrix
    corr_matrix = np.corrcoef(expr_profiles)
    abs_corr = np.abs(corr_matrix)
    np.fill_diagonal(abs_corr, 0.0) # Remove self loops
    
    # Select the top K highest correlated pairs (undirected)
    # We take the upper triangle to avoid duplicates
    triu_indices = np.triu_indices(num_genes, k=1)
    flat_indices = np.argsort(abs_corr[triu_indices])[::-1] # Sorted descending
    
    # Reconstruct top K edges
    K = 1000  # Number of active edges in unbiased graph
    top_k_indices = flat_indices[:K]
    
    undirected_edges = []
    for idx in top_k_indices:
        u = triu_indices[0][idx]
        v = triu_indices[1][idx]
        undirected_edges.append((u, v, abs_corr[u, v]))
        
    print(f"Reconstructed {len(undirected_edges)} highest-correlation candidate edges.")
    
    # Directionality heuristics
    heuristics = {
        "Variance (High->Low)": lambda u, v: (u, v) if vars_val[u] > vars_val[v] else (v, u),
        "Variance (Low->High)": lambda u, v: (u, v) if vars_val[u] < vars_val[v] else (v, u),
        "Mean (High->Low)": lambda u, v: (u, v) if means_val[u] > means_val[v] else (v, u),
        "Mean (Low->High)": lambda u, v: (u, v) if means_val[u] < means_val[v] else (v, u),
        "Arbitrary Index": lambda u, v: (u, v) if u < v else (v, u),
        "Random": lambda u, v: (u, v) if random.random() > 0.5 else (v, u)
    }
    
    for heur_name, orient_func in heuristics.items():
        print(f"\nEvaluating Heuristic: {heur_name}")
        edges = []
        F_abs = []
        for u, v, w in undirected_edges:
            src, tgt = orient_func(u, v)
            edges.append((src, tgt))
            F_abs.append(w)
            
        F_abs = np.array(F_abs)
        
        # Build DiGraph for NetworkX baselines
        G = nx.DiGraph()
        G.add_nodes_from(range(num_genes))
        G.add_edges_from(edges)
        
        # Centralities
        out_deg = dict(G.out_degree())
        in_deg = dict(G.in_degree())
        try:
            pagerank = nx.pagerank(G, alpha=0.85)
        except Exception:
            pagerank = {i: 0.0 for i in range(num_genes)}
            
        try:
            hits_h, _ = nx.hits(G, max_iter=500)
        except Exception:
            hits_h = {i: 0.0 for i in range(num_genes)}
            
        # Hodge Potential (with constant flow 1.0)
        r1, c1, d1 = [], [], []
        for idx, (u, v) in enumerate(edges):
            r1.extend([u, v])
            c1.extend([idx, idx])
            d1.extend([-1.0, 1.0])
        B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, K))
        
        p_const = lsqr(B1.T, np.ones(K), atol=1e-5, btol=1e-5)[0]
        hodge_const_scores = {idx: p_const[idx] for idx in range(num_genes)}
        
        # Hodge Potential (with absolute correlation flow)
        p_abs = lsqr(B1.T, F_abs, atol=1e-5, btol=1e-5)[0]
        hodge_abs_scores = {idx: p_abs[idx] for idx in range(num_genes)}
        
        # Evaluate
        p10_out, p50_out = evaluate_metric(out_deg, gene_names, true_tfs, ascending=False)
        p10_in, p50_in = evaluate_metric(in_deg, gene_names, true_tfs, ascending=False)
        p10_pr, p50_pr = evaluate_metric(pagerank, gene_names, true_tfs, ascending=False)
        p10_hub, p50_hub = evaluate_metric(hits_h, gene_names, true_tfs, ascending=False)
        
        # Hodge Basins (Ascending potential)
        p10_hodge_c_asc, p50_hodge_c_asc = evaluate_metric(hodge_const_scores, gene_names, true_tfs, ascending=True)
        p10_hodge_a_asc, p50_hodge_a_asc = evaluate_metric(hodge_abs_scores, gene_names, true_tfs, ascending=True)
        
        # Hodge Peaks (Descending potential)
        p10_hodge_c_desc, p50_hodge_c_desc = evaluate_metric(hodge_const_scores, gene_names, true_tfs, ascending=False)
        p10_hodge_a_desc, p50_hodge_a_desc = evaluate_metric(hodge_abs_scores, gene_names, true_tfs, ascending=False)
        
        print(f"  Method              | Prec@10  | Prec@50")
        print(f"  --------------------|----------|---------")
        print(f"  Out-Degree          | {p10_out*100:6.1f}% | {p50_out*100:7.1f}%")
        print(f"  In-Degree           | {p10_in*100:6.1f}% | {p50_in*100:7.1f}%")
        print(f"  PageRank            | {p10_pr*100:6.1f}% | {p50_pr*100:7.1f}%")
        print(f"  HITS Hub            | {p10_hub*100:6.1f}% | {p50_hub*100:7.1f}%")
        print(f"  Hodge Basin (Const) | {p10_hodge_c_asc*100:6.1f}% | {p50_hodge_c_asc*100:7.1f}%")
        print(f"  Hodge Basin (Abs)   | {p10_hodge_a_asc*100:6.1f}% | {p50_hodge_a_asc*100:7.1f}%")
        print(f"  Hodge Peak (Const)  | {p10_hodge_c_desc*100:6.1f}% | {p50_hodge_c_desc*100:7.1f}%")
        print(f"  Hodge Peak (Abs)    | {p10_hodge_a_desc*100:6.1f}% | {p50_hodge_a_desc*100:7.1f}%")
