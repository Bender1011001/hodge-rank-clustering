"""
Evaluate Hodge Curl and isolated feedback loops (cyclic triangles) vs 
feed-forward loops (transitive triangles) on TRRUST gene regulatory networks.
"""

import csv
import urllib.request
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
import networkx as nx

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

def evaluate_loops(name: str, url: str):
    raw_path = TMP_DIR / f"trrust_{name}.tsv"
    download_trrust(url, raw_path)
    nodes, edges_list = parse_trrust(raw_path)

    num_genes = len(nodes)
    num_e = len(edges_list)
    edge_to_idx = {edges_list[idx]: idx for idx in range(num_e)}

    print(f"\n=======================================================")
    print(f"EVALUATING CURL/FEEDBACK LOOPS: TRRUST {name.upper()}")
    print(f"=======================================================")
    print(f"Nodes (Genes): {num_genes}")
    print(f"Edges: {num_e}")

    G = nx.DiGraph()
    G.add_nodes_from(range(num_genes))
    G.add_edges_from(edges_list)

    # Find all triangles in the undirected sense
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
    print(f"Total undirected triangles: {num_t}")

    if num_t == 0:
        print("No triangles found.")
        if raw_path.exists():
            raw_path.unlink()
        return

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

    # Solve Hodge Decomposition with uniform flow F = 1.0 along directed edges
    F = np.ones(num_e)
    p = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
    F_grad = B1.T.dot(p)
    F_res = F - F_grad

    c = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]

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

    if raw_path.exists():
        raw_path.unlink()

def main():
    evaluate_loops("human", HUMAN_URL)
    evaluate_loops("mouse", MOUSE_URL)

if __name__ == "__main__":
    main()
