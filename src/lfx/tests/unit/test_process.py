"""Tests for lfx.processing.process.apply_tweaks.

These mirror the langflow-side regression tests in
``src/backend/tests/unit/test_process.py`` so the two copies of ``apply_tweaks``
(``langflow.processing.process`` used by the API and ``lfx.processing.process``)
cannot drift. They guard the Tweaks-API code-injection gate (CWE-94): a tweak must
never override an executable/sandbox input, while leaving benign fields tweakable.
"""

from __future__ import annotations

from unittest.mock import patch

from lfx.processing.process import apply_tweaks


def _template_node(template: dict, *, node_type: str | None = None) -> dict:
    data: dict = {"node": {"template": template}}
    if node_type is not None:
        data["type"] = node_type
    return {"id": "n", "data": data}


def test_apply_tweaks_applies_ordinary_field():
    """Sanity: a plain field on a non-code component is overridden as usual."""
    node = _template_node({"param1": {"value": "old", "type": "str"}})
    apply_tweaks(node, {"param1": "new"})
    assert node["data"]["node"]["template"]["param1"]["value"] == "new"


def test_apply_tweaks_blocks_code_named_field():
    """The literal 'code' field is blocked, and the warning names the field."""
    node = _template_node({"code": {"value": "original_code", "type": "code"}})

    with patch("lfx.processing.process.logger") as mock_logger:
        apply_tweaks(node, {"code": "attempted_injection"})
        mock_logger.warning.assert_called_once_with("Security: refusing to override code field 'code' via tweaks.")

    assert node["data"]["node"]["template"]["code"]["value"] == "original_code"


def test_apply_tweaks_blocks_code_type_field_with_other_name():
    """A code-injection bypass: a field of type 'code' but named something other than 'code'."""
    node = _template_node(
        {
            "custom_source": {"value": "original", "type": "code"},
            "param1": {"value": "ok", "type": "str"},
        }
    )
    apply_tweaks(node, {"custom_source": "import os; os.system('id')", "param1": "new"})

    assert node["data"]["node"]["template"]["custom_source"]["value"] == "original"
    assert node["data"]["node"]["template"]["param1"]["value"] == "new"


def test_apply_tweaks_blocks_python_interpreter_code_and_imports():
    """python_code (exec input) and global_imports (sandbox allow-list) stay blocked.

    Both are MultilineInput/StrInput → template type 'str', so they are caught by the
    component-type + field-name guard, not by field_type=='code'.
    """
    node = _template_node(
        {
            "python_code": {"value": "print('safe')", "type": "str"},
            "global_imports": {"value": "math", "type": "str"},
        },
        node_type="PythonREPLComponent",
    )
    apply_tweaks(node, {"python_code": "__import__('os').system('id')", "global_imports": "os,subprocess"})

    assert node["data"]["node"]["template"]["python_code"]["value"] == "print('safe')"
    assert node["data"]["node"]["template"]["global_imports"]["value"] == "math"


def test_apply_tweaks_allows_benign_fields_on_code_execution_component():
    """Scoped block: name/description on a Python REPL tool remain tweakable."""
    node = _template_node(
        {
            "name": {"value": "old_name", "type": "str"},
            "description": {"value": "old desc", "type": "str"},
            "code": {"value": "print('safe')", "type": "str"},
        },
        node_type="PythonREPLTool",
    )
    apply_tweaks(node, {"name": "new_name", "description": "new desc", "code": "__import__('os').system('id')"})

    assert node["data"]["node"]["template"]["name"]["value"] == "new_name"
    assert node["data"]["node"]["template"]["description"]["value"] == "new desc"
    assert node["data"]["node"]["template"]["code"]["value"] == "print('safe')"


def test_apply_tweaks_blocks_removed_python_code_structured_tool_code():
    """The removed PythonCodeStructuredTool's exec input 'tool_code' (type 'str') stays blocked."""
    node = _template_node(
        {"tool_code": {"value": "stored_code", "type": "str"}},
        node_type="PythonCodeStructuredTool",
    )
    apply_tweaks(node, {"tool_code": "__import__('os').system('id')"})

    assert node["data"]["node"]["template"]["tool_code"]["value"] == "stored_code"


def test_apply_tweaks_smart_transform_blocks_instruction_allows_data():
    """Smart Transform's filter_instruction drives an eval()'d lambda → blocked; data is not."""
    node = _template_node(
        {
            "filter_instruction": {"value": "uppercase the text", "type": "str"},
            "sample_size": {"value": 10, "type": "int"},
        },
        node_type="Smart Transform",
    )
    apply_tweaks(node, {"filter_instruction": "lambda x: __import__('os').system('id')", "sample_size": 25})

    assert node["data"]["node"]["template"]["filter_instruction"]["value"] == "uppercase the text"
    assert node["data"]["node"]["template"]["sample_size"]["value"] == 25
