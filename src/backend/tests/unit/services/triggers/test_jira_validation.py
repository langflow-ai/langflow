"""Actionable Jira trigger configuration errors."""

import json
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.triggers.providers.jira import collector
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx_jira.client import JiraClient

from tests.unit.services.triggers.jira_testkit import SITE, issue, lease_for

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("issue_type", ["Bug", "0", "-1", '10001" OR 1=1', 10001, []])
def test_invalid_issue_type_names_the_field(issue_type):
    with pytest.raises(ValueError, match=r"Issue Type ID.*positive numeric ID"):
        collector.normalize_config(
            "jira.issue_created",
            {"connection": "jira/work", "project": "DEMO", "issue_type_id": issue_type},
        )


@pytest.mark.parametrize("project", ["demo", 'DEMO" OR 1=1', "", None])
def test_invalid_project_names_the_field(project):
    with pytest.raises(ValueError, match="uppercase Jira project key"):
        collector.normalize_config("jira.issue_created", {"connection": "jira/work", "project": project})


@pytest.mark.parametrize("connection", ["", "google/work", None])
def test_invalid_connection_names_the_field(connection):
    with pytest.raises(ValueError, match="owned Jira connection"):
        collector.normalize_config("jira.issue_created", {"connection": connection, "project": "DEMO"})


@pytest.mark.parametrize("issue_type", [None, ""])
def test_empty_issue_type_remains_optional(issue_type):
    config = collector.normalize_config(
        "jira.issue_created", {"connection": "jira/work", "project": "DEMO", "issue_type_id": issue_type}
    )
    assert config["issue_type_id"] == ""


@pytest.mark.parametrize("over_limit", [False, True])
async def test_snapshot_limit_is_actionable_and_preserves_cursor(monkeypatch, over_limit):
    monkeypatch.setenv("LANGFLOW_JIRA_CLOUD_ID", SITE)

    def handler(request):
        page = int(json.loads(request.content).get("nextPageToken", "0"))
        return httpx.Response(
            200,
            json={
                "issues": [issue(str(page * 100 + index + 1)) for index in range(100)],
                "nextPageToken": str(page + 1),
                "isLast": page == 49 and not over_limit,
            },
        )

    monkeypatch.setattr(
        collector, "JiraClient", lambda lease: JiraClient(lease, transport=httpx.MockTransport(handler))
    )
    node = SimpleNamespace(
        kind="jira.issue_created",
        config={"connection": "jira/work", "project": "DEMO"},
        provider_state={},
        connection_id=None,
    )
    if over_limit:
        with pytest.raises(SourceConfigurationError, match=r"5000-issue.*Issue Type ID"):
            await collector.collect(node, lease_for()[0])
    else:
        result = await collector.collect(node, lease_for()[0])
        assert len(result.cursor["issues"]) == 5000
        assert result.baseline
        assert result.items == []
    assert node.provider_state == {}
