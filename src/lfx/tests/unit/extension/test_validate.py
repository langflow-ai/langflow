"""Tests for ``lfx.extension.validate.validate_extension``.

Coverage targets:
    - schema validation (delegated to test_manifest, smoke-checked here).
    - path-safety (no ``..``, absolute, or symlink-escape).
    - AST inspection: syntax, Component subclass present, build() declared,
      reject top-level ``import *``, flag top-level I/O primitives.
    - default validate runs under 100ms on the basic template.
    - crafted bundle with malicious top-level side effect: default validate
      does NOT trigger it; --execute-imports DOES, in a subprocess, with
      a detectable canary.
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

import pytest
from lfx.extension.errors import ERROR_CODES
from lfx.extension.validate import validate_extension

if TYPE_CHECKING:
    from pathlib import Path

_BASE_MANIFEST = {
    "id": "lfx-openai",
    "version": "1.2.3",
    "name": "OpenAI Bundle",
    "lfx": {"compat": ["1"]},
    "bundles": [{"name": "openai", "path": "openai"}],
}


def _component_source(*, with_build: bool = True) -> str:
    """Minimal Component-shaped source.

    Self-contained so the subprocess used by --execute-imports does not need
    langflow installed.
    """
    body = "    def build(self):\n        return None\n" if with_build else "    pass\n"
    return f"class Component:\n    pass\n\nclass OpenAIThing(Component):\n    display_name = 'X'\n{body}"


def _make_bundle(
    tmp_path: Path,
    *,
    manifest: dict | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """Lay out a synthetic extension at ``tmp_path``."""
    manifest = manifest if manifest is not None else _BASE_MANIFEST
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle_dir = tmp_path / manifest["bundles"][0]["path"]
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = files if files is not None else {"text.py": _component_source()}
    for name, source in files.items():
        target = bundle_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return tmp_path


def _codes(report) -> list[str]:
    return [e.code for e in report.errors.errors]


# ---------------------------------------------------------------------------
# Pass 1: discovery + schema
# ---------------------------------------------------------------------------


def test_missing_manifest_emits_manifest_not_found(tmp_path: Path) -> None:
    report = validate_extension(tmp_path)
    assert not report.ok
    assert _codes(report) == ["manifest-not-found"]


def test_invalid_json_emits_manifest_invalid(tmp_path: Path) -> None:
    (tmp_path / "extension.json").write_text("{not json", encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["manifest-invalid"]


def test_invalid_pyproject_emits_manifest_invalid(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[bad toml", encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["manifest-invalid"]


def test_schema_violation_emits_manifest_invalid(tmp_path: Path) -> None:
    bad = {**_BASE_MANIFEST, "id": "BAD_ID"}
    (tmp_path / "extension.json").write_text(json.dumps(bad), encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["manifest-invalid"]


def test_deferred_field_emits_dedicated_code(tmp_path: Path) -> None:
    bad = {**_BASE_MANIFEST, "services": {"foo": "bar"}}
    (tmp_path / "extension.json").write_text(json.dumps(bad), encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["field-deferred-in-this-milestone"]
    assert report.errors.errors[0].content == "services"


def test_multi_bundle_emits_dedicated_code(tmp_path: Path) -> None:
    bad = {
        **_BASE_MANIFEST,
        "bundles": [
            {"name": "a", "path": "a"},
            {"name": "b", "path": "b"},
        ],
    }
    (tmp_path / "extension.json").write_text(json.dumps(bad), encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["multi-bundle-unsupported"]


# ---------------------------------------------------------------------------
# Pass 2: path-safety
# ---------------------------------------------------------------------------


def test_bundle_path_not_found(tmp_path: Path) -> None:
    (tmp_path / "extension.json").write_text(json.dumps(_BASE_MANIFEST), encoding="utf-8")
    report = validate_extension(tmp_path)
    assert _codes(report) == ["bundle-path-not-found"]


@pytest.mark.skipif(os.name == "nt", reason="symlinks unreliable on Windows CI")
def test_symlink_escape_flagged(tmp_path: Path) -> None:
    _make_bundle(tmp_path)
    bundle = tmp_path / "openai"
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    try:
        (bundle / "escape_link.py").symlink_to(outside / "anything.py")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported in this environment")
    report = validate_extension(tmp_path)
    assert "path-escape" in _codes(report)


# ---------------------------------------------------------------------------
# Pass 3: AST inspection
# ---------------------------------------------------------------------------


def test_happy_path_passes(tmp_path: Path) -> None:
    _make_bundle(tmp_path)
    report = validate_extension(tmp_path)
    assert report.ok, _codes(report)
    assert report.bundle_files_scanned == 1
    assert report.manifest is not None


def test_syntax_error_flagged(tmp_path: Path) -> None:
    _make_bundle(tmp_path, files={"broken.py": "def oops(:\n"})
    report = validate_extension(tmp_path)
    assert "syntax-error" in _codes(report)


def test_no_component_subclass_flagged(tmp_path: Path) -> None:
    _make_bundle(tmp_path, files={"x.py": "x = 1\n"})
    report = validate_extension(tmp_path)
    assert "no-component-subclass" in _codes(report)


def test_build_method_missing_flagged(tmp_path: Path) -> None:
    _make_bundle(tmp_path, files={"text.py": _component_source(with_build=False)})
    report = validate_extension(tmp_path)
    assert "build-method-missing" in _codes(report)


def test_output_method_satisfies_invocable_check(tmp_path: Path) -> None:
    """A class with ``Output(method="X")`` + ``def X`` is invocable without literal ``build``.

    Mirrors the production duckduckgo / arxiv bundles, which declare their
    entry-point via ``outputs = [Output(method="...")]`` rather than a
    literal ``build`` method.  The validator must accept this shape;
    flagging it would force every modern Component to add a vestigial
    ``build`` stub.
    """
    src = (
        "class Component:\n"
        "    pass\n\n"
        "class Output:\n"
        "    def __init__(self, **kwargs):\n"
        "        pass\n\n"
        "class OpenAIThing(Component):\n"
        "    display_name = 'X'\n"
        "    outputs = [Output(name='dataframe', method='fetch_content_dataframe')]\n\n"
        "    def fetch_content_dataframe(self):\n"
        "        return None\n"
    )
    _make_bundle(tmp_path, files={"text.py": src})
    report = validate_extension(tmp_path)
    assert "build-method-missing" not in _codes(report), report.errors.errors


def test_output_method_without_matching_def_still_flagged(tmp_path: Path) -> None:
    """``Output(method="X")`` without a ``def X`` does NOT satisfy the check.

    Defense-in-depth: the static check passes only when the named method
    actually exists on the class.  A typo'd method name would otherwise
    sneak past the validator and crash at run-time.
    """
    src = (
        "class Component:\n"
        "    pass\n\n"
        "class Output:\n"
        "    def __init__(self, **kwargs):\n"
        "        pass\n\n"
        "class OpenAIThing(Component):\n"
        "    display_name = 'X'\n"
        "    outputs = [Output(name='dataframe', method='typo_doesnt_exist')]\n"
    )
    _make_bundle(tmp_path, files={"text.py": src})
    report = validate_extension(tmp_path)
    assert "build-method-missing" in _codes(report)


def test_import_star_flagged(tmp_path: Path) -> None:
    src = "from os.path import *\n" + _component_source()
    _make_bundle(tmp_path, files={"text.py": src})
    report = validate_extension(tmp_path)
    assert "import-star-disallowed" in _codes(report)


@pytest.mark.parametrize(
    "io_call",
    [
        "open('/etc/passwd').read()",
        "import socket\nsocket.socket()",
        "import subprocess\nsubprocess.run(['echo'])",
        "import os\nos.system('echo hi')",
    ],
)
def test_top_level_io_flagged(tmp_path: Path, io_call: str) -> None:
    src = f"{io_call}\n{_component_source()}"
    _make_bundle(tmp_path, files={"text.py": src})
    report = validate_extension(tmp_path)
    assert "top-level-io-disallowed" in _codes(report)


def test_io_inside_function_body_not_flagged(tmp_path: Path) -> None:
    """I/O inside a function does NOT execute on import; should NOT trigger."""
    src = (
        "class Component:\n"
        "    pass\n"
        "\n"
        "def helper():\n"
        "    open('/etc/passwd')\n"
        "\n"
        "class OpenAIThing(Component):\n"
        "    def build(self):\n"
        "        return None\n"
    )
    _make_bundle(tmp_path, files={"text.py": src})
    report = validate_extension(tmp_path)
    assert report.ok, _codes(report)


def test_empty_bundle_flagged(tmp_path: Path) -> None:
    (tmp_path / "extension.json").write_text(json.dumps(_BASE_MANIFEST), encoding="utf-8")
    (tmp_path / "openai").mkdir()
    report = validate_extension(tmp_path)
    assert "bundle-empty" in _codes(report)


# ---------------------------------------------------------------------------
# Pass 4: --execute-imports
# ---------------------------------------------------------------------------


def test_default_validate_does_not_execute_malicious_side_effect(tmp_path: Path) -> None:
    """A bundle module that writes a canary file MUST NOT be executed by default.

    This is the security invariant: even if the manifest is otherwise valid
    and the AST passes (because the side effect is wrapped in a user function),
    the bundle's own code MUST NOT run during a default validate.
    """
    canary = tmp_path / "canary.txt"
    # The side effect is intentionally NOT one of the AST-flagged primitives;
    # it's a user function that writes a file.  AST inspection cannot see
    # through the function call, but default validate must still not execute
    # the module.
    src = (
        "from pathlib import Path\n"
        f"def _trigger():\n"
        f"    Path({str(canary)!r}).write_text('triggered', encoding='utf-8')\n"
        "_trigger()\n" + _component_source()
    )
    _make_bundle(tmp_path, files={"text.py": src})
    validate_extension(tmp_path)
    assert not canary.exists(), "default validate must NOT execute bundle code"


def test_execute_imports_runs_in_subprocess_and_isolates_state(tmp_path: Path) -> None:
    """Subprocess runs the bundle but does not inherit langflow server state.

    Two assertions:

    1. A canary written by the bundle's import-time code DOES appear (proving
       the subprocess actually ran the module).
    2. The subprocess does NOT inherit LANGFLOW_* env vars from the parent.
    """
    canary = tmp_path / "canary.txt"
    secret_canary = tmp_path / "leaked_state.txt"
    src = (
        "import os\n"
        "from pathlib import Path\n"
        f"Path({str(canary)!r}).write_text('triggered', encoding='utf-8')\n"
        f"# Should be empty since LANGFLOW_* is filtered out:\n"
        f"_state = os.environ.get('LANGFLOW_DATABASE_URL', '')\n"
        f"if _state:\n"
        f"    Path({str(secret_canary)!r}).write_text(_state, encoding='utf-8')\n"
    )
    # Use a non-Component file so the AST pass passes (no Component required
    # in side-effect modules).  Add a sibling component to satisfy the
    # has-Component-subclass check.
    _make_bundle(
        tmp_path,
        files={
            "side_effect.py": src,
            "component.py": _component_source(),
        },
    )
    os.environ["LANGFLOW_DATABASE_URL"] = "sqlite:///parent-state"
    try:
        report = validate_extension(tmp_path, execute_imports=True)
    finally:
        os.environ.pop("LANGFLOW_DATABASE_URL", None)

    # The subprocess actually ran the side-effect module:
    assert canary.exists(), f"--execute-imports must invoke the bundle's modules. Got errors: {_codes(report)}"
    # ...but did not inherit langflow server state:
    assert not secret_canary.exists(), "--execute-imports leaked LANGFLOW_* env vars into the bundle subprocess"


def test_execute_imports_reports_failure(tmp_path: Path) -> None:
    src = "raise RuntimeError('boom')\n"
    _make_bundle(
        tmp_path,
        files={"failing.py": src, "component.py": _component_source()},
    )
    report = validate_extension(tmp_path, execute_imports=True)
    assert "execute-imports-failed" in _codes(report)


# ---------------------------------------------------------------------------
# Performance acceptance criterion
# ---------------------------------------------------------------------------


def test_default_validate_under_100ms_on_basic_template(tmp_path: Path) -> None:
    _make_bundle(tmp_path)
    # Warm Python imports first to avoid measuring one-time costs.
    validate_extension(tmp_path)
    runs = []
    for _ in range(5):
        t0 = time.perf_counter()
        validate_extension(tmp_path)
        runs.append((time.perf_counter() - t0) * 1000)
    median = sorted(runs)[len(runs) // 2]
    assert median < 100.0, f"validate took {median:.2f}ms (median), threshold 100ms"


# ---------------------------------------------------------------------------
# All emitted error codes are members of ERROR_CODES (regression catch).
# ---------------------------------------------------------------------------


def test_all_emitted_codes_are_registered(tmp_path: Path) -> None:
    """Belt-and-braces guard.

    Every code the validator produces must be in ERROR_CODES so it has a
    corresponding format_extension_error branch.
    """
    bad = {**_BASE_MANIFEST, "id": "BAD"}
    (tmp_path / "extension.json").write_text(json.dumps(bad), encoding="utf-8")
    report = validate_extension(tmp_path)
    for err in report.errors.errors:
        assert err.code in ERROR_CODES
