"""Tests for flow_requirements module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfx.utils.flow_requirements import (
    MODULE_EXTRA_DEPS,
    PROVIDER_PACKAGES,
    _detect_providers_from_template,
    _extract_component_requirements,
    _extract_imports,
    _get_import_to_dist_map,
    _get_lfx_provided_imports,
    _get_lfx_transitive_dists,
    _import_to_package,
    _pin_version,
    generate_requirements_from_file,
    generate_requirements_from_flow,
    generate_requirements_txt,
)


def _find_starter_projects_dir() -> Path:
    """Walk up from this test file to find the monorepo root and locate starter projects."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "src" / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"
        if candidate.is_dir():
            return candidate
    return Path("STARTER_PROJECTS_NOT_FOUND")


STARTER_PROJECTS_DIR = _find_starter_projects_dir()


# ---------------------------------------------------------------------------
# Helpers to build minimal flow JSON structures
# ---------------------------------------------------------------------------


def _make_node(
    component_type: str,
    code: str = "",
    template_extra: dict | None = None,
    node_type: str = "genericNode",
) -> dict:
    """Build a minimal flow node dict for testing."""
    template: dict = {"_type": "Component"}
    if code:
        template["code"] = {
            "type": "code",
            "value": code,
        }
    if template_extra:
        template.update(template_extra)
    return {
        "id": f"{component_type}-test1",
        "type": node_type,
        "data": {
            "display_name": component_type,
            "id": f"{component_type}-test1",
            "type": component_type,
            "node": {
                "display_name": component_type,
                "template": template,
            },
        },
    }


def _make_flow(*nodes: dict) -> dict:
    """Build a minimal flow dict from nodes."""
    return {
        "data": {
            "nodes": list(nodes),
            "edges": [],
        },
        "name": "Test Flow",
    }


# ===================================================================
# Unit tests: _extract_imports
# ===================================================================


class TestExtractImports:
    def test_simple_import(self):
        result = _extract_imports("import os")
        assert "os" in result

    def test_from_import(self):
        result = _extract_imports("from pathlib import Path")
        assert "pathlib" in result

    def test_dotted_import(self):
        result = _extract_imports("from langchain_openai.chat_models import ChatOpenAI")
        assert "langchain_openai" in result

    def test_relative_import_skipped(self):
        result = _extract_imports("from .utils import helper")
        assert len(result) == 0

    def test_multiple_imports(self):
        code = """
import os
import json
from typing import Any
from langchain_openai import ChatOpenAI
from bs4 import BeautifulSoup
"""
        result = _extract_imports(code)
        assert "os" in result
        assert "json" in result
        assert "typing" in result
        assert "langchain_openai" in result
        assert "bs4" in result

    def test_syntax_error_returns_empty(self):
        result = _extract_imports("def broken(")
        assert result == set()

    def test_empty_source(self):
        result = _extract_imports("")
        assert result == set()

    def test_lfx_imports(self):
        code = "from lfx.schema.message import Message"
        result = _extract_imports(code)
        assert "lfx" in result

    def test_try_except_imports(self):
        code = """
try:
    from openai import BadRequestError
except ImportError:
    pass
"""
        result = _extract_imports(code)
        assert "openai" in result

    def test_conditional_import_in_function(self):
        code = """
def build_model(self):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic()
"""
        result = _extract_imports(code)
        assert "langchain_anthropic" in result


# ===================================================================
# Unit tests: _import_to_package (now backed by importlib.metadata)
# ===================================================================


class TestImportToPackage:
    def test_known_mapping_via_metadata(self):
        """importlib.metadata.packages_distributions() resolves these."""
        assert _import_to_package("PIL") == "pillow"
        assert _import_to_package("bs4") == "beautifulsoup4"

    def test_langchain_mapping_via_metadata(self):
        assert _import_to_package("langchain_openai") == "langchain-openai"
        assert _import_to_package("langchain_anthropic") == "langchain-anthropic"

    def test_fallback_underscore_to_hyphen(self):
        """Unknown packages fall back to replacing _ with -."""
        assert _import_to_package("totally_unknown_pkg_xyz") == "totally-unknown-pkg-xyz"

    def test_simple_package_unchanged(self):
        assert _import_to_package("requests") == "requests"
        assert _import_to_package("numpy") == "numpy"

    def test_googleapiclient_mapping(self):
        assert _import_to_package("googleapiclient") == "google-api-python-client"

    def test_mem0_mapping(self):
        assert _import_to_package("mem0") == "mem0ai"


# ===================================================================
# Unit tests: dynamic resolution helpers
# ===================================================================


class TestDynamicResolution:
    def test_import_to_dist_map_returns_dict(self):
        result = _get_import_to_dist_map()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_import_to_dist_map_has_known_entries(self):
        result = _get_import_to_dist_map()
        assert "PIL" in result
        assert "pillow" in result["PIL"]

    def test_lfx_transitive_dists_includes_lfx(self):
        dists = _get_lfx_transitive_dists()
        assert "lfx" in dists

    def test_lfx_transitive_dists_includes_langchain(self):
        dists = _get_lfx_transitive_dists()
        assert "langchain" in dists
        assert "langchain-core" in dists

    def test_lfx_transitive_dists_includes_pydantic(self):
        dists = _get_lfx_transitive_dists()
        assert "pydantic" in dists

    def test_lfx_provided_imports_includes_expected(self):
        provided = _get_lfx_provided_imports()
        for imp in ["orjson", "fastapi", "pydantic", "langchain", "pandas", "PIL"]:
            assert imp in provided, f"{imp} should be provided by lfx"

    def test_lfx_provided_imports_excludes_optional(self):
        """Packages not in lfx's dep tree should NOT be in provided."""
        provided = _get_lfx_provided_imports()
        # langchain-openai is an optional provider, not a core lfx dep
        assert "langchain_openai" not in provided


# ===================================================================
# Unit tests: _detect_providers_from_template
# ===================================================================


class TestDetectProviders:
    def test_no_model_field(self):
        template = {"_type": "Component", "code": {"value": ""}}
        assert _detect_providers_from_template(template) == set()

    def test_empty_model_field(self):
        template = {"model": {"value": []}}
        assert _detect_providers_from_template(template) == set()

    def test_openai_provider(self):
        template = {
            "model": {
                "value": [{"provider": "OpenAI", "name": "gpt-4o"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"OpenAI"}

    def test_anthropic_provider(self):
        template = {
            "model": {
                "value": [{"provider": "Anthropic", "name": "claude-3-opus"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"Anthropic"}

    def test_agent_llm_field(self):
        template = {
            "agent_llm": {
                "value": [{"provider": "Google Generative AI", "name": "gemini-pro"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"Google Generative AI"}

    def test_multiple_providers(self):
        template = {
            "model": {
                "value": [{"provider": "OpenAI", "name": "gpt-4o"}],
            },
            "embeddings_model": {
                "value": [{"provider": "Google Generative AI", "name": "embedding-001"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"OpenAI", "Google Generative AI"}

    def test_non_dict_value_skipped(self):
        template = {"model": {"value": "not a list"}}
        assert _detect_providers_from_template(template) == set()

    def test_model_field_not_dict(self):
        template = {"model": "not a dict"}
        assert _detect_providers_from_template(template) == set()


# ===================================================================
# Unit tests: _extract_component_requirements
# ===================================================================


class TestExtractComponentRequirements:
    def test_lfx_only_component(self):
        code = """
from lfx.schema.message import Message
from lfx.io import Output
"""
        node = _make_node("ChatInput", code)
        packages, providers = _extract_component_requirements(node)
        assert len(packages) == 0
        assert len(providers) == 0

    def test_stdlib_filtered(self):
        code = """
import os
import json
import re
from typing import Any
from collections import OrderedDict
"""
        node = _make_node("Custom", code)
        packages, _ = _extract_component_requirements(node)
        assert len(packages) == 0

    def test_lfx_provided_filtered(self):
        code = """
import orjson
from fastapi.encoders import jsonable_encoder
import pandas as pd
from pydantic import BaseModel
"""
        node = _make_node("ChatOutput", code)
        packages, _ = _extract_component_requirements(node)
        assert len(packages) == 0

    def test_external_dep_detected(self):
        code = """
from langchain_openai import ChatOpenAI
"""
        node = _make_node("OpenAIModel", code)
        packages, _ = _extract_component_requirements(node)
        assert "langchain-openai" in packages

    def test_provider_detected(self):
        node = _make_node(
            "LanguageModel",
            "from lfx.base.models.model import LCModelComponent",
            template_extra={
                "model": {
                    "value": [{"provider": "Anthropic", "name": "claude-3"}],
                },
            },
        )
        _, providers = _extract_component_requirements(node)
        assert "Anthropic" in providers

    def test_note_node_handled(self):
        node = _make_node("ReadMe", node_type="noteNode")
        packages, providers = _extract_component_requirements(node)
        # Note nodes have no code, so empty results
        assert len(packages) == 0
        assert len(providers) == 0

    def test_no_code_field(self):
        node = _make_node("Empty")
        packages, providers = _extract_component_requirements(node)
        assert len(packages) == 0
        assert len(providers) == 0

    def test_module_extra_deps(self):
        """Extra runtime deps (lxml, tabulate) must be included for bs4.

        Note: bs4 itself (beautifulsoup4) may or may not appear depending on
        whether it's transitively provided by lfx, but the extra runtime deps
        must always be included.
        """
        code = """
from bs4 import BeautifulSoup
"""
        node = _make_node("URLTool", code)
        packages, _ = _extract_component_requirements(node)
        assert "lxml" in packages
        assert "tabulate" in packages

    def test_langflow_imports_filtered(self):
        """Components with langflow imports should NOT list langflow as a dep.

        lfx provides the langflow interfaces at runtime, so langflow/langflow_base
        should be filtered out just like lfx itself.
        """
        code = """
from langflow.custom import Component
from langflow.io import MessageTextInput
"""
        node = _make_node("LegacyComponent", code)
        packages, _ = _extract_component_requirements(node)
        assert "langflow" not in packages
        assert "langflow-base" not in packages


# ===================================================================
# Unit tests: generate_requirements_from_flow
# ===================================================================


class TestGenerateRequirementsFromFlow:
    def test_empty_flow(self):
        flow = _make_flow()
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]

    def test_lfx_only_flow(self):
        node = _make_node(
            "ChatInput",
            "from lfx.schema.message import Message",
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]

    def test_external_dep_flow(self):
        node = _make_node(
            "OpenAIModel",
            "from langchain_openai import ChatOpenAI",
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "lfx" in result
        assert "langchain-openai" in result

    def test_provider_adds_package(self):
        node = _make_node(
            "LLM",
            "from lfx.base.models.model import LCModelComponent",
            template_extra={
                "model": {
                    "value": [{"provider": "OpenAI", "name": "gpt-4o"}],
                },
            },
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-openai" in result

    def test_note_nodes_skipped(self):
        note = _make_node("ReadMe", node_type="noteNode")
        component = _make_node(
            "ChatInput",
            "from lfx.schema.message import Message",
        )
        flow = _make_flow(note, component)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]

    def test_include_lfx_false(self):
        flow = _make_flow()
        result = generate_requirements_from_flow(flow, include_lfx=False, pin_versions=False)
        assert "lfx" not in result

    def test_custom_lfx_package_name(self):
        flow = _make_flow()
        result = generate_requirements_from_flow(flow, lfx_package="lfx-nightly", pin_versions=False)
        assert "lfx-nightly" in result
        assert "lfx" not in result

    def test_results_sorted(self):
        node1 = _make_node("A", "from langchain_openai import ChatOpenAI")
        node2 = _make_node("B", "from bs4 import BeautifulSoup")
        flow = _make_flow(node1, node2)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        # lfx should be first, then sorted extras
        assert result[0] == "lfx"
        extras = result[1:]
        assert extras == sorted(extras)

    def test_deduplication(self):
        node1 = _make_node("A", "from langchain_openai import ChatOpenAI")
        node2 = _make_node("B", "from langchain_openai import OpenAI")
        flow = _make_flow(node1, node2)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result.count("langchain-openai") == 1

    def test_multiple_providers(self):
        node1 = _make_node(
            "LLM",
            "",
            template_extra={
                "model": {"value": [{"provider": "OpenAI", "name": "gpt-4o"}]},
            },
        )
        node2 = _make_node(
            "Embeddings",
            "",
            template_extra={
                "embeddings_model": {"value": [{"provider": "Google Generative AI", "name": "embedding-001"}]},
            },
        )
        flow = _make_flow(node1, node2)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-openai" in result
        assert "langchain-google-genai" in result


# ===================================================================
# Unit tests: version pinning
# ===================================================================


class TestVersionPinning:
    def test_pin_version_installed_package(self):
        """Installed packages should get ==X.Y.Z suffix."""
        result = _pin_version("lfx")
        assert result.startswith("lfx==")
        # Version should be a valid semver-ish string
        version_part = result.split("==")[1]
        assert len(version_part) > 0

    def test_pin_version_uninstalled_package(self):
        """Packages not installed should return bare name."""
        result = _pin_version("totally-nonexistent-package-xyz-999")
        assert result == "totally-nonexistent-package-xyz-999"

    def test_pin_versions_true_by_default(self):
        """Default behavior should pin versions."""
        flow = _make_flow()
        result = generate_requirements_from_flow(flow)
        assert result[0].startswith("lfx==")

    def test_pin_versions_false(self):
        """pin_versions=False should return bare names."""
        flow = _make_flow()
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]

    def test_pinned_output_includes_versions_for_installed_deps(self):
        """Installed deps should get pinned; uninstalled deps stay bare."""
        node = _make_node("A", "from langchain_openai import ChatOpenAI")
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=True)
        # lfx is installed, so it should be pinned
        assert result[0].startswith("lfx==")
        # langchain-openai may or may not be installed depending on env;
        # just verify it appears in the output
        langchain_openai_entries = [r for r in result if r.startswith("langchain-openai")]
        assert len(langchain_openai_entries) == 1

    def test_pinned_txt_output(self):
        """generate_requirements_txt should respect pin_versions."""
        flow = _make_flow()
        txt_pinned = generate_requirements_txt(flow, pin_versions=True)
        txt_unpinned = generate_requirements_txt(flow, pin_versions=False)
        assert "==" in txt_pinned
        assert "==" not in txt_unpinned


# ===================================================================
# Unit tests: generate_requirements_txt
# ===================================================================


class TestGenerateRequirementsTxt:
    def test_has_header_comments(self):
        flow = _make_flow()
        txt = generate_requirements_txt(flow)
        assert txt.startswith("# Auto-generated")
        assert "# This file contains" in txt

    def test_has_trailing_newline(self):
        flow = _make_flow()
        txt = generate_requirements_txt(flow)
        assert txt.endswith("\n")

    def test_packages_on_separate_lines(self):
        node = _make_node("A", "from langchain_openai import ChatOpenAI")
        flow = _make_flow(node)
        txt = generate_requirements_txt(flow, pin_versions=False)
        lines = [l for l in txt.strip().split("\n") if l and not l.startswith("#")]
        assert "lfx" in lines
        assert "langchain-openai" in lines


# ===================================================================
# Integration tests: real starter project templates
# ===================================================================


class TestStarterProjects:
    """Integration tests using actual starter project JSON files."""

    @pytest.fixture
    def basic_prompting_flow(self) -> dict:
        path = STARTER_PROJECTS_DIR / "Basic Prompting.json"
        if not path.exists():
            pytest.skip("Basic Prompting.json not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @pytest.fixture
    def simple_agent_flow(self) -> dict:
        path = STARTER_PROJECTS_DIR / "Simple Agent.json"
        if not path.exists():
            pytest.skip("Simple Agent.json not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_basic_prompting_lfx_only(self, basic_prompting_flow):
        """Basic Prompting (no model selected) should only need lfx."""
        result = generate_requirements_from_flow(basic_prompting_flow, pin_versions=False)
        assert result == ["lfx"]

    def test_basic_prompting_with_openai_provider(self, basic_prompting_flow):
        """When OpenAI is selected as provider, langchain-openai should be added."""
        for node in basic_prompting_flow["data"]["nodes"]:
            node_data = node.get("data", {})
            if node_data.get("type") == "LanguageModelComponent":
                template = node_data["node"]["template"]
                template["model"] = {
                    "value": [{"provider": "OpenAI", "name": "gpt-4o-mini"}],
                }
                break

        result = generate_requirements_from_flow(basic_prompting_flow, pin_versions=False)
        assert "lfx" in result
        assert "langchain-openai" in result

    def test_basic_prompting_with_anthropic_provider(self, basic_prompting_flow):
        """When Anthropic is selected, langchain-anthropic should be added."""
        for node in basic_prompting_flow["data"]["nodes"]:
            node_data = node.get("data", {})
            if node_data.get("type") == "LanguageModelComponent":
                template = node_data["node"]["template"]
                template["model"] = {
                    "value": [{"provider": "Anthropic", "name": "claude-3-opus"}],
                }
                break

        result = generate_requirements_from_flow(basic_prompting_flow, pin_versions=False)
        assert "lfx" in result
        assert "langchain-anthropic" in result

    def test_simple_agent_has_community(self, simple_agent_flow):
        """Simple Agent should require langchain-community for its tools."""
        result = generate_requirements_from_flow(simple_agent_flow, pin_versions=False)
        assert "lfx" in result
        assert "langchain-community" in result

    def test_basic_prompting_from_file(self):
        """Test the file-based API."""
        path = STARTER_PROJECTS_DIR / "Basic Prompting.json"
        if not path.exists():
            pytest.skip("Basic Prompting.json not found")
        result = generate_requirements_from_file(path, pin_versions=False)
        assert result == ["lfx"]

    def test_lfx_nightly_package_name(self, basic_prompting_flow):
        """Test specifying lfx-nightly as the package name."""
        result = generate_requirements_from_flow(
            basic_prompting_flow, lfx_package="lfx-nightly", pin_versions=False,
        )
        assert result[0] == "lfx-nightly"
        assert "lfx" not in result

    def test_pinned_output_from_starter(self, basic_prompting_flow):
        """Default (pinned) output should have version specifiers."""
        result = generate_requirements_from_flow(basic_prompting_flow)
        assert result[0].startswith("lfx==")


# ===================================================================
# Data integrity tests
# ===================================================================


class TestDataIntegrity:
    """Verify the mapping tables and dynamic resolution are consistent."""

    def test_all_providers_have_packages(self):
        for provider, pkgs in PROVIDER_PACKAGES.items():
            assert len(pkgs) > 0, f"Provider {provider} has no packages"

    def test_provider_packages_are_strings(self):
        for provider, pkgs in PROVIDER_PACKAGES.items():
            for pkg in pkgs:
                assert isinstance(pkg, str), f"Package {pkg} for {provider} is not a string"

    def test_known_langchain_packages_resolved_by_metadata(self):
        """importlib.metadata should correctly resolve common langchain packages."""
        expected = {
            "langchain_openai": "langchain-openai",
            "langchain_anthropic": "langchain-anthropic",
            "langchain_ollama": "langchain-ollama",
        }
        for import_name, pkg_name in expected.items():
            assert _import_to_package(import_name) == pkg_name

    def test_module_extra_deps_values_are_lists(self):
        for mod, deps in MODULE_EXTRA_DEPS.items():
            assert isinstance(deps, list), f"Extra deps for {mod} should be a list"
