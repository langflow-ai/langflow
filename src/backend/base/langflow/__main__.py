import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from sqlmodel import select

from langflow.services.database.models.folder.utils import create_default_folder_if_it_doesnt_exist
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.settings.constants import DEFAULT_SUPERUSER
from langflow.services.utils import initialize_services
from langflow.utils.cli import api_key_banner, display_results, setup_and_run_langflow
from langflow.utils.logger import configure

console = Console()

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to.", envvar="LANGFLOW_HOST"),
    workers: int = typer.Option(1, help="Number of worker processes.", envvar="LANGFLOW_WORKERS"),
    timeout: int = typer.Option(300, help="Worker timeout in seconds.", envvar="LANGFLOW_WORKER_TIMEOUT"),
    port: int = typer.Option(7860, help="Port to listen on.", envvar="LANGFLOW_PORT"),
    flows_path: Optional[Path] = typer.Option(
        None,
        help="Path to the directory containing flows to preload.",
        envvar="LANGFLOW_LOAD_FLOWS_PATH",
    ),
    components_path: Optional[Path] = typer.Option(
        Path(__file__).parent / "components",
        help="Path to the directory containing custom components.",
        envvar="LANGFLOW_COMPONENTS_PATH",
    ),
    # .env file param
    env_file: Path = typer.Option(None, help="Path to the .env file containing environment variables."),
    log_level: str = typer.Option("critical", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
    log_file: Path = typer.Option("logs/langflow.log", help="Path to the log file.", envvar="LANGFLOW_LOG_FILE"),
    cache: Optional[str] = typer.Option(
        envvar="LANGFLOW_LANGCHAIN_CACHE",
        help="Type of cache to use. (InMemoryCache, SQLiteCache)",
        default=None,
    ),
    dev: bool = typer.Option(False, help="Run in development mode (may contain bugs)"),
    path: str = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
        envvar="LANGFLOW_FRONTEND_PATH",
    ),
    open_browser: bool = typer.Option(
        True,
        help="Open the browser after starting the server.",
        envvar="LANGFLOW_OPEN_BROWSER",
    ),
    remove_api_keys: bool = typer.Option(
        False,
        help="Remove API keys from the projects saved in the database.",
        envvar="LANGFLOW_REMOVE_API_KEYS",
    ),
    backend_only: bool = typer.Option(
        False,
        help="Run only the backend server without the frontend.",
        envvar="LANGFLOW_BACKEND_ONLY",
    ),
    store: bool = typer.Option(
        True,
        help="Enables the store features.",
        envvar="LANGFLOW_STORE",
    ),
):
    """
    Run Langflow.
    """
    setup_and_run_langflow(
        host=host,
        workers=workers,
        timeout=timeout,
        port=port,
        flows_path=flows_path,
        components_path=components_path,
        env_file=env_file,
        log_level=log_level,
        log_file=log_file,
        cache=cache,
        dev=dev,
        path=path,
        open_browser=open_browser,
        remove_api_keys=remove_api_keys,
        backend_only=backend_only,
        store=store,
        serve=False,
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to.", envvar="LANGFLOW_HOST"),
    workers: int = typer.Option(1, help="Number of worker processes.", envvar="LANGFLOW_WORKERS"),
    timeout: int = typer.Option(300, help="Worker timeout in seconds.", envvar="LANGFLOW_WORKER_TIMEOUT"),
    port: int = typer.Option(7860, help="Port to listen on.", envvar="LANGFLOW_PORT"),
    components_path: Optional[Path] = typer.Option(
        Path(__file__).parent / "components",
        help="Path to the directory containing custom components.",
        envvar="LANGFLOW_COMPONENTS_PATH",
    ),
    # .env file param
    env_file: Path = typer.Option(None, help="Path to the .env file containing environment variables."),
    log_level: str = typer.Option("critical", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
    log_file: Path = typer.Option("logs/langflow.log", help="Path to the log file.", envvar="LANGFLOW_LOG_FILE"),
    cache: Optional[str] = typer.Option(
        envvar="LANGFLOW_LANGCHAIN_CACHE",
        help="Type of cache to use. (InMemoryCache, SQLiteCache)",
        default=None,
    ),
    dev: bool = typer.Option(False, help="Run in development mode (may contain bugs)"),
    path: str = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
        envvar="LANGFLOW_FRONTEND_PATH",
    ),
    open_browser: bool = typer.Option(
        True,
        help="Open the browser after starting the server.",
        envvar="LANGFLOW_OPEN_BROWSER",
    ),
    remove_api_keys: bool = typer.Option(
        False,
        help="Remove API keys from the projects saved in the database.",
        envvar="LANGFLOW_REMOVE_API_KEYS",
    ),
    store: bool = typer.Option(
        True,
        help="Enables the store features.",
        envvar="LANGFLOW_STORE",
    ),
):
    """Serve Langflow"""
    setup_and_run_langflow(
        host=host,
        workers=workers,
        timeout=timeout,
        port=port,
        components_path=components_path,
        env_file=env_file,
        log_level=log_level,
        log_file=log_file,
        cache=cache,
        dev=dev,
        path=path,
        open_browser=open_browser,
        remove_api_keys=remove_api_keys,
        backend_only=True,
        store=store,
        serve=True,
    )


@app.command()
def superuser(
    username: str = typer.Option(..., prompt=True, help="Username for the superuser."),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for the superuser."),
    log_level: str = typer.Option("error", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
):
    """
    Create a superuser.
    """
    configure(log_level=log_level)
    initialize_services()
    db_service = get_db_service()
    with session_getter(db_service) as session:
        from langflow.services.auth.utils import create_super_user

        if create_super_user(db=session, username=username, password=password):
            # Verify that the superuser was created
            from langflow.services.database.models.user.model import User

            user: User = session.exec(select(User).where(User.username == username)).first()
            if user is None or not user.is_superuser:
                typer.echo("Superuser creation failed.")
                return
            # Now create the first folder for the user
            result = create_default_folder_if_it_doesnt_exist(session, user.id)
            if result:
                typer.echo("Default folder created successfully.")
            else:
                raise RuntimeError("Could not create default folder.")
            typer.echo("Superuser created successfully.")

        else:
            typer.echo("Superuser creation failed.")


# command to copy the langflow database from the cache to the current directory
# because now the database is stored per installation
@app.command()
def copy_db():
    """
    Copy the database files to the current directory.

    This function copies the 'langflow.db' and 'langflow-pre.db' files from the cache directory to the current directory.
    If the files exist in the cache directory, they will be copied to the same directory as this script (__main__.py).

    Returns:
        None
    """
    import shutil

    from platformdirs import user_cache_dir

    cache_dir = Path(user_cache_dir("langflow"))
    db_path = cache_dir / "langflow.db"
    pre_db_path = cache_dir / "langflow-pre.db"
    # It should be copied to the current directory
    # this file is __main__.py and it should be in the same directory as the database
    destination_folder = Path(__file__).parent
    if db_path.exists():
        shutil.copy(db_path, destination_folder)
        typer.echo(f"Database copied to {destination_folder}")
    else:
        typer.echo("Database not found in the cache directory.")
    if pre_db_path.exists():
        shutil.copy(pre_db_path, destination_folder)
        typer.echo(f"Pre-release database copied to {destination_folder}")
    else:
        typer.echo("Pre-release database not found in the cache directory.")


@app.command()
def migration(
    test: bool = typer.Option(True, help="Run migrations in test mode."),
    fix: bool = typer.Option(
        False,
        help="Fix migrations. This is a destructive operation, and should only be used if you know what you are doing.",
    ),
):
    """
    Run or test migrations.
    """
    if fix:
        if not typer.confirm(
            "This will delete all data necessary to fix migrations. Are you sure you want to continue?"
        ):
            raise typer.Abort()

    initialize_services(fix_migration=fix)
    db_service = get_db_service()
    if not test:
        db_service.run_migrations()
    results = db_service.run_migrations_test()
    display_results(results)


@app.command()
def api_key(
    log_level: str = typer.Option("error", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
):
    """
    Creates an API key for the default superuser if AUTO_LOGIN is enabled.

    Args:
        log_level (str, optional): Logging level. Defaults to "error".

    Returns:
        None
    """
    configure(log_level=log_level)
    initialize_services()
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings
    if not auth_settings.AUTO_LOGIN:
        typer.echo("Auto login is disabled. API keys cannot be created through the CLI.")
        return
    with session_scope() as session:
        from langflow.services.database.models.user.model import User

        superuser = session.exec(select(User).where(User.username == DEFAULT_SUPERUSER)).first()
        if not superuser:
            typer.echo("Default superuser not found. This command requires a superuser and AUTO_LOGIN to be enabled.")
            return
        from langflow.services.database.models.api_key import ApiKey, ApiKeyCreate
        from langflow.services.database.models.api_key.crud import create_api_key, delete_api_key

        api_key = session.exec(select(ApiKey).where(ApiKey.user_id == superuser.id)).first()
        if api_key:
            delete_api_key(session, api_key.id)

        api_key_create = ApiKeyCreate(name="CLI")
        unmasked_api_key = create_api_key(session, api_key_create, user_id=superuser.id)
        session.commit()
        # Create a banner to display the API key and tell the user it won't be shown again
        api_key_banner(unmasked_api_key)


def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app()


if __name__ == "__main__":
    main()
