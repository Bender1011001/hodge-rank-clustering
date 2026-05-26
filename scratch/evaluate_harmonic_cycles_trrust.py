"""
Evaluate Hodge Harmonic flow magnitude as a predictor of directed feedback cycle edges
on TRRUST human/mouse transcriptional regulatory networks.
"""

import csv
import urllib.request
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
import networkx as nx
from sklearn.metrics import roc_auc_score, average_precision_score

ROOT = Path(__file__).resolve().parents[1]
HUMAN_URL = "https://www.grnpedia.org/trrust/data/trrust_rawdata.human.tsv"
MOUSE_URL = "https://www.grnpedia.org/trrust/data/trrust_rawdata.mouse.tsv"
TMP_DIR = ROOT / ".tmp"

def download_trrust(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading from {url} to {dest}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        dest.write_bytes(response.read())

def parse_trrust(path: Path) -> tuple[list[str], list[tuple[int, int]]]:
    node_to_idx = {}
    nodes = []

    def get_node(name: str) -> int:
        if name not in node_to_idx:
            node_to_idx[name] = len(nodes)
            nodes.append(name)
        return node_to_idx[name]

    edges = set()
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or len(row) < 2:
                continue
            tf, target = row[0].strip(), row[1].strip()
            if tf == target:
                continue
            u = get_node(tf)
            v = get_node(target)
            edges.add((u, v))

    return nodes, list(edges)

def evaluate_harmonic(name: str, url: str):
    raw_path = TMP_DIR / f"trrust_{name}.tsv"
    download_trrust(url, raw_path)
    nodes, edges_list = parse_trrust(raw_path)

    num_genes = len(nodes)
    num_e = len(edges_list)
    edge_to_idx = {edges_list[idx]: idx for idx in range(num_e)}

    print(f"\n=======================================================")
    print(f"EVALUATING HARMONIC FLOW VS CYCLE EDGES: TRRUST {name.upper()}")
    print(f"=======================================================")
    print(f"Nodes (Genes): {num_genes}")
    print(f"Edges: {num_e}")

    G = nx.DiGraph()
    G.add_nodes_from(range(num_genes))
    G.add_edges_from(edges_list)

    # Find cycle edges.
    # An edge (u, v) is in a cycle if and only if v can reach u.
    # To make this fast, we only check within strongly connected components (SCCs) of size >= 2.
    print("Finding strongly connected components...")
    sccs = list(nx.strongly_connected_components(G))
    
    cycle_edges = set()
    for scc in sccs:
        if len(scc) >= 2:
            sub = G.subgraph(scc)
            for u, v in sub.edges():
                if nx.has_path(sub, v, u):
                    cycle_edges.add((u, v))

    print(f"Edges in feedback cycles: {len(cycle_edges)}")

    # Create target array for classification
    y_true = np.zeros(num_e)
    for idx, (u, v) in enumerate(edges_list):
        if (u, v) in cycle_edges:
            y_true[idx] = 1.0

    # Build Boundary Matrix B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    # Find triangles
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
    print(f"Total triangles: {num_t}")

    # Build B2
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

    # Solve Hodge Decomposition
    F = np.ones(num_e)
    p = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
    F_grad = B1.T.dot(p)
    F_res = F - F_grad

    if B2 is not None:
        c = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]
        F_curl = B2.dot(c)
    else:
        F_curl = np.zeros(num_e)

    F_harm = F_res - F_curl
    harm_mags = np.abs(F_harm)

    if np.sum(y_true) > 0 and np.sum(y_true) < num_e:
        auc = roc_auc_score(y_true, harm_mags)
        ap = average_precision_score(y_true, harm_mags)
        
        mean_cycle_harm = np.mean(harm_mags[y_true == 1.0])
        mean_non_cycle_harm = np.mean(harm_mags[y_true == 0.0])
        
        print(f"Mean |F_harm| for Cycle Edges:     {mean_cycle_harm:.4f}")
        print(f"Mean |F_harm| for Non-Cycle Edges: {mean_non_cycle_harm:.4f}")
        print(f"Classification performance of |F_harm| for cycle edges:")
        print(f"  ROC AUC Score:     {auc:.4f}")
        print(f"  Average Precision: {ap:.4f} (baseline: {np.mean(y_true):.4f})")
    else:
        print("No feedback cycle edges exist or all edges are cycle edges.")

    if raw_path.exists():
        raw_path.unlink()

def main():
    evaluate_harmonic("human", HUMAN_URL)
    evaluate_harmonic("mouse", MOUSE_URL)

if __name__ == "__main__":
    main()
