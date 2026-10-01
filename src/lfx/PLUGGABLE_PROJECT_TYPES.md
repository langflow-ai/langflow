# Project type plugins

Project types declare the form used to configure a project. The five built-in types and
installed plugins inherit `ProjectTypeDefinition`. The project API serves their forms and
accepts their registered names without a database migration.

This first slice supports declarations, discovery, and the existing field write-through.
Type-specific save, composition, archive and starter hooks are separate follow-up work.
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
Existing database project reads retain the stored type and config. That read guarantee does
not yet define missing-plugin archive import, execution or editing behavior; those remain
part of the later lifecycle work.

## Verification

`tests/data/project_type_plugin` is a buildable third-party package. Discovery tests use its
actual entry-point metadata and import its Python module without mocking discovery. They
cover the generated form, write-through, configuration precedence, collisions, malformed
entries, concurrent lookup, recursive imports, and both fresh Agent/project import orders.
Backend tests cover the custom form/config API and preserving a project when its type is
unavailable. The five built-in form payloads remain unchanged by the class conversion.
