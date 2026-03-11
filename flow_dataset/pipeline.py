#!/usr/bin/env python3
"""
Langflow Flow Creation Dataset Pipeline

1. Build dataset from starter projects (instruction + flow JSON)
2. Use Claude API to generate flows from instructions
3. Evaluate generated flows vs originals
4. Output final evaluation table
"""

from __future__ import annotations

import json
import glob
import os
import sys
import time
import uuid
import csv
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    print("Installing anthropic SDK...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

# Paths
STARTER_PROJECTS_DIR = Path(__file__).parent.parent / "src/backend/base/langflow/initial_setup/starter_projects"
INSTRUCTIONS_MD = Path(__file__).parent / "flow_creation_instructions.md"
DATASET_FILE = Path(__file__).parent / "dataset.json"
GENERATED_DIR = Path(__file__).parent / "generated_flows"
EVALUATION_FILE = Path(__file__).parent / "evaluation.json"
EVALUATION_CSV = Path(__file__).parent / "evaluation.csv"


def build_dataset():
    """Step 1: Build dataset from starter project JSON files."""
    print("\n=== STEP 1: Building Dataset ===\n")
    dataset = []

    json_files = sorted(glob.glob(str(STARTER_PROJECTS_DIR / "*.json")))
    print(f"Found {len(json_files)} starter project JSON files")

    for filepath in json_files:
        with open(filepath) as f:
            flow = json.load(f)

        name = flow.get("name", Path(filepath).stem)
        description = flow.get("description", "")
        tags = flow.get("tags", [])

        # Extract node summary for richer instruction
        nodes = flow.get("data", {}).get("nodes", [])
        node_types = []
        for n in nodes:
            nd = n.get("data", {})
            ntype = nd.get("type", "")
            display = nd.get("display_name", ntype)
            if ntype and ntype not in ("note", "undefined"):
                node_types.append(display)

        edges = flow.get("data", {}).get("edges", [])

        # Build instruction (what we'd tell the agent)
        instruction = f"Create a Langflow flow called '{name}'.\n"
        instruction += f"Description: {description}\n"
        if tags:
            instruction += f"Tags: {', '.join(tags)}\n"
        instruction += f"\nThe flow should use approximately {len(node_types)} components "
        instruction += f"and {len(edges)} connections.\n"
        instruction += f"Components to use: {', '.join(node_types)}\n"

        dataset.append({
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "instruction": instruction,
            "description": description,
            "tags": tags,
            "node_count": len(node_types),
            "edge_count": len(edges),
            "node_types": node_types,
            "original_flow": flow,
            "source_file": Path(filepath).name,
        })

    # Save dataset
    with open(DATASET_FILE, "w") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Dataset saved: {len(dataset)} entries -> {DATASET_FILE}")
    return dataset


def generate_flow(client, instruction: str, instructions_md: str) -> dict | None:
    """Step 2: Use Claude to generate a flow JSON from an instruction."""
    prompt = f"""You are a Langflow flow builder. Follow these instructions precisely:

{instructions_md}

---

Now, create the following flow:

{instruction}

Return ONLY valid JSON. No markdown, no explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Clean up potential markdown wrapping
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3].strip()

        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        # Try to extract JSON from response
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


def evaluate_flow(client, original: dict, generated: dict, name: str) -> dict:
    """Step 3: Use Claude to evaluate generated flow vs original."""
    # Prepare simplified versions for comparison
    def simplify_flow(flow):
        nodes = flow.get("data", {}).get("nodes", [])
        edges = flow.get("data", {}).get("edges", [])
        node_summary = []
        for n in nodes:
            nd = n.get("data", {})
            if nd.get("type") in ("note", "undefined", ""):
                continue
            node_summary.append({
                "type": nd.get("type"),
                "display_name": nd.get("display_name"),
                "id": nd.get("id"),
            })
        edge_summary = []
        for e in edges:
            src = e.get("data", {}).get("sourceHandle", {})
            tgt = e.get("data", {}).get("targetHandle", {})
            edge_summary.append({
                "from": f"{src.get('dataType', '?')}.{src.get('name', '?')}",
                "to": f"{tgt.get('id', '?').split('-')[0] if '-' in str(tgt.get('id','')) else tgt.get('id','?')}.{tgt.get('fieldName', '?')}",
            })
        return {"nodes": node_summary, "edges": edge_summary, "name": flow.get("name", "")}

    orig_simple = simplify_flow(original)
    gen_simple = simplify_flow(generated)

    prompt = f"""You are evaluating a generated Langflow flow against the original.

Flow: "{name}"

## Original Flow
{json.dumps(orig_simple, indent=2)}

## Generated Flow
{json.dumps(gen_simple, indent=2)}

Evaluate the generated flow on these criteria (0-10 each):

1. **structure_score**: Does it have the right components/node types? (exact types matter)
2. **connections_score**: Are the edges/connections correct? (right outputs to right inputs)
3. **completeness_score**: Does it include all necessary components? (nothing missing)
4. **correctness_score**: Would this flow actually work in Langflow? (valid connections, proper I/O)
5. **overall_score**: Overall quality as a weighted average

Return ONLY a JSON object like:
{{
  "structure_score": 8,
  "connections_score": 7,
  "completeness_score": 9,
  "correctness_score": 6,
  "overall_score": 7.5,
  "notes": "Brief explanation of issues found"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3].strip()
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception as e:
        print(f"  Evaluation error: {e}")
        return {
            "structure_score": 0,
            "connections_score": 0,
            "completeness_score": 0,
            "correctness_score": 0,
            "overall_score": 0,
            "notes": f"Evaluation failed: {e}",
        }


def run_pipeline(limit: int | None = None):
    """Run the complete pipeline."""
    # Step 1: Build dataset
    dataset = build_dataset()

    if limit:
        dataset = dataset[:limit]
        print(f"\nLimiting to {limit} flows for testing")

    # Load instructions
    with open(INSTRUCTIONS_MD) as f:
        instructions_md = f.read()

    # Initialize Claude client
    client = anthropic.Anthropic()

    # Create output directory
    GENERATED_DIR.mkdir(exist_ok=True)

    # Step 2: Generate flows
    print(f"\n=== STEP 2: Generating {len(dataset)} Flows ===\n")
    results = []

    for i, entry in enumerate(dataset):
        name = entry["name"]
        print(f"[{i+1}/{len(dataset)}] Generating: {name}...", end=" ", flush=True)

        generated = generate_flow(client, entry["instruction"], instructions_md)

        if generated:
            # Save generated flow
            gen_path = GENERATED_DIR / f"{name}.json"
            with open(gen_path, "w") as f:
                json.dump(generated, f, indent=2)
            print("OK")
        else:
            print("FAILED")

        results.append({
            "id": entry["id"],
            "name": name,
            "instruction": entry["instruction"],
            "description": entry["description"],
            "original_nodes": entry["node_count"],
            "original_edges": entry["edge_count"],
            "generated": generated is not None,
            "generated_flow": generated,
        })

        # Small delay to avoid rate limiting
        if i < len(dataset) - 1:
            time.sleep(1)

    # Step 3: Evaluate
    print(f"\n=== STEP 3: Evaluating {len(results)} Flows ===\n")
    evaluations = []

    for i, result in enumerate(results):
        name = result["name"]
        print(f"[{i+1}/{len(results)}] Evaluating: {name}...", end=" ", flush=True)

        if not result["generated"]:
            eval_result = {
                "structure_score": 0,
                "connections_score": 0,
                "completeness_score": 0,
                "correctness_score": 0,
                "overall_score": 0,
                "notes": "Generation failed",
            }
        else:
            original = dataset[i]["original_flow"]
            eval_result = evaluate_flow(client, original, result["generated_flow"], name)

        print(f"Score: {eval_result.get('overall_score', 'N/A')}")

        evaluations.append({
            "name": name,
            "description": result["description"],
            "original_nodes": result["original_nodes"],
            "original_edges": result["original_edges"],
            "generated": result["generated"],
            **eval_result,
        })

        if i < len(results) - 1:
            time.sleep(1)

    # Step 4: Save results
    print("\n=== STEP 4: Saving Results ===\n")

    with open(EVALUATION_FILE, "w") as f:
        json.dump(evaluations, f, indent=2, ensure_ascii=False)

    # CSV table
    with open(EVALUATION_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "description", "original_nodes", "original_edges",
            "generated", "structure_score", "connections_score",
            "completeness_score", "correctness_score", "overall_score", "notes",
        ])
        writer.writeheader()
        writer.writerows(evaluations)

    # Print summary table
    print("\n" + "=" * 120)
    print(f"{'Flow Name':<35} {'Nodes':>5} {'Edges':>5} {'Gen':>4} {'Struct':>6} {'Conn':>6} {'Compl':>6} {'Corr':>6} {'Overall':>7}")
    print("-" * 120)

    total_score = 0
    count = 0
    for e in evaluations:
        gen_mark = "Y" if e["generated"] else "N"
        print(
            f"{e['name']:<35} {e['original_nodes']:>5} {e['original_edges']:>5} "
            f"{gen_mark:>4} {e['structure_score']:>6} {e['connections_score']:>6} "
            f"{e['completeness_score']:>6} {e['correctness_score']:>6} {e['overall_score']:>7}"
        )
        if e["generated"]:
            total_score += e["overall_score"]
            count += 1

    print("-" * 120)
    avg = total_score / count if count else 0
    print(f"{'AVERAGE':.<35} {'':>5} {'':>5} {count:>4} {'':>6} {'':>6} {'':>6} {'':>6} {avg:>7.1f}")
    print("=" * 120)

    print(f"\nFiles saved:")
    print(f"  Dataset:     {DATASET_FILE}")
    print(f"  Generated:   {GENERATED_DIR}/")
    print(f"  Evaluation:  {EVALUATION_FILE}")
    print(f"  CSV:         {EVALUATION_CSV}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Langflow Flow Creation Pipeline")
    parser.add_argument("--limit", type=int, help="Limit number of flows to process")
    parser.add_argument("--step", choices=["dataset", "generate", "evaluate", "all"], default="all")
    args = parser.parse_args()

    if args.step == "dataset":
        build_dataset()
    else:
        run_pipeline(limit=args.limit)
