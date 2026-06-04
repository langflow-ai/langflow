"""Import-time entrypoint for ``gunicorn --preload``.

gunicorn's master imports this module ONCE before forking. Building + warming the
registry here means the library, imported component modules, and warm flow graphs
all live in the master heap and are inherited by every forked worker via
copy-on-write. Workers are recycled per request when ``--max-requests 1`` is set;
each new fork re-inherits this warm image.

The ``gc.freeze()`` that keeps this heap out of the GC (so refcount/GC traversal
doesn't dirty the shared pages) is NOT done here — it runs in the gunicorn
``pre_fork`` hook (:meth:`lfx.cli.serve_gunicorn.LFXGunicornApp.pre_fork`), i.e.
in the master immediately before each fork, which is the correct point to freeze
the fully-built heap while preserving copy-on-write sharing.
"""

from lfx.cli.serve_app import build_registry_from_env, create_multi_serve_app

registry = build_registry_from_env()
app = create_multi_serve_app(registry=registry)
