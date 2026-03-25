"""add deployment guard triggers

Revision ID: 97c9a98c9c01
Revises: 8255e9fc18d9
Create Date: 2026-03-25 00:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97c9a98c9c01"  # pragma: allowlist secret
down_revision: str | None = "8255e9fc18d9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upgrade_postgresql() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_flow_version_delete_if_deployed()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM flow_version_deployment_attachment
                WHERE flow_version_id = OLD.id
            ) THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:'
                    || 'Cannot delete flow version because it is attached to one or more deployments. '
                    || 'Detach it from all deployments first.';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_flow_version_delete_if_deployed
        BEFORE DELETE ON flow_version
        FOR EACH ROW
        EXECUTE FUNCTION prevent_flow_version_delete_if_deployed();
        """
    )

    op.execute(
        """
        CREATE FUNCTION prevent_folder_delete_if_has_deployments()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM deployment
                WHERE project_id = OLD.id
            ) THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:'
                    || 'Cannot delete project because it contains one or more deployments. '
                    || 'Remove all deployments first.';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_folder_delete_if_has_deployments
        BEFORE DELETE ON folder
        FOR EACH ROW
        EXECUTE FUNCTION prevent_folder_delete_if_has_deployments();
        """
    )

    op.execute(
        """
        CREATE FUNCTION prevent_flow_move_if_deployed()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.folder_id IS DISTINCT FROM NEW.folder_id THEN
                IF EXISTS (
                    SELECT 1
                    FROM flow_version fv
                    JOIN flow_version_deployment_attachment fvda ON fvda.flow_version_id = fv.id
                    JOIN deployment d ON d.id = fvda.deployment_id
                    WHERE fv.flow_id = OLD.id
                      AND d.project_id = OLD.folder_id
                ) THEN
                    RAISE EXCEPTION '%',
                        'DEPLOYMENT_GUARD:FLOW_DEPLOYED_IN_PROJECT:'
                        || 'Cannot move flow to a different project because it has versions deployed '
                        || 'in the current project. Detach deployed versions first.';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_flow_move_if_deployed
        BEFORE UPDATE ON flow
        FOR EACH ROW
        EXECUTE FUNCTION prevent_flow_move_if_deployed();
        """
    )


def _upgrade_sqlite() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_prevent_flow_version_delete_if_deployed
        BEFORE DELETE ON flow_version
        FOR EACH ROW
        WHEN EXISTS (
            SELECT 1
            FROM flow_version_deployment_attachment
            WHERE flow_version_id = OLD.id
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:'
                || 'Cannot delete flow version because it is attached to one or more deployments. '
                || 'Detach it from all deployments first.'
            );
        END;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_prevent_folder_delete_if_has_deployments
        BEFORE DELETE ON folder
        FOR EACH ROW
        WHEN EXISTS (
            SELECT 1
            FROM deployment
            WHERE project_id = OLD.id
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:'
                || 'Cannot delete project because it contains one or more deployments. '
                || 'Remove all deployments first.'
            );
        END;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_prevent_flow_move_if_deployed
        BEFORE UPDATE OF folder_id ON flow
        FOR EACH ROW
        WHEN OLD.folder_id IS NOT NEW.folder_id
            AND EXISTS (
                SELECT 1
                FROM flow_version fv
                JOIN flow_version_deployment_attachment fvda ON fvda.flow_version_id = fv.id
                JOIN deployment d ON d.id = fvda.deployment_id
                WHERE fv.flow_id = OLD.id
                  AND d.project_id = OLD.folder_id
            )
        BEGIN
            SELECT RAISE(
                ABORT,
                'DEPLOYMENT_GUARD:FLOW_DEPLOYED_IN_PROJECT:'
                || 'Cannot move flow to a different project because it has versions deployed '
                || 'in the current project. Detach deployed versions first.'
            );
        END;
        """
    )


def _downgrade_postgresql() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_move_if_deployed ON flow;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_folder_delete_if_has_deployments ON folder;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_version_delete_if_deployed ON flow_version;")

    op.execute("DROP FUNCTION IF EXISTS prevent_flow_move_if_deployed();")
    op.execute("DROP FUNCTION IF EXISTS prevent_folder_delete_if_has_deployments();")
    op.execute("DROP FUNCTION IF EXISTS prevent_flow_version_delete_if_deployed();")


def _downgrade_sqlite() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_move_if_deployed;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_folder_delete_if_has_deployments;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_version_delete_if_deployed;")


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        _upgrade_postgresql()
        return
    if dialect_name == "sqlite":
        _upgrade_sqlite()
        return

    msg = f"Unsupported dialect for deployment guard migration: {dialect_name}"
    raise RuntimeError(msg)


def downgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        _downgrade_postgresql()
        return
    if dialect_name == "sqlite":
        _downgrade_sqlite()
        return

    msg = f"Unsupported dialect for deployment guard migration: {dialect_name}"
    raise RuntimeError(msg)
