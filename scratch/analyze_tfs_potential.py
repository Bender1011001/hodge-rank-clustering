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
    print(f"ANALYZING POTENTIALS: NETWORK {net_num}")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
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
        print("No active edges.")
        continue

    # Boundary Matrix B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    # Min-norm solution via LSQR
    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    
    # Analyze active genes (degree > 0)
    G = nx.DiGraph()
    G.add_nodes_from(range(num_genes))
    G.add_edges_from(edges)
    
    active_nodes = [n for n, d in G.degree() if d > 0]
    active_tfs = [gene_names[n] for n in active_nodes if gene_names[n] in true_tfs]
    active_targets = [gene_names[n] for n in active_nodes if gene_names[n] not in true_tfs]
    
    print(f"Total genes: {num_genes}")
    print(f"Active nodes (degree > 0): {len(active_nodes)}")
    print(f"  Active TFs (TFs with active edges): {len(active_tfs)}")
    print(f"  Active targets (non-TFs with active edges): {len(active_targets)}")
    
    # Component analysis
    G_undirected = nx.Graph(G)
    components = list(nx.connected_components(G_undirected))
    components_with_edges = [c for c in components if len(c) > 1]
    print(f"Connected components (size > 1): {len(components_with_edges)}")
    
    # Distribution of potentials
    active_tfs_idx = [gene_names.index(name) for name in active_tfs]
    active_targets_idx = [gene_names.index(name) for name in active_targets]
    isolated_idx = [idx for idx in range(num_genes) if G.degree(idx) == 0]
    
    p_tfs = p_raw[active_tfs_idx] if active_tfs_idx else []
    p_targets = p_raw[active_targets_idx] if active_targets_idx else []
    p_isolated = p_raw[isolated_idx] if isolated_idx else []
    
    if len(p_tfs) > 0:
        print(f"Active TFs potential: mean={np.mean(p_tfs):.4f}, std={np.std(p_tfs):.4f}, min={np.min(p_tfs):.4f}, max={np.max(p_tfs):.4f}")
    if len(p_targets) > 0:
        print(f"Active targets potential: mean={np.mean(p_targets):.4f}, std={np.std(p_targets):.4f}, min={np.min(p_targets):.4f}, max={np.max(p_targets):.4f}")
    if len(p_isolated) > 0:
        print(f"Isolated nodes potential: mean={np.mean(p_isolated):.4f}, std={np.std(p_isolated):.4f}")
        
    # Check the sorted rank of active TFs in the list of ALL genes, and the list of ACTIVE genes
    sorted_all_idx = np.argsort(p_raw)  # Ascending potential (lowest first)
    all_ranks = {idx: rank for rank, idx in enumerate(sorted_all_idx)}
    
    tf_ranks_in_all = [all_ranks[idx] for idx in active_tfs_idx]
    print(f"Average rank of active TFs in all genes (ascending): {np.mean(tf_ranks_in_all):.1f} / {num_genes}")
    print(f"Top 10 lowest potential nodes - how many are TFs: {sum(1 for idx in sorted_all_idx[:10] if gene_names[idx] in true_tfs)}/10")
    print(f"Top 50 lowest potential nodes - how many are TFs: {sum(1 for idx in sorted_all_idx[:50] if gene_names[idx] in true_tfs)}/50")
    
    # Now let's restrict ONLY to active nodes
    p_active = p_raw[active_nodes]
    sorted_active_sub_idx = np.argsort(p_active)
    sorted_active_idx = [active_nodes[i] for i in sorted_active_sub_idx]
    active_ranks = {idx: rank for rank, idx in enumerate(sorted_active_idx)}
    tf_ranks_in_active = [active_ranks[idx] for idx in active_tfs_idx]
    
    print(f"Average rank of active TFs in active genes (ascending): {np.mean(tf_ranks_in_active):.1f} / {len(active_nodes)}")
    print(f"Top 10 active lowest potential nodes - how many are TFs: {sum(1 for idx in sorted_active_idx[:10] if gene_names[idx] in true_tfs)}/10")
    print(f"Top 50 active lowest potential nodes - how many are TFs: {sum(1 for idx in sorted_active_idx[:50] if gene_names[idx] in true_tfs)}/50")
    
    # Out-degree vs Potential correlation
    active_out_deg = [G.out_degree(idx) for idx in active_nodes]
    active_potentials = p_raw[active_nodes]
    corr_deg_pot = np.corrcoef(active_out_deg, active_potentials)[0, 1]
    print(f"Correlation between out-degree and potential in active nodes: {corr_deg_pot:.4f}")
