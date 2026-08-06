"""Autogenerate compatibility rules for active EXPAND migration windows."""

from alembic.operations import ops

# ``sso_config`` is deliberately in an EXPAND window: released N-1 services
# still need the scalar columns, while N reads the typed JSON representation.
# Alembic therefore sees the retained DB-only columns and nullable typed columns
# as a future CONTRACT migration. Keep this list exact and remove it with that
# contract revision; rolling-compatibility migration tests assert that the
# temporary physical schema remains present and synchronized.
SSO_EXPAND_LEGACY_COLUMNS = frozenset(
    {
        "provider",
        "provider_name",
        "enforce_sso",
        "client_id",
        "discovery_url",
        "redirect_uri",
        "scopes",
        "token_endpoint",
        "authorization_endpoint",
        "jwks_uri",
        "issuer",
    }
)
SSO_EXPAND_NULLABLE_COLUMNS = frozenset({"slug", "display_name", "protocol", "provider_settings"})
_REMOVE_COLUMN_DIFF_LENGTH = 4
_MODIFY_NULLABLE_DIFF_LENGTH = 7


def filter_sso_expand_diffs(diffs: list) -> list:
    """Suppress only schema diffs intentionally deferred to SSO CONTRACT."""
    significant_diffs = []
    for diff in diffs:
        # Alembic can group multiple alter-column operations in a nested list.
        if isinstance(diff, list):
            filtered_group = filter_sso_expand_diffs(diff)
            if filtered_group:
                significant_diffs.append(filtered_group)
            continue
        if not isinstance(diff, tuple):
            significant_diffs.append(diff)
            continue

        if (
            len(diff) >= _REMOVE_COLUMN_DIFF_LENGTH
            and diff[0] == "remove_column"
            and diff[2] == "sso_config"
            and getattr(diff[3], "name", None) in SSO_EXPAND_LEGACY_COLUMNS
        ):
            continue
        if (
            len(diff) >= _MODIFY_NULLABLE_DIFF_LENGTH
            and diff[0] == "modify_nullable"
            and diff[2] == "sso_config"
            and diff[3] in SSO_EXPAND_NULLABLE_COLUMNS
            and diff[5] is True
            and diff[6] is False
        ):
            continue
        significant_diffs.append(diff)

    return significant_diffs


def _filter_sso_expand_operations(container: ops.OpContainer) -> None:
    filtered_operations = []
    for operation in container.ops:
        if isinstance(operation, ops.OpContainer):
            _filter_sso_expand_operations(operation)
            if operation.ops:
                filtered_operations.append(operation)
            continue

        if (
            isinstance(operation, ops.DropColumnOp)
            and operation.table_name == "sso_config"
            and operation.column_name in SSO_EXPAND_LEGACY_COLUMNS
        ):
            continue

        if (
            isinstance(operation, ops.AlterColumnOp)
            and operation.table_name == "sso_config"
            and operation.column_name in SSO_EXPAND_NULLABLE_COLUMNS
            and operation.existing_nullable is True
            and operation.modify_nullable is False
        ):
            # Preserve any type/default/comment change Alembic grouped with the
            # expected nullable diff so real schema drift remains visible.
            operation.modify_nullable = None
            if not operation.has_changes():
                continue

        filtered_operations.append(operation)

    container.ops[:] = filtered_operations


def filter_expand_revision_directives(_context, _revision, directives: list[ops.MigrationScript]) -> None:
    """Apply active EXPAND allowlists to Alembic autogenerate/check output."""
    for directive in directives:
        for upgrade_ops, downgrade_ops in zip(
            directive.upgrade_ops_list,
            directive.downgrade_ops_list,
            strict=True,
        ):
            _filter_sso_expand_operations(upgrade_ops)
            upgrade_ops.reverse_into(downgrade_ops)
