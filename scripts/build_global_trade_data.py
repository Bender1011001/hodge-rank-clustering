"""
Build Global Trade Dataset and Run Discrete Hodge Decomposition.
Downloads WITS 2017 international trade network (nodes/edges) and country coordinates,
computes net trade flows, runs Hodge decomposition, and exports visual layout files.
"""

from __future__ import annotations

import csv
import json
import urllib.request
import io
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr

# Data URLs
WITS_NODES_URL = "https://raw.githubusercontent.com/aminst/wits/master/data/2017/nodelist.csv"
WITS_EDGES_URL = "https://raw.githubusercontent.com/aminst/wits/master/data/2017/edgelist_threshold.csv"
COORD_GIST_URL = "https://gist.githubusercontent.com/tadast/8827699/raw/countries_codes_and_coordinates.csv"

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "site" / "data" / "trade"


def fetch_csv(url: str) -> list[dict]:
    """Fetch a CSV file from a URL and return a list of dictionaries."""
    print(f"Fetching from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8")

    # Use csv.DictReader to parse the CSV string
    reader = csv.DictReader(io.StringIO(content))
    return [row for row in reader]


def parse_coordinates(rows: list[dict]) -> dict[str, tuple[str, float, float]]:
    """Parse coordinate gist rows into a mapping of Alpha-3 code -> (name, lat, lon)."""
    coord_map = {}
    for row in rows:
        # Strip whitespace and quotes from keys and values
        clean_row = {k.strip().replace('"', ''): v.strip().replace('"', '') for k, v in row.items()}

        iso3 = clean_row.get("Alpha-3 code")
        name = clean_row.get("Country")
        lat_str = clean_row.get("Latitude (average)")
        lon_str = clean_row.get("Longitude (average)")

        if iso3 and name and lat_str and lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                coord_map[iso3] = (name, lat, lon)
            except ValueError:
                continue
    return coord_map


def main() -> None:
    # 1. Download datasets
    raw_nodes = fetch_csv(WITS_NODES_URL)
    raw_edges = fetch_csv(WITS_EDGES_URL)
    raw_coords = fetch_csv(COORD_GIST_URL)

    # Parse coordinates
    coord_map = parse_coordinates(raw_coords)

    # Define coordinate overrides for missing/mismatched ISO3 codes if any
    coord_overrides = {
        "ROM": (45.9432, 24.9668), # Romania (sometimes ROM or ROU)
        "ZAR": (-4.0383, 21.7587), # Democratic Republic of the Congo (Zaire)
    }

    # 2. Process countries (nodes)
    node_to_idx = {}
    nodes_metadata = []

    for idx, row in enumerate(raw_nodes):
        iso3 = row["country_iso3"].strip()
        node_to_idx[iso3] = len(nodes_metadata)

        # Parse numeric attributes safely
        try:
            gdp = float(row.get("gdp_us_dollar", 0.0))
        except (ValueError, TypeError):
            gdp = 0.0

        try:
            population = float(row.get("population", 0.0))
        except (ValueError, TypeError):
            population = 0.0

        try:
            gdp_capita = float(row.get("gdp_per_capita", 0.0))
        except (ValueError, TypeError):
            gdp_capita = 0.0

        try:
            landlocked = int(row.get("landlocked", 0))
        except (ValueError, TypeError):
            landlocked = 0

        # Retrieve name, lat/lon
        name_lat_lon = coord_map.get(iso3)
        if name_lat_lon:
            name, lat, lon = name_lat_lon
        else:
            name = iso3
            lat, lon = coord_overrides.get(iso3, (0.0, 0.0))

        nodes_metadata.append({
            "iso3": iso3,
            "name": name,
            "continent": row.get("continent", "Unknown").strip(),
            "gdp": gdp,
            "population": population,
            "gdp_capita": gdp_capita,
            "landlocked": landlocked,
            "latitude": lat,
            "longitude": lon
        })

    print(f"Loaded {len(nodes_metadata)} countries.")

    # 3. Construct net trade flows
    # WITS edge list has exporter as source, importer as target.
    # Exporter (source) -> Importer (target) represents flow of goods.
    # We want to compute net flow of goods: F_uv = Trade(u->v) - Trade(v->u).
    # Since the coordinates/nodes list has 166 countries, we only keep flows between these countries.
    trade_matrix = defaultdict(float)
    for row in raw_edges:
        u = row["source"].strip()
        v = row["target"].strip()
        try:
            val = float(row["weight"])
        except ValueError:
            val = 0.0

        if u in node_to_idx and v in node_to_idx:
            trade_matrix[(u, v)] = val

    # Build unique undirected edges
    all_countries = list(node_to_idx.keys())
    edges_list = []
    F_list = []

    for i in range(len(all_countries)):
        u = all_countries[i]
        for j in range(i + 1, len(all_countries)):
            v = all_countries[j]
            t_uv = trade_matrix[(u, v)]
            t_vu = trade_matrix[(v, u)]
            net_flow = t_uv - t_vu

            if abs(net_flow) > 1e-3:
                # We save edge as (u, v) and flow as net_flow
                edges_list.append((u, v))
                F_list.append(net_flow)

    num_v = len(nodes_metadata)
    num_e = len(edges_list)
    F = np.array(F_list)
    print(f"Constructed net flow network with {num_v} nodes and {num_e} edges.")

    # 4. Run Hodge Decomposition
    # Map edges to indices
    edge_to_idx = {edges_list[idx]: idx for idx in range(num_e)}

    # Build B1 (boundary incidence matrix)
    r1, c1, d1 = [], [], []
    for idx, (u, v) in enumerate(edges_list):
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        r1.extend([u_idx, v_idx])
        c1.extend([idx, idx])
        d1.extend([-1.0, 1.0])  # flow goes from u to v if net_flow > 0
    B1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_v, num_e))

    # Build B2 (triangle mapping)
    # Build adjacency list
    adj = {i: set() for i in range(num_v)}
    for (u, v) in edges_list:
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        adj[u_idx].add(v_idx)
        adj[v_idx].add(u_idx)

    r2, c2, d2 = [], [], []
    t_idx = 0
    for u_idx in range(num_v):
        neighbors = sorted([v for v in adj[u_idx] if v > u_idx])
        for i in range(len(neighbors)):
            v_idx = neighbors[i]
            for j in range(i + 1, len(neighbors)):
                w_idx = neighbors[j]
                if w_idx in adj[v_idx]:
                    # Triangle found (u_idx, v_idx, w_idx) with u_idx < v_idx < w_idx
                    u_code = all_countries[u_idx]
                    v_code = all_countries[v_idx]
                    w_code = all_countries[w_idx]

                    e_vw = edge_to_idx.get((v_code, w_code))
                    e_uw = edge_to_idx.get((u_code, w_code))
                    e_uv = edge_to_idx.get((u_code, v_code))

                    if e_vw is not None and e_uw is not None and e_uv is not None:
                        r2.extend([e_vw, e_uw, e_uv])
                        c2.extend([t_idx, t_idx, t_idx])
                        d2.extend([1.0, -1.0, 1.0])
                        t_idx += 1

    B2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_e, t_idx)) if t_idx > 0 else None

    # Solve potential field p using LSQR
    p_raw = lsqr(B1.T, F, atol=1e-6, btol=1e-6)[0]
    F_grad = B1.T.dot(p_raw)
    F_res = F - F_grad

    # Solve curl flow
    if B2 is not None:
        c_solve = lsqr(B2, F_res, atol=1e-6, btol=1e-6)[0]
        F_curl = B2.dot(c_solve)
    else:
        F_curl = np.zeros(num_e)

    # Solve harmonic flow
    F_harm = F_res - F_curl

    # Compute Norms
    grad_norm = float(np.linalg.norm(F_grad))
    curl_norm = float(np.linalg.norm(F_curl))
    harm_norm = float(np.linalg.norm(F_harm))
    total_norm = float(np.linalg.norm(F_grad + F_curl + F_harm))

    print(f"Triangles found: {t_idx}")
    print(f"Gradient Flow Norm:  {grad_norm:.4f} ({grad_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Curl Flow Norm:      {curl_norm:.4f} ({curl_norm/max(1e-6, total_norm)*100:.1f}%)")
    print(f"Harmonic Flow Norm:  {harm_norm:.4f} ({harm_norm/max(1e-6, total_norm)*100:.1f}%)")

    # Normalize potential field to 0 - 100%
    p_min, p_max = np.min(p_raw), np.max(p_raw)
    p_norm = (p_raw - p_min) / (p_max - p_min) if p_max > p_min else p_raw

    # Compute total trade volume per country for ranking and sizing
    country_volumes = defaultdict(float)
    country_net_balance = defaultdict(float)

    for (u, v), t_val in trade_matrix.items():
        country_volumes[u] += t_val
        country_volumes[v] += t_val
        country_net_balance[u] += t_val  # exports add to balance
        country_net_balance[v] -= t_val  # imports subtract from balance

    # 5. Export JSON site layout files
    export_nodes = []
    for idx, c in enumerate(nodes_metadata):
        iso3 = c["iso3"]
        export_nodes.append({
            "id": iso3,
            "label": iso3,
            "name": c["name"],
            "continent": c["continent"],
            "gdp": c["gdp"],
            "population": c["population"],
            "gdpCapita": c["gdp_capita"],
            "landlocked": c["landlocked"],
            "latitude": c["latitude"],
            "longitude": c["longitude"],
            "potentialNorm": float(p_norm[idx]),
            "tradeVolume": float(country_volumes[iso3]),
            "netTradeBalance": float(country_net_balance[iso3]),
            "documentCount": int(country_volumes[iso3] / 1e5) + 1, # legacy visualizer sizing field
            "mentionCount": int(country_volumes[iso3] / 1e5) + 1  # legacy visualizer sizing field
        })

    export_edges = []
    for idx, (u, v) in enumerate(edges_list):
        export_edges.append({
            "source": u,
            "target": v,
            "documentCount": 1,
            "hodge": {
                "gradient": float(F_grad[idx]),
                "curl": float(F_curl[idx]),
                "harmonic": float(F_harm[idx]),
                "total": float(F[idx])
            }
        })

    # Sort nodes by potential ascending (lowest potential is the source of flow, i.e. regulators/exporters)
    sorted_indices_asc = np.argsort(p_norm)
    top_exporters = []
    for rank, idx in enumerate(sorted_indices_asc[:10], start=1):
        iso3 = all_countries[idx]
        top_exporters.append({
            "rank": rank,
            "iso3": iso3,
            "potential": float(p_norm[idx]),
            "netBalance": float(country_net_balance[iso3])
        })

    top_importers = []
    for rank, idx in enumerate(reversed(sorted_indices_asc[-10:]), start=1):
        iso3 = all_countries[idx]
        top_importers.append({
            "rank": rank,
            "iso3": iso3,
            "potential": float(p_norm[idx]),
            "netBalance": float(country_net_balance[iso3])
        })

    summary_data = {
        "dataset": "WITS 2017 Global Supply Chain Network",
        "counts": {
            "countries": len(nodes_metadata),
            "trade_flows": len(edges_list),
            "triangles": t_idx
        },
        "hodge": {
            "gradientNorm": grad_norm,
            "curlNorm": curl_norm,
            "harmonicNorm": harm_norm,
            "totalNorm": total_norm
        },
        "top_regulators": top_exporters,  # named top_regulators for legacy layout compatibility
        "top_targets": top_importers       # named top_targets for legacy layout compatibility
    }

    # Write files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "nodes.json").open("w", encoding="utf-8") as f:
        json.dump(export_nodes, f, indent=2)
    with (OUTPUT_DIR / "edges.json").open("w", encoding="utf-8") as f:
        json.dump(export_edges, f, indent=2)
    with (OUTPUT_DIR / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"Successfully processed global trade network. Outputs stored in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
