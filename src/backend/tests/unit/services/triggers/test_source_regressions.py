"""Regressions for production source entry points and thin notifications."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langflow.services.triggers.ingress.verifiers import _graph_identity
from langflow.services.triggers.listeners.adapters import ProviderSourcePollAdapter
from lfx.custom.utils import create_component_template


async def test_registered_source_adapter_can_poll_an_empty_connection():
    context = SimpleNamespace(triggers=[], stopping=asyncio.Event())
    assert await ProviderSourcePollAdapter(interval_s=30).poll(context) == 0


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_source_catalog_preserves_each_components_identity_and_fields(provider):
    root = Path(__file__).resolve().parents[6]
    directory = root / f"src/bundles/{provider}/src/lfx_{provider}/components/{provider}"
    package_name = f"_source_catalog_{provider}"
    # Load a package without importing unrelated optional provider components.
    package = type(sys)(package_name)
    package.__path__ = [str(directory)]
    sys.modules[package_name] = package
    name = f"{package_name}.source_triggers"
    spec = importlib.util.spec_from_file_location(name, directory / "source_triggers.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        classes = [
            value
            for key, value in vars(module).items()
            if key.endswith("TriggerComponent") and not key.startswith("Base")
        ]
        assert len(classes) == 3
        for component_class in classes:
            component = component_class()
            template, _ = create_component_template(
                component_extractor=component, module_name=component_class.__module__
            )
            assert template["display_name"] == component.display_name
            assert {field.name for field in component.inputs} <= template["template"].keys()
    finally:
        for key in list(sys.modules):
            if key == package_name or key.startswith(package_name + "."):
                sys.modules.pop(key)


def test_unversioned_graph_root_notification_has_no_permanent_identity():
    assert not _graph_identity({"subscriptionId": "watch", "resource": "drives/one/root", "changeType": "updated"})


def test_graph_notification_id_distinguishes_unversioned_updates():
    notification = {"subscriptionId": "watch", "resource": "drives/one/root", "changeType": "updated"}
    assert _graph_identity({**notification, "id": "one"}) != _graph_identity({**notification, "id": "two"})
