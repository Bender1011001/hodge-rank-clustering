import argparse
import os
import sys
import csv
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.synapse_auth import login_synapse

# Network Synapse ID mapping:
# Net 1: In Silico (1643 genes)
# Net 3: E. coli (4511 genes)
# Net 4: Yeast (5950 genes)
NETS = {
    1: {"name": "net1", "expr": "syn2787226", "gold": "syn2787240", "tfs": "syn2787227", "desc": "DREAM5 in-silico regulatory network"},
    3: {"name": "net3", "expr": "syn2787234", "gold": "syn2787243", "tfs": "syn2787235", "desc": "DREAM5 ecoli regulatory network"},
    4: {"name": "net4", "expr": "syn2787238", "gold": "syn2787244", "tfs": "syn2787239", "desc": "DREAM5 yeast regulatory network"}
}


def process_network(net_num, syn, tmp_dir):
    info = NETS[net_num]
    expr_id = info["expr"]
    gold_id = info["gold"]
    tfs_id = info["tfs"]
    name = info["name"]
    desc = info["desc"]

    print(f"\n--- Downloading Net {net_num} ({desc}) ---")
    expr_file = syn.get(expr_id, downloadLocation=str(tmp_dir))
    gold_file = syn.get(gold_id, downloadLocation=str(tmp_dir))
    tfs_file = syn.get(tfs_id, downloadLocation=str(tmp_dir))

    # Parse TFs
    true_tfs = set()
    with open(tfs_file.path, "r", encoding="utf-8") as handle:
        for line in handle:
            val = line.strip()
            if val:
                true_tfs.add(val)

    # Parse Expression
    gene_names = []
    expr_profiles = []
    with open(expr_file.path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        gene_names = [n.strip() for n in next(reader) if n.strip()]
        for row in reader:
            if not row:
                continue
            expr_profiles.append([float(val) for val in row])
    expr_profiles = np.array(expr_profiles).T
    num_genes = len(gene_names)
    gene_to_idx = {n: idx for idx, n in enumerate(gene_names)}
    print(f"Loaded expression profiles for {num_genes} genes.")

    # Parse Gold Standard
    true_edges = set()
    with open(gold_file.path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or len(row) < 3:
                continue
            if row[2].strip() == "1":
                tf = row[0].strip()
                target = row[1].strip()
                if tf in gene_to_idx and target in gene_to_idx:
                    true_edges.add((gene_to_idx[tf], gene_to_idx[target]))

    print(f"Loaded {len(true_edges)} true positive directed regulation edges.")

    # Compute correlation flow matrix
    print("Computing Pearson correlation matrix...")
    corr_matrix = np.corrcoef(expr_profiles)

    # We select active TF-target pairs based on top correlations
    edges = []
    F = []
    edge_to_idx = {}
    threshold = 0.55  # Correlation cutoff

    for tf_idx, target_idx in true_edges:
        flow = corr_matrix[tf_idx, target_idx]
        if np.abs(flow) >= threshold:
            idx = len(edges)
            edges.append((tf_idx, target_idx))
            # We use absolute correlation flow for DREAM5 to prevent potential field cancellation
            F.append(np.abs(flow))
            edge_to_idx[(min(tf_idx, target_idx), max(tf_idx, target_idx))] = idx

    F = np.array(F)
    num_e = len(edges)
    print(f"Assembled {num_e} active directed regulation edges above threshold={threshold}.")

    if num_e == 0:
        print("No edges matched the threshold.")
        return None

    # Assemble Boundary Matrix B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    # Assemble B2 (Triangles)
    adj = {i: set() for i in range(num_genes)}
    for (u, v) in edges:
        adj[u].add(v)
        adj[v].add(u)

    r2, c2, d2 = [], [], []
    t_idx = 0
    for u in range(num_genes):
        neighbors = sorted([v for v in adj[u] if v > u])
        for i in range(len(neighbors)):
            v = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w = neighbors[j]
                if w in adj[v]:
                    # Triangle found
                    e_vw = edge_to_idx.get((v, w))
                    e_uw = edge_to_idx.get((u, w))
                    e_uv = edge_to_idx.get((u, v))
                    if e_vw is not None and e_uw is not None and e_uv is not None:
                        r2.extend([e_vw, e_uw, e_uv])
                        c2.extend([t_idx, t_idx, t_idx])
                        d2.extend([1.0, -1.0, 1.0])
                        t_idx += 1

    B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

    # Solve potential field Phi using LSQR
    print("Solving Hodge Potential field...")
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

    # Compute Norms
    grad_norm = float(np.linalg.norm(F_grad))
    curl_norm = float(np.linalg.norm(F_curl))
    harm_norm = float(np.linalg.norm(F_harm))
    total_norm = float(np.linalg.norm(F_grad + F_curl + F_harm))

    print(f"Triangles: {t_idx}")
    print(f"Gradient Flow Norm:  {grad_norm:.4f} ({grad_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Curl Flow Norm:      {curl_norm:.4f} ({curl_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Harmonic Flow Norm:  {harm_norm:.4f} ({harm_norm/max(1e-6, total_norm)*100:.1f}%)")

    # Normalize potentials
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Sort nodes by potential ascending (lowest potential is the source of flow, i.e. regulators)
    sorted_indices_asc = np.argsort(p_norm)

    # Master Regulators (Sources / Potential Basins: low potential)
    master_regulators = []
    print("\nTop 10 Master Regulators (Potential Basins / Sources):")
    for rank, idx in enumerate(sorted_indices_asc[:10], start=1):
        gene_name = gene_names[idx]
        pot = p_norm[idx]
        master_regulators.append({"rank": rank, "gene": gene_name, "potential": float(pot)})
        print(f"  {rank}. {gene_name} (Potential: {pot*100:.1f}%)")

    # Downstream Targets (Sinks / Potential Peaks: high potential)
    target_sinks = []
    print("\nTop 10 Downstream Targets (Potential Peaks / Sinks):")
    for rank, idx in enumerate(reversed(sorted_indices_asc[-10:]), start=1):
        gene_name = gene_names[idx]
        pot = p_norm[idx]
        target_sinks.append({"rank": rank, "gene": gene_name, "potential": float(pot)})
        print(f"  {rank}. {gene_name} (Potential: {pot*100:.1f}%)")

    # Export top 120 nodes by total degree to JSON for force-directed web visualization
    degrees = np.zeros(num_genes)
    out_degrees = np.zeros(num_genes)
    for u, v in edges:
        degrees[u] += 1
        degrees[v] += 1
        out_degrees[u] += 1

    N = 120
    top_indices = np.argsort(degrees)[::-1][:N]
    top_indices_set = set(top_indices)

    export_nodes = []
    for idx in top_indices:
        gene_name = gene_names[idx]
        export_nodes.append({
            "id": gene_name,
            "label": gene_name,
            "documentCount": int(degrees[idx]),
            "mentionCount": int(degrees[idx]),
            "kind": "tf" if (gene_name in true_tfs or out_degrees[idx] > 0) else "gene",
            "potentialNorm": float(p_norm[idx])
        })

    export_edges = []
    for edge_idx, (u, v) in enumerate(edges):
        if u in top_indices_set and v in top_indices_set:
            export_edges.append({
                "source": gene_names[u],
                "target": gene_names[v],
                "documentCount": 1,
                "hodge": {
                    "gradient": float(F_grad[edge_idx]),
                    "curl": float(F_curl[edge_idx]),
                    "harmonic": float(F_harm[edge_idx]),
                    "total": float(F[edge_idx])
                }
            })

    out_dir = ROOT / "site" / "data" / "dream5"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{name}_nodes.json").open("w", encoding="utf-8") as f:
        json.dump(export_nodes, f, indent=2)
    with (out_dir / f"{name}_edges.json").open("w", encoding="utf-8") as f:
        json.dump(export_edges, f, indent=2)

    # Clean up raw files
    for filepath in [expr_file.path, gold_file.path, tfs_file.path]:
        p = Path(filepath)
        if p.exists():
            p.unlink()

    return {
        "dataset": desc,
        "counts": {
            "genes": num_genes,
            "interactions": num_e,
            "triangles": t_idx
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


def main():
    parser = argparse.ArgumentParser(description="Download and run DREAM5 Hodge pipeline.")
    parser.add_argument("--net", type=int, choices=[1, 3, 4], help="DREAM5 network number (1, 3, or 4). If not set, runs all networks.")
    args = parser.parse_args()

    print("Logging in to Synapse...")
    syn = login_synapse()

    tmp_dir = ROOT / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    networks_to_run = [args.net] if args.net is not None else [1, 3, 4]

    results = {}
    # If a combined summary already exists, load it first to avoid losing other nets' data
    summary_path = ROOT / "site" / "data" / "dream5" / "summary.json"
    if summary_path.exists():
        try:
            results = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}

    for net_num in networks_to_run:
        net_res = process_network(net_num, syn, tmp_dir)
        if net_res is not None:
            results[f"net{net_num}"] = net_res

    # Write combined summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved combined analysis summary to: {summary_path}")


if __name__ == "__main__":
    main()
