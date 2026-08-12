"""Tests for the Python regex substitutions embedded in the Makefile patch target.

The `make patch v=X.Y.Z` command uses inline Python one-liners to update version
pins across several files. These tests run the same regexes against realistic file
content so regressions are caught without needing to run make.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Helpers — mirror the Makefile one-liners exactly
# ---------------------------------------------------------------------------


def _patch_main_pyproject(txt: str, langflow_version: str, base_version: str) -> str:
    txt = re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)
    return re.sub(
        r'"langflow-base(?:\[[^\]]*\])?(?:==|>=|~=)[^"]*"',
        f'"langflow-base[complete]>={base_version}"',
        txt,
    )


def _patch_langflow_base_pyproject(txt: str, base_version: str, langflow_version: str) -> str:
    txt = re.sub(r'^version = ".*"', f'version = "{base_version}"', txt, flags=re.MULTILINE)
    return re.sub(r'"lfx(?:~=|>=)[^"]*"', f'"lfx~={langflow_version}"', txt)


def _patch_lfx_pyproject(txt: str, langflow_version: str) -> str:
    return re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# langflow-base pin in main pyproject.toml
# ---------------------------------------------------------------------------


class TestLangflowBasePinSubstitution:
    V = "1.11.0"
    B = "0.11.0"

    def test_replaces_gte_with_extras(self):
        # Real format in pyproject.toml as of 1.10.0
        txt = '    "langflow-base[complete]>=0.10.0",'
        assert '"langflow-base[complete]>=0.11.0"' in _patch_main_pyproject(txt, self.V, self.B)

    def test_replaces_equality_pin(self):
        txt = '    "langflow-base==0.10.0",'
        assert '"langflow-base[complete]>=0.11.0"' in _patch_main_pyproject(txt, self.V, self.B)

    def test_replaces_compatible_release_pin(self):
        txt = '    "langflow-base~=0.10.0",'
        assert '"langflow-base[complete]>=0.11.0"' in _patch_main_pyproject(txt, self.V, self.B)

    def test_replaces_bare_gte_without_extras(self):
        txt = '    "langflow-base>=0.10.0",'
        assert '"langflow-base[complete]>=0.11.0"' in _patch_main_pyproject(txt, self.V, self.B)

    def test_does_not_touch_workspace_line(self):
        txt = "langflow-base = { workspace = true }"
        assert _patch_main_pyproject(txt, self.V, self.B) == txt

    def test_updates_version_field(self):
        txt = 'version = "1.10.0"'
        assert 'version = "1.11.0"' in _patch_main_pyproject(txt, self.V, self.B)

    def test_realistic_pyproject_fragment(self):
        txt = """\
[project]
name = "langflow"
version = "1.10.0"
dependencies = [
    "langflow-base[complete]>=0.10.0",
    "httpx>=0.23.0",
]
"""
        result = _patch_main_pyproject(txt, "1.11.0", "0.11.0")
        assert 'version = "1.11.0"' in result
        assert '"langflow-base[complete]>=0.11.0"' in result
        assert '"httpx>=0.23.0"' in result  # unrelated dep untouched


# ---------------------------------------------------------------------------
# lfx pin in src/backend/base/pyproject.toml
# ---------------------------------------------------------------------------


class TestLfxPinSubstitution:
    V = "1.11.0"
    B = "0.11.0"

    def test_replaces_tilde_form(self):
        # Stable form written by make patch
        txt = '    "lfx~=1.10.0",'
        assert '"lfx~=1.11.0"' in _patch_langflow_base_pyproject(txt, self.B, self.V)

    def test_replaces_gte_range_form(self):
        # Form written by release.yml after a pre-release build:
        # "lfx>=X.Y.Z,<X.(Y+1).dev0"
        txt = '    "lfx>=1.10.0,<1.11.dev0",'
        assert '"lfx~=1.11.0"' in _patch_langflow_base_pyproject(txt, self.B, self.V)

    def test_does_not_touch_workspace_line(self):
        txt = "lfx = { workspace = true }"
        assert _patch_langflow_base_pyproject(txt, self.B, self.V) == txt

    def test_updates_version_field(self):
        txt = 'version = "0.10.0"'
        assert 'version = "0.11.0"' in _patch_langflow_base_pyproject(txt, self.B, self.V)

    def test_realistic_langflow_base_fragment(self):
        txt = """\
[project]
name = "langflow-base"
version = "0.10.0"
dependencies = [
    "lfx~=1.10.0",
    "pydantic>=2.0.0",
]
"""
        result = _patch_langflow_base_pyproject(txt, "0.11.0", "1.11.0")
        assert 'version = "0.11.0"' in result
        assert '"lfx~=1.11.0"' in result
        assert '"pydantic>=2.0.0"' in result  # unrelated dep untouched

    def test_realistic_gte_range_form_fragment(self):
        """Simulates state after release.yml runs a pre-release build."""
        txt = """\
[project]
name = "langflow-base"
version = "0.10.3"
dependencies = [
    "lfx>=1.10.3,<1.11.dev0",
    "pydantic>=2.0.0",
]
"""
        result = _patch_langflow_base_pyproject(txt, "0.11.0", "1.11.0")
        assert '"lfx~=1.11.0"' in result
        assert '"pydantic>=2.0.0"' in result


# ---------------------------------------------------------------------------
# lfx pyproject.toml version
# ---------------------------------------------------------------------------


class TestLfxVersionSubstitution:
    def test_updates_version(self):
        txt = 'version = "1.10.0"'
        assert 'version = "1.11.0"' in _patch_lfx_pyproject(txt, "1.11.0")

    def test_realistic_lfx_fragment(self):
        txt = """\
[project]
name = "lfx"
version = "1.10.0"
description = "Lightweight executor for Langflow"
"""
        result = _patch_lfx_pyproject(txt, "1.11.0")
        assert 'version = "1.11.0"' in result
        assert "Lightweight executor" in result


# ---------------------------------------------------------------------------
# release.yml: major.minor extraction from the current lfx constraint
#
# release.yml computes the next constraint ceiling from the CURRENT pin with:
#   MAJOR_MINOR=$(echo "$CURRENT_CONSTRAINT" | sed -E 's/^[^0-9]*([0-9]+\\.[0-9]+).*/\\1/')
# It must read the LOWER bound, including when the pin is already in the range form
# ">=X.Y.Z,<X.(Y+1).dev0" that release.yml itself writes — otherwise the ceiling drifts.
# ---------------------------------------------------------------------------


def _release_yml_major_minor(constraint_line: str) -> str:
    """Mirror the release.yml sed: anchor to the FIRST version in the line."""
    return re.sub(r"^[^0-9]*([0-9]+\.[0-9]+).*", r"\1", constraint_line)


def _old_greedy_major_minor(constraint_line: str) -> str:
    r"""The previous (buggy) greedy sed: 's/.*[~>=<]+([0-9]+\.[0-9]+).*/\1/'."""
    return re.sub(r".*[~>=<]+([0-9]+\.[0-9]+).*", r"\1", constraint_line)


class TestReleaseYmlMajorMinorExtraction:
    def test_extracts_from_tilde_form(self):
        assert _release_yml_major_minor('    "lfx~=1.10.0",') == "1.10"

    def test_extracts_lower_bound_from_range_form(self):
        # The form release.yml writes after a pre-release build. Must read 1.10, not 1.11.
        assert _release_yml_major_minor('    "lfx>=1.10.0,<1.11.dev0",') == "1.10"

    def test_extracts_from_gte_only_form(self):
        assert _release_yml_major_minor('    "lfx>=1.10.0",') == "1.10"

    def test_ceiling_is_next_minor_not_drifted(self):
        # MAJOR.NEXT_MINOR computed from a range-form pin must be 1.11, not 1.12.
        major_minor = _release_yml_major_minor('    "lfx>=1.10.0,<1.11.dev0",')
        major, minor = major_minor.split(".")
        assert f"{major}.{int(minor) + 1}" == "1.11"

    def test_old_greedy_regex_was_wrong_on_range_form(self):
        # Documents the bug the fix addresses: greedy match grabbed the upper bound (1.11),
        # so the ceiling drifted upward by one minor each release cycle.
        assert _old_greedy_major_minor('    "lfx>=1.10.0,<1.11.dev0",') == "1.11"
        assert _release_yml_major_minor('    "lfx>=1.10.0,<1.11.dev0",') == "1.10"
