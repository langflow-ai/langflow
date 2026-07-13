"""Host bootstrap / hook contracts for the extracted services package."""

from __future__ import annotations

import copy

import pytest
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType


@pytest.fixture(autouse=True)
def _reset_service_manager_and_providers():
    from langflow_services.auth import service as auth_service
    from langflow_services.database import factory as database_factory
    from langflow_services.memory_base import kb_hooks
    from langflow_services.providers import _CRUD, _HOOKS

    manager = get_service_manager()
    manager.services.clear()
    manager.factories.clear()
    manager.service_classes.clear()
    manager.factory_registered = False
    manager._plugins_discovered = False

    crud_snapshot = copy.copy(_CRUD)
    hooks_snapshot = copy.copy(_HOOKS)
    alembic_snapshot = database_factory._alembic_path_provider
    jit_hook_snapshot = auth_service._jit_user_defaults_hook
    flow_hook_snapshot = auth_service._get_user_by_flow_hook
    kb_snapshot = (
        kb_hooks._KB_STORAGE_HELPER,
        kb_hooks._KB_ANALYSIS_HELPER,
        kb_hooks._KB_INGESTION_HELPER,
        kb_hooks._CHUNK_TEXT_FOR_INGESTION,
    )
    _CRUD.clear()
    _HOOKS.clear()
    database_factory.set_alembic_path_provider(None)
    auth_service._jit_user_defaults_hook = None
    auth_service._get_user_by_flow_hook = None
    kb_hooks._KB_STORAGE_HELPER = None
    kb_hooks._KB_ANALYSIS_HELPER = None
    kb_hooks._KB_INGESTION_HELPER = None
    kb_hooks._CHUNK_TEXT_FOR_INGESTION = None

    yield

    _CRUD.clear()
    _HOOKS.clear()
    _CRUD.update(crud_snapshot)
    _HOOKS.update(hooks_snapshot)
    database_factory.set_alembic_path_provider(alembic_snapshot)
    auth_service._jit_user_defaults_hook = jit_hook_snapshot
    auth_service._get_user_by_flow_hook = flow_hook_snapshot
    (
        kb_hooks._KB_STORAGE_HELPER,
        kb_hooks._KB_ANALYSIS_HELPER,
        kb_hooks._KB_INGESTION_HELPER,
        kb_hooks._CHUNK_TEXT_FOR_INGESTION,
    ) = kb_snapshot

    manager.services.clear()
    manager.factories.clear()
    manager.service_classes.clear()
    manager.factory_registered = False
    manager._plugins_discovered = False


def test_services_bootstrap_without_host_hooks_fails_database_factory() -> None:
    from langflow_services.bootstrap import register_all_service_factories
    from langflow_services.database.factory import DatabaseServiceFactory
    from langflow_services.providers import get_crud

    register_all_service_factories()
    factory = DatabaseServiceFactory()
    settings = get_service_manager().get(ServiceType.SETTINGS_SERVICE)

    with pytest.raises(RuntimeError, match="CRUD provider"):
        get_crud("user")

    with pytest.raises(RuntimeError, match="Alembic path provider is not registered"):
        factory.create(settings)


def test_langflow_register_all_service_factories_registers_host_hooks() -> None:
    from langflow.services.utils import register_all_service_factories
    from langflow_services.providers import get_crud, get_version_info, require_hook

    register_all_service_factories()

    assert get_crud("user") is not None
    assert get_crud("api_key") is not None
    assert get_crud("jobs") is not None
    assert require_hook("clean_authz_audit_log") is not None
    assert require_hook("get_version_info") is not None
    assert require_hook("teardown_superuser") is not None
    version_info = get_version_info()
    assert version_info["package"].lower() != "lfx"
    assert version_info["version"] != "0.1.0" or "langflow" in version_info["package"].lower()

    manager = get_service_manager()
    assert ServiceType.AUTH_SERVICE.value in manager.factories or ServiceType.AUTH_SERVICE in manager.service_classes
    assert manager.are_factories_registered()


def test_memory_base_and_jobs_remain_lazy_after_bootstrap() -> None:
    from langflow.services.utils import register_all_service_factories

    register_all_service_factories()
    manager = get_service_manager()
    assert ServiceType.MEMORY_BASE_SERVICE.value not in manager.factories
    assert ServiceType.JOB_SERVICE.value not in manager.factories


def test_audit_cleanup_module_exposes_clean_authz_audit_log() -> None:
    from langflow.services.task import audit_cleanup

    assert callable(audit_cleanup.clean_authz_audit_log)


def test_missing_version_hook_raises() -> None:
    from langflow_services.providers import get_version_info

    with pytest.raises(RuntimeError, match="get_version_info"):
        get_version_info()
