"""
Canonical Flow Representation

Converts Langflow flow JSON to/from a minimal canonical form that captures
the TOPOLOGY (which components and how they connect) without:
- Template variable names (dynamic Prompt inputs)
- Node IDs
- Positions
- Component configuration details

Canonical format:
{
  "name": "Flow Name",
  "description": "What it does",
  "nodes": [
    {"type": "ChatInput", "id": "A"},
    {"type": "Agent", "id": "B"},
    {"type": "ChatOutput", "id": "C"},
    {"type": "TavilySearchComponent", "id": "D"},
  ],
  "edges": [
    {"from": "A", "to": "B", "conn": "message"},      # fixed connection
    {"from": "D", "to": "B", "conn": "tool"},          # tool connection
    {"from": "A", "to": "E", "conn": "template_var"},   # dynamic prompt variable
    {"from": "B", "to": "C", "conn": "message"},       # fixed connection
  ]
}

Connection types (semantic):
  "message"      - Message/text data flow (input_value, search_query, etc)
  "system"       - System prompt connection (system_message, system_prompt)
  "tool"         - Tool connection to Agent
  "model"        - LLM model connection
  "embedding"    - Embedding model connection
  "data"         - Data/DataFrame flow (ingest_data, data_inputs, input_data, etc)
  "template_var" - Dynamic Prompt template variable
"""

import json
import string
from collections import defaultdict

# Component type normalization (aliases -> canonical name)
TYPE_ALIASES = {
    "URL": "URLComponent",
    "Prompt Template": "Prompt",
    "parser": "ParserComponent",
    "OpenAIModel": "LanguageModelComponent",
    "OpenAIEmbeddings": "EmbeddingModel",
    # Common agent prediction errors — normalize to canonical names
    "AgentQLComponent": "AgentQL",
    "ApifyActorsComponent": "ApifyActors",
    "NeedleComponent": "needle",
    "YouTubeTranscriptsComponent": "YouTubeTranscripts",
    "SaveToFileComponent": "SaveToFile",
    "ScrapeGraphSearchApiComponent": "ScrapeGraphSearchApi",
    "YouTubeCommentsComponentComponent": "YouTubeCommentsComponent",
}

# Fixed field -> semantic connection type
FIELD_TO_CONN = {
    # Message inputs
    "input_value": "message",
    "search_query": "message",
    "input_text": "message",
    "message": "message",
    # System prompt
    "system_message": "system",
    "system_prompt": "system",
    # Tools
    "tools": "tool",
    # Models
    "llm": "model",
    "model": "model",
    # Embeddings
    "embedding_model": "embedding",
    # Data flow
    "ingest_data": "data",
    "data_inputs": "data",
    "input_data": "data",
    "input_df": "data",
    "data": "data",
    "df": "data",
    "dataframe": "data",
    # Specific fixed fields
    "transcript_id": "data",
    "connection_string": "data",
    # Model connections
    "llm": "model",
    "model": "model",
    # Loop
    "": "loop_back",
}

# Also classify by output name when field name is ambiguous
OUTPUT_TO_CONN = {
    "model_output": "model",
    "build_model": "model",
    "embeddings": "embedding",
    "build_embeddings": "embedding",
}

# All known fixed fields (appear consistently across flows)
FIXED_FIELDS = set(FIELD_TO_CONN.keys())


def normalize_type(t):
    """Normalize component type to canonical form."""
    return TYPE_ALIASES.get(t, t)


def classify_connection(field_name, source_type, target_type, output_name="", output_types=None):
    """Classify a connection as a semantic type."""
    # If target is a Prompt, all non-standard fields are template variables
    if target_type in ("Prompt", "Prompt Template"):
        return "template_var"

    # Check if it's a known fixed field
    if field_name in FIELD_TO_CONN:
        return FIELD_TO_CONN[field_name]

    # If source output is a tool type
    if "tool" in field_name.lower():
        return "tool"

    # Classify by output name
    if output_name in OUTPUT_TO_CONN:
        return OUTPUT_TO_CONN[output_name]

    # Classify by output types
    if output_types:
        if any(t in ("DataFrame", "Data") for t in output_types):
            return "data"
        if any(t == "Tool" for t in output_types):
            return "tool"
        if any(t == "LanguageModel" for t in output_types):
            return "model"
        if any(t == "Embeddings" for t in output_types):
            return "embedding"

    # Default to message for unknown
    return "message"


def flow_to_canonical(flow):
    """Convert a Langflow flow JSON to canonical representation."""
    nodes_data = flow.get("data", {}).get("nodes", [])
    edges_data = flow.get("data", {}).get("edges", [])

    # Build node list (skip notes/undefined)
    nodes = []
    id_map = {}  # original_id -> canonical_id (A, B, C, ...)
    id_to_type = {}  # original_id -> normalized type
    idx = 0

    for n in nodes_data:
        nd = n.get("data", {})
        ntype = nd.get("type", "")
        if not ntype or ntype in ("note", "undefined"):
            continue

        ntype = normalize_type(ntype)
        canonical_id = string.ascii_uppercase[idx] if idx < 26 else "N{}".format(idx)
        id_map[n.get("id", "")] = canonical_id
        id_to_type[n.get("id", "")] = ntype
        nodes.append({"type": ntype, "id": canonical_id})
        idx += 1

    # Pre-scan: which Prompt nodes receive ChatInput as a template_var?
    # If a Prompt gets ChatInput, it incorporates the question -> output is "message"
    # If not, the Prompt is a static system prompt -> output is "system"
    prompts_with_user_input = set()
    for e in edges_data:
        src_id = e.get("source", "")
        tgt_id = e.get("target", "")
        src_type = id_to_type.get(src_id, "")
        tgt_type = id_to_type.get(tgt_id, "")
        tgt_handle = e.get("data", {}).get("targetHandle", {})
        field_name = tgt_handle.get("fieldName", "")

        if src_type == "ChatInput" and tgt_type == "Prompt" and field_name not in FIXED_FIELDS:
            prompts_with_user_input.add(tgt_id)

    # Build edge list
    edges = []
    for e in edges_data:
        src_id = e.get("source", "")
        tgt_id = e.get("target", "")

        if src_id not in id_map or tgt_id not in id_map:
            continue

        src_handle = e.get("data", {}).get("sourceHandle", {})
        tgt_handle = e.get("data", {}).get("targetHandle", {})

        field_name = tgt_handle.get("fieldName", "")
        src_type = id_to_type.get(src_id, "")
        tgt_type = id_to_type.get(tgt_id, "")
        output_name = src_handle.get("name", "")
        output_types = src_handle.get("output_types", [])

        conn = classify_connection(field_name, src_type, tgt_type, output_name, output_types)

        # Refine Prompt->LLM/Agent based on actual field name
        if src_type == "Prompt" and tgt_type in ("LanguageModelComponent", "Agent"):
            if field_name in ("system_message", "system_prompt"):
                conn = "system"
            elif field_name in ("input_value",):
                conn = "message"
            elif src_id in prompts_with_user_input:
                conn = "message"
            else:
                conn = "system"

        edges.append({
            "from": id_map[src_id],
            "to": id_map[tgt_id],
            "conn": conn,
        })

    return {
        "name": flow.get("name", ""),
        "description": flow.get("description", ""),
        "nodes": nodes,
        "edges": edges,
    }


def normalize_canonical(canonical):
    """Normalize a canonical flow to collapse equivalent patterns.

    Pattern equivalence:
      Pattern A: ChatInput->LLM[message] + Prompt->LLM[system]
      Pattern B: ChatInput->Prompt[template_var] + Prompt->LLM[message]

    Both are valid ways to wire a chatbot. We normalize to Pattern A
    so that comparison is fair regardless of which pattern was chosen.

    Same applies to LLM->LLM chaining vs LLM->Prompt->LLM.
    """
    node_types = {n["id"]: n["type"] for n in canonical["nodes"]}
    edges = [dict(e) for e in canonical["edges"]]
    nodes = list(canonical["nodes"])

    # Detect Pattern B: X->Prompt[template_var] + Prompt->Target[message]
    # where X is ChatInput or LLM (for chaining)
    changed = True
    while changed:
        changed = False
        for i, e in enumerate(edges):
            src_type = node_types.get(e["from"], "")
            tgt_type = node_types.get(e["to"], "")

            if tgt_type != "Prompt" or e["conn"] != "template_var":
                continue
            # Normalize any source feeding into Prompt as template_var
            # when that Prompt connects to an LLM/Agent
            if src_type == "Prompt":
                continue  # Skip Prompt->Prompt template_var

            prompt_id = e["to"]

            # Find: this Prompt -> LLM/Agent [message] or [system]
            prompt_to_llm = None
            for j, e2 in enumerate(edges):
                if e2["from"] == prompt_id and e2["conn"] in ("message", "system"):
                    llm_type = node_types.get(e2["to"], "")
                    if llm_type in ("LanguageModelComponent", "Agent"):
                        prompt_to_llm = j
                        break

            if prompt_to_llm is None:
                continue

            llm_id = edges[prompt_to_llm]["to"]

            # Transform: X->Prompt[template_var] becomes X->LLM[message]
            #            Prompt->LLM[message/system] becomes Prompt->LLM[system]
            edges[i] = {"from": e["from"], "to": llm_id, "conn": "message"}
            edges[prompt_to_llm] = {"from": prompt_id, "to": llm_id, "conn": "system"}
            changed = True
            break

    return {
        "name": canonical["name"],
        "description": canonical["description"],
        "nodes": nodes,
        "edges": edges,
    }


def canonical_to_text(canonical):
    """Convert canonical form to a compact text representation."""
    lines = []
    lines.append("# {}".format(canonical["name"]))
    if canonical.get("description"):
        lines.append("# {}".format(canonical["description"]))
    lines.append("")

    # Nodes
    lines.append("nodes:")
    for n in canonical["nodes"]:
        lines.append("  {}: {}".format(n["id"], n["type"]))

    # Edges grouped by connection type
    lines.append("")
    lines.append("edges:")
    for e in canonical["edges"]:
        lines.append("  {} -> {} [{}]".format(e["from"], e["to"], e["conn"]))

    return "\n".join(lines)


def text_to_canonical(text):
    """Parse compact text representation back to canonical form."""
    lines = text.strip().split("\n")

    canonical = {"name": "", "description": "", "nodes": [], "edges": [], "params": {}}

    section = None
    current_param_key = None
    current_param_lines = []

    def _flush_param():
        if current_param_key and current_param_lines:
            canonical["params"][current_param_key] = "\n".join(current_param_lines).strip()

    for line in lines:
        raw_line = line
        line = line.strip()

        if not line and section != "params":
            continue
        if line.startswith("# "):
            if not canonical["name"]:
                canonical["name"] = line[2:]
            else:
                canonical["description"] = line[2:]
            continue
        if line == "nodes:":
            _flush_param()
            section = "nodes"
            current_param_key = None
            continue
        if line == "edges:":
            _flush_param()
            section = "edges"
            current_param_key = None
            continue
        if line == "params:":
            _flush_param()
            section = "params"
            current_param_key = None
            continue

        if section == "nodes":
            # "A: ChatInput"
            parts = line.split(": ", 1)
            if len(parts) == 2:
                canonical["nodes"].append({"id": parts[0], "type": parts[1]})

        elif section == "edges":
            # "A -> B [message]"
            parts = line.split(" -> ", 1)
            if len(parts) == 2:
                from_id = parts[0]
                rest = parts[1]
                # Parse "B [message]"
                bracket_start = rest.index("[")
                to_id = rest[:bracket_start].strip()
                conn = rest[bracket_start+1:rest.index("]")]
                canonical["edges"].append({"from": from_id, "to": to_id, "conn": conn})

        elif section == "params":
            # "B.template: |" or "B.template: single line value"
            # or continuation of multiline value
            if "." in line and ": " in line.split(".")[0] + line.split(".", 1)[1]:
                # Check if this is a new key (e.g., "B.template: ...")
                dot_pos = line.index(".")
                colon_pos = line.index(": ", dot_pos)
                key = line[:colon_pos]
                value = line[colon_pos + 2:]
                _flush_param()
                current_param_key = key
                current_param_lines = []
                if value and value != "|":
                    current_param_lines.append(value)
            elif current_param_key:
                # Continuation line — preserve indentation relative to params block
                # Strip at most 4 spaces of indentation (params block indent)
                stripped = raw_line
                for _ in range(4):
                    if stripped.startswith(" "):
                        stripped = stripped[1:]
                current_param_lines.append(stripped)

    _flush_param()
    return canonical


if __name__ == "__main__":
    with open("dataset.json") as f:
        dataset = json.load(f)

    print("=" * 70)
    print("CANONICAL REPRESENTATIONS")
    print("=" * 70)

    # Show a few examples
    examples = ["Simple Agent", "Memory Chatbot", "Twitter Thread Generator",
                "Basic Prompt Chaining", "Custom Component Generator",
                "Hybrid Search RAG", "Instagram Copywriter"]

    for entry in dataset:
        if entry["name"] in examples:
            canonical = flow_to_canonical(entry["original_flow"])
            print()
            print(canonical_to_text(canonical))
            print()
            print("-" * 70)

    # Now convert ALL and check: do equivalent flows produce same canonical?
    print("\n\n" + "=" * 70)
    print("FULL DATASET CANONICAL CONVERSION")
    print("=" * 70)

    all_canonical = []
    for entry in dataset:
        if "original_flow" not in entry:
            continue
        canonical = flow_to_canonical(entry["original_flow"])
        text = canonical_to_text(canonical)
        # Verify roundtrip
        parsed = text_to_canonical(text)
        assert len(parsed["nodes"]) == len(canonical["nodes"]), \
            "{}: nodes mismatch after roundtrip".format(entry["name"])
        assert len(parsed["edges"]) == len(canonical["edges"]), \
            "{}: edges mismatch after roundtrip".format(entry["name"])
        all_canonical.append({"name": entry["name"], "canonical": canonical, "text": text})
        print("  OK  {} ({} nodes, {} edges)".format(
            entry["name"], len(canonical["nodes"]), len(canonical["edges"])))

    # Save
    with open("canonical_dataset.json", "w") as f:
        json.dump(all_canonical, f, indent=2, ensure_ascii=False)

    print("\nSaved {} canonical flows to canonical_dataset.json".format(len(all_canonical)))
