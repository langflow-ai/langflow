"""The Slack app manifests Langflow publishes agree with everything that depends on them.

TRG-5's acceptance criterion: "documented scopes equal the app manifest". A
customer creates their Slack app from ``docs/static/files/slack/*.json``, so the
manifests are the contract with Slack. They must cover every event the
event-transport matrix subscribes to, every scope the matrix and the bundle's
components require, the scope table on the docs page, and the Request URL the
ingress route actually serves. Drift in any direction fails here, not at a
customer's first silent trigger.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = REPO_ROOT / "docs" / "static" / "files" / "slack"
EVENTS_API_MANIFEST = MANIFESTS / "langflow-slack-app-events-api.json"
SOCKET_MODE_MANIFEST = MANIFESTS / "langflow-slack-app-socket-mode.json"
MATRIX = REPO_ROOT / "design" / "dedicated-integrations-triggers" / "matrices" / "slack-events.json"
CAPABILITIES = (
    REPO_ROOT / "src" / "bundles" / "slack" / "src" / "lfx_slack" / "components" / "slack" / "capabilities.v1.json"
)
DOCS_PAGE = REPO_ROOT / "docs" / "docs" / "Components" / "bundles-slack.mdx"
INGRESS_ROUTE = REPO_ROOT / "src" / "backend" / "base" / "langflow" / "api" / "v1" / "trigger_ingress.py"

#: The app-level token's scope. It belongs to the token, not to the bot, so it
#: is never in a manifest's bot scopes.
APP_TOKEN_SCOPE = "connections:write"  # noqa: S105 - an OAuth scope name, not a credential


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=["events_api", "socket_mode"])
def manifest(request) -> dict:
    return _load(EVENTS_API_MANIFEST if request.param == "events_api" else SOCKET_MODE_MANIFEST)


def _mechanisms() -> list[dict]:
    return [
        mechanism
        for mechanism in _load(MATRIX)["mechanisms"]
        if mechanism["mechanism_id"] in {"slack.events_api", "slack.socket_mode"}
    ]


def _documented_bot_scopes() -> set[str]:
    page = DOCS_PAGE.read_text(encoding="utf-8")
    match = re.search(r"slack-app-bot-scopes:start \*/\}(.*?)\{/\* slack-app-bot-scopes:end", page, re.DOTALL)
    assert match, "the docs page lost its bot-scope table markers"
    return set(re.findall(r"^\| `([a-z_:.]+)` \|", match.group(1), re.MULTILINE))


def _capability_scopes(prefix: str) -> set[str]:
    scopes: set[str] = set()
    for capability in _load(CAPABILITIES)["capabilities"]:
        if capability["id"].startswith(prefix):
            scopes.update(capability["required_scopes"])
            scopes.update(item["scope"] for item in capability.get("conditional_scopes", []))
    return scopes


def test_the_documented_scopes_equal_the_manifest(manifest: dict) -> None:
    assert set(manifest["oauth_config"]["scopes"]["bot"]) == _documented_bot_scopes()


def test_the_manifest_subscribes_to_every_event_the_matrix_delivers(manifest: dict) -> None:
    for mechanism in _mechanisms():
        assert set(manifest["settings"]["event_subscriptions"]["bot_events"]) == set(mechanism["events"])


def test_the_manifest_grants_every_scope_the_matrix_requires(manifest: dict) -> None:
    bot = set(manifest["oauth_config"]["scopes"]["bot"])
    assert APP_TOKEN_SCOPE not in bot
    for mechanism in _mechanisms():
        assert set(mechanism["required_scopes"]) - {APP_TOKEN_SCOPE} <= bot, mechanism["mechanism_id"]


def test_the_manifest_grants_every_scope_the_as_app_actions_need(manifest: dict) -> None:
    assert _capability_scopes("slack.bot.") <= set(manifest["oauth_config"]["scopes"]["bot"])


def test_the_events_api_manifest_also_serves_the_as_user_actions() -> None:
    manifest = _load(EVENTS_API_MANIFEST)
    assert _capability_scopes("slack.user.") <= set(manifest["oauth_config"]["scopes"]["user"])


def test_each_manifest_turns_on_exactly_its_own_transport() -> None:
    events_api = _load(EVENTS_API_MANIFEST)["settings"]
    socket_mode = _load(SOCKET_MODE_MANIFEST)["settings"]

    assert events_api["socket_mode_enabled"] is False
    assert "request_url" in events_api["event_subscriptions"]
    assert socket_mode["socket_mode_enabled"] is True
    assert "request_url" not in socket_mode["event_subscriptions"]


def test_the_request_url_is_the_route_langflow_serves() -> None:
    request_url = _load(EVENTS_API_MANIFEST)["settings"]["event_subscriptions"]["request_url"]
    source = INGRESS_ROUTE.read_text(encoding="utf-8")
    prefix = re.search(r'APIRouter\(prefix="([^"]+)"', source).group(1)
    route = re.search(r'@router\.post\("(/slack/apps/\{registration_id\})"\)', source)

    assert route, "the Slack app route moved; update the manifest's Request URL"
    expected = f"/api/v1{prefix}{route.group(1)}".replace("{registration_id}", "REGISTRATION_ID")
    assert request_url == f"https://LANGFLOW_HOST{expected}"
