"""Extras-drift guard for ``langflow-base[services]`` / ``[complete]`` / ``[all]``.

``src/backend/base/pyproject.toml`` defines:

* ``services`` — exhaustive concrete-service backends/providers (opt-in)
* ``complete`` — default host feature set pulled by ``pip install langflow``
* ``all`` — backward-compatible alias for ``complete`` (does NOT include ``services``)

These invariants must not drift by hand-edit: PostgreSQL and Celery must stay
inside ``services`` but must NOT appear in ``complete`` or ``all``, and every
service-owned backend/provider extra must remain referenced by ``services``.
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# File lives at src/backend/tests/unit/… → parents[2] is src/backend.
BASE_PYPROJECT = Path(__file__).resolve().parents[2] / "base" / "pyproject.toml"

# Direct packages that service code imports but were previously only transitive.
REQUIRED_DIRECT_PACKAGES = frozenset({"anyio", "tenacity", "dill"})

# Service-owned backend/provider extras that ``services`` must reference.
REQUIRED_SERVICE_EXTRAS = frozenset(
    {
        "postgresql",
        "redis",
        "chroma",
        "aioboto3",
        "celery",
        "kubernetes",
        "langfuse",
        "langwatch",
        "langsmith",
        "arize",
        "openinference",
        "opik",
        "traceloop",
        "openlayer",
        "ibm-watsonx-clients",
    }
)

# Must stay out of the default ``pip install langflow`` / ``[complete]`` / ``[all]`` path.
COMPLETE_MUST_NOT_INCLUDE = frozenset({"postgresql", "celery", "services"})


def _load_optional() -> dict[str, list[str]]:
    assert BASE_PYPROJECT.is_file(), f"pyproject.toml not found at {BASE_PYPROJECT}"
    with BASE_PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["optional-dependencies"]


def _package_name(spec: str) -> str:
    for sep in ("[", " ", ";", "=", "<", ">", "!", "~"):
        if sep in spec:
            spec = spec.split(sep, 1)[0]
    return spec.strip().lower()


def _extra_refs(specs: list[str], package: str = "langflow-base") -> set[str]:
    """Return referenced extras from ``package[extra]`` self-refs."""
    prefix = f"{package}["
    found: set[str] = set()
    for spec in specs:
        if not spec.startswith(prefix) or "]" not in spec:
            continue
        inner = spec[len(prefix) : spec.index("]")]
        found.update(part.strip() for part in inner.split(",") if part.strip())
    return found


def test_services_extra_exists_and_includes_direct_packages() -> None:
    optional = _load_optional()
    assert "services" in optional, "Expected `services` optional-dependency group"
    names = {_package_name(s) for s in optional["services"]}
    missing = REQUIRED_DIRECT_PACKAGES - names
    assert not missing, (
        f"`services` is missing required direct packages: {sorted(missing)}. Current specs: {optional['services']}"
    )


def test_services_extra_references_every_service_backend() -> None:
    optional = _load_optional()
    refs = _extra_refs(optional["services"])
    missing = REQUIRED_SERVICE_EXTRAS - refs
    assert not missing, (
        f"`services` is missing required backend/provider extras: {sorted(missing)}. Referenced: {sorted(refs)}"
    )


def test_celery_extra_includes_celery_and_asgiref() -> None:
    optional = _load_optional()
    assert "celery" in optional, "Expected `celery` optional-dependency group"
    names = {_package_name(s) for s in optional["celery"]}
    for required in ("celery", "asgiref"):
        assert required in names, f"`celery` extra is missing `{required}`. Current specs: {optional['celery']}"


def test_complete_remains_independent_of_services() -> None:
    optional = _load_optional()
    refs = _extra_refs(optional["complete"])
    leaked = COMPLETE_MUST_NOT_INCLUDE & refs
    assert not leaked, (
        f"`complete` must not pull {sorted(leaked)}; "
        f"those stay opt-in via `[services]` or `[complete,services]`. Referenced: {sorted(refs)}"
    )
    # Direct package names in complete (should not list postgresql/celery/services either).
    names = {_package_name(s) for s in optional["complete"]}
    for forbidden in ("postgresql", "celery", "psycopg", "psycopg2"):
        assert forbidden not in names, f"`complete` must not declare `{forbidden}` directly"


def test_all_remains_alias_for_complete() -> None:
    """Backward compat: [all] must stay equivalent to [complete], not pull [services]."""
    optional = _load_optional()
    assert "all" in optional
    refs = _extra_refs(optional["all"])
    assert refs == {"complete"}, (
        f"`all` must be exactly an alias for complete; got {sorted(refs)}. Specs: {optional['all']}"
    )
    leaked = COMPLETE_MUST_NOT_INCLUDE & refs
    assert not leaked, f"`all` must not pull {sorted(leaked)}; keep PostgreSQL/Celery opt-in via `[services]`"


def test_postgresql_and_celery_cannot_fall_out_of_services() -> None:
    """Regression: the headline gaps that motivated `[services]`."""
    optional = _load_optional()
    refs = _extra_refs(optional["services"])
    for required in ("postgresql", "celery"):
        assert required in refs, (
            f"`services` lost `{required}` — this was the gap vs `[complete]`. Referenced: {sorted(refs)}"
        )
    # Celery extra itself must exist so the self-ref resolves.
    assert "celery" in optional
    assert "postgresql" in optional
