"""
Verify if the predicted Hodge master regulators (peaks) are true transcription factors in the TRRUST database,
and compare their precision against random baselines and potential sinks.
"""

import csv
import json
import urllib.request
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr

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

def parse_trrust(path: Path) -> tuple[list[str], list[tuple[int, int]], set[str]]:
    node_to_idx = {}
    nodes = []
    true_tfs = set()

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
            true_tfs.add(tf)

    return nodes, list(edges), true_tfs

def verify_trrust_tfs(name: str, url: str):
    raw_path = TMP_DIR / f"trrust_{name}.tsv"
    download_trrust(url, raw_path)
    nodes, edges_list, true_tfs = parse_trrust(raw_path)

    num_genes = len(nodes)
    num_e = len(edges_list)
    print(f"\n=======================================================")
    print(f"VERIFYING REGULATORS (TFs): TRRUST {name.upper()}")
    print(f"=======================================================")
    print(f"Nodes (Genes): {num_genes}")
    print(f"Edges: {num_e}")
    print(f"True Transcription Factors: {len(true_tfs)}")
    
    random_baseline = len(true_tfs) / num_genes
    print(f"Random Baseline (TF Ratio): {random_baseline*100:.2f}%")

    # Run Hodge Decomposition with uniform flow F = 1.0 along directed edges
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    F = np.ones(num_e)
    p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]

    # Normalize potential field
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Sort nodes by potential (Descending: Peaks, Ascending: Sinks)
    sorted_indices = np.argsort(-p_norm)

    # Evaluate Precision at K
    for K in [10, 20, 50, 100, 200]:
        top_peaks = [nodes[idx] for idx in sorted_indices[:K]]
        top_sinks = [nodes[idx] for idx in sorted_indices[-K:]]

        prec_peaks = sum(1 for gene in top_peaks if gene in true_tfs) / K
        prec_sinks = sum(1 for gene in top_sinks if gene in true_tfs) / K

        print(f"K = {K:3d}:")
        print(f"  Precision @ {K} (Hodge Potential PEAKS): {prec_peaks*100:6.2f}% (ratio to baseline: {prec_peaks/max(1e-6, random_baseline):.2f}x)")
        print(f"  Precision @ {K} (Hodge Potential SINKS): {prec_sinks*100:6.2f}% (ratio to baseline: {prec_sinks/max(1e-6, random_baseline):.2f}x)")

    if raw_path.exists():
        raw_path.unlink()

def main():
    verify_trrust_tfs("human", HUMAN_URL)
    verify_trrust_tfs("mouse", MOUSE_URL)

if __name__ == "__main__":
    main()
