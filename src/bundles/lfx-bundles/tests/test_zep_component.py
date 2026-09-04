"""Unit tests for the tombstoned Zep Chat Memory component (``lfx-bundles``).

``ZepChatMemory`` is legacy (replaced by the Message History component) and its
implementation targeted the zep-python v1 SDK; the pinned ``zep-python==2.0.2``
removed that API, so ``build_message_history`` could never succeed. The
component is now a non-functional stub. These tests pin the stub contract:

* flow identity (component name, display_name, inputs, output wiring) is
  unchanged, so saved flows keep loading and i18n locale keys are unaffected;
* ``build_message_history`` fails with a clear, actionable error -- not the old
  misleading ``pip install zep-python`` ImportError hint;
* the stub never imports ``zep_python``, so the failure mode does not depend on
  which zep-python version happens to be installed.
"""

import ast
import inspect

import pytest
from lfx_bundles.zep import ZepChatMemory
from lfx_bundles.zep import zep as zep_module


@pytest.fixture
def component():
    return ZepChatMemory(
        url="http://localhost:8000",
        api_key="test-api-key",  # pragma: allowlist secret
        api_base_path="api/v1",
        session_id="test-session",
        _session_id="test-run-session",
    )


def test_flow_identity_is_preserved(component):
    # The component name is a flow-identity contract: saved flows reference it and
    # migration_table.json maps it. The deprecation metadata must survive the stub.
    assert ZepChatMemory.name == "ZepChatMemory"
    assert ZepChatMemory.legacy is True
    assert ZepChatMemory.replacement == ["helpers.Memory"]
    assert ZepChatMemory.display_name == "Zep Chat Memory"

    frontend_node = component.to_frontend_node()
    template = frontend_node["data"]["node"]["template"]
    for field in ("url", "api_key", "api_base_path", "session_id"):
        assert field in template
    assert template["url"]["value"] == "http://localhost:8000"

    # Same single Memory output, wired to the same method name.
    assert [(output.name, output.method) for output in component.outputs] == [
        ("memory", "build_message_history"),
    ]


def test_build_raises_actionable_error_not_install_hint(component):
    with pytest.raises(RuntimeError, match="no longer functions") as exc_info:
        component.build_message_history()

    error_text = str(exc_info.value)
    # Points at the designated replacement...
    assert "Message History" in error_text
    # ...and is not the old misleading missing-dependency path.
    assert not isinstance(exc_info.value, ImportError)
    assert "pip install" not in error_text


def test_stub_does_not_import_zep_python():
    tree = ast.parse(inspect.getsource(zep_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    zep_imports = {name for name in imported if name == "zep_python" or name.startswith("zep_python.")}
    assert not zep_imports
