"""lfx-asyntai: Asyntai AI Chatbot bundle.

This package is the distribution unit ``lfx-asyntai``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers three components under the namespaced IDs
``ext:asyntai:<ClassName>@official``:

- ``AsyntaiAskComponent``: ask the Asyntai AI chatbot a question about a website.
- ``AsyntaiAddKnowledgeComponent``: add a web page or a text to its knowledge base.
- ``AsyntaiLeadsComponent``: list the leads that visitors left in the chat.

Asyntai (https://asyntai.com) is an AI chatbot for websites.  The components
call its public REST API directly with ``httpx`` and need only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_asyntai.components.asyntai import (
    AsyntaiAddKnowledgeComponent,
    AsyntaiAskComponent,
    AsyntaiLeadsComponent,
)

__all__ = ["AsyntaiAddKnowledgeComponent", "AsyntaiAskComponent", "AsyntaiLeadsComponent"]
