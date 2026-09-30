import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
FASTMCP_CONSTRUCTION_SITES = (
    REPOSITORY_ROOT / "src/lfx/src/lfx/mcp/server.py",
    REPOSITORY_ROOT / "src/backend/base/langflow/agentic/mcp/server.py",
)


@pytest.mark.parametrize(
    "source_path",
    FASTMCP_CONSTRUCTION_SITES,
    ids=lambda path: str(path.relative_to(REPOSITORY_ROOT)),
)
def test_fastmcp_settings_guard_precedes_server_construction(source_path: Path) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    guard_lines: list[int] = []
    construction_lines: list[int] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "ensure_fastmcp_settings_ready":
            guard_lines.append(node.lineno)
        elif node.func.id == "FastMCP":
            construction_lines.append(node.lineno)

    assert construction_lines
    assert guard_lines
    assert min(guard_lines) < min(construction_lines)


@pytest.mark.parametrize(
    "module_name",
    ["lfx.mcp.server", "langflow.agentic.mcp.server"],
)
def test_fastmcp_server_constructs_in_clean_subprocess_without_incomplete_field_warning(module_name: str) -> None:
    """Both import-time server constructors resolve Settings before Pydantic validates it."""
    script = """
import importlib
import sys
import warnings

from mcp.server.fastmcp.server import Settings

try:
    from pydantic.warnings import IncompleteFieldDefinitionWarning
except ImportError:
    # Pydantic releases without the named category use a plain warning. Keep
    # the same regression sensitive to its stable message in those versions.
    warnings.filterwarnings("error", message=r".*incomplete.*field.*definition.*")
else:
    warnings.simplefilter("error", IncompleteFieldDefinitionWarning)

module = importlib.import_module(sys.argv[1])
assert Settings.__pydantic_complete__
assert module.mcp.settings is not None
"""
    environment = os.environ.copy()
    source_paths = (REPOSITORY_ROOT / "src/lfx/src", REPOSITORY_ROOT / "src/backend/base")
    environment["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in source_paths), environment.get("PYTHONPATH", "")]
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["DO_NOT_TRACK"] = "true"

    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, module_name],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
