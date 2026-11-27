# Feature: Hot reload of LANGFLOW_LOAD_FLOWS_PATH

> Status: Implemented, pending review
> Related: [langflow-ai/langflow#11918](https://github.com/langflow-ai/langflow/issues/11918)

## Summary

`LANGFLOW_LOAD_FLOWS_PATH` loads flow JSON files once, at startup. To pick up a
changed or added file, you had to restart Langflow. With
`LANGFLOW_WATCH_FLOWS_PATH=true`, Langflow checks the directory while it runs
and applies new and changed files without a restart.

The setting is off by default, so existing deployments behave the same.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `LANGFLOW_WATCH_FLOWS_PATH` | `false` | Turns on the watch. Requires `LANGFLOW_LOAD_FLOWS_PATH`. |
| `LANGFLOW_FS_FLOWS_POLLING_INTERVAL` | `10000` | Milliseconds between checks. This existing setting is shared with the `fs_path` flow sync. |
| `LANGFLOW_LOAD_FLOWS_OVERWRITE_ON_NAME_MATCH` | `false` | Applies to reloads the same way it applies at startup. |
| `LANGFLOW_LOAD_FLOWS_PRESERVE_VARIABLE_BINDINGS` | `true` | Applies to reloads the same way it applies at startup. |

## Behavior

- **What is watched.** Only top-level `*.json` files in the directory.
  Subdirectories are ignored, as they are at startup.
- **New or changed file.** A file is reapplied when its modification time
  differs from the one recorded when it was last applied. An older time counts
  too, so restoring a backup with `rsync -a` or `cp -p` is picked up. It goes through
  `upsert_flow_from_file`, the same function startup loading uses, and is owned
  by the same superuser.
- **Unchanged file.** Skipped. No database write.
- **Deleted file.** The flow stays in the database. Langflow logs one warning:
  `Flow file <name> was removed from LANGFLOW_LOAD_FLOWS_PATH; its flow was left in place.`
- **Invalid JSON.** The file is skipped with a warning, and other files in the
  same pass still apply. The file is retried the next time it changes.
- **Edited in the visual editor.** The file wins. When a file changes and its
  flow was edited in the UI since the file was last applied, Langflow logs a
  warning before overwriting the edits.
- **Misconfiguration.** If `LANGFLOW_LOAD_FLOWS_PATH` is unset or isn't a
  directory, the watch logs a warning and does not start. Langflow keeps
  running.

## Design

The full decision record, with alternatives, is in the coursework design note.
The short version:

- **Polling, not filesystem events.** Event APIs such as inotify are unreliable
  on network volumes and Kubernetes ConfigMaps, which replace files by swapping
  symlinks. Polling a directory's `stat` results is cheap and works everywhere.
- **One writer per pass.** Every worker starts the watch task. Each pass first
  takes the `load-flows-path-watch` row in the `trigger_lease` table
  (`langflow.services.triggers.leases`), so only one process writes. This works
  on SQLite and PostgreSQL. The lease TTL is the larger of 30 seconds and three
  polling intervals.
- **Migration safety.** Each pass runs inside `async_writing(name="flow_watch")`
  and skips itself while a migration pauses writes.
- **UI-edit detection by fingerprint.** The watcher stores a SHA-256 hash of
  each applied flow's name, description, and data. A different hash at the next
  reload means someone edited the flow. Timestamps aren't used because
  `flow.updated_at` is stored without a time zone and written in both local time
  and UTC.
- **Not `fs_path`.** The existing `sync_flows_from_fs` mirror is two-way and
  restricted to each user's own data directory. Pointing it at the load
  directory would make UI saves of those flows fail.

## Code

| File | Change |
|---|---|
| `src/lfx/src/lfx/services/settings/groups/components.py` | Adds `watch_flows_path`. |
| `src/backend/base/langflow/initial_setup/setup.py` | Adds `watch_flows_from_directory` and its helpers. |
| `src/backend/base/langflow/main.py` | Starts the task in the lifespan when enabled, and cancels it on shutdown. |

## Tests

- `src/backend/tests/unit/initial_setup/test_watch_flows_from_directory.py`:
  15 tests of a single pass, covering new, changed, unchanged, removed, and
  invalid files, the lease, the UI-edit warning, and configuration warnings.
- `src/backend/tests/unit/initial_setup/test_watch_flows_system.py`: 3 tests
  that start the app, change files on disk, and read the flows over the API.

## Known limitations

- **Deletes aren't synced.** Removing a file never deletes a flow.
- **Lease takeover.** If a different process takes over the lease, it starts
  with its own record of applied files and may reapply them. In that case a UI
  edit can be overwritten without the warning.
- **Clock granularity.** A file rewritten within the filesystem's timestamp
  resolution, which is up to two seconds on some filesystems, can be missed
  until it changes again.
