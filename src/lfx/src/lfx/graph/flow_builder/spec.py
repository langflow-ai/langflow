"""Parse compact flow spec text into a structured dict.

Format:
    name: My Flow
    description: What it does

    nodes:
      A: ChatInput
      B: OpenAIModel
      C: ChatOutput

    edges:
      A.message -> B.input_value
      B.text_output -> C.input_value

    config:
      B.model_name: gpt-4o
      B.temperature: 0.5
      C.system_prompt: |
        Multi-line value
        continues here.

Config values are auto-coerced: numbers become int/float, true/false
become booleans. Multi-line values (starting with ``|``) stay as
strings. Continuation lines are dedented by up to 4 leading spaces.
"""

from __future__ import annotations

import re

_CONFIG_KEY_RE = re.compile(r"^(\w+\.\w+): (.*)$")


def _coerce_value(v: str):
    """Coerce a string value to int, float, bool, or None if applicable."""
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() in ("null", "none"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def parse_flow_spec(text: str) -> dict:
    """Parse a flow spec string into a structured dict.

    Returns:
        {
            "name": str,
            "description": str,
            "nodes": [{"id": "A", "type": "ChatInput"}, ...],
            "edges": [{"source_id": "A", "source_output": "message",
                        "target_id": "B", "target_input": "input_value"}, ...],
            "config": {"A": {"field": value, ...}, ...},
        }
    """
    lines = text.strip().split("\n")

    result: dict = {
        "name": "",
        "description": "",
        "nodes": [],
        "edges": [],
        "config": {},
    }

    section: str | None = None
    current_config_key: str | None = None
    current_config_lines: list[str] = []
    current_config_is_multiline: bool = False
    config_key_indent: int | None = None  # indent level of config keys

    def _flush_config():
        nonlocal current_config_key, current_config_lines, current_config_is_multiline
        if current_config_key and current_config_lines:
            node_id, field = current_config_key.split(".", 1)
            raw = "\n".join(current_config_lines).strip()
            value = raw if current_config_is_multiline else _coerce_value(raw)
            result["config"].setdefault(node_id, {})[field] = value
        current_config_key = None
        current_config_lines = []
        current_config_is_multiline = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            if section == "config" and current_config_key:
                current_config_lines.append("")
            continue

        # Top-level keys
        if line == "nodes:":
            _flush_config()
            section = "nodes"
            continue
        if line == "edges:":
            _flush_config()
            section = "edges"
            continue
        if line == "config:":
            _flush_config()
            section = "config"
            continue

        if section is None:
            if line.startswith("name:"):
                result["name"] = line[5:].strip()
            elif line.startswith("description:"):
                result["description"] = line[12:].strip()
            else:
                msg = f"Unrecognized line: '{line}'. Expected 'name:', 'description:', or a section header."
                raise ValueError(msg)
            continue

        _expected_split_parts = 2

        if section == "nodes":
            # "A: ChatInput"
            parts = line.split(":", 1)
            if len(parts) != _expected_split_parts:
                msg = f"Invalid node definition: '{line}'. Expected format: 'ID: ComponentType'"
                raise ValueError(msg)
            result["nodes"].append(
                {
                    "id": parts[0].strip(),
                    "type": parts[1].strip(),
                }
            )

        elif section == "edges":
            # "A.message -> B.input_value"
            if " -> " not in line:
                msg = f"Invalid edge definition: '{line}'. Expected format: 'Node.output -> Node.input'"
                raise ValueError(msg)
            left, right = line.split(" -> ", 1)
            src_parts = left.strip().split(".", 1)
            tgt_parts = right.strip().split(".", 1)
            if len(src_parts) != _expected_split_parts or len(tgt_parts) != _expected_split_parts:
                msg = f"Invalid edge definition: '{line}'. Both sides must be 'Node.port'"
                raise ValueError(msg)
            result["edges"].append(
                {
                    "source_id": src_parts[0],
                    "source_output": src_parts[1],
                    "target_id": tgt_parts[0],
                    "target_input": tgt_parts[1],
                }
            )

        elif section == "config":
            # Determine indentation of this line
            line_indent = len(raw_line) - len(raw_line.lstrip())

            # In multiline mode, lines indented deeper than the key level
            # are continuations, not new keys.
            is_continuation = (
                current_config_is_multiline and config_key_indent is not None and line_indent > config_key_indent
            )

            if not is_continuation:
                match = _CONFIG_KEY_RE.match(line)
                if match:
                    _flush_config()
                    if config_key_indent is None:
                        config_key_indent = line_indent
                    current_config_key = match.group(1)
                    value = match.group(2)
                    current_config_lines = []
                    if value == "|":
                        current_config_is_multiline = True
                    elif value:
                        current_config_lines.append(value)
                    continue
                if not current_config_key:
                    msg = f"Invalid config entry: '{line}'. Expected format: 'Node.field: value'"
                    raise ValueError(msg)

            # Continuation of multi-line value
            if current_config_key:
                # Preserve relative indentation (strip up to 4 leading spaces)
                stripped = raw_line
                for _ in range(4):
                    stripped = stripped.removeprefix(" ")
                current_config_lines.append(stripped)

    _flush_config()

    if not result["nodes"]:
        msg = "No nodes found in spec. Expected 'nodes:' section with 'ID: Type' entries."
        raise ValueError(msg)

    return result


def validate_spec_references(parsed: dict) -> None:
    """Validate that all edge and config references point to existing nodes.

    This is extracted as a shared function because the same validation
    is needed in create_flow_from_spec, update_flow_from_spec, and
    build_flow_from_spec. Keeping it in one place prevents the three
    copies from drifting out of sync.

    Raises:
        ValueError: If any reference points to an unknown node.
    """
    node_ids = {n["id"] for n in parsed.get("nodes", [])}
    for spec_id in parsed.get("config", {}):
        if spec_id not in node_ids:
            msg = f"Config references unknown node '{spec_id}'. Available: {sorted(node_ids)}"
            raise ValueError(msg)
    for edge in parsed.get("edges", []):
        if edge["source_id"] not in node_ids:
            msg = f"Edge references unknown source '{edge['source_id']}'. Available: {sorted(node_ids)}"
            raise ValueError(msg)
        if edge["target_id"] not in node_ids:
            msg = f"Edge references unknown target '{edge['target_id']}'. Available: {sorted(node_ids)}"
            raise ValueError(msg)
