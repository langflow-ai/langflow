#!/usr/bin/env python3
"""Test script to demonstrate workflow payload optimization."""

import json
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src" / "backend" / "base"))

from langflow.api.v1.workflow_edit_tools import _optimize_workflow_payload


def analyze_payload(payload: dict, name: str) -> dict:
    """Analyze payload size and token count."""
    json_str = json.dumps(payload, indent=2)
    size_bytes = len(json_str.encode("utf-8"))
    size_kb = size_bytes / 1024

    # Rough token estimation (1 token ≈ 4 characters)
    estimated_tokens = len(json_str) / 4

    return {
        "name": name,
        "size_bytes": size_bytes,
        "size_kb": round(size_kb, 2),
        "estimated_tokens": int(estimated_tokens),
        "json_length": len(json_str),
    }


def main():
    # Load the Simple Agent workflow
    workflow_file = Path(__file__).parent / "Simple Agent.json"

    if not workflow_file.exists():
        print(f"❌ Workflow file not found: {workflow_file}")
        return

    with open(workflow_file) as f:
        full_data = json.load(f)

    # Extract payload
    payload = full_data.get("data", {})

    # Analyze original
    original_stats = analyze_payload(payload, "Original Payload")

    # Optimize without code
    optimized_no_code = _optimize_workflow_payload(payload, include_code=False)
    optimized_no_code_stats = analyze_payload(optimized_no_code, "Optimized (no code)")

    # Optimize with code
    optimized_with_code = _optimize_workflow_payload(payload, include_code=True)
    optimized_with_code_stats = analyze_payload(optimized_with_code, "Optimized (with code)")

    # Print results
    print("\n" + "=" * 70)
    print("📊 WORKFLOW PAYLOAD OPTIMIZATION ANALYSIS")
    print("=" * 70)

    print(f"\n📁 File: {workflow_file.name}")
    print(f"🔢 Nodes: {len(payload.get('nodes', []))}")
    print(f"🔗 Edges: {len(payload.get('edges', []))}")

    print("\n" + "-" * 70)
    print(f"{'Metric':<30} {'Original':<15} {'Optimized':<15} {'Reduction':<15}")
    print("-" * 70)

    for metric in ["size_kb", "estimated_tokens"]:
        orig_val = original_stats[metric]
        opt_val = optimized_no_code_stats[metric]
        reduction = ((orig_val - opt_val) / orig_val) * 100

        unit = "KB" if metric == "size_kb" else "tokens"

        print(
            f"{metric.replace('_', ' ').title():<30} "
            f"{orig_val:>10} {unit:<4} "
            f"{opt_val:>10} {unit:<4} "
            f"{reduction:>8.1f}% ⬇️"
        )

    print("-" * 70)

    # Show what was removed
    print("\n🗑️  Removed fields (per node):")
    print("   • code (source code - hundreds of lines)")
    print("   • file_path, fileTypes, load_from_db")
    print("   • placeholder, password, title_case")
    print("   • curl, endpoint (generated fields)")
    print("   • Large string values (>500 chars)")
    print("   • Long info texts (>200 chars)")

    print("\n✅ Kept fields (per node):")
    print("   • Node ID, type, position")
    print("   • Display name, description")
    print("   • All field names and types")
    print("   • Input/output types (for validation)")
    print("   • Required, advanced, show flags")
    print("   • Short values and info texts")
    print("   • Full edges array (connections)")

    print("\n💡 Recommendations:")
    print(
        f"   • Use include_code=false (default) - saves {original_stats['estimated_tokens'] - optimized_no_code_stats['estimated_tokens']:,} tokens"
    )
    print("   • Only set include_code=true when inspecting implementation")
    print(
        f"   • Token savings: ~{((original_stats['estimated_tokens'] - optimized_no_code_stats['estimated_tokens']) / original_stats['estimated_tokens']) * 100:.0f}% per workflow GET"
    )

    print("\n" + "=" * 70 + "\n")

    # Save samples
    samples_dir = Path(__file__).parent / "optimization_samples"
    samples_dir.mkdir(exist_ok=True)

    with open(samples_dir / "original.json", "w") as f:
        json.dump(payload, f, indent=2)

    with open(samples_dir / "optimized_no_code.json", "w") as f:
        json.dump(optimized_no_code, f, indent=2)

    with open(samples_dir / "optimized_with_code.json", "w") as f:
        json.dump(optimized_with_code, f, indent=2)

    print(f"📁 Sample files saved to: {samples_dir}")
    print("   • original.json")
    print("   • optimized_no_code.json")
    print("   • optimized_with_code.json")


if __name__ == "__main__":
    main()
