"""Multiplayer writes to a flow: ``POST /api/v2/flows/{id}/ops`` on the flow's operation log.

One engine object per process (``LANGFLOW_FLOW_ENGINE``) does every graph
computation; the server code is the same for every engine. Three write modes
(``LANGFLOW_FLOW_WRITE_MODE``):

- ``nocache``: each write builds the graph from ``Flow.data``, applies the
  batch, appends the log rows and writes ``Flow.data`` in one transaction.
- ``cache``: as ``nocache``, but the graph stays loaded in a per-process LRU
  cache and catches up from the log when another process wrote.
- ``wal``: the cache, and writers append log rows only. A checkpoint task
  writes ``Flow.data`` every ``flow_revision_checkpoint_cadence`` revisions.

Every operation-log write takes ``pg_advisory_xact_lock`` on the flow
(``oplog.lock_flow``) and reads the head revision from the log.
"""
