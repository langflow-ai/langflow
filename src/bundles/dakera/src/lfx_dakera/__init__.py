"""lfx-dakera: Dakera Memory bundle for Langflow.

This package is the distribution unit ``lfx-dakera``. At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py``
and registers ``DakeraMemoryComponent`` under the namespaced ID
``ext:dakera:DakeraMemoryComponent@official``.

Quick-start:
    docker run -p 3300:3300 -e DAKERA_API_KEY=demo ghcr.io/dakera-ai/dakera:latest
    pip install lfx-dakera
    langflow run
"""

from lfx_dakera.components.dakera.dakera_memory import DakeraMemoryComponent

__all__ = ["DakeraMemoryComponent"]
