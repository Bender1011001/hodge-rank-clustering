"""
Run Hodge Decomposition on TRRUST Gene Regulatory Networks.
Downloads human and mouse TRRUST transcriptional regulatory networks,
constructs the directed flow network, solves the discrete Hodge decomposition,
and ranks nodes by their regulatory potential.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr

HUMAN_URL = "https://www.grnpedia.org/trrust/data/trrust_rawdata.human.tsv"
MOUSE_URL = "https://www.grnpedia.org/trrust/data/trrust_rawdata.mouse.tsv"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "site" / "data" / "trrust"


def download_trrust(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading from {url} to {dest}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        dest.write_bytes(response.read())


def parse_trrust(path: Path) -> tuple[list[str], list[tuple[int, int, float]]]:
    # Maps gene names to indices
    node_to_idx = {}
    nodes = []

    def get_node(name: str) -> int:
        if name not in node_to_idx:
            node_to_idx[name] = len(nodes)
            nodes.append(name)
        return node_to_idx[name]

    # Collect edge raw flows
    # Maps (u, v) to list of flows
    edge_flows = defaultdict(list)

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or len(row) < 3:
                continue
            tf, target, reg_type = row[0].strip(), row[1].strip(), row[2].strip()
            if tf == target:
                continue  # Ignore self-loops for Hodge boundary matrices

            u = get_node(tf)
            v = get_node(target)

            # Assign numeric flow value: activation is downstream positive flow (+1.0),
            # repression is negative flow (-1.0), unknown is neutral (+0.5)
            if "activation" in reg_type.lower():
                flow = 1.0
            elif "repression" in reg_type.lower():
                flow = -1.0
            else:
                flow = 0.5

            edge_flows[(u, v)].append(flow)

    # Average the flows for duplicate TF-target entries
    edges = []
    for (u, v), flows in edge_flows.items():
        avg_flow = sum(flows) / len(flows)
        edges.append((u, v, avg_flow))

    return nodes, edges


def run_hodge_decomposition(nodes: list[str], edges: list[tuple[int, int, float]]):
    num_v = len(nodes)
    num_e = len(edges)

    # Map edges to indices
    edge_to_idx = {}
    edges_list = []
    F = np.zeros(num_e)

    for idx, (u, v, flow) in enumerate(edges):
        # We sort nodes to ensure undirected edge key consistency for triangles
        u_sorted, v_sorted = min(u, v), max(u, v)
        edge_to_idx[(u_sorted, v_sorted)] = idx
        edges_list.append((u, v))
        F[idx] = flow

    # Build B1 (boundary incidence matrix)
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])  # flows from u to v
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))

    # Build B2 (triangle mapping)
    # Build adjacency list
    adj = {i: set() for i in range(num_v)}
    for (u, v) in edges_list:
        adj[u].add(v)
        adj[v].add(u)

    r2, c2, d2 = [], [], []
    t_idx = 0
    for u in range(num_v):
        neighbors = sorted([v for v in adj[u] if v > u])
        for i in range(len(neighbors)):
            v = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w = neighbors[j]
                if w in adj[v]:
                    # Triangle found (u, v, w) with u < v < w
                    # Map edges in sorted node order
                    e_vw = edge_to_idx[(v, w)]
                    e_uw = edge_to_idx[(u, w)]
                    e_uv = edge_to_idx[(u, v)]

                    r2.extend([e_vw, e_uw, e_uv])
                    c2.extend([t_idx, t_idx, t_idx])
                    d2.extend([1.0, -1.0, 1.0])
                    t_idx += 1

    B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

    # Solve potential field Phi using LSQR
    p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad

    # Solve curl
    if B2 is not None:
        c = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]
        F_curl = B2.dot(c)
    else:
        F_curl = np.zeros(num_e)

    # Solve harmonic component
    F_harm = F_res - F_curl

    return p_raw, F_grad, F_curl, F_harm, t_idx, edges_list, F


def process_dataset(name: str, url: str) -> dict:
    raw_path = Path(__file__).resolve().parents[1] / ".tmp" / f"trrust_{name}.tsv"
    download_trrust(url, raw_path)
    nodes, edges = parse_trrust(raw_path)

    print(f"\n--- Processing TRRUST {name.upper()} Dataset ---")
    print(f"Nodes (Genes): {len(nodes)}")
    print(f"Edges (Directed Interactions): {len(edges)}")

    p_raw, F_grad, F_curl, F_harm, t_count, edges_list, F = run_hodge_decomposition(nodes, edges)

    # Compute Norms
    grad_norm = float(np.linalg.norm(F_grad))
    curl_norm = float(np.linalg.norm(F_curl))
    harm_norm = float(np.linalg.norm(F_harm))
    total_norm = float(np.linalg.norm(F_grad + F_curl + F_harm))

    print(f"Triangles: {t_count}")
    print(f"Gradient Flow Norm:  {grad_norm:.4f} ({grad_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Curl Flow Norm:      {curl_norm:.4f} ({curl_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Harmonic Flow Norm:  {harm_norm:.4f} ({harm_norm/max(1e-6, total_norm)*100:.1f}%)")

    # Normalize potential field to 0 - 100%
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Sort nodes by potential ascending (lowest potential is the source of flow, i.e. regulators)
    sorted_indices_asc = np.argsort(p_norm)

    # Master Regulators (Sources / Potential Basins: low potential)
    master_regulators = []
    print("\nTop 10 Master Regulators (Potential Basins / Sources):")
    for rank, idx in enumerate(sorted_indices_asc[:10], start=1):
        gene_name = nodes[idx]
        pot = p_norm[idx]
        master_regulators.append({"rank": rank, "gene": gene_name, "potential": float(pot)})
        print(f"  {rank}. {gene_name} (Potential: {pot*100:.1f}%)")

    # Downstream Targets (Sinks / Potential Peaks: high potential)
    target_sinks = []
    print("\nTop 10 Downstream Targets (Potential Peaks / Sinks):")
    for rank, idx in enumerate(reversed(sorted_indices_asc[-10:]), start=1):
        gene_name = nodes[idx]
        pot = p_norm[idx]
        target_sinks.append({"rank": rank, "gene": gene_name, "potential": float(pot)})
        print(f"  {rank}. {gene_name} (Potential: {pot*100:.1f}%)")

    # Export top 120 nodes by total degree to JSON for force-directed web visualization
    degrees = np.zeros(len(nodes))
    out_degrees = np.zeros(len(nodes))
    for idx, (u, v) in enumerate(edges_list):
        degrees[u] += 1
        degrees[v] += 1
        out_degrees[u] += 1

    N = 120
    top_indices = np.argsort(degrees)[::-1][:N]
    top_indices_set = set(top_indices)

    export_nodes = []
    for idx in top_indices:
        export_nodes.append({
            "id": nodes[idx],
            "label": nodes[idx],
            "documentCount": int(degrees[idx]),
            "mentionCount": int(degrees[idx]),
            "kind": "tf" if out_degrees[idx] > 0 else "gene",
            "potentialNorm": float(p_norm[idx])
        })

    export_edges = []
    for edge_idx, (u, v) in enumerate(edges_list):
        if u in top_indices_set and v in top_indices_set:
            export_edges.append({
                "source": nodes[u],
                "target": nodes[v],
                "documentCount": 1,
                "hodge": {
                    "gradient": float(F_grad[edge_idx]),
                    "curl": float(F_curl[edge_idx]),
                    "harmonic": float(F_harm[edge_idx]),
                    "total": float(F[edge_idx])
                }
            })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / f"{name}_nodes.json").open("w", encoding="utf-8") as f:
        json.dump(export_nodes, f, indent=2)
    with (OUTPUT_DIR / f"{name}_edges.json").open("w", encoding="utf-8") as f:
        json.dump(export_edges, f, indent=2)

    # Clean up raw files
    if raw_path.exists():
        raw_path.unlink()

    return {
        "dataset": f"TRRUST {name} regulatory network",
        "counts": {
            "genes": len(nodes),
            "interactions": len(edges),
            "triangles": t_count
        },
        "hodge": {
            "gradientNorm": grad_norm,
            "curlNorm": curl_norm,
            "harmonicNorm": harm_norm,
            "totalNorm": total_norm
        },
        "top_regulators": master_regulators,
        "top_targets": target_sinks
    }


def main() -> None:
    results = {}
    results["human"] = process_dataset("human", HUMAN_URL)
    results["mouse"] = process_dataset("mouse", MOUSE_URL)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved analysis summary to: {summary_path}")


if __name__ == "__main__":
    main()
