"""Constants for lfx package."""

from pathlib import Path

# Base path for components - will be in lfx package when components are moved
BASE_COMPONENTS_PATH = str(Path(__file__).parent / "components")

# Marks a CancelledError as "a human withdrew this run" rather than "the service killed it".
# asyncio gives one exception type for both, so the distinction rides on args and the producers
# stamp it. It lives here rather than next to the graph exceptions because langflow's service
# modules read it too, and importing lfx.graph.* from them early enough drags lfx/graph/__init__
# (which imports Graph) into a circular import. This module imports nothing but pathlib.
USER_CANCELLED_MESSAGE = "LANGFLOW_USER_CANCELLED"
