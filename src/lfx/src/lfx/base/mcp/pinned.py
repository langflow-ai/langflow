"""Pinned action-to-tool mode for preset MCP components.

A *pinned* preset does not trust runtime discovery.  The bundle that ships the
component freezes, in its capability manifest:

* the server endpoint and transport,
* an explicit action-to-tool mapping (one MCP tool identifier per capability),
* the raw JSON Schema of each pinned tool's arguments and results,
* and a "server version" pin, which is the content digest of the pinned
  ``tools/list`` plus the ``InitializeResult.serverInfo`` name/version when the
  server sends one (the MCP specification does not require it, and several GA
  servers do not).

At load time the discovered toolset is compared against that pin and any
difference -- an added, removed, or renamed tool, an argument- or result-schema
change, or a server-version/digest mismatch -- raises
:class:`~lfx.integrations.errors.IncompatibleToolError` instead of degrading to
whatever the server currently offers.  At call time the pinned argument schema
is enforced again, because ``MCPStructuredTool`` deliberately passes keys that
are not in the derived args schema through to the server
(``lfx.base.mcp.util`` ``_convert_parameters``); a discovery-time check alone
would let a drifted argument reach the provider.  Only an argument the pin does
not declare counts as drift: an omitted *required* field is a caller mistake no
bundle release can fix, so it is left to the derived args schema, which rejects
it with a message an agent can correct on the next turn.

The digest deliberately covers tool identity and schemas only, not tool
descriptions: descriptions are prompt material that providers edit routinely,
and folding them into the pin would turn every copy edit into a customer-visible
outage.  Descriptions still travel through the existing MCP redaction path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from lfx.integrations.errors import IncompatibleToolError

if TYPE_CHECKING:
    from lfx.base.mcp.util import MCPServerInfo

DIGEST_PREFIX = "sha256:"

__all__ = [
    "DIGEST_PREFIX",
    "DiscoveredTool",
    "PinnedServerSpec",
    "PinnedToolDiff",
    "PinnedToolSpec",
    "diff_pinned_tools",
    "discovered_tool",
    "enforce_pinned_tools",
    "pinned_spec_from_capabilities",
    "tools_list_digest",
    "validate_pinned_arguments",
]


# --------------------------------------------------------------------- models
class PinnedToolSpec(BaseModel):
    """One frozen MCP tool: its identifier and its raw JSON Schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: StrictStr = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


class PinnedServerSpec(BaseModel):
    """The pinned endpoint plus the complete tool set a component may see."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    server_url: StrictStr = Field(min_length=1)
    transport: Literal["streamable_http"] = "streamable_http"
    tools: tuple[PinnedToolSpec, ...] = Field(min_length=1)
    tools_list_hash: StrictStr | None = None
    server_name: StrictStr | None = None
    server_version: StrictStr | None = None

    @model_validator(mode="after")
    def _tool_names_are_unique(self) -> PinnedServerSpec:
        names = [tool.name for tool in self.tools]
        if len(set(names)) != len(names):
            msg = "A pinned MCP server spec must not repeat a tool name"
            raise ValueError(msg)
        return self

    @property
    def names(self) -> tuple[str, ...]:
        """Pinned tool identifiers, in manifest order."""
        return tuple(tool.name for tool in self.tools)

    def tool(self, name: str) -> PinnedToolSpec | None:
        """Return the pinned tool with this identifier, or ``None``."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def digest(self) -> str:
        """Content digest of the pinned tool set, in the ``tools/list`` form."""
        return tools_list_digest(self.tools)


@dataclass(frozen=True, slots=True)
class DiscoveredTool:
    """A tool as the server returned it, reduced to what the pin compares."""

    name: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


def discovered_tool(tool: Any) -> DiscoveredTool:
    """Normalize an MCP ``types.Tool`` or an ``MCPStructuredTool`` for comparison.

    ``update_tools`` turns each discovered tool into a ``StructuredTool`` whose
    derived ``args_schema`` has already lost the raw JSON Schema, so the raw
    schemas are carried forward on the tool's ``metadata`` instead.

    ``metadata`` is read FIRST and every candidate must be a mapping: a
    LangChain tool is a ``Runnable``, which defines ``input_schema`` and
    ``output_schema`` properties of its own that return pydantic model *classes*.
    Reading those first would silently compare an empty schema against the pin
    and report every real tool as re-shaped.
    """
    metadata = getattr(tool, "metadata", None)
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return DiscoveredTool(
        name=str(getattr(tool, "name", None) or ""),
        input_schema=_first_mapping(
            metadata.get("input_schema"),
            getattr(tool, "inputSchema", None),
            getattr(tool, "input_schema", None),
        )
        or {},
        output_schema=_first_mapping(
            metadata.get("output_schema"),
            getattr(tool, "outputSchema", None),
            getattr(tool, "output_schema", None),
        ),
    )


def _first_mapping(*candidates: Any) -> dict[str, Any] | None:
    """First candidate that is actually a JSON-Schema-shaped mapping."""
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return None


# --------------------------------------------------------------------- digest
def _canonical(value: Any) -> str:
    """Stable JSON form: key order and separators cannot change the digest."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def tools_list_digest(tools: Iterable[Any]) -> str:
    """Return the content digest of a tool list (identity plus schemas only)."""
    entries = sorted(
        (view.name, _canonical(view.input_schema), _canonical(view.output_schema))
        for view in (_view(tool) for tool in tools)
    )
    payload = _canonical(entries).encode("utf-8")
    return f"{DIGEST_PREFIX}{hashlib.sha256(payload).hexdigest()}"


def _view(tool: Any) -> DiscoveredTool:
    """Accept a pinned spec, an already-normalized view, or a live tool object."""
    if isinstance(tool, DiscoveredTool):
        return tool
    if isinstance(tool, PinnedToolSpec):
        return DiscoveredTool(name=tool.name, input_schema=tool.input_schema, output_schema=tool.output_schema)
    return discovered_tool(tool)


# ----------------------------------------------------------------------- diff
@dataclass(frozen=True, slots=True)
class PinnedToolDiff:
    """Every way a discovered tool set can differ from its pin."""

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    renamed: tuple[tuple[str, str], ...] = ()
    changed: tuple[tuple[str, str], ...] = ()
    server_mismatch: tuple[str, ...] = ()

    @property
    def is_compatible(self) -> bool:
        return not (self.added or self.removed or self.changed or self.server_mismatch)

    def as_details(self) -> dict[str, Any]:
        """Sanitizable details for the typed error."""
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "renamed": [f"{before} -> {after}" for before, after in self.renamed],
            "changed": [f"{name}: {reason}" for name, reason in self.changed],
            "server": list(self.server_mismatch),
        }

    def summary(self) -> str:
        """One human sentence naming what drifted."""
        parts: list[str] = []
        if self.added:
            parts.append(f"added {', '.join(self.added)}")
        if self.removed:
            parts.append(f"removed {', '.join(self.removed)}")
        if self.renamed:
            parts.append("renamed " + ", ".join(f"{before} to {after}" for before, after in self.renamed))
        if self.changed:
            parts.append("changed " + ", ".join(f"{name} ({reason})" for name, reason in self.changed))
        if self.server_mismatch:
            parts.append("; ".join(self.server_mismatch))
        return "; ".join(parts) or "no difference"


def _renamed_pairs(
    removed: Sequence[str],
    added: Sequence[str],
    pinned: Mapping[str, PinnedToolSpec],
    found: Mapping[str, DiscoveredTool],
) -> tuple[tuple[str, str], ...]:
    """Pair a removed pin with an added tool that carries the same schemas.

    A rename is still reported as ``removed`` plus ``added`` (it fails closed
    either way); the pairing exists so the error names the likely rename.
    """
    pairs: list[tuple[str, str]] = []
    claimed: set[str] = set()
    for gone in removed:
        pin = pinned[gone]
        for candidate in added:
            if candidate in claimed:
                continue
            view = found[candidate]
            if _canonical(view.input_schema) == _canonical(pin.input_schema) and _canonical(
                view.output_schema
            ) == _canonical(pin.output_schema):
                pairs.append((gone, candidate))
                claimed.add(candidate)
                break
    return tuple(pairs)


def diff_pinned_tools(
    spec: PinnedServerSpec,
    discovered: Iterable[Any],
    *,
    server_info: MCPServerInfo | None = None,
) -> PinnedToolDiff:
    """Compare a discovered tool set against its pin. Any difference is a drift."""
    found = {view.name: view for view in (_view(tool) for tool in discovered) if view.name}
    pinned = {tool.name: tool for tool in spec.tools}

    added = tuple(sorted(set(found) - set(pinned)))
    removed = tuple(sorted(set(pinned) - set(found)))

    changed: list[tuple[str, str]] = []
    for name in sorted(set(pinned) & set(found)):
        pin, view = pinned[name], found[name]
        if _canonical(view.input_schema) != _canonical(pin.input_schema):
            changed.append((name, "argument schema"))
        if _canonical(view.output_schema) != _canonical(pin.output_schema):
            changed.append((name, "result schema"))

    server_mismatch: list[str] = []
    if spec.tools_list_hash is not None:
        actual = tools_list_digest(found.values())
        if actual != spec.tools_list_hash:
            server_mismatch.append(f"tools/list digest {actual} does not match the pinned {spec.tools_list_hash}")
    expected_version = spec.server_version
    if expected_version is not None:
        actual_version = server_info.version if server_info is not None else None
        if actual_version != expected_version:
            reported = actual_version or "no version"
            server_mismatch.append(f"server version {reported} does not match the pinned {expected_version}")
    expected_name = spec.server_name
    if expected_name is not None:
        actual_name = server_info.name if server_info is not None else None
        if actual_name != expected_name:
            reported = actual_name or "no name"
            server_mismatch.append(f"server name {reported} does not match the pinned {expected_name}")

    return PinnedToolDiff(
        added=added,
        removed=removed,
        renamed=_renamed_pairs(removed, added, pinned, found),
        changed=tuple(changed),
        server_mismatch=tuple(server_mismatch),
    )


def enforce_pinned_tools(
    spec: PinnedServerSpec,
    discovered: Iterable[Any],
    *,
    provider: str | None = None,
    server_label: str | None = None,
    server_info: MCPServerInfo | None = None,
) -> PinnedToolDiff:
    """Raise :class:`IncompatibleToolError` unless discovery matches the pin exactly."""
    diff = diff_pinned_tools(spec, discovered, server_info=server_info)
    if diff.is_compatible:
        return diff
    label = server_label or spec.server_url
    msg = f"The MCP server {label} no longer matches the tool contract pinned by this component: {diff.summary()}."
    raise IncompatibleToolError(msg, provider=provider, details=diff.as_details())


# ------------------------------------------------------------------ arguments
def validate_pinned_arguments(
    tool: PinnedToolSpec,
    arguments: Mapping[str, Any],
    *,
    provider: str | None = None,
) -> None:
    """Reject arguments the pinned schema does not declare.

    A discovery-time diff is not enough on its own: ``MCPStructuredTool``
    forwards keys that are absent from the derived args schema, so a widened
    provider tool would still receive drifted arguments at call time.

    Only *unexpected* arguments are treated as an incompatibility.  A missing
    required argument is a caller-side mistake -- an agent routinely omits a
    field -- not evidence that the provider drifted, and no bundle release can
    fix it, so it is deliberately left to the derived args schema, whose
    validation error (``lfx.base.mcp.util._handle_tool_validation_error``) names
    the field and is self-correctable on the next turn.
    """
    schema = tool.input_schema or {}
    properties = schema.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}

    if schema.get("additionalProperties") is True:
        return
    unexpected = sorted(str(key) for key in arguments if key not in properties)
    if not unexpected:
        return

    msg = (
        f"Arguments for the pinned tool {tool.name!r} do not match its pinned schema: "
        f"unexpected argument(s) {', '.join(unexpected)}."
    )
    raise IncompatibleToolError(
        msg,
        provider=provider,
        hint="Reconnect the flow to a bundle release whose pin matches the server, or correct the arguments.",
        details={"tool": tool.name, "unexpected": unexpected},
    )


# ------------------------------------------------------------- manifest bridge
def pinned_spec_from_capabilities(capabilities: Sequence[Any]) -> PinnedServerSpec:
    """Build the runtime pin from the ``substrate == "mcp"`` capabilities of a manifest.

    Every MCP capability that shares one server contributes one pinned tool, so
    the union is the complete tool set the server is allowed to expose: a tool
    outside it is an *added* tool and fails closed.  All contributing
    capabilities must agree on the endpoint, transport, digest, and server
    identity; disagreement is a manifest error, not a runtime decision.

    A declared ``tools_list_hash`` must also be the digest of exactly these
    tools.  Computing it over a wider recording than the manifest pins is an easy
    authoring mistake, and it would otherwise surface at every load as two
    stacked runtime complaints (an added tool plus a digest mismatch) that read
    like provider drift; checked here it is a bundle error at build time.
    """
    mcp_capabilities = [cap for cap in capabilities if getattr(cap, "substrate", None) == "mcp"]
    if not mcp_capabilities:
        msg = "No capability with substrate 'mcp' was supplied, so there is nothing to pin"
        raise ValueError(msg)

    tools: dict[str, PinnedToolSpec] = {}
    server: dict[str, Any] = {}
    for capability in mcp_capabilities:
        pin = getattr(capability, "mcp_pin", None)
        tool_name = getattr(capability, "mcp_tool", None)
        if pin is None or not tool_name:
            msg = f"Capability {getattr(capability, 'id', '<unknown>')!r} has substrate 'mcp' without a complete pin"
            raise ValueError(msg)
        identity = {
            "server_url": pin.server_url,
            "transport": pin.transport,
            "tools_list_hash": pin.tools_list_hash,
            "server_name": pin.server_name,
            "server_version": pin.server_version,
        }
        if not server:
            server = identity
        elif server != identity:
            msg = (
                "Pinned MCP capabilities that share a component must pin the same server endpoint, transport, "
                "digest, and server identity"
            )
            raise ValueError(msg)
        candidate = PinnedToolSpec(
            name=tool_name,
            input_schema=dict(pin.input_schema),
            output_schema=dict(pin.output_schema) if pin.output_schema is not None else None,
        )
        existing = tools.get(tool_name)
        if existing is not None and existing != candidate:
            msg = f"Two pinned capabilities map to the MCP tool {tool_name!r} with different schemas"
            raise ValueError(msg)
        tools[tool_name] = candidate

    spec = PinnedServerSpec(tools=tuple(tools.values()), **server)
    declared = spec.tools_list_hash
    if declared is not None and declared != spec.digest():
        msg = (
            f"The pinned tools_list_hash {declared} is not the digest of the pinned tools "
            f"({spec.digest()}). Compute it over exactly the tools these capabilities pin."
        )
        raise ValueError(msg)
    return spec
