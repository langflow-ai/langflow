"""Trigger settings use the same human labels as the component palette."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.triggers import source_arming
from langflow.services.triggers.providers.servicenow.runtime import PROVIDER
from lfx_servicenow.components import servicenow as components


def test_runtime_trigger_labels_match_the_palette():
    for kind in PROVIDER.kinds:
        assert kind.display_name == getattr(components, kind.component).display_name


@pytest.mark.parametrize("kind", [spec.kind for spec in PROVIDER.kinds])
async def test_hosted_trigger_refusal_explains_supported_deployment(monkeypatch, kind):
    connection = SimpleNamespace(id=uuid4())

    class Session:
        async def exec(self, _query):
            return SimpleNamespace(first=lambda: connection)

    monkeypatch.setattr(source_arming, "deployment_context", lambda: "hosted")
    monkeypatch.setattr(source_arming, "get_kind", lambda value: next(s for s in PROVIDER.kinds if s.kind == value))
    monkeypatch.setattr(
        source_arming,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(trigger_ingress_enabled=False)),
    )

    with pytest.raises(
        ValueError,
        match=(
            r"ServiceNow triggers are not supported on hosted Langflow\. "
            r"They require self-managed Langflow with a running listener\."
        ),
    ):
        await source_arming.resolve_arming(
            Session(), kind=kind, owner_id=uuid4(), config={"connection": "servicenow/work", "delivery_mode": "poll"}
        )
