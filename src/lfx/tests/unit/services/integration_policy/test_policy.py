"""Integration provider ceiling and action deny-list decisions (INT-7, LE-2465)."""

from __future__ import annotations

import re

import pytest
from lfx.integrations.capabilities import IntegrationCapability, IntegrationProvider, OAuthProfile
from lfx.services.integration_policy import (
    BaseIntegrationPolicyService,
    IntegrationPolicyContext,
    IntegrationPolicyError,
    IntegrationPolicyPurpose,
    IntegrationPolicyService,
    IntegrationPolicySnapshot,
    integration_policy_key_provider,
    normalize_integration_policy_key,
)
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot, policy_bundle_content_hash


def _capability(policy_keys: tuple[str, ...] = ("integrations.google.drive.search",)) -> IntegrationCapability:
    return IntegrationCapability(
        id="google.drive.files.search",
        display_name="Drive: Search Files",
        auth_profile_id="user",
        identity="user_delegated",
        required_scopes=("drive.file",),
        policy_keys=policy_keys,
        substrate="sdk",
        maturity="ga",
        deployment_contexts=("hosted",),
        risk="read",
        component_ref="GoogleDriveSearchComponent",
    )


def _snapshot(
    *,
    allowed: frozenset[str],
    candidates: frozenset[str],
    blocked: frozenset[str] = frozenset(),
) -> IntegrationPolicySnapshot:
    return IntegrationPolicySnapshot(
        context=IntegrationPolicyContext(),
        purpose=IntegrationPolicyPurpose.USE,
        candidate_provider_ids=candidates,
        allowed_provider_ids=allowed,
        blocked_action_keys=blocked,
    )


# --------------------------------------------------------------------------- hash


def test_bundle_content_hash_is_stable_when_integration_sets_are_empty() -> None:
    """QA: hash stability when integration sets are empty."""
    legacy = policy_bundle_content_hash(
        approved_provider_ids=("openai",),
        blocked_component_keys=("Prompt",),
        blocked_template_keys=("basic_prompting",),
        blocked_model_keys=("openai::gpt-4",),
    )
    with_defaults = policy_bundle_content_hash(
        approved_provider_ids=("openai",),
        blocked_component_keys=("Prompt",),
        blocked_template_keys=("basic_prompting",),
        blocked_model_keys=("openai::gpt-4",),
        approved_integration_provider_ids=(),
        blocked_integration_action_keys=(),
    )
    assert legacy == with_defaults


@pytest.mark.parametrize(
    "kwargs",
    [
        {"approved_integration_provider_ids": ("google",)},
        {"blocked_integration_action_keys": ("integrations.google.drive.search",)},
    ],
)
def test_bundle_content_hash_changes_when_integration_content_is_set(kwargs: dict) -> None:
    base = policy_bundle_content_hash(
        approved_provider_ids=(),
        blocked_component_keys=(),
        blocked_template_keys=(),
    )
    assert (
        policy_bundle_content_hash(
            approved_provider_ids=(),
            blocked_component_keys=(),
            blocked_template_keys=(),
            **kwargs,
        )
        != base
    )


def test_publish_rejects_same_revision_with_conflicting_integration_content() -> None:
    service = PolicyBundleService()
    first = PolicyBundleSnapshot(revision=3, initialized=True, approved_integration_provider_ids=frozenset({"google"}))
    service.publish(first)
    conflicting = PolicyBundleSnapshot(
        revision=3,
        initialized=True,
        approved_integration_provider_ids=frozenset({"slack"}),
    )
    with pytest.raises(ValueError, match="conflicting content"):
        service.publish(conflicting)


def test_publish_rejects_same_revision_with_conflicting_blocked_action_keys() -> None:
    service = PolicyBundleService()
    service.publish(PolicyBundleSnapshot(revision=2, initialized=True))
    with pytest.raises(ValueError, match="conflicting content"):
        service.publish(
            PolicyBundleSnapshot(
                revision=2,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.google.drive.search"}),
            )
        )


# --------------------------------------------------------------------------- key grammar


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("integrations.google.drive.search", "integrations.google.drive.search"),
        ("  integrations.google.drive.search  ", "integrations.google.drive.search"),
        ("Integrations.Google.Drive.Search", "integrations.google.drive.search"),
        ("integrations.slack.bot.post_message", "integrations.slack.bot.post_message"),
    ],
)
def test_normalize_integration_policy_key_accepts_the_grammar(raw: str, expected: str) -> None:
    assert normalize_integration_policy_key(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "google.drive.search",
        "integrations.google",
        "integrations..search",
        "integrations.google.drive search",
        "integrations.google.drive/search",
    ],
)
def test_normalize_integration_policy_key_rejects_keys_outside_the_grammar(raw: str) -> None:
    with pytest.raises(ValueError, match="Integration action policy keys"):
        normalize_integration_policy_key(raw)


def test_integration_policy_key_provider_returns_the_provider_segment() -> None:
    assert integration_policy_key_provider("integrations.microsoft.mail.send") == "microsoft"


# --------------------------------------------------------------------------- capability manifest grammar


def test_capability_rejects_policy_keys_outside_the_integrations_namespace() -> None:
    with pytest.raises(ValueError, match="Integration action policy keys"):
        _capability(policy_keys=("google.drive.search",))


def test_provider_rejects_capability_policy_keys_of_another_provider() -> None:
    profile = OAuthProfile(id="user", kind="oauth2_authorization_code", identity="user_delegated")
    with pytest.raises(ValueError, match=re.escape("outside 'integrations.google.'")):
        IntegrationProvider(
            provider_id="google",
            display_name="Google",
            auth_profiles=(profile,),
            capabilities=(_capability(policy_keys=("integrations.slack.chat.post",)),),
        )


# --------------------------------------------------------------------------- snapshot decisions


def test_snapshot_blocks_a_provider_outside_the_ceiling() -> None:
    """QA: policy tests cover provider blocking."""
    snapshot = _snapshot(allowed=frozenset({"slack"}), candidates=frozenset({"slack", "google"}))
    assert snapshot.allows_provider("slack")
    assert not snapshot.allows_provider("google")
    assert not snapshot.allows_action("integrations.google.drive.search")
    with pytest.raises(IntegrationPolicyError) as excinfo:
        snapshot.require_provider("google")
    assert excinfo.value.provider_id == "google"
    assert excinfo.value.policy_key is None


def test_snapshot_blocks_one_action_of_an_approved_provider() -> None:
    """QA: policy tests cover action blocking."""
    snapshot = _snapshot(
        allowed=frozenset({"google"}),
        candidates=frozenset({"google"}),
        blocked=frozenset({"integrations.google.drive.search"}),
    )
    assert snapshot.allows_provider("google")
    assert not snapshot.allows_action("integrations.google.drive.search")
    assert snapshot.allows_action("integrations.google.drive.upload")
    with pytest.raises(IntegrationPolicyError) as excinfo:
        snapshot.require_action("integrations.google.drive.search")
    assert excinfo.value.policy_key == "integrations.google.drive.search"


def test_snapshot_blocks_a_capability_when_any_of_its_policy_keys_is_denied() -> None:
    capability = _capability(policy_keys=("integrations.google.drive.search", "integrations.google.drive.read"))
    allowed_snapshot = _snapshot(allowed=frozenset({"google"}), candidates=frozenset({"google"}))
    assert allowed_snapshot.allows_capability(capability)
    blocked_snapshot = _snapshot(
        allowed=frozenset({"google"}),
        candidates=frozenset({"google"}),
        blocked=frozenset({"integrations.google.drive.read"}),
    )
    assert not blocked_snapshot.allows_capability(capability)
    assert blocked_snapshot.blocked_action_key(capability.policy_keys) == "integrations.google.drive.read"


def test_snapshot_denies_malformed_keys_instead_of_passing_them_through() -> None:
    snapshot = _snapshot(allowed=frozenset({"google"}), candidates=frozenset({"google"}))
    assert not snapshot.allows_action("google.drive.search")
    with pytest.raises(IntegrationPolicyError):
        snapshot.require_action("google.drive.search")


def test_snapshot_rejects_allowed_providers_outside_the_candidate_set() -> None:
    with pytest.raises(ValueError, match="must be a subset"):
        _snapshot(allowed=frozenset({"google"}), candidates=frozenset({"slack"}))


# --------------------------------------------------------------------------- OSS default service


def test_oss_default_is_unrestricted_when_no_ceiling_is_configured() -> None:
    """QA: OSS pass-through behavior remains unchanged when no integration policy is set."""
    bundle = PolicyBundleService()
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    snapshot = service.resolve(
        context=IntegrationPolicyContext(),
        candidate_provider_ids=frozenset({"google", "slack"}),
        purpose=IntegrationPolicyPurpose.DISCOVER,
    )
    assert snapshot.allowed_provider_ids == frozenset({"google", "slack"})
    assert snapshot.blocked_action_keys == frozenset()
    assert snapshot.allows_action("integrations.google.drive.search")


def test_oss_default_applies_the_bundle_ceiling_and_deny_list() -> None:
    """QA: policy tests cover user enablement within the operator ceiling."""
    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(
            revision=1,
            initialized=True,
            approved_integration_provider_ids=frozenset({"google"}),
            blocked_integration_action_keys=frozenset({"integrations.google.drive.delete"}),
        )
    )
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    snapshot = service.resolve(
        context=IntegrationPolicyContext(),
        candidate_provider_ids=frozenset({"google", "slack"}),
        purpose=IntegrationPolicyPurpose.USE,
    )
    assert snapshot.allowed_provider_ids == frozenset({"google"})
    assert snapshot.allows_action("integrations.google.drive.search")
    assert not snapshot.allows_action("integrations.google.drive.delete")
    assert not snapshot.allows_action("integrations.slack.chat.post")


def test_oss_default_fails_closed_only_while_a_ceiling_is_active() -> None:
    bundle = PolicyBundleService()
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    bundle.mark_source_unavailable()
    unrestricted = service.get_allowed_provider_ids(
        context=IntegrationPolicyContext(),
        candidate_provider_ids=frozenset({"google"}),
        purpose=IntegrationPolicyPurpose.USE,
    )
    assert set(unrestricted) == {"google"}

    bundle.publish(
        PolicyBundleSnapshot(revision=1, initialized=True, approved_integration_provider_ids=frozenset({"google"}))
    )
    bundle.mark_source_unavailable()
    restricted = service.get_allowed_provider_ids(
        context=IntegrationPolicyContext(),
        candidate_provider_ids=frozenset({"google"}),
        purpose=IntegrationPolicyPurpose.USE,
    )
    assert set(restricted) == set()


def test_default_service_does_not_report_an_external_ceiling() -> None:
    assert IntegrationPolicyService().external_approved_integration_provider_ids is None


# --------------------------------------------------------------------------- caching


class _CountingPolicyService(BaseIntegrationPolicyService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.set_ready()

    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):  # noqa: ARG002
        self.calls += 1
        return candidate_provider_ids


def test_snapshots_are_cached_until_invalidated() -> None:
    service = _CountingPolicyService()
    arguments = {
        "context": IntegrationPolicyContext(user_id="u1"),
        "candidate_provider_ids": frozenset({"google"}),
        "purpose": IntegrationPolicyPurpose.DISCOVER,
    }
    service.resolve(**arguments)
    service.resolve(**arguments)
    assert service.calls == 1
    service.invalidate()
    service.resolve(**arguments)
    assert service.calls == 2


def test_distinct_principals_do_not_share_a_cached_decision() -> None:
    service = _CountingPolicyService()
    service.resolve(
        context=IntegrationPolicyContext(user_id="u1"),
        candidate_provider_ids=frozenset({"google"}),
        purpose=IntegrationPolicyPurpose.USE,
    )
    service.resolve(
        context=IntegrationPolicyContext(user_id="u2"),
        candidate_provider_ids=frozenset({"google"}),
        purpose=IntegrationPolicyPurpose.USE,
    )
    assert service.calls == 2


async def test_async_resolution_uses_the_same_cache() -> None:
    service = _CountingPolicyService()
    arguments = {
        "context": IntegrationPolicyContext(user_id="u1"),
        "candidate_provider_ids": frozenset({"google"}),
        "purpose": IntegrationPolicyPurpose.USE,
    }
    await service.aresolve(**arguments)
    service.resolve(**arguments)
    assert service.calls == 1
