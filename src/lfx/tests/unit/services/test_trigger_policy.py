"""The trigger facet is a stable, optional part of the shared policy bundle."""

import pytest
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot, policy_bundle_content_hash


def _hash(**kwargs):
    return policy_bundle_content_hash(
        approved_provider_ids=(), blocked_component_keys=(), blocked_template_keys=(), **kwargs
    )


def test_unset_trigger_policy_preserves_legacy_hash_and_allows_existing_kinds():
    assert _hash(approved_trigger_kinds=None) == _hash()
    snapshot = PolicyBundleSnapshot()
    assert snapshot.allows_trigger_kind("google.gmail")
    assert snapshot.allows_trigger_kind("schedule")


def test_explicit_trigger_ceiling_denies_unapproved_provider_and_kind():
    snapshot = PolicyBundleSnapshot(approved_trigger_kinds=frozenset({"google.calendar", "slack.message"}))
    assert snapshot.allows_trigger_kind("google.calendar")
    assert snapshot.allows_trigger_kind("slack.message")
    assert not snapshot.allows_trigger_kind("google.gmail")
    assert not snapshot.allows_trigger_kind("microsoft.mail")
    assert not snapshot.allows_trigger_kind("schedule")


def test_empty_trigger_ceiling_denies_all_and_has_distinct_content_hash():
    assert not PolicyBundleSnapshot(approved_trigger_kinds=frozenset()).allows_trigger_kind("slack.message")
    assert _hash(approved_trigger_kinds=()) != _hash()


def test_trigger_content_hash_is_order_independent_and_changes_for_a_kind():
    assert _hash(approved_trigger_kinds=["slack.message", "google.gmail", "slack.message"]) == _hash(
        approved_trigger_kinds=["google.gmail", "slack.message"]
    )
    assert _hash(approved_trigger_kinds=["google.gmail"]) != _hash(approved_trigger_kinds=["google.calendar"])


def test_publishing_same_revision_with_changed_trigger_policy_is_refused():
    service = PolicyBundleService()
    service.publish(PolicyBundleSnapshot(revision=1, approved_trigger_kinds=frozenset({"google.gmail"})))
    with pytest.raises(ValueError, match="conflicting content"):
        service.publish(PolicyBundleSnapshot(revision=1, approved_trigger_kinds=frozenset()))
