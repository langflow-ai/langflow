"""Tests for the Python regex substitutions embedded in the Makefile patch target.

The `make patch v=X.Y.Z` command uses inline Python one-liners to update version
pins across several files. These tests run the same regexes against realistic file
content so regressions are caught without needing to run make.
"""

from __future__ import annotations

import json
import re

# ---------------------------------------------------------------------------
# Helpers — mirror the Makefile one-liners exactly
# ---------------------------------------------------------------------------


def _patch_main_pyproject(txt: str, langflow_version: str, core_compat_version: str) -> str:
    txt = re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)
    return re.sub(
        r'"langflow-core(\[[^\]]*\])?(?:==|>=|~=)[^"]*"',
        lambda match: f'"langflow-core{match.group(1) or ""}~={core_compat_version}"',
        txt,
    )


def _patch_langflow_base_pyproject(txt: str, base_version: str, langflow_version: str) -> str:
    txt = re.sub(r'^version = ".*"', f'version = "{base_version}"', txt, flags=re.MULTILINE)
    return re.sub(
        r'"lfx(?P<extra>\[[^\]]+\])?(?:~=|>=)[^"]*"',
        lambda match: f'"lfx{match.group("extra") or ""}~={langflow_version}"',
        txt,
    )


def _patch_langflow_core_pyproject(txt: str, langflow_version: str, base_compat_version: str) -> str:
    txt = re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)
    return re.sub(
        r'"langflow-base(\[[^\]]*\])?(?:==|>=|~=)[^"]*"',
        rf'"langflow-base\1~={base_compat_version}"',
        txt,
    )


def _patch_lfx_pyproject(txt: str, langflow_version: str) -> str:
    return re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)


def _patch_sdk_pyproject(txt: str, sdk_version: str) -> str:
    return re.sub(r'^version = ".*"', f'version = "{sdk_version}"', txt, flags=re.MULTILINE)


def _patch_lfx_sdk_dependency(txt: str, sdk_version: str) -> str:
    return re.sub(r'"langflow-sdk(?:==|>=|~=)[^"]*"', f'"langflow-sdk>={sdk_version}"', txt)


def _component_index_version_matches(txt: str, langflow_version: str) -> bool:
    return json.loads(txt).get("version") == langflow_version


# ---------------------------------------------------------------------------
# langflow-core pins in main pyproject.toml
# ---------------------------------------------------------------------------


class TestLangflowCorePinSubstitution:
    V = "1.11.1"
    C = "1.11.0"

    def test_replaces_gte_with_extras(self):
        txt = '    "langflow-core[audio]>=1.10.0",'
        assert '"langflow-core[audio]~=1.11.0"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_replaces_equality_pin(self):
        txt = '    "langflow-core==1.10.0",'
        assert '"langflow-core~=1.11.0"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_replaces_compatible_release_pin(self):
        txt = '    "langflow-core~=1.10.0",'
        assert '"langflow-core~=1.11.0"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_replaces_bare_gte_without_extras(self):
        txt = '    "langflow-core>=1.10.0",'
        assert '"langflow-core~=1.11.0"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_does_not_touch_workspace_line(self):
        txt = "langflow-core = { workspace = true }"
        assert _patch_main_pyproject(txt, self.V, self.C) == txt

    def test_updates_version_field(self):
        txt = 'version = "1.10.0"'
        assert 'version = "1.11.1"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_patch_release_preserves_minor_compatibility_floor(self):
        txt = 'dependencies = ["langflow-core~=1.11.0"]'
        assert '"langflow-core~=1.11.0"' in _patch_main_pyproject(txt, self.V, self.C)

    def test_realistic_pyproject_fragment(self):
        txt = """\
[project]
name = "langflow"
version = "1.11.0"
dependencies = [
    "langflow-core~=1.11.0",
]
[project.optional-dependencies]
audio = ["langflow-core[audio]~=1.11.0"]
postgresql = ["langflow-core[postgresql]~=1.11.0"]
"""
        result = _patch_main_pyproject(txt, self.V, self.C)
        assert 'version = "1.11.1"' in result
        assert '"langflow-core~=1.11.0"' in result
        assert '"langflow-core[audio]~=1.11.0"' in result
        assert '"langflow-core[postgresql]~=1.11.0"' in result


# ---------------------------------------------------------------------------
# langflow-base pins and product version in langflow-core pyproject.toml
# ---------------------------------------------------------------------------


class TestLangflowCoreSubstitution:
    V = "1.11.1"
    B = "0.11.0"

    def test_updates_product_version(self):
        txt = 'version = "1.11.0"'
        assert 'version = "1.11.1"' in _patch_langflow_core_pyproject(txt, self.V, self.B)

    def test_updates_complete_base_dependency(self):
        txt = '    "langflow-base[complete]~=0.11.0",'
        result = _patch_langflow_core_pyproject(txt, self.V, self.B)
        assert '"langflow-base[complete]~=0.11.0"' in result

    def test_updates_postgresql_base_dependency(self):
        txt = 'postgresql = ["langflow-base[postgresql]>=0.11.0,<0.12.0"]'
        result = _patch_langflow_core_pyproject(txt, self.V, self.B)
        assert '"langflow-base[postgresql]~=0.11.0"' in result

    def test_updates_audio_base_dependency(self):
        txt = 'audio = ["langflow-base[audio]~=0.11.0"]'
        result = _patch_langflow_core_pyproject(txt, self.V, self.B)
        assert '"langflow-base[audio]~=0.11.0"' in result

    def test_preserves_unrelated_dependencies(self):
        txt = 'dependencies = ["langflow-base[complete]~=0.11.0", "httpx>=0.28"]'
        result = _patch_langflow_core_pyproject(txt, self.V, self.B)
        assert '"httpx>=0.28"' in result


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

    def test_preserves_extra(self):
        txt = 'toolguard = ["lfx[toolguard]~=1.10.0"]'
        assert '"lfx[toolguard]~=1.11.0"' in _patch_langflow_base_pyproject(txt, self.B, self.V)

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
# SDK version and LFX SDK dependency
# ---------------------------------------------------------------------------


class TestSdkVersionSubstitution:
    def test_updates_sdk_version(self):
        txt = '[project]\nname = "langflow-sdk"\nversion = "0.3.0"\n'
        result = _patch_sdk_pyproject(txt, "0.4.0")
        assert 'version = "0.4.0"' in result
        assert 'name = "langflow-sdk"' in result

    def test_updates_lfx_sdk_dependency(self):
        txt = 'dependencies = ["langflow-sdk~=0.3.0", "orjson>=3.10.0"]'
        result = _patch_lfx_sdk_dependency(txt, "0.4.0")
        assert '"langflow-sdk>=0.4.0"' in result
        assert '"orjson>=3.10.0"' in result


# ---------------------------------------------------------------------------
# component-index version validation
# ---------------------------------------------------------------------------


class TestComponentIndexVersionValidation:
    def test_accepts_matching_top_level_version(self):
        index = {"entries": [], "version": "1.12.0"}
        assert _component_index_version_matches(json.dumps(index), "1.12.0")

    def test_rejects_nested_match_when_top_level_version_is_stale(self):
        index = {
            "entries": [["example", {"metadata": {"dependencies": [{"name": "langflow", "version": "1.12.0"}]}}]],
            "version": "1.11.0",
        }
        assert not _component_index_version_matches(json.dumps(index), "1.12.0")


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
