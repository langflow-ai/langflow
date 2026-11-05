"""Connection and telemetry boundary for GitLab action components."""

from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.errors import InvalidRequestError, ProviderUnavailableError
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput, IntInput
from lfx.schema.data import Data

from lfx_gitlab.client import GitLabClient, bounded_text, positive_id


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


def project_input():
    return IntInput(
        name="project_id",
        display_name="Project ID",
        required=True,
        info="Numeric GitLab project ID. Project paths and URLs are unavailable.",
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
        path = f"/projects/{positive_id(self.project_id)}"
        operation = self.operation
        if self.resource != "project":
            path += "/" + {"issue": "issues", "merge_request": "merge_requests"}[self.resource]
        if self.resource != "project" and operation in {"get", "update", "comment"}:
            path += "/" + str(positive_id(self.number))
        body = None
        if operation == "comment":
            path += "/notes"
            body = {"body": bounded_text(self.body, required=True)}
        elif operation == "create":
            body = {
                "title": bounded_text(self.title, required=True, maximum=255),
                "description": bounded_text(self.body_content),
            }
            if self.resource == "merge_request":
                body.update(
                    source_branch=bounded_text(self.source_branch, required=True, maximum=255),
                    target_branch=bounded_text(self.target_branch, required=True, maximum=255),
                )
        elif operation == "update":
            body = {}
            if self.title not in (None, ""):
                body["title"] = bounded_text(self.title, required=True, maximum=255)
            if self.body_content not in (None, ""):
                body["description"] = bounded_text(self.body_content)
            if self.state_event not in {"unchanged", "close", "reopen"}:
                msg = "Choose a supported state change."
                raise InvalidRequestError(msg, provider="gitlab")
            if self.state_event != "unchanged":
                body["state_event"] = self.state_event
            if not body:
                msg = "Provide a new title, description, or state change."
                raise InvalidRequestError(msg, provider="gitlab")
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
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
