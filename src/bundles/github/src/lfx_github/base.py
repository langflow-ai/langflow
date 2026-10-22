"""Connection and telemetry boundary shared by GitHub action components."""

from __future__ import annotations

from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput, DropdownInput, IntInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_github.client import GitHubClient, bounded_text, positive_id, repository_path

__all__ = [
    "DropdownInput",
    "GitHubActionComponent",
    "IntInput",
    "MultilineInput",
    "Output",
    "StrInput",
    "connection_input",
    "repository_input",
]


def connection_input(capability: str) -> ConnectionRefInput:
    return ConnectionRefInput(
        name="connection",
        display_name="GitHub Connection",
        provider="github",
        auth_profile_id="github-installation",
        identity_kind="instance",
        ownership_mode="user",
        required_scopes=[],
        capabilities=[capability],
        required=True,
        info="A GitHub App installation connection. Actions run as the app within its selected repositories.",
    )


def repository_input() -> StrInput:
    return StrInput(name="repository", display_name="Repository", required=True, info="GitHub.com owner/repository.")


class GitHubActionComponent(Component):
    icon = "Github"
    capability_id: ClassVar[str] = ""
    operation: ClassVar[str] = ""
    resource: ClassVar[str] = ""

    def _pre_run_setup(self) -> None:
        self.__dict__.pop("_github_result", None)

    async def build_result(self) -> Data:
        cached = self.__dict__.get("_github_result")
        if cached is not None:
            return Data(data=cached)
        path = repository_path(self.repository)
        operation = self.operation
        body = None
        if self.resource:
            path += "/" + self.resource
        if operation in {"get", "update", "comment"}:
            path += "/" + str(positive_id(self.number))
        if operation == "comment":
            path += "/comments"
            body = {"body": bounded_text(self.body, required=True)}
        elif operation in {"create", "update"}:
            body = {"title": bounded_text(self.title, required=True, maximum=256), "body": bounded_text(self.body)}
            if self.resource == "pulls" and operation == "create":
                body.update(
                    head=bounded_text(self.head, required=True, maximum=256),
                    base=bounded_text(self.base, required=True, maximum=256),
                )
            if operation == "update":
                if self.state not in {"open", "closed"}:
                    from lfx.integrations.errors import InvalidRequestError

                    msg = "State must be open or closed."
                    raise InvalidRequestError(msg, provider="github")
                body["state"] = self.state
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
        method = "POST" if operation in {"create", "comment"} else "PATCH" if operation == "update" else "GET"
        async with (
            integration_action(
                self, provider="github", capability=self.capability_id, owner_kind=credential.owner_kind
            ),
            GitHubClient(lease) as client,
        ):
            result = await client.request(method, path, body=body)
        if not isinstance(result, dict):
            from lfx.integrations.errors import ProviderUnavailableError

            raise ProviderUnavailableError(provider="github")
        self.__dict__["_github_result"] = result
        return Data(data=result)
