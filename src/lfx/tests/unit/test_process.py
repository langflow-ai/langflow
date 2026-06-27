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
from lfx.utils.flow_validation import CODE_EXECUTION_COMPONENT_TYPES, CODE_EXECUTION_FIELD_NAMES


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


def test_apply_tweaks_blocks_csv_agent_dangerous_code_flag():
    """CSVAgent's LangChain Python-execution opt-in is a sandbox boundary."""
    node = _template_node(
        {
            "allow_dangerous_code": {"value": False, "type": "bool"},
            "input_value": {"value": "summarize", "type": "str"},
        },
        node_type="CSVAgent",
    )
    apply_tweaks(node, {"allow_dangerous_code": True, "input_value": "count rows"})

    assert node["data"]["node"]["template"]["allow_dangerous_code"]["value"] is False
    assert node["data"]["node"]["template"]["input_value"]["value"] == "count rows"


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


# The intended code/sandbox inputs for code-execution component types that expose
# such fields in their templates, kept independently from the production sets so
# this test acts as a checksum on the comment-only sync between
# CODE_EXECUTION_COMPONENT_TYPES and CODE_EXECUTION_FIELD_NAMES (see
# lfx/utils/flow_validation.py). "code" is the conventional exec input that
# apply_tweaks() blocks globally by name, so it is allowed here without being
# listed in CODE_EXECUTION_FIELD_NAMES.
#   - CSVAgent: allow_dangerous_code enables LangChain Python execution
#   - PythonREPLComponent (Python Interpreter): python_code exec + global_imports sandbox
#   - PythonREPLTool (Python REPL): code exec (global block) + global_imports sandbox
#   - Smart Transform (LambdaFilterComponent): filter_instruction → eval()'d lambda
#   - PythonCodeStructuredTool (removed): tool_code exec input, type retained
_EXPECTED_CODE_FIELDS_BY_TYPE: dict[str, set[str]] = {
    "CSVAgent": {"allow_dangerous_code"},
    "PythonREPLComponent": {"python_code", "global_imports"},
    "PythonREPLTool": {"code", "global_imports"},
    "Smart Transform": {"filter_instruction"},
    "PythonCodeStructuredTool": {"tool_code"},
}

# Code-execution components with no tweakable code/sandbox field. They are still
# blocked on unauthenticated public builds by CODE_EXECUTION_COMPONENT_TYPES.
_CODE_EXECUTION_TYPES_WITHOUT_TWEAK_CODE_FIELDS = {
    "CodeActAgentSmolagents",
    "Cuga",
    "OpenDsStarAgent",
}

# Field name globally blocked by apply_tweaks() regardless of component type.
_GLOBALLY_BLOCKED_FIELD = "code"


def test_every_code_execution_type_has_registered_code_fields():
    """Tripwire: each registered code-exec type must declare its code fields here.

    Forcing function for the next code-execution component: adding a type to
    CODE_EXECUTION_COMPONENT_TYPES without either registered code/sandbox fields
    or an explicit no-field entry fails immediately. This keeps the by-name half
    of the guard from silently going stale, since the component classes themselves
    aren't importable in this unit env (optional deps).
    """
    expected_component_types = set(_EXPECTED_CODE_FIELDS_BY_TYPE) | _CODE_EXECUTION_TYPES_WITHOUT_TWEAK_CODE_FIELDS
    assert expected_component_types == set(CODE_EXECUTION_COMPONENT_TYPES), (
        "CODE_EXECUTION_COMPONENT_TYPES changed without updating _EXPECTED_CODE_FIELDS_BY_TYPE. "
        "Register the new component's code/sandbox input field name(s), or explicitly mark it as a "
        "runtime code-execution component with no tweakable code/sandbox fields."
    )

    covered = set(CODE_EXECUTION_FIELD_NAMES) | {_GLOBALLY_BLOCKED_FIELD}
    for component_type, code_fields in _EXPECTED_CODE_FIELDS_BY_TYPE.items():
        missing = code_fields - covered
        assert not missing, (
            f"{component_type} exposes executable/sandbox field(s) {sorted(missing)} that the Tweaks "
            f"guard would not block. Add them to CODE_EXECUTION_FIELD_NAMES in lfx/utils/flow_validation.py."
        )


def test_no_unclaimed_code_execution_field_names():
    """Every CODE_EXECUTION_FIELD_NAMES entry must belong to a known code-exec type.

    Guards against a stale frozenset entry left behind after a component is
    removed or renamed (the inverse of the tripwire above).
    """
    claimed = set().union(*_EXPECTED_CODE_FIELDS_BY_TYPE.values())
    unclaimed = set(CODE_EXECUTION_FIELD_NAMES) - claimed
    assert not unclaimed, (
        f"CODE_EXECUTION_FIELD_NAMES has entries {sorted(unclaimed)} not claimed by any code-execution "
        "component type. Remove them or register the owning type in _EXPECTED_CODE_FIELDS_BY_TYPE."
    )
