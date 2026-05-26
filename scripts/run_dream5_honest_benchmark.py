import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.synapse_auth import login_synapse


NETS = {
    1: {
        "name": "net1",
        "expr": "syn2787226",
        "gold": "syn2787240",
        "tfs": "syn2787227",
        "desc": "DREAM5 in-silico regulatory network",
    },
    3: {
        "name": "net3",
        "expr": "syn2787234",
        "gold": "syn2787243",
        "tfs": "syn2787235",
        "desc": "DREAM5 E. coli regulatory network",
    },
    4: {
        "name": "net4",
        "expr": "syn2787238",
        "gold": "syn2787244",
        "tfs": "syn2787239",
        "desc": "DREAM5 yeast regulatory network",
    },
}


def parse_expression(path):
    gene_names = []
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        gene_names = [name.strip() for name in next(reader) if name.strip()]
        for row in reader:
            if row:
                rows.append([float(value) for value in row])
    return gene_names, np.asarray(rows, dtype=float).T


def parse_tfs(path):
    tfs = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value:
                tfs.append(value)
    return tfs


def parse_gold(path, gene_to_idx):
    gold_rows = []
    positives = 0
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue
            tf_name = row[0].strip()
            target_name = row[1].strip()
            label_text = row[2].strip()
            if tf_name not in gene_to_idx or target_name not in gene_to_idx:
                continue
            try:
                label = int(float(label_text))
            except ValueError:
                continue
            if label not in (0, 1):
                continue
            positives += label
            gold_rows.append((gene_to_idx[tf_name], gene_to_idx[target_name], label))
    return gold_rows, positives


def standardize_rows(values):
    centered = values - values.mean(axis=1, keepdims=True)
    scale = centered.std(axis=1, ddof=1, keepdims=True)
    scale[scale == 0.0] = np.inf
    return centered / scale


def tf_gene_correlations(expr_profiles, tf_indices):
    z = standardize_rows(expr_profiles)
    denom = max(1, z.shape[1] - 1)
    return z[tf_indices].dot(z.T) / denom


def build_hodge_graph(tf_indices, corr_tf_gene, top_per_tf, max_edges):
    candidates = []
    for row_idx, tf_idx in enumerate(tf_indices):
        weights = np.abs(corr_tf_gene[row_idx]).copy()
        weights[tf_idx] = -np.inf
        if top_per_tf >= len(weights):
            target_indices = np.argsort(weights)[::-1]
        else:
            unsorted = np.argpartition(weights, -top_per_tf)[-top_per_tf:]
            target_indices = unsorted[np.argsort(weights[unsorted])[::-1]]
        for target_idx in target_indices:
            weight = float(weights[target_idx])
            if np.isfinite(weight):
                candidates.append((weight, tf_idx, int(target_idx)))

    candidates.sort(reverse=True)
    if max_edges > 0:
        candidates = candidates[:max_edges]

    num_genes = corr_tf_gene.shape[1]
    edge_count = len(candidates)
    if edge_count == 0:
        return {
            "potential": np.zeros(num_genes, dtype=float),
            "edges": [],
            "edge_values": {},
            "residual_norm": 0.0,
            "flow_norm": 0.0,
        }

    r1 = []
    c1 = []
    d1 = []
    flows = np.empty(edge_count, dtype=float)
    edges = []
    for edge_idx, (weight, source_idx, target_idx) in enumerate(candidates):
        r1.extend([source_idx, target_idx])
        c1.extend([edge_idx, edge_idx])
        d1.extend([-1.0, 1.0])
        flows[edge_idx] = weight
        edges.append((source_idx, target_idx))

    b1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_genes, edge_count))
    potential = lsqr(b1.T, flows, atol=1e-6, btol=1e-6)[0]
    grad = b1.T.dot(potential)
    residual_norm = float(np.linalg.norm(flows - grad))
    edge_values = {
        edge: (float(flow), float(gradient))
        for edge, flow, gradient in zip(edges, flows, grad)
    }
    return {
        "potential": potential,
        "edges": edges,
        "edge_values": edge_values,
        "residual_norm": residual_norm,
        "flow_norm": float(np.linalg.norm(flows)),
    }


def score_gold_rows(gold_rows, tf_to_row, corr_tf_gene, hodge_graph):
    potential = hodge_graph["potential"]
    edge_values = hodge_graph["edge_values"]
    potential_span = float(np.ptp(potential))
    if potential_span <= 0.0:
        potential_span = 1.0
    scores = {
        "pearson_abs": [],
        "pearson_signed": [],
        "hodge_delta": [],
        "hodge_reverse_delta": [],
        "hodge_abs_delta": [],
        "hodge_delta_norm": [],
        "hodge_weighted": [],
        "hodge_weighted_norm": [],
        "hodge_blend": [],
        "hodge_blend_norm": [],
        "candidate_abs_corr": [],
        "candidate_gradient": [],
        "candidate_fit_score": [],
    }
    labels = []
    records = []
    diagnostics = {
        "candidate_positive_edges": 0,
        "candidate_negative_edges": 0,
        "positive_edges_scored": 0,
        "negative_edges_scored": 0,
        "mean_abs_corr_positive": 0.0,
        "mean_abs_corr_negative": 0.0,
        "mean_hodge_delta_positive": 0.0,
        "mean_hodge_delta_negative": 0.0,
        "potential_span": potential_span,
    }
    sums = {
        "abs_corr_positive": 0.0,
        "abs_corr_negative": 0.0,
        "delta_positive": 0.0,
        "delta_negative": 0.0,
    }
    for tf_idx, target_idx, label in gold_rows:
        row_idx = tf_to_row.get(tf_idx)
        if row_idx is None:
            continue
        corr = float(corr_tf_gene[row_idx, target_idx])
        abs_corr = abs(corr)
        delta = float(potential[target_idx] - potential[tf_idx])
        positive_delta = max(0.0, delta)
        reverse_delta = max(0.0, -delta)
        abs_delta = abs(delta)
        positive_delta_norm = positive_delta / potential_span
        edge_value = edge_values.get((tf_idx, target_idx))
        is_candidate = edge_value is not None
        if edge_value is None:
            candidate_gradient = 0.0
            candidate_fit_score = 0.0
        else:
            flow, gradient = edge_value
            candidate_gradient = max(0.0, gradient)
            candidate_fit_score = max(0.0, abs_corr - abs(flow - gradient))

        scores["pearson_abs"].append(abs_corr)
        scores["pearson_signed"].append(corr)
        scores["hodge_delta"].append(positive_delta)
        scores["hodge_reverse_delta"].append(reverse_delta)
        scores["hodge_abs_delta"].append(abs_delta)
        scores["hodge_delta_norm"].append(positive_delta_norm)
        scores["hodge_weighted"].append(abs_corr * positive_delta)
        scores["hodge_weighted_norm"].append(abs_corr * positive_delta_norm)
        scores["hodge_blend"].append((0.7 * abs_corr) + (0.3 * positive_delta))
        scores["hodge_blend_norm"].append(
            (0.9 * abs_corr) + (0.1 * positive_delta_norm)
        )
        scores["candidate_abs_corr"].append(abs_corr if is_candidate else 0.0)
        scores["candidate_gradient"].append(candidate_gradient)
        scores["candidate_fit_score"].append(candidate_fit_score)
        labels.append(label)
        records.append(
            {
                "label": label,
                "tf_idx": tf_idx,
                "target_idx": target_idx,
                "abs_corr": abs_corr,
                "hodge_delta": positive_delta,
            }
        )
        if label == 1:
            diagnostics["positive_edges_scored"] += 1
            diagnostics["candidate_positive_edges"] += int(is_candidate)
            sums["abs_corr_positive"] += abs_corr
            sums["delta_positive"] += positive_delta
        else:
            diagnostics["negative_edges_scored"] += 1
            diagnostics["candidate_negative_edges"] += int(is_candidate)
            sums["abs_corr_negative"] += abs_corr
            sums["delta_negative"] += positive_delta

    if diagnostics["positive_edges_scored"] > 0:
        diagnostics["mean_abs_corr_positive"] = (
            sums["abs_corr_positive"] / diagnostics["positive_edges_scored"]
        )
        diagnostics["mean_hodge_delta_positive"] = (
            sums["delta_positive"] / diagnostics["positive_edges_scored"]
        )
    if diagnostics["negative_edges_scored"] > 0:
        diagnostics["mean_abs_corr_negative"] = (
            sums["abs_corr_negative"] / diagnostics["negative_edges_scored"]
        )
        diagnostics["mean_hodge_delta_negative"] = (
            sums["delta_negative"] / diagnostics["negative_edges_scored"]
        )
    diagnostics["candidate_positive_rate"] = (
        diagnostics["candidate_positive_edges"]
        / max(1, diagnostics["positive_edges_scored"])
    )
    diagnostics["candidate_negative_rate"] = (
        diagnostics["candidate_negative_edges"]
        / max(1, diagnostics["negative_edges_scored"])
    )
    diagnostics["top_rank_diagnostics"] = top_rank_diagnostics(records)
    return np.asarray(labels, dtype=int), {
        name: np.asarray(values, dtype=float) for name, values in scores.items()
    }, diagnostics


def top_rank_diagnostics(records):
    output = {}
    for score_name in ("hodge_delta", "abs_corr"):
        ordered = sorted(records, key=lambda item: item[score_name], reverse=True)
        output[score_name] = {}
        for k in (100, 500, 1000):
            top = ordered[: min(k, len(ordered))]
            if not top:
                output[score_name][str(k)] = {
                    "positives": 0,
                    "unique_tfs": 0,
                    "unique_targets": 0,
                    "mean_abs_corr": 0.0,
                    "mean_hodge_delta": 0.0,
                }
                continue
            output[score_name][str(k)] = {
                "positives": int(sum(item["label"] for item in top)),
                "unique_tfs": len({item["tf_idx"] for item in top}),
                "unique_targets": len({item["target_idx"] for item in top}),
                "mean_abs_corr": float(
                    np.mean([item["abs_corr"] for item in top])
                ),
                "mean_hodge_delta": float(
                    np.mean([item["hodge_delta"] for item in top])
                ),
            }
    return output


def precision_at_k(labels, scores, k):
    if len(labels) == 0:
        return None
    k = min(k, len(labels))
    if k == 0:
        return None
    order = np.argsort(scores)[::-1][:k]
    return float(np.mean(labels[order]))


def evaluate(labels, scores_by_name):
    output = {}
    has_both_classes = len(set(labels.tolist())) == 2
    for name, scores in scores_by_name.items():
        result = {
            "precision_at_100": precision_at_k(labels, scores, 100),
            "precision_at_500": precision_at_k(labels, scores, 500),
            "precision_at_1000": precision_at_k(labels, scores, 1000),
        }
        if has_both_classes:
            result["aupr"] = float(average_precision_score(labels, scores))
            result["auroc"] = float(roc_auc_score(labels, scores))
        else:
            result["aupr"] = None
            result["auroc"] = None
        output[name] = result
    return output


def load_network(syn, net_num, tmp_dir):
    info = NETS[net_num]
    expr_file = syn.get(info["expr"], downloadLocation=str(tmp_dir))
    gold_file = syn.get(info["gold"], downloadLocation=str(tmp_dir))
    tfs_file = syn.get(info["tfs"], downloadLocation=str(tmp_dir))
    try:
        gene_names, expr_profiles = parse_expression(expr_file.path)
        gene_to_idx = {name: idx for idx, name in enumerate(gene_names)}
        tf_names = parse_tfs(tfs_file.path)
        tf_indices = [gene_to_idx[name] for name in tf_names if name in gene_to_idx]
        gold_rows, positives = parse_gold(gold_file.path, gene_to_idx)
        return gene_names, expr_profiles, tf_indices, gold_rows, positives
    finally:
        for filepath in (expr_file.path, gold_file.path, tfs_file.path):
            path = Path(filepath)
            if path.exists():
                path.unlink()


def run_network(syn, net_num, args):
    tmp_dir = ROOT / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    gene_names, expr_profiles, tf_indices, gold_rows, positives = load_network(
        syn, net_num, tmp_dir
    )
    corr_tf_gene = tf_gene_correlations(expr_profiles, tf_indices)
    tf_to_row = {tf_idx: row_idx for row_idx, tf_idx in enumerate(tf_indices)}
    hodge_graph = build_hodge_graph(
        tf_indices, corr_tf_gene, args.top_per_tf, args.max_hodge_edges
    )
    labels, scores_by_name, diagnostics = score_gold_rows(
        gold_rows, tf_to_row, corr_tf_gene, hodge_graph
    )
    metrics = evaluate(labels, scores_by_name)
    return {
        "dataset": NETS[net_num]["desc"],
        "leakage_control": {
            "gold_used_for_inference": False,
            "gold_used_for_scoring_only": True,
            "inference_inputs": ["expression matrix", "provided TF list"],
        },
        "counts": {
            "genes": len(gene_names),
            "tfs": len(tf_indices),
            "gold_pairs_scored": int(len(labels)),
            "gold_positive_edges": int(positives),
            "hodge_candidate_edges": len(hodge_graph["edges"]),
        },
        "hodge_graph": {
            "top_per_tf": args.top_per_tf,
            "max_edges": args.max_hodge_edges,
            "residual_norm": hodge_graph["residual_norm"],
            "flow_norm": hodge_graph["flow_norm"],
            "residual_to_flow_ratio": (
                hodge_graph["residual_norm"] / hodge_graph["flow_norm"]
                if hodge_graph["flow_norm"] > 0.0
                else None
            ),
        },
        "diagnostics": diagnostics,
        "metrics": metrics,
    }


def print_summary(results):
    for key, result in results.items():
        counts = result["counts"]
        print(f"\n{key}: {result['dataset']}")
        print(
            f"  genes={counts['genes']} tfs={counts['tfs']} "
            f"gold_pairs={counts['gold_pairs_scored']} positives={counts['gold_positive_edges']} "
            f"hodge_edges={counts['hodge_candidate_edges']}"
        )
        diagnostics = result["diagnostics"]
        print(
            "  candidate coverage: "
            f"pos={diagnostics['candidate_positive_rate']:.3f} "
            f"neg={diagnostics['candidate_negative_rate']:.3f}; "
            "mean abs corr pos/neg="
            f"{diagnostics['mean_abs_corr_positive']:.4f}/"
            f"{diagnostics['mean_abs_corr_negative']:.4f}; "
            "mean hodge delta pos/neg="
            f"{diagnostics['mean_hodge_delta_positive']:.4f}/"
            f"{diagnostics['mean_hodge_delta_negative']:.4f}"
        )
        print("  method             AUPR     AUROC    P@100   P@500   P@1000")
        for method, metrics in result["metrics"].items():
            aupr = metrics["aupr"]
            auroc = metrics["auroc"]
            p100 = metrics["precision_at_100"]
            p500 = metrics["precision_at_500"]
            p1000 = metrics["precision_at_1000"]
            print(
                f"  {method:<16} "
                f"{aupr if aupr is not None else float('nan'):7.4f} "
                f"{auroc if auroc is not None else float('nan'):7.4f} "
                f"{p100 if p100 is not None else float('nan'):7.4f} "
                f"{p500 if p500 is not None else float('nan'):7.4f} "
                f"{p1000 if p1000 is not None else float('nan'):7.4f}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Run leakage-free DREAM5-style edge ranking from expression data."
    )
    parser.add_argument(
        "--net",
        type=int,
        choices=sorted(NETS),
        action="append",
        help="Network number to run. Repeat for multiple networks. Defaults to all.",
    )
    parser.add_argument("--top-per-tf", type=int, default=200)
    parser.add_argument("--max-hodge-edges", type=int, default=50000)
    parser.add_argument(
        "--output",
        default=str(ROOT / "site" / "data" / "dream5" / "honest_scores.json"),
    )
    args = parser.parse_args()

    syn = login_synapse()
    nets = args.net or sorted(NETS)
    results = {}
    for net_num in nets:
        results[f"net{net_num}"] = run_network(syn, net_num, args)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print_summary(results)
    print(f"\nSaved leakage-free scores to {output_path}")


if __name__ == "__main__":
    main()
