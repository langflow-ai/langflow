"""Primary MEAS-01 / MEAS-07 fixture: ChatInput -> Prompt -> LanguageModel -> ChatOutput.

D-01 (CONTEXT.md): primary fixture is `basic_prompting` because it exercises the
common openai + langchain_openai import path without pulling in heavy RAG deps.
Clean signal for the dep-install-vs-import dominance question (MEAS-07).

Before building the graph, we install the BaseChatOpenAI mock IFF the env var
is set. D-04 locks this so the harness runs with no OPENAI_API_KEY in CI.
The mock is a NO-OP when LFX_BENCHMARK_MOCK_LLM is unset (fixture still works
against a real API key for local dev).
"""

from __future__ import annotations

from langflow.initial_setup.starter_projects.basic_prompting import basic_prompting_graph

from src.backend.tests.benchmarks.mock_llm import install_if_enabled

# MUST run BEFORE basic_prompting_graph() constructs the OpenAIModelComponent,
# because ChatOpenAI._generate/._agenerate are bound at module import time.
# install_if_enabled() short-circuits if LFX_BENCHMARK_MOCK_LLM is not set.
install_if_enabled()

# Module-level `graph = ...` is REQUIRED by `lfx run <path>.py`.
graph = basic_prompting_graph()
