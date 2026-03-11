"""
Hydrator: Converts canonical flow representation → full Langflow JSON.

Takes the compact canonical form (nodes + typed edges) and produces
a complete, importable Langflow flow JSON by:
1. Looking up component I/O specs from components_full.json
2. Mapping semantic connection types to exact field/output names
3. Generating proper node IDs, positions, and edge handles
"""

import json
import random
import string
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Load component specs (for input/output type matching)
with open(SCRIPT_DIR / "components_full.json") as f:
    _raw_comps = json.load(f)

COMP_SPECS = {}
for c in _raw_comps:
    t = c["type"]
    if t not in COMP_SPECS:
        COMP_SPECS[t] = c

# Add canonical type aliases so hydrator accepts normalized names
_CANONICAL_ALIASES = {
    "Prompt": "Prompt Template",
    "parser": "ParserComponent",
    "URL": "URLComponent",
}
for alias, real in _CANONICAL_ALIASES.items():
    if alias not in COMP_SPECS and real in COMP_SPECS:
        COMP_SPECS[alias] = COMP_SPECS[real]

# Load real component templates extracted from dataset flows
# These have correct method names, field types, and display settings
_COMP_TEMPLATES_PATH = SCRIPT_DIR / "component_templates.json"
COMP_TEMPLATES = {}
if _COMP_TEMPLATES_PATH.exists():
    with open(_COMP_TEMPLATES_PATH) as f:
        COMP_TEMPLATES = json.load(f)

# Patch missing fields in COMP_SPECS (for input/output resolution)
_PATCHES = {
    "StructuredOutput": {
        "inputs": [{"name": "llm", "display": "Language Model", "types": ["LanguageModel"]}],
    },
    "SmartRouter": {
        "inputs": [{"name": "llm", "display": "Language Model", "types": ["LanguageModel"]}],
    },
    "BatchRunComponent": {
        "inputs": [{"name": "model", "display": "Language Model", "types": ["LanguageModel"]}],
    },
    "DataFrameToToolset": {
        "inputs": [{"name": "dataframe", "display": "DataFrame", "types": ["DataFrame"]}],
    },
    "DataFrameOperationsComponent": {
        "inputs": [{"name": "df", "display": "DataFrame", "types": ["DataFrame"]}],
    },
}
for comp_type, patch in _PATCHES.items():
    if comp_type not in COMP_SPECS:
        COMP_SPECS[comp_type] = {"type": comp_type, "name": comp_type, "description": "", "inputs": [], "outputs": []}
    spec = COMP_SPECS[comp_type]
    existing_input_names = {i["name"] for i in spec.get("inputs", [])}
    for inp in patch.get("inputs", []):
        if inp["name"] not in existing_input_names:
            spec["inputs"].append(inp)


# Semantic connection type → candidate target field names (in priority order)
CONN_TO_FIELDS = {
    "message": ["input_value", "search_query", "input_text", "message"],
    "system": ["system_message", "system_prompt"],
    "tool": ["tools"],
    "model": ["llm", "model"],
    "embedding": ["embedding_model"],
    "data": ["ingest_data", "data_inputs", "input_data", "input_df", "data", "df", "dataframe"],
    "loop_back": [""],
    "template_var": [],  # dynamic — any field not in the fixed set
}

# Semantic connection type → candidate source output names (in priority order)
CONN_TO_OUTPUTS = {
    "message": ["response", "text_output", "message", "parsed_text", "prompt",
                 "messages_text", "output_data", "message_output", "text"],
    "system": ["prompt"],
    "tool": ["component_as_tool", "tools"],
    "model": ["model_output", "build_model"],
    "embedding": ["embeddings", "build_embeddings"],
    "data": ["dataframe", "search_results", "data", "structured_output",
             "dataframe_output", "page_results", "raw_results", "item", "done",
             "batch_results", "data_output"],
    "loop_back": ["response", "text_output", "structured_output", "data_output"],
    "template_var": ["text", "message", "response", "text_output", "parsed_text",
                     "page_results", "raw_results", "messages_text", "prompt",
                     "component_as_tool"],
}


def _rand_id(n=5):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _get_all_outputs(comp_type):
    """Get all outputs for a component from templates (preferred) or specs."""
    ct = COMP_TEMPLATES.get(comp_type, {})
    if ct.get("outputs"):
        return ct["outputs"]
    spec = COMP_SPECS.get(comp_type, {})
    return spec.get("outputs", [])


def _find_output(comp_type, conn_type):
    """Find the best output name for a component given connection type."""
    # Tool connections always use component_as_tool (runtime-generated, may not be in template)
    if conn_type == "tool":
        return "component_as_tool"

    outputs = _get_all_outputs(comp_type)
    output_names = [o["name"] for o in outputs]

    # First try: match by name from priority list
    for candidate in CONN_TO_OUTPUTS.get(conn_type, []):
        if candidate in output_names:
            return candidate

    # Second try: match by output TYPE
    expected_types = {
        "message": {"Message"},
        "system": {"Message"},
        "tool": {"Tool"},
        "model": {"LanguageModel"},
        "embedding": {"Embeddings"},
        "data": {"DataFrame", "Data"},
        "loop_back": {"Message", "Data"},
    }
    wanted = expected_types.get(conn_type, set())
    if wanted:
        for o in outputs:
            if set(o.get("types", [])) & wanted:
                return o["name"]

    # Fallback: first output
    return output_names[0] if output_names else "output"


def _find_output_types(comp_type, output_name):
    """Get output types for a component's output."""
    if output_name == "component_as_tool":
        return ["Tool"]
    for o in _get_all_outputs(comp_type):
        if o["name"] == output_name:
            return o.get("types", ["Message"])
    return ["Message"]


def _find_input_field(comp_type, conn_type, used_fields=None):
    """Find the best input field for a component given connection type."""
    if used_fields is None:
        used_fields = set()

    # For template_var on Prompt: generate a variable name
    if conn_type == "template_var":
        var_idx = len([f for f in used_fields if f.startswith("var")]) + 1
        return "var_{}".format(var_idx)

    # For loop_back: use empty field name (Langflow loop convention)
    if conn_type == "loop_back":
        return ""

    # Get all input field names from templates (authoritative) and specs (fallback)
    ct = COMP_TEMPLATES.get(comp_type, {})
    tmpl_fields = set(ct.get("template", {}).keys()) - {"_type", "code"}
    spec = COMP_SPECS.get(comp_type, {})
    spec_names = [i["name"] for i in spec.get("inputs", [])]
    all_names = list(tmpl_fields | set(spec_names))

    # First try: match by name from priority list, but only if field exists in template
    for candidate in CONN_TO_FIELDS.get(conn_type, []):
        if candidate in tmpl_fields and candidate not in used_fields:
            return candidate
    # Also check spec names as fallback
    for candidate in CONN_TO_FIELDS.get(conn_type, []):
        if candidate in spec_names and candidate not in used_fields:
            return candidate

    # Second try: match by input TYPE from template fields
    expected_types = {
        "message": {"Message"},
        "system": {"Message"},
        "tool": {"Tool"},
        "model": {"LanguageModel"},
        "embedding": {"Embeddings"},
        "data": {"DataFrame", "Data"},
    }
    wanted = expected_types.get(conn_type, set())
    if wanted:
        # Check template fields first
        tmpl = ct.get("template", {})
        for fname, fdata in tmpl.items():
            if fname in ("_type", "code") or fname in used_fields:
                continue
            if not isinstance(fdata, dict):
                continue
            field_types = set(fdata.get("input_types", []))
            if field_types & wanted:
                if conn_type == "system" and "system" in fname:
                    return fname
        for fname, fdata in tmpl.items():
            if fname in ("_type", "code") or fname in used_fields:
                continue
            if not isinstance(fdata, dict):
                continue
            field_types = set(fdata.get("input_types", []))
            if field_types & wanted:
                return fname
        # Fallback to spec inputs
        for inp in spec.get("inputs", []):
            if inp["name"] not in used_fields and set(inp.get("types", [])) & wanted:
                return inp["name"]

    # Fallback: prefer input_value
    if "input_value" in all_names and "input_value" not in used_fields:
        return "input_value"

    for name in all_names:
        if name not in used_fields and name not in ("code", "_type", "add_current_date_tool"):
            return name

    return "input_value"


def _find_input_types(comp_type, field_name):
    """Get input types for a component's field."""
    # Check authoritative template first
    ct = COMP_TEMPLATES.get(comp_type, {})
    tmpl = ct.get("template", {})
    if field_name in tmpl and isinstance(tmpl[field_name], dict):
        # input_types key exists → use it (even if empty list)
        if "input_types" in tmpl[field_name]:
            return tmpl[field_name]["input_types"]
    # Fallback to specs
    spec = COMP_SPECS.get(comp_type, {})
    for i in spec.get("inputs", []):
        if i["name"] == field_name:
            return i.get("types", ["str"])
    # Template vars accept Message
    return ["Message"]


def _handle_to_str(handle_dict):
    """Serialize a handle dict to the React Flow string format Langflow expects."""
    return json.dumps(handle_dict, separators=(", ", ": ")).replace('"', "\u0153")


def _get_field_type(comp_type, field_name):
    """Get the Langflow 'type' value for an input field from real templates."""
    ct = COMP_TEMPLATES.get(comp_type, {})
    tmpl = ct.get("template", {})
    if field_name in tmpl:
        return tmpl[field_name].get("type", "str")
    # Fallback: infer from accepted types
    spec = COMP_SPECS.get(comp_type, {})
    for inp in spec.get("inputs", []):
        if inp["name"] == field_name:
            types = inp.get("types", [])
            handle_types = {"Tool", "LanguageModel", "Embeddings", "Data", "DataFrame"}
            if any(t in handle_types for t in types):
                return "other"
            return "str"
    return "str"


def _build_template(comp_type, connected_fields):
    """Build a proper node template from real component templates.

    Uses extracted real templates when available, falls back to component specs.
    """
    ct = COMP_TEMPLATES.get(comp_type)
    if ct:
        # Start from real template
        template = json.loads(json.dumps(ct["template"]))  # deep copy

        # Ensure all connected fields are visible
        for field_name in connected_fields:
            if field_name in template:
                template[field_name]["show"] = True
                template[field_name]["advanced"] = False

        # Add dynamic template_var fields not in the real template
        for field_name, field_types in connected_fields.items():
            if field_name not in template and field_name != "_type":
                template[field_name] = {
                    "_input_type": "MessageInput",
                    "advanced": False,
                    "display_name": field_name,
                    "dynamic": False,
                    "info": "",
                    "input_types": field_types,
                    "list": False,
                    "load_from_db": False,
                    "name": field_name,
                    "placeholder": "",
                    "required": False,
                    "show": True,
                    "title_case": False,
                    "tool_mode": False,
                    "trace_as_metadata": True,
                    "type": "str",
                    "value": "",
                }

        return template

    # Fallback: build from component specs
    spec = COMP_SPECS.get(comp_type, {})
    template = {"_type": "Component"}

    for inp in spec.get("inputs", []):
        name = inp["name"]
        types = inp.get("types", [])
        handle_types = {"Tool", "LanguageModel", "Embeddings", "Data", "DataFrame"}
        type_cat = "other" if any(t in handle_types for t in types) else "str"
        input_type = "HandleInput" if type_cat == "other" else ("MessageInput" if "Message" in types else "StrInput")

        template[name] = {
            "_input_type": input_type,
            "advanced": name not in connected_fields,
            "display_name": inp.get("display", name),
            "dynamic": False,
            "info": "",
            "input_types": types,
            "list": name == "tools",
            "load_from_db": False,
            "name": name,
            "placeholder": "",
            "required": False,
            "show": True,
            "title_case": False,
            "tool_mode": False,
            "trace_as_metadata": True,
            "type": type_cat,
            "value": "",
        }

    for field_name, field_types in connected_fields.items():
        if field_name not in template and field_name != "_type":
            template[field_name] = {
                "_input_type": "MessageInput",
                "advanced": False,
                "display_name": field_name,
                "dynamic": False,
                "info": "",
                "input_types": field_types,
                "list": False,
                "load_from_db": False,
                "name": field_name,
                "placeholder": "",
                "required": False,
                "show": True,
                "title_case": False,
                "tool_mode": False,
                "trace_as_metadata": True,
                "type": "str",
                "value": "",
            }

    return template


def _build_outputs(comp_type):
    """Build output list from real templates or fallback to specs."""
    ct = COMP_TEMPLATES.get(comp_type)
    if ct:
        outputs = []
        for o in ct["outputs"]:
            outputs.append({
                "allows_loop": False,
                "cache": True,
                "display_name": o.get("display_name", o["name"]),
                "group_outputs": False,
                "method": o["method"],
                "name": o["name"],
                "selected": o.get("selected", "Message"),
                "tool_mode": True,
                "types": o.get("types", ["Message"]),
                "value": "__UNDEFINED__",
            })
        return outputs

    # Fallback
    spec = COMP_SPECS.get(comp_type, {})
    outputs = []
    for o in spec.get("outputs", []):
        outputs.append({
            "allows_loop": False,
            "cache": True,
            "display_name": o.get("display", o["name"]),
            "group_outputs": False,
            "method": o.get("method", o["name"]),
            "name": o["name"],
            "selected": o.get("types", ["Message"])[0] if o.get("types") else "Message",
            "tool_mode": True,
            "types": o.get("types", ["Message"]),
            "value": "__UNDEFINED__",
        })
    return outputs


DEFAULT_MODEL = [{
    "category": "OpenAI",
    "icon": "OpenAI",
    "metadata": {
        "api_key_param": "api_key",
        "context_length": 128000,
        "model_class": "ChatOpenAI",
        "model_name_param": "model_name",
    },
    "name": "gpt-4o-mini",
    "provider": "OpenAI",
}]


def hydrate(canonical, default_model=None):
    """Convert canonical representation to full Langflow flow JSON.

    Args:
        canonical: Canonical flow dict with nodes, edges, and optional params.
        default_model: Model selection value for LanguageModelComponent nodes.
                       Defaults to DEFAULT_MODEL (gpt-4o-mini).
    """
    if default_model is None:
        default_model = DEFAULT_MODEL

    nodes_spec = canonical["nodes"]
    edges_spec = canonical["edges"]

    # Generate real node IDs
    node_id_map = {}  # canonical_id -> real_id
    node_type_map = {}  # canonical_id -> type
    for n in nodes_spec:
        real_id = "{}-{}".format(n["type"], _rand_id())
        node_id_map[n["id"]] = real_id
        node_type_map[n["id"]] = n["type"]

    # Track which nodes are used as tools (need tool_mode=true)
    tool_mode_nodes = set()
    for e in edges_spec:
        if e["conn"] == "tool":
            tool_mode_nodes.add(e["from"])

    # Track used input fields per target node (to avoid duplicates)
    used_fields = {n["id"]: set() for n in nodes_spec}

    # Build edges and track which fields are connected per node
    connected_fields = {n["id"]: {} for n in nodes_spec}  # cid -> {field: types}
    edges = []
    for e in edges_spec:
        src_cid = e["from"]
        tgt_cid = e["to"]
        conn = e["conn"]

        src_type = node_type_map[src_cid]
        tgt_type = node_type_map[tgt_cid]
        src_real = node_id_map[src_cid]
        tgt_real = node_id_map[tgt_cid]

        output_name = _find_output(src_type, conn)
        output_types = _find_output_types(src_type, output_name)

        field_name = _find_input_field(tgt_type, conn, used_fields[tgt_cid])
        # Tools field accepts multiple connections, don't mark as used
        if conn != "tool":
            used_fields[tgt_cid].add(field_name)
        input_types = _find_input_types(tgt_type, field_name)

        # Track connected fields for template building
        connected_fields[tgt_cid][field_name] = input_types

        source_handle = {
            "dataType": src_type,
            "id": src_real,
            "name": output_name,
            "output_types": output_types,
        }
        target_handle = {
            "fieldName": field_name,
            "id": tgt_real,
            "inputTypes": input_types,
            "type": _get_field_type(tgt_type, field_name),
        }

        src_handle_str = _handle_to_str(source_handle)
        tgt_handle_str = _handle_to_str(target_handle)

        edges.append({
            "animated": False,
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
            },
            "id": "reactflow__edge-{}{}-{}{}".format(
                src_real, src_handle_str, tgt_real, tgt_handle_str
            ),
            "source": src_real,
            "sourceHandle": src_handle_str,
            "target": tgt_real,
            "targetHandle": tgt_handle_str,
        })

    # Build nodes with positions (left-to-right layout)
    # Simple topological sort for x positioning
    depth = {n["id"]: 0 for n in nodes_spec}
    for e in edges_spec:
        depth[e["to"]] = max(depth[e["to"]], depth[e["from"]] + 1)

    # Group by depth for y positioning
    by_depth = {}
    for cid, d in depth.items():
        by_depth.setdefault(d, []).append(cid)

    positions = {}
    for d, cids in by_depth.items():
        for i, cid in enumerate(cids):
            positions[cid] = {"x": d * 400, "y": i * 300}

    nodes = []
    for n in nodes_spec:
        cid = n["id"]
        ntype = n["type"]
        real_id = node_id_map[cid]
        spec = COMP_SPECS.get(ntype, {})
        ct = COMP_TEMPLATES.get(ntype, {})

        is_tool = cid in tool_mode_nodes
        outputs = _build_outputs(ntype)

        # Tool-mode nodes: use only component_as_tool output
        if is_tool:
            tool_output = [o for o in outputs if o["name"] == "component_as_tool"]
            if tool_output:
                outputs = tool_output
            else:
                # Component doesn't have component_as_tool in template — add standard one
                outputs = [{
                    "allows_loop": False,
                    "cache": True,
                    "display_name": "Toolset",
                    "group_outputs": False,
                    "method": "to_toolkit",
                    "name": "component_as_tool",
                    "selected": "Tool",
                    "tool_mode": True,
                    "types": ["Tool"],
                    "value": "__UNDEFINED__",
                }]

        template = _build_template(ntype, connected_fields.get(cid, {}))

        # Apply params from canonical
        params = canonical.get("params", {})
        for param_key, param_value in params.items():
            # param_key is "NODE_ID.field_name" e.g. "B.template"
            if "." not in param_key:
                continue
            p_node_id, p_field = param_key.split(".", 1)
            if p_node_id != cid:
                continue
            if p_field in template and isinstance(template[p_field], dict):
                template[p_field]["value"] = param_value
            elif p_field == "agent_description" and "agent_description" in template:
                template["agent_description"]["value"] = param_value

        # Set default model on LLM/Agent nodes
        if ntype in ("LanguageModelComponent", "Agent") and default_model:
            if "model" in template and isinstance(template["model"], dict):
                if not template["model"].get("value"):
                    template["model"]["value"] = default_model

        # For Prompt nodes, add custom_fields listing template variables
        custom_fields = {}
        if ntype in ("Prompt", "Prompt Template"):
            tv_fields = [f for f in connected_fields.get(cid, {}) if f not in ("_type",)]
            if tv_fields:
                custom_fields["template"] = tv_fields

        display_name = ct.get("display_name", spec.get("name", ntype))
        description = ct.get("description", spec.get("description", ""))
        field_order = ct.get("field_order", [inp["name"] for inp in spec.get("inputs", [])])
        icon = ct.get("icon", "")

        node_inner = {
            "base_classes": spec.get("base_classes", []),
            "display_name": display_name,
            "documentation": "",
            "edited": False,
            "field_order": field_order,
            "frozen": False,
            "outputs": outputs,
            "template": template,
        }
        if is_tool:
            node_inner["tool_mode"] = True
        if custom_fields:
            node_inner["custom_fields"] = custom_fields
        if icon:
            node_inner["icon"] = icon

        node = {
            "data": {
                "description": description,
                "display_name": display_name,
                "id": real_id,
                "node": node_inner,
                "type": ntype,
            },
            "id": real_id,
            "position": positions.get(cid, {"x": 0, "y": 0}),
            "type": "genericNode",
        }
        nodes.append(node)

    return {
        "data": {
            "edges": edges,
            "nodes": nodes,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
        "description": canonical.get("description", ""),
        "endpoint_name": None,
        "id": str(uuid.uuid4()),
        "is_component": False,
        "last_tested_version": "1.4.2",
        "name": canonical.get("name", "Untitled Flow"),
    }


if __name__ == "__main__":
    from canonical import text_to_canonical, flow_to_canonical, canonical_to_text

    # Test: canonical text → hydrated JSON
    test_text = """# Simple Agent
# A simple but powerful starter agent.

nodes:
  A: ChatInput
  B: Agent
  C: ChatOutput
  D: CalculatorComponent
  E: URLComponent

edges:
  A -> B [message]
  D -> B [tool]
  E -> B [tool]
  B -> C [message]"""

    canonical = text_to_canonical(test_text)
    flow_json = hydrate(canonical)

    print("=== Hydrated Flow ===")
    print("Name:", flow_json["name"])
    print("Nodes:", len(flow_json["data"]["nodes"]))
    print("Edges:", len(flow_json["data"]["edges"]))
    print()

    for n in flow_json["data"]["nodes"]:
        nd = n["data"]
        print("  {} ({}) at {}".format(nd["display_name"], nd["type"], n["position"]))

    print()
    for e in flow_json["data"]["edges"]:
        src = e["data"]["sourceHandle"]
        tgt = e["data"]["targetHandle"]
        print("  {}.{} -> {}.{}".format(src["dataType"], src["name"], tgt["id"].split("-")[0], tgt["fieldName"]))

    # Validate roundtrip: original → canonical → hydrate → canonical → compare
    print("\n\n=== Roundtrip Validation ===")
    with open("dataset.json") as f:
        dataset = json.load(f)

    for entry in dataset[:10]:
        orig_canonical = flow_to_canonical(entry["original_flow"])
        hydrated = hydrate(orig_canonical)
        re_canonical = flow_to_canonical(hydrated)

        # Compare
        def typed_edges(c):
            types = {n["id"]: n["type"] for n in c["nodes"]}
            return sorted((types[e["from"]], types[e["to"]], e["conn"]) for e in c["edges"])

        orig_e = typed_edges(orig_canonical)
        re_e = typed_edges(re_canonical)

        match = orig_e == re_e
        print("  {} {} (edges: {} vs {})".format(
            "OK" if match else "!!",
            entry["name"],
            len(orig_e), len(re_e),
        ))
        if not match:
            for e in orig_e:
                if e not in re_e:
                    print("    MISSING: {}.{} -> {}".format(*e))
            for e in re_e:
                if e not in orig_e:
                    print("    EXTRA:   {}.{} -> {}".format(*e))
