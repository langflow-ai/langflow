"""Register extra OpenAI-compatible model providers in Langflow.

Importing this package arms a lazy hook that injects the configured providers
(DeepSeek, GLM/Z.ai by default) into Langflow's model catalog when Langflow
loads — without editing any Langflow / lfx source file.

Public API:
    from langflow_extra_providers import apply
    apply()        # force registration immediately (returns provider names)
"""

from __future__ import annotations

import logging

from .patch import apply

logger = logging.getLogger("langflow_extra_providers")

__all__ = ["apply"]
__version__ = "0.1.0"

# Arm the auto-apply hook on import. Wrapped so a failure here can never break
# the host interpreter (the .pth file imports us at startup for every process).
try:
    from .hook import install as _install

    _install()
except Exception:  # noqa: BLE001
    logger.exception("langflow-extra-providers: failed to install auto-apply hook")
