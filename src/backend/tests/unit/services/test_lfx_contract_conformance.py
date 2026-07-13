"""Tests that concrete Langflow services conform to LFX contracts."""

from __future__ import annotations

import pytest
from langflow.services.base import Service as LangflowService
from langflow.services.factory import ServiceFactory as LangflowServiceFactory
from langflow.services.schema import ServiceType as LangflowServiceType
from langflow_services.factory import ServiceFactory as PackageServiceFactory
from lfx.services.base import Service as LfxService
from lfx.services.factory import ServiceFactory as LfxServiceFactory
from lfx.services.schema import ServiceType as LfxServiceType


def test_service_base_identity() -> None:
    assert LangflowService is LfxService


def test_service_type_identity() -> None:
    assert LangflowServiceType is LfxServiceType
    assert LangflowServiceType.JOB_SERVICE is LfxServiceType.JOB_SERVICE
    assert LangflowServiceType.MEMORY_BASE_SERVICE is LfxServiceType.MEMORY_BASE_SERVICE


def test_concrete_factory_subclasses_lfx_factory() -> None:
    assert issubclass(PackageServiceFactory, LfxServiceFactory)
    assert LangflowServiceFactory is PackageServiceFactory


def test_state_service_is_lfx_service_subclass() -> None:
    from langflow_services.state.service import InMemoryStateService

    assert issubclass(InMemoryStateService, LfxService)


@pytest.mark.parametrize(
    ("services_path", "langflow_path"),
    [
        ("langflow_services.state.factory", "langflow.services.state.factory"),
        ("langflow_services.auth.factory", "langflow.services.auth.factory"),
        ("langflow_services.database.factory", "langflow.services.database.factory"),
        ("langflow_services.cache.factory", "langflow.services.cache.factory"),
    ],
)
def test_factory_shim_identity(services_path: str, langflow_path: str) -> None:
    import importlib

    svc = importlib.import_module(services_path)
    host = importlib.import_module(langflow_path)
    # Compare primary *Factory class on each module
    svc_factory = next(v for k, v in vars(svc).items() if k.endswith("Factory") and isinstance(v, type))
    host_factory = next(v for k, v in vars(host).items() if k.endswith("Factory") and isinstance(v, type))
    assert svc_factory is host_factory
