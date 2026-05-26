import sys
import csv
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr, eigs
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

for net_num in [1, 3, 4]:
    print(f"\n=======================================================")
    print(f"DIAGNOSING TOPOLOGY: NETWORK {net_num}")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
    # Run network assembly
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

    # Graph Laplacian L = B1 * B1.T
    L = B1.dot(B1.T).toarray()
    
    # Calculate Spectral Gap (second smallest eigenvalue of the Laplacian)
    # Since G is likely disconnected (contains many isolated genes), the number of connected
    # components determines the number of 0 eigenvalues. Let's find the components.
    G_undirected = nx.Graph()
    G_undirected.add_nodes_from(range(num_genes))
    G_undirected.add_edges_from(edges)
    # Remove isolated nodes (out-degree = 0 and in-degree = 0)
    non_isolated = [node for node, deg in G_undirected.degree() if deg > 0]
    G_sub = G_undirected.subgraph(non_isolated).copy()
    components = list(nx.connected_components(G_sub))
    num_components = len(components)
    
    # Get spectral gap of the largest connected component
    if num_components > 0:
        largest_cc = max(components, key=len)
        L_sub = nx.laplacian_matrix(G_sub.subgraph(largest_cc)).toarray().astype(float)
        eigenvals = np.linalg.eigvalsh(L_sub)
        # Sort eigenvalues ascending
        eigenvals = np.sort(eigenvals)
        spectral_gap = eigenvals[1] if len(eigenvals) > 1 else 0.0
        max_eigenval = eigenvals[-1] if len(eigenvals) > 0 else 0.0
    else:
        spectral_gap = 0.0
        max_eigenval = 0.0
        largest_cc = []

    # Triangles Count (B2 rank)
    adj = {i: set() for i in range(num_genes)}
    for (u, v) in edges:
        adj[u].add(v)
        adj[v].add(u)

    triangles = 0
    for u in range(num_genes):
        neighbors = sorted([v for v in adj[u] if v > u])
        for i in range(len(neighbors)):
            v = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w = neighbors[j]
                if w in adj[v]:
                    triangles += 1

    # Solve flow norms
    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad
    
    grad_norm = np.linalg.norm(F_grad)
    res_norm = np.linalg.norm(F_res)
    total_norm = np.linalg.norm(F)

    # Print Topological Invariants
    print(f"Total Genes: {num_genes} | Active Edges: {num_e}")
    print(f"Disconnected Components (active): {num_components}")
    print(f"Largest Component Size: {len(largest_cc)} nodes")
    if len(largest_cc) > 0:
        print(f"  Largest CC Spectral Gap: {spectral_gap:.5f}")
        print(f"  Largest CC Max Eigenvalue: {max_eigenval:.5f}")
        print(f"  Condition Number Estimate (Max/Gap): {max_eigenval/max(1e-6, spectral_gap):.1f}")
    print(f"Triangles (B2 count): {triangles}")
    print(f"Gradient Flow Norm Ratio: {grad_norm/max(1e-6, total_norm)*100:.2f}%")
    print(f"Residual Flow Norm Ratio: {res_norm/max(1e-6, total_norm)*100:.2f}%")
