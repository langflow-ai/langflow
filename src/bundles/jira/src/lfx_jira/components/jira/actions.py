"""Explicit Jira issue operations with server-enforced connection policies."""

from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from lfx_jira.base import JiraActionComponent
from lfx_jira.manifest import connection_input
from lfx_jira.schema import (
    FIELDS,
    document,
    invalid,
    issue_data,
    issue_key,
    numeric_id,
    project_key,
    search_body,
    text,
)

PAGE_SIZE = 100


class JiraSearchIssuesComponent(JiraActionComponent):
    display_name = "Jira Search Issues"
    description = "Search one project by optional status ID with explicit continuation."
    name = "JiraSearchIssues"
    capability_id = "jira.issue.search"
    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="project", display_name="Project Key", required=True),
        MessageTextInput(name="status_id", display_name="Status ID"),
        MessageTextInput(name="page", display_name="Next Page Token", advanced=True),
    ]
    outputs = [Output(display_name="Issues", name="issues", method="search_issues")]

    async def search_issues(self) -> Data:
        project = project_key(self.project)
        result = await self.perform(
            "POST",
            "/rest/api/3/search/jql",
            body=search_body(project, getattr(self, "status_id", "") or "", getattr(self, "page", "") or ""),
        )
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("issues"), list)
            or len(result["issues"]) > PAGE_SIZE
        ):
            msg = "Jira returned an invalid search result."
            raise invalid(msg)
        rows = [issue_data(row, project=project) for row in result["issues"]]
        page = result.get("nextPageToken")
        if page is not None:
            page = text(page, maximum=8192)
        return Data(data={"issues": rows, "next_page_token": page, "is_last": result.get("isLast", not bool(page))})


class JiraReadIssueComponent(JiraActionComponent):
    display_name = "Jira Read Issue"
    description = "Read the summary, status, project and timestamps of one issue."
    name = "JiraReadIssue"
    capability_id = "jira.issue.read"
    inputs = [connection_input(capability_id), MessageTextInput(name="issue", display_name="Issue Key", required=True)]
    outputs = [Output(display_name="Issue", name="result", method="read_issue")]

    async def read_issue(self) -> Data:
        key = issue_key(self.issue)
        result = await self.perform("GET", f"/rest/api/3/issue/{key}", params={"fields": ",".join(FIELDS)})
        return Data(data=issue_data(result, key=key))


class JiraCreateIssueComponent(JiraActionComponent):
    display_name = "Jira Create Issue"
    description = "Create one issue with a summary, type ID and optional plain text description."
    name = "JiraCreateIssue"
    capability_id = "jira.issue.create"
    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="project", display_name="Project Key", required=True),
        MessageTextInput(name="issue_type_id", display_name="Issue Type ID", required=True),
        MessageTextInput(name="summary", display_name="Summary", required=True),
        MessageTextInput(name="description_text", display_name="Description"),
    ]
    outputs = [Output(display_name="Issue", name="result", method="create_issue")]

    async def create_issue(self) -> Data:
        project = project_key(self.project)
        fields = {
            "project": {"key": project},
            "issuetype": {"id": numeric_id(self.issue_type_id)},
            "summary": text(self.summary, maximum=255),
        }
        if getattr(self, "description_text", ""):
            fields["description"] = document(self.description_text)
        result = await self.perform("POST", "/rest/api/3/issue", body={"fields": fields}, write=True)
        if not isinstance(result, dict) or issue_key(result.get("key")).rsplit("-", 1)[0] != project:
            msg = "Jira returned an unrelated issue."
            raise invalid(msg)
        return Data(data={"id": numeric_id(result.get("id")), "key": result["key"]})


class JiraUpdateIssueComponent(JiraActionComponent):
    display_name = "Jira Update Issue"
    description = "Update one issue summary and optionally replace its plain text description."
    name = "JiraUpdateIssue"
    capability_id = "jira.issue.update"
    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="issue", display_name="Issue Key", required=True),
        MessageTextInput(name="summary", display_name="Summary", required=True),
        MessageTextInput(name="description_text", display_name="Description"),
    ]
    outputs = [Output(display_name="Result", name="result", method="update_issue")]

    async def update_issue(self) -> Data:
        key = issue_key(self.issue)
        fields = {"summary": text(self.summary, maximum=255)}
        if getattr(self, "description_text", ""):
            fields["description"] = document(self.description_text)
        await self.perform("PUT", f"/rest/api/3/issue/{key}", body={"fields": fields}, write=True)
        return Data(data={"key": key, "updated": True})


class JiraTransitionIssueComponent(JiraActionComponent):
    display_name = "Jira Transition Issue"
    description = "Apply an available transition ID after checking the issue workflow."
    name = "JiraTransitionIssue"
    capability_id = "jira.issue.transition"
    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="issue", display_name="Issue Key", required=True),
        MessageTextInput(name="transition_id", display_name="Transition ID", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="transition_issue")]

    async def transition_issue(self) -> Data:
        key, transition = issue_key(self.issue), numeric_id(self.transition_id)
        result = await self.perform("GET", f"/rest/api/3/issue/{key}/transitions")
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("transitions"), list)
            or not any(isinstance(row, dict) and row.get("id") == transition for row in result["transitions"])
        ):
            msg = "This transition is unavailable for the issue and account."
            raise invalid(msg)
        await self.perform(
            "POST", f"/rest/api/3/issue/{key}/transitions", body={"transition": {"id": transition}}, write=True
        )
        return Data(data={"key": key, "transition_id": transition, "transitioned": True})
