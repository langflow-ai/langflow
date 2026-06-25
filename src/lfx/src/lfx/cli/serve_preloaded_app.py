"""Import-time entrypoint for ``gunicorn --preload``.

gunicorn's master imports this module ONCE before forking. Building + warming the
registry here means the library, imported component modules, and warm flow graphs
all live in the master heap and are inherited by every forked worker via
copy-on-write. Workers are recycled after ``--max-requests`` requests; each new fork
re-inherits this warm image.

The ``gc.freeze()`` that keeps this heap out of the GC (so refcount/GC traversal
doesn't dirty the shared pages) is NOT done here — it runs in the gunicorn
``pre_fork`` hook (:meth:`lfx.cli.serve_gunicorn.LFXGunicornApp.pre_fork`), i.e.
in the master immediately before each fork, which is the correct point to freeze
the fully-built heap while preserving copy-on-write sharing.
"""

import os

from lfx.cli.serve_app import build_registry_from_env, create_multi_serve_app
from lfx.cli.serve_identity import IdentityConfig

registry = build_registry_from_env()
# Same env round-trip as the uvicorn factory (create_serve_app): _launch_workers
# exports LFX_SERVE_IDENTITY_* before importing this module for gunicorn --preload,
# so the warm shared app enforces the operator's identity config.
app = create_multi_serve_app(registry=registry, identity_config=IdentityConfig.from_env(os.environ))

# WSGI bridge entrypoint for the opt-in ``lfx serve --use-sync-workers`` mode, which
# runs gunicorn's blocking ``sync`` worker so the kernel routes each request to an
# idle worker (an async worker keeps accepting connections while busy, which can
# queue a second request behind an in-flight one even when other workers are idle).
# The ASGI->WSGI bridge is created LAZILY on first request, never at preload: a2wsgi
# spins up a background event-loop thread, and threads do not survive fork(), so a
# bridge built in the preload master would be dead in every forked worker. Building
# it on first call constructs it inside the (post-fork) worker process instead.
_bridge = None


def wsgi_application(environ, start_response):
    """Lazily-constructed a2wsgi bridge wrapping the preloaded ASGI ``app``."""
    global _bridge  # noqa: PLW0603
    if _bridge is None:
        try:
            from a2wsgi import ASGIMiddleware
        except ImportError as exc:  # pragma: no cover - exercised via --use-sync-workers without the dep
            msg = "lfx serve --use-sync-workers requires the 'a2wsgi' package. Install it with: pip install a2wsgi"
            raise RuntimeError(msg) from exc
        _bridge = ASGIMiddleware(app)
    return _bridge(environ, start_response)
