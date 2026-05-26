"""Tests for the FlowAction enum and its coercion in ensure_flow_permission."""

from __future__ import annotations

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ShareAction,
    VariableAction,
)


def test_flow_action_values_match_policy_strings():
    """Policy action strings match FlowAction enum values."""
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


def test_deployment_action_values_match_policy_strings():
    """Policy action strings match DeploymentAction enum values."""
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


def test_knowledge_base_action_values():
    """Knowledge bases support read/write/create/delete plus an INGEST verb."""
    values = {member.value for member in KnowledgeBaseAction}
    assert values == {"read", "write", "create", "delete", "ingest"}


def test_variable_action_values():
    values = {member.value for member in VariableAction}
    assert values == {"read", "write", "create", "delete"}


def test_file_action_values():
    values = {member.value for member in FileAction}
    assert values == {"read", "write", "create", "delete"}


def test_share_action_values():
    """Share actions cover CRUD over ``authz_share`` rows themselves."""
    values = {member.value for member in ShareAction}
    assert values == {"read", "create", "update", "delete"}


def test_new_actions_subclass_str():
    """All new action enums subclass str so they coerce in audit/log paths."""
    for member in (
        KnowledgeBaseAction.READ,
        VariableAction.CREATE,
        FileAction.DELETE,
        ShareAction.UPDATE,
    ):
        assert isinstance(member, str)
