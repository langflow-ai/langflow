# Project type plugins

Project types declare the form used to configure a project. The five built-in types and
installed plugins inherit `ProjectTypeDefinition`. The project API serves their forms and
accepts their registered names without a database migration.

This delivery supports declarations, discovery, slot contracts, capabilities, project references,
and transactional save hooks with pure graph composition. Tool Pack, Skill Pack, Eval Suite and
custom types use these hooks. Agent Harness retains its existing save/composition path until
the next two migration slices. Archive and starter hooks are separate follow-up work.
Custom React pages and widgets are not part of the Python plugin contract.

## Declare a type

```python
from lfx.inputs.inputs import StrInput
from lfx.projects import ProjectTypeDefinition, ProjectTypeField


class SupportDeskType(ProjectTypeDefinition):
    name = "support-desk"
    display_name = "Support desk"
    icon = "Headset"
    description = "Triage incoming support requests."
    fields = (
        ProjectTypeField(
            name="team",
            section="Routing",
            input=StrInput(name="team", display_name="Team"),
        ),
    )
```

Classes are stateless and take no constructor arguments. The registry caches one instance
per class. Do not keep project, request, user, or database state on the instance or class.
Field names must be unique. A flow-bound field uses the exact registered `SlotDefinition`
returned by `get_slot`; a custom slot must be registered before declaring its fields.

Publish the class through package metadata. The entry-point key must equal its `name`:

```toml
[project.entry-points."lfx.project_type.adapters"]
support-desk = "acme_langflow.types:SupportDeskType"
```

Entry-point classes do not need a registration decorator. For an in-process declaration,
use `register_project_type(SupportDeskType)` or `@register_project_type`.
This replaces the pre-release `ProjectType(...)` instance registration API.

## Declare a flow-bound field

A field selects its flow contract directly. Its name does not need to match a built-in field:

```python
from lfx.projects import get_slot

briefing = ProjectTypeField(
    name="briefing",
    input=StrInput(name="briefing", display_name="Briefing"),
    slot_definition=get_slot("Instructions"),
    supports_flow_binding=True,
)
```

The project's baseline, output listing, and draft-validation routes resolve this declaration
after checking project ownership and permissions. They retain the existing flow permission and
dependency checks. Output discovery inspects the graph without executing its saved code.

For a new contract, subclass `SlotDefinition` and register its instance before declaring the
project type. `binding_contract()` lazily returns the Pydantic binding model, output discovery
function, and binding validator. Discovery takes graph data and returns output choices. The
validator takes graph data and a binding; it must check both the selected output and the reviewed
revision. `validate_binding()` checks the model type before calling that validator. The existing
Tool contract instead validates the complete flow definition, including its identity.

An optional `build_baseline(initial_value, *, initial_config)` returns a normal flow creation
payload. Declare a unique `default_flow_ref` for a slot that provides it. References resolve only
registered factories; a request cannot supply an import path. The API labels the returned graph
with the selected slot and project field. Set `validation_hint` and `baseline_error_hint` to safe
user-facing guidance; parser exception details are not exposed.

The form publishes a slot's `binding_kind`, `binding_label`, `validation_hint`, and
`initial_config_fields`. Timeout and compaction threshold defaults come from the binding model.
The current flow picker vocabulary is `instructions`, `hook`, `context`, `compaction`, and
`permission`. Python plugins reuse those controls; they do not introduce React controls. A
custom field can therefore reuse the context picker and its declared timeout without changing
the page. The existing Scorer contract also owns its validator and output discovery, while the
Eval Suite keeps its dedicated page.

Declaring a slot does not install an Agent runtime handler or implement a project save hook. Built-in
harness composition, snapshots, and archive remapping now read Agent input and origin metadata
from their slots, with the same saved keys. A custom type must prepare and compose its flow
bindings through the hooks below. The default hooks only apply declared literal field targets.
Successful output discovery alone does not make a custom binding executable.

## Capabilities and project references

Types declare archive policy and the existing UI panels they need:

```python
class LibraryType(ProjectTypeDefinition):
    name = "document-library"
    display_name = "Document library"
    icon = "BookOpen"
    allows_empty_project = True
    exportable = True
    panels = ("reports",)
    fields = ()
```

`allows_empty_project` defaults to `False`. It permits exporting a project without flows and
importing its empty project ZIP, including the composition root. Creation of an empty project
remains allowed for all types. `exportable` defaults to `True`; setting it to `False` blocks
project archive export and import, including dependencies in a composition. Eval Suite declares
`False` until its retained candidates and scorers can be archived. Archive policy is checked on
the server. It does not replace authorization.

The current panel keys are `agent`, `reports`, `local-tool-review`, `harness-return`, and
`evaluation`. They reuse the existing controls and layout. `evaluation` selects the dedicated
Eval Suite page; the others select sections of the standard form. A form tab is available when
the declaration supplies fields or panels. Selecting a panel does not install its backend
behavior: the Agent and evaluation panels still need the corresponding save/runtime support.
Plugins cannot add arbitrary React panels.

Set `ProjectTypeField.references` to the target project type. Registration validates the
declaration without resolving that target during plugin import:

```python
libraries = ProjectTypeField(
    name="libraries",
    input=StrInput(name="libraries", display_name="Libraries", list=True, value=[]),
    references="document-library",
)
```

A saved reference has `project_id`, `expected_type`, and a 64-character revision digest. An
omitted `expected_type` takes the field's declared target. List inputs accept lists of unique
project references; other inputs accept one reference. The save path validates the shape,
authorizes project read access, and compares the actual stored type with the declaration.
A forged `expected_type` cannot make a different type compatible. Inaccessible project IDs
remain 404s. A rejected save leaves the previous configuration intact.

The generic check validates reference identity, type and access. It does not establish that a
plugin's revision is current or authorize executing its flows. Built-in Tool Pack and Skill Pack
validators retain their revision, dependency and execution checks. Custom revision handling and
composition belong in the save hooks below. Reference remapping still needs the archive slice. The existing reference
pickers read the target from the field; their review UI currently supports Tool Packs and Skill
Packs. Other targets can use the configuration API, with no custom reviewer implied.

## Prepare and compose a save

Lifecycle records and errors are public in `lfx.projects.lifecycle`. Override an asynchronous
`save_config` to validate or normalize config. It returns `PreparedSave`; it never commits.
The default synchronous `compose` applies declared `writes_to` fields while preserving inputs
edited independently on the canvas. This example retains that behavior:

```python
from lfx.projects.lifecycle import PreparedSave, ProjectConfigError, ProjectSaveContext, SaveRequest


class ValidatedSupportDeskType(SupportDeskType):
    name = "validated-support-desk"

    async def save_config(self, request: SaveRequest, ctx: ProjectSaveContext) -> PreparedSave:
        prepared = await super().save_config(request, ctx)
        if prepared.config is None:
            return prepared
        config = dict(prepared.config)
        if "team" in config:
            if not isinstance(config["team"], str) or not config["team"].strip():
                raise ProjectConfigError("Choose a support team.", field_path="team")
            config["team"] = config["team"].strip()
        return PreparedSave(config, prepared.target_flow_ids)
```

`SaveRequest` supplies detached project and local-flow views, proposed and previous config,
and an operation of `create`, `replace`, or `clear`. The default hook selects local targets
only when the type declares at least one `writes_to` field. A custom hook can select a subset
with `PreparedSave.target_flow_ids`. Hooks also run for types with no form fields.

For specialized composition, override
`compose(prepared: PreparedSave, ctx: CompositionContext) -> tuple[FlowChange, ...]`.
Its context contains only authorized, unlocked target views and prior server-owned applied
values. Return at most one `FlowChange` for each supplied target, with its original token,
new JSON graph data and next applied values. It must perform no I/O. `PreparedSave.state` can
carry temporary preparation records; it is neither persisted nor returned by the API. Do not
store a context, session, callable or open resource there or on the cached type instance.

### Authorized source access

The preparation context exposes four operations. It does not expose an ORM session:

| Method | Guarantee |
|---|---|
| `read_project(project_id, expected_type=...)` | Authorizes READ and checks the actual stored type. For the project being saved, returns its pending config. |
| `read_flow(FlowSelector(id=...), access="read" or "execute")` | Authorizes READ and optionally EXECUTE. Returns a detached graph and opaque read token. Legacy names must be unambiguous within the caller's account. |
| `pin_sources((token, ...), label=...)` | Accepts only this context's EXECUTE-authorized tokens. Preserves their exact graph data in the current transaction and returns server-owned version references. |
| `read_saved_source(SourceVersionReference(...))` | Rechecks current READ/EXECUTE access and verifies version ownership, flow identity and executable revision. Missing versions fail; there is no fallback to the current graph. |

The type must validate its selected output, reviewed revisions and complete dependency set
before pinning. A caller-supplied version ID is never proof of review. Historical snapshot reuse
requires a trusted previous binding; Eval Suite permits it only when the whole scorer binding
is unchanged. Updating a scorer pins current reviewed definitions. Pack resolvers share these
context operations with the ordinary manifest routes and never execute saved components.

Views are frozen records containing copied dictionaries. Mutating a nested dictionary cannot
mutate stored state or alter what a read token represents. Resource changes detected during
preparation reject the save with 409. The host tracks layout and metadata as well as executable
revisions, checks target permissions, and limits one attempt to 500 flows and 500 projects.

### Persistence and failures

The host validates config, references, target IDs, read tokens and proposed changes. It retains
previous applied values outside plugin config; `_applied` is host-owned. It writes normalized
config, accepted graph changes and required source versions in one database transaction.
Required source-version failures abort the save. Restore points for changed target graphs
remain best effort. Locked targets are counted and excluded from composition.

An update that omits `project_config` invokes no hooks. `{}` is a replacement. `null` is a clear
and must remain `None` in the prepared result. The previous config is available for removing
owned wiring. Clearing does not promise to restore every previous literal input. Changing a
configured project's type requires clearing its config first; no implicit migration occurs.

Raise `ProjectConfigError` with safe, actionable text for invalid config (422). Unavailable
sources use `ProjectResourceUnavailableError` (404); conflicts use `ProjectSaveConflictError`
(409). Unexpected exceptions receive a generic 500 response. The host rolls back database
writes on failure, including any new versions created earlier in that save.

Two limits remain: file-backed graphs are still synchronized before the database commit, so
the database and filesystem are not atomic together. Deployed PostgreSQL concurrency acceptance
is also pending. Installed types execute trusted Python. Hooks must not run flows, call
providers, write files or perform external effects; the host cannot roll back arbitrary plugin I/O.

Standalone LFX can use these hooks with an in-memory or other host-provided context. Database
preparation has no implicit Langflow dependency. Runtime execution still consumes already
composed graph inputs, not project config or a new project-type runtime registry.

## Discovery and precedence

The project registry reuses `AdapterRegistry` discovery and configuration parsing. It adds
declaration validation for every source. Use the project-specific registration functions;
the module owns its stateless declaration registry.

1. Built-ins and host registrations load at import/startup. Re-registering the identical
   class is idempotent. Replacing one requires `override=True` before the first lookup.
2. The first `get_project_type`, `registered_project_types`, or `all_project_types` call
   discovers installed entry points. They cannot replace an already registered key. As with
   the service adapter registry, the first discovered entry point for an unclaimed key wins.
   Use distinct names or explicit configuration to resolve package collisions.
3. Operator configuration runs last and can replace an existing key:

   ```toml
   [project_type.adapters]
   support-desk = "acme_langflow.types:SupportDeskType"
   ```

Configuration uses the settings service's config directory, falling back to the current
directory. `lfx.toml` takes precedence over `pyproject.toml`, where the section is
`[tool.lfx.project_type.adapters]`. Later host registrations cannot replace a resolved type.
Installing/removing packages or changing configuration requires a process restart.

Declarations may import `get_slot`. They must not look up project types while their plugin
module is being imported: discovery rejects that recursive lookup rather than deadlocking.
Unimportable or invalid discovered declarations are logged and skipped, following the shared
adapter discovery policy. Explicit registrations raise their validation error to the caller.

Packages and configured imports execute trusted Python code with the server's privileges.
Installation/configuration belongs to the operator; this mechanism does not sandbox plugins
or accept Python package names from a project's saved configuration.

## Missing plugins

An unavailable type raises an explicit lookup error. It never resolves to a different type.
Existing database project reads and unrelated metadata edits retain the stored type and config.
Explicit config saves or clears return 422. Export refuses an unavailable type because its
archive policy cannot be checked. Missing-plugin archive import and execution still need the
later lifecycle work; the legacy import fallback is not changed here.

## Verification

`tests/data/project_type_plugin` is a buildable third-party package. Discovery tests use its
actual entry-point metadata and import its Python module without mocking discovery. They
cover the generated form, write-through, configuration precedence, collisions, malformed
entries, concurrent lookup, recursive imports, and both fresh Agent/project import orders.
Backend tests cover the custom form/config API and preserving a project when its type is
unavailable. They also exercise a custom field and slot through baseline creation, saved-output
discovery and draft validation. Slot tests use real built-in baseline graphs to verify output
selection, stale-revision rejection and model defaults. Frontend tests cover the same declared
defaults and a field whose name is not built in. The five built-in form payloads remain unchanged
by the class conversion; slot behavior adds binding metadata to their existing flow contracts.
Capability tests cover installed-plugin metadata, custom reference targets, empty-project ZIP
round trips, blocked archive import/export, blocked composition dependencies, foreign project
privacy and rollback on a reference mismatch. UI tests cover panel selection for a renamed type
and retaining the selected form tab while metadata loads.

Lifecycle tests use the real entry-point plugin through the configuration API to normalize,
authorize and snapshot a source, compose local targets, and preserve independent canvas edits.
They cover untrusted version IDs and tokens, READ versus EXECUTE, changed source/target state,
foreign and duplicate targets, locked targets, fields-empty types, missing plugins, clear versus
empty versus omitted config, and rollback after a source version or a target graph is staged.
Pack/eval tests retain transitive review and workflow execution coverage. These checks use
SQLite and provider replacements; they do not establish live-provider or deployed-topology acceptance.
