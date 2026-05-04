"""Tests for ``lfx.extension.init_template`` (LE-1016).

Coverage:
    - Basic template renders a manifest that round-trips through the
      LE-1014 validator with zero errors (AC #1).
    - Generated test file is a syntactically valid pytest module that
      imports + executes (AC #2).
    - Unknown ``--template`` value (e.g. ``full``) returns a typed
      ``template-deferred-in-this-milestone`` error (AC #3).
    - Refuses to scaffold over a non-empty directory.
    - Identifier-derivation helpers handle weird inputs gracefully.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from lfx.extension import (
    BASIC_TEMPLATE,
    InitOptions,
    init_extension,
    validate_extension,
)
from lfx.extension.init_template import (
    deferred_template_names,
    derive_bundle_name,
    derive_display_name,
    derive_extension_id,
)

if TYPE_CHECKING:
    from pathlib import Path


def _options(target: Path, *, template: str = BASIC_TEMPLATE) -> InitOptions:
    eid = derive_extension_id(target.name)
    return InitOptions(
        target=target,
        extension_id=eid,
        bundle_name=derive_bundle_name(eid),
        display_name=derive_display_name(eid),
        template=template,
    )


# ---------------------------------------------------------------------------
# AC #1: init then validate is clean
# ---------------------------------------------------------------------------


def test_basic_template_validates_clean(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    result = init_extension(_options(target))
    assert result.ok, result.errors

    report = validate_extension(target)
    assert report.ok, [e.code for e in report.errors.errors]
    # The basic template ships an __init__.py + hello.py inside the bundle.
    assert report.bundle_files_scanned >= 1


# ---------------------------------------------------------------------------
# AC #2: generated test file is well-formed
# ---------------------------------------------------------------------------


def test_generated_test_file_parses_as_python(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    init_extension(_options(target))
    test_file = target / "tests" / "test_hello.py"
    assert test_file.is_file()
    # Must parse as Python without syntax errors.
    tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
    test_funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(test_funcs) >= 2  # both happy-path tests are written


def test_generated_test_file_runs_against_generated_component(tmp_path: Path) -> None:
    """End-to-end: import the generated module and invoke its component.

    We do NOT exec the generated test via pytest here (that would require
    pytest-in-pytest gymnastics); instead we mirror the test's assertions
    against the same component to confirm the contract is real.
    """
    target = tmp_path / "my-ext"
    init_extension(_options(target))

    # Add the bundle dir to sys.path and import the component as if from
    # the generated test's perspective.  This proves the test file's
    # ``from components.my_ext.hello import ...`` line is resolvable when
    # run from the extension root.
    import sys

    sys.path.insert(0, str(target))
    try:
        from components.my_ext.hello import MyExtHelloComponent  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(target))

    component = MyExtHelloComponent()
    component.name = "Eric"
    assert component.build() == "Hello, Eric!"


# ---------------------------------------------------------------------------
# AC #3: unknown template fails cleanly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", ["full", "service", "route", "multi-bundle", "starter-projects"])
def test_deferred_templates_emit_typed_error(tmp_path: Path, template: str) -> None:
    target = tmp_path / "my-ext"
    result = init_extension(_options(target, template=template))
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert codes == ["template-deferred-in-this-milestone"]
    # Author-facing hint points back to the basic template.
    assert "basic" in result.errors[0].hint
    # No files were written.
    assert not target.exists() or not any(target.iterdir())


def test_deferred_template_names_lists_known_future_templates() -> None:
    names = list(deferred_template_names())
    assert names == sorted(names)  # stable order
    # Every name we explicitly trigger above is listed.
    for tpl in ["full", "service", "route", "multi-bundle", "starter-projects"]:
        assert tpl in names


# ---------------------------------------------------------------------------
# Refuse to scaffold over a non-empty target
# ---------------------------------------------------------------------------


def test_refuses_non_empty_target(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    target.mkdir()
    (target / "important.txt").write_text("don't clobber me", encoding="utf-8")
    result = init_extension(_options(target))
    codes = [e.code for e in result.errors]
    assert codes == ["extension-target-exists"]
    # Important file untouched.
    assert (target / "important.txt").read_text(encoding="utf-8") == "don't clobber me"


def test_accepts_empty_existing_directory(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    target.mkdir()
    result = init_extension(_options(target))
    assert result.ok, result.errors
    assert (target / "extension.json").is_file()


def test_refuses_target_that_is_a_file(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    target.write_text("not a directory", encoding="utf-8")
    result = init_extension(_options(target))
    assert not result.ok
    assert result.errors[0].code == "extension-target-invalid"


# ---------------------------------------------------------------------------
# Identifier derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dir_name", "expected_id"),
    [
        ("my-ext", "my-ext"),
        ("My_Cool_Extension", "my-cool-extension"),
        ("a", "my-extension"),  # too short -> fallback
        ("123-bad-prefix", "my-extension"),  # non-alpha prefix -> fallback
        ("ok name", "ok-name"),
        ("ok-NAME!!!", "ok-name"),
    ],
)
def test_derive_extension_id(dir_name: str, expected_id: str) -> None:
    assert derive_extension_id(dir_name) == expected_id


@pytest.mark.parametrize(
    ("eid", "expected"),
    [
        ("my-ext", "my_ext"),
        ("a-b-c", "a_b_c"),
        ("x", "my_bundle"),  # too short -> fallback
    ],
)
def test_derive_bundle_name(eid: str, expected: str) -> None:
    assert derive_bundle_name(eid) == expected


def test_derive_display_name_title_cases() -> None:
    assert derive_display_name("my-cool-extension") == "My Cool Extension"


# ---------------------------------------------------------------------------
# File contents are deterministic
# ---------------------------------------------------------------------------


def test_manifest_carries_schema_pointer(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    init_extension(_options(target))
    payload = (target / "extension.json").read_text(encoding="utf-8")
    assert '"$schema"' in payload
    assert "schemas.langflow.org/extension/v1.json" in payload


def test_files_written_list_is_complete(tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    result = init_extension(_options(target))
    rels = sorted(p.relative_to(target).as_posix() for p in result.files_written)
    assert rels == [
        ".gitignore",
        "README.md",
        "components/my_ext/__init__.py",
        "components/my_ext/hello.py",
        "extension.json",
        "tests/__init__.py",
        "tests/test_hello.py",
    ]
