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

    op.execute(
        """
        CREATE FUNCTION prevent_deployment_project_move()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.project_id IS DISTINCT FROM NEW.project_id THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_PROJECT_MOVE:'
                    || 'Cannot move deployment to a different project. '
                    || 'Re-create it in the target project instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_deployment_project_move
        BEFORE UPDATE ON deployment
        FOR EACH ROW
        EXECUTE FUNCTION prevent_deployment_project_move();
        """
    )

    op.execute(
        """
        CREATE FUNCTION prevent_deployment_provider_account_move()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.deployment_provider_account_id IS DISTINCT FROM NEW.deployment_provider_account_id THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_MOVE:'
                    || 'Cannot move deployment to a different deployment provider account. '
                    || 'Re-create it under the target provider account instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_deployment_provider_account_move
        BEFORE UPDATE ON deployment
        FOR EACH ROW
        EXECUTE FUNCTION prevent_deployment_provider_account_move();
        """
    )

    op.execute(
        """
        CREATE FUNCTION prevent_deployment_provider_account_identity_update()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.provider_tenant_id IS DISTINCT FROM NEW.provider_tenant_id
               OR OLD.provider_url IS DISTINCT FROM NEW.provider_url
               OR OLD.provider_key IS DISTINCT FROM NEW.provider_key THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE:'
                    || 'Cannot modify provider key, provider tenant id, or provider URL '
                    || 'on an existing deployment provider account. '
                    || 'Re-create the account instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_deployment_provider_account_identity_update
        BEFORE UPDATE ON deployment_provider_account
        FOR EACH ROW
        EXECUTE FUNCTION prevent_deployment_provider_account_identity_update();
        """
    )

    op.execute(
        """
        CREATE FUNCTION prevent_cross_project_attachment()
        RETURNS TRIGGER
        AS $$
        DECLARE
            flow_project_id UUID;
            deployment_project_id UUID;
        BEGIN
            SELECT f.folder_id INTO flow_project_id
            FROM flow_version fv
            JOIN flow f ON f.id = fv.flow_id
            WHERE fv.id = NEW.flow_version_id;

            SELECT d.project_id INTO deployment_project_id
            FROM deployment d
            WHERE d.id = NEW.deployment_id;

            IF flow_project_id IS DISTINCT FROM deployment_project_id THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:CROSS_PROJECT_ATTACHMENT:'
                    || 'Cannot attach a flow version to a deployment in a different project.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_cross_project_attachment
        BEFORE INSERT ON flow_version_deployment_attachment
        FOR EACH ROW
        EXECUTE FUNCTION prevent_cross_project_attachment();
        """
    )


def _upgrade_sqlite() -> None:
    op.execute(
        "CREATE TRIGGER trg_prevent_flow_version_delete_if_deployed\n"
        "BEFORE DELETE ON flow_version\n"
        "FOR EACH ROW\n"
        "WHEN EXISTS (\n"
        "    SELECT 1\n"
        "    FROM flow_version_deployment_attachment\n"
        "    WHERE flow_version_id = OLD.id\n"
        ")\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:Cannot delete flow version because it is attached "
        "to one or more deployments. Detach it from all deployments first.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_folder_delete_if_has_deployments\n"
        "BEFORE DELETE ON folder\n"
        "FOR EACH ROW\n"
        "WHEN EXISTS (\n"
        "    SELECT 1\n"
        "    FROM deployment\n"
        "    WHERE project_id = OLD.id\n"
        ")\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:Cannot delete project because it contains one "
        "or more deployments. Remove all deployments first.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_flow_move_if_deployed\n"
        "BEFORE UPDATE OF folder_id ON flow\n"
        "FOR EACH ROW\n"
        "WHEN OLD.folder_id IS NOT NEW.folder_id\n"
        "    AND EXISTS (\n"
        "        SELECT 1\n"
        "        FROM flow_version fv\n"
        "        JOIN flow_version_deployment_attachment fvda ON fvda.flow_version_id = fv.id\n"
        "        JOIN deployment d ON d.id = fvda.deployment_id\n"
        "        WHERE fv.flow_id = OLD.id\n"
        "          AND d.project_id = OLD.folder_id\n"
        "    )\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:FLOW_DEPLOYED_IN_PROJECT:Cannot move flow to a different project because "
        "it has versions deployed in the current project. Detach deployed versions first.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_deployment_project_move\n"
        "BEFORE UPDATE OF project_id ON deployment\n"
        "FOR EACH ROW\n"
        "WHEN OLD.project_id IS NOT NEW.project_id\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_PROJECT_MOVE:Cannot move deployment to a different project. "
        "Re-create it in the target project instead.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_deployment_provider_account_move\n"
        "BEFORE UPDATE OF deployment_provider_account_id ON deployment\n"
        "FOR EACH ROW\n"
        "WHEN OLD.deployment_provider_account_id IS NOT NEW.deployment_provider_account_id\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_MOVE:Cannot move deployment to a different "
        "deployment provider account. Re-create it under the target provider account instead.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_deployment_provider_account_identity_update\n"
        "BEFORE UPDATE OF provider_key, provider_tenant_id, provider_url ON deployment_provider_account\n"
        "FOR EACH ROW\n"
        "WHEN OLD.provider_tenant_id IS NOT NEW.provider_tenant_id\n"
        "  OR OLD.provider_url IS NOT NEW.provider_url\n"
        "  OR OLD.provider_key IS NOT NEW.provider_key\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE:"
        "Cannot modify provider key, provider tenant id, or provider URL "
        "on an existing deployment provider account. "
        "Re-create the account instead.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_cross_project_attachment\n"
        "BEFORE INSERT ON flow_version_deployment_attachment\n"
        "FOR EACH ROW\n"
        "WHEN (\n"
        "    SELECT f.folder_id\n"
        "    FROM flow_version fv\n"
        "    JOIN flow f ON f.id = fv.flow_id\n"
        "    WHERE fv.id = NEW.flow_version_id\n"
        ") IS NOT (\n"
        "    SELECT d.project_id\n"
        "    FROM deployment d\n"
        "    WHERE d.id = NEW.deployment_id\n"
        ")\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:CROSS_PROJECT_ATTACHMENT:"
        "Cannot attach a flow version to a deployment in a different project.'\n"
        "    );\n"
        "END;\n"
    )


def _downgrade_postgresql() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_cross_project_attachment ON flow_version_deployment_attachment;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_identity_update ON deployment_provider_account;"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_move ON deployment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_project_move ON deployment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_move_if_deployed ON flow;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_folder_delete_if_has_deployments ON folder;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_version_delete_if_deployed ON flow_version;")

    # LIFO order: last function created in upgrade is dropped first
    op.execute("DROP FUNCTION IF EXISTS prevent_cross_project_attachment();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_provider_account_identity_update();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_provider_account_move();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_project_move();")
    op.execute("DROP FUNCTION IF EXISTS prevent_flow_move_if_deployed();")
    op.execute("DROP FUNCTION IF EXISTS prevent_folder_delete_if_has_deployments();")
    op.execute("DROP FUNCTION IF EXISTS prevent_flow_version_delete_if_deployed();")


def _downgrade_sqlite() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_cross_project_attachment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_identity_update;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_move;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_project_move;")
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
