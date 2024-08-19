import os
import warnings
from logging.config import fileConfig

from alembic import context
from loguru import logger
from sqlalchemy import engine_from_config, pool

from langflow.services.database.models import *  # noqa
from langflow.services.database.service import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = os.getenv("LANGFLOW_DATABASE_URL")
    url = url or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    try:
        from langflow.services.database.factory import DatabaseServiceFactory
        from langflow.services.deps import get_db_service
        from langflow.services.manager import initialize_settings_service, service_manager

        initialize_settings_service()
        service_manager.register_factory(DatabaseServiceFactory())
        connectable = get_db_service().engine
    except Exception as e:
        logger.error(f"Error getting database engine: {e}")
        url = os.getenv("LANGFLOW_DATABASE_URL")
        url = url or config.get_main_option("sqlalchemy.url")
        if url:
            config.set_main_option("sqlalchemy.url", url)
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
