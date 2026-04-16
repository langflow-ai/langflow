"""Secondary MEAS-01 fixture: document loader + embeddings + LLM.

D-02 (CONTEXT.md): secondary fixture = `document_qa` for worst-case RAG comparison.
NOT used for MEAS-07 dep-install isolation. Only `basic_prompting` is used there.

OPEN QUESTION A (01-RESEARCH.md Open Questions 2): `document_qa` uses FileComponent
which may require an actual file on disk. If `lfx run fixtures/document_qa.py` fails
with a "file not found" or similar error during plan 05 driver work, add a 1KB text
fixture at `src/backend/tests/benchmarks/fixtures/sample_doc.txt` and wire FileComponent
to it. Do NOT pre-emptively create that file here; confirm the failure mode first.
"""

from __future__ import annotations

from langflow.initial_setup.starter_projects.document_qa import document_qa_graph

from src.backend.tests.benchmarks.mock_llm import install_if_enabled

install_if_enabled()

graph = document_qa_graph()
