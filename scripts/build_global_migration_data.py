"""
Build global migration-flow site artifacts with discrete Hodge decomposition.

The migration matrix is the 2010-2015 bilateral migrant-flow sample shipped in
the NSA rank-based-linkage repository. Rows are origin ISO-2 code, destination
ISO-2 code, and estimated flow. The builder converts opposing directed flows
into a net pairwise flow and exports compact JSON for the static atlas.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr


MIGRATION_URL = (
    "https://raw.githubusercontent.com/NationalSecurityAgency/"
    "rank-based-linkage/master/src/main/resources/"
    "migrantFlows2010-15-200countries-originfirst.csv"
)
COORD_URL = "https://gist.githubusercontent.com/tadast/8827699/raw/countries_codes_and_coordinates.csv"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "site" / "data" / "migration"


def fetch_text(url: str) -> str:
    print(f"Fetching {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "hodge-rank-clustering"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def parse_coordinates(csv_text: str) -> dict[str, dict[str, object]]:
    rows = csv.DictReader(io.StringIO(csv_text))
    out: dict[str, dict[str, object]] = {}
    for row in rows:
        clean = {key.strip().strip('"'): value.strip().strip('"') for key, value in row.items()}
        alpha2 = clean.get("Alpha-2 code", "")
        alpha3 = clean.get("Alpha-3 code", "")
        name = clean.get("Country", "")
        lat_raw = clean.get("Latitude (average)", "")
        lon_raw = clean.get("Longitude (average)", "")
        if not alpha2 or not alpha3 or not name:
            continue
        try:
            latitude = float(lat_raw)
            longitude = float(lon_raw)
        except ValueError:
            continue
        out[alpha2] = {
            "alpha2": alpha2,
            "alpha3": alpha3,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
        }
    return out


def parse_flows(csv_text: str) -> dict[tuple[str, str], float]:
    flows: dict[tuple[str, str], float] = defaultdict(float)
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if len(row) < 3:
            continue
        origin = row[0].strip().strip('"')
        destination = row[1].strip().strip('"')
        if not origin or not destination or origin == destination:
            continue
        try:
            flow = float(row[2])
        except ValueError:
            continue
        if flow > 0:
            flows[(origin, destination)] += flow
    return flows


def build_net_edges(
    directed_flows: dict[tuple[str, str], float],
    countries: list[str],
) -> tuple[list[tuple[str, str]], np.ndarray, dict[str, dict[str, float]]]:
    country_set = set(countries)
    pair_seen: set[tuple[str, str]] = set()
    edges: list[tuple[str, str]] = []
    values: list[float] = []
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0})

    for (origin, destination), flow in directed_flows.items():
        if origin not in country_set or destination not in country_set:
            continue
        totals[origin]["outflow"] += flow
        totals[destination]["inflow"] += flow

    for origin, destination in sorted(directed_flows):
        if origin not in country_set or destination not in country_set:
            continue
        pair = tuple(sorted((origin, destination)))
        if pair in pair_seen:
            continue
        pair_seen.add(pair)
        u, v = pair
        net = directed_flows.get((u, v), 0.0) - directed_flows.get((v, u), 0.0)
        if abs(net) > 1e-9:
            edges.append((u, v))
            values.append(net)

    return edges, np.array(values, dtype=float), totals


def hodge_decompose(num_vertices: int, edges: list[tuple[int, int]], flow: np.ndarray) -> dict[str, object]:
    num_edges = len(edges)
    if num_edges == 0:
        zero = np.zeros(0)
        return {
            "gradient": zero,
            "curl": zero,
            "harmonic": zero,
            "potential": np.zeros(num_vertices),
            "gradient_norm": 0.0,
            "curl_norm": 0.0,
            "harmonic_norm": 0.0,
            "total_norm": 0.0,
            "triangles": 0,
        }

    r1: list[int] = []
    c1: list[int] = []
    d1: list[float] = []
    for edge_index, (u, v) in enumerate(edges):
        r1.extend([u, v])
        c1.extend([edge_index, edge_index])
        d1.extend([-1.0, 1.0])
    b1 = sp.csr_matrix((d1, (r1, c1)), shape=(num_vertices, num_edges))

    potential = lsqr(b1.T, flow, atol=1e-6, btol=1e-6)[0]
    gradient = b1.T.dot(potential)
    residual = flow - gradient

    adjacency: dict[int, set[int]] = defaultdict(set)
    edge_to_index: dict[tuple[int, int], int] = {}
    for edge_index, (u, v) in enumerate(edges):
        adjacency[u].add(v)
        adjacency[v].add(u)
        edge_to_index[(min(u, v), max(u, v))] = edge_index

    r2: list[int] = []
    c2: list[int] = []
    d2: list[float] = []
    triangle_index = 0
    for u in range(num_vertices):
        for v in sorted(node for node in adjacency[u] if node > u):
            common = sorted(node for node in adjacency[u].intersection(adjacency[v]) if node > v)
            for w in common:
                e_uv = edge_to_index[(u, v)]
                e_vw = edge_to_index[(v, w)]
                e_uw = edge_to_index[(u, w)]
                r2.extend([e_vw, e_uw, e_uv])
                c2.extend([triangle_index, triangle_index, triangle_index])
                d2.extend([1.0, -1.0, 1.0])
                triangle_index += 1

    if triangle_index:
        b2 = sp.csr_matrix((d2, (r2, c2)), shape=(num_edges, triangle_index))
        curl_coefficients = lsqr(b2, residual, atol=1e-6, btol=1e-6)[0]
        curl = b2.dot(curl_coefficients)
    else:
        curl = np.zeros(num_edges)

    harmonic = residual - curl
    return {
        "gradient": gradient,
        "curl": curl,
        "harmonic": harmonic,
        "potential": potential,
        "gradient_norm": float(np.linalg.norm(gradient)),
        "curl_norm": float(np.linalg.norm(curl)),
        "harmonic_norm": float(np.linalg.norm(harmonic)),
        "total_norm": float(np.linalg.norm(flow)),
        "triangles": triangle_index,
    }


def normalize(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    min_value = float(values.min())
    max_value = float(values.max())
    if max_value <= min_value:
        return np.zeros_like(values)
    return (values - min_value) / (max_value - min_value)


def main() -> None:
    migration_text = fetch_text(MIGRATION_URL)
    coord_text = fetch_text(COORD_URL)
    coords = parse_coordinates(coord_text)
    directed_flows = parse_flows(migration_text)

    codes_in_flows = sorted({code for pair in directed_flows for code in pair})
    missing_coordinates = [code for code in codes_in_flows if code not in coords]
    countries = [code for code in codes_in_flows if code in coords]
    country_to_index = {code: index for index, code in enumerate(countries)}

    net_edges_codes, net_flow, totals = build_net_edges(directed_flows, countries)
    indexed_edges = [(country_to_index[u], country_to_index[v]) for u, v in net_edges_codes]

    print(f"Countries with coordinates: {len(countries)}")
    print(f"Directed source rows: {len(directed_flows)}")
    print(f"Net migration edges: {len(indexed_edges)}")
    if missing_coordinates:
        print(f"Missing coordinates for {len(missing_coordinates)} codes: {', '.join(missing_coordinates)}")

    hodge = hodge_decompose(len(countries), indexed_edges, net_flow)
    potential_norm = normalize(np.asarray(hodge["potential"], dtype=float))
    gradient = np.asarray(hodge["gradient"], dtype=float)
    curl = np.asarray(hodge["curl"], dtype=float)
    harmonic = np.asarray(hodge["harmonic"], dtype=float)

    nodes = []
    for code, index in country_to_index.items():
        meta = coords[code]
        inflow = totals[code]["inflow"]
        outflow = totals[code]["outflow"]
        nodes.append(
            {
                "id": code,
                "label": code,
                "alpha3": meta["alpha3"],
                "name": meta["name"],
                "latitude": meta["latitude"],
                "longitude": meta["longitude"],
                "potentialNorm": float(potential_norm[index]),
                "migrationInflow": float(inflow),
                "migrationOutflow": float(outflow),
                "netMigrationBalance": float(inflow - outflow),
                "migrationVolume": float(inflow + outflow),
                "documentCount": int((inflow + outflow) / 1000.0) + 1,
                "mentionCount": int((inflow + outflow) / 1000.0) + 1,
            }
        )

    edge_order = sorted(range(len(net_edges_codes)), key=lambda i: abs(net_flow[i]), reverse=True)
    export_edges = []
    for edge_index in edge_order:
        source, target = net_edges_codes[edge_index]
        export_edges.append(
            {
                "source": source,
                "target": target,
                "netFlow": float(net_flow[edge_index]),
                "absNetFlow": float(abs(net_flow[edge_index])),
                "documentCount": 1,
                "hodge": {
                    "gradient": float(gradient[edge_index]),
                    "curl": float(curl[edge_index]),
                    "harmonic": float(harmonic[edge_index]),
                    "total": float(net_flow[edge_index]),
                },
            }
        )

    source_order = np.argsort(potential_norm)
    top_origins = []
    for rank, index in enumerate(source_order[:10], start=1):
        code = countries[int(index)]
        top_origins.append(
            {
                "rank": rank,
                "iso2": code,
                "name": coords[code]["name"],
                "potential": float(potential_norm[index]),
                "netMigrationBalance": float(totals[code]["inflow"] - totals[code]["outflow"]),
            }
        )

    top_destinations = []
    for rank, index in enumerate(reversed(source_order[-10:]), start=1):
        code = countries[int(index)]
        top_destinations.append(
            {
                "rank": rank,
                "iso2": code,
                "name": coords[code]["name"],
                "potential": float(potential_norm[index]),
                "netMigrationBalance": float(totals[code]["inflow"] - totals[code]["outflow"]),
            }
        )

    summary = {
        "dataset": "Global bilateral migrant flows, 2010-2015",
        "sources": {
            "migration": MIGRATION_URL,
            "coordinates": COORD_URL,
            "upstream_project": "NationalSecurityAgency/rank-based-linkage",
        },
        "counts": {
            "countries": len(countries),
            "directed_flows": len(directed_flows),
            "net_flows": len(net_edges_codes),
            "triangles": int(hodge["triangles"]),
            "missing_coordinate_codes": len(missing_coordinates),
        },
        "hodge": {
            "gradientNorm": hodge["gradient_norm"],
            "curlNorm": hodge["curl_norm"],
            "harmonicNorm": hodge["harmonic_norm"],
            "totalNorm": hodge["total_norm"],
        },
        "top_origins": top_origins,
        "top_destinations": top_destinations,
        "missing_coordinate_codes": missing_coordinates,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "nodes.json").write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "edges.json").write_text(json.dumps(export_edges, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved migration artifacts to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
