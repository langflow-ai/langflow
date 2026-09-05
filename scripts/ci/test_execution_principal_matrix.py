from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_execution_principal_matrix import DEFAULT_MATRIX, REQUIRED_DIMENSIONS, validate_matrix

CI_SCRIPTS_WORKFLOW = DEFAULT_MATRIX.parents[2] / ".github" / "workflows" / "ci-scripts-test.yml"
EXECUTION_PRINCIPAL_MODULE = (
    DEFAULT_MATRIX.parents[2] / "src" / "backend" / "base" / "langflow" / "api" / "utils" / "execution_principal.py"
)


def _load_execution_principal_module():
    """Import the runtime family table without importing the langflow package.

    The CI-scripts job installs only jsonschema/orjson/packaging/pytest/requests,
    so ``import langflow`` is not available here; the module itself imports one
    lfx symbol, which is stubbed for the same reason.

    The stub is installed ONLY when lfx is genuinely absent. Guarding on the real
    package rather than on the submodule key keeps this safe if these tests are
    ever collected in the same session as the backend suite, where shadowing
    ``lfx.services.authorization.base`` would break every later importer.
    """
    import sys
    import types
    import uuid
    from importlib import util
    from importlib.util import find_spec

    def _lfx_is_importable() -> bool:
        if "lfx" in sys.modules:
            return True
        try:
            return find_spec("lfx") is not None
        except (ImportError, ValueError):
            return False

    if not _lfx_is_importable():
        for name in ("lfx", "lfx.services", "lfx.services.authorization"):
            sys.modules.setdefault(name, types.ModuleType(name))
        stub = types.ModuleType("lfx.services.authorization.base")
        stub.PUBLIC_ANONYMOUS_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "urn:langflow:principal:anonymous-public")

        class ExecutionPrincipal:  # minimal stand-in; only the table is under test
            def __init__(self, **kwargs) -> None:
                self.__dict__.update(kwargs)

        stub.ExecutionPrincipal = ExecutionPrincipal
        sys.modules["lfx.services.authorization.base"] = stub

    spec = util.spec_from_file_location("_langflow_execution_principal", EXECUTION_PRINCIPAL_MODULE)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    # Register before exec: @dataclass resolves string annotations through
    # ``sys.modules[cls.__module__]``, which is absent for a hand-loaded module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _workflow_pull_request_paths() -> list[str]:
    """Read the quoted pull-request path filters without adding a YAML dependency."""
    workflow = CI_SCRIPTS_WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("    paths:\n") == 1, "expected exactly one pull-request paths block"
    assert "  workflow_dispatch:" in workflow, "expected workflow_dispatch to terminate the paths block"
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    entries = [line.strip().removeprefix("- ") for line in paths_block.splitlines() if line.strip()]
    for entry in entries:
        assert entry.startswith('"'), f"path filter must start with a double quote: {entry}"
        assert entry.endswith('"'), f"path filter must end with a double quote: {entry}"
    return [json.loads(entry) for entry in entries]


def _github_path_matches(path: str, pattern: str) -> bool:
    """Match the ``*`` and ``**`` forms used by this workflow's path filters."""
    regex_parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern[index : index + 2] == "**":
            regex_parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            regex_parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            regex_parts.append("[^/]")
            index += 1
        else:
            regex_parts.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(regex_parts), path) is not None


def test_execution_principal_matrix_is_complete() -> None:
    assert validate_matrix() == []


def test_every_entrypoint_declares_each_principal_and_safety_dimension() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))

    for entrypoint in matrix["entrypoints"]:
        assert set(entrypoint) >= REQUIRED_DIMENSIONS
        assert entrypoint["test_references"]


def test_ci_workflow_watches_every_canonical_source_and_test_reference() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    workflow_paths = _workflow_pull_request_paths()
    canonical_paths = {entrypoint["source"] for entrypoint in matrix["entrypoints"]} | {
        reference.split("::", 1)[0]
        for entrypoint in matrix["entrypoints"]
        for reference in entrypoint["test_references"]
    }

    uncovered = sorted(
        path for path in canonical_paths if not any(_github_path_matches(path, pattern) for pattern in workflow_paths)
    )
    assert uncovered == [], f"CI scripts checker is not triggered by canonical matrix paths: {uncovered}"


def test_checker_rejects_a_missing_error_policy(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0].pop("error_policy")
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    assert any("error_policy" in error and "missing" in error for error in validate_matrix(incomplete))


def test_checker_reports_missing_matrix_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    assert validate_matrix(missing) == [
        f"could not read execution-principal matrix {missing}: [Errno 2] No such file or directory: '{missing}'"
    ]


def test_checker_reports_malformed_matrix_json(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    errors = validate_matrix(malformed)

    assert len(errors) == 1
    assert "is not valid JSON" in errors[0]
    assert str(malformed) in errors[0]


def test_checker_rejects_generic_non_behavioral_test_references(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    generic_references = {
        "v1_run": "src/backend/tests/unit/api/v1/test_endpoints.py::test_get_config_basic",
        "webhook": "src/backend/tests/unit/api/v1/test_endpoints.py::test_get_version",
    }
    for entrypoint in source["entrypoints"]:
        if entrypoint["family"] in generic_references:
            entrypoint["test_references"] = [generic_references[entrypoint["family"]]]
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(incomplete)
    assert any("v1_run" in error and "behavior-specific" in error for error in errors)
    assert any("webhook" in error and "behavior-specific" in error for error in errors)


def test_checker_rejects_a_missing_connection_resolution(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0].pop("connection_resolution")
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    assert any("connection_resolution" in error and "missing" in error for error in validate_matrix(incomplete))


def test_checker_rejects_an_unknown_connection_resolution(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0]["connection_resolution"] = "sometimes"
    unknown = tmp_path / "execution-principal-matrix.json"
    unknown.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(unknown)

    assert any("unknown connection_resolution 'sometimes'" in error for error in errors)


def test_checker_rejects_an_anonymous_family_that_resolves_a_connection(tmp_path: Path) -> None:
    """The rule the ticket states outright: public/A2A/anonymous resolve nothing."""
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    for entrypoint in source["entrypoints"]:
        if entrypoint["dependency_principal"] == "anonymous_public":
            entrypoint["connection_resolution"] = "owner_or_explicit_share"
    mismatched = tmp_path / "execution-principal-matrix.json"
    mismatched.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(mismatched)

    assert any("pairs dependency_principal 'anonymous_public'" in error and "'never'" in error for error in errors)


def test_checker_rejects_a_flow_owner_family_without_the_non_interactive_opt_in(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    for entrypoint in source["entrypoints"]:
        if entrypoint["family"] == "webhook":
            entrypoint["connection_resolution"] = "owner_or_explicit_share"
    mismatched = tmp_path / "execution-principal-matrix.json"
    mismatched.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(mismatched)

    assert any("'webhook'" in error and "owner_non_interactive_opt_in" in error for error in errors)


def test_checker_requires_a_connection_test_reference_for_the_webhook_family(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    for entrypoint in source["entrypoints"]:
        if entrypoint["family"] == "webhook":
            entrypoint["test_references"] = [
                reference for reference in entrypoint["test_references"] if "connection" not in reference
            ]
    stripped = tmp_path / "execution-principal-matrix.json"
    stripped.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(stripped)

    assert any("'webhook'" in error and "behavior-specific" in error and "connection" in error for error in errors)


def test_checker_requires_prose_for_every_connection_rule(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0]["connection_resolution_note"] = "   "
    blank = tmp_path / "execution-principal-matrix.json"
    blank.write_text(json.dumps(source), encoding="utf-8")

    assert any("must explain its connection_resolution" in error for error in validate_matrix(blank))


def test_matrix_connection_rules_match_the_runtime_family_table() -> None:
    """The matrix and ``api/utils/execution_principal.py`` are one contract.

    The matrix is the reviewable document and the table is what actually runs;
    a change to either without the other is the drift this test exists to stop.
    """
    execution_principal = _load_execution_principal_module()
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))

    from_matrix = {entrypoint["family"]: entrypoint["connection_resolution"] for entrypoint in matrix["entrypoints"]}

    assert from_matrix == execution_principal.CONNECTION_RESOLUTION_BY_FAMILY
    assert set(from_matrix) == execution_principal.EXECUTION_FAMILIES
