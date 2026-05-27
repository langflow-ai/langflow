"""Tests for built-in authz system roles seeded by the foundations migration."""

from __future__ import annotations

import importlib

_MIGRATION = importlib.import_module("langflow.alembic.versions.7c8d9e0f1a2b_authz_foundations")


def test_three_system_roles_are_seeded():
    """The migration seeds exactly viewer / developer / admin."""
    names = [name for name, _, _ in _MIGRATION._SYSTEM_ROLES]
    assert names == ["viewer", "developer", "admin"]


def test_viewer_has_only_read_and_execute_grants():
    """Viewer should never expose write/delete-class permissions."""
    permissions = set(_MIGRATION._VIEWER_PERMISSIONS)
    forbidden_verbs = {"write", "create", "delete", "admin", "deploy", "ingest", "update"}
    for slug in permissions:
        _, verb = slug.split(":")
        assert verb not in forbidden_verbs, f"viewer must not include {slug}"


def test_developer_includes_viewer_permissions():
    """Developer is a strict superset of viewer."""
    viewer = set(_MIGRATION._VIEWER_PERMISSIONS)
    developer_lookup = {name: perms for name, _, perms in _MIGRATION._SYSTEM_ROLES}
    developer = set(developer_lookup["developer"])
    assert viewer.issubset(developer)


def test_admin_includes_developer_permissions():
    """Admin is a strict superset of developer (and therefore of viewer)."""
    lookup = {name: set(perms) for name, _, perms in _MIGRATION._SYSTEM_ROLES}
    assert lookup["developer"].issubset(lookup["admin"])


def test_admin_has_share_administration_permissions():
    """Admin is the only role with share:* — viewers cannot mint grants."""
    admin = {name: set(perms) for name, _, perms in _MIGRATION._SYSTEM_ROLES}["admin"]
    assert {"share:create", "share:read", "share:update", "share:delete"}.issubset(admin)


def test_permission_slugs_use_resource_action_format():
    """Slugs must match ``{resource}:{action}`` so PolicySync can split them."""
    for _, _, permissions in _MIGRATION._SYSTEM_ROLES:
        for slug in permissions:
            assert slug.count(":") == 1, slug
            resource, verb = slug.split(":")
            assert resource, slug
            assert verb, slug


def test_revision_chain_is_linear_after_api_key_expires_at():
    """Foundations migration follows api_key expires_at migration f6b3ce6845d4."""
    assert _MIGRATION.revision == "7c8d9e0f1a2b"
    assert _MIGRATION.down_revision == "f6b3ce6845d4"
