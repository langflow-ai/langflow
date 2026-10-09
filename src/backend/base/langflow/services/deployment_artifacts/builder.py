"""Build a deterministic, secret-scrubbed package from one persisted project."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import stat
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypeVar

from lfx.base.knowledge_bases.backends import is_local_backend
from lfx.base.models.provider_registry import model_component_provider_id, resolve_provider_id
from lfx.helpers.base_model import coalesce_bool
from lfx.integrations.models import ConnectionRef
from sqlmodel import col, select

from langflow.services.auth.mcp_encryption import decrypt_mcp_config
from langflow.services.authorization import (
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ensure_flows_permission,
    ensure_knowledge_base_permission,
    ensure_project_permission,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow, FlowRead, FlowType
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.mcp_server.model import MCPServer
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.deps import get_variable_service
from langflow.utils.canonical_json import canonical_json_bytes
from langflow.utils.flow_secrets import strip_secret_field_values_in_place
from langflow.utils.mcp_config_secrets import (
    MCP_SECRET_CONFIG_MAPS,
    NON_SECRET_HEADERS,
    project_id_from_mcp_url,
    variable_name_for,
    variable_reference_name,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead

LFPKG_MEDIA_TYPE = "application/vnd.langflow.lfpkg+zip"

_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_ZIP_FILE_MODE = stat.S_IFREG | 0o644
_MAX_JSON_DEPTH = 128
_MAX_JSON_ITEMS = 500_000
_MAX_ARTIFACT_JSON_ITEMS = 2_000_000
_FLOW_PAGE_SIZE = 4
_ASCII_CONTROL_CUTOFF = 0x20
_UTF8_ONE_BYTE_MAX = 0x7F
_UTF8_TWO_BYTE_MAX = 0x7FF
_UTF8_THREE_BYTE_MAX = 0xFFFF
_UNICODE_SURROGATE_MIN = 0xD800
_UNICODE_SURROGATE_MAX = 0xDFFF
_VOLATILE_TOP_LEVEL_FIELDS = frozenset(
    {"updated_at", "created_at", "user_id", "folder_id", "workspace_id", "access_type", "gradient", "version_token"}
)
_VOLATILE_NODE_FIELDS = frozenset({"positionAbsolute", "dragging", "selected"})

_T = TypeVar("_T")


class ProjectArtifactError(ValueError):
    """Base class for safe, caller-visible package construction failures."""


class EmptyProjectArtifactError(ProjectArtifactError):
    """Raised when a project has no flows to package."""


class ProjectArtifactNotFoundError(ProjectArtifactError):
    """Raised when the requested project is not visible to the caller."""


class ProjectArtifactLimitError(ProjectArtifactError):
    """Raised when package input exceeds a configured resource ceiling."""


@dataclass(frozen=True, slots=True)
class ProjectArtifactLimits:
    """Resource ceilings applied before returning an in-memory package."""

    max_flow_count: int = 500
    max_flow_bytes: int = 8 * 1024 * 1024
    max_expanded_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        for field_name in ("max_flow_count", "max_flow_bytes", "max_expanded_bytes"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                msg = f"{field_name} must be a positive integer"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProjectArtifactFlow:
    """Manifest metadata for one packaged flow."""

    flow_id: UUID
    name: str
    path: str
    sha256: str
    size: int
    required_variables: tuple[str, ...]
    required_connections: tuple[ProjectArtifactRequiredConnection, ...]
    required_providers: tuple[str, ...] = ()
    required_models: tuple[ProjectArtifactRequiredModel, ...] = ()
    # Model fields that name no resolvable provider: a selection left to run
    # time cannot be read here, and a count is the honest way to say so.
    unresolved_model_fields: int = 0
    # What this flow's MCP servers need where it is deployed: variable names an
    # external server's credential resolves from, and sibling projects an
    # internal one calls, which have to already be deployed there.
    required_mcp_variables: tuple[str, ...] = ()
    required_mcp_projects: tuple[ProjectArtifactRequiredMcpProject, ...] = ()


@dataclass(frozen=True, order=True, slots=True)
class ProjectArtifactRequiredMcpProject:
    """One sibling project a flow's MCP server calls, and the name it calls it by.

    The name is carried rather than derived. An auto-created project server is named
    after its project, but a server can be added under any name, and a rebuilt
    connection stored under a name the flow does not use is a row the flow never
    finds -- failing at the first tool call rather than at deploy.
    """

    server_name: str
    project_id: str


@dataclass(frozen=True, order=True, slots=True)
class ProjectArtifactRequiredConnection:
    """One non-secret connection handle and its static scope requirements."""

    provider: str
    name: str
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True, order=True, slots=True)
class ProjectArtifactRequiredModel:
    """One model a flow selects, in the shape the policy blocks models by.

    ``ModelProviderPolicyDecision.allows_model`` matches a blocked key by bare
    name, by ``provider::name``, or by ``provider::type::name``, so a provider
    identity alone cannot answer whether the selected model is usable. Carrying
    the name and type is what lets a deploy target check the second question.

    ``model_type`` is the catalog's own value (``llm`` or ``embeddings``) and is
    absent when the saved selection did not carry it; the policy then tries
    every type segment, so an absent type never widens what is allowed.
    """

    provider: str
    name: str
    model_type: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectArtifactExternalMcpServer:
    """One external MCP server a packaged flow calls, and the config it reaches it by.

    Returned beside the archive and deliberately *not* written into it. The manifest
    and the packaged graphs reduce every MCP field to a name, because an lfpkg is a
    file people store and move; the configuration still has to reach a deploy target,
    so it rides on this object to whoever is deploying and no further.

    Only a config whose every credential is already a variable reference appears here.
    Saving a flow rewrites a literal into a generated ``MCP_*`` name, so for a saved
    flow that is every external server, and one that still holds a literal is left out
    rather than handed on.
    """

    server_name: str
    config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectArtifact:
    """Immutable package bytes and non-secret response metadata."""

    content: bytes
    filename: str
    media_type: str
    project_id: UUID
    project_name: str
    flows: tuple[ProjectArtifactFlow, ...]
    # MB/KB the packaged flows reference, shaped for the Control Plane's SyncRequest.
    # Empty when no flow references a Memory Base or Knowledge Base.
    dependencies: dict[str, Any] = field(default_factory=dict)
    project_description: str | None = None
    # Beside the bytes, never inside them. See ProjectArtifactExternalMcpServer.
    external_mcp_servers: tuple[ProjectArtifactExternalMcpServer, ...] = ()

    @property
    def flow_count(self) -> int:
        """Return the number of flow payloads in the package."""
        return len(self.flows)


@dataclass(frozen=True, slots=True)
class ProjectDeploymentSnapshotFlow:
    """One safe, replacement-compatible flow in a deployment snapshot."""

    flow_id: UUID
    name: str
    endpoint_name: str | None
    description: str | None
    data: dict[str, Any]
    # Exposure/presentation FlowCreate fields, carried end-to-end so a
    # rollback (PUT /replacement-operations only applies fields the caller
    # sends) or a restore-after-delete does not silently reset them to
    # FlowCreate's defaults. workspace_id/user_id/folder_id are deliberately
    # excluded pending a decision on how a deploy target should treat them.
    # Same types and defaults as FlowBase.
    is_component: bool | None = False
    locked: bool | None = False
    mcp_enabled: bool | None = False
    action_name: str | None = None
    action_description: str | None = None
    access_type: AccessTypeEnum = AccessTypeEnum.PRIVATE
    flow_type: FlowType = FlowType.WORKFLOW
    a2a_enabled: bool | None = False
    a2a_card_overrides: dict[str, Any] | None = None
    tags: list[str] | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    gradient: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            msg = f"flow file {self.flow_id} has an empty name"
            raise ProjectArtifactError(msg)


@dataclass(frozen=True, slots=True)
class ProjectDeploymentSnapshot:
    """A read-only serving snapshot detached from the database session."""

    project_id: UUID
    project_name: str
    project_description: str | None
    flows: tuple[ProjectDeploymentSnapshotFlow, ...]
    dependencies: dict[str, Any]
    required_variables: tuple[str, ...]
    required_connections: tuple[ProjectArtifactRequiredConnection, ...] = ()
    # Same two facts the packaged manifest carries. A snapshot deploy and a
    # zip deploy must present the same provider requirements, or the deploy
    # precheck's answer would depend on which path the caller took.
    required_providers: tuple[str, ...] = ()
    required_models: tuple[ProjectArtifactRequiredModel, ...] = ()
    unresolved_model_fields: int = 0
    # What the flows' MCP servers need from wherever this is deployed: global
    # variable names only whoever runs that environment can supply, and sibling
    # projects that have to already be deployed there for a connection to resolve.
    required_mcp_variables: tuple[str, ...] = ()
    required_mcp_projects: tuple[ProjectArtifactRequiredMcpProject, ...] = ()

    def __post_init__(self) -> None:
        if not self.project_name or not self.project_name.strip():
            msg = "project snapshot has an empty project name"
            raise ProjectArtifactError(msg)


@dataclass(frozen=True, slots=True)
class _FlowSnapshot:
    flow_id: UUID
    name: str
    payload: dict[str, Any]
    owner_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class _SnapshotBatch:
    snapshots: tuple[_FlowSnapshot, ...]
    estimated_bytes: int
    item_count: int


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=path, date_time=_FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = _ZIP_FILE_MODE << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    return info


@dataclass(frozen=True, slots=True)
class _ModelRequirements:
    """What one flow's model fields ask of a deploy target.

    Kept as one value rather than three loose returns because every caller
    needs all three together: the two lists are only trustworthy when read
    alongside the count of fields neither list could describe.
    """

    providers: tuple[str, ...] = ()
    models: tuple[ProjectArtifactRequiredModel, ...] = ()
    unresolved_fields: int = 0

    @staticmethod
    def merged(parts: Iterable[_ModelRequirements]) -> _ModelRequirements:
        """Union several flows' requirements, deduplicating and summing the count."""
        providers: set[str] = set()
        models: set[ProjectArtifactRequiredModel] = set()
        unresolved = 0
        for part in parts:
            providers.update(part.providers)
            models.update(part.models)
            unresolved += part.unresolved_fields
        return _ModelRequirements(
            providers=tuple(sorted(providers)),
            models=tuple(sorted(models, key=_model_sort_key)),
            unresolved_fields=unresolved,
        )


@dataclass(frozen=True, slots=True)
class _McpRequirements:
    """What one flow's MCP servers ask of a deploy target.

    Two lists because the target answers two different questions about them. A
    variable it has to already hold, which only whoever runs that environment can
    supply. A project that has to already be deployed there, which the deploy can
    check for itself and then rebuild the connection against.

    Nothing here counts secrets left embedded in a config, deliberately. A strict
    snapshot already refuses to capture a flow whose MCP config is not provably
    free of them, so by the time requirements are collected the only values left
    are references. A count would record a state this path cannot reach.
    """

    variables: tuple[str, ...] = ()
    projects: tuple[ProjectArtifactRequiredMcpProject, ...] = ()

    @staticmethod
    def merged(parts: Iterable[_McpRequirements]) -> _McpRequirements:
        """Union several flows' requirements, deduplicating both lists."""
        variables: set[str] = set()
        projects: set[ProjectArtifactRequiredMcpProject] = set()
        for part in parts:
            variables.update(part.variables)
            projects.update(part.projects)
        return _McpRequirements(variables=tuple(sorted(variables)), projects=tuple(sorted(projects)))


def _model_sort_key(model: ProjectArtifactRequiredModel) -> tuple[str, str, str]:
    """Order models deterministically even when only some carry a type.

    The dataclass ordering compares ``model_type`` directly, and ``None``
    cannot be ordered against a string: one flow can type a model the other
    leaves untyped, and the merged set holds both.
    """
    return (model.provider, model.name, model.model_type or "")


_MODEL_BASE_CLASSES = frozenset({"LanguageModel", "Embeddings"})
# ``ModelInput`` keeps this literal as the value when the builder wires the
# model in over an edge instead of picking one. The provider then belongs to
# the connected component, which this walk reaches on its own, so the field
# itself requires nothing and must not be counted as unresolved.
_MODEL_CONNECTED_SENTINEL = "connect_other_models"


def _model_entry_selection(entry: object) -> tuple[str, str | None, str | None] | None:
    """The provider, model name and model type one model-field entry selects.

    ``None`` when the entry names no provider. A bare model name is
    deliberately not treated as a provider: the runtime resolves those through
    the catalog, so deriving an identity from the model string would invent a
    provider that policy would then refuse.

    The model name can be absent even when the provider is not, so the two are
    reported separately rather than as one key.
    """
    if not isinstance(entry, dict):
        return None
    provider = entry.get("provider")
    name = entry.get("name")
    if isinstance(provider, str) and provider.strip() and provider.strip().casefold() != "unknown":
        metadata = entry.get("metadata")
        raw_type = metadata.get("model_type") if isinstance(metadata, dict) else None
        model_type = raw_type.strip() if isinstance(raw_type, str) and raw_type.strip() else None
        model_name = name.strip() if isinstance(name, str) and name.strip() else None
        return provider.strip(), model_name, model_type
    # Observed shape: the real spec serialized into ``name`` with the outer
    # provider left as a placeholder. Unwrap once rather than lose the identity.
    if isinstance(name, str) and name.strip().startswith(("[", "{")):
        try:
            parsed = json.loads(name)
        except (ValueError, RecursionError):
            # RecursionError: JSON nested inside a string escapes the flow's own
            # depth preflight, so a deeply nested value must not crash packaging.
            return None
        if isinstance(parsed, list):
            # Only a single wrapped spec is unwrapped. Reading the first of
            # several would report a partial list as the whole answer; as
            # unreadable, the field is counted as unresolved instead.
            if len(parsed) != 1:
                return None
            parsed = parsed[0]
        return _model_entry_selection(parsed)
    return None


def _model_field_selections(value: object) -> tuple[list[tuple[str, str | None, str | None]], bool] | None:
    """Every selection one model-field value carries, and whether any entry was unreadable.

    ``None`` means the field states no requirement at all. Otherwise the flag
    is true when the field states a requirement this code cannot fully read:
    no entries, or one entry among readable ones that names no provider. Either
    way the selections listed are not the field's whole answer, so the field
    counts as unresolved even though its readable providers are still listed.
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return [], True
        if text == _MODEL_CONNECTED_SENTINEL:
            return None
        try:
            parsed = json.loads(text)
        except (ValueError, RecursionError):
            # A bare name. The catalog decides the provider, so nothing to read.
            return [], True
        entries = parsed if isinstance(parsed, list) else [parsed]
    elif isinstance(value, dict):
        entries = [value]
    elif isinstance(value, list):
        entries = list(value)
    else:
        return [], True
    selections = [_model_entry_selection(entry) for entry in entries]
    readable = [selection for selection in selections if selection is not None]
    return readable, not entries or len(readable) < len(selections)


def _connected_model_overrides(flow_data: dict) -> dict[str, set[str]]:
    """Index runtime override inputs by node, within this graph's edge scope."""
    connected: dict[str, set[str]] = {}
    edges = flow_data.get("edges")
    if not isinstance(edges, list):
        return connected
    for edge in edges:
        if not isinstance(edge, dict) or not isinstance(target := edge.get("target"), str):
            continue
        data = edge.get("data")
        if isinstance(data, dict) and data:
            handle = data.get("targetHandle")
            field_name = handle.get("fieldName") if isinstance(handle, dict) else None
        else:
            # Legacy edges encode the input as ``types|field|node``.
            handle = edge.get("targetHandle")
            parts = handle.split("|") if isinstance(handle, str) else []
            field_name = parts[1] if len(parts) > 1 else None
        if field_name in ("provider", "model_name"):
            connected.setdefault(target, set()).add(field_name)
    return connected


def _apply_model_requirement_overrides(
    selections: tuple[list[tuple[str, str | None, str | None]], bool] | None,
    template: dict,
    connected_fields: Collection[str],
) -> tuple[list[tuple[str, str | None, str | None]], bool] | None:
    """Apply the canonical model selector's scalar overlays without resolving variables.

    Runtime ``apply_model_overrides`` uses the first selection when an overlay
    is active. Variable- or edge-backed values are unknown at packaging time:
    retain only identities still known and mark the field as incomplete.
    """
    overrides: dict[str, str] = {}
    dynamic: set[str] = set()
    for name in ("provider", "model_name"):
        field_value = template.get(name)
        if not isinstance(field_value, dict):
            continue
        if name in connected_fields or coalesce_bool(field_value.get("load_from_db")):
            dynamic.add(name)
        elif isinstance(value := field_value.get("value"), str):
            overrides[name] = value.strip()
        elif value is not None:
            dynamic.add(name)
    if not any(overrides.values()) and not dynamic:
        return selections
    if "provider" in dynamic or selections is None:
        return [], True
    readable, incomplete = selections
    provider_override = overrides.get("provider")
    name_override = overrides.get("model_name")
    if readable:
        provider, model_name, model_type = readable[0]
        # A different provider clears the old selection's metadata at runtime.
        if provider_override and provider_override != provider:
            model_type = None
        provider = provider_override or provider
        model_name = None if "model_name" in dynamic else (name_override or model_name)
        return [(provider, model_name, model_type)], incomplete or bool(dynamic)
    if provider_override:
        model_name = None if "model_name" in dynamic else (name_override or None)
        return [(provider_override, model_name, None)], True
    return [], True


def _standalone_provider(node_inner: dict) -> str | None:
    """The provider of a component that is itself a model, not one that holds a field."""
    base_classes = node_inner.get("base_classes")
    if not isinstance(base_classes, list) or not _MODEL_BASE_CLASSES.intersection(base_classes):
        return None
    metadata = node_inner.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    # Local utilities and delegating wrappers have no provider of their own.
    if metadata.get("model_provider_policy_mode") in ("none", "delegate"):
        return None
    component = SimpleNamespace(
        display_name=node_inner.get("display_name"),
        model_provider_id=metadata.get("model_provider_id"),
    )
    module_name = metadata.get("module")
    return model_component_provider_id(component, module_name=module_name if isinstance(module_name, str) else None)


#: A model field declares what kind of model it holds (``ModelInput.model_type``),
#: in the input's vocabulary. The policy keys models by the catalog's vocabulary.
#: A declaration outside this map yields no type, and an untyped model makes the
#: policy try every type segment, so an unknown declaration never widens access.
_FIELD_MODEL_TYPES = {"language": "llm", "embedding": "embeddings"}


def _collect_model_requirements(flow_data: object) -> _ModelRequirements:
    """Collect model providers and selected models from regular and grouped nodes.

    Two shapes, because a flow names a provider in two ways: a model-typed
    field whose value carries the selection, and a component that is itself a
    model and implies one. Walked without recursion, like the connection refs.

    Providers and models are collected together but reported separately,
    because a deploy target asks two questions of them: whether the provider is
    approved at all, and whether the specific model it selects is blocked. A
    standalone model component answers only the first - it implies a provider
    but names no model - so the model list is never a complete mirror of the
    provider list.

    ``unresolved_fields`` counts model fields whose effective requirements
    cannot be fully read, including runtime overrides. A caller that treats
    the lists as the whole answer would pass a project the target cannot serve.
    """
    if not isinstance(flow_data, dict):
        return _ModelRequirements()
    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return _ModelRequirements()
    providers: set[str] = set()
    models: set[ProjectArtifactRequiredModel] = set()
    unresolved = 0
    node_frames = [(iter(nodes), _connected_model_overrides(flow_data))]
    while node_frames:
        node_iterator, connected_overrides = node_frames[-1]
        try:
            node = next(node_iterator)
        except StopIteration:
            node_frames.pop()
            continue
        if not isinstance(node, dict):
            continue
        node_inner = node.get("data", {}).get("node") if isinstance(node.get("data"), dict) else None
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        base_classes = node_inner.get("base_classes")
        has_model_output = isinstance(base_classes, list) and any(
            isinstance(base_class, str) and base_class in _MODEL_BASE_CLASSES for base_class in base_classes
        )
        saw_model_field = False
        if isinstance(template, dict):
            for field_name, field_value in template.items():
                if not isinstance(field_value, dict) or field_value.get("type") != "model":
                    continue
                saw_model_field = True
                # A selection saved from the model picker carries no type of its
                # own, but the runtime still checks one -- a language model as
                # ``llm`` -- so a typeless model reported here would be refused by
                # a typed allowlist the runtime satisfies. The field says which.
                declared_type = field_value.get("model_type")
                field_type = _FIELD_MODEL_TYPES.get(declared_type) if isinstance(declared_type, str) else None
                field_selections = _model_field_selections(field_value.get("value"))
                # Model consumers may have unrelated scalar fields with these
                # names. The overlays belong to the model selector components.
                if field_name == "model" and has_model_output:
                    node_id = node.get("id")
                    connected_fields = connected_overrides.get(node_id, set()) if isinstance(node_id, str) else set()
                    field_selections = _apply_model_requirement_overrides(field_selections, template, connected_fields)
                if field_selections is None:
                    continue
                selections, incomplete = field_selections
                if incomplete:
                    unresolved += 1
                for provider, model_name, model_type in selections:
                    provider_id = resolve_provider_id(provider)
                    providers.add(provider_id)
                    if model_name is not None:
                        models.add(
                            ProjectArtifactRequiredModel(
                                provider=provider_id,
                                name=model_name,
                                model_type=model_type or field_type,
                            )
                        )
        # A component holding a model field delegates the choice to that field;
        # only one with no such field speaks for its own provider.
        if not saw_model_field and (standalone := _standalone_provider(node_inner)) is not None:
            providers.add(standalone)
        nested_flow = node_inner.get("flow")
        if isinstance(nested_flow, dict):
            nested_data = nested_flow.get("data")
            nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
            if isinstance(nested_nodes, list):
                node_frames.append((iter(nested_nodes), _connected_model_overrides(nested_data)))
    return _ModelRequirements(
        providers=tuple(sorted(providers)),
        models=tuple(sorted(models, key=_model_sort_key)),
        unresolved_fields=unresolved,
    )


def _effective_mcp_config(
    server_name: object, inline: object, registered: Mapping[str, dict[str, Any]] | None
) -> dict[str, Any]:
    """The config a flow actually reaches this server through.

    The registered row wins over whatever is inline, because that is the precedence
    ``resolve_mcp_config`` applies when the flow runs. Reading them the other way round
    lets a deploy declare one target while the flow calls another.

    Usually there is nothing inline at all: selecting a registered server stores only
    its name, and the address book holds the rest.
    """
    if isinstance(server_name, str) and registered:
        from_row = registered.get(server_name)
        if isinstance(from_row, dict) and from_row:
            return from_row
    return inline if isinstance(inline, dict) else {}


def _mcp_config_url(config: dict[str, Any]) -> object:
    """The address this config connects to, whichever shape it is written in.

    A streamable-HTTP entry puts it at ``url``. The stdio entry Langflow seeds for a
    project puts it in ``args``, after the mcp-proxy flags, which is why reading
    ``url`` alone failed to recognise a sibling project configured that way.
    """
    if config.get("url") is not None:
        return config.get("url")
    args = config.get("args")
    if isinstance(args, list):
        for argument in args:
            if isinstance(argument, str) and project_id_from_mcp_url(argument):
                return argument
    return None


def _mcp_config_requirements(
    server_name: object, config: object
) -> tuple[set[str], set[ProjectArtifactRequiredMcpProject]]:
    """Read one server's config for the variables and the project it depends on.

    Mirrors what ``strip_config_secrets`` touches, so the two cannot drift: the
    credential-bearing maps it rewrites are the only places a reference survives,
    because the top-level secret fields are deleted rather than replaced.

    ``server_name`` travels with the project because that is what the flow resolves
    by: the component looks its server up by name and prefers the stored row over
    the config embedded here, so a deploy that rebuilds the connection under any
    other name writes a row the flow never finds.

    One of our own projects reports *only* the project, never the credential beside
    it. The deploy replaces that whole configuration with the target's own address
    and a key minted there, so the author's credential is discarded rather than
    carried -- and it is the authoring plane's key, which the target must never be
    asked to hold. Declaring it refuses every internal connection for a variable
    nobody should set.
    """
    variables: set[str] = set()
    projects: set[ProjectArtifactRequiredMcpProject] = set()
    if not isinstance(config, dict) or not isinstance(server_name, str) or not server_name:
        return variables, projects
    url = _mcp_config_url(config)
    if url_variable := variable_reference_name(url):
        # A URL behind a variable names no project until it resolves, so it is
        # reported as a variable and treated as external. Being wrong this way
        # asks for something harmless; the other way mints a key for a stranger.
        variables.add(url_variable)
    elif project_id := project_id_from_mcp_url(url):
        return variables, {ProjectArtifactRequiredMcpProject(server_name=server_name, project_id=project_id)}
    for key in MCP_SECRET_CONFIG_MAPS:
        entries = config.get(key)
        if not isinstance(entries, dict):
            continue
        for entry_key, entry_value in entries.items():
            if key == "headers" and str(entry_key).lower() in NON_SECRET_HEADERS:
                continue
            if entry_value in (None, ""):
                continue
            # The name the target will resolve this credential from, which must be the
            # one `_referenced_mcp_config` writes into the carried config. A value that
            # is already a reference keeps its name; a literal read from the address
            # book is declared under the name the scrubber would have given it, because
            # that is the name it travels as.
            variables.add(variable_reference_name(entry_value) or variable_name_for(server_name, str(entry_key)))
    return variables, projects


def _mcp_field_values(flow_data: object) -> Iterator[dict[str, Any]]:
    """Every MCP field value in a flow, from regular and grouped nodes alike.

    Walked without recursion, like the connection refs. Shared by the two readers of
    these fields so a server reachable by one is reachable by the other: a config the
    requirements see but the carried list does not would declare a credential nothing
    then resolves.
    """
    if not isinstance(flow_data, dict):
        return
    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return
    node_frames = [iter(nodes)]
    while node_frames:
        try:
            node = next(node_frames[-1])
        except StopIteration:
            node_frames.pop()
            continue
        if not isinstance(node, dict):
            continue
        node_inner = node.get("data", {}).get("node") if isinstance(node.get("data"), dict) else None
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        if isinstance(template, dict):
            for field_value in template.values():
                if not isinstance(field_value, dict) or field_value.get("type") != "mcp":
                    continue
                value = field_value.get("value")
                if isinstance(value, dict):
                    yield value
        nested_flow = node_inner.get("flow")
        if isinstance(nested_flow, dict):
            nested_data = nested_flow.get("data")
            nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
            if isinstance(nested_nodes, list):
                node_frames.append(iter(nested_nodes))


def _referenced_mcp_config(server_name: str, config: dict[str, Any]) -> dict[str, Any] | None:
    """The config to carry to a deploy target, with every credential a variable name.

    The address book holds real credentials, so it can never be carried as-is. Each
    one is replaced by the name of the variable the target resolves it from, using the
    same deterministic naming the save-time scrubber uses -- so a value already written
    as a reference is kept untouched, and a literal becomes the name it would have been
    given anyway. The target then asks its own variable store, which is what lets one
    environment hold a sandbox credential and another the real one.

    Returns ``None`` for a config this cannot be done to safely. A credential inside
    ``args`` is the case that matters: the stdio shape hides one after ``--headers``,
    and rewriting positional arguments is guesswork, so such a config is left behind
    rather than risk carrying the value itself.
    """
    carried = deepcopy(config)
    args = carried.get("args")
    if isinstance(args, list) and any(isinstance(a, str) and a == "--headers" for a in args):
        return None
    for key in MCP_SECRET_CONFIG_MAPS:
        entries = carried.get(key)
        if not isinstance(entries, dict):
            continue
        for entry_key, entry_value in list(entries.items()):
            if key == "headers" and str(entry_key).lower() in NON_SECRET_HEADERS:
                continue
            if entry_value in (None, "") or variable_reference_name(entry_value) is not None:
                continue
            entries[entry_key] = variable_name_for(server_name, str(entry_key))
    return carried


def _collect_external_mcp_servers(
    flow_data: object, registered: Mapping[str, dict[str, Any]] | None = None
) -> tuple[ProjectArtifactExternalMcpServer, ...]:
    """The external MCP servers a flow calls, read from its unscrubbed data.

    Walks the same fields as ``_collect_mcp_requirements`` and splits the two kinds the
    same way: a URL naming one of our projects is a sibling, which a deploy rebuilds
    against its target, and anything else is external, which a deploy can only carry.
    """
    servers: dict[str, ProjectArtifactExternalMcpServer] = {}
    for value in _mcp_field_values(flow_data):
        name = value.get("name")
        config = _effective_mcp_config(name, value.get("config"), registered)
        if not isinstance(name, str) or not name or not config:
            continue
        url = _mcp_config_url(config)
        if project_id_from_mcp_url(url) is not None:
            continue
        # No address, nothing to connect to. Carrying it would write a row on the
        # target that the component then resolves through in preference to anything
        # else, which is worse than carrying nothing at all.
        if not url:
            continue
        if name in servers:
            continue
        carried = _referenced_mcp_config(name, config)
        if carried is None:
            continue
        servers[name] = ProjectArtifactExternalMcpServer(server_name=name, config=carried)
    return tuple(servers.values())


def _collect_mcp_requirements(
    flow_data: object, registered: Mapping[str, dict[str, Any]] | None = None
) -> _McpRequirements:
    """Collect what a flow's MCP servers need, from regular and grouped nodes.

    The project ids collected here name a project but do not prove one is ours:
    any host can serve that path shape. Confirming the origin belongs to the
    deploy target is the caller's job, and skipping it would mint a key for this
    plane and write it into a config pointing somewhere else.
    """
    variables: set[str] = set()
    projects: set[ProjectArtifactRequiredMcpProject] = set()
    for value in _mcp_field_values(flow_data):
        name = value.get("name")
        field_variables, field_projects = _mcp_config_requirements(
            name, _effective_mcp_config(name, value.get("config"), registered)
        )
        variables.update(field_variables)
        projects.update(field_projects)
    return _McpRequirements(variables=tuple(sorted(variables)), projects=tuple(sorted(projects)))


def _collect_required_connections(flow_data: object) -> tuple[ProjectArtifactRequiredConnection, ...]:
    """Collect connection refs from regular and grouped nodes without recursion."""
    if not isinstance(flow_data, dict):
        return ()
    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return ()
    collected: dict[tuple[str, str], set[str]] = {}
    node_frames = [iter(nodes)]
    while node_frames:
        try:
            node = next(node_frames[-1])
        except StopIteration:
            node_frames.pop()
            continue
        if not isinstance(node, dict):
            continue
        node_inner = node.get("data", {}).get("node") if isinstance(node.get("data"), dict) else None
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        if isinstance(template, dict):
            for field_value in template.values():
                if not isinstance(field_value, dict) or field_value.get("type") != "connection_ref":
                    continue
                value = field_value.get("value")
                if value in (None, ""):
                    continue
                try:
                    ref = ConnectionRef.parse(value)
                except ValueError as exc:
                    msg = "project artifact contains an invalid connection reference"
                    raise ProjectArtifactError(msg) from exc
                declared_provider = field_value.get("provider")
                if declared_provider is not None and (
                    not isinstance(declared_provider, str) or declared_provider != ref.provider
                ):
                    msg = "project artifact connection reference does not match its declared provider"
                    raise ProjectArtifactError(msg)
                raw_scopes = field_value.get("required_scopes", [])
                if not isinstance(raw_scopes, list) or any(
                    not isinstance(scope, str) or not scope.strip() for scope in raw_scopes
                ):
                    msg = f"connection {ref.to_handle()!r} has invalid required scopes"
                    raise ProjectArtifactError(msg)
                collected.setdefault((ref.provider, ref.name), set()).update(scope.strip() for scope in raw_scopes)
        nested_flow = node_inner.get("flow")
        if isinstance(nested_flow, dict):
            nested_data = nested_flow.get("data")
            nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
            if isinstance(nested_nodes, list):
                node_frames.append(iter(nested_nodes))
    return tuple(
        ProjectArtifactRequiredConnection(provider=provider, name=name, scopes=tuple(sorted(scopes)))
        for (provider, name), scopes in sorted(collected.items())
    )


async def _known_variable_names(session: AsyncSession, owner_id: UUID | None) -> frozenset[str]:
    """Return the global-variable names the project owner's snapshot may keep as bindings.

    Mirrors ``langflow.api.v1.flows_helpers._export_variable_names`` (kept as its
    own copy here rather than imported, so this services-layer module does not
    reach up into api.v1). A snapshot keeps a ``load_from_db`` value only when
    it names one of the owner's existing global variables, so a name-shaped
    literal secret behind a stale ``load_from_db`` flag is never captured.
    """
    if owner_id is None:
        return frozenset()
    names = await get_variable_service().list_variables(user_id=owner_id, session=session)
    return frozenset(name for name in names if name)


def _normalized_flow_data(
    snapshot: _FlowSnapshot,
    *,
    strict_secret_safety: bool = False,
    keep_mcp_config: bool = False,
    known_variable_names: Collection[str] | None = None,
    registered_mcp_servers: Mapping[str, dict[str, Any]] | None = None,
) -> tuple[
    dict[str, Any],
    tuple[str, ...],
    tuple[ProjectArtifactRequiredConnection, ...],
    _ModelRequirements,
    _McpRequirements,
]:
    """Return the scrubbed flow envelope and the requirements read off it.

    The requirements are the flow's required variables, its connection refs,
    the model providers it selects, and a count of model fields that selected
    none.

    Kept separate from byte serialization so a caller that needs the
    structured envelope itself - a deployment snapshot flow, for instance -
    is not forced to serialize it to JSON and parse it back.

    ``keep_mcp_config`` is only ever passed by the deployment-snapshot caller:
    the zip/.lfpkg export path always gets a name-only MCP field, matching
    every other secret export. See ``strip_secret_field_values_in_place`` for
    what "provably clean" means and why an unclean config is nulled rather
    than dropped, which is what makes the strict equality check below fail
    closed on it.

    ``known_variable_names``, when given, narrows preserved ``load_from_db``
    values to ones naming a variable the project owner actually has - see
    ``strip_secret_field_values_in_place`` for why that closes the
    stale-flag/name-shaped-secret gap a shape check alone cannot.
    """
    # Scrubbing and volatile-field removal mutate nested values in place. Copy
    # first so aliases held by the snapshot or persisted Flow data stay intact.
    scrubbed = deepcopy(snapshot.payload)
    # Deployment scrubbing keeps ``load_from_db`` variable-name references so
    # the serving side can provision credentials under the same names; the
    # collected names feed the manifest's required-variables listing.
    variable_references: set[str] = set()
    required_connections = _collect_required_connections(scrubbed.get("data"))
    model_requirements = _collect_model_requirements(scrubbed.get("data"))
    mcp_requirements = _collect_mcp_requirements(scrubbed.get("data"), registered_mcp_servers)
    scrubbed["data"] = strip_secret_field_values_in_place(
        scrubbed.get("data"),
        variable_references=variable_references,
        known_variable_names=known_variable_names,
        keep_mcp_config=keep_mcp_config,
    )
    if strict_secret_safety and scrubbed.get("data") != snapshot.payload.get("data"):
        msg = f"flow file {snapshot.flow_id} contains values that cannot be safely captured"
        raise ProjectArtifactError(msg)
    # Deployment packages retain runtime-native code strings. Strict snapshots
    # also retain every graph field after the scrub equality check so a serving
    # baseline can be replayed without false drift from editor-only metadata.
    # The normal git
    # export path splits code into one list element per line, which is useful
    # for diffs but can amplify a newline-heavy value into millions of Python
    # objects before serialization.
    for key in _VOLATILE_TOP_LEVEL_FIELDS:
        scrubbed.pop(key, None)
    data = scrubbed.get("data")
    if not strict_secret_safety and isinstance(data, dict):
        nodes = data.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict):
                    for key in _VOLATILE_NODE_FIELDS:
                        node.pop(key, None)
    return scrubbed, tuple(sorted(variable_references)), required_connections, model_requirements, mcp_requirements


def _normalized_flow_bytes(
    snapshot: _FlowSnapshot,
    *,
    strict_secret_safety: bool = False,
    registered_mcp_servers: Mapping[str, dict[str, Any]] | None = None,
) -> tuple[
    bytes,
    tuple[str, ...],
    tuple[ProjectArtifactRequiredConnection, ...],
    _ModelRequirements,
    _McpRequirements,
]:
    scrubbed, variable_references, required_connections, model_requirements, mcp_requirements = _normalized_flow_data(
        snapshot, strict_secret_safety=strict_secret_safety, registered_mcp_servers=registered_mcp_servers
    )
    return (
        canonical_json_bytes(scrubbed),
        variable_references,
        required_connections,
        model_requirements,
        mcp_requirements,
    )


def _json_string_size(value: str) -> int:
    """Return a conservative UTF-8 JSON string size without allocating bytes."""
    total = 2  # surrounding quotes
    for character in value:
        codepoint = ord(character)
        if _UNICODE_SURROGATE_MIN <= codepoint <= _UNICODE_SURROGATE_MAX:
            msg = "project artifact text contains an invalid Unicode surrogate"
            raise ProjectArtifactError(msg)
        if character in {'"', "\\"}:
            total += 2
        elif codepoint < _ASCII_CONTROL_CUTOFF:
            total += 6
        elif codepoint <= _UTF8_ONE_BYTE_MAX:
            total += 1
        elif codepoint <= _UTF8_TWO_BYTE_MAX:
            total += 2
        elif codepoint <= _UTF8_THREE_BYTE_MAX:
            total += 3
        else:
            total += 4
    return total


def _preflight_json_value(
    value: object,
    *,
    flow_id: UUID,
    max_bytes: int,
    max_items: int,
) -> tuple[int, int]:
    """Conservatively bound one JSON-compatible value without serializing it."""
    total_size = 0
    item_count = 0
    # Iterator frames keep traversal memory proportional to nesting depth,
    # rather than allocating one pending tuple per element in a wide list.
    frames: list[tuple[Iterator[object], int]] = [(iter((value,)), 0)]
    while frames:
        values, depth = frames[-1]
        try:
            value = next(values)
        except StopIteration:
            frames.pop()
            continue
        item_count += 1
        if item_count > max_items:
            msg = f"flow file {flow_id} exceeds the {max_items}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        if depth > _MAX_JSON_DEPTH:
            msg = f"flow file {flow_id} exceeds the {_MAX_JSON_DEPTH}-level nesting limit"
            raise ProjectArtifactLimitError(msg)

        if isinstance(value, dict):
            # Braces plus one colon per entry and one comma between entries.
            total_size += 2 + (2 * len(value))
            for key in value:
                total_size += _json_string_size(str(key))
            if value:
                frames.append((iter(value.values()), depth + 1))
        elif isinstance(value, (list, tuple)):
            total_size += 2 + len(value)
            if value:
                frames.append((iter(value), depth + 1))
        elif isinstance(value, str):
            total_size += _json_string_size(value)
        elif value is None or isinstance(value, bool):
            total_size += 5
        elif isinstance(value, (int, float)):
            total_size += len(str(value))
        else:
            msg = f"flow file {flow_id} contains unsupported persisted data"
            raise ProjectArtifactError(msg)

        if total_size > max_bytes:
            msg = f"flow file {flow_id} exceeds the {max_bytes}-byte preflight limit"
            raise ProjectArtifactLimitError(msg)
    return total_size, item_count


def _snapshot_rows(
    rows: tuple[Flow, ...],
    *,
    limits: ProjectArtifactLimits,
    remaining_expanded_bytes: int,
    remaining_items: int,
) -> _SnapshotBatch:
    """Detach and bound one small database page outside the event loop."""
    snapshots: list[_FlowSnapshot] = []
    estimated_bytes = 0
    item_count = 0
    for flow in rows:
        # Bound the persisted graph before Pydantic copies it into a detached
        # payload, then bound the complete exported model against both the
        # per-flow and remaining aggregate budgets.
        _preflight_json_value(
            flow.data,
            flow_id=flow.id,
            max_bytes=limits.max_flow_bytes,
            max_items=_MAX_JSON_ITEMS,
        )
        payload = FlowRead.model_validate(flow, from_attributes=True).model_dump(mode="json")
        flow_size, flow_items = _preflight_json_value(
            payload,
            flow_id=flow.id,
            max_bytes=limits.max_flow_bytes,
            max_items=_MAX_JSON_ITEMS,
        )
        if estimated_bytes + flow_size > remaining_expanded_bytes:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        if item_count + flow_items > remaining_items:
            msg = f"artifact exceeds the {_MAX_ARTIFACT_JSON_ITEMS}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        estimated_bytes += flow_size
        item_count += flow_items
        snapshots.append(_FlowSnapshot(flow_id=flow.id, name=flow.name, payload=payload, owner_id=flow.user_id))
    return _SnapshotBatch(tuple(snapshots), estimated_bytes, item_count)


def _model_entry(model: ProjectArtifactRequiredModel) -> dict[str, str]:
    """One required model as manifest JSON, omitting a type the flow did not carry."""
    entry = {"provider": model.provider, "name": model.name}
    if model.model_type is not None:
        entry["model_type"] = model.model_type
    return entry


def _mcp_project_entry(project: ProjectArtifactRequiredMcpProject) -> dict[str, str]:
    """One sibling project as the manifest carries it, name first for readability."""
    return {"server_name": project.server_name, "project_id": project.project_id}


def _build_archive(
    *,
    project_id: UUID,
    project_name: str,
    project_description: str | None = None,
    snapshots: tuple[_FlowSnapshot, ...],
    limits: ProjectArtifactLimits,
    dependencies: dict[str, list[dict[str, Any]]] | None = None,
    strict_secret_safety: bool = False,
    registered_mcp_servers: Mapping[str, dict[str, Any]] | None = None,
) -> ProjectArtifact:
    flow_entries: list[ProjectArtifactFlow] = []
    files: list[tuple[str, bytes]] = []
    expanded_size = 0

    # Validate all manifest-only persisted text before serializing any file.
    _json_string_size(project_name)
    for snapshot in snapshots:
        _json_string_size(snapshot.name)

    external_mcp: dict[str, ProjectArtifactExternalMcpServer] = {}
    for snapshot in snapshots:
        path = f"flows/{snapshot.flow_id}.json"
        # Read from the payload as saved, before scrubbing: the packaged graph below
        # keeps only the server's name, so this is the one place the configuration is
        # still here to be handed on.
        for server in _collect_external_mcp_servers(snapshot.payload.get("data"), registered_mcp_servers):
            external_mcp.setdefault(server.server_name, server)
        (
            content,
            required_variables,
            required_connections,
            model_requirements,
            mcp_requirements,
        ) = _normalized_flow_bytes(
            snapshot,
            strict_secret_safety=strict_secret_safety,
            registered_mcp_servers=registered_mcp_servers,
        )
        size = len(content)
        if size > limits.max_flow_bytes:
            msg = f"flow file {snapshot.flow_id} is {size} bytes, exceeding the {limits.max_flow_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        expanded_size += size
        if expanded_size > limits.max_expanded_bytes:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        files.append((path, content))
        flow_entries.append(
            ProjectArtifactFlow(
                flow_id=snapshot.flow_id,
                name=snapshot.name,
                path=path,
                sha256=hashlib.sha256(content).hexdigest(),
                size=size,
                required_variables=required_variables,
                required_connections=required_connections,
                required_providers=model_requirements.providers,
                required_models=model_requirements.models,
                unresolved_model_fields=model_requirements.unresolved_fields,
                required_mcp_variables=mcp_requirements.variables,
                required_mcp_projects=mcp_requirements.projects,
            )
        )

    required_connections_by_handle: dict[tuple[str, str], set[str]] = {}
    for flow in flow_entries:
        for connection in flow.required_connections:
            required_connections_by_handle.setdefault((connection.provider, connection.name), set()).update(
                connection.scopes
            )
    manifest_required_connections = [
        {"provider": provider, "name": name, "scopes": sorted(scopes)}
        for (provider, name), scopes in sorted(required_connections_by_handle.items())
    ]
    manifest_models = _ModelRequirements.merged(
        _ModelRequirements(
            providers=flow.required_providers,
            models=flow.required_models,
            unresolved_fields=flow.unresolved_model_fields,
        )
        for flow in flow_entries
    )
    manifest_mcp = _McpRequirements.merged(
        _McpRequirements(variables=flow.required_mcp_variables, projects=flow.required_mcp_projects)
        for flow in flow_entries
    )
    manifest: dict[str, Any] = {
        # v2 is already assigned to flows[].version_id. Dependencies use v3,
        # connection requirements use v4, model providers use v5, and MCP
        # requirements use v6, so an older reader refuses an artifact instead of
        # deploying without provisioning required resources. Each level is
        # claimed only when its field is populated, so a project that needs no
        # provider still packages as a version older readers already accept. An
        # unresolved count alone does not claim v5: it names nothing a target
        # could provision or approve, so an older reader loses nothing by
        # ignoring it. v6 is claimed on either MCP list, because both name
        # something the target must already have for the flow to run at all.
        "schema_version": (
            6
            if (manifest_mcp.variables or manifest_mcp.projects)
            else (
                5 if manifest_models.providers else (4 if manifest_required_connections else (3 if dependencies else 1))
            )
        ),
        "project": {"id": str(project_id), "name": project_name},
        # Names of every load_from_db-bound global variable the packaged flows
        # reference; the deploy target must provision each name before serving.
        "required_variables": sorted({name for flow in flow_entries for name in flow.required_variables}),
        # Model provider identities the packaged flows select, and the number
        # of model fields that selected none. A choice deferred to run time
        # cannot be read from the flow, so the count is what stops the list
        # from reading as the complete set of requirements.
        **(
            {
                "required_providers": list(manifest_models.providers),
                "required_models": [_model_entry(item) for item in manifest_models.models],
                "unresolved_model_fields": manifest_models.unresolved_fields,
            }
            if manifest_models.providers or manifest_models.unresolved_fields
            else {}
        ),
        # What the packaged flows' MCP servers need from the deploy target.
        # Omitted entirely when there is nothing to declare, so an artifact for
        # a project with no MCP servers is byte-identical to one built before.
        **(
            {
                "required_mcp_variables": list(manifest_mcp.variables),
                "required_mcp_projects": [_mcp_project_entry(item) for item in manifest_mcp.projects],
            }
            if manifest_mcp.variables or manifest_mcp.projects
            else {}
        ),
        "flows": [
            {
                "id": str(flow.flow_id),
                "name": flow.name,
                "path": flow.path,
                "sha256": flow.sha256,
                "size": flow.size,
                "required_variables": list(flow.required_variables),
                **({"required_providers": list(flow.required_providers)} if flow.required_providers else {}),
                **(
                    {"required_models": [_model_entry(item) for item in flow.required_models]}
                    if flow.required_models
                    else {}
                ),
                **({"unresolved_model_fields": flow.unresolved_model_fields} if flow.unresolved_model_fields else {}),
                **(
                    {"required_mcp_variables": list(flow.required_mcp_variables)} if flow.required_mcp_variables else {}
                ),
                **(
                    {"required_mcp_projects": [_mcp_project_entry(item) for item in flow.required_mcp_projects]}
                    if flow.required_mcp_projects
                    else {}
                ),
                **(
                    {
                        "required_connections": [
                            {"provider": item.provider, "name": item.name, "scopes": list(item.scopes)}
                            for item in flow.required_connections
                        ]
                    }
                    if flow.required_connections
                    else {}
                ),
            }
            for flow in flow_entries
        ],
    }
    if manifest_required_connections:
        manifest["required_connections"] = manifest_required_connections
    if dependencies:
        manifest["dependencies"] = dependencies
    manifest_bytes = canonical_json_bytes(manifest)
    if len(manifest_bytes) > limits.max_flow_bytes:
        msg = f"manifest file is {len(manifest_bytes)} bytes, exceeding the {limits.max_flow_bytes}-byte limit"
        raise ProjectArtifactLimitError(msg)
    expanded_size += len(manifest_bytes)
    if expanded_size > limits.max_expanded_bytes:
        msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
        raise ProjectArtifactLimitError(msg)

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        archive.writestr(_zip_info("manifest.json"), manifest_bytes)
        for path, content in files:
            archive.writestr(_zip_info(path), content)

    return ProjectArtifact(
        content=output.getvalue(),
        filename=f"langflow-project-{project_id}.lfpkg",
        media_type=LFPKG_MEDIA_TYPE,
        project_id=project_id,
        project_name=project_name,
        flows=tuple(flow_entries),
        dependencies=dependencies or {},
        project_description=project_description,
        external_mcp_servers=tuple(external_mcp.values()),
    )


async def _run_sync_non_abandoning(function: Callable[[], _T]) -> _T:
    """Delay request cancellation until a capacity-accounted worker exits."""
    worker = asyncio.create_task(asyncio.to_thread(function))
    cancellation_requested = False
    while True:
        try:
            result = await asyncio.shield(worker)
            break
        except asyncio.CancelledError:
            cancellation_requested = True
            current_task = asyncio.current_task()
            uncancel = getattr(current_task, "uncancel", None)
            if callable(uncancel):
                uncancel()

    if cancellation_requested:
        raise asyncio.CancelledError
    return result


async def _build_archive_non_abandoning(
    *,
    project_id: UUID,
    project_name: str,
    project_description: str | None = None,
    snapshots: tuple[_FlowSnapshot, ...],
    limits: ProjectArtifactLimits,
    dependencies: dict[str, list[dict[str, Any]]] | None = None,
    strict_secret_safety: bool = False,
    registered_mcp_servers: Mapping[str, dict[str, Any]] | None = None,
) -> ProjectArtifact:
    """Build an archive without outliving its caller's capacity lease."""
    return await _run_sync_non_abandoning(
        partial(
            _build_archive,
            project_id=project_id,
            project_name=project_name,
            project_description=project_description,
            snapshots=snapshots,
            limits=limits,
            dependencies=dependencies,
            strict_secret_safety=strict_secret_safety,
            registered_mcp_servers=registered_mcp_servers,
        )
    )


def _collect_dependency_refs(payload: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Return (memory_base_names, knowledge_base_names) referenced by a flow's nodes.

    A flow references a Memory Base by name at ``template.memory_base.value`` (the
    MB is flow-scoped) and a Knowledge Base by name at ``template.knowledge_base.value``,
    with ``template.new_kb_name.value`` naming a KB the flow creates inline. These
    names are the deploy target's provisioning keys — the same values the serving
    plane resolves the MB/KB by at run time.
    """
    mb_names: set[str] = set()
    kb_names: set[str] = set()
    data = payload.get("data")
    if not isinstance(data, dict):
        return mb_names, kb_names
    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        template = (((node.get("data") or {}).get("node")) or {}).get("template")
        if not isinstance(template, dict):
            continue
        for field_name, bucket in (("memory_base", mb_names), ("knowledge_base", kb_names), ("new_kb_name", kb_names)):
            entry = template.get(field_name)
            value = entry.get("value") if isinstance(entry, dict) else None
            if isinstance(value, str) and value.strip():
                bucket.add(value.strip())
    return mb_names, kb_names


# Non-secret backend routing fields used by the registered Chroma Cloud and
# OpenSearch backends. Credential values are represented only by ``*_variable``
# pointers, which are handled separately below.
_SAFE_BACKEND_ROUTING_KEYS = frozenset(
    {
        "cloud_host",
        "cloud_port",
        "cloud_region",
        "collection_name",
        "engine",
        "index_name",
        "mode",
        "space_type",
        "text_field",
        "use_ssl",
        "vector_field",
        "verify_certs",
    }
)
_SAFE_BACKEND_VALUE_TYPES = (str, int, float, bool)


def _scrub_backend_config(backend_config: dict[str, Any] | None) -> dict[str, Any]:
    """Return only deployable routing fields and variable-name pointers."""
    if not isinstance(backend_config, dict):
        return {}
    scrubbed: dict[str, Any] = {}
    for key, value in backend_config.items():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
        if lowered.endswith("_variable"):
            if isinstance(value, str):
                scrubbed[key] = value
            continue
        if lowered in _SAFE_BACKEND_ROUTING_KEYS and isinstance(value, _SAFE_BACKEND_VALUE_TYPES):
            scrubbed[key] = value
    return scrubbed


def _validated_backend_config(
    backend_type: object,
    backend_config: object,
    *,
    resource_kind: str,
    strict: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Validate the deployment's storage provider and portable configuration."""
    if not isinstance(backend_type, str) or not backend_type.strip():
        msg = f"referenced {resource_kind} has no deployable backend type"
        raise ProjectArtifactError(msg)
    config = backend_config if isinstance(backend_config, dict) else {}
    resolved_backend_type = backend_type.strip()
    if resolved_backend_type.lower() == "chroma":
        msg = f"referenced {resource_kind} uses retired Chroma storage. Migrate it to a supported remote provider"
        raise ProjectArtifactError(msg)
    try:
        local = is_local_backend(resolved_backend_type.lower(), config)
    except ValueError as exc:
        msg = f"referenced {resource_kind} uses an unknown vector-store backend"
        raise ProjectArtifactError(msg) from exc
    if local:
        label = "Chroma" if resolved_backend_type.lower() == "chroma" else "SQLite"
        msg = f"referenced {resource_kind} uses local {label}, which cannot be provisioned on the deployment target"
        raise ProjectArtifactError(msg)
    scrubbed = _scrub_backend_config(config)
    if strict:
        dropped = [key for key, value in config.items() if key not in scrubbed and value not in (None, "", [], {})]
        if dropped:
            msg = f"referenced {resource_kind} contains unsupported or unsafe backend configuration"
            raise ProjectArtifactError(msg)
    return resolved_backend_type, scrubbed


def _required_dependency_string(value: object, *, field_name: str, resource_kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"referenced {resource_kind} is missing {field_name}"
        raise ProjectArtifactError(msg)
    return value


def _store_dependency(
    items: dict[str, dict[str, Any]],
    *,
    name: str,
    item: dict[str, Any],
    resource_kind: str,
) -> None:
    existing = items.get(name)
    if existing is not None and existing != item:
        msg = f"referenced {resource_kind} name {name!r} is ambiguous across flow owners"
        raise ProjectArtifactError(msg)
    items[name] = item


async def _resolve_dependencies(
    session: AsyncSession,
    *,
    user: User | UserRead,
    owner_id: UUID,
    workspace_id: UUID | None,
    project_id: UUID,
    snapshots: tuple[_FlowSnapshot, ...],
    strict: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Resolve the MB/KB names the packaged flows reference to their provisioning specs.

    The names come from the flows; the specs come from each flow author's
    ``memory_base`` / ``knowledge_base`` rows. Each emitted item is shaped 1:1
    with the Control Plane's ``KnowledgeBaseItem`` / ``MemoryBaseItem`` so the
    deploy target passes it straight through the same validation with no second
    schema to drift. A Memory Base's backend lives on its auto-generated backing
    KB, so its ``backendType`` / ``backendConfig`` are read from that KB, and the
    backing KB is dropped from the KB list so it is never provisioned twice.
    Every resolved resource is authorized before its provisioning metadata is
    returned. Returns ``{}`` when the flows reference no MB or KB.
    """
    mb_refs: set[tuple[UUID, str]] = set()
    kb_refs: set[tuple[UUID, str]] = set()
    for snapshot in snapshots:
        refs_mb, refs_kb = _collect_dependency_refs(snapshot.payload)
        source_owner_id = getattr(snapshot, "owner_id", None) or owner_id
        mb_refs.update((source_owner_id, name) for name in refs_mb)
        kb_refs.update((source_owner_id, name) for name in refs_kb)
    if not mb_refs and not kb_refs:
        return {}

    memory_bases: dict[str, dict[str, Any]] = {}
    mb_backing_kb_refs: set[tuple[UUID, str]] = set()
    if mb_refs:
        mb_owner_ids = {ref_owner_id for ref_owner_id, _name in mb_refs}
        mb_names = {name for _ref_owner_id, name in mb_refs}
        candidate_mb_rows = (
            await session.exec(
                select(MemoryBase).where(
                    col(MemoryBase.user_id).in_(mb_owner_ids),
                    col(MemoryBase.name).in_(mb_names),
                )
            )
        ).all()
        mb_rows = [mb for mb in candidate_mb_rows if (mb.user_id, mb.name) in mb_refs]
        mb_by_ref = {(mb.user_id, mb.name): mb for mb in mb_rows}
        if mb_refs - set(mb_by_ref):
            msg = "one or more referenced Memory Bases were not found"
            raise ProjectArtifactError(msg)

        mb_backing_kb_refs = {(mb.user_id, mb.kb_name) for mb in mb_rows if mb.kb_name}
        if len(mb_backing_kb_refs) != len(mb_rows):
            msg = "a referenced Memory Base has no backing Knowledge Base"
            raise ProjectArtifactError(msg)
        backing_owner_ids = {backing_owner_id for backing_owner_id, _name in mb_backing_kb_refs}
        backing_names = {name for _backing_owner_id, name in mb_backing_kb_refs}
        candidate_backing_rows = (
            await session.exec(
                select(KnowledgeBaseRecord).where(
                    col(KnowledgeBaseRecord.user_id).in_(backing_owner_ids),
                    col(KnowledgeBaseRecord.name).in_(backing_names),
                )
            )
        ).all()
        backing_rows = [kb for kb in candidate_backing_rows if (kb.user_id, kb.name) in mb_backing_kb_refs]
        backing_by_ref = {(kb.user_id, kb.name): kb for kb in backing_rows}
        if mb_backing_kb_refs - set(backing_by_ref):
            msg = "a referenced Memory Base's backing Knowledge Base was not found"
            raise ProjectArtifactError(msg)

        for mb in sorted(mb_rows, key=lambda row: (row.name, str(row.user_id))):
            await ensure_knowledge_base_permission(
                user,
                KnowledgeBaseAction.READ,
                kb_id=mb.id,
                kb_user_id=mb.user_id,
                kb_name=mb.kb_name,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            backing_kb = backing_by_ref[(mb.user_id, mb.kb_name)]
            backend_type, backend_config = _validated_backend_config(
                backing_kb.backend_type,
                backing_kb.backend_config,
                resource_kind="Memory Base",
                strict=strict,
            )
            embedding_model = _required_dependency_string(
                mb.embedding_model,
                field_name="embedding model",
                resource_kind="Memory Base",
            )
            if mb.preprocessing and not mb.preproc_model:
                msg = "referenced Memory Base is missing its preprocessing model"
                raise ProjectArtifactError(msg)
            item: dict[str, Any] = {
                "name": mb.name,
                "flowId": str(mb.flow_id),
                "embeddingModel": embedding_model,
                "backendType": backend_type,
                "backendConfig": backend_config,
                "threshold": mb.threshold,
                "autoCapture": mb.auto_capture,
                "preprocessing": mb.preprocessing,
            }
            if mb.preproc_model:
                item["preprocModel"] = mb.preproc_model
            if mb.preproc_instructions:
                item["preprocInstructions"] = mb.preproc_instructions
            if mb.preproc_kill_phrase:
                item["preprocKillPhrase"] = mb.preproc_kill_phrase
            _store_dependency(memory_bases, name=mb.name, item=item, resource_kind="Memory Base")

    # Provisioning an MB creates its backing KB; never emit that exact KB on its own.
    kb_refs -= mb_backing_kb_refs
    knowledge_bases: dict[str, dict[str, Any]] = {}
    if kb_refs:
        kb_owner_ids = {ref_owner_id for ref_owner_id, _name in kb_refs}
        kb_names = {name for _ref_owner_id, name in kb_refs}
        candidate_kb_rows = (
            await session.exec(
                select(KnowledgeBaseRecord).where(
                    col(KnowledgeBaseRecord.user_id).in_(kb_owner_ids),
                    col(KnowledgeBaseRecord.name).in_(kb_names),
                )
            )
        ).all()
        kb_rows = [kb for kb in candidate_kb_rows if (kb.user_id, kb.name) in kb_refs]
        kb_by_ref = {(kb.user_id, kb.name): kb for kb in kb_rows}
        if kb_refs - set(kb_by_ref):
            msg = "one or more referenced Knowledge Bases were not found"
            raise ProjectArtifactError(msg)

        for kb in sorted(kb_rows, key=lambda row: (row.name, str(row.user_id))):
            await ensure_knowledge_base_permission(
                user,
                KnowledgeBaseAction.READ,
                kb_id=kb.id,
                kb_user_id=kb.user_id,
                kb_name=kb.name,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            backend_type, backend_config = _validated_backend_config(
                kb.backend_type,
                kb.backend_config,
                resource_kind="Knowledge Base",
                strict=strict,
            )
            model_selection = kb.model_selection if isinstance(kb.model_selection, dict) else {}
            embedding_provider = _required_dependency_string(
                model_selection.get("provider"),
                field_name="embedding provider",
                resource_kind="Knowledge Base",
            )
            embedding_model = _required_dependency_string(
                model_selection.get("name"),
                field_name="embedding model",
                resource_kind="Knowledge Base",
            )
            item = {
                "name": kb.name,
                "embeddingProvider": embedding_provider,
                "embeddingModel": embedding_model,
                "backendType": backend_type,
                "backendConfig": backend_config,
            }
            if kb.column_config:
                item["columnConfig"] = [
                    {
                        "columnName": entry.get("column_name", entry.get("columnName", "")),
                        # Rows can hold flags typed into the column table as strings.
                        "vectorize": coalesce_bool(entry.get("vectorize")),
                        "identifier": coalesce_bool(entry.get("identifier")),
                    }
                    for entry in kb.column_config
                    if isinstance(entry, dict)
                ]
            _store_dependency(knowledge_bases, name=kb.name, item=item, resource_kind="Knowledge Base")

    dependencies: dict[str, list[dict[str, Any]]] = {}
    if knowledge_bases:
        dependencies["knowledgeBases"] = [knowledge_bases[name] for name in sorted(knowledge_bases)]
    if memory_bases:
        dependencies["memoryBases"] = [memory_bases[name] for name in sorted(memory_bases)]
    return dependencies


@dataclass(frozen=True, slots=True)
class _ProjectSnapshotData:
    """Authorized, revision-consistent flow data staged before encoding."""

    project_id: UUID
    project_name: str
    project_description: str | None
    project_user_id: UUID | None
    snapshots: tuple[_FlowSnapshot, ...]
    dependencies: dict[str, list[dict[str, Any]]]


async def _verify_project_identity_unchanged(
    session: AsyncSession,
    *,
    project_id: UUID,
    project_name: str,
    project_description: str | None,
) -> None:
    """Fail a strict capture if the project's own name or description moved mid-packaging."""
    current_project = (
        await session.exec(select(Folder.id, Folder.name, Folder.description).where(Folder.id == project_id))
    ).first()
    if current_project is None or (current_project[1], current_project[2]) != (project_name, project_description):
        msg = "project changed during packaging"
        raise ProjectArtifactError(msg)


async def _registered_mcp_servers(session: AsyncSession, owner_id: UUID | None) -> dict[str, dict[str, Any]]:
    """The owner's MCP address book, decrypted, keyed by the name a flow resolves by.

    A flow references a server by name and usually carries no config of its own: the
    row is where the url and credentials live, and ``resolve_mcp_config`` prefers it
    over anything inline at run time. Reading it here makes this side agree with that,
    so a deploy cannot declare one thing while the flow runs against another.

    Decrypted because the url is what has to be read, and it is stored inside the same
    encrypted blob as the credentials. Nothing decrypted here is carried anywhere: the
    callers take the url, and replace every credential with the name of the variable
    that resolves it on the target.
    """
    if owner_id is None:
        return {}
    rows = (await session.exec(select(MCPServer).where(MCPServer.user_id == owner_id))).all()
    servers: dict[str, dict[str, Any]] = {}
    for row in rows:
        config = decrypt_mcp_config(row.config or {})
        if isinstance(config, dict):
            servers[row.name] = config
    return servers


async def _prepare_project_snapshot_data(
    session: AsyncSession,
    user: User | UserRead,
    project_id: UUID,
    *,
    flow_ids: Sequence[UUID] | None,
    limits: ProjectArtifactLimits,
    strict_snapshot: bool,
) -> _ProjectSnapshotData:
    """Authorize, load, and bound every flow a package or snapshot needs.

    Shared by ``build_project_artifact`` and ``build_project_deployment_snapshot``
    so both run identical authorization, revision-consistency, and
    dependency-resolution logic; only how the resulting flows are encoded (a
    zip archive vs. a JSON-native snapshot) differs downstream.

    The project lookup widens beyond the caller's owner namespace only when the
    registered authorization service explicitly supports cross-user fetch. Flow
    membership is determined by project folder regardless of author. Read checks
    are split into an actor-owned batch and a non-owned batch so the owner override
    is never applied to another author's flow, and every check must pass before
    any flow is packaged. Flow authorship and revision are revalidated while
    packaging so either kind of concurrent change fails consistently.
    """
    selected_flow_ids: tuple[UUID, ...] | None = None
    if flow_ids is not None:
        if not flow_ids:
            msg = "flow_ids must contain at least one flow ID when provided"
            raise ProjectArtifactError(msg)
        if len(set(flow_ids)) != len(flow_ids):
            msg = "flow_ids must not contain duplicate flow IDs"
            raise ProjectArtifactError(msg)
        selected_flow_ids = tuple(sorted(flow_ids, key=str))

    project = await authorized_or_owner_scoped(
        session,
        Folder,
        id_column=Folder.id,
        resource_id=project_id,
        owner_column=Folder.user_id,
        owner_id=user.id,
    )
    if project is None:
        msg = "Project not found"
        raise ProjectArtifactNotFoundError(msg)
    project_description = getattr(project, "description", None)

    await ensure_project_permission(
        user,
        ProjectAction.READ,
        project_id=project_id,
        project_user_id=project.user_id,
        workspace_id=project.workspace_id,
    )

    if selected_flow_ids is not None and len(selected_flow_ids) > limits.max_flow_count:
        msg = f"selected flow count {len(selected_flow_ids)} exceeds the {limits.max_flow_count}-flow limit"
        raise ProjectArtifactLimitError(msg)
    revision_statement = select(Flow.id, Flow.user_id, Flow.updated_at).where(Flow.folder_id == project_id)
    if selected_flow_ids is not None:
        revision_statement = revision_statement.where(col(Flow.id).in_(selected_flow_ids))
    revision_rows = list(
        (await session.exec(revision_statement.order_by(col(Flow.id)).limit(limits.max_flow_count + 1))).all()
    )
    if selected_flow_ids is not None and len(revision_rows) != len(selected_flow_ids):
        msg = "one or more selected flows were not found in the project"
        raise ProjectArtifactNotFoundError(msg)
    if not revision_rows:
        msg = "project has no flows to package"
        raise EmptyProjectArtifactError(msg)
    if len(revision_rows) > limits.max_flow_count:
        msg = f"project flow count {len(revision_rows)} exceeds the {limits.max_flow_count}-flow limit"
        raise ProjectArtifactLimitError(msg)

    ordered_revisions = tuple(sorted(revision_rows, key=lambda revision: str(revision[0])))
    ordered_flow_ids = tuple(flow_id for flow_id, _flow_user_id, _updated_at in ordered_revisions)
    initial_revisions = {flow_id: (flow_user_id, updated_at) for flow_id, flow_user_id, updated_at in ordered_revisions}
    actor_owned_flow_ids = [
        flow_id for flow_id, flow_user_id, _updated_at in ordered_revisions if flow_user_id == user.id
    ]
    non_owned_flow_ids = [
        flow_id for flow_id, flow_user_id, _updated_at in ordered_revisions if flow_user_id != user.id
    ]
    for permission_flow_ids, flow_user_id in (
        (actor_owned_flow_ids, user.id),
        (non_owned_flow_ids, None),
    ):
        if permission_flow_ids:
            await ensure_flows_permission(
                user,
                FlowAction.READ,
                flow_ids=permission_flow_ids,
                flow_user_id=flow_user_id,
                workspace_id=project.workspace_id,
                folder_id=project_id,
            )

    snapshots: list[_FlowSnapshot] = []
    estimated_bytes = 0
    item_count = 0
    for page_start in range(0, len(ordered_flow_ids), _FLOW_PAGE_SIZE):
        page_ids = ordered_flow_ids[page_start : page_start + _FLOW_PAGE_SIZE]
        rows = list(
            (
                await session.exec(
                    select(Flow)
                    .where(
                        col(Flow.id).in_(page_ids),
                        Flow.folder_id == project_id,
                    )
                    .order_by(col(Flow.id))
                )
            ).all()
        )
        ordered_rows = tuple(sorted(rows, key=lambda flow: str(flow.id)))
        if strict_snapshot and any(flow.fs_path for flow in ordered_rows):
            msg = "filesystem-backed flows cannot be safely captured"
            raise ProjectArtifactError(msg)
        expected_page_revisions = tuple((flow_id, *initial_revisions[flow_id]) for flow_id in page_ids)
        if tuple((flow.id, flow.user_id, flow.updated_at) for flow in ordered_rows) != expected_page_revisions:
            msg = "project flows changed during packaging"
            raise ProjectArtifactError(msg)

        remaining_expanded_bytes = limits.max_expanded_bytes - estimated_bytes
        remaining_items = _MAX_ARTIFACT_JSON_ITEMS - item_count
        if remaining_expanded_bytes <= 0:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        if remaining_items <= 0:
            msg = f"artifact exceeds the {_MAX_ARTIFACT_JSON_ITEMS}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        batch = await _run_sync_non_abandoning(
            partial(
                _snapshot_rows,
                ordered_rows,
                limits=limits,
                remaining_expanded_bytes=remaining_expanded_bytes,
                remaining_items=remaining_items,
            )
        )
        snapshots.extend(batch.snapshots)
        estimated_bytes += batch.estimated_bytes
        item_count += batch.item_count

    final_revision_statement = select(Flow.id, Flow.user_id, Flow.updated_at).where(Flow.folder_id == project_id)
    if selected_flow_ids is not None:
        final_revision_statement = final_revision_statement.where(col(Flow.id).in_(selected_flow_ids))
    final_revisions = tuple(
        (await session.exec(final_revision_statement.order_by(col(Flow.id)).limit(limits.max_flow_count + 1))).all()
    )
    if final_revisions != ordered_revisions:
        msg = "project flows changed during packaging"
        raise ProjectArtifactError(msg)

    dependencies = await _resolve_dependencies(
        session,
        user=user,
        owner_id=project.user_id,
        workspace_id=project.workspace_id,
        project_id=project_id,
        snapshots=tuple(snapshots),
        strict=strict_snapshot,
    )
    return _ProjectSnapshotData(
        project_id=project_id,
        project_name=project.name,
        project_description=project_description,
        project_user_id=project.user_id,
        snapshots=tuple(snapshots),
        dependencies=dependencies,
    )


async def build_project_artifact(
    session: AsyncSession,
    user: User | UserRead,
    project_id: UUID,
    *,
    flow_ids: Sequence[UUID] | None = None,
    limits: ProjectArtifactLimits | None = None,
    strict_snapshot: bool = False,
) -> ProjectArtifact:
    """Package selected readable flows, or every flow assigned to the project, into a zip.

    See ``_prepare_project_snapshot_data`` for the shared authorization,
    revision-consistency, and dependency-resolution behavior.
    """
    effective_limits = limits or ProjectArtifactLimits()
    prepared = await _prepare_project_snapshot_data(
        session,
        user,
        project_id,
        flow_ids=flow_ids,
        limits=effective_limits,
        strict_snapshot=strict_snapshot,
    )

    # The owner's address book, read once: a flow references a server by name and
    # usually carries no config, so this is where the url and credential names are.
    registered_mcp_servers = await _registered_mcp_servers(session, prepared.project_user_id)

    # Archive construction is intentionally non-abandoning. If the HTTP request
    # is cancelled, keep the caller suspended until the worker exits so the
    # Enterprise package semaphore continues to account for its memory use.
    artifact = await _build_archive_non_abandoning(
        project_id=prepared.project_id,
        project_name=prepared.project_name,
        project_description=prepared.project_description,
        snapshots=prepared.snapshots,
        limits=effective_limits,
        dependencies=prepared.dependencies,
        strict_secret_safety=strict_snapshot,
        registered_mcp_servers=registered_mcp_servers,
    )
    if strict_snapshot:
        await _verify_project_identity_unchanged(
            session,
            project_id=prepared.project_id,
            project_name=prepared.project_name,
            project_description=prepared.project_description,
        )
    return artifact


def _build_deployment_snapshot_flows(
    snapshots: tuple[_FlowSnapshot, ...],
    *,
    limits: ProjectArtifactLimits,
    known_variable_names: Collection[str] | None = None,
    registered_mcp_servers: Mapping[str, dict[str, Any]] | None = None,
    initial_expanded_bytes: int = 0,
) -> tuple[
    list[ProjectDeploymentSnapshotFlow],
    tuple[str, ...],
    tuple[ProjectArtifactRequiredConnection, ...],
    _ModelRequirements,
    _McpRequirements,
]:
    """Scrub and bound each flow for a snapshot without ever encoding or reading back a zip.

    ``known_variable_names`` is the project owner's real global-variable names,
    fetched once by the caller (this runs off the event loop via
    ``_run_sync_non_abandoning`` and cannot make its own DB call) - see
    ``_normalized_flow_data``.

    ``initial_expanded_bytes`` seeds the aggregate size bound with the
    project's own name and description - text that is not a flow but is still
    part of the captured snapshot - so a large enough project name/description
    cannot evade ``max_expanded_bytes`` entirely.

    Applies the same per-flow and aggregate byte bounds ``_build_archive`` applies
    to its zip entries - computed from the same canonical JSON encoding - so a
    snapshot cannot exceed the limits a packaged artifact would enforce.
    """
    flows: list[ProjectDeploymentSnapshotFlow] = []
    required_variables: set[str] = set()
    required_connections_by_handle: dict[tuple[str, str], set[str]] = {}
    model_requirements: list[_ModelRequirements] = []
    mcp_requirements: list[_McpRequirements] = []
    expanded_size = initial_expanded_bytes
    for snapshot in snapshots:
        _json_string_size(snapshot.name)
        (
            scrubbed,
            variable_references,
            required_connections,
            flow_model_requirements,
            flow_mcp_requirements,
        ) = _normalized_flow_data(
            snapshot,
            strict_secret_safety=True,
            keep_mcp_config=True,
            known_variable_names=known_variable_names,
            registered_mcp_servers=registered_mcp_servers,
        )
        content_size = len(canonical_json_bytes(scrubbed))
        if content_size > limits.max_flow_bytes:
            msg = (
                f"flow file {snapshot.flow_id} is {content_size} bytes, "
                f"exceeding the {limits.max_flow_bytes}-byte limit"
            )
            raise ProjectArtifactLimitError(msg)
        expanded_size += content_size
        if expanded_size > limits.max_expanded_bytes:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)

        data = scrubbed.get("data")
        if not isinstance(data, dict):
            msg = f"flow file {snapshot.flow_id} has no graph data"
            raise ProjectArtifactError(msg)
        flows.append(
            ProjectDeploymentSnapshotFlow(
                flow_id=snapshot.flow_id,
                name=snapshot.name,
                endpoint_name=scrubbed.get("endpoint_name"),
                description=scrubbed.get("description"),
                data=data,
                is_component=scrubbed.get("is_component", False),
                locked=scrubbed.get("locked", False),
                mcp_enabled=scrubbed.get("mcp_enabled", False),
                action_name=scrubbed.get("action_name"),
                action_description=scrubbed.get("action_description"),
                # Package-volatile presentation fields, read from the unscrubbed
                # source so the snapshot still round-trips them.
                access_type=AccessTypeEnum(snapshot.payload.get("access_type") or AccessTypeEnum.PRIVATE),
                # Not volatile - untouched by the scrub - but read the same way for
                # consistency with the other exposure fields on this line.
                flow_type=FlowType(scrubbed.get("flow_type") or FlowType.WORKFLOW),
                a2a_enabled=scrubbed.get("a2a_enabled", False),
                a2a_card_overrides=scrubbed.get("a2a_card_overrides"),
                tags=scrubbed.get("tags"),
                icon=scrubbed.get("icon"),
                icon_bg_color=scrubbed.get("icon_bg_color"),
                gradient=snapshot.payload.get("gradient"),
            )
        )
        required_variables.update(variable_references)
        model_requirements.append(flow_model_requirements)
        mcp_requirements.append(flow_mcp_requirements)
        for connection in required_connections:
            required_connections_by_handle.setdefault((connection.provider, connection.name), set()).update(
                connection.scopes
            )

    required_connections_out = tuple(
        ProjectArtifactRequiredConnection(provider=provider, name=name, scopes=tuple(sorted(scopes)))
        for (provider, name), scopes in sorted(required_connections_by_handle.items())
    )
    return (
        flows,
        tuple(sorted(required_variables)),
        required_connections_out,
        _ModelRequirements.merged(model_requirements),
        _McpRequirements.merged(mcp_requirements),
    )


async def build_project_deployment_snapshot(
    session: AsyncSession,
    user: User | UserRead,
    project_id: UUID,
    *,
    limits: ProjectArtifactLimits | None = None,
) -> ProjectDeploymentSnapshot:
    """Capture one bounded, secret-safe, read-only serving snapshot.

    Shares authorization, revision-consistency, and dependency resolution with
    ``build_project_artifact`` via ``_prepare_project_snapshot_data``, but never
    encodes a zip archive: the snapshot endpoint needs JSON, not an archive, so
    each flow is scrubbed and bounded directly from its structured form instead
    of being packaged, then unpacked again. Strict capture makes any graph or
    dependency information lost by scrubbing fail closed instead of creating an
    incomplete rollback baseline.
    """
    effective_limits = limits or ProjectArtifactLimits()
    prepared = await _prepare_project_snapshot_data(
        session,
        user,
        project_id,
        flow_ids=None,
        limits=effective_limits,
        strict_snapshot=True,
    )
    # Both the project name and description are captured verbatim in the
    # snapshot; check both for the same invalid-surrogate failure mode
    # (see _json_string_size) and count both toward max_expanded_bytes so
    # neither can evade the aggregate size bound every flow is held to.
    project_text_bytes = _json_string_size(prepared.project_name)
    if prepared.project_description is not None:
        project_text_bytes += _json_string_size(prepared.project_description)
    known_variable_names = await _known_variable_names(session, prepared.project_user_id)
    registered_mcp_servers = await _registered_mcp_servers(session, prepared.project_user_id)

    (
        flows,
        required_variables,
        required_connections,
        model_requirements,
        mcp_requirements,
    ) = await _run_sync_non_abandoning(
        partial(
            _build_deployment_snapshot_flows,
            prepared.snapshots,
            limits=effective_limits,
            known_variable_names=known_variable_names,
            registered_mcp_servers=registered_mcp_servers,
            initial_expanded_bytes=project_text_bytes,
        )
    )

    await _verify_project_identity_unchanged(
        session,
        project_id=prepared.project_id,
        project_name=prepared.project_name,
        project_description=prepared.project_description,
    )

    return ProjectDeploymentSnapshot(
        project_id=prepared.project_id,
        project_name=prepared.project_name,
        project_description=prepared.project_description,
        flows=tuple(flows),
        dependencies=dict(prepared.dependencies),
        required_variables=required_variables,
        required_connections=required_connections,
        required_providers=model_requirements.providers,
        required_models=model_requirements.models,
        unresolved_model_fields=model_requirements.unresolved_fields,
        required_mcp_variables=mcp_requirements.variables,
        required_mcp_projects=mcp_requirements.projects,
    )
