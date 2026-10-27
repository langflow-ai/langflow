"""Check every saved flow of a source database against this release, before upgrading to it.

The shared upgrade rule (``lfx.upgrade.checker``) gives each node a status. Every outdated node then
gets a dry run of the editor's Update: the node is rebuilt from this release's code and its saved
values are carried over, as the ``/api/v1/custom_component`` route does, and nothing is saved. The
rule then compares the rebuilt node with the saved one, so a node is breaking only when an update
would actually lose a connection, a value, a field, or an output.

A dry run executes component code. While it runs, every network call in the process is refused (an
audit hook sees each socket connect and name lookup), it has a time limit, and anything it raises
is recorded on that node instead of stopping the check.

Each node also gets ``runs``: what the upgraded server executes for it under the target's settings
(its saved code, the server's code, or nothing), decided by the runtime's own build checks.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import sys
import textwrap
import threading
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template, update_rebuilt_node
from lfx.extension.migration.loader import load_migration_table
from lfx.interface.components import ComponentCache
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.upgrade.checker import breaking_reasons, build_registry_lookup, classify_node, iter_flow_nodes
from lfx.utils.flow_code import normalize_code_for_import
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    is_code_execution_component,
    prepare_flow_build_for_user_from_cache,
)
from lfx.utils.python_repl_security import code_execution_refusal

from langflow.initial_setup.constants import STARTER_FOLDER_NAME

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from lfx.extension.migration.schema import MigrationTable
    from lfx.upgrade.checker import NodeStatus

    from langflow.upgrade_check.reader import SourceDatabase, SourceFlow

DRY_RUN_SECONDS = 30.0

# A node in one of these states makes its flow fail.
_FAILING = frozenset({"outdated_breaking", "retired", "blocked"})
# A node with one of these reasons, and nothing failing, makes its flow warn.
_WARNING = frozenset({"customized", "could_not_verify", "build_failed"})

# Audit events of an outbound connection or a name lookup; the same names from Python 3.10 to 3.14.
_NETWORK_EVENTS = frozenset(
    {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto"}
)
# ponytail: one process-wide gate. The command runs the check alone in its process, and a dry run's
# calls can come from any thread (asyncio resolves names in its executor). If the check ever runs
# inside a server (the admin page), this would also refuse the server's own calls during a dry run;
# gate per context then. The network is refused while any thread here is running a dry run, so a
# dry run past its time limit stays refused until it ends.
_dry_run_threads: set[int] = set()
_refused_calls: list[str] = []


@dataclass(frozen=True)
class TargetSettings:
    """The upgraded server's settings that decide what a saved node runs.

    The command fills them from its flags, and the report records them. Each field is the server
    setting of the same name (``LANGFLOW_<NAME>``), so the runtime's checks read them as they are.
    """

    allow_custom_components: bool = True
    substitute_outdated_component_code: bool = True
    block_code_interpreter_components: bool = False
    custom_component_admin_only: bool = False
    allow_components_paths_override: bool = True
    components_path: tuple[str, ...] = ()

    @property
    def loaded_components_path(self) -> list[str]:
        """The custom component folders the server loads: none when custom code is blocked without an override."""
        if self.allow_custom_components or self.allow_components_paths_override:
            return list(self.components_path)
        return []


@dataclass(frozen=True)
class Target:
    """This release as the upgraded server runs it: its components, its settings, and the source's catalog rules."""

    # Every type a saved node can carry, for the upgrade rule.
    lookup: Mapping[str, dict]
    # The same components, for the runtime's own build checks.
    components: ComponentCache
    settings: TargetSettings
    catalog_policy: CatalogPolicySnapshot

    @classmethod
    def from_registry(
        cls,
        all_types: Mapping[str, Any],
        settings: TargetSettings | None = None,
        catalog_policy: CatalogPolicySnapshot | None = None,
    ) -> Target:
        """``all_types`` from ``load_upgrade_registry(settings.loaded_components_path)``.

        ``catalog_policy`` is ``source.catalog_policy().snapshot``; its ``data_error`` belongs in
        the report's errors, since the upgraded server would not start on it.
        """
        components = ComponentCache()
        components.all_types_dict, components.all_types_ready = dict(all_types), True
        return cls(
            target_lookup(all_types),
            components,
            settings or TargetSettings(),
            catalog_policy or CatalogPolicySnapshot(),
        )


@dataclass
class NodeResult:
    """A node that needs a look: anything but ``ok``, or a node the upgraded server refuses."""

    id: str
    group_path: list[str]
    type: str
    display_name: str
    status: str
    # saved_code, server_code, or refused.
    runs: str | None = None
    reasons: list[dict[str, str | None]] = field(default_factory=list)
    # Set for outdated nodes: ``result`` is keeps, loses, could_not_verify, or build_failed.
    dry_run: dict[str, Any] | None = None
    replacement: list[str] | None = None
    bundle: str | None = None


@dataclass
class FlowResult:
    """One flow, saved component, or running flow version, and its nodes that need a look."""

    id: str
    kind: str
    name: str | None
    owner: dict[str, str | None] | None
    project: dict[str, str] | None
    last_edited_at: str | None
    status: str = "ok"
    nodes: list[NodeResult] = field(default_factory=list)
    ok_nodes: int = 0
    flow_id: str | None = None
    version_number: int | None = None
    used_by: dict[str, list[str]] | None = None
    # Set when the saved data could not be read; the flow then has no nodes.
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_source(source: SourceDatabase, target: Target) -> Iterator[FlowResult]:
    """Yield a result for every flow, saved component, and running flow version of ``source``.

    Iterate inside ``open_source``: the rows stream from its connection. Starter projects are
    skipped, since startup recreates them.
    """
    users = {user.id: user for user in source.users}
    projects = {project.id: {"id": project.id, "name": project.name} for project in source.projects}
    starter_projects = {
        project.id for project in source.projects if project.name == STARTER_FOLDER_NAME and project.user_id is None
    }

    def result(row, kind: str, name: str | None, folder_id: str | None, last_edited_at: str | None, **extra):
        user = users.get(row.user_id)
        owner = {"id": row.user_id, "username": user.username if user else None} if row.user_id else None
        flow = FlowResult(row.id, kind, name, owner, projects.get(folder_id), last_edited_at, **extra)
        if row.data_error:
            flow.status, flow.error = "warn", row.data_error
            return flow
        is_superuser = bool(user and user.is_superuser)
        flow.nodes, flow.ok_nodes = check_nodes(row.data or {}, target, user_id=row.user_id, is_superuser=is_superuser)
        flow.status = flow_status(flow.nodes)
        return flow

    # Flow id to (name, project id), for the versions; starter flows map to None.
    flows: dict[str, tuple[str, str | None] | None] = {}
    for row in source.flows():
        if row.folder_id in starter_projects:
            flows[row.id] = None
            continue
        flows[row.id] = (row.name, row.folder_id)
        yield result(row, "component" if _is_component(row) else "flow", row.name, row.folder_id, row.updated_at)
    for row in source.flow_versions():
        if row.flow_id in flows and flows[row.flow_id] is None:
            continue
        name, folder_id = flows.get(row.flow_id) or (None, None)
        used_by = {"deployments": list(row.attached_to_deployments), "triggers": list(row.pinned_by_triggers)}
        yield result(
            row,
            "flow_version",
            name,
            folder_id,
            row.created_at,
            flow_id=row.flow_id,
            version_number=row.version_number,
            used_by=used_by,
        )


def target_lookup(all_types: Mapping[str, Any]) -> dict[str, dict]:
    """Index this release's components by every type a saved node can carry.

    On top of the aliases ``build_registry_lookup`` keeps, a legacy type that the extension migration
    table rewrites when a flow loads finds the component it is rewritten to, when that is installed.
    """
    lookup = build_registry_lookup(all_types)
    for entry in _migration_table().entries:
        if entry.target in lookup:
            lookup.setdefault(entry.legacy_value, lookup[entry.target])
    return lookup


def check_nodes(
    flow_data: dict, target: Target, *, user_id: str | None = None, is_superuser: bool = False
) -> tuple[list[NodeResult], int]:
    """Check every node of ``flow_data``, groups included, against ``target``.

    Returns the nodes that need a look (not ok, or refused) and the number of the others. The
    owner, ``user_id``, owns the dry runs, and ``is_superuser`` decides admin-only rules.
    """
    _install_network_guard()
    flow_data = normalize_code_for_import(flow_data)
    nodes: list[NodeResult] = []
    ok_nodes = 0
    for node, connected_fields, group_path in iter_flow_nodes(flow_data.get("nodes", []), flow_data.get("edges")):
        status = classify_node(node, target.lookup, connected_fields)
        if status is None:
            continue
        runs, refusal = _runs(node, target, is_superuser=is_superuser)
        if status.status == "ok" and refusal is None:
            ok_nodes += 1
            continue
        result = _node_result(node, status, group_path, connected_fields, target.lookup, user_id)
        result.runs = runs
        result.reasons += [refusal] if refusal else []
        if _loses_edits(result):
            result.reasons = [_reason("customized", None, _EDITS_DO_NOT_RUN)]
        nodes.append(result)
    return nodes, ok_nodes


def flow_status(nodes: list[NodeResult]) -> str:
    if any(node.status in _FAILING or node.runs == "refused" or _loses_edits(node) for node in nodes):
        return "fail"
    if any(reason["code"] in _WARNING for node in nodes for reason in node.reasons):
        return "warn"
    return "ok"


def _node_result(
    node: dict,
    status: NodeStatus,
    group_path: tuple[str, ...],
    connected_fields: set[str] | None,
    lookup: Mapping[str, dict],
    user_id: str | None,
) -> NodeResult:
    node_info = node.get("data", {}).get("node", {})
    entry = lookup.get(status.component_type, {})
    result = NodeResult(
        id=status.node_id,
        group_path=list(group_path),
        type=status.component_type,
        display_name=status.display_name,
        status=status.status,
        bundle=entry.get("bundle"),
    )
    if status.status == "blocked":
        result.bundle = _missing_bundle(status.component_type, node_info)
        result.reasons = [
            _reason("bundle_not_installed", None, f"the {result.bundle} bundle is not installed")
            if result.bundle
            else _reason("custom_type_missing", None, f"{status.component_type} is not a component of this release")
        ]
    elif status.status == "retired":
        result.replacement = status.replacement or None
        result.reasons = [_reason("retired", None, f"retired in {status.retired_in}")]
    elif status.status == "customized":
        result.reasons = [_reason("customized", None, "the saved code was edited")]
    elif status.status != "ok":
        rebuilt, failure = _dry_run(entry, node_info, user_id)
        if failure is not None:
            # The rule's own verdict stands, and the node says why the dry run could not decide.
            reasons = [asdict(reason) for reason in breaking_reasons(entry, node_info, connected_fields)]
            result.reasons = [*reasons, failure]
            result.dry_run = {"result": failure["code"]}
        else:
            reasons = [asdict(reason) for reason in breaking_reasons(rebuilt, node_info, connected_fields)]
            result.status = "outdated_breaking" if reasons else "outdated_safe"
            result.reasons = reasons
            result.dry_run = {"result": "loses" if reasons else "keeps"}
    return result


_EDITS_DO_NOT_RUN = "the saved edits will not run: this server runs its own code for this component"


def _loses_edits(node: NodeResult) -> bool:
    """A customized node the upgraded server runs with its own code: the flow will not behave as saved."""
    return node.status == "customized" and node.runs == "server_code"


def _runs(node: dict, target: Target, *, is_superuser: bool) -> tuple[str, dict | None]:
    """What the upgraded server executes for ``node``, and the ``refused`` reason when it executes nothing.

    The runtime's own checks decide, as a build for the owner runs them: the build policy, then
    the rule the code-execution gate applies when such a component runs.
    """
    data = node.get("data", {})
    try:
        sanitized = prepare_flow_build_for_user_from_cache(
            {"nodes": [node], "edges": []},
            is_superuser=is_superuser,
            settings=target.settings,
            cache=target.components,
            catalog_policy_snapshot=target.catalog_policy,
        )
    except CustomComponentValidationError as exc:
        return "refused", _reason("refused", None, str(exc))
    if is_code_execution_component(data.get("type"), data.get("node", {}).get("display_name")) and (
        refusal := code_execution_refusal(target.settings, is_superuser=is_superuser)
    ):
        return "refused", _reason("refused", None, refusal)
    # Stored code runs only when custom code is allowed and admin-only rules did not swap in the
    # server's copy (resolve_trusted_code_for_build); restricted builds run the server's code.
    if sanitized is None and target.settings.allow_custom_components:
        return "saved_code", None
    return "server_code", None


def _dry_run(entry: Mapping[str, Any], saved_node: dict, user_id: str | None) -> tuple[dict | None, dict | None]:
    """Return the node the editor's Update makes from ``saved_node`` with ``entry``'s code, or why there is none.

    The update runs in its own thread and event loop, so a time limit can stop waiting for it. A
    thread past the limit is left to end on its own; it is a daemon, so it never holds the process.
    """
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["node"] = asyncio.run(_update(entry, copy.deepcopy(saved_node), user_id))
        except BaseException as exc:  # noqa: BLE001 - whatever the component raises is reported on the node
            outcome["error"] = exc

    _refused_calls.clear()
    thread = threading.Thread(target=run, name="upgrade-check-dry-run", daemon=True)
    thread.start()
    thread.join(DRY_RUN_SECONDS)
    if _refused_calls:
        return None, _reason("could_not_verify", None, f"the update makes a network call: {_refused_calls[0]}")
    if thread.is_alive():
        return None, _reason("could_not_verify", None, f"the update did not finish in {DRY_RUN_SECONDS:g} seconds")
    error = outcome.get("error")
    if isinstance(error, _BuildError):
        return None, _reason("build_failed", None, f"this release's code does not build: {_short(error)}")
    if error is not None:
        return None, _reason("could_not_verify", None, f"the update failed: {_short(error)}")
    return outcome["node"], None


class _BuildError(Exception):
    """This release's code for the node does not build."""


async def _update(entry: Mapping[str, Any], saved_node: dict, user_id: str | None) -> dict:
    """What the editor's Update runs on the server, without the route's policy checks."""
    # The event loop already exists, so its own sockets (a local pair on Windows) are not refused.
    _dry_run_threads.add(threading.get_ident())
    try:
        metadata = saved_node.get("metadata")
        class_name = metadata.get("component_class_name") if isinstance(metadata, dict) else None
        try:
            built, instance = build_custom_component_template(
                Component(_code=entry["template"]["code"]["value"]),
                user_id=user_id,
                class_name=class_name if isinstance(class_name, str) and class_name else None,
            )
        except Exception as exc:
            raise _BuildError from exc
        return await update_rebuilt_node(instance, built, saved_node)
    finally:
        _dry_run_threads.discard(threading.get_ident())


def _refuse_network(event: str, args: tuple[Any, ...]) -> None:
    if _dry_run_threads and event in _NETWORK_EVENTS:
        # connect and sendto get (socket, address); the lookups get the host first.
        target = args[1] if event in {"socket.connect", "socket.sendto"} else args[0]
        _refused_calls.append(f"{event} {target!r}")
        msg = f"the upgrade check refuses network calls ({event} {target!r})"
        raise ConnectionRefusedError(msg)


@functools.cache
def _install_network_guard() -> None:
    sys.addaudithook(_refuse_network)


def _missing_bundle(component_type: str, node_info: Mapping[str, Any]) -> str | None:
    """Name the bundle that ships a type this release lacks, or ``None`` for a custom type.

    The saved type, the address discovery stamped on the node, or its saved import path can name
    it: an ``ext:<bundle>:<Class>@<slot>`` address directly, a legacy name through the extension
    migration table.
    """
    table = _migration_table()
    metadata = node_info.get("metadata")
    module = metadata.get("module") if isinstance(metadata, dict) else None
    for value in (component_type, node_info.get("namespaced_id"), module):
        if not isinstance(value, str):
            continue
        entry = table.lookup_bare(value) or table.lookup_import_path(value) or table.lookup_legacy_slot(value)
        address = entry.target if entry else value
        if address.startswith("ext:"):
            return address.split(":")[1]
    return None


def _migration_table() -> MigrationTable:
    table, error = load_migration_table()  # cached for the process
    if table is None:
        msg = f"cannot read the extension migration table: {error.message if error else 'unknown error'}"
        raise RuntimeError(msg)
    return table


def _is_component(flow: SourceFlow) -> bool:
    """Read ``is_component`` the way the server does when the row left it unset."""
    if flow.is_component is not None:
        return flow.is_component
    data = flow.data or {}
    inferred = data.get("is_component")
    return bool(inferred) if inferred is not None else len(data.get("nodes", [])) == 1


def _reason(code: str, field_name: str | None, message: str) -> dict[str, str | None]:
    return {"code": code, "field": field_name, "message": message}


def _short(error: BaseException) -> str:
    """The innermost cause in one line, short enough for a report."""
    while error.__cause__ is not None:
        error = error.__cause__
    return textwrap.shorten(f"{type(error).__name__}: {error}", width=300, placeholder="...")
