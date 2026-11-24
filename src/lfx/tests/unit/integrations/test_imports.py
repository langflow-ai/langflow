"""Connection schemas must not add provider client or telemetry imports."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["lfx.integrations", "lfx.extension.manifest", "lfx.inputs.input_mixin"])
def test_schema_imports_do_not_load_mcp_or_observability(module: str) -> None:
    result = subprocess.run(  # noqa: S603 - fixed interpreter and parametrized local module names
        [
            sys.executable,
            "-c",
            "import importlib, sys; "
            f"importlib.import_module({module!r}); "
            "assert 'mcp' not in sys.modules; "
            "assert 'lfx.base.mcp.util' not in sys.modules; "
            + (
                "assert 'lfx.observability' not in sys.modules; assert 'langchain_core' not in sys.modules"
                if module != "lfx.inputs.input_mixin"
                else ""  # Inputs already import observability on the release base.
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_public_exports_remain_available() -> None:
    from lfx import integrations

    for name in integrations.__all__:
        assert getattr(integrations, name) is not None
    with pytest.raises(AttributeError):
        _ = integrations.not_a_public_contract
