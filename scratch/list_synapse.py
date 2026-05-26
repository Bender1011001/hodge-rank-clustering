import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.synapse_auth import login_synapse

syn = login_synapse()

def list_recursive(parent_id, depth=0, max_depth=3):
    if depth > max_depth:
        return
    indent = "  " * depth
    try:
        children = syn.getChildren(parent_id)
        for child in children:
            print(f"{indent}Name: {child['name']} | ID: {child['id']} | Type: {child['type']}")
            if child['type'] == "org.sagebionetworks.repo.model.Folder":
                list_recursive(child['id'], depth + 1, max_depth)
    except Exception as e:
        print(f"{indent}Error listing {parent_id}: {e}")

list_recursive("syn2787211")
