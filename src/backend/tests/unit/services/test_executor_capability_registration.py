"""Regression test for the executor/capability service-factory wiring.

``ExecutorService`` declares a hard dependency on ``CAPABILITY_SERVICE``. The
langflow backend must register ``CapabilityServiceFactory`` alongside
``ExecutorServiceFactory`` or the service manager cannot resolve the dependency
when it builds ``ExecutorService`` -- which made every flow run 500 with
``NoFactoryRegisteredError`` / "ExecutorService is not available".
"""

from __future__ import annotations

from langflow.services.utils import register_all_service_factories
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType


def test_executor_dependency_factories_are_registered():
    register_all_service_factories()
    service_manager = get_service_manager()

    executor_factory = service_manager.factories.get(ServiceType.EXECUTOR_SERVICE.value)
    assert executor_factory is not None, "ExecutorServiceFactory is not registered"

    for dependency in executor_factory.dependencies:
        assert dependency.value in service_manager.factories, (
            f"ExecutorService depends on {dependency.value}, but no factory is registered for it; "
            f"the service manager cannot build ExecutorService."
        )

    # The specific dependency that regressed.
    assert ServiceType.CAPABILITY_SERVICE.value in service_manager.factories
