"""
Evaluate predicted canonical flows against ground truth.
Loads predictions from predicted_canonicals/*.json,
compares against canonical_dataset.json labels.
"""

import json
import os
from collections import Counter
from canonical import flow_to_canonical, text_to_canonical, normalize_canonical, normalize_type


def load_predictions():
    """Load all prediction files."""
    preds = {}
    pred_dir = "predicted_canonicals"
    if not os.path.isdir(pred_dir):
        return preds
    for fname in sorted(os.listdir(pred_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(pred_dir, fname)) as f:
            batch = json.load(f)
        for item in batch:
            preds[item["name"]] = item["predicted_canonical_text"]
    return preds


def evaluate(pred_text, label_canonical):
    """Compare predicted canonical text against label canonical."""
    try:
        pred_c = text_to_canonical(pred_text)
        # Normalize component type names
        for n in pred_c["nodes"]:
            n["type"] = normalize_type(n["type"])
    except Exception as e:
        return {"error": str(e), "struct": 0, "conn": 0, "overall": 0}

    # Node comparison by type
    pred_types = Counter(n["type"] for n in pred_c["nodes"])
    label_types = Counter(n["type"] for n in label_canonical["nodes"])

    all_types = set(list(pred_types.keys()) + list(label_types.keys()))
    type_matches = sum(min(pred_types.get(t, 0), label_types.get(t, 0)) for t in all_types)
    type_total = max(sum(pred_types.values()), sum(label_types.values()))
    struct_score = (type_matches / type_total * 10) if type_total > 0 else 10

    # Edge comparison by (src_type, tgt_type, conn)
    def typed_edges(c):
        types = {n["id"]: n["type"] for n in c["nodes"]}
        return [(types.get(e["from"], "?"), types.get(e["to"], "?"), e["conn"]) for e in c["edges"]]

    pred_edges = typed_edges(pred_c)
    label_edges = typed_edges(label_canonical)

    # Also compare with normalization (pattern equivalence)
    pred_norm = normalize_canonical(pred_c)
    label_norm = normalize_canonical(label_canonical)
    pred_edges_norm = typed_edges(pred_norm)
    label_edges_norm = typed_edges(label_norm)

    # Match edges (allowing duplicates)
    label_remaining = list(label_edges_norm)
    matched = 0
    for pe in pred_edges_norm:
        if pe in label_remaining:
            matched += 1
            label_remaining.remove(pe)

    total = max(len(pred_edges_norm), len(label_edges_norm))
    conn_score = (matched / total * 10) if total > 0 else 10

    overall = struct_score * 0.3 + conn_score * 0.7

    return {
        "struct": round(struct_score, 1),
        "conn": round(conn_score, 1),
        "overall": round(overall, 1),
        "matched_edges": matched,
        "total_edges": total,
        "pred_nodes": sum(pred_types.values()),
        "label_nodes": sum(label_types.values()),
    }


if __name__ == "__main__":
    with open("canonical_dataset.json") as f:
        labels = json.load(f)

    label_map = {item["name"]: item["canonical"] for item in labels}
    preds = load_predictions()

    if not preds:
        print("No predictions found in predicted_canonicals/")
        exit(1)

    results = []
    print("{:<40} {:>6} {:>6} {:>8} {:>7}".format("Flow", "Struct", "Conn", "Overall", "Edges"))
    print("-" * 73)

    for name in sorted(preds.keys()):
        if name not in label_map:
            print("{:<40} LABEL NOT FOUND".format(name))
            continue

        r = evaluate(preds[name], label_map[name])
        r["name"] = name
        results.append(r)

        print("{:<40} {:>6.1f} {:>6.1f} {:>8.1f} {:>3}/{:<3}".format(
            name[:39], r["struct"], r["conn"], r["overall"],
            r["matched_edges"], r["total_edges"]))

    if results:
        avg_s = sum(r["struct"] for r in results) / len(results)
        avg_c = sum(r["conn"] for r in results) / len(results)
        avg_o = sum(r["overall"] for r in results) / len(results)
        print("-" * 73)
        print("{:<40} {:>6.1f} {:>6.1f} {:>8.1f}".format(
            "AVERAGE ({} flows)".format(len(results)), avg_s, avg_c, avg_o))

        perfect = sum(1 for r in results if r["conn"] >= 10.0)
        good = sum(1 for r in results if r["conn"] >= 8.0)
        print("\nPerfect: {}/{}  Good(>=8): {}/{}".format(
            perfect, len(results), good, len(results)))
