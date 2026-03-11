#!/usr/bin/env python3
"""
End-to-end flow generation pipeline:
1. LLM generates canonical form (topology + params)
2. Hydrator converts to full Langflow JSON
3. Upload to Langflow via API
4. Run with test input
5. Report results (or retry on failure)
"""

import json
import sys
import time
from pathlib import Path

import anthropic
import requests

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from canonical import text_to_canonical, normalize_type
from hydrator import hydrate, COMP_SPECS, DEFAULT_MODEL

LANGFLOW_URL = "http://localhost:7860"
CANONICAL_SYSTEM_PROMPT = (SCRIPT_DIR / "canonical_system_prompt.md").read_text()


def generate_canonical(description: str, name: str = "My Flow") -> dict:
    """Stage 1: LLM generates canonical text from description."""
    user_prompt = (
        "Instruction: Create a Langflow flow called '{name}'.\n"
        "Description: {desc}\n"
    ).format(name=name, desc=description)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=CANONICAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()

    return text


def parse_and_hydrate(canonical_text: str, name: str, description: str) -> dict:
    """Stage 2: Parse canonical text and hydrate to full JSON."""
    canonical = text_to_canonical(canonical_text)

    # Normalize types
    for n in canonical["nodes"]:
        n["type"] = normalize_type(n["type"])

    # Validate types
    unknown = [n["type"] for n in canonical["nodes"] if n["type"] not in COMP_SPECS]
    if unknown:
        raise ValueError("Unknown component types: {}".format(unknown))

    canonical["name"] = name
    canonical["description"] = description

    flow_json = hydrate(canonical)
    flow_json["name"] = name
    flow_json["description"] = description
    return flow_json


def upload_flow(flow_json: dict) -> str:
    """Stage 3: Upload flow to Langflow, return flow_id."""
    resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/flows/",
        json=flow_json,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["id"]


def run_flow(flow_id: str, input_text: str) -> dict:
    """Stage 4: Run the flow with test input."""
    resp = requests.post(
        f"{LANGFLOW_URL}/api/v1/run/{flow_id}",
        json={
            "input_value": input_text,
            "input_type": "chat",
            "output_type": "chat",
        },
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def delete_flow(flow_id: str):
    """Clean up: delete the flow."""
    requests.delete(f"{LANGFLOW_URL}/api/v1/flows/{flow_id}")


def extract_output(run_result: dict) -> str:
    """Extract the text output from run result."""
    outputs = run_result.get("outputs", [])
    for output_group in outputs:
        for output in output_group.get("outputs", []):
            results = output.get("results", {})
            message = results.get("message", {})
            if isinstance(message, dict):
                text = message.get("text", "")
                if text:
                    return text
            # Try artifacts
            artifacts = output.get("artifacts", {})
            if artifacts.get("message"):
                return artifacts["message"]
    return ""


def generate_and_run(description: str, name: str = "My Flow", test_input: str = "",
                     max_retries: int = 2, save_path: str = None) -> dict:
    """Full pipeline: generate → hydrate → upload → run → validate."""

    print(f"[1/4] Generating canonical for: {name}")
    canonical_text = generate_canonical(description, name)
    print(f"  Canonical:\n{canonical_text}\n")

    print(f"[2/4] Hydrating to full JSON...")
    try:
        flow_json = parse_and_hydrate(canonical_text, name, description)
    except ValueError as e:
        return {"success": False, "error": str(e), "stage": "hydration", "canonical": canonical_text}

    print(f"  Nodes: {len(flow_json['data']['nodes'])}, Edges: {len(flow_json['data']['edges'])}")

    if save_path:
        with open(save_path, "w") as f:
            json.dump(flow_json, f, indent=2)
        print(f"  Saved to {save_path}")

    print(f"[3/4] Uploading to Langflow...")
    try:
        flow_id = upload_flow(flow_json)
    except Exception as e:
        return {"success": False, "error": str(e), "stage": "upload", "canonical": canonical_text}
    print(f"  Flow ID: {flow_id}")

    if not test_input:
        print(f"[4/4] No test input provided, skipping run.")
        return {
            "success": True,
            "flow_id": flow_id,
            "canonical": canonical_text,
            "stage": "uploaded",
        }

    print(f"[4/4] Running with input: {test_input[:100]}...")
    try:
        result = run_flow(flow_id, test_input)
        output = extract_output(result)
        print(f"  Output: {output[:200]}...")
        success = bool(output)
    except Exception as e:
        output = ""
        success = False
        result = {"error": str(e)}
        print(f"  Run failed: {e}")

    # Clean up
    delete_flow(flow_id)

    return {
        "success": success,
        "flow_id": flow_id,
        "canonical": canonical_text,
        "output": output,
        "run_result": result if not success else None,
        "stage": "completed" if success else "run_failed",
    }


if __name__ == "__main__":
    result = generate_and_run(
        name="YouTube Comments Summarizer",
        description="Fetches all comments from a YouTube video and summarizes them using an LLM.",
        test_input="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        save_path="/Users/rodrigonader/Downloads/YouTube Comments Summarizer.json",
    )

    print("\n" + "=" * 60)
    print(f"Result: {'SUCCESS' if result['success'] else 'FAILED'}")
    print(f"Stage: {result['stage']}")
    if result.get("output"):
        print(f"Output: {result['output'][:500]}")
    if result.get("error"):
        print(f"Error: {result['error']}")
