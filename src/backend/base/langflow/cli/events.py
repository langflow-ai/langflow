"""JSON-lines events for commands that an admin UI runs as a child process."""

from __future__ import annotations

import json
import sys
from typing import Any


def emit(event: str, **fields: Any) -> None:
    """Write one event as a JSON object on its own line of stdout, flushed so a reader sees it at once."""
    sys.stdout.write(json.dumps({"event": event, **fields}, default=str) + "\n")
    sys.stdout.flush()
