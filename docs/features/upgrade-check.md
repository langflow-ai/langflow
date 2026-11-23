# Upgrade check

Unpublished notes for `langflow upgrade-check`, the **Settings > Upgrade reports** page, and the repair API. The published guide is `docs/docs/Deployment/upgrade-check.mdx`.

## Isolation

The command reads no server setting from its environment or `.env` file. Its child keeps only interpreter and operating system essentials. Provider credential variables are removed. Home, configuration, cache, and working directory are temporary. Explicit source, output, and custom component paths are resolved before this isolation. Supported SDK offline settings also prevent automatic model metadata downloads.

Selected PostgreSQL sources still use libpq's normal connection precedence, including explicit URL values, `PG*` variables, service definitions, default password and TLS files, and Kerberos inputs. These private source inputs travel over stdin and apply only while opening and reading the source connections, using the caller's original home and working directory. They are removed before component discovery or dry runs. The existing connection stays open for later read-only pages. Provider credentials are never added to the child's environment, and source inputs are not copied into reports or child process arguments.

For `sslrootcert=system`, the source-only context also preserves `SSL_CERT_FILE` and `SSL_CERT_DIR`, including relative paths resolved from the caller's working directory.

The guard refuses these Python network audit events: `socket.connect`, `socket.getaddrinfo`, `socket.gethostbyname`, `socket.gethostbyaddr`, `socket.getnameinfo`, `socket.sendto`, and `socket.sendmsg`. Some Python networking remains allowed, including `socket.bind`.

The guard permits only two local metadata probes used by installed dependencies: the canonical system Git executable with exactly `version`, and the canonical system `file` executable with exactly `-b` and the current interpreter path. Executable identity, arguments, target, sanitized environment, and system PATH are checked before launch. Alternate executables, arguments, and environments are refused. Refusals remain recorded even if component code catches the exception.

The Python audit guard is not an operating system sandbox. It cannot contain native extension transports or arbitrary native code. Run the check with trusted installed components and custom folders. Source database connections open before component discovery and remain read-only. A discovery worker that exceeds its time limit stays guarded until it ends. Unrelated component import or template errors keep the shared loader's existing skip behavior. This check does not turn those skips into complete discovery evidence.

During discovery, a refused operation or a wait over the discovery timeout stops the check with exit 2, so the command does not publish a report against an incomplete registry. During a node's dry run, a refused or incomplete update records `could_not_verify` as its dry-run result and reason, and the check continues. That result does not replace the node's compatibility status, which can remain `outdated_safe` or `outdated_breaking`.

Update replays saved, nonempty refresh selectors that the current component still declares, including selectors on components other than Run Flow or MCP. Those hooks can use their configured services and add latency in the editor. The isolated checker refuses external discovery and records incomplete refresh warnings.

PostgreSQL reads use read-only transactions. Both the editor database and an optional Serving database are read before any component dry run begins. Read transactions end before component checks. A scan across multiple short reads is not one database snapshot.

The command replaces a report file atomically rather than truncating an inode through a hard link.

## Report document

`--json` prints one JSON object per line. Each flow is `{"event": "flow", "flow": {...}}` as soon as it is checked. The last line of a finished check is `{"event": "report", "report": {...}}`. If the check cannot finish, the last line is `{"event": "error", "code": "...", "message": "..."}`.

`--output` writes one JSON document with these keys:

- `format_version`: `1`.
- `generated_at`: when the check ran, in UTC.
- `source`: dialect, credential-free identity, Alembic revision, and how many flows, saved components, and running flow versions were read.
- `target`: Langflow and LFX versions, component-index hash, installed bundles, and custom component folders with their component counts.
- `settings`: every setting the check used, and the catalog rules it applied.
- `inputs`: the resolved output path, or `null`, and whether JSON events were selected.
- `network_policy`: component callbacks cannot use Python network audit events. Only allowlisted local system metadata probes may launch a process. Explicit source database connections are read-only. This guard is not an operating system sandbox.
- `summary`: flow counts by status, and node counts by status.
- `flows`: every checked flow, saved component, and running flow version, including healthy rows. Each row has its owner, project, last edit, separate Editor and Serving usage, and nodes that need review. Each node lists `status`, `runs`, `reasons`, and `dry_run` (`keeps`, `loses`, `could_not_verify`, or `build_failed`).
- `errors`: saved rows that could not be read, and catalog rules that could not be read. Those errors stop the upgraded server from starting.

The source identity contains a `kind`, a structured `locator`, and a `sha256` fingerprint of that locator. SQLite uses the canonical database file path, so symlinks to the same path have the same identity. PostgreSQL uses the connected host, port, database, and a fingerprint of the ordered schema search path. Schema names and arbitrary connection options are not copied into the report. Usernames, passwords, and URL query parameters are excluded. Changing only credentials does not change the identity when the endpoint and selected schemas stay the same. The identity's shape and fingerprint are validated together. This identifies the selected locator. It does not authenticate an installation or prove that its data stayed unchanged. The report binds each available usage source to that credential-free identity and never contains its connection URL.

## Flow usage accounting

Usage comes from the existing job table. Only workflow jobs with execution evidence count as runs. The supported execution states are `in_progress`, `completed`, `failed`, `timed_out`, and `suspended`. A suspended graph already executed before it paused for human input. Errors count failed and timed-out jobs. Queued jobs do not count. Canceled jobs cannot establish whether execution started, so they are excluded and flagged. Ingestion, evaluation, and unclassified job types are excluded.

The last run uses the newest creation time among jobs with execution evidence. This timestamp marks job creation because older schemas do not retain a separate execution-start timestamp. Stored timestamp components are validated before UTC normalization. SQLite and PostgreSQL timestamps retain microsecond precision. Retained coverage shows the oldest and newest workflow job creation times observed, including queued and canceled records.

The report keeps `coverage.complete` false and leaves the retention policy unknown because it does not load the source server's settings. Missing tables, missing required columns, and unavailable databases produce explicit unknown values and limitation codes. They do not become zero counts or compatibility failures.

The Serving adapter requires the preserved Editor flow ID in `job.flow_id`. It needs no new route on the older Serving release. A missing Serving configuration or missing preserved Editor ID is visible in the report.

## Repair API

The settings page calls this API. An active superuser previews selected stored flows and applies verified safe updates during database maintenance. The server selects replacement code from its installed component registry. The request cannot supply a graph, component source, or a repair result.

`POST /api/v1/upgrade-repairs/preview` takes `flow_ids` and an optional imported `report_id`. Each request selects between 1 and 100 distinct flow IDs. The response contains the installed Langflow and LFX versions, a target registry fingerprint, and one result for each selected flow. These installed versions describe the code used for repair, independently of an imported report's target metadata. Preview does not change any flow or create a recovery version.

A ready result includes `flow_id`, `version_token`, `data_sha256`, and the number of nodes that can update. Keep the exact values for the apply request. A legacy flow can have an explicit null token. The digest still identifies the stored graph that the administrator reviewed.

`POST /api/v1/upgrade-repairs/apply` takes the preview's `target_sha256` and a `flows` array. Each entry contains only `flow_id`, `version_token`, and `data_sha256`. An optional `report_id` links the server's results to imported report history. The server checks the source graph and registry again before applying any update.

Enable database maintenance, stop incoming traffic, and wait for admitted work to finish. The API refuses repair while the job table contains running jobs. The instance migration file pause always refuses repair, including superuser requests. Maintenance authentication requires an existing API key or local JWT.

Each flow uses its own transaction. A successful transaction creates an owner-visible retained recovery version, updates the graph, and records its report outcome together. A failed transaction rolls back the graph, version token, and recovery entry. Other selected flows still receive independent results. Recovery versions are protected from normal history pruning and deletion.

The caller's authorization permits the cross-user write. The stored owner's identity, project, workspace, and provider policy govern the component context. Repair does not read provider credentials or execute saved component code. Saved field values, global-variable references, and all nested edges must remain intact. Nodes marked `edited=true` stay unchanged.

| Status | Meaning |
|---|---|
| `ready` | Preview found safe updates for this flow. |
| `updated` | Apply committed the update and its retained recovery version. |
| `unchanged` | No eligible node needs an update. |
| `manual` | The server could not prove preservation or requires a separate repair procedure. |
| `conflict` | The reviewed source changed or the database was busy. Preview again. |
| `forbidden` | Authorization refused the selected write. |
| `not_found` | The selected flow no longer exists. |
| `failed` | The repair transaction did not commit. |

Manual cases include locked flows, file-backed flows, missing owners, malformed graphs, duplicate node IDs, and breaking or unavailable component contracts. File-backed flows require a separate update of their external source files. Dynamic fields whose update cannot be verified remain manual. Delegated model inputs and provider overrides are checked under the stored owner's policy. Unknown, malformed, connected, or global-variable provider selections return `provider_selection_unverifiable` and require manual review. No input is hydrated to resolve that uncertainty. The existing conservative static MCP classification still applies. A missing prerequisite or unavailable database is reported as a failure rather than an authorization denial.

After repair, graph replacements require the flow's current `If-Match` token. An older author session cannot overwrite the repaired graph by omitting the header. A missing token returns `428`. A stale token returns `409`. Reload the flow before saving again. Metadata-only changes retain their existing behavior.

Saved outcomes show updates, refusals, conflicts, and recovery identifiers independently of the immutable imported report.

## Account erasure

Account erasure deletes a report and its repair history when the report's creator or an owner is identified by the account's immutable ID. A matching owner name without a valid owner ID requires manual attribution review because names can be reused. The erase request remains **Erasing**, keeps the report and account, and stops automatic retries. Its error includes `report_owner_attribution_required`, `manual_review_required: true`, and the report ID. Earlier completed erase steps remain committed. Review the archive's owner attribution and resolve the ambiguity through the approved data-handling process before using the existing manual retry action. Retrying an unchanged archive does not bypass the review requirement.
