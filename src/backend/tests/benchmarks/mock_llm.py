"""BaseChatOpenAI monkey-patch for cold-start benchmarks.

Locked by D-04 (CONTEXT.md): LLM calls in fixtures are mocked at call site so
that the full import-time cost (openai + langchain_openai + transitive deps) is
still paid. The only thing eliminated is the real HTTP request.

Correction from CONTEXT.md's original wording: patch `_generate` / `_agenerate`,
NOT `_call`. `_call` does NOT exist on BaseChatOpenAI in langchain-openai 1.1.12
(the version in this workspace). See Pitfall 4 in 01-RESEARCH.md.

Activation: set LFX_BENCHMARK_MOCK_LLM=1 in the environment. The harness sets
this in every scenario that would otherwise attempt a real API call.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid paying the import cost when the mock is NOT enabled
    from langchain_core.outputs import ChatResult as _ChatResult


_FIXED_CONTENT = "Benchmark-fixed response."


def _build_fixed_response() -> _ChatResult:
    """Construct the ChatResult lazily. Import langchain_core only when we patch."""
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=_FIXED_CONTENT))])


def _mock_generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG001
    return _build_fixed_response()


async def _mock_agenerate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG001
    return _build_fixed_response()


def install_mock() -> None:
    """Monkey-patch BaseChatOpenAI._generate and ._agenerate.

    Idempotent: safe to call multiple times. Records the patch on the class
    itself so subsequent imports of BaseChatOpenAI pick it up.

    Costs paid: importing langchain_openai.chat_models.base (several hundred ms
    cold). This is the desired cold-start cost per D-04; the only thing we mock
    out is the NETWORK side of the call, not the import chain.
    """
    # Import at call time. This is what triggers the full openai + langchain_openai
    # cold-start cost. Do NOT hoist to module scope; the mock must remain free
    # for code that imports mock_llm for typing purposes only.
    from langchain_openai.chat_models.base import BaseChatOpenAI

    BaseChatOpenAI._generate = _mock_generate  # type: ignore[assignment]
    BaseChatOpenAI._agenerate = _mock_agenerate  # type: ignore[assignment]


def install_if_enabled() -> bool:
    """Call install_mock() iff LFX_BENCHMARK_MOCK_LLM is truthy. Returns True if installed."""
    if os.environ.get("LFX_BENCHMARK_MOCK_LLM"):
        install_mock()
        return True
    return False


# Auto-install on module import so the JSON-fixture code path can trigger the mock via the
# LFX_BENCHMARK_BOOTSTRAP_MODULE hook in lfx/_bench.py. No-op when LFX_BENCHMARK_MOCK_LLM is unset.
# Kept at module scope (not inside a function) so a single import is enough; this is what the
# benchmark driver relies on since the JSON fixture path does not execute any fixture Python code.
install_if_enabled()
