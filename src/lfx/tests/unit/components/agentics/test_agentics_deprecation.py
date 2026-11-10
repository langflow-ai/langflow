"""The Agentics components are deprecated because agentics-py can't be installed alongside Langflow."""

from __future__ import annotations

import sys

import pytest
from lfx.components.agentics.agenerate_component import AgenerateComponent
from lfx.components.agentics.amap_component import AMapComponent
from lfx.components.agentics.areduce_component import AreduceComponent
from lfx.components.agentics.constants import AGENTICS_DOCS_URL, ERROR_AGENTICS_NOT_INSTALLED
from lfx.schema.dataframe import DataFrame

_SCHEMA = [{"name": "summary", "description": "Summary", "type": "str", "multiple": False}]

_COMPONENT_OUTPUTS = [
    pytest.param(AMapComponent, "aMap", id="aMap"),
    pytest.param(AreduceComponent, "aReduce", id="aReduce"),
    pytest.param(AgenerateComponent, "aGenerate", id="aGenerate"),
]


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [AMapComponent, AreduceComponent, AgenerateComponent])
def test_should_be_legacy_so_new_flows_do_not_offer_it(component_class):
    assert getattr(component_class, "legacy", False) is True
    assert component_class().to_frontend_node()["data"]["node"]["legacy"] is True


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(("component_class", "method"), _COMPONENT_OUTPUTS)
async def test_should_explain_the_missing_sdk_without_suggesting_an_install(monkeypatch, component_class, method):
    # A None entry makes ``import agentics`` fail even on a machine where the SDK happens to be installed.
    monkeypatch.setitem(sys.modules, "agentics", None)
    component = component_class(_id=method)
    component.set(source=DataFrame([{"text": "hello"}]), schema=_SCHEMA, instructions="")

    with pytest.raises(ImportError) as exc_info:
        await getattr(component, method)()

    assert str(exc_info.value) == ERROR_AGENTICS_NOT_INSTALLED
    assert isinstance(exc_info.value.__cause__, ImportError)


@pytest.mark.unit
def test_error_message_warns_against_installing_agentics_py_and_links_the_docs():
    # Installing agentics-py into a Langflow environment downgrades langchain-core and breaks Langflow,
    # so the message must steer users away from it rather than toward it.
    assert "Don't install it" in ERROR_AGENTICS_NOT_INSTALLED
    assert "`pip install agentics-py`" in ERROR_AGENTICS_NOT_INSTALLED
    assert "`uv pip install agentics-py`" in ERROR_AGENTICS_NOT_INSTALLED
    assert "Please install" not in ERROR_AGENTICS_NOT_INSTALLED
    assert AGENTICS_DOCS_URL in ERROR_AGENTICS_NOT_INSTALLED
