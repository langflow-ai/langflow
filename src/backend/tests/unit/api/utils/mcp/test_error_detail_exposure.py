"""Raw component errors belong to the flow owner, not to whoever can reach the tool.

A project with ``auth_type="none"`` executes as its owning principal so the flow can read
the owner's variables and files. Deciding what to disclose from that same principal makes
every anonymous caller look like the owner, which is how owner-level tracebacks reached
the public MCP endpoint.
"""

from uuid import uuid4

import pytest
from langflow.api.v1.mcp_utils import authenticated_caller_ctx, caller_owns_resource


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture(autouse=True)
def _reset_caller():
    token = authenticated_caller_ctx.set(None)
    yield
    authenticated_caller_ctx.reset(token)


def test_should_not_disclose_when_no_caller_authenticated(owner_id):
    """The public path never establishes a caller, so it must not inherit owner privilege."""
    assert caller_owns_resource(owner_id) is False


def test_should_disclose_to_the_authenticated_owner(owner_id):
    authenticated_caller_ctx.set(owner_id)

    assert caller_owns_resource(owner_id) is True


def test_should_not_disclose_to_a_different_authenticated_user(owner_id):
    authenticated_caller_ctx.set(uuid4())

    assert caller_owns_resource(owner_id) is False


def test_should_not_disclose_for_an_ownerless_resource():
    authenticated_caller_ctx.set(uuid4())

    assert caller_owns_resource(None) is False
