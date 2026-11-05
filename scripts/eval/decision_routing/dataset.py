"""Routing suites: what to ask, the routes to choose between, and labelled cases.

A suite is a JSON file that names its cases file (JSON Lines, one case per line)::

    {
      "name": "support-ticket-routing",
      "kind": "choice",
      "question": "Which team should handle this customer message?",
      "minimum_probability": 0.7,
      "routes": [{"name": "Billing", "description": "...", "minimum_probability": null}],
      "cases": "support_ticket_routing.jsonl"
    }

    {"id": "billing-001", "text": "I was charged twice.", "expected": "Billing", "tags": ["billing"]}

``expected`` is a route name, or ``Else`` for a message no route should take. Boolean suites have no
routes; their cases expect ``Yes``, ``No`` or ``Else``. Score suites name ordered ``levels`` in place
of routes, and every case expects a level.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ELSE = "Else"
KINDS = ("choice", "boolean", "score")
BOOLEAN_OUTCOMES = ("Yes", "No")


@dataclass(frozen=True)
class Route:
    name: str
    description: str = ""
    minimum_probability: float | None = None


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expected: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Suite:
    name: str
    kind: str
    question: str
    routes: tuple[Route, ...]
    minimum_probability: float | None
    cases: tuple[Case, ...]

    @property
    def outcomes(self) -> tuple[str, ...]:
        """Every label a case can expect."""
        named = BOOLEAN_OUTCOMES if self.kind == "boolean" else tuple(route.name for route in self.routes)
        return (*named, ELSE) if self.kind != "score" else named


class SuiteError(ValueError):
    """A suite or case file a run can't use; says which line or field to fix."""


def _route(raw: object, where: str) -> Route:
    if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
        msg = f"{where} needs a name."
        raise SuiteError(msg)
    minimum = raw.get("minimum_probability")
    if minimum is not None and not (isinstance(minimum, int | float) and 0 <= minimum <= 1):
        msg = f"{where}'s minimum_probability must be a number from 0 to 1."
        raise SuiteError(msg)
    return Route(
        name=str(raw["name"]).strip(), description=str(raw.get("description") or ""), minimum_probability=minimum
    )


def _cases(path: Path, outcomes: tuple[str, ...]) -> tuple[Case, ...]:
    cases: list[Case] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{path.name} line {number}"
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = f"{where} isn't valid JSON: {exc.msg}."
            raise SuiteError(msg) from None
        case_id, text, expected = (str(raw.get(key) or "").strip() for key in ("id", "text", "expected"))
        if not (case_id and text and expected):
            msg = f"{where} needs an id, text and expected."
            raise SuiteError(msg)
        if case_id in seen:
            msg = f"{where} repeats the id {case_id!r}."
            raise SuiteError(msg)
        if expected not in outcomes:
            msg = f"{where} expects {expected!r}, which isn't one of: {', '.join(outcomes)}."
            raise SuiteError(msg)
        seen.add(case_id)
        cases.append(Case(id=case_id, text=text, expected=expected, tags=tuple(raw.get("tags") or ())))
    if not cases:
        msg = f"{path.name} has no cases."
        raise SuiteError(msg)
    return tuple(cases)


def load_suite(path: str | Path) -> Suite:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Can't read the suite {path}: {exc}."
        raise SuiteError(msg) from None
    kind = raw.get("kind")
    if kind not in KINDS:
        msg = f"kind must be one of: {', '.join(KINDS)}."
        raise SuiteError(msg)
    question = str(raw.get("question") or "").strip()
    if not question:
        msg = "The suite needs a question."
        raise SuiteError(msg)
    table = "levels" if kind == "score" else "routes"
    rows = raw.get(table) or []
    if kind == "boolean" and rows:
        msg = "A Boolean suite has no routes: its outcomes are Yes and No."
        raise SuiteError(msg)
    if kind != "boolean" and len(rows) < 2:  # noqa: PLR2004 - a choice needs two options
        msg = f"The suite needs at least two {table}."
        raise SuiteError(msg)
    routes = tuple(_route(row, f"{table}[{i}]") for i, row in enumerate(rows))
    if len({route.name.casefold() for route in routes}) != len(routes) or any(r.name == ELSE for r in routes):
        msg = f"Every one of the {table} needs a different name, and none can be called {ELSE}."
        raise SuiteError(msg)
    minimum = raw.get("minimum_probability")
    if kind != "score" and not (isinstance(minimum, int | float) and 0 <= minimum <= 1):
        msg = "minimum_probability must be a number from 0 to 1."
        raise SuiteError(msg)
    cases_path = path.parent / str(raw.get("cases") or "")
    if not cases_path.is_file():
        msg = f"The cases file {cases_path} doesn't exist."
        raise SuiteError(msg)
    suite = Suite(
        name=str(raw.get("name") or path.stem),
        kind=kind,
        question=question,
        routes=routes,
        minimum_probability=None if kind == "score" else float(minimum),
        cases=(),
    )
    return Suite(**{**suite.__dict__, "cases": _cases(cases_path, suite.outcomes)})
