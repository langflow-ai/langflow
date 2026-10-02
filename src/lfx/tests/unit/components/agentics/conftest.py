"""Shared fixtures for the Agentics component tests.

agentics-py cannot be installed alongside lfx (no release is compatible with lfx's dependency
floors; see ``ERROR_AGENTICS_NOT_INSTALLED`` in ``lfx.components.agentics.constants``). Rather than
skipping, these tests run the real component code against an in-memory stand-in for the slice of
the agentics-py 0.3.6 API the components call, with the LLM transduction scripted by each test.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest
from lfx.components.agentics import agenerate_component, amap_component, areduce_component
from pydantic import BaseModel, create_model

if TYPE_CHECKING:
    from collections.abc import Callable

# agentics-py's default AG.instructions; the aMap component appends user instructions to it.
_DEFAULT_INSTRUCTIONS = "Generate an object of the specified type from the following input."


def _field_definitions(atype: type[BaseModel]) -> dict[str, Any]:
    return {name: (info.annotation, None) for name, info in atype.model_fields.items()}


@dataclass
class FakeAgenticsSDK:
    """Records what a component asked the SDK to do and scripts what the "LLM" returns."""

    transduce: Callable[[FakeAG, FakeAG], list[BaseModel]] | None = None
    generate: Callable[[type[BaseModel], int], list[BaseModel] | None] | None = None
    transductions: list[tuple[FakeAG, FakeAG]] = field(default_factory=list)
    generate_calls: list[dict[str, Any]] = field(default_factory=list)


class FakeAG:
    """Stand-in for ``agentics.AG`` that mirrors the agentics-py 0.3.6 behaviour the components use."""

    sdk: FakeAgenticsSDK  # bound per test by the ``fake_agentics`` fixture

    def __init__(
        self,
        atype: type[BaseModel] | None = None,
        states: list[BaseModel] | None = None,
        transduction_type: str | None = None,
        llm: Any = None,
        instructions: str = _DEFAULT_INSTRUCTIONS,
        areduce_batch_size: int | None = None,
    ) -> None:
        self.atype = atype
        self.states = list(states or [])
        self.transduction_type = transduction_type
        self.llm = llm
        self.instructions = instructions
        self.areduce_batch_size = areduce_batch_size
        self.prompt_template: str | None = None

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> FakeAG:
        atype = create_model("AType", **{str(column): (Any, None) for column in df.columns})
        return cls(atype=atype, states=[atype(**row) for row in df.to_dict(orient="records")])

    def __iter__(self):
        return iter(self.states)

    def subset_atype(self, fields: set[str]) -> type[BaseModel]:
        kept = {name: spec for name, spec in _field_definitions(self.atype).items() if name in fields}
        return create_model("Subset", **kept)

    def rebind_atype(self, atype: type[BaseModel]) -> FakeAG:
        names = set(atype.model_fields)
        return FakeAG(atype=atype, states=[atype(**state.model_dump(include=names)) for state in self.states])

    def merge_states(self, other: FakeAG) -> FakeAG:
        # Like agentics-py, the merged schema dedupes field names, but each merged state is built from both
        # sides' values, so a field present on both sides is passed twice ("got multiple values for keyword
        # argument ..."). That TypeError is what aMap's overlap dedup must avoid.
        merged = create_model("Merged", **{**_field_definitions(self.atype), **_field_definitions(other.atype)})
        states = [
            merged(**mine.model_dump(), **theirs.model_dump())
            for mine, theirs in zip(self.states, other.states, strict=True)
        ]
        return FakeAG(atype=merged, states=states)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([state.model_dump() for state in self.states])

    def __lshift__(self, source: FakeAG):
        return self._transduce(source)

    async def _transduce(self, source: FakeAG) -> FakeAG:
        self.sdk.transductions.append((self, source))
        return FakeAG(atype=self.atype, states=self.sdk.transduce(self, source))


def create_pydantic_model(fields: list[tuple[str, str, str, bool]], name: str = "AType") -> type[BaseModel]:
    """Stand-in for ``agentics.core.atype.create_pydantic_model``: every field is an optional ``Any``.

    That matches what agentics-py 0.3.6 builds from ``build_schema_fields`` output today. The SDK reads
    ``(name, type, description, required)`` but ``build_schema_fields`` emits ``(name, description, type,
    required)``, so the type lookup always misses. It's a pre-existing bug; these tests don't cover field typing.
    """
    return create_model(name, **{field_name: (Any, None) for field_name, *_ in fields})


@pytest.fixture
def fake_agentics(monkeypatch) -> FakeAgenticsSDK:
    """Install the stand-in SDK under the ``agentics`` module names the components import."""
    sdk = FakeAgenticsSDK()
    monkeypatch.setattr(FakeAG, "sdk", sdk, raising=False)

    async def generate_prototypical_instances(atype, n_instances, llm=None, instructions=None):
        sdk.generate_calls.append(
            {"atype": atype, "n_instances": n_instances, "llm": llm, "instructions": instructions}
        )
        return sdk.generate(atype, n_instances)

    modules = {
        "agentics": {"AG": FakeAG},
        "agentics.core": {},
        "agentics.core.atype": {"create_pydantic_model": create_pydantic_model},
        "agentics.core.transducible_functions": {"generate_prototypical_instances": generate_prototypical_instances},
    }
    for name, attributes in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    return sdk


@pytest.fixture
def fake_llm(monkeypatch) -> object:
    """Bypass provider and credential resolution (and the crewai import behind it); it isn't under test here."""
    llm = object()
    for module in (agenerate_component, amap_component, areduce_component):
        monkeypatch.setattr(module, "prepare_llm_from_component", lambda _component: llm)
    return llm
