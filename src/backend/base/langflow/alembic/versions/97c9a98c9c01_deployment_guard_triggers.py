"""add deployment guard triggers

Revision ID: 97c9a98c9c01
Revises: 8255e9fc18d9
Create Date: 2026-03-25 00:00:00.000000

Phase: EXPAND

This migration adds DB triggers to enforce constraints for every write path
(API, scripts, direct SQL, and concurrent workers). Each guard prevents rows
from staying syntactically valid while becoming semantically wrong relative to
related tables.

Trigger contract and rationale:

1) trg_prevent_flow_move_if_deployed (flow UPDATE folder_id)
   Block flow.folder_id updates when the same flow still has attachment rows
   through flow_version -> flow_version_deployment_attachment -> deployment
   in the old project (deployment.project_id = OLD.folder_id).

2) trg_prevent_deployment_project_move (deployment UPDATE project_id)
   Block deployment.project_id updates because attachment rows keep
   deployment_id fixed; changing project_id would make that deployment.id
   point across project boundaries relative to attached flow_version -> flow.

3) trg_prevent_deployment_resource_key_update (deployment UPDATE resource_key)
   Block changes to deployment.resource_key because it is the provider
   owned id for that deployment.
   The consequence of changing the resource_key is
   that any rows in the flow_version_deployment_attachment table
   referencing the langflow owned deployment id would now
   silently point to a different deployment resource in the provider,
   corrupting the flow_version_deployment_attachment F.K reference.

4) trg_prevent_deployment_provider_account_move
   (deployment UPDATE deployment_provider_account_id)
   Block changing the FK reference
   deployment.deployment_provider_account_id -> deployment_provider_account.id.
   For a fixed deployment.id/resource_key, repointing that FK
   changes ownership of the deployment to an invalid provider account.

5) trg_prevent_deployment_provider_account_identity_update
   (deployment_provider_account UPDATE provider_key/provider_tenant_id/provider_url)
   Block edits to provider account identity fields so linked deployments do
   not silently point ownership to an invalid provider account.

Note:
   This identity immutability guard is intentionally GLOBAL for the current
   schema shape (provider_key + provider_url + provider_tenant_id). If a
   future provider uses a different identity tuple (for example
   AWS account_id/region without URL/tenant), handle that via an additive schema
   migration and replace this global trigger with provider-specific identity
   guards in that migration.

6) trg_prevent_cross_project_attachment
   (flow_version_deployment_attachment INSERT)
   Block attaching a flow version to a deployment in a different project.
   flow_version -> flow.folder_id and deployment.project_id do not match.
   Protecting project-scoped deployment boundaries.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97c9a98c9c01"  # pragma: allowlist secret
down_revision: str | None = "8255e9fc18d9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upgrade_postgresql() -> None:
    # Guard 1:
    # Block flow.folder_id updates when the same flow still has attachment rows
    # through flow_version -> flow_version_deployment_attachment -> deployment
    # in the old project (deployment.project_id = OLD.folder_id).
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
                        || 'UPDATE flow.folder_id blocked: versions of this flow remain attached to deployments '
                        || 'in the current project scope (OLD.folder_id). '
                        || 'Remove rows from flow_version_deployment_attachment for this flow in the current '
                        || 'project before changing flow.folder_id.';
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

    # Guard 2:
    # Block deployment.project_id updates because attachment rows keep
    # deployment_id fixed; changing project_id would make that deployment.id
    # point across project boundaries relative to attached flow_version -> flow.
    op.execute(
        """
        CREATE FUNCTION prevent_deployment_project_move()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.project_id IS DISTINCT FROM NEW.project_id THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_PROJECT_MOVE:'
                    || 'UPDATE deployment.project_id blocked: project scope is immutable for existing deployments. '
                    || 'Re-create the deployment in the target project.';
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

    # Guard 3:
    # Block changes to deployment.resource_key because it is the provider
    # owned id for that deployment.
    # The consequence of changing the resource_key is
    # that any rows in the flow_version_deployment_attachment table
    # referencing the langflow owned deployment id would now
    # silently point to a different deployment resource in the provider,
    # corrupting the flow_version_deployment_attachment F.K reference.
    op.execute(
        """
        CREATE FUNCTION prevent_deployment_resource_key_update()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.resource_key IS DISTINCT FROM NEW.resource_key THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_RESOURCE_KEY_UPDATE:'
                    || 'Cannot modify deployment resource key on an existing deployment. Re-create it instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_deployment_resource_key_update
        BEFORE UPDATE ON deployment
        FOR EACH ROW
        EXECUTE FUNCTION prevent_deployment_resource_key_update();
        """
    )

    # Guard 4:
    # Block changing the FK reference
    # deployment.deployment_provider_account_id -> deployment_provider_account.id.
    # For a fixed deployment.id/resource_key, repointing that FK
    # changes ownership of the deployment to an invalid provider account.
    op.execute(
        """
        CREATE FUNCTION prevent_deployment_provider_account_move()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF OLD.deployment_provider_account_id IS DISTINCT FROM NEW.deployment_provider_account_id THEN
                RAISE EXCEPTION '%',
                    'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_MOVE:'
                    || 'UPDATE deployment.deployment_provider_account_id blocked: provider account scope is immutable '
                    || 'for existing deployments. Re-create the deployment under the target provider account.';
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

    # Guard 5:
    # Block edits to provider account identity fields so linked deployments do
    # not silently point ownership to an invalid provider account.
    # NOTE:
    # This identity immutability guard is intentionally GLOBAL for the current
    # schema shape (provider_key + provider_url + provider_tenant_id). If a
    # future provider uses a different identity tuple (for example
    # account_id/region without URL/tenant), handle that via an additive schema
    # migration and replace this global trigger with provider-specific identity
    # guards in that migration.
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
                    || 'UPDATE deployment_provider_account blocked: provider_key, provider_tenant_id, and '
                    || 'provider_url are immutable on existing accounts. Re-create the account instead.';
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

    # Guard 6:
    # Block attaching a flow version to a deployment in a different project.
    # flow_version -> flow.folder_id and deployment.project_id do not match.
    # Protecting project-scoped deployment boundaries.
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
                    || 'INSERT flow_version_deployment_attachment blocked: flow project scope (flow.folder_id) '
                    || 'does not match deployment project scope (deployment.project_id).';
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
    # SQLite mirrors PostgreSQL trigger behavior for local/dev/test.
    # Detailed rationale for each guard is documented in _upgrade_postgresql().
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
        "        'DEPLOYMENT_GUARD:FLOW_DEPLOYED_IN_PROJECT:UPDATE flow.folder_id blocked: versions of this "
        "flow remain attached to deployments in the current project scope (OLD.folder_id). Remove rows from "
        "flow_version_deployment_attachment for this flow in the current project before changing "
        "flow.folder_id.'\n"
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
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_PROJECT_MOVE:UPDATE deployment.project_id blocked: project "
        "scope is immutable for existing deployments. Re-create the deployment in the target project.'\n"
        "    );\n"
        "END;\n"
    )

    op.execute(
        "CREATE TRIGGER trg_prevent_deployment_resource_key_update\n"
        "BEFORE UPDATE OF resource_key ON deployment\n"
        "FOR EACH ROW\n"
        "WHEN OLD.resource_key IS NOT NEW.resource_key\n"
        "BEGIN\n"
        "    SELECT RAISE(\n"
        "        ABORT,\n"
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_RESOURCE_KEY_UPDATE:Cannot modify deployment resource key on an "
        "existing deployment. Re-create it instead.'\n"
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
        "        'DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_MOVE:UPDATE "
        "deployment.deployment_provider_account_id blocked: provider account scope is immutable for existing "
        "deployments. Re-create the deployment under the target provider account.'\n"
        "    );\n"
        "END;\n"
    )

    # Keep parity with the PostgreSQL note above: the current SQLite trigger is
    # global because the current schema has one identity tuple. Future provider-
    # specific identity fields should be introduced in a new migration that
    # replaces this trigger with provider-specific guards.
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
        "UPDATE deployment_provider_account blocked: provider_key, provider_tenant_id, and "
        "provider_url are immutable on existing accounts. Re-create the account instead.'\n"
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
        "INSERT flow_version_deployment_attachment blocked: flow project scope (flow.folder_id) does not "
        "match deployment project scope (deployment.project_id).'\n"
        "    );\n"
        "END;\n"
    )


def _downgrade_postgresql() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_cross_project_attachment ON flow_version_deployment_attachment;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_identity_update ON deployment_provider_account;"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_move ON deployment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_resource_key_update ON deployment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_project_move ON deployment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_move_if_deployed ON flow;")

    # LIFO order: last function created in upgrade is dropped first
    op.execute("DROP FUNCTION IF EXISTS prevent_cross_project_attachment();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_provider_account_identity_update();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_provider_account_move();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_resource_key_update();")
    op.execute("DROP FUNCTION IF EXISTS prevent_deployment_project_move();")
    op.execute("DROP FUNCTION IF EXISTS prevent_flow_move_if_deployed();")


def _downgrade_sqlite() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_cross_project_attachment;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_identity_update;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_provider_account_move;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_resource_key_update;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_deployment_project_move;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_flow_move_if_deployed;")


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
