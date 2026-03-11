#!/Users/rodrigonader/Documents/langflow_exp/.venv/bin/python
"""
Langflow Flow Generator MCP Server

Generates Langflow flow JSON via a 2-stage pipeline:
1. LLM predicts compact canonical form (nodes + typed edges)
2. Deterministic hydrator converts canonical → full importable JSON
"""

import json
import os
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp[cli]"])
    from mcp.server.fastmcp import FastMCP

try:
    import anthropic
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from canonical import text_to_canonical, normalize_type
from hydrator import hydrate, COMP_SPECS


def load_file(name):
    path = SCRIPT_DIR / name
    return path.read_text() if path.exists() else ""


CANONICAL_SYSTEM_PROMPT = load_file("canonical_system_prompt.md")

mcp = FastMCP("langflow-flow-generator")


@mcp.tool()
def generate_flow(description: str, name: str = "My Flow", tags: str = "") -> str:
    """Generate a complete Langflow flow JSON from a natural language description.

    Uses a 2-stage pipeline: LLM predicts canonical topology, then deterministic
    hydrator converts it to full importable Langflow JSON.

    Args:
        description: What the flow should do (e.g. "A chatbot that searches the web and answers questions")
        name: Name for the flow
        tags: Comma-separated tags (e.g. "chatbots,agents")

    Returns:
        Complete Langflow flow JSON ready to import
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    user_prompt = (
        "Instruction: Create a Langflow flow called '{name}'.\n"
        "Description: {desc}\n"
    ).format(name=name, desc=description)

    if tag_list:
        user_prompt += "Tags: {}\n".format(", ".join(tag_list))

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=CANONICAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    canonical_text = response.content[0].text.strip()

    # Strip markdown fences if present
    if canonical_text.startswith("```"):
        lines = canonical_text.split("\n")
        canonical_text = "\n".join(lines[1:])
        if canonical_text.endswith("```"):
            canonical_text = canonical_text[:-3].strip()

    # Parse canonical text
    try:
        canonical = text_to_canonical(canonical_text)
    except Exception as e:
        return json.dumps({
            "error": "Failed to parse canonical output: {}".format(e),
            "canonical_text": canonical_text,
        }, indent=2)

    # Normalize component types
    for n in canonical["nodes"]:
        n["type"] = normalize_type(n["type"])

    # Validate all component types exist
    unknown = [n["type"] for n in canonical["nodes"] if n["type"] not in COMP_SPECS]
    if unknown:
        return json.dumps({
            "error": "Unknown component types: {}".format(unknown),
            "canonical_text": canonical_text,
        }, indent=2)

    # Set name/description
    canonical["name"] = name
    canonical["description"] = description

    # Hydrate to full JSON
    try:
        flow_json = hydrate(canonical)
    except Exception as e:
        return json.dumps({
            "error": "Hydration failed: {}".format(e),
            "canonical_text": canonical_text,
        }, indent=2)

    if tag_list:
        flow_json["tags"] = tag_list

    return json.dumps(flow_json, indent=2)


@mcp.tool()
def list_components(category: str = "") -> str:
    """List available Langflow components, optionally filtered by category.

    Args:
        category: Filter by category (e.g. "agents", "tools", "processing"). Empty = all.

    Returns:
        List of components with name, type, description, inputs and outputs
    """
    components_path = SCRIPT_DIR / "components_full.json"
    if not components_path.exists():
        return "Component reference not found"

    with open(components_path) as f:
        components = json.load(f)

    if category:
        cat_lower = category.lower()
        components = [c for c in components if
                      cat_lower in c.get("module", "").lower() or
                      cat_lower in c["name"].lower() or
                      cat_lower in c.get("description", "").lower()]

    lines = []
    for c in components:
        inputs_str = ", ".join(
            "{} ({})".format(i["name"], "/".join(i["types"]))
            for i in c.get("inputs", [])[:5]
        )
        outputs_str = ", ".join(
            "{} ({})".format(o["name"], "/".join(o["types"]))
            for o in c.get("outputs", [])
        )
        lines.append("- **{}** (`{}`): {}\n  Inputs: {}\n  Outputs: {}".format(
            c["name"], c["type"], c.get("description", "")[:100],
            inputs_str or "none",
            outputs_str or "none",
        ))

    return "Found {} components:\n\n{}".format(len(lines), "\n\n".join(lines))


@mcp.tool()
def validate_flow(flow_json: str) -> str:
    """Validate a Langflow flow JSON for structural correctness.

    Args:
        flow_json: The flow JSON string to validate

    Returns:
        Validation results with any issues found
    """
    try:
        flow = json.loads(flow_json)
    except json.JSONDecodeError as e:
        return "INVALID JSON: {}".format(e)

    issues = []

    if "data" not in flow:
        issues.append("Missing 'data' key")
        return "INVALID: " + "; ".join(issues)

    nodes = flow["data"].get("nodes", [])
    edges = flow["data"].get("edges", [])

    if not nodes:
        issues.append("No nodes found")
    if not edges:
        issues.append("No edges found")

    node_ids = set()
    node_types = {}
    for n in nodes:
        nid = n.get("id", "")
        nd = n.get("data", {})
        ntype = nd.get("type", "")
        if ntype in ("note", "undefined"):
            continue
        if not nid:
            issues.append("Node missing ID")
        elif nid in node_ids:
            issues.append("Duplicate node ID: {}".format(nid))
        node_ids.add(nid)
        node_types[nid] = ntype

    types_present = set(node_types.values())
    if not types_present.intersection({"ChatInput", "TextInput", "Webhook", "File"}):
        issues.append("No input node (ChatInput/TextInput/File)")
    if not types_present.intersection({"ChatOutput", "TextOutput"}):
        issues.append("No output node (ChatOutput/TextOutput)")

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src not in node_ids:
            issues.append("Edge source '{}' not in nodes".format(src))
        if tgt not in node_ids:
            issues.append("Edge target '{}' not in nodes".format(tgt))

    connected = set()
    for e in edges:
        connected.add(e.get("source", ""))
        connected.add(e.get("target", ""))

    for nid in node_ids:
        if nid not in connected and node_types.get(nid) not in ("note", "undefined"):
            issues.append("Orphan node: {} ({})".format(nid, node_types.get(nid, "?")))

    if issues:
        return "ISSUES FOUND ({}):\n- {}".format(len(issues), "\n- ".join(issues))

    return "VALID: {} nodes, {} edges, all checks passed".format(len(node_ids), len(edges))


if __name__ == "__main__":
    mcp.run()
