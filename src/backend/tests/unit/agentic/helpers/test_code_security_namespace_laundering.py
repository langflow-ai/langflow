"""Restricted module namespaces cannot become ordinary mappings through copies."""

import pytest
from langflow.agentic.helpers.code_security import scan_code_security


@pytest.mark.parametrize(
    ("module", "access"),
    [
        pytest.param("builtins", 'namespace["exec"]("pass")', id="builtin-exec"),
        pytest.param("builtins", 'namespace["open"]("example.txt")', id="builtin-open"),
        pytest.param("os", 'namespace["system"]("ignored")', id="os-system"),
        pytest.param("os", 'namespace["environ"]', id="os-environ"),
    ],
)
@pytest.mark.parametrize(
    "binding",
    [
        pytest.param("namespace = {**vars(module)}", id="dict-unpack"),
        pytest.param("original = vars(module)\nnamespace = {**original}", id="aliased-dict-unpack"),
        pytest.param("namespace = vars(module).copy()", id="mapping-copy"),
        pytest.param("original = vars(module)\nnamespace = original.copy()", id="aliased-mapping-copy"),
        pytest.param("namespace = dict(vars(module))", id="dict-constructor"),
        pytest.param("namespace = [vars(module)][0]", id="list"),
        pytest.param("namespace = (vars(module),)[0]", id="tuple"),
        pytest.param("mappings = [vars(module)]\nnamespace = mappings[0]", id="aliased-list"),
        pytest.param('namespace = {"mapping": vars(module)}["mapping"]', id="nested-dict"),
    ],
)
def test_rejects_restricted_namespace_laundering(module, access, binding):
    code = f"import {module} as module\n{binding}\n{access}"

    result = scan_code_security(code)

    assert result.is_safe is False
    assert result.violations


@pytest.mark.parametrize(
    "code",
    [
        pytest.param('original = {"name": "example"}\ncopy = {**original}\nvalue = copy["name"]', id="dict-unpack"),
        pytest.param('original = {"name": "example"}\ncopy = original.copy()\nvalue = copy["name"]', id="mapping-copy"),
        pytest.param(
            'original = {"name": "example"}\ncopy = dict(original)\nvalue = copy["name"]', id="dict-constructor"
        ),
        pytest.param('value = [{"name": "example"}][0]["name"]', id="list"),
        pytest.param('value = ({"name": "example"},)[0]["name"]', id="tuple"),
        pytest.param('class Record:\n    name = "example"\nvalue = vars(Record)["name"]', id="static-namespace-field"),
    ],
)
def test_preserves_ordinary_mapping_copies_and_static_namespace_reads(code):
    assert scan_code_security(code).is_safe is True
