"""Tests for the FlowAction enum and its coercion in ensure_flow_permission."""

from __future__ import annotations

from langflow.services.authorization.actions import DeploymentAction, FlowAction


def test_flow_action_values_match_casbin_strings():
    """Casbin policies use lowercase action strings; the enum values must match."""
    assert FlowAction.READ.value == "read"
    assert FlowAction.WRITE.value == "write"
    assert FlowAction.CREATE.value == "create"
    assert FlowAction.DELETE.value == "delete"
    assert FlowAction.EXECUTE.value == "execute"
    assert FlowAction.DEPLOY.value == "deploy"


def test_flow_action_subclasses_str():
    """Subclassing str lets the enum be passed wherever a string is accepted."""
    assert isinstance(FlowAction.READ, str)
    assert FlowAction.WRITE == "write"


def test_flow_action_is_iterable_and_complete():
    """The enum exposes exactly the six canonical actions."""
    values = {member.value for member in FlowAction}
    assert values == {"read", "write", "create", "delete", "execute", "deploy"}


def test_deployment_action_values_match_casbin_strings():
    """Casbin policies use lowercase action strings; the enum values must match."""
    assert DeploymentAction.READ.value == "read"
    assert DeploymentAction.WRITE.value == "write"
    assert DeploymentAction.CREATE.value == "create"
    assert DeploymentAction.DELETE.value == "delete"
    assert DeploymentAction.EXECUTE.value == "execute"


def test_deployment_action_subclasses_str():
    """Subclassing str lets the enum be passed wherever a string is accepted."""
    assert isinstance(DeploymentAction.WRITE, str)
    assert DeploymentAction.DELETE == "delete"


def test_deployment_action_is_iterable_and_complete():
    """The enum exposes exactly the five canonical deployment actions (no DEPLOY)."""
    values = {member.value for member in DeploymentAction}
    assert values == {"read", "write", "create", "delete", "execute"}
