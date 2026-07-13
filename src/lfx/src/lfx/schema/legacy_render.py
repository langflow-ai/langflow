"""Project the new content_blocks model back onto the release-1.11.0 (v1) wire shape.

The in-memory ``Message`` is the source of truth and carries the new content_blocks
union: groups are tagged ``type="group"``, every node carries ``id``/``contents``,
and an agent's final answer is a trailing top-level ``TextContent``. The v1 API must
keep emitting the exact pre-1.11.0 shape, so these pure helpers run only at the v1
boundary (the v1 read models, ``MessageResponse.from_message``, the v1 event stream,
and the v1 openai-responses consumer). The v2 (AG-UI / workflows) path serializes the
live ``Message`` directly and keeps the new shape, so it must never call these.

Baseline v1 invariants reproduced here:
- ``content_blocks`` holds groups only (baseline never stored a top-level text leaf).
- each group is ``{title, contents, allow_markdown, media_url}`` in that order.
- leaves carry no ``id`` / ``contents`` keys.
- an agent's answer lives inside the "Agent Steps" group as a trailing "Output" leaf.
"""

from __future__ import annotations

import json

_OUTPUT_HEADER = {"title": "Output", "icon": "MessageSquare"}
_AGENT_STEPS_TITLE = "Agent Steps"


def legacy_text(message) -> str:
    """The v1 ``text`` value: always a string. A pending stream/iterator renders as ""."""
    text = message.text
    return text if isinstance(text, str) else ""


def _is_group(block) -> bool:
    if not isinstance(block, dict):
        return False
    if block.get("type") == "group":
        return True
    # A legacy group dict read back from the DB carries no discriminator.
    return "title" in block and "contents" in block and "type" not in block


def _legacy_leaf(node: dict) -> dict:
    # Drop the two additive keys the new model puts on every leaf. ``id`` sat right
    # after ``type`` and ``contents`` right after ``header`` in the new node, so plain
    # deletion leaves the remaining keys in baseline order (type, duration, header, ...).
    return {k: v for k, v in node.items() if k not in ("id", "contents")}


def _legacy_group(block: dict) -> dict:
    return {
        "title": block.get("title"),
        "contents": [_legacy_leaf(c) for c in block.get("contents") or []],
        "allow_markdown": block.get("allow_markdown", True),
        "media_url": block.get("media_url"),
    }


def legacy_content_blocks(blocks) -> list[dict]:
    """Project new-model content_blocks (serialized dicts) onto the v1 shape.

    Groups are kept and rendered legacy; top-level text leaves are dropped because
    baseline never stored one. For an agent message (a group titled "Agent Steps")
    the relocated answer is folded back into that group as the trailing "Output"
    leaf, reproducing baseline. In every other case the answer text is carried by
    the message's ``text`` / ``data["text"]`` and is not re-injected, which keeps
    generic ``.text=`` / multi-group / custom-titled-group messages untouched.

    The agent renderer can also emit a flat, chronological log (interleaved text +
    tool_use leaves with no wrapping group). release-1.11.0 rendered agent steps
    inside an "Agent Steps" group, so reconstruct one here when the top level holds
    a ``tool_use`` leaf and no group exists, otherwise the group-only rule below
    would drop every tool call and leave v1 with an empty content_blocks. The gate
    is ``tool_use`` specifically (the agent-step signal), not "any non-text leaf":
    plain ``from_lc_message`` conversions put top-level ``usage`` / ``media`` /
    ``image`` leaves on ordinary replies, and those must stay text-only on the v1
    wire (a tool-less agent answer likewise carries no steps and projects to []).
    """
    blocks = blocks or []
    groups = [b for b in blocks if _is_group(b)]
    leaves = [b for b in blocks if isinstance(b, dict) and not _is_group(b)]

    if not groups and any(leaf.get("type") == "tool_use" for leaf in leaves):
        return [
            {
                "title": _AGENT_STEPS_TITLE,
                "contents": [_legacy_leaf(leaf) for leaf in leaves],
                "allow_markdown": True,
                "media_url": None,
            }
        ]

    answer = "".join(leaf.get("text", "") for leaf in leaves if leaf.get("type") == "text")

    rendered: list[dict] = []
    folded = False
    for block in groups:
        group = _legacy_group(block)
        if not folded and answer and block.get("title") == _AGENT_STEPS_TITLE:
            # ``duration`` is None on purpose: the new model relocates the answer to a
            # bare top-level TextContent (the text setter builds ``TextContent(text=...)``
            # with no duration), so the answer's timing baseline once stamped on the
            # in-group leaf is simply not present to carry through. This is a faithful
            # projection of what the message holds, not a dropped field.
            group["contents"].append({"type": "text", "duration": None, "header": dict(_OUTPUT_HEADER), "text": answer})
            folded = True
        rendered.append(group)
    return rendered


def project_payload_to_v1(obj):
    """Recursively project every message ``content_blocks`` in a nested payload.

    Used at v1 boundaries that serialize whole run results or stream events (the
    ``/run`` endpoint and its streaming ``end`` event) where messages sit at
    arbitrary depth. Pure: returns a new structure, the live objects are
    untouched. Wherever a dict carries a ``content_blocks`` list it is rendered
    to the legacy v1 shape, and a co-located non-string ``text`` is coerced to "".
    """
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if key == "content_blocks" and isinstance(value, list):
                out[key] = legacy_content_blocks(value)
            else:
                out[key] = project_payload_to_v1(value)
        if isinstance(out.get("content_blocks"), list) and "text" in out and not isinstance(out["text"], str):
            # Reached only when text is non-string (the guard above); v1 text is
            # always a string, so a co-located non-string projects to "".
            out["text"] = ""
        return out
    if isinstance(obj, list):
        return [project_payload_to_v1(item) for item in obj]
    return obj


def render_v1_content_blocks(value):
    """Normalize any content_blocks value to the legacy v1 shape.

    Accepts ``ContentType`` model instances (live ``Message``), serialized dicts
    (a DB-row read), a JSON string, a list mixing those, or ``None``. ``None`` is
    returned unchanged; everything else is normalized to dicts and projected with
    :func:`legacy_content_blocks`. This is the single entry point every v1 wire
    model uses so the projection cannot drift between them.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        return value
    dicts = []
    for block in value:
        if hasattr(block, "model_dump"):
            dicts.append(block.model_dump())
        elif isinstance(block, str):
            dicts.append(json.loads(block))
        else:
            dicts.append(block)
    return legacy_content_blocks(dicts)
