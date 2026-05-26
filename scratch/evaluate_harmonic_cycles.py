import sys
import csv
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
import synapseclient
from pathlib import Path
import networkx as nx
from sklearn.metrics import roc_auc_score, average_precision_score

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

for net_num in [1, 3, 4]:
    print(f"\n=======================================================")
    print(f"EVALUATING HARMONIC FLOW VS CYCLE EDGES: NETWORK {net_num}")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
    num_genes = len(gene_names)
    
    # Construct NetworkX DiGraph
    G = nx.DiGraph()
    G.add_nodes_from(range(num_genes))
    G.add_edges_from(true_edges)
    
    edges_list = list(true_edges)
    num_e = len(edges_list)
    edge_to_idx = {edges_list[idx]: idx for idx in range(num_e)}
    
    # 1. Identify edges that participate in ANY directed cycles (feedback loops)
    print("Finding strongly connected components...")
    sccs = list(nx.strongly_connected_components(G))
    cycle_edges = set()
    for scc in sccs:
        if len(scc) >= 2:
            sub = G.subgraph(scc)
            for u, v in sub.edges():
                if nx.has_path(sub, v, u):
                    cycle_edges.add((u, v))
            
    print(f"Total directed edges: {num_e}")
    print(f"Edges in feedback cycles: {len(cycle_edges)}")
    
    # Create target array for classification (1 if in cycle, 0 if not)
    y_true = np.zeros(num_e)
    for idx, (u, v) in enumerate(edges_list):
        if (u, v) in cycle_edges:
            y_true[idx] = 1.0
            
    # 2. Setup Boundary Matrix B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))
    
    # 3. Find all triangles
    adj = {i: set() for i in range(num_genes)}
    for (u, v) in edges_list:
        adj[u].add(v)
        adj[v].add(u)
        
    triangles_nodes = []
    for u in range(num_genes):
        neighbors = sorted([v for v in adj[u] if v > u])
        for i in range(len(neighbors)):
            v = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w = neighbors[j]
                if w in adj[v]:
                    triangles_nodes.append((u, v, w))
                    
    num_t = len(triangles_nodes)
    print(f"Total triangles (2-simplices): {num_t}")
    
    # 4. Setup Boundary Matrix B2 (if triangles exist)
    if num_t > 0:
        r2, c2, d2 = [], [], []
        for t_idx, (u, v, w) in enumerate(triangles_nodes):
            # Edge 1
            if (u, v) in edge_to_idx:
                r2.append(edge_to_idx[(u, v)])
                d2.append(1.0)
            elif (v, u) in edge_to_idx:
                r2.append(edge_to_idx[(v, u)])
                d2.append(-1.0)
            c2.append(t_idx)
            # Edge 2
            if (v, w) in edge_to_idx:
                r2.append(edge_to_idx[(v, w)])
                d2.append(1.0)
            elif (w, v) in edge_to_idx:
                r2.append(edge_to_idx[(w, v)])
                d2.append(-1.0)
            c2.append(t_idx)
            # Edge 3
            if (u, w) in edge_to_idx:
                r2.append(edge_to_idx[(u, w)])
                d2.append(-1.0)
            elif (w, u) in edge_to_idx:
                r2.append(edge_to_idx[(w, u)])
                d2.append(1.0)
            c2.append(t_idx)
        B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, num_t))
    else:
        B2 = None
        
    # 5. Solve Hodge Decomposition
    # Constant flow along directed edges (1.0)
    F = np.ones(num_e)
    
    p = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p)
    F_res = F - F_grad
    
    if B2 is not None:
        c = lsqr(B2, F_res, atol=1e-5, btol=1e-5)[0]
        F_curl = B2.dot(c)
    else:
        F_curl = np.zeros(num_e)
        
    F_harm = F_res - F_curl
    
    # 6. Evaluate Harmonic flow magnitudes as predictors of feedback cycle edges
    harm_mags = np.abs(F_harm)
    
    # Calculate classification metrics if cycle edges exist
    if np.sum(y_true) > 0:
        auc = roc_auc_score(y_true, harm_mags)
        ap = average_precision_score(y_true, harm_mags)
        
        # Print means
        mean_cycle_harm = np.mean(harm_mags[y_true == 1.0])
        mean_non_cycle_harm = np.mean(harm_mags[y_true == 0.0])
        
        print(f"Mean |F_harm| for Cycle Edges:     {mean_cycle_harm:.4f}")
        print(f"Mean |F_harm| for Non-Cycle Edges: {mean_non_cycle_harm:.4f}")
        print(f"Classification performance of |F_harm| for feedback cycle edges:")
        print(f"  ROC AUC Score:     {auc:.4f}")
        print(f"  Average Precision: {ap:.4f} (baseline: {np.mean(y_true):.4f})")
    else:
        print("No feedback cycle edges exist in this network.")
