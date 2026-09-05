"""Pytest fixtures for the lfx-microsoft bundle tests.

The helpers live in :mod:`microsoft_testkit` so test modules can import them by
name; pytest puts this directory on ``sys.path`` under the default prepend
import mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.services.connection.base import BaseConnectionResolverService
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from microsoft_testkit import RecordingResolver, credential

if TYPE_CHECKING:
    from lfx.integrations.models import ResolvedCredential


@pytest.fixture
def resolver_factory():
    """Register a resolver in the service manager for the duration of a test."""
    manager = get_service_manager()
    previous = manager.services.get(ServiceType.CONNECTION_RESOLVER_SERVICE)

    def _register(*credentials: ResolvedCredential) -> RecordingResolver:
        resolver = RecordingResolver(list(credentials) or [credential()])
        manager.services[ServiceType.CONNECTION_RESOLVER_SERVICE] = resolver
        return resolver

    yield _register

    if previous is None:
        manager.services.pop(ServiceType.CONNECTION_RESOLVER_SERVICE, None)
    else:
        manager.services[ServiceType.CONNECTION_RESOLVER_SERVICE] = previous


@pytest.fixture
def unset_resolver():
    """Remove any registered resolver so the env fallback is selected."""
    manager = get_service_manager()
    previous = manager.services.get(ServiceType.CONNECTION_RESOLVER_SERVICE)
    manager.services.pop(ServiceType.CONNECTION_RESOLVER_SERVICE, None)
    yield manager
    if previous is not None:
        manager.services[ServiceType.CONNECTION_RESOLVER_SERVICE] = previous
    else:
        manager.services.pop(ServiceType.CONNECTION_RESOLVER_SERVICE, None)


__all__ = ["BaseConnectionResolverService", "resolver_factory", "unset_resolver"]
