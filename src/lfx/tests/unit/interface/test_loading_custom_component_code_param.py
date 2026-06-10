"""Regression tests for stripping the reserved ``code`` param before ``build()`` (#8610 / PR #12712).

Reusing a custom component could leave ``code`` in the params dict; ``build(**params)`` then
raised ``TypeError: build() got an unexpected keyword argument 'code'`` for components whose
``build`` method does not accept ``**kwargs``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from lfx.interface.initialize import loading


class _StrictBuildComponentSync:
    """Minimal stand-in for a custom component with a strict ``build`` signature (no ``**kwargs``)."""

    repr_value = None

    def __init__(self) -> None:
        self._vertex = SimpleNamespace(outputs=[{"name": "output"}])

    def get_vertex(self):
        return self._vertex

    def build(self):
        return "sync-ok"

    def custom_repr(self):
        return "repr"

    def set_artifacts(self, artifacts) -> None:
        self._artifacts = artifacts

    def set_results(self, results) -> None:
        self._results = results


class _StrictBuildComponentAsync:
    repr_value = None

    def __init__(self) -> None:
        self._vertex = SimpleNamespace(outputs=[{"name": "output"}])

    def get_vertex(self):
        return self._vertex

    async def build(self):
        return "async-ok"

    def custom_repr(self):
        return "repr"

    def set_artifacts(self, artifacts) -> None:
        self._artifacts = artifacts

    def set_results(self, results) -> None:
        self._results = results


@pytest.mark.parametrize(
    "params_factory",
    [
        lambda: {"code": "not executed"},
        dict,
        lambda: {"code": None},
    ],
)
async def test_build_custom_component_does_not_pass_code_to_strict_build(params_factory):
    params = params_factory()
    component = _StrictBuildComponentSync()

    _, build_result, _ = await loading.build_custom_component(params, component)

    assert build_result == "sync-ok"
    assert "code" not in params


async def test_build_custom_component_async_strict_build_strips_code():
    params = {"code": "ignored"}
    component = _StrictBuildComponentAsync()

    _, build_result, _ = await loading.build_custom_component(params, component)

    assert build_result == "async-ok"
    assert "code" not in params


def test_get_params_copy_includes_code_vertex_params():
    """``get_params`` is used on reuse; callers strip ``code`` before ``build()``."""
    vertex_params = {"code": "x", "other": 1}
    out = loading.get_params(vertex_params)
    assert out["code"] == "x"
    assert out is not vertex_params


def test_reuse_path_custom_params_pop_code_none_safe():
    """Popping ``code`` must not fail when the key is absent (matches vertex / loading behavior)."""
    custom_params = loading.get_params({"foo": 1})
    custom_params.pop("code", None)
    assert custom_params == {"foo": 1}
