"""Tests for the Python regex substitutions embedded in the Makefile patch target.

The `make patch v=X.Y.Z` command uses inline Python one-liners to update version
pins across several files. Core dependency tests execute the actual Makefile
one-liners against realistic file content without running the full patch target.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# ---------------------------------------------------------------------------
# Helpers for Makefile substitutions
# ---------------------------------------------------------------------------


def _patch_core_pyproject(txt: str, relative: str, version: str) -> str:
    makefile = Path(__file__).resolve().parents[4] / "Makefile"
    line = next(line for line in makefile.read_text().splitlines() if f"fname='{relative}'" in line)
    command = shlex.split(line.strip().removesuffix("\\").rstrip())
    assert command[:2] == ["python", "-c"]
    program = command[2].replace("$$LANGFLOW_VERSION", version)
    with TemporaryDirectory() as directory:
        path = Path(directory) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(txt)
        subprocess.run([sys.executable, "-c", program], cwd=directory, check=True, capture_output=True)  # noqa: S603
        return path.read_text()


def _patch_main_pyproject(txt: str, langflow_version: str) -> str:
    return _patch_core_pyproject(txt, "pyproject.toml", langflow_version)


def _patch_langflow_base_pyproject(txt: str, langflow_version: str) -> str:
    return _patch_core_pyproject(txt, "src/backend/base/pyproject.toml", langflow_version)


@pytest.mark.parametrize(
    ("relative", "dependency"),
    [("pyproject.toml", "langflow-base[audio]"), ("src/backend/base/pyproject.toml", "lfx[cassandra]")],
)
@pytest.mark.parametrize("version", ["1.12.2", "1.13.0rc1", "1.13.0.dev3"])
def test_core_patch_preserves_markers_and_is_idempotent(relative: str, dependency: str, version: str):
    txt = f'dependencies = ["{dependency}>=1.0,<2; sys_platform != \'win32\'", "lfx-openai>=0.1,<1"]'
    result = _patch_core_pyproject(txt, relative, version)

    assert f"\"{dependency}=={version}; sys_platform != 'win32'\"" in result
    assert '"lfx-openai>=0.1,<1"' in result
    assert _patch_core_pyproject(result, relative, version) == result


def _patch_lfx_pyproject(txt: str, langflow_version: str) -> str:
    return re.sub(r'^version = ".*"', f'version = "{langflow_version}"', txt, flags=re.MULTILINE)


def _patch_sdk_pyproject(txt: str, sdk_version: str) -> str:
    return re.sub(r'^version = ".*"', f'version = "{sdk_version}"', txt, flags=re.MULTILINE)


def _patch_lfx_sdk_dependency(txt: str, sdk_version: str) -> str:
    return re.sub(r'"langflow-sdk(?:==|>=|~=)[^"]*"', f'"langflow-sdk>={sdk_version}"', txt)


def _component_index_version_matches(txt: str, langflow_version: str) -> bool:
    return json.loads(txt).get("version") == langflow_version


# ---------------------------------------------------------------------------
# langflow-base pins in main pyproject.toml
# ---------------------------------------------------------------------------


class TestLangflowBasePinSubstitution:
    V = "1.12.1"

    def test_replaces_gte_with_extras(self):
        txt = '    "langflow-base[audio]>=1.11.0",'
        assert '"langflow-base[audio]==1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_replaces_equality_pin(self):
        txt = '    "langflow-base==1.11.0",'
        assert '"langflow-base==1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_replaces_compatible_release_pin(self):
        txt = '    "langflow-base~=1.11.0",'
        assert '"langflow-base==1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_replaces_bare_gte_without_extras(self):
        txt = '    "langflow-base>=1.11.0",'
        assert '"langflow-base==1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_does_not_touch_workspace_line(self):
        txt = "langflow-base = { workspace = true }"
        assert _patch_main_pyproject(txt, self.V) == txt

    def test_updates_version_field(self):
        txt = 'version = "1.10.0"'
        assert 'version = "1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_patch_release_pins_the_requested_patch(self):
        txt = 'dependencies = ["langflow-base~=1.12.0"]'
        assert '"langflow-base==1.12.1"' in _patch_main_pyproject(txt, self.V)

    def test_realistic_pyproject_fragment(self):
        txt = """\
[project]
name = "langflow"
version = "1.12.0"
dependencies = [
    "langflow-base~=1.12.0",
]
[project.optional-dependencies]
audio = ["langflow-base[audio]~=1.12.0"]
postgresql = ["langflow-base[postgresql]~=1.12.0"]
"""
        result = _patch_main_pyproject(txt, self.V)
        assert 'version = "1.12.1"' in result
        assert '"langflow-base==1.12.1"' in result
        assert '"langflow-base[audio]==1.12.1"' in result
        assert '"langflow-base[postgresql]==1.12.1"' in result


# ---------------------------------------------------------------------------
# lfx pin in src/backend/base/pyproject.toml
# ---------------------------------------------------------------------------


class TestLfxPinSubstitution:
    V = "1.12.1"

    def test_replaces_equality_pin(self):
        txt = '    "lfx==1.12.0",'
        assert '"lfx==1.12.1"' in _patch_langflow_base_pyproject(txt, self.V)

    def test_replaces_tilde_form(self):
        # Older stable releases used a compatible range.
        txt = '    "lfx~=1.10.0",'
        assert '"lfx==1.12.1"' in _patch_langflow_base_pyproject(txt, self.V)

    def test_replaces_gte_range_form(self):
        # Older release candidates used a bounded range.
        txt = '    "lfx>=1.10.0,<1.11.dev0",'
        assert '"lfx==1.12.1"' in _patch_langflow_base_pyproject(txt, self.V)

    def test_preserves_extra(self):
        txt = 'toolguard = ["lfx[toolguard]~=1.10.0"]'
        assert '"lfx[toolguard]==1.12.1"' in _patch_langflow_base_pyproject(txt, self.V)

    def test_does_not_touch_workspace_line(self):
        txt = "lfx = { workspace = true }"
        assert _patch_langflow_base_pyproject(txt, self.V) == txt

    def test_updates_version_field(self):
        txt = 'version = "0.10.0"'
        assert 'version = "1.12.1"' in _patch_langflow_base_pyproject(txt, self.V)

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
        result = _patch_langflow_base_pyproject(txt, "1.12.1")
        assert 'version = "1.12.1"' in result
        assert '"lfx==1.12.1"' in result
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
        result = _patch_langflow_base_pyproject(txt, "1.12.1")
        assert '"lfx==1.12.1"' in result
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

    @pytest.mark.parametrize("operator", ["==", ">=", "~="])
    def test_updates_lfx_sdk_dependency(self, operator):
        txt = f'dependencies = ["langflow-sdk{operator}0.3.0", "orjson>=3.10.0"]'
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
