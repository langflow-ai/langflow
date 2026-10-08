# Managed SQLite upgrade controller

The 1.13 controller stages the signed one-time Chroma reader, stops the selected
old worker family, verifies a metadata backup and maintenance receipt, starts the
new application, and waits for its migration-aware readiness endpoint. Existing
vectors are migrated automatically by the application's storage coordinator.

This controller supports one host, local storage and a SQLite application
metadata database. Run it as the **non-root application account**, from outside
the old supervisor's session. The old application must have a foreground
supervisor that is the leader of its own dedicated POSIX session. All API,
background and Memory workers must remain in that session. Windows services,
container orchestrators, distributed workers, PostgreSQL metadata and workers
that detach into other sessions require their deployment-specific controller.
The controller fails closed when it cannot inspect a worker or listener.

Disable the service manager's external restart policy before invoking this
command and keep it disabled throughout migration. `--external-restarts-disabled`
records this explicit operator contract. The controller cannot prove that an
external manager will not recreate a terminated service. Do not point it at a
shared login shell, a machine-wide service manager or an unrelated process.

Install 1.13 into a clean environment, retaining the original data paths and
application configuration. Provision Docker, the qualified cosign release and
the helper release digest, as described in
[the helper release instructions](../../tools/chroma_migration_helper/README.md).
Offline kits must be loaded and verified using those instructions first. The
controller checks signature verification and local image availability before
stopping any worker. Root-owned private files must be transferred to the
application account through the deployment manager rather than made public.

Obtain the old foreground supervisor PID from its deployment manager, then get
its exact creation time using the new environment's installed psutil:

```sh
/path/to/1.13/bin/python -c 'import psutil, sys; print(psutil.Process(int(sys.argv[1])).create_time())' 12345
```

Copy the full printed value into `--supervisor-created`. Do not use `ps -o lstart`,
which rounds away the required precision. Linux journal identities additionally
retain kernel start ticks and boot ID so clock adjustments cannot invalidate a
paused family. Run the controller from the **new** environment:

```sh
export LANGFLOW_KB_MIGRATION_HELPER_IMAGE=ghcr.io/langflow-ai/langflow-chroma-migration@sha256:<release-digest>
/path/to/1.13/bin/python -m langflow.services.knowledge_base_storage.controller \
  --root /absolute/knowledge-bases \
  --database /absolute/langflow.db \
  --state /private/upgrade-1.13 \
  --supervisor-pid 12345 \
  --supervisor-created 1234567890.0 \
  --cwd /absolute/application-directory \
  --port 7860 \
  --external-restarts-disabled \
  -- /path/to/1.13/bin/python -m langflow run --host 127.0.0.1 --port 7860
```

The PID and creation time in this example are placeholders. Never guess them.
The command after `--` is an argument vector, executed directly without a shell.
It must remain in the foreground and honor the existing instance configuration.
Pass credentials through the application's normal private environment or secret
configuration, not command arguments, because the private journal records argv.
The controller explicitly sets the knowledge-base root, SQLite metadata URL,
maintenance receipt and helper settings in the new process's environment.
Do not override those paths with CLI arguments or a different configuration file.

Before shutdown, the controller suspends the exact supervisor, inventories and
suspends its entire session, and durably records every PID and creation time.
Only then does it terminate those recorded identities. After the graceful stop
period (30 seconds by default), it kills remaining matching workers and verifies
that the family exited. PID reuse, escaped sessions and unexpected workers stop
the upgrade. Failure before the stop is committed resumes workers suspended by
the controller. After the stop is committed, it leaves the old service stopped
and preserves the journal for forward recovery.

The maintenance verifier creates and checks a consistent SQLite metadata backup,
fingerprints every legacy source, and writes a private receipt. The new process
is launched only after this barrier. It records its own identity atomically
before executing the application, so resuming after a parent-controller crash
cannot launch a second instance. The controller command uses an IPv4 loopback listener. Readiness requires both a successful
`/healthz?require_storage_ready=true`
response and a listening socket owned by that exact new supervisor's session.
An unrelated healthy service on the port cannot satisfy the gate.

A private `application.log` captures the new process output. Backup and source
files remain retained. Helper cleanup is handled by the application coordinator
when the migration batch finishes. A helper cleanup failure does not roll routing
back to Chroma.

## Resume and forward repair

Re-run the **same command with the same state directory** after interruption.
The journal binds the host, old supervisor identity, data paths, command and
helper settings. Completed shutdown and backup steps are reused. A running new
application is observed instead of launched again. A readiness timeout leaves
it available for the authenticated administration and migration retry APIs.
Fix the reported issue and re-run the controller to observe readiness.

If the new process has exited, inspect the private application log first.
Re-run the same command with `--restart-new` to explicitly restart the selected
new application. The old source is never automatically restarted, and the
pre-upgrade metadata backup is never restored automatically. Once new writes
have happened, recovery must continue forward. Keep external old-version
restarts disabled and hand the recorded new supervisor PID back to the service
manager only after readiness succeeds.

If the controller is killed while workers are suspended, resume using the same
state directory. It recovers the dedicated session and its shutdown journal.
Do not delete the journal or substitute a new state directory. Preserve failed
backup attempts for diagnosis. A different deployment topology needs its own
shutdown proof rather than bypassing the maintenance receipt checks.

Recent MCP stdio tools can leave subprocesses in separate sessions for several
minutes. The controller refuses these escaped sessions before stopping the app.
Stop using stdio tools and let their cached subprocesses expire before preparing
the upgrade, or stop the complete deployment through its deployment manager.
