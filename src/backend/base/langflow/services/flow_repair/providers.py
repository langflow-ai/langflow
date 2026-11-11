"""Prove provider identities from trusted declarations and inert saved values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lfx.base.models.provider_registry import provider_id_for
from lfx.base.models.provider_selection import (
    CANONICAL_MODEL_INPUT,
    CUSTOM_MODEL_PROVIDER,
    LEGACY_MODEL_PROVIDER_INPUT,
    MODEL_PROVIDER_OVERRIDE_INPUT,
    raw_model_provider_names,
)
from lfx.inputs.input_mixin import FieldTypes
from lfx.inputs.inputs import ModelInput
from lfx.upgrade.checker import _connected_fields_by_node, _target_handle, flow_node_id


class ProviderSelectionUnverifiableError(ValueError):
    """A provider identity needs runtime input, unsupported metadata, or discovery."""


def _unverifiable() -> ProviderSelectionUnverifiableError:
    return ProviderSelectionUnverifiableError("The selected model provider could not be verified")


def _known_provider(name: object) -> str:
    if not isinstance(name, str) or not (provider := provider_id_for(name.strip())):
        raise _unverifiable()
    return provider


def _saved_parameters(
    declared: Mapping[str, Any], saved: Mapping[str, Any], names: list[str], connected: set[str]
) -> dict[str, Any]:
    relevant = set(names)
    if CANONICAL_MODEL_INPUT in names and (
        MODEL_PROVIDER_OVERRIDE_INPUT in declared or MODEL_PROVIDER_OVERRIDE_INPUT in saved
    ):
        relevant.add(MODEL_PROVIDER_OVERRIDE_INPUT)
    if LEGACY_MODEL_PROVIDER_INPUT in declared or LEGACY_MODEL_PROVIDER_INPUT in saved:
        relevant.add(LEGACY_MODEL_PROVIDER_INPUT)
    parameters = {}
    for name in relevant:
        field = saved.get(name, declared.get(name))
        if not isinstance(field, Mapping) or field.get("load_from_db") or name in connected:
            raise _unverifiable()
        parameters[name] = field.get("value")
    override = parameters.get(MODEL_PROVIDER_OVERRIDE_INPUT)
    if override not in (None, ""):
        if MODEL_PROVIDER_OVERRIDE_INPUT not in declared or not isinstance(override, str):
            raise _unverifiable()
        if override.strip():
            _known_provider(override)
    legacy = parameters.get(LEGACY_MODEL_PROVIDER_INPUT)
    if legacy not in (None, ""):
        if legacy == CUSTOM_MODEL_PROVIDER:
            raise _unverifiable()
        _known_provider(legacy)
    for name in names:
        selection = parameters.get(name)
        if selection in (None, "", []):
            if declared[name].get("required") and not legacy:
                raise _unverifiable()
            continue
        values = [selection] if isinstance(selection, Mapping) else selection
        if not isinstance(values, list) or not values or not all(isinstance(value, Mapping) for value in values):
            raise _unverifiable()
        provider = (
            override
            if name == CANONICAL_MODEL_INPUT and isinstance(override, str) and override.strip()
            else values[0].get("provider")
        )
        _known_provider(provider)
    return parameters


def _nested_edges(node: Mapping[str, Any], edges: list[dict]) -> list[dict]:
    projected = []
    template = node["data"]["node"].get("template", {})
    for edge in edges:
        handle = _target_handle(edge) if edge.get("target") == flow_node_id(node) else None
        if handle is None:
            continue
        field = template.get(handle.get("fieldName"))
        proxy = handle.get("proxy") or (field.get("proxy") if isinstance(field, Mapping) else None)
        if isinstance(proxy, Mapping):
            projected.append({"target": proxy.get("id"), "data": {"targetHandle": {"fieldName": proxy.get("field")}}})
    return projected


def component_provider_ids(
    graph: dict, registry: Mapping[str, dict], inherited_edges: list[dict] | None = None
) -> set[str]:
    providers = set()
    edges = [*graph.get("edges", []), *(inherited_edges or [])]
    connected = _connected_fields_by_node(edges) or {}
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        info = data.get("node") or {}
        entry = registry.get(data.get("type"), {})
        metadata = entry.get("metadata") or {}
        declared, saved = entry.get("template") or {}, info.get("template") or {}
        if metadata.get("model_provider_policy_mode") != "none":
            standalone = metadata.get("model_provider_id")
            if standalone:
                providers.add(_known_provider(standalone))
            names = [
                name
                for name, field in declared.items()
                if isinstance(field, Mapping)
                and (field.get("_input_type") == ModelInput.__name__ or field.get("type") == FieldTypes.MODEL)
            ]
            parameters = _saved_parameters(declared, saved, names, connected.get(flow_node_id(node), set()))
            selections = raw_model_provider_names(names, parameters)
            if metadata.get("model_provider_policy_mode") == "delegate" and not selections:
                raise _unverifiable()
            providers.update(_known_provider(name) for name in selections)
        nested = info.get("flow", {}).get("data")
        if nested:
            providers.update(component_provider_ids(nested, registry, _nested_edges(node, edges)))
    return providers
