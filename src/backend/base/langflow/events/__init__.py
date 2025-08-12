# Expose the external Events class that OpenSearch expects
# This avoids the import conflict when opensearch tries "from events import Events"
try:
    import importlib
    import sys

    external_events = importlib.import_module("events")
    Events = external_events.Events
except (ImportError, AttributeError):
    # Fallback if external events package isn't available
    class Events:
        pass


# Import our own event manager
from .event_manager import EventManager
