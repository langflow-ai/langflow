"""The bundle manifest, the capability manifest, and the components agree."""

from __future__ import annotations

import json
from pathlib import Path

import lfx_slack
import pytest
from lfx.extension import load_extension, validate_extension
from lfx.inputs.inputs import ConnectionRefInput
from lfx.integrations.capabilities import IntegrationCapabilityManifest

BUNDLE_ROOT = Path(lfx_slack.__file__).parent
MANIFEST_PATH = BUNDLE_ROOT / "components" / "slack" / "capabilities.v1.json"

BOT_CAPABILITIES = {"slack.bot.post", "slack.bot.add_reaction", "slack.bot.list_channel_members"}
USER_CAPABILITIES = {"slack.user.search", "slack.user.read_thread", "slack.user.send", "slack.user.canvas"}
#: One capability per trigger per transport: the Events API on a bot
#: installation, Socket Mode on an app-level token.
TRIGGER_CAPABILITIES = {
    "slack.trigger.message.events_api": ("slack-bot-install", {"hosted", "self_managed"}),
    "slack.trigger.message.socket_mode": ("slack-app-token", {"self_managed", "desktop"}),
    "slack.trigger.reaction.events_api": ("slack-bot-install", {"hosted", "self_managed"}),
    "slack.trigger.reaction.socket_mode": ("slack-app-token", {"self_managed", "desktop"}),
}


def _is_trigger(capability) -> bool:
    return capability.id in TRIGGER_CAPABILITIES


@pytest.fixture(scope="module")
def manifest() -> IntegrationCapabilityManifest:
    return IntegrationCapabilityManifest.model_validate(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def test_extension_validates() -> None:
    result = validate_extension(BUNDLE_ROOT)

    assert result.ok, result.errors


def test_loader_exposes_the_slack_integration() -> None:
    result = load_extension(BUNDLE_ROOT, distribution="lfx-slack")

    assert result.ok, result.errors
    assert len(result.integrations) == 1
    loaded = result.integrations[0]
    assert loaded.provider_id == "slack"
    assert loaded.bundle == "slack"
    assert loaded.capability_manifest.schema_version == 1
    assert {profile.id for profile in loaded.capability_manifest.auth_profiles} == {
        "slack-user-oauth",
        "slack-bot-install",
        "slack-app-token",
    }
    assert len(loaded.capability_manifest.capabilities) == 7 + len(TRIGGER_CAPABILITIES)


def test_every_capability_points_at_an_exported_component(manifest: IntegrationCapabilityManifest) -> None:
    for capability in manifest.capabilities:
        assert capability.component_ref, capability.id
        assert hasattr(lfx_slack, capability.component_ref), capability.component_ref
        component_class = getattr(lfx_slack, capability.component_ref)
        if _is_trigger(capability):
            assert capability.id in component_class.capability_ids
        else:
            assert component_class.capability_id == capability.id


def test_bot_capabilities_are_absent_from_desktop(manifest: IntegrationCapabilityManifest) -> None:
    """Slack desktop redirects may not request bot scopes (matrix fact 5)."""
    for capability in manifest.capabilities:
        contexts = set(capability.deployment_contexts)
        if _is_trigger(capability):
            continue
        if capability.id in BOT_CAPABILITIES:
            assert "desktop" not in contexts, capability.id
            assert contexts == {"hosted", "self_managed", "headless"}
        else:
            assert capability.id in USER_CAPABILITIES
            assert contexts == {"hosted", "self_managed", "desktop", "headless"}


def test_bot_profile_declares_no_desktop_client_type(manifest: IntegrationCapabilityManifest) -> None:
    bot = next(profile for profile in manifest.auth_profiles if profile.id == "slack-bot-install")
    user = next(profile for profile in manifest.auth_profiles if profile.id == "slack-user-oauth")

    assert "desktop" not in bot.client_type_by_context
    assert "desktop" not in bot.owner_by_context
    assert bot.supports_pkce is False
    assert user.supports_pkce is True
    assert user.client_type_by_context["desktop"] == "public"
    # Slack sends scopes comma-separated, not space-separated.
    assert user.scope_separator == ","
    assert bot.scope_separator == ","


def test_policy_keys_are_namespaced_per_identity(manifest: IntegrationCapabilityManifest) -> None:
    keys = {capability.id: capability.policy_keys for capability in manifest.capabilities}

    assert keys["slack.user.search"] == ("integrations.slack.user.search",)
    assert keys["slack.bot.list_channel_members"] == ("integrations.slack.bot.list_channel_members",)
    for capability in manifest.capabilities:
        for key in capability.policy_keys:
            assert key.startswith("integrations.slack.")


def test_component_connection_fields_match_the_manifest(manifest: IntegrationCapabilityManifest) -> None:
    """The palette's connection picker filters on exactly what the manifest declares."""
    for capability in manifest.capabilities:
        if _is_trigger(capability):
            continue
        component_class = getattr(lfx_slack, capability.component_ref)
        connection = next(i for i in component_class.inputs if isinstance(i, ConnectionRefInput))
        assert connection.provider == "slack"
        assert connection.auth_profile_id == capability.auth_profile_id
        assert connection.capabilities == [capability.id]
        assert set(connection.required_scopes) == set(capability.required_scopes)
        assert {(s.scope, s.condition.input) for s in connection.conditional_scopes} == {
            (s.scope, s.condition.input) for s in capability.conditional_scopes
        }
        # Same mapping the Microsoft bundle derives from its manifest. Slack's user
        # and bot scopes share names, so this is what lets the picker flag a bot
        # connection on a user action before the run's token-prefix check does.
        assert connection.identity_kind == {"user_delegated": "user", "bot": "instance"}[capability.identity]


def test_conditional_scope_inputs_exist_on_their_component(manifest: IntegrationCapabilityManifest) -> None:
    """A conditional scope keyed on a non-existent input would silently never activate."""
    for capability in manifest.capabilities:
        if not capability.conditional_scopes:
            continue
        component_class = getattr(lfx_slack, capability.component_ref)
        input_names = {getattr(i, "name", None) for i in component_class.inputs}
        for requirement in capability.conditional_scopes:
            assert requirement.condition.input in input_names, requirement.scope


def test_display_names_follow_the_palette_naming_decision(manifest: IntegrationCapabilityManifest) -> None:
    for capability in manifest.capabilities:
        component_class = getattr(lfx_slack, capability.component_ref)
        assert component_class.display_name == capability.display_name
        assert component_class.display_name.startswith("Slack: ")
        assert component_class.icon == "Slack"


def test_no_component_exposes_a_request_target() -> None:
    """The Slack API root is a constant; nothing in the palette can redirect it."""
    forbidden = {"base_url", "url", "endpoint", "host", "proxy", "api_url"}
    for name in lfx_slack.__all__:
        component_class = getattr(lfx_slack, name)
        input_names = {getattr(i, "name", None) for i in component_class.inputs}
        assert not (input_names & forbidden), name


# --------------------------------------------------------------------------- #
# Trigger capabilities
# --------------------------------------------------------------------------- #


def test_each_trigger_offers_one_capability_per_transport(manifest: IntegrationCapabilityManifest) -> None:
    """The connection a trigger names decides its transport, so each transport is its own capability.

    Socket Mode is absent from hosted (a Marketplace app cannot use it) and the
    Events API from Desktop (Slack has nowhere to deliver to).
    """
    shipped = {capability.id: capability for capability in manifest.capabilities if _is_trigger(capability)}
    assert set(shipped) == set(TRIGGER_CAPABILITIES)
    for capability_id, (profile, contexts) in TRIGGER_CAPABILITIES.items():
        capability = shipped[capability_id]
        assert capability.auth_profile_id == profile
        assert set(capability.deployment_contexts) == contexts
        assert capability.identity == "bot"
        assert capability.risk == "read"


def test_the_app_level_token_profile_is_manual_entry_and_never_hosted(manifest: IntegrationCapabilityManifest) -> None:
    profile = next(profile for profile in manifest.auth_profiles if profile.id == "slack-app-token")

    assert profile.kind == "api_key"
    assert profile.identity == "bot"
    assert profile.default_scopes == ("connections:write",)
    assert "hosted" not in profile.client_type_by_context
    assert profile.supports_refresh is False


def test_socket_mode_capabilities_need_only_the_app_level_scope(manifest: IntegrationCapabilityManifest) -> None:
    for capability in manifest.capabilities:
        if capability.id.endswith(".socket_mode"):
            assert capability.required_scopes == ("connections:write",)


def test_trigger_connection_fields_accept_either_transport(manifest: IntegrationCapabilityManifest) -> None:
    """No profile or scope filter: either Slack connection type can back a trigger."""
    for name in ("SlackOnMessageTriggerComponent", "SlackOnReactionTriggerComponent"):
        component_class = getattr(lfx_slack, name)
        connection = next(i for i in component_class.inputs if isinstance(i, ConnectionRefInput))
        assert connection.provider == "slack"
        assert connection.auth_profile_id == ""
        assert connection.required_scopes == []
        assert connection.ownership_mode == "user"
        assert set(connection.capabilities) == set(component_class.capability_ids)
        assert {c.component_ref for c in manifest.capabilities if c.id in component_class.capability_ids} == {name}
