import sys
import csv
import synapseclient
from pathlib import Path
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.synapse_auth import login_synapse
syn = login_synapse()

tmp_dir = ROOT / ".tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

NETS = {
    1: {"name": "in-silico", "gold": "syn2787240"},
    3: {"name": "ecoli", "gold": "syn2787243"},
    4: {"name": "yeast", "gold": "syn2787244"}
}

for net_num, info in NETS.items():
    gold_file = syn.get(info["gold"], downloadLocation=str(tmp_dir))
    
    # Simple parse to count nodes and construct DiGraph
    G = nx.DiGraph()
    with open(gold_file.path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or len(row) < 3:
                continue
            if row[2].strip() == "1":
                G.add_edge(row[0].strip(), row[1].strip())
                
    Path(gold_file.path).unlink()
    
    is_dag = nx.is_directed_acyclic_graph(G)
    cycles = list(nx.simple_cycles(G))
    print(f"Network {net_num} ({info['name']}): is_dag={is_dag} | Simple cycles count={len(cycles)}")
    if cycles:
        print(f"  Example cycles: {cycles[:5]}")
