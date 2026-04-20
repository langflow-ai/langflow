"""Scoping conftest for the benchmarks tree.

These scripts are entry points for hyperfine / pyinstrument / -X importtime;
they are NOT pytest tests. We ignore collection here so `pytest src/backend/tests`
continues to work without accidentally running benchmark drivers.

Plan 02 extends this file with the LFX_BENCHMARK_MOCK_LLM autouse fixture
(BaseChatOpenAI._generate / ._agenerate monkey-patch). Intentionally left
without that fixture here, plan 02 owns the mock.
"""

from __future__ import annotations

# Opt out of pytest collection for every .py under this directory.
# See pytest docs: https://docs.pytest.org/en/stable/reference/customize.html#confval-collect_ignore_glob
collect_ignore_glob = ["*.py"]
