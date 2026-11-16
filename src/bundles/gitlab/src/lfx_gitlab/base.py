"""Connection and telemetry boundary for GitLab action components."""

from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.errors import AuthExpiredError, InvalidRequestError, ProviderUnavailableError
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput, IntInput
from lfx.schema.data import Data

from lfx_gitlab.client import GitLabAuthExpiredError, GitLabClient, bounded_text, positive_id


def connection_input(capability):
    return ConnectionRefInput(
        name="connection",
        display_name="GitLab Connection",
        provider="gitlab",
        auth_profile_id="gitlab-personal-token",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=["api"],
        capabilities=[capability],
        required=True,
        info="Use a verified personal access token for this deployment's configured GitLab instance.",
    )


def project_input(*, connectable=True):
    return IntInput(
        name="project_id",
        display_name="Project ID",
        required=True,
        input_types=["Message"] if connectable else [],
        info="Numeric GitLab project ID. Project paths and URLs are unavailable.",
        tool_mode=connectable,
    )


class GitLabActionComponent(Component):
    icon = "Gitlab"
    capability_id: ClassVar[str] = ""
    operation: ClassVar[str] = ""
    resource: ClassVar[str] = ""

    def _pre_run_setup(self):
        self.__dict__.pop("_gitlab_result", None)

    async def build_result(self) -> Data:
        if "_gitlab_result" in self.__dict__:
            return Data(data=self.__dict__["_gitlab_result"])
        path = f"/projects/{positive_id(self.project_id, field='Project ID')}"
        operation = self.operation
        if self.resource != "project":
            path += "/" + {"issue": "issues", "merge_request": "merge_requests"}[self.resource]
        if self.resource != "project" and operation in {"get", "update", "comment"}:
            number_field = "Issue Number" if self.resource == "issue" else "Merge Request Number"
            path += "/" + str(positive_id(self.number, field=number_field))
        body = None
        if operation == "comment":
            path += "/notes"
            body = {"body": bounded_text(self.body, required=True, field="Comment")}
        elif operation == "create":
            body = {
                "title": bounded_text(self.title, required=True, maximum=255, field="Title"),
                "description": bounded_text(self.body_content, field="Description"),
            }
            if self.resource == "merge_request":
                body.update(
                    source_branch=bounded_text(self.source_branch, required=True, maximum=255, field="Source Branch"),
                    target_branch=bounded_text(self.target_branch, required=True, maximum=255, field="Target Branch"),
                )
        elif operation == "update":
            body = {}
            if self.title not in (None, ""):
                body["title"] = bounded_text(self.title, required=True, maximum=255, field="Title")
            if self.body_content not in (None, ""):
                body["description"] = bounded_text(self.body_content, field="Description")
            if self.state_event not in {"unchanged", "close", "reopen"}:
                msg = "Choose a supported state change."
                raise InvalidRequestError(msg, provider="gitlab")
            if self.state_event != "unchanged":
                body["state_event"] = self.state_event
            if not body:
                msg = "Provide a new title, description, or state change."
                raise InvalidRequestError(msg, provider="gitlab")
        lease = self.resolve_connection("connection")
        try:
            credential = await lease.get_credential()
        except AuthExpiredError:
            raise GitLabAuthExpiredError from None
        method = "POST" if operation in {"create", "comment"} else "PUT" if operation == "update" else "GET"
        async with (
            integration_action(
                self, provider="gitlab", capability=self.capability_id, owner_kind=credential.owner_kind
            ),
            GitLabClient(lease) as client,
        ):
            result = await client.request(method, path, body=body)
        if not isinstance(result, dict):
            raise ProviderUnavailableError(provider="gitlab")
        self.__dict__["_gitlab_result"] = result
        return Data(data=result)
