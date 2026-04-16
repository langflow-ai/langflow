"""No-op flow for the MEAS-01 bare-boot scenario.

D-03 (CONTEXT.md) locks the bare-boot scenario as `lfx run <no-op flow>`,
NOT `lfx --help`, because `--help` short-circuits before services init and
component-index warmup. This flow runs the FULL cold-start path (service
init + component index + graph build) with the MINIMAL amount of work done
inside the flow itself: a single ChatInput -> ChatOutput with an empty message.

No LLM, no tools, no pandas/langchain_core imports triggered by the flow.
The cost measured here is:
  - Python interpreter startup
  - `import lfx` (transitive imports)
  - service init (`initialize_services()`)
  - component index warmup (`get_and_cache_all_types_dict()`)
  - graph construction for two cheap nodes
  - single-vertex-build execution.

Assumption A6 (RESEARCH.md): a ChatInput -> ChatOutput graph is runnable
without additional config.
"""

from __future__ import annotations

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

chat_input = ChatInput()
chat_input.set(input_value="")

chat_output = ChatOutput()
chat_output.set(input_value=chat_input.message_response)

# Module-level `graph = ...` is REQUIRED by `lfx run <path>.py`.
# See src/lfx/src/lfx/cli/run.py (pitfall 5 in 01-RESEARCH.md).
graph = Graph(start=chat_input, end=chat_output)
