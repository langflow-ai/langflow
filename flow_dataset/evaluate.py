#!/usr/bin/env python3
"""
Evaluate generated flows vs originals.
Reads from dataset.json and generated_flows/, produces evaluation results.
This script is meant to be called with a range of indices to evaluate.
"""

import json
import sys
import os
from pathlib import Path

def simplify_flow(flow):
    """Extract simplified structure for comparison."""
    nodes = flow.get("data", {}).get("nodes", [])
    edges = flow.get("data", {}).get("edges", [])

    node_summary = []
    for n in nodes:
        nd = n.get("data", {})
        ntype = nd.get("type", "")
        if ntype in ("note", "undefined", ""):
            continue
        node_summary.append({
            "type": ntype,
            "display_name": nd.get("display_name", ntype),
        })

    edge_summary = []
    for e in edges:
        src = e.get("data", {}).get("sourceHandle", {})
        tgt = e.get("data", {}).get("targetHandle", {})
        edge_summary.append({
            "from_type": src.get("dataType", "?"),
            "from_output": src.get("name", "?"),
            "to_field": tgt.get("fieldName", "?"),
        })

    return {
        "name": flow.get("name", ""),
        "description": flow.get("description", ""),
        "nodes": node_summary,
        "edges": edge_summary,
        "node_count": len(node_summary),
        "edge_count": len(edge_summary),
    }


def evaluate_pair(original, generated, name):
    """Programmatic evaluation of generated flow vs original."""
    orig = simplify_flow(original)
    gen = simplify_flow(generated)

    # 1. Structure score: compare node types
    orig_types = sorted([n["type"] for n in orig["nodes"]])
    gen_types = sorted([n["type"] for n in gen["nodes"]])

    # Count matching types
    orig_type_counts = {}
    for t in orig_types:
        orig_type_counts[t] = orig_type_counts.get(t, 0) + 1
    gen_type_counts = {}
    for t in gen_types:
        gen_type_counts[t] = gen_type_counts.get(t, 0) + 1

    all_types = set(list(orig_type_counts.keys()) + list(gen_type_counts.keys()))
    type_matches = 0
    type_total = 0
    for t in all_types:
        o = orig_type_counts.get(t, 0)
        g = gen_type_counts.get(t, 0)
        type_matches += min(o, g)
        type_total += max(o, g)

    structure_score = (type_matches / type_total * 10) if type_total > 0 else 0

    # 2. Connections score: compare edge patterns
    orig_edges = sorted([(e["from_type"], e["from_output"], e["to_field"]) for e in orig["edges"]])
    gen_edges = sorted([(e["from_type"], e["from_output"], e["to_field"]) for e in gen["edges"]])

    edge_matches = 0
    gen_edges_remaining = list(gen_edges)
    for oe in orig_edges:
        if oe in gen_edges_remaining:
            edge_matches += 1
            gen_edges_remaining.remove(oe)

    edge_total = max(len(orig_edges), len(gen_edges))
    connections_score = (edge_matches / edge_total * 10) if edge_total > 0 else 0

    # 3. Completeness score: are all original node types present?
    missing_types = []
    for t in all_types:
        if orig_type_counts.get(t, 0) > gen_type_counts.get(t, 0):
            missing_types.append(t)
    extra_types = []
    for t in all_types:
        if gen_type_counts.get(t, 0) > orig_type_counts.get(t, 0):
            extra_types.append(t)

    completeness = 1.0 - (len(missing_types) / len(all_types)) if all_types else 1.0
    completeness_score = completeness * 10

    # 4. Correctness score: node count match + edge count match + has I/O
    node_count_diff = abs(orig["node_count"] - gen["node_count"])
    edge_count_diff = abs(orig["edge_count"] - gen["edge_count"])

    has_input = any(n["type"] in ("ChatInput", "TextInput") for n in gen["nodes"])
    has_output = any(n["type"] in ("ChatOutput", "TextOutput") for n in gen["nodes"])

    correctness = 10.0
    correctness -= min(node_count_diff * 1.0, 3.0)  # penalty for wrong node count
    correctness -= min(edge_count_diff * 0.8, 3.0)   # penalty for wrong edge count
    if not has_input:
        correctness -= 2.0
    if not has_output:
        correctness -= 2.0
    correctness_score = max(0, correctness)

    # Overall weighted average
    overall_score = round(
        structure_score * 0.3 +
        connections_score * 0.3 +
        completeness_score * 0.2 +
        correctness_score * 0.2, 1
    )

    notes_parts = []
    if missing_types:
        notes_parts.append("Missing: {}".format(", ".join(missing_types)))
    if extra_types:
        notes_parts.append("Extra: {}".format(", ".join(extra_types)))
    if node_count_diff > 0:
        notes_parts.append("Node count diff: {}".format(node_count_diff))
    if edge_count_diff > 0:
        notes_parts.append("Edge count diff: {}".format(edge_count_diff))

    return {
        "structure_score": round(structure_score, 1),
        "connections_score": round(connections_score, 1),
        "completeness_score": round(completeness_score, 1),
        "correctness_score": round(correctness_score, 1),
        "overall_score": overall_score,
        "notes": "; ".join(notes_parts) if notes_parts else "Perfect match",
        "orig_nodes": orig_types,
        "gen_nodes": gen_types,
    }


if __name__ == "__main__":
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    gen_dir = os.path.join(os.path.dirname(__file__), "generated_flows")

    with open(dataset_path) as f:
        dataset = json.load(f)

    # Only evaluate the first 33 (starter projects that we generated)
    dataset = dataset[:33]

    evaluations = []

    for i, entry in enumerate(dataset):
        name = entry["name"]

        # Try to find generated file (handle different naming conventions)
        gen_path = None
        # Normalize name for file matching
        name_normalized = name.lower().replace(" ", "_").replace("&", "and").replace("é", "e")
        for candidate in [
            os.path.join(gen_dir, "{}.json".format(name)),
            os.path.join(gen_dir, "{}.json".format(name_normalized)),
        ]:
            if os.path.exists(candidate):
                gen_path = candidate
                break

        if not gen_path:
            # Try fuzzy match
            gen_files = os.listdir(gen_dir)
            for gf in gen_files:
                gf_norm = gf.lower().replace(" ", "").replace("_", "").replace("-", "")
                name_norm = name.lower().replace(" ", "").replace("_", "").replace("-", "").replace("&", "and").replace("é", "e")
                if name_norm in gf_norm or gf_norm.replace(".json", "") in name_norm:
                    gen_path = os.path.join(gen_dir, gf)
                    break

        if not gen_path:
            print("[{}/{}] {}: NOT FOUND".format(i+1, len(dataset), name))
            evaluations.append({
                "name": name,
                "description": entry["description"],
                "original_nodes": entry["node_count"],
                "original_edges": entry["edge_count"],
                "generated": False,
                "structure_score": 0,
                "connections_score": 0,
                "completeness_score": 0,
                "correctness_score": 0,
                "overall_score": 0,
                "notes": "Generated flow file not found",
            })
            continue

        with open(gen_path) as f:
            generated = json.load(f)

        result = evaluate_pair(entry["original_flow"], generated, name)

        print("[{}/{}] {}: overall={} (struct={}, conn={}, compl={}, corr={})".format(
            i+1, len(dataset), name,
            result["overall_score"], result["structure_score"],
            result["connections_score"], result["completeness_score"],
            result["correctness_score"]
        ))

        evaluations.append({
            "name": name,
            "description": entry["description"],
            "original_nodes": entry["node_count"],
            "original_edges": entry["edge_count"],
            "generated": True,
            "structure_score": result["structure_score"],
            "connections_score": result["connections_score"],
            "completeness_score": result["completeness_score"],
            "correctness_score": result["correctness_score"],
            "overall_score": result["overall_score"],
            "notes": result["notes"],
        })

    # Save results
    eval_path = os.path.join(os.path.dirname(__file__), "evaluation.json")
    with open(eval_path, "w") as f:
        json.dump(evaluations, f, indent=2, ensure_ascii=False)

    # CSV
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), "evaluation.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "description", "original_nodes", "original_edges",
            "generated", "structure_score", "connections_score",
            "completeness_score", "correctness_score", "overall_score", "notes",
        ])
        writer.writeheader()
        writer.writerows(evaluations)

    # Print table
    print("\n" + "=" * 130)
    print("{:<35} {:>5} {:>5} {:>4} {:>7} {:>7} {:>7} {:>7} {:>8}".format(
        "Flow Name", "Nodes", "Edges", "Gen", "Struct", "Conn", "Compl", "Corr", "Overall"))
    print("-" * 130)

    total = 0
    count = 0
    for e in evaluations:
        gen = "Y" if e["generated"] else "N"
        print("{:<35} {:>5} {:>5} {:>4} {:>7} {:>7} {:>7} {:>7} {:>8}".format(
            e["name"][:35], e["original_nodes"], e["original_edges"],
            gen, e["structure_score"], e["connections_score"],
            e["completeness_score"], e["correctness_score"], e["overall_score"]
        ))
        if e["generated"]:
            total += e["overall_score"]
            count += 1

    print("-" * 130)
    avg = total / count if count else 0
    print("{:<35} {:>5} {:>5} {:>4} {:>7} {:>7} {:>7} {:>7} {:>8.1f}".format(
        "AVERAGE", "", "", str(count), "", "", "", "", avg))
    print("=" * 130)

    print("\nSaved: {} and {}".format(eval_path, csv_path))
