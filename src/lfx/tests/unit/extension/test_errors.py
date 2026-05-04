"""Snapshot tests for format_extension_error -- one branch per error code."""

from __future__ import annotations

import pytest
from lfx.extension.errors import (
    DOCS_BASE,
    ERROR_CODES,
    ExtensionError,
    ExtensionErrorCollection,
    format_extension_error,
)


def test_extension_error_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="Unknown extension error code"):
        ExtensionError(code="not-a-real-code", message="x", hint="y")


def test_ref_url_default_anchors_to_code() -> None:
    err = ExtensionError(code="manifest-invalid", message="x", hint="y")
    assert err.ref_url == f"{DOCS_BASE}#manifest-invalid"


def test_to_dict_contains_all_fields() -> None:
    err = ExtensionError(
        code="manifest-invalid",
        message="bad",
        hint="fix it",
        location="/x/y",
        content="oops",
    )
    payload = err.to_dict()
    assert set(payload) == {"code", "message", "location", "content", "hint", "ref_url"}
    assert payload["ref_url"].endswith("#manifest-invalid")


def test_collection_ok_when_no_errors() -> None:
    coll = ExtensionErrorCollection()
    coll.add_warning(ExtensionError(code="manifest-invalid", message="m", hint="h"))
    assert coll.ok is True
    coll.add_error(ExtensionError(code="manifest-invalid", message="m", hint="h"))
    assert coll.ok is False


# ---------------------------------------------------------------------------
# Snapshot per branch
# ---------------------------------------------------------------------------


def _err(code: str, **kw: object) -> ExtensionError:
    base: dict = {"message": "msg", "hint": "fix it", "location": "loc", "content": "content"}
    base.update(kw)
    return ExtensionError(code=code, **base)


# Snapshot table: each code -> expected first line.  The trailing 4 lines
# (location/content/hint/see) are constant in shape so we assert structure
# rather than full text to keep snapshots stable when wording changes.
# Lines are intentionally long so the diff between expected and actual is one
# line per change; ``noqa: E501`` is intentional throughout this dict.
_FIRST_LINE_EXPECTATIONS: dict[str, str] = {
    "manifest-not-found": "error[manifest-not-found]: No extension.json or [tool.langflow.extension] entry found in loc.",  # noqa: E501
    "manifest-invalid": "error[manifest-invalid]: Invalid manifest at loc: msg",
    "manifest-unreadable": "error[manifest-unreadable]: Could not read manifest at loc: msg",
    "field-deferred-in-this-milestone": "error[field-deferred-in-this-milestone]: Manifest field 'content' is deferred in this milestone.",  # noqa: E501
    "multi-bundle-deferred-in-this-milestone": "error[multi-bundle-deferred-in-this-milestone]: Manifest declares more than one bundle entry; multi-bundle extensions are deferred in this milestone.",  # noqa: E501
    "template-deferred-in-this-milestone": "error[template-deferred-in-this-milestone]: Template 'content' is deferred in this milestone.",  # noqa: E501
    "path-escape": "error[path-escape]: Path 'content' escapes the bundle root (..; absolute path; or symlink leaving the bundle directory).",  # noqa: E501
    "bundle-path-not-found": "error[bundle-path-not-found]: Bundle path 'content' (resolved from manifest field loc) does not exist.",  # noqa: E501
    "bundle-empty": "error[bundle-empty]: Bundle 'content' contains no Python source files.",
    "syntax-error": "error[syntax-error]: Syntax error in loc: msg",
    "no-component-subclass": "error[no-component-subclass]: No Component subclass found anywhere in bundle 'content'.",
    "build-method-missing": "error[build-method-missing]: Component class at loc does not declare a build() method.",
    "import-star-disallowed": "error[import-star-disallowed]: Top-level wildcard import in loc: content",
    "top-level-io-disallowed": "error[top-level-io-disallowed]: Top-level I/O primitive 'content' used in loc; bundle module import must be side-effect free.",  # noqa: E501
    "execute-imports-failed": "error[execute-imports-failed]: Subprocess import probe (--execute-imports) failed for loc: msg",  # noqa: E501
    "module-import-failed": "error[module-import-failed]: Failed to import bundle module loc: msg",
    "duplicate-component-name": "error[duplicate-component-name]: Duplicate Component class name 'content' in bundle loc; component class names must be unique within a bundle.",  # noqa: E501
    "duplicate-inline-bundle": "error[duplicate-inline-bundle]: Inline bundle name 'content' appears in multiple LANGFLOW_COMPONENTS_PATH entries; first wins. Locations: loc.",  # noqa: E501
    "inline-bundle-name-invalid": "error[inline-bundle-name-invalid]: Inline bundle directory 'content' does not match the bundle name pattern (lowercase snake_case).",  # noqa: E501
    "installed-extension-immutable": "error[installed-extension-immutable]: Extension 'content' is installed via pip and cannot be mutated at runtime.",  # noqa: E501
    "seed-directory-immutable": "error[seed-directory-immutable]: Extension 'content' comes from a seed directory and cannot be mutated at runtime.",  # noqa: E501
    "seed-directory-not-found": "error[seed-directory-not-found]: Configured seed directory loc does not exist or is not a directory.",  # noqa: E501
    "duplicate-extension-id": "error[duplicate-extension-id]: Extension id 'content' is registered more than once (already at loc).",  # noqa: E501
}


def test_every_known_code_has_snapshot() -> None:
    """Catch missing snapshots for new ERROR_CODES additions.

    Every code in ERROR_CODES MUST have a snapshot expectation here so
    a ticket cannot ship a new code without a format branch and a test.
    """
    missing = ERROR_CODES - _FIRST_LINE_EXPECTATIONS.keys()
    extra = _FIRST_LINE_EXPECTATIONS.keys() - ERROR_CODES
    assert not missing, f"Missing snapshot for codes: {sorted(missing)}"
    assert not extra, f"Snapshot for unknown code(s): {sorted(extra)}"


@pytest.mark.parametrize("code", sorted(ERROR_CODES))
def test_format_branch_for_code(code: str) -> None:
    err = _err(code)
    rendered = format_extension_error(err)
    expected_first_line = _FIRST_LINE_EXPECTATIONS[code]
    lines = rendered.splitlines()
    assert lines[0] == expected_first_line
    # The four follow-on lines are stable in shape:
    assert "  location: loc" in rendered
    assert "  content:  content" in rendered
    assert "  hint:     fix it" in rendered
    assert f"  see:      {DOCS_BASE}#{code}" in rendered


def test_format_omits_blank_location_and_content() -> None:
    err = ExtensionError(code="manifest-invalid", message="m", hint="h")
    out = format_extension_error(err)
    assert "location:" not in out
    assert "content:" not in out
    assert "hint:     h" in out
