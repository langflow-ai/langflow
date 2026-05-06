"""Tests for langflow_local_constants — the curated metadata of the bundled local model provider.

These constants are the single source of truth for the "Langflow Model" provider that ships
with Langflow so it works without an OPENAI_API_KEY (or any third-party credential).

Why a separate constants file: the metadata is referenced from at least three call sites
(provider_queries, model_metadata, the future setup wizard). Keeping it in one module
prevents drift and follows the repo convention used by ollama_constants, openai_constants, etc.
"""

from __future__ import annotations

import pytest


class TestLangflowLocalProviderName:
    def test_should_expose_canonical_provider_name(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME

        assert LANGFLOW_LOCAL_PROVIDER_NAME == "Langflow Model"

    def test_should_expose_canonical_default_model(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_DEFAULT_MODEL

        # Why qwen2.5:1.5b: ~1GB Q4 quantized, real tool calling support, smallest viable
        # model for the Agent component to function out-of-the-box. See PLAN doc §3.1.
        assert LANGFLOW_LOCAL_DEFAULT_MODEL == "qwen2.5:1.5b"


class TestLangflowLocalModelsDetailed:
    def test_should_contain_at_least_one_model(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_MODELS_DETAILED

        assert len(LANGFLOW_LOCAL_MODELS_DETAILED) >= 1

    def test_every_model_should_use_provider_name_constant(self):
        from lfx.base.models.langflow_local_constants import (
            LANGFLOW_LOCAL_MODELS_DETAILED,
            LANGFLOW_LOCAL_PROVIDER_NAME,
        )

        for model in LANGFLOW_LOCAL_MODELS_DETAILED:
            assert model["provider"] == LANGFLOW_LOCAL_PROVIDER_NAME

    def test_default_model_should_be_marked_default_true(self):
        from lfx.base.models.langflow_local_constants import (
            LANGFLOW_LOCAL_DEFAULT_MODEL,
            LANGFLOW_LOCAL_MODELS_DETAILED,
        )

        default_entries = [m for m in LANGFLOW_LOCAL_MODELS_DETAILED if m["name"] == LANGFLOW_LOCAL_DEFAULT_MODEL]

        assert len(default_entries) == 1
        assert default_entries[0]["default"] is True

    def test_default_model_must_support_tool_calling(self):
        # Why: the Agent component is the most common entry point. A default model
        # that cannot tool-call would break starter projects that use the Agent.
        from lfx.base.models.langflow_local_constants import (
            LANGFLOW_LOCAL_DEFAULT_MODEL,
            LANGFLOW_LOCAL_MODELS_DETAILED,
        )

        default = next(m for m in LANGFLOW_LOCAL_MODELS_DETAILED if m["name"] == LANGFLOW_LOCAL_DEFAULT_MODEL)
        assert default["tool_calling"] is True

    def test_every_model_should_use_langflow_icon(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_MODELS_DETAILED

        for model in LANGFLOW_LOCAL_MODELS_DETAILED:
            assert model["icon"] == "Langflow"


class TestAllowedBaseUrls:
    """SSRF guard: ChatLangflowLocal must reject base_urls outside this whitelist."""

    def test_should_allow_localhost(self):
        from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS

        assert "http://localhost:11434" in ALLOWED_BASE_URLS

    def test_should_allow_loopback_ipv4(self):
        from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS

        assert "http://127.0.0.1:11434" in ALLOWED_BASE_URLS

    def test_should_allow_docker_host(self):
        # Why: when Langflow runs inside a container, Ollama on the host is reached
        # via host.docker.internal:11434 (Docker Desktop on macOS/Windows, and via
        # --add-host on Linux). This is mandatory for Docker support.
        from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS

        assert "http://host.docker.internal:11434" in ALLOWED_BASE_URLS

    def test_should_be_a_frozenset_for_o1_lookup(self):
        # Why frozenset and not list/tuple: O(1) membership test in the SSRF guard
        # (called on every ChatLangflowLocal __init__) and protects against accidental
        # mutation at runtime that could widen the allowlist.
        from lfx.base.models.langflow_local_constants import ALLOWED_BASE_URLS

        assert isinstance(ALLOWED_BASE_URLS, frozenset)


class TestCuratedModelNames:
    """Anti-injection guard: only the curated list of models is accepted."""

    def test_should_expose_curated_model_names_set(self):
        from lfx.base.models.langflow_local_constants import CURATED_MODEL_NAMES

        assert isinstance(CURATED_MODEL_NAMES, frozenset)

    def test_curated_names_should_match_models_detailed(self):
        from lfx.base.models.langflow_local_constants import (
            CURATED_MODEL_NAMES,
            LANGFLOW_LOCAL_MODELS_DETAILED,
        )

        assert frozenset(m["name"] for m in LANGFLOW_LOCAL_MODELS_DETAILED) == CURATED_MODEL_NAMES


class TestModuleSurfaceArea:
    def test_module_should_export_only_constants(self):
        # Why: a constants module must contain ONLY constants — no functions, no classes.
        # File-structure rule: one responsibility per file (DEVELOPMENT_RULE §3).
        import inspect

        from lfx.base.models import langflow_local_constants as mod

        public_members = [name for name in dir(mod) if not name.startswith("_")]
        for name in public_members:
            attr = getattr(mod, name)
            # Allow re-exported helpers/types that are imported but not defined here
            if inspect.getmodule(attr) is not mod:
                continue
            assert not inspect.isfunction(attr), f"{name} is a function — move it to a helpers file"
            assert not inspect.isclass(attr), f"{name} is a class — move it out of constants"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
