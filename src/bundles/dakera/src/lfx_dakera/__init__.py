"""lfx-dakera: Dakera Memory bundle for Langflow.

This package is the distribution unit ``lfx-dakera``. At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py``
and registers ``DakeraMemoryComponent`` under the namespaced ID
``ext:dakera:DakeraMemoryComponent@official``.

Quick-start:
    # Dakera server (self-hosting bundles a MinIO object store):
    git clone https://github.com/dakera-ai/dakera-deploy && cd dakera-deploy
    docker compose -f docker/docker-compose.yml up -d   # server on :3000

    pip install lfx-dakera
    langflow run
"""

from lfx_dakera.components.dakera.dakera_memory import DakeraMemoryComponent

__all__ = ["DakeraMemoryComponent"]
