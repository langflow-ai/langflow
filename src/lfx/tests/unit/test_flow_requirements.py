"""Tests for flow_requirements module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.utils.flow_requirements import (
    MODULE_EXTRA_DEPS,
    _detect_providers_from_template,
    _extract_component_requirements,
    _extract_imports,
    _get_import_to_dist_map,
    _get_lfx_provided_imports,
    _get_lfx_transitive_dists,
    _import_to_package,
    _pin_version,
    _resolve_embedding_provider_packages,
    _resolve_provider_packages,
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
    def test_import_to_dist_map_returns_mapping(self):
        result = _get_import_to_dist_map()
        # Returns a read-only MappingProxyType (not a plain dict)
        from collections.abc import Mapping

        assert isinstance(result, Mapping)
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
        import_map = _get_import_to_dist_map()
        # Only assert for imports that are resolvable in this environment;
        # packages_distributions() can only map installed packages.
        expected = ["orjson", "fastapi", "pydantic", "langchain", "pandas", "PIL"]
        resolvable = [imp for imp in expected if imp in import_map]
        assert len(resolvable) > 0, "No expected imports are resolvable in this environment"
        for imp in resolvable:
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

    def test_azure_openai_provider(self):
        template = {
            "model": {
                "value": [{"provider": "Azure OpenAI", "name": "gpt-4o"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"Azure OpenAI"}

    def test_amazon_bedrock_provider(self):
        template = {
            "model": {
                "value": [{"provider": "Amazon Bedrock", "name": "anthropic.claude-3"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"Amazon Bedrock"}

    def test_ibm_watsonx_provider(self):
        template = {
            "model": {
                "value": [{"provider": "IBM watsonx.ai", "name": "ibm/granite-13b"}],
            },
        }
        result = _detect_providers_from_template(template)
        assert result == {"IBM watsonx.ai"}

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
        """Imports that are transitively provided by lfx should not appear as requirements.

        Only tests against imports that are resolvable in this environment,
        since packages_distributions() can only map installed packages.
        """
        provided = _get_lfx_provided_imports()
        candidates = ["orjson", "fastapi", "pandas", "pydantic"]
        resolvable = [imp for imp in candidates if imp in provided]
        if not resolvable:
            pytest.skip("None of the test imports are lfx-provided in this environment")
        code = "\n".join(f"import {imp}" for imp in resolvable)
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

    def test_azure_openai_provider_adds_package(self):
        node = _make_node(
            "LLM",
            "",
            template_extra={
                "model": {"value": [{"provider": "Azure OpenAI", "name": "gpt-4o"}]},
            },
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-openai" in result

    def test_amazon_bedrock_provider_adds_package(self):
        node = _make_node(
            "LLM",
            "",
            template_extra={
                "model": {"value": [{"provider": "Amazon Bedrock", "name": "anthropic.claude-3"}]},
            },
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-aws" in result

    def test_ibm_watsonx_provider_adds_package(self):
        node = _make_node(
            "LLM",
            "",
            template_extra={
                "model": {"value": [{"provider": "IBM watsonx.ai", "name": "ibm/granite-13b"}]},
            },
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-ibm" in result

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
        lines = [line for line in txt.strip().split("\n") if line and not line.startswith("#")]
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

    def test_basic_prompting_includes_anthropic(self, basic_prompting_flow):
        """Basic Prompting (Anthropic pre-selected) should need lfx + anthropic deps."""
        result = generate_requirements_from_flow(basic_prompting_flow, pin_versions=False)
        assert "lfx" in result
        assert "langchain-anthropic" in result

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
        assert "lfx" in result
        assert "langchain-anthropic" in result

    def test_lfx_nightly_package_name(self, basic_prompting_flow):
        """Test specifying lfx-nightly as the package name."""
        result = generate_requirements_from_flow(
            basic_prompting_flow,
            lfx_package="lfx-nightly",
            pin_versions=False,
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
    """Verify dynamic resolution and mapping tables are consistent."""

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


class TestResolveProviderPackages:
    """Verify dynamic provider resolution via inspect."""

    @staticmethod
    def _skip_if_provider_not_loaded(provider_name: str):
        """Skip test if the provider's component class isn't loaded in MODEL_PROVIDERS_DICT.

        MODEL_PROVIDERS_DICT only contains providers whose packages are
        installed in the current environment.
        """
        try:
            from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT
        except ImportError:
            pytest.skip("MODEL_PROVIDERS_DICT not available")
        if provider_name not in MODEL_PROVIDERS_DICT:
            pytest.skip(f"{provider_name} component not loaded (package not installed)")

    def test_openai_provider_resolves(self):
        self._skip_if_provider_not_loaded("OpenAI")
        packages = _resolve_provider_packages("OpenAI")
        assert "langchain-openai" in packages

    def test_anthropic_provider_resolves(self):
        self._skip_if_provider_not_loaded("Anthropic")
        packages = _resolve_provider_packages("Anthropic")
        assert "langchain-anthropic" in packages

    def test_amazon_bedrock_provider_resolves(self):
        self._skip_if_provider_not_loaded("Amazon Bedrock")
        packages = _resolve_provider_packages("Amazon Bedrock")
        assert "langchain-aws" in packages

    def test_google_provider_resolves(self):
        self._skip_if_provider_not_loaded("Google Generative AI")
        packages = _resolve_provider_packages("Google Generative AI")
        assert "langchain-google-genai" in packages

    def test_ollama_provider_resolves(self):
        self._skip_if_provider_not_loaded("Ollama")
        packages = _resolve_provider_packages("Ollama")
        assert "langchain-ollama" in packages

    def test_unknown_provider_returns_empty(self):
        packages = _resolve_provider_packages("NonexistentProvider")
        assert packages == set()

    def test_function_level_imports_captured(self):
        """Verify imports inside function bodies (e.g. build_model) are captured.

        This is critical because many provider components use lazy imports
        inside methods like ``build_model()`` rather than at module level.
        """
        self._skip_if_provider_not_loaded("Amazon Bedrock")
        packages = _resolve_provider_packages("Amazon Bedrock")
        # boto3 and langchain_aws are imported inside build_model(), not at module level
        assert "boto3" in packages
        assert "langchain-aws" in packages

    def test_all_registered_providers_resolve_to_packages(self):
        """Every provider in MODEL_PROVIDERS_DICT should resolve to at least one package."""
        try:
            from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT
        except ImportError:
            pytest.skip("MODEL_PROVIDERS_DICT not available")
        for provider_name in MODEL_PROVIDERS_DICT:
            packages = _resolve_provider_packages(provider_name)
            assert len(packages) > 0, f"Provider {provider_name} resolved to no packages"


class TestResolveEmbeddingProviderPackages:
    """Verify embedding provider resolution via unified models metadata."""

    def test_openai_embedding_resolves(self):
        packages = _resolve_embedding_provider_packages("OpenAI")
        assert "langchain-openai" in packages

    def test_google_embedding_resolves(self):
        packages = _resolve_embedding_provider_packages("Google Generative AI")
        assert "langchain-google-genai" in packages

    def test_ollama_embedding_resolves(self):
        packages = _resolve_embedding_provider_packages("Ollama")
        assert "langchain-ollama" in packages

    def test_unknown_provider_returns_empty(self):
        packages = _resolve_embedding_provider_packages("NonexistentProvider")
        assert packages == set()

    def test_language_only_provider_returns_empty(self):
        """Providers without embedding support should return empty (not warn)."""
        packages = _resolve_embedding_provider_packages("Anthropic")
        assert packages == set()

    def test_ibm_watsonx_embedding_resolves(self):
        packages = _resolve_embedding_provider_packages("IBM WatsonX")
        assert "langchain-ibm" in packages

    def test_all_embedding_providers_resolve(self):
        """Every provider in EMBEDDING_PROVIDER_CLASS_MAPPING should resolve to a package."""
        from lfx.base.models.unified_models import EMBEDDING_PROVIDER_CLASS_MAPPING

        for provider in EMBEDDING_PROVIDER_CLASS_MAPPING:
            packages = _resolve_embedding_provider_packages(provider)
            assert len(packages) > 0, f"Embedding provider '{provider}' resolved to no packages"

    def test_embedding_only_flow(self):
        """A flow with only an embedding model should still get provider packages."""
        node = _make_node(
            "EmbeddingModel",
            "from lfx.base.embeddings.model import LCEmbeddingsModel",
            template_extra={
                "model": {"value": [{"provider": "OpenAI", "name": "text-embedding-3-small"}]},
            },
        )
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert "langchain-openai" in result


# ===================================================================
# Error handling tests
# ===================================================================


class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_generate_requirements_from_file_not_found(self, tmp_path):
        """FileNotFoundError should propagate for missing files."""
        with pytest.raises(FileNotFoundError):
            generate_requirements_from_file(tmp_path / "nonexistent.json")

    def test_generate_requirements_from_file_invalid_json(self, tmp_path):
        """JSONDecodeError should propagate for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            generate_requirements_from_file(bad_file)

    def test_generate_requirements_from_file_wrong_structure(self, tmp_path):
        """A valid JSON file that isn't a flow should still produce a result (just lfx)."""
        wrong_file = tmp_path / "wrong.json"
        wrong_file.write_text('{"not": "a flow"}', encoding="utf-8")
        result = generate_requirements_from_file(wrong_file, pin_versions=False)
        assert result == ["lfx"]

    def test_flow_with_empty_code_value(self):
        """A node with an empty code string should not crash."""
        node = _make_node("Empty", "")
        flow = _make_flow(node)
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]

    def test_flow_with_malformed_node(self):
        """Nodes with missing expected fields should be handled gracefully."""
        flow = {"data": {"nodes": [{"type": "genericNode", "data": {}}]}}
        result = generate_requirements_from_flow(flow, pin_versions=False)
        assert result == ["lfx"]


# ===================================================================
# Typer CLI tests: lfx requirements
# ===================================================================


class TestTyperRequirementsCommand:
    """Tests for the typer-based ``lfx requirements`` CLI command."""

    @pytest.fixture
    def runner(self):
        from typer.testing import CliRunner

        return CliRunner()

    @pytest.fixture
    def app(self):
        from lfx.__main__ import app

        return app

    @pytest.fixture
    def flow_file(self, tmp_path):
        flow = _make_flow(_make_node("Simple", "import lfx"))
        path = tmp_path / "flow.json"
        path.write_text(json.dumps(flow), encoding="utf-8")
        return path

    def test_happy_path_stdout(self, runner, app, flow_file):
        result = runner.invoke(app, ["requirements", str(flow_file), "--no-pin"])
        assert result.exit_code == 0
        assert "lfx" in result.output

    def test_output_flag_writes_file(self, runner, app, flow_file, tmp_path):
        out = tmp_path / "requirements.txt"
        result = runner.invoke(app, ["requirements", str(flow_file), "-o", str(out), "--no-pin"])
        assert result.exit_code == 0
        assert out.exists()
        assert "lfx" in out.read_text(encoding="utf-8")
        assert "Requirements written to" in result.output

    def test_no_lfx_flag(self, runner, app, flow_file):
        result = runner.invoke(app, ["requirements", str(flow_file), "--no-lfx", "--no-pin"])
        assert result.exit_code == 0
        # With --no-lfx and only lfx imports, no packages should appear after header
        lines = [line for line in result.output.strip().split("\n") if line and not line.startswith("#")]
        assert "lfx" not in lines

    def test_no_pin_flag(self, runner, app, flow_file):
        result = runner.invoke(app, ["requirements", str(flow_file), "--no-pin"])
        assert result.exit_code == 0
        assert "==" not in result.output

    def test_default_pins_versions(self, runner, app, flow_file):
        result = runner.invoke(app, ["requirements", str(flow_file)])
        assert result.exit_code == 0
        assert "lfx==" in result.output

    def test_lfx_package_flag(self, runner, app, flow_file):
        result = runner.invoke(app, ["requirements", str(flow_file), "--lfx-package", "lfx-nightly", "--no-pin"])
        assert result.exit_code == 0
        assert "lfx-nightly" in result.output
        # Should not contain bare "lfx" as a separate line
        lines = [line for line in result.output.strip().split("\n") if line and not line.startswith("#")]
        assert "lfx" not in lines

    def test_file_not_found(self, runner, app, tmp_path):
        result = runner.invoke(app, ["requirements", str(tmp_path / "missing.json")])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_invalid_json(self, runner, app, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = runner.invoke(app, ["requirements", str(bad)])
        assert result.exit_code == 1
        assert "Error" in result.output
