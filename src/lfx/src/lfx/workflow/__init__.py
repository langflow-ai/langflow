"""V2 workflow contract layer shared by the langflow backend and ``lfx serve``.

This package holds the protocol-agnostic pieces of the V2 workflow API:

    - ``adapters``: the ``StreamAdapter`` protocol, the ``langflow``/``agui`` SSE
      adapters, and the registry (``get_stream_adapter`` / ``available_protocols``).
    - ``agui_translator``: translates EventManager events into AG-UI events.
    - ``converters``: parses ``WorkflowRunRequest`` and builds the structured
      ``WorkflowExecutionResponse``.

It depends only on ``lfx.schema.workflow`` and ``ag_ui`` (no langflow imports),
so both runtimes consume one contract. The langflow backend layers its stateful
"vehicle" (database, job queue, auth) on top.
"""
