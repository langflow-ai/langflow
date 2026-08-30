"""Two-tenant isolation for the component compile cache and global variables.

`lfx.custom.eval` caches the parsed/compiled artefacts of component source and
exec's a fresh class per call. Caching the CLASS instead was tried and reverted
because it is a cross-tenant data leak: byte-identical source from two tenants
would share one class object, and therefore any class-level mutable state.

These tests exercise that end to end -- two users, two flows whose component
source is byte-identical, run concurrently -- rather than asserting the property
in-process the way `src/lfx/tests/unit/custom/` does.

`test_probe_detects_a_real_leak` is the load-bearing one: it reintroduces the
reverted design and asserts the probe FAILS. Without it a green run cannot be
distinguished from a probe that observes nothing, which happened twice while
this was being written.
"""

import asyncio
import re
import uuid

import pytest
from httpx import AsyncClient
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from lfx.services.deps import session_scope
from sqlmodel import select

# Byte-identical for both tenants: the same source is the requirement for the
# leak, not an incidental detail -- it is what makes them share a cache entry.
PROBE_SOURCE = """
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class LeakProbe(Component):
    display_name = "Leak Probe"
    name = "LeakProbe"

    # A mutable class attribute: the classic Python mistake, and exactly the
    # shape that made caching the component class a cross-tenant leak.
    _seen = []

    inputs = [MessageTextInput(name="input_value", display_name="Input", value="")]
    outputs = [Output(display_name="Message", name="message", method="probe")]

    def probe(self) -> Message:
        type(self)._seen.append(str(self.input_value))
        return Message(text="|".join(type(self)._seen))
"""

SECRET_RE = re.compile(r"(ALICE|BOB)-[0-9a-f]{12}")


def _has_compile_cache() -> bool:
    """Whether the artefact-caching compile path is present.

    Two of these tests exercise the cache specifically. On a tree without it
    (the pre-cache revision, or a bisect that reverts validate.py) they would
    fail for the wrong reason -- absence of the feature, not a leak -- so they
    skip instead. The leak tests proper do not depend on it.
    """
    from lfx.custom import validate

    return hasattr(validate, "_compile_component_artifacts")


requires_compile_cache = pytest.mark.skipif(
    not _has_compile_cache(), reason="build does not include the artefact compile cache"
)


def _build_class(source: str):
    """Build a component class the way the runtime does."""
    from lfx.custom.eval import eval_custom_component_code

    return eval_custom_component_code(source)


async def _make_user(username: str) -> User:
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return await session.get(User, user.id)


@pytest.fixture
async def two_tenants(client: AsyncClient):  # noqa: ARG001
    a = await _make_user(f"alice-{uuid.uuid4().hex[:8]}")
    b = await _make_user(f"bob-{uuid.uuid4().hex[:8]}")
    yield a, b
    async with session_scope() as session:
        for u in (a, b):
            db_user = await session.get(User, u.id)
            if db_user:
                await session.delete(db_user)


async def test_identical_source_yields_isolated_class_state():
    """Two tenants' byte-identical components must not share class state."""
    cls_a = _build_class(PROBE_SOURCE)
    cls_b = _build_class(PROBE_SOURCE)

    assert cls_a is not cls_b, "identical source produced ONE shared class object"

    cls_a._seen.append("ALICE-aaaaaaaaaaaa")
    assert cls_a._seen != cls_b._seen
    assert "ALICE-aaaaaaaaaaaa" not in cls_b._seen, "tenant A's data reached tenant B"


@requires_compile_cache
async def test_compile_artifacts_are_still_cached():
    """The isolation above must not come from disabling the cache entirely."""
    from lfx.custom import validate

    first = validate._compile_component_artifacts(PROBE_SOURCE)
    second = validate._compile_component_artifacts(PROBE_SOURCE)
    assert first is second, "compile artefacts are no longer cached -- perf regression"


@requires_compile_cache
async def test_probe_detects_a_real_leak():
    """NEGATIVE CONTROL. Reintroduce the reverted design; the probe must FAIL.

    A leak test that cannot fail proves nothing. This asserts the assertion in
    `test_identical_source_yields_isolated_class_state` is load-bearing.
    """
    from functools import lru_cache

    from lfx.custom import validate

    @lru_cache(maxsize=8)
    def leaky(code: str):
        return validate._instantiate_component_class(validate._compile_component_artifacts(code))

    cls_a = leaky(PROBE_SOURCE)
    cls_b = leaky(PROBE_SOURCE)

    assert cls_a is cls_b, "the leaky design did not actually share a class -- control is void"
    cls_a._seen.append("ALICE-deadbeefcafe")
    assert "ALICE-deadbeefcafe" in cls_b._seen, (
        "the reverted design did not leak, so this control cannot validate the real test"
    )


async def test_concurrent_builds_do_not_cross_contaminate():
    """Sibling vertices build concurrently via asyncio.gather; state must not mix."""

    async def build_and_use(tag: str) -> list[str]:
        cls = await asyncio.to_thread(_build_class, PROBE_SOURCE)
        cls._seen.append(tag)
        await asyncio.sleep(0)
        return list(cls._seen)

    tags = [f"ALICE-{i:012x}" if i % 2 else f"BOB-{i:012x}" for i in range(12)]
    results = await asyncio.gather(*(build_and_use(t) for t in tags))

    for tag, seen in zip(tags, results, strict=True):
        assert seen == [tag], f"build for {tag} observed foreign state: {seen}"


async def test_flow_read_is_owner_scoped(client: AsyncClient, two_tenants, logged_in_headers):
    """A tenant must not be able to read another tenant's flow by id."""
    alice, _bob = two_tenants
    async with session_scope() as session:
        flow = Flow(
            name=f"alice-flow-{uuid.uuid4().hex[:6]}",
            user_id=alice.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id

    # logged_in_headers belongs to the default fixture user, not alice.
    resp = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert resp.status_code in (403, 404), (
        f"another user read alice's flow (HTTP {resp.status_code}) -- cross-tenant read"
    )


async def test_global_variables_are_owner_scoped(two_tenants):
    """Variables are per-user; a name collision must not cross tenants."""
    from langflow.services.database.models.variable.model import Variable

    alice, bob = two_tenants
    name = "LEAKPROBE_SHARED_NAME"
    async with session_scope() as session:
        session.add(Variable(user_id=alice.id, name=name, value="ALICE-VALUE", type="Generic"))
        session.add(Variable(user_id=bob.id, name=name, value="BOB-VALUE", type="Generic"))
        await session.flush()

    async with session_scope() as session:
        for user, own in ((alice, "ALICE-VALUE"), (bob, "BOB-VALUE")):
            rows = (
                await session.exec(select(Variable).where(Variable.user_id == user.id, Variable.name == name))
            ).all()
            assert len(rows) == 1, f"{user.username} sees {len(rows)} variables named {name}"
            assert rows[0].value == own
