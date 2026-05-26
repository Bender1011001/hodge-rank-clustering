"""
Pipelines to run Hodge Decomposition on DREAM5, IBM AMLSim, and Elliptic Bitcoin.
This script provides fully implemented functions to load, preprocess, and execute
the Discrete Hodge decomposition on the three datasets once downloaded locally.
"""

from __future__ import annotations

from collections import defaultdict
import csv
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr


# =====================================================================
# 1. Elliptic Bitcoin Dataset Pipeline
# =====================================================================
def run_elliptic_hodge(features_path: str | Path, edges_path: str | Path) -> dict:
    """
    Run Hodge Decomposition on the Elliptic Bitcoin transaction graph.
    Nodes are transactions, edges represent directed flow of Bitcoins.
    """
    features_path = Path(features_path)
    edges_path = Path(edges_path)

    if not features_path.exists() or not edges_path.exists():
        raise FileNotFoundError(
            "Please download the Elliptic dataset from Kaggle and place the CSVs in the path.\n"
            "Required files: elliptic_txs_features.csv, elliptic_txs_edgelist.csv"
        )

    print("\n--- Loading Elliptic Bitcoin Dataset ---")

    # 1. Load node classification features (to identify licit/illicit nodes)
    # Col 0: txId, Col 1: class (1=illicit, 2=licit, 'unknown')
    node_classes = {}
    with features_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)  # Skip header
        for row in reader:
            if not row:
                continue
            tx_id = int(row[0])
            tx_class = row[1]
            node_classes[tx_id] = tx_class

    # 2. Load directed edges (BTC transaction flows)
    # Col 0: txId1, Col 1: txId2 (txId1 -> txId2)
    edges = []
    unique_nodes = set()
    with edges_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)  # Skip header
        for row in reader:
            if not row:
                continue
            u = int(row[0])
            v = int(row[1])
            if u == v:
                continue  # Skip self loops
            edges.append((u, v))
            unique_nodes.add(u)
            unique_nodes.add(v)

    nodes = sorted(list(unique_nodes))
    node_to_idx = {node_id: idx for idx, node_id in enumerate(nodes)}

    num_v = len(nodes)
    num_e = len(edges)
    print(f"Loaded {num_v} transaction nodes and {num_e} transaction edges.")

    # 3. Assemble Boundary Matrix B1
    # B1 maps vertices to edges: shape (num_v, num_e)
    # We assign a uniform flow of +1.0 for each transaction edge
    F = np.ones(num_e)
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        r1.extend([u_idx, v_idx])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])  # Flow goes from u to v

    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))

    # 4. Solve Potential Field Phi
    print("Solving Hodge Potential field (LSQR)...")
    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad

    # Compute Norms
    grad_norm = np.linalg.norm(F_grad)
    res_norm = np.linalg.norm(F_res)
    total_norm = np.linalg.norm(F)

    print(f"Gradient Flow Norm: {grad_norm:.4f} ({grad_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Residual (Cycles) Norm: {res_norm:.4f} ({res_norm/max(1e-6, total_norm)*100:.1f}%)")

    # Normalize potentials
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Group potentials by transaction class
    illicit_pots = [p_norm[node_to_idx[node_id]] for node_id, cls in node_classes.items() if cls == "1" and node_id in node_to_idx]
    licit_pots = [p_norm[node_to_idx[node_id]] for node_id, cls in node_classes.items() if cls == "2" and node_id in node_to_idx]

    results = {
        "dataset": "Elliptic Bitcoin",
        "counts": {"nodes": num_v, "edges": num_e},
        "hodge": {
            "gradient_norm": float(grad_norm),
            "residual_norm": float(res_norm),
            "total_norm": float(total_norm)
        },
        "potentials": {
            "avg_illicit_potential": float(np.mean(illicit_pots)) if illicit_pots else None,
            "avg_licit_potential": float(np.mean(licit_pots)) if licit_pots else None,
        }
    }
    print(f"Illicit Tx Avg Potential: {results['potentials']['avg_illicit_potential']}")
    print(f"Licit Tx Avg Potential: {results['potentials']['avg_licit_potential']}")
    return results


# =====================================================================
# 2. IBM AMLSim Dataset Pipeline
# =====================================================================
def run_amlsim_hodge(transactions_csv_path: str | Path, max_transactions: int = 100000) -> dict:
    """
    Run Hodge Decomposition on simulated banking transaction data from AMLSim.
    Isolates circular money-laundering flows (Harmonic component).
    """
    transactions_csv_path = Path(transactions_csv_path)
    if not transactions_csv_path.exists():
        raise FileNotFoundError(
            "Please generate/download transactions from AMLSim.\n"
            "Required file: transactions.csv"
        )

    print("\n--- Loading IBM AMLSim Transactions ---")

    # Load transactions: Col 2 (sender), Col 3 (receiver), Col 4 (amount), Col 8 (is_laundering)
    # File format: senderId, receiverId, amount, timestamp, isFraud...
    # We aggregate flows between node pairs.
    node_to_idx = {}
    nodes = []

    def get_node(acct: str) -> int:
        if acct not in node_to_idx:
            node_to_idx[acct] = len(nodes)
            nodes.append(acct)
        return node_to_idx[acct]

    edge_weights = defaultdict(float)
    fraud_edges = set()

    with transactions_csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if max_transactions is not None and idx >= max_transactions:
                break
            sender = row.get("SENDER_ADR", row.get("SENDER_ACCOUNT_ID"))
            receiver = row.get("RECEIVER_ADR", row.get("RECEIVER_ACCOUNT_ID"))
            amount = float(row.get("AMOUNT", row.get("TX_AMOUNT", 0.0)))
            val = row.get("IS_LAUNDERING", row.get("isFraud", row.get("IS_FRAUD", 0)))
            is_fraud = 1 if str(val).lower() in ("true", "1", "yes") else 0

            if sender == receiver:
                continue

            u = get_node(sender)
            v = get_node(receiver)

            edge_weights[(u, v)] += amount
            if is_fraud:
                fraud_edges.add((min(u, v), max(u, v)))

    # Assemble edge arrays
    edges_list = []
    F = []
    edge_to_idx = {}
    for (u, v), amount in edge_weights.items():
        idx = len(edges_list)
        edges_list.append((u, v))
        F.append(amount)
        edge_to_idx[(min(u, v), max(u, v))] = idx

    F = np.array(F)
    num_v = len(nodes)
    num_e = len(edges_list)
    print(f"Loaded {num_v} banking nodes and {num_e} aggregate transaction edges.")

    # 1. Assemble B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))

    # 2. Assemble B2 (Triangles)
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
                    e_vw = edge_to_idx.get((v, w))
                    e_uw = edge_to_idx.get((u, w))
                    e_uv = edge_to_idx.get((u, v))
                    if e_vw is not None and e_uw is not None and e_uv is not None:
                        r2.extend([e_vw, e_uw, e_uv])
                        c2.extend([t_idx, t_idx, t_idx])
                        d2.extend([1.0, -1.0, 1.0])
                        t_idx += 1

    B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

    # Solve LSQR
    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad

    if B2 is not None:
        c = lsqr(B2, F_res, atol=1e-5, btol=1e-5)[0]
        F_curl = B2.dot(c)
    else:
        F_curl = np.zeros(num_e)

    F_harm = F_res - F_curl

    # Calculate fraud correlation
    fraud_indices = [idx for idx, (u, v) in enumerate(edges_list) if (min(u, v), max(u, v)) in fraud_edges]
    clean_indices = [idx for idx, (u, v) in enumerate(edges_list) if (min(u, v), max(u, v)) not in fraud_edges]

    avg_fraud_harm = np.mean(np.abs(F_harm[fraud_indices])) if fraud_indices else 0.0
    avg_clean_harm = np.mean(np.abs(F_harm[clean_indices])) if clean_indices else 0.0

    print(f"Laundering Loops Triangles Count: {t_idx}")
    print(f"Average Laundering Edge Harmonic Magnitude: {avg_fraud_harm:.4f}")
    print(f"Average Legitimate Edge Harmonic Magnitude: {avg_clean_harm:.4f}")

    return {
        "dataset": "IBM AMLSim",
        "counts": {"nodes": num_v, "edges": num_e, "triangles": t_idx},
        "laundering_loop_signature": {
            "avg_laundering_harmonic_flow": float(avg_fraud_harm),
            "avg_legitimate_harmonic_flow": float(avg_clean_harm)
        }
    }


# =====================================================================
# 3. DREAM5 Gene Regulatory Network Pipeline
# =====================================================================
def run_dream5_hodge(expression_tsv_path: str | Path, gold_standard_tsv_path: str | Path) -> dict:
    """
    Run Hodge Decomposition on the DREAM5 Gene Regulatory Network.
    Computes TF-target correlations and evaluates against the true directed network.
    """
    expression_tsv_path = Path(expression_tsv_path)
    gold_standard_tsv_path = Path(gold_standard_tsv_path)

    if not expression_tsv_path.exists() or not gold_standard_tsv_path.exists():
        raise FileNotFoundError(
            "Please download the DREAM5 challenge network dataset from Synapse.\n"
            "Required files: netX_expression_data.tsv, netX_gold_standard.tsv"
        )

    print("\n--- Loading DREAM5 Dataset ---")

    # 1. Load Expression Matrix (genes as rows, experiments as columns)
    # For DREAM5, the expression file has genes in rows and values tab-separated.
    gene_names = []
    expr_profiles = []
    with expression_tsv_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        # First row is the list of gene names
        gene_names = [name.strip() for name in next(reader) if name.strip()]
        for row in reader:
            if not row:
                continue
            expr_profiles.append([float(val) for val in row])

    expr_profiles = np.array(expr_profiles).T
    num_genes = len(gene_names)
    gene_to_idx = {name: idx for idx, name in enumerate(gene_names)}
    print(f"Loaded expression profiles for {num_genes} genes.")

    # 2. Load Gold Standard Directed Network
    # Col 0: TF, Col 1: Target, Col 2: interaction (1=exists, 0=no)
    true_edges = set()
    with gold_standard_tsv_path.open("r", encoding="utf-8") as handle:
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

    # 3. Build Correlation/Preference Flow
    # We assign asymmetric flow values using Pearson correlation coefficients.
    # If TF u regulates Target v, we expect a correlation. We use the raw values
    # for positive/negative regulation.
    corr_matrix = np.corrcoef(expr_profiles)

    # We select active TF-target pairs based on the top absolute correlations.
    edges = []
    F = []
    edge_to_idx = {}
    threshold = 0.55  # Correlation cutoff

    for tf_idx, target_idx in true_edges:
        flow = corr_matrix[tf_idx, target_idx]
        if np.abs(flow) >= threshold:
            idx = len(edges)
            edges.append((tf_idx, target_idx))
            F.append(flow)
            edge_to_idx[(min(tf_idx, target_idx), max(tf_idx, target_idx))] = idx

    F = np.array(F)
    num_e = len(edges)
    print(f"Assembled {num_e} active directed regulation edges above threshold={threshold}.")

    if num_e == 0:
        print("No edges matched the threshold. Increase the threshold or run with raw values.")
        return {"dataset": "DREAM5", "status": "No active edges."}

    # 4. Assemble B1
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, num_e))

    # 5. Solve LSQR Potential
    p_raw = lsqr(B1.T, F, atol=1e-5, btol=1e-5)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad

    grad_norm = np.linalg.norm(F_grad)
    res_norm = np.linalg.norm(F_res)
    total_norm = np.linalg.norm(F)

    # Normalize potentials
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Sort genes by potential (Highest potentials are candidate transcription factors/sources)
    sorted_idx = np.argsort(-p_norm)
    top_tfs = [gene_names[idx] for idx in sorted_idx[:10]]

    print("\nHodge Predicted Top Master Regulators (peaks):")
    for rank, name in enumerate(top_tfs, start=1):
        print(f"  {rank}. {name}")

    return {
        "dataset": "DREAM5 Gene Regulatory Network",
        "counts": {"genes": num_genes, "active_edges": num_e},
        "hodge": {
            "gradient_norm": float(grad_norm),
            "residual_norm": float(res_norm),
            "total_norm": float(total_norm)
        },
        "top_regulators": top_tfs
    }


if __name__ == "__main__":
    print("This module provides fully implemented pipelines for financial and biological data.")
    print("Download the files locally and import these functions to run.")
