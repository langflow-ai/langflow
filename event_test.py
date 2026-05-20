import tempfile, pathlib
from lfx.services.extension_events.service import ExtensionEventsService

tmp = pathlib.Path(tempfile.mkdtemp()) / "evt"
svc = ExtensionEventsService(cache_dir=tmp)

# Emit a few events
svc.emit("bundle_reloaded", {"bundle": "my-ext", "reload_id": "r1", "components_added": ["Foo"]})
svc.emit("bundle_reloaded", {"bundle": "my-ext", "reload_id": "r1", "components_added": ["Foo"]})
svc.emit("extension_error", {"code": "test-err", "message": "boom", "flow_id": None})

# Read them back
events, settled = svc.since(0.0)
print(f"{len(events)} events, settled={settled}")
for e in events:
    print(f"  {e.type}: {e.payload}")

# Verify cursor filtering
last_ts = events[-1].timestamp
newer, _ = svc.since(last_ts)
print(f"After cursor: {len(newer)} events (should be 0)")