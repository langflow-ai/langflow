import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alembic.util.exc import CommandError
from loguru import logger
from sqlmodel import Session, select, text

from langflow.services.database.models import TransactionTable
from langflow.services.deps import get_monitor_service

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService

from typing import Dict, List


def migrate_messages_from_monitor_service_to_database(session: Session) -> bool:
    from langflow.schema.message import Message
    from langflow.services.database.models.message import MessageTable

    try:
        monitor_service = get_monitor_service()
        messages_df = monitor_service.get_messages()
    except Exception as e:
        if "Table with name messages does not exist" in str(e):
            logger.debug(f"Error retrieving messages from monitor service: {e}")
        else:
            logger.warning(f"Error retrieving messages from monitor service: {e}")
        return False

    if messages_df.empty:
        logger.info("No messages to migrate.")
        return True

    original_messages: List[Dict] = messages_df.to_dict(orient="records")

    db_messages = session.exec(select(MessageTable)).all()
    db_messages = [msg[0] for msg in db_messages]  # type: ignore
    db_msg_dict = {(msg.text, msg.timestamp.isoformat(), str(msg.flow_id), msg.session_id): msg for msg in db_messages}
    # Filter out messages that already exist in the database
    original_messages_filtered = []
    for message in original_messages:
        key = (message["text"], message["timestamp"].isoformat(), str(message["flow_id"]), message["session_id"])
        if key not in db_msg_dict:
            original_messages_filtered.append(message)
    if not original_messages_filtered:
        logger.info("No messages to migrate.")
        return True
    try:
        # Bulk insert messages
        session.bulk_insert_mappings(
            MessageTable,  # type: ignore
            [MessageTable.from_message(Message(**msg)).model_dump() for msg in original_messages_filtered],
        )
        session.commit()
    except Exception as e:
        logger.error(f"Error during message insertion: {str(e)}")
        session.rollback()
        return False

    # Create a dictionary for faster lookup

    all_ok = True
    for orig_msg in original_messages_filtered:
        key = (orig_msg["text"], orig_msg["timestamp"].isoformat(), str(orig_msg["flow_id"]), orig_msg["session_id"])
        matching_db_msg = db_msg_dict.get(key)

        if matching_db_msg is None:
            logger.warning(f"Message not found in database: {orig_msg}")
            all_ok = False
        else:
            # Validate other fields
            if any(getattr(matching_db_msg, k) != v for k, v in orig_msg.items() if k != "index"):
                logger.warning(f"Message mismatch in database: {orig_msg}")
                all_ok = False

    if all_ok:
        messages_ids = [message["index"] for message in original_messages]
        monitor_service.delete_messages(messages_ids)
        logger.info("Migration completed successfully. Original messages deleted.")
    else:
        logger.warning("Migration completed with errors. Original messages not deleted.")

    return all_ok


def initialize_database(fix_migration: bool = False):
    logger.debug("Initializing database")
    from langflow.services.deps import get_db_service

    database_service: "DatabaseService" = get_db_service()
    try:
        database_service.create_db_and_tables()
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.error(f"Error creating DB and tables: {exc}")
            raise RuntimeError("Error creating DB and tables") from exc
    try:
        database_service.check_schema_health()
    except Exception as exc:
        logger.error(f"Error checking schema health: {exc}")
        raise RuntimeError("Error checking schema health") from exc
    try:
        database_service.run_migrations(fix=fix_migration)
    except CommandError as exc:
        # if "overlaps with other requested revisions" or "Can't locate revision identified by"
        # are not in the exception, we can't handle it
        if "overlaps with other requested revisions" not in str(
            exc
        ) and "Can't locate revision identified by" not in str(exc):
            raise exc
        # This means there's wrong revision in the DB
        # We need to delete the alembic_version table
        # and run the migrations again
        logger.warning("Wrong revision in DB, deleting alembic_version table and running migrations again")
        with session_getter(database_service) as session:
            session.exec(text("DROP TABLE alembic_version"))
        database_service.run_migrations(fix=fix_migration)
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.error(exc)
        raise exc
    logger.debug("Database initialized")


@contextmanager
def session_getter(db_service: "DatabaseService"):
    try:
        session = Session(db_service.engine)
        yield session
    except Exception as e:
        logger.error("Session rollback because of exception:", e)
        session.rollback()
        raise
    finally:
        session.close()


@dataclass
class Result:
    name: str
    type: str
    success: bool


@dataclass
class TableResults:
    table_name: str
    results: list[Result]


def migrate_transactions_from_monitor_service_to_database(session: Session) -> None:
    try:
        monitor_service = get_monitor_service()
        batch = monitor_service.get_transactions()
    except Exception as e:
        if "Table with name transactions does not exist" in str(e):
            logger.debug(f"Error retrieving transactions from monitor service: {e}")
        else:
            logger.warning(f"Error retrieving transactions from monitor service: {e}")
        return

    if not batch:
        logger.debug("No transactions to migrate.")
        return
    to_delete = []
    while batch:
        logger.debug(f"Migrating {len(batch)} transactions")
        for row in batch:
            tt = TransactionTable(
                flow_id=row["flow_id"],
                status=row["status"],
                error=row["error"],
                timestamp=row["timestamp"],
                vertex_id=row["vertex_id"],
                inputs=json.loads(row["inputs"]) if row["inputs"] else None,
                outputs=json.loads(row["outputs"]) if row["outputs"] else None,
                target_id=row["target_id"],
            )
            to_delete.append(row["index"])
            session.add(tt)
        session.commit()
        monitor_service.delete_transactions(to_delete)
        batch = monitor_service.get_transactions()
    logger.debug("Transactions migrations completed.")
