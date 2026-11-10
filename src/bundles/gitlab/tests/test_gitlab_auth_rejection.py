"""GitLab rejections reach the connection resolver without retrying the rejected token."""

from dataclasses import replace
from functools import partial
from hashlib import sha256

import httpx
import pytest
from lfx.integrations.errors import AuthExpiredError
from lfx_gitlab.client import GitLabClient
from lfx_gitlab.components.gitlab import GitLabGetProjectComponent
from pydantic import SecretStr


@pytest.mark.parametrize("replacement", [False, True])
async def test_provider_rejection_reports_the_token_and_retries_only_a_replacement(lease, replacement):
    credential = await lease.get_credential()
    resolutions = []

    async def resolve(request):
        resolutions.append(request)
        assert request.rejected_token_digest == sha256(credential.access_token.get_secret_value().encode()).hexdigest()
        if not replacement:
            raise AuthExpiredError(provider="gitlab")
        return replace(credential, access_token=SecretStr("synthetic-replacement-token"))

    lease._resolver.resolve = resolve
    requests = []

    def handle(request):
        requests.append(request)
        if request.headers["private-token"] == credential.access_token.get_secret_value():
            return httpx.Response(401, text="private provider failure")
        return httpx.Response(200, json={"id": 80})

    async with GitLabClient(lease, transport=httpx.MockTransport(handle)) as client:
        if replacement:
            assert await client.request("GET", "/projects/80") == {"id": 80}
        else:
            with pytest.raises(AuthExpiredError):
                await client.request("GET", "/projects/80")
    assert len(resolutions) == 1
    assert len(requests) == (2 if replacement else 1)


@pytest.mark.parametrize("during_resolution", [False, True])
async def test_action_errors_include_reconnect_guidance(monkeypatch, lease, during_resolution):
    if during_resolution:

        async def rejected(_request):
            raise AuthExpiredError(provider="gitlab")

        lease._resolver.resolve = rejected
    monkeypatch.setattr(GitLabGetProjectComponent, "resolve_connection", lambda _self, _field: lease)
    monkeypatch.setattr(
        "lfx_gitlab.base.GitLabClient",
        partial(GitLabClient, transport=httpx.MockTransport(lambda _request: httpx.Response(401))),
    )
    component = GitLabGetProjectComponent(connection="gitlab/work", project_id=80)
    with pytest.raises(AuthExpiredError, match="Reconnect the GitLab connection") as caught:
        await component.build_result()
    assert caught.value.code == "auth-expired"
