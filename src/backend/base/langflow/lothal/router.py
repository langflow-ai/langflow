"""Phase router — `process_turn` dispatches a turn to its phase engine (Story 0.3).

Epic 0's last seam. The chat endpoint hands a turn to `process_turn(phase, ...)`;
the router looks up the engine registered for that phase and returns its
`LLMResponse`. Engines plug in through `@register_engine` (the open/closed seam,
mirroring the LLM provider registry in `llm/registry.py`): adding the engine for
a phase never touches `process_turn`.

`process_turn` is provider-agnostic and output-shape-agnostic — each engine
decides whether it emits clarification `suggestions` or a `next_phase`
transition, and the chat endpoint reads the same `LLMResponse` either way. Built-in
engines live in `langflow.lothal.engines` and self-register on import (Epic 1+);
none ship in Epic 0, so the router is pure infrastructure until then.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message


@dataclass
class LLMResponse:
    """One phase engine's reply for a turn — the single shape the chat endpoint reads.

    `text` is the assistant message and is always present. `suggestions` are
    clarification chips and stay `[]` for phases that don't offer them.
    `next_phase` is the transition target, or `None` when the turn keeps the
    project in its current phase.

    `diagram_d2` is the turn's diagram artifact when it touches the diagram: **D2
    source text** (the Epic D artifact, persisted to `lothal_project.diagram_d2`),
    and `None` otherwise. `artifacts` is the turn's full artifact file-map —
    `{path: content}`, e.g. `{"adr.md": ..., "diagrams/context.d2": ...}` — when a
    stage rewrites it (the ARCHITECTURE engine, Epic E.3, persisted to
    `lothal_project.artifacts`), and `None` for turns that don't touch it. The
    architecture engine sets both: `artifacts` is the whole map and `diagram_d2`
    mirrors `diagrams/sequence.d2` so the single-diagram read/approve flow keeps
    working until the multi-diagram read endpoints land (E.4). `warning` is an
    optional coherence warning raised when an edited/generated D2 contradicts the
    PRD (Epic D.10); the chat endpoint stores it as a second ASSISTANT message,
    and it is `None` when everything is coherent (or for phases that don't
    validate). The engine itself never writes the DB.
    """

    text: str
    suggestions: list[str] = field(default_factory=list)
    next_phase: str | None = None
    diagram_d2: str | None = None
    artifacts: dict[str, str] | None = None
    warning: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            msg = "LLMResponse.text must be a non-empty string."
            raise ValueError(msg)
        if not isinstance(self.suggestions, list) or not all(isinstance(s, str) for s in self.suggestions):
            msg = "LLMResponse.suggestions must be a list of strings."
            raise ValueError(msg)
        if self.next_phase is not None and not isinstance(self.next_phase, str):
            msg = "LLMResponse.next_phase must be a string or None."
            raise ValueError(msg)
        if self.diagram_d2 is not None and not isinstance(self.diagram_d2, str):
            msg = "LLMResponse.diagram_d2 must be a string or None."
            raise ValueError(msg)
        if self.artifacts is not None and (
            not isinstance(self.artifacts, dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.artifacts.items())
        ):
            msg = "LLMResponse.artifacts must be a dict mapping str paths to str contents, or None."
            raise ValueError(msg)
        if self.warning is not None and (not isinstance(self.warning, str) or not self.warning.strip()):
            msg = "LLMResponse.warning must be a non-empty string or None."
            raise ValueError(msg)


class PhaseEngine(ABC):
    """The logic for one phase `process_turn` can route to.

    A subclass sets a unique `phase` (a `ProjectPhase` value, e.g.
    `"CLARIFICATION"`) and turns a turn into an `LLMResponse` in `process`.
    Decorate it with `@register_engine` to make it selectable for its phase.
    """

    phase: ClassVar[str]

    @abstractmethod
    async def process(
        self,
        history: list[Message],
        user_message: str,
        *,
        prd: str | None = None,
        current_d2: str | None = None,
        artifacts: dict[str, str] | None = None,
        target_artifact: str | None = None,
    ) -> LLMResponse:
        """Handle one turn and return the assistant reply for it.

        `history` is the project's prior turns (oldest first, the ORM `Message`
        rows); `user_message` is the turn the user just sent. Engines typically
        call `build_messages` (Story 0.2) then `call_llm` (Story 0.1).

        `prd`, `current_d2`, `artifacts`, and `target_artifact` are the project
        state the chat endpoint threads through for engines that edit existing
        state: the synthesised PRD, the current single-diagram D2 source, the
        current artifact file-map (`{path: content}`, Epic E.3), and the active
        artifact key the user is refining. The ARCHITECTURE engine keys
        generate-vs-refine off `artifacts` and routes a refine edit to
        `target_artifact`; conversation-only engines ignore them. All are
        keyword-only with `None` defaults so an engine declares only the inputs
        it uses.
        """


_ENGINES: dict[str, type[PhaseEngine]] = {}
_INSTANCES: dict[str, PhaseEngine] = {}


def register_engine(cls: type[PhaseEngine]) -> type[PhaseEngine]:
    """Class decorator: register `cls` as the engine for its `phase`.

    The `phase` is stripped before use so registration and `get_engine` lookup
    always agree; a phase that already has an engine is rejected rather than
    silently overwritten.
    """
    raw_phase = getattr(cls, "phase", None)
    if not isinstance(raw_phase, str) or not raw_phase.strip():
        msg = f"{cls.__name__} must define a non-empty string `phase` to be registered."
        raise ValueError(msg)
    phase = raw_phase.strip()
    if phase in _ENGINES:
        msg = f"Phase {phase!r} already has an engine registered ({_ENGINES[phase].__name__})."
        raise ValueError(msg)
    _ENGINES[phase] = cls
    return cls


def available_phases() -> list[str]:
    """Sorted phases that have a registered engine."""
    return sorted(_ENGINES)


def get_engine(phase: str) -> PhaseEngine:
    """Resolve (and cache) the engine registered for `phase`.

    Raises `ValueError` listing the available phases when none is registered.
    """
    resolved = phase.strip() if isinstance(phase, str) else phase
    try:
        cls = _ENGINES[resolved]
    except (KeyError, TypeError) as exc:
        msg = f"No engine registered for phase {phase!r}; available: {available_phases()}."
        raise ValueError(msg) from exc
    engine = _INSTANCES.get(resolved)
    if engine is None:
        engine = cls()
        _INSTANCES[resolved] = engine
    return engine


async def process_turn(
    phase: str,
    history: list[Message],
    user_message: str,
    *,
    prd: str | None = None,
    current_d2: str | None = None,
    artifacts: dict[str, str] | None = None,
    target_artifact: str | None = None,
) -> LLMResponse:
    """Route one turn to its phase engine and return the engine's `LLMResponse`.

    `phase` is the project's current phase; `history` is its prior turns (oldest
    first) and `user_message` is the new turn. `prd`, `current_d2`, `artifacts`,
    and `target_artifact` are the project's current PRD, single-diagram D2
    source, artifact file-map, and the active artifact key — passed straight
    through to the engine for the phases that edit existing state (refinement,
    D.8; the architecture artifact map, E.3). An unknown phase raises
    `ValueError`. The router stays unchanged as engines are added (open/closed):
    each engine decides whether to return `suggestions`, a `next_phase`, or
    `artifacts`, and which of these inputs it reads.
    """
    engine = get_engine(phase)
    response = await engine.process(
        history,
        user_message,
        prd=prd,
        current_d2=current_d2,
        artifacts=artifacts,
        target_artifact=target_artifact,
    )
    if not isinstance(response, LLMResponse):
        msg = f"Engine for phase {phase!r} returned {type(response).__name__}, expected LLMResponse."
        raise TypeError(msg)
    return response


# Built-in phase engines self-register on import (Epic 1+). Kept last so the
# names above (PhaseEngine, register_engine, LLMResponse) exist when engine
# modules import them — mirrors `caller.py` importing the provider package.
import langflow.lothal.engines  # noqa: E402, F401  -- registers built-in phase engines
