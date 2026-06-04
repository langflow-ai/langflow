"""Import-time entrypoint for ``gunicorn --preload``.

gunicorn's master imports this module ONCE before forking. Building + warming the
registry here means the library, imported component modules, and warm flow graphs
all live in the master heap and are inherited by every forked worker via
copy-on-write. ``gc.freeze()`` keeps that heap out of the GC so refcount/GC
traversal doesn't dirty the shared pages. Workers are recycled per request
(``max_requests=1``); each new fork re-inherits this frozen, warm image.
"""

import gc

from lfx.cli.serve_app import build_registry_from_env, create_multi_serve_app

registry = build_registry_from_env()
app = create_multi_serve_app(registry=registry)

# Must run in the master, after the full preload, before any fork. Placing it at
# module-import bottom guarantees that under --preload.
gc.freeze()
