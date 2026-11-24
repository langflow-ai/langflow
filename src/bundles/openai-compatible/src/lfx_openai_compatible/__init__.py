"""lfx-openai-compatible: generic OpenAI-compatible model-provider bundle.

Distribution unit ``lfx-openai-compatible``. At runtime Langflow's loader
discovers the ``extension.json`` shipped alongside this ``__init__.py`` and
registers its ``providers[]`` entry, merging an **OpenAI Compatible** provider
into the unified model system. Any endpoint that speaks the OpenAI API shape
(OpenRouter, Together, Groq, Fireworks, self-hosted vLLM/TGI/LM Studio, ...)
can be configured through it, so the provider reuses ``ChatOpenAI`` /
``OpenAIEmbeddings`` and discovers models live from the endpoint's
``/v1/models`` route (see :mod:`lfx_openai_compatible.discovery`).

Requested in https://github.com/langflow-ai/langflow/issues/12839.
"""
