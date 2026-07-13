"""Regression coverage for services extraction parity fixes."""

from __future__ import annotations

import importlib
import pickle
from pathlib import Path

import orjson
import pytest


def test_session_orjson_dumps_indent_parity() -> None:
    from langflow_services.session.utils import orjson_dumps

    payload = {"b": 2, "a": 1}
    indented = orjson_dumps(payload, sort_keys=True, indent_2=True)
    compact = orjson_dumps(payload, sort_keys=True, indent_2=False)

    assert indented == orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode()
    assert compact == orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode()
    assert indented != compact


def test_services_deps_propagates_factory_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow_services import deps
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    manager = get_service_manager()

    def boom(*_args, **_kwargs):
        msg = "factory boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(manager, "get", boom)
    monkeypatch.setattr(manager, "are_factories_registered", lambda: True)

    with pytest.raises(RuntimeError, match="factory boom"):
        deps.get_service(ServiceType.CACHE_SERVICE)


def test_exception_pickle_roundtrip_preserves_langflow_module() -> None:
    from langflow.exceptions.api import WorkflowExecutionError, WorkflowResourceError

    for exc_cls in (WorkflowExecutionError, WorkflowResourceError):
        restored = pickle.loads(pickle.dumps(exc_cls("boom")))  # noqa: S301
        assert type(restored) is exc_cls
        assert restored.__class__.__module__ == "langflow.exceptions.api"


def test_orm_identity_across_import_paths() -> None:
    from langflow.services.database.models.flow import Flow as HostFlow
    from langflow.services.database.models.user import User as HostUser
    from langflow_services.database import models as services_models
    from lfx.services.database.models.flow import Flow as LfxFlow
    from lfx.services.database.models.user import User as LfxUser

    assert HostFlow is LfxFlow
    assert HostUser is LfxUser
    assert services_models.Flow is LfxFlow
    assert services_models.User is LfxUser


def test_all_concrete_factory_shims_preserve_identity() -> None:
    services_root = Path(__file__).resolve().parents[4] / "langflow-services" / "src" / "langflow_services"
    factory_modules = sorted(
        path.parent.relative_to(services_root).as_posix().replace("/", ".")
        for path in services_root.rglob("factory.py")
        if path.parent != services_root
    )
    assert factory_modules

    for relative in factory_modules:
        services_path = f"langflow_services.{relative}.factory"
        langflow_path = f"langflow.services.{relative}.factory"
        svc = importlib.import_module(services_path)
        host = importlib.import_module(langflow_path)
        svc_factories = [v for k, v in vars(svc).items() if k.endswith("Factory") and isinstance(v, type)]
        host_factories = [v for k, v in vars(host).items() if k.endswith("Factory") and isinstance(v, type)]
        assert svc_factories, f"no Factory class in {services_path}"
        assert set(svc_factories) == set(host_factories)


def test_get_auth_service_uses_auth_factory_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow_services import deps
    from langflow_services.auth.factory import AuthServiceFactory

    captured: dict[str, object] = {}

    def fake_get_service(service_type, default=None):
        captured["service_type"] = service_type
        captured["default"] = default
        return "auth"

    monkeypatch.setattr(deps, "get_service", fake_get_service)
    assert deps.get_auth_service() == "auth"
    assert isinstance(captured["default"], AuthServiceFactory)
