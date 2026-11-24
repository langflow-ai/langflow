"""Unit tests for exported component code helpers."""

from lfx.utils.flow_code import has_code_lines, normalize_code_for_import


def _flow(value: object, *, field_type: str = "code") -> dict:
    template = {"code": {"type": field_type, "value": value}}
    return {"data": {"nodes": [{"id": "n1", "data": {"node": {"template": template}}}], "edges": []}}


def test_has_code_lines_detects_exported_code_in_both_payload_shapes():
    exported = _flow(["line one", "line two", ""])

    assert has_code_lines(exported)
    assert has_code_lines(exported["data"])
    assert not has_code_lines(normalize_code_for_import(exported))


def test_has_code_lines_ignores_string_code_and_other_list_fields():
    assert not has_code_lines(_flow("line one\n"))
    assert not has_code_lines(_flow(["a", "b"], field_type="str"))
    assert not has_code_lines({"data": {"nodes": "not a list"}})
