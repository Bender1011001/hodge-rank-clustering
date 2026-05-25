"""
Build compact OpenFlights visualization artifacts for the local site.

The script downloads OpenFlights airport and route snapshots into a temporary
folder, converts directional routes into an asymmetric preference matrix, runs
TrueHodgeRankClustering, writes compact JSON artifacts, and removes the raw
downloads by default.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hodge_rank import TrueHodgeRankClustering


AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
ROUTES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"
LAND_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "hodge-rank-clustering-openflights-demo/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def clean_value(value: str) -> str:
    return "" if value == r"\N" else value


def parse_int(value: str) -> int | None:
    if not value or value == r"\N":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: str) -> float | None:
    if not value or value == r"\N":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_airports(path: Path) -> dict[int, dict]:
    airports: dict[int, dict] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 8:
                continue
            airport_id = parse_int(row[0])
            lat = parse_float(row[6])
            lon = parse_float(row[7])
            if airport_id is None or lat is None or lon is None:
                continue
            code = clean_value(row[4]) or clean_value(row[5]) or f"OF{airport_id}"
            airports[airport_id] = {
                "airport_id": airport_id,
                "name": clean_value(row[1]),
                "city": clean_value(row[2]),
                "country": clean_value(row[3]),
                "code": code,
                "iata": clean_value(row[4]),
                "icao": clean_value(row[5]),
                "lat": lat,
                "lon": lon,
                "altitude_ft": parse_float(row[8]) if len(row) > 8 else None,
            }
    return airports


def load_direct_routes(path: Path, airports: dict[int, dict]) -> Counter[tuple[int, int]]:
    pair_counts: Counter[tuple[int, int]] = Counter()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 8:
                continue
            source_id = parse_int(row[3])
            destination_id = parse_int(row[5])
            stops = parse_int(row[7])
            if (
                source_id is None
                or destination_id is None
                or source_id == destination_id
                or source_id not in airports
                or destination_id not in airports
                or (stops is not None and stops > 0)
            ):
                continue
            pair_counts[(source_id, destination_id)] += 1
    return pair_counts


def haversine_km(a: dict, b: dict) -> float:
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b["lon"] - a["lon"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def build_distance_matrix(
    airport_ids: list[int],
    airports: dict[int, dict],
    pair_counts: Counter[tuple[int, int]],
    inbound: Counter[int],
    outbound: Counter[int],
) -> np.ndarray:
    n = len(airport_ids)
    matrix = np.full((n, n), 100000.0, dtype=float)
    max_in_log = max((math.log1p(inbound[airport_id]) for airport_id in airport_ids), default=1.0)
    max_out_log = max((math.log1p(outbound[airport_id]) for airport_id in airport_ids), default=1.0)

    for i, source_id in enumerate(airport_ids):
        for j, destination_id in enumerate(airport_ids):
            if i == j:
                matrix[i, j] = np.inf
                continue

            direct_count = pair_counts.get((source_id, destination_id), 0)
            if direct_count > 0:
                destination_pull = 1.0 + 0.35 * (math.log1p(inbound[destination_id]) / max_in_log)
                source_reach = 1.0 + 0.10 * (math.log1p(outbound[source_id]) / max_out_log)
                matrix[i, j] = 1.0 / (direct_count * destination_pull * source_reach)
            else:
                # Non-routes remain much worse than direct routes; the distance
                # jitter only gives deterministic ordering when a row has few routes.
                matrix[i, j] = 100000.0 + haversine_km(airports[source_id], airports[destination_id]) / 20000.0
    return matrix


def normalize(values: list[float]) -> dict[str, float]:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    if not finite:
        return {"min": 0.0, "max": 1.0}
    lo = min(finite)
    hi = max(finite)
    if hi == lo:
        hi = lo + 1.0
    return {"min": lo, "max": hi}


def scaled(value: float | None, bounds: dict[str, float]) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return (value - bounds["min"]) / (bounds["max"] - bounds["min"])


def round_coordinates(value, precision: int = 2):
    if isinstance(value, list):
        if value and all(isinstance(item, (int, float)) for item in value):
            return [round(float(item), precision) for item in value[:2]]
        return [round_coordinates(item, precision) for item in value]
    return value


def build_land_artifact(raw_dir: Path, output_root: Path) -> dict:
    land_raw_path = raw_dir / "ne_110m_land.geojson"
    download_file(LAND_URL, land_raw_path)
    land = json.loads(land_raw_path.read_text(encoding="utf-8"))

    processed = {
        "type": "FeatureCollection",
        "name": "Natural Earth 110m land",
        "source": LAND_URL,
        "features": [],
    }

    for feature in land.get("features", []):
        geometry = feature.get("geometry")
        if not geometry or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        processed["features"].append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": geometry["type"],
                    "coordinates": round_coordinates(geometry.get("coordinates", [])),
                },
            }
        )

    land_output_dir = output_root / "world"
    land_output_dir.mkdir(parents=True, exist_ok=True)
    land_output_path = land_output_dir / "land.geojson"
    land_output_path.write_text(json.dumps(processed, separators=(",", ":")), encoding="utf-8")
    return {
        "source": LAND_URL,
        "features": len(processed["features"]),
        "artifact": str(land_output_path),
        "bytes": land_output_path.stat().st_size,
    }


def build_artifacts(args: argparse.Namespace) -> dict:
    raw_dir = (args.raw_dir or ROOT / ".tmp" / f"openflights_raw_{os.getpid()}").resolve()
    output_dir = args.output_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_root = output_dir.parent

    airports_path = raw_dir / "airports.dat"
    routes_path = raw_dir / "routes.dat"

    started = time.perf_counter()
    download_file(AIRPORTS_URL, airports_path)
    download_file(ROUTES_URL, routes_path)

    land_summary = build_land_artifact(raw_dir, output_root)
    airports = load_airports(airports_path)
    pair_counts = load_direct_routes(routes_path, airports)

    inbound: Counter[int] = Counter()
    outbound: Counter[int] = Counter()
    for (source_id, destination_id), count in pair_counts.items():
        outbound[source_id] += count
        inbound[destination_id] += count

    ranked_airports = sorted(
        (airport_id for airport_id in airports if inbound[airport_id] + outbound[airport_id] > 0),
        key=lambda airport_id: (inbound[airport_id] + outbound[airport_id], inbound[airport_id]),
        reverse=True,
    )
    selected_airport_ids = ranked_airports[: args.max_airports]
    selected_set = set(selected_airport_ids)
    selected_index = {airport_id: index for index, airport_id in enumerate(selected_airport_ids)}
    selected_pair_counts = Counter(
        {
            pair: count
            for pair, count in pair_counts.items()
            if pair[0] in selected_set and pair[1] in selected_set and count >= args.min_route_count
        }
    )

    distance_matrix = build_distance_matrix(selected_airport_ids, airports, selected_pair_counts, inbound, outbound)

    model = TrueHodgeRankClustering(k=min(args.k, len(selected_airport_ids) - 1), min_core=args.min_core, tau=args.tau)
    labels = model.fit_predict(D=distance_matrix)

    potential_by_local = {int(core_id): float(model.potential[i]) for i, core_id in enumerate(model.core_nodes)}
    potential_bounds = normalize(list(potential_by_local.values()))
    edge_component_by_pair: dict[tuple[int, int], dict] = {}
    for edge_index, (u, v) in enumerate(model.edges):
        edge_component_by_pair[(int(u), int(v))] = {
            "gradient": float(model.F_grad[edge_index]),
            "curl": float(model.F_curl[edge_index]),
            "harmonic": float(model.F_harm[edge_index]),
        }

    nodes = []
    id_by_airport = {airport_id: str(airport_id) for airport_id in selected_airport_ids}
    for local_id, airport_id in enumerate(selected_airport_ids):
        airport = airports[airport_id]
        potential = potential_by_local.get(local_id)
        nodes.append(
            {
                "id": id_by_airport[airport_id],
                "airportId": airport_id,
                "code": airport["code"],
                "name": airport["name"],
                "city": airport["city"],
                "country": airport["country"],
                "lat": airport["lat"],
                "lon": airport["lon"],
                "inboundRoutes": int(inbound[airport_id]),
                "outboundRoutes": int(outbound[airport_id]),
                "totalRoutes": int(inbound[airport_id] + outbound[airport_id]),
                "cluster": int(labels[local_id]),
                "core": local_id in potential_by_local,
                "potential": potential,
                "potentialNorm": scaled(potential, potential_bounds),
            }
        )

    edge_rows = []
    for (source_id, destination_id), count in selected_pair_counts.most_common(args.max_edges):
        source_local = selected_index[source_id]
        destination_local = selected_index[destination_id]
        undirected = tuple(sorted((source_local, destination_local)))
        source_label = int(labels[source_local])
        destination_label = int(labels[destination_local])
        edge_rows.append(
            {
                "source": id_by_airport[source_id],
                "target": id_by_airport[destination_id],
                "count": int(count),
                "sourceCluster": source_label,
                "targetCluster": destination_label,
                "sameCluster": source_label == destination_label and source_label != -1,
                "hodge": edge_component_by_pair.get(undirected),
            }
        )

    clusters = []
    nodes_by_cluster: dict[int, list[dict]] = defaultdict(list)
    for node in nodes:
        nodes_by_cluster[node["cluster"]].append(node)
    for cluster_id, cluster_nodes in sorted(nodes_by_cluster.items(), key=lambda item: item[0]):
        if cluster_id < 0:
            label = "Unassigned"
        else:
            label = f"Cluster {cluster_id + 1}"
        top_nodes = sorted(cluster_nodes, key=lambda node: node["totalRoutes"], reverse=True)[:8]
        clusters.append(
            {
                "id": cluster_id,
                "label": label,
                "nodeCount": len(cluster_nodes),
                "routeTotal": int(sum(node["totalRoutes"] for node in cluster_nodes)),
                "topAirports": [
                    {
                        "id": node["id"],
                        "code": node["code"],
                        "city": node["city"],
                        "country": node["country"],
                        "totalRoutes": node["totalRoutes"],
                        "potentialNorm": node["potentialNorm"],
                    }
                    for node in top_nodes
                ],
            }
        )

    summary = {
        "dataset": "OpenFlights airport route snapshot",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "airports": AIRPORTS_URL,
            "routes": ROUTES_URL,
            "land": LAND_URL,
            "licenseNote": "OpenFlights data is free to use; keep attribution to OpenFlights and the source URL.",
        },
        "parameters": {
            "maxAirports": args.max_airports,
            "maxEdges": args.max_edges,
            "k": model.k,
            "minCore": args.min_core,
            "tau": args.tau,
            "minRouteCount": args.min_route_count,
        },
        "counts": {
            "rawAirports": len(airports),
            "rawDirectedAirportPairs": len(pair_counts),
            "selectedAirports": len(nodes),
            "visualEdges": len(edge_rows),
            "clusters": len([cluster for cluster in clusters if cluster["id"] >= 0]),
            "coreNodes": int(len(model.core_nodes)),
            "hodgeEdges": int(len(model.edges)),
            "triangles": int(model.num_triangles),
        },
        "hodge": {
            "gradientNorm": float(np.linalg.norm(model.F_grad)),
            "curlNorm": float(np.linalg.norm(model.F_curl)),
            "harmonicNorm": float(np.linalg.norm(model.F_harm)),
        },
        "processingSeconds": round(time.perf_counter() - started, 3),
        "rawDataRetained": bool(args.keep_raw),
        "land": land_summary,
    }

    if not args.keep_raw:
        shutil.rmtree(raw_dir, ignore_errors=True)

    summary["rawDirectory"] = str(raw_dir)
    summary["rawDirectoryExistsAfterRun"] = raw_dir.exists()

    (output_dir / "nodes.json").write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    (output_dir / "edges.json").write_text(json.dumps(edge_rows, indent=2), encoding="utf-8")
    (output_dir / "clusters.json").write_text(json.dumps(clusters, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OpenFlights Hodge clustering site artifacts.")
    parser.add_argument("--max-airports", type=int, default=420)
    parser.add_argument("--max-edges", type=int, default=2200)
    parser.add_argument("--min-route-count", type=int, default=1)
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--min-core", type=int, default=2)
    parser.add_argument("--tau", type=float, default=0.005)
    parser.add_argument("--keep-raw", action="store_true")
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "site" / "data" / "openflights")
    return parser.parse_args()


def main() -> None:
    summary = build_artifacts(parse_args())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
