import sys
import csv
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
    print(f"EVALUATING CURL/FEEDBACK LOOPS: NETWORK {net_num}")
    print(f"=======================================================")
    info = NETS[net_num]
    gene_names, expr_profiles, true_edges, true_tfs = load_data(info["expr"], info["gold"], info["tfs"])
    
    num_genes = len(gene_names)
    
    # We build the gold standard graph directly to inspect its topological structure
    # and see if Hodge Curl can isolate loops in the ground truth
    G = nx.DiGraph()
    G.add_nodes_from(range(num_genes))
    G.add_edges_from(true_edges)
    
    edges_list = list(true_edges)
    num_e = len(edges_list)
    edge_to_idx = {edges_list[idx]: idx for idx in range(num_e)}
    
    # Find all triangles in the undirected graph
    G_undirected = nx.Graph(G)
    triangles_nodes = []
    
    adj = {i: set() for i in range(num_genes)}
    for (u, v) in edges_list:
        adj[u].add(v)
        adj[v].add(u)
        
    for u in range(num_genes):
        neighbors = sorted([v for v in adj[u] if v > u])
        for i in range(len(neighbors)):
            v = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w = neighbors[j]
                if w in adj[v]:
                    triangles_nodes.append((u, v, w))
                    
    num_t = len(triangles_nodes)
    print(f"Total directed edges: {num_e}")
    print(f"Total undirected triangles: {num_t}")
    
    if num_t == 0:
        print("No triangles found.")
        continue
        
    # Classify triangles: Cyclic (feedback loop) vs Transitive (feed-forward loop)
    # Since G is a DiGraph, we look at the arrows.
    # For a triangle (u, v, w), we check the out-degrees inside the subgraph
    cyclic_triangles = []
    transitive_triangles = []
    
    for u, v, w in triangles_nodes:
        sub = G.subgraph([u, v, w])
        # A directed 3-node graph is cyclic if every node has in-degree 1 and out-degree 1
        degrees = [sub.in_degree(n) for n in [u, v, w]]
        if all(d == 1 for d in degrees):
            cyclic_triangles.append((u, v, w))
        else:
            transitive_triangles.append((u, v, w))
            
    print(f"  Cyclic Triangles (Feedback Loops):   {len(cyclic_triangles)}")
    print(f"  Transitive Triangles (Feed-forward): {len(transitive_triangles)}")
    
    # Assemble Boundary Matrix B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))
    
    # Assemble Boundary Matrix B2 (Triangles -> Edges)
    # We traverse canonically: u < v < w
    # boundary: [v,w] - [u,w] + [u,v]
    r2, c2, d2 = [], [], []
    for t_idx, (u, v, w) in enumerate(triangles_nodes):
        # We need to find the actual edges in G.
        # Note: the edge in G could be directed in either direction.
        # We define the sign of the edge in the triangle boundary relative to the graph edge direction.
        # Canonical traversal path: u -> v -> w -> u
        
        # Edge 1: between u and v
        if (u, v) in edge_to_idx:
            r2.append(edge_to_idx[(u, v)])
            d2.append(1.0)
        elif (v, u) in edge_to_idx:
            r2.append(edge_to_idx[(v, u)])
            d2.append(-1.0)
        c2.append(t_idx)
        
        # Edge 2: between v and w
        if (v, w) in edge_to_idx:
            r2.append(edge_to_idx[(v, w)])
            d2.append(1.0)
        elif (w, v) in edge_to_idx:
            r2.append(edge_to_idx[(w, v)])
            d2.append(-1.0)
        c2.append(t_idx)
        
        # Edge 3: between u and w. Traversing w -> u is opposite to canonical u -> w
        if (u, w) in edge_to_idx:
            r2.append(edge_to_idx[(u, w)])
            d2.append(-1.0)
        elif (w, u) in edge_to_idx:
            r2.append(edge_to_idx[(w, u)])
            d2.append(1.0)
        c2.append(t_idx)
        
    B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, num_t))
    
    # Verify B1 * B2 = 0
    test_zero = B1.dot(B2).toarray()
    max_err = np.max(np.abs(test_zero))
    print(f"Verification: B1 * B2 max error = {max_err:.1e}")
    
    # Run Hodge Decomposition
    # Flow along directed edges is constant 1.0
    F = np.ones(num_e)
    
    p = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p)
    F_res = F - F_grad
    
    # Solve for Curl coefficients: B2 * c = F_res
    c = lsqr(B2, F_res, atol=1e-5, btol=1e-5)[0]
    
    # Analyze curl coefficients for cyclic vs transitive triangles
    c_cyclic = []
    c_transitive = []
    
    for t_idx, (u, v, w) in enumerate(triangles_nodes):
        val = np.abs(c[t_idx])
        sub = G.subgraph([u, v, w])
        degrees = [sub.in_degree(n) for n in [u, v, w]]
        if all(d == 1 for d in degrees):
            c_cyclic.append(val)
        else:
            c_transitive.append(val)
            
    if c_cyclic:
        print(f"Cyclic Triangles Curl:     mean={np.mean(c_cyclic):.4f}, std={np.std(c_cyclic):.4f}, min={np.min(c_cyclic):.4f}, max={np.max(c_cyclic):.4f}")
    else:
        print("Cyclic Triangles Curl:     N/A (none exist)")
    if c_transitive:
        print(f"Transitive Triangles Curl: mean={np.mean(c_transitive):.4f}, std={np.std(c_transitive):.4f}, min={np.min(c_transitive):.4f}, max={np.max(c_transitive):.4f}")
    else:
        print("Transitive Triangles Curl: N/A (none exist)")
