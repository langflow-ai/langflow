"""Script to fix the Vector Store RAG.json file."""

import json
from pathlib import Path

file_path = "src/backend/base/langflow/initial_setup/starter_projects/Vector Store RAG.json"


def fix_json_file(file_path):
    """Fixes the Vector Store RAG.json file by removing the parser node and specific AstraDB fields."""
    with Path(file_path).open("r+") as f:
        data = json.load(f)

    # Remove parser-YIJGN node
    if "data" in data and "nodes" in data["data"]:
        data["data"]["nodes"] = [node for node in data["data"]["nodes"] if node.get("id") != "parser-YIJGN"]

    # Remove edges connected to parser-YIJGN
    if "data" in data and "edges" in data["data"]:
        data["data"]["edges"] = [
            edge
            for edge in data["data"]["edges"]
            if edge.get("source") != "parser-YIJGN" and edge.get("target") != "parser-YIJGN"
        ]

    # Modify AstraDB nodes
    if "data" in data and "nodes" in data["data"]:
        for node in data["data"]["nodes"]:
            if (
                node.get("data")
                and node["data"].get("type") == "AstraDB"
                and "node" in node["data"]
                and "template" in node["data"]["node"]
            ):
                template = node["data"]["node"]["template"]
                for key in ["password", "token", "keyspace", "secure_connect_bundle"]:
                    if key in template:
                        del template[key]

    with Path(file_path).open("w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    fix_json_file(file_path)
