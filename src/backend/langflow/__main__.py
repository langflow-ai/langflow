import platform
import socket
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from multiprocess import cpu_count  # type: ignore
from rich import box
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import select

from langflow.main import setup_app
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.utils import initialize_services, initialize_settings_service
from langflow.utils.logger import configure, logger

console = Console()

app = typer.Typer(no_args_is_help=True)


def get_number_of_workers(workers=None):
    if workers == -1 or workers is None:
        workers = (cpu_count() * 2) + 1
    logger.debug(f"Number of workers: {workers}")
    return workers


def display_results(results):
    """
    Display the results of the migration.
    """
    for table_results in results:
        table = Table(title=f"Migration {table_results.table_name}")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Status")

        for result in table_results.results:
            status = "Success" if result.success else "Failure"
            color = "green" if result.success else "red"
            table.add_row(result.name, result.type, f"[{color}]{status}[/{color}]")

        console.print(table)
        console.print()  # Print a new line


def set_var_for_macos_issue():
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    # we need to set this var is we are running on MacOS
    # otherwise we get an error when running gunicorn

    if platform.system() in ["Darwin"]:
        import os

        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        # https://stackoverflow.com/questions/75747888/uwsgi-segmentation-fault-with-flask-python-app-behind-nginx-after-running-for-2 # noqa
        os.environ["no_proxy"] = "*"  # to avoid error with gunicorn
        logger.debug("Set OBJC_DISABLE_INITIALIZE_FORK_SAFETY to YES to avoid error")


def update_settings(
    config: str,
    cache: Optional[str] = None,
    dev: bool = False,
    remove_api_keys: bool = False,
    components_path: Optional[Path] = None,
    store: bool = False,
):
    """Update the settings from a config file."""

    # Check for database_url in the environment variables
    initialize_settings_service()
    settings_service = get_settings_service()
    if config:
        logger.debug(f"Loading settings from {config}")
        settings_service.settings.update_from_yaml(config, dev=dev)
    if remove_api_keys:
        logger.debug(f"Setting remove_api_keys to {remove_api_keys}")
        settings_service.settings.update_settings(REMOVE_API_KEYS=remove_api_keys)
    if cache:
        logger.debug(f"Setting cache to {cache}")
        settings_service.settings.update_settings(CACHE=cache)
    if components_path:
        logger.debug(f"Adding component path {components_path}")
        settings_service.settings.update_settings(COMPONENTS_PATH=components_path)
    if not store:
        logger.debug("Setting store to False")
        settings_service.settings.update_settings(STORE=False)


def version_callback(value: bool):
    """
    Show the version and exit.
    """
    from langflow import __version__

    if value:
        typer.echo(f"Langflow Version: {__version__}")
        raise typer.Exit()


@app.callback()
def main_entry_point(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show the version and exit."
    ),
):
    """
    Main entry point for the Langflow CLI.
    """
    pass


@app.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to.", envvar="LANGFLOW_HOST"),
    workers: int = typer.Option(1, help="Number of worker processes.", envvar="LANGFLOW_WORKERS"),
    timeout: int = typer.Option(300, help="Worker timeout in seconds."),
    port: int = typer.Option(7860, help="Port to listen on.", envvar="LANGFLOW_PORT"),
    components_path: Optional[Path] = typer.Option(
        Path(__file__).parent / "components",
        help="Path to the directory containing custom components.",
        envvar="LANGFLOW_COMPONENTS_PATH",
    ),
    config: str = typer.Option(Path(__file__).parent / "config.yaml", help="Path to the configuration file."),
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
    Run the Langflow.
    """

    set_var_for_macos_issue()
    # override env variables with .env file

    if env_file:
        load_dotenv(env_file, override=True)

    configure(log_level=log_level, log_file=log_file)
    update_settings(
        config,
        dev=dev,
        remove_api_keys=remove_api_keys,
        cache=cache,
        components_path=components_path,
        store=store,
    )
    # create path object if path is provided
    static_files_dir: Optional[Path] = Path(path) if path else None
    app = setup_app(static_files_dir=static_files_dir, backend_only=backend_only)
    # check if port is being used
    if is_port_in_use(port, host):
        port = get_free_port(port)

    options = {
        "bind": f"{host}:{port}",
        "workers": get_number_of_workers(workers),
        "timeout": timeout,
    }

    # Define an env variable to know if we are just testing the server
    if "pytest" in sys.modules:
        return

    if platform.system() in ["Windows"]:
        # Run using uvicorn on MacOS and Windows
        # Windows doesn't support gunicorn
        # MacOS requires an env variable to be set to use gunicorn
        run_on_windows(host, port, log_level, options, app)
    else:
        # Run using gunicorn on Linux
        run_on_mac_or_linux(host, port, log_level, options, app)


def run_on_mac_or_linux(host, port, log_level, options, app):
    print_banner(host, port)
    run_langflow(host, port, log_level, options, app)


def run_on_windows(host, port, log_level, options, app):
    """
    Run the Langflow server on Windows.
    """
    print_banner(host, port)
    run_langflow(host, port, log_level, options, app)


def is_port_in_use(port, host="localhost"):
    """
    Check if a port is in use.

    Args:
        port (int): The port number to check.
        host (str): The host to check the port on. Defaults to 'localhost'.

    Returns:
        bool: True if the port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def get_free_port(port):
    """
    Given a used port, find a free port.

    Args:
        port (int): The port number to check.

    Returns:
        int: A free port number.
    """
    while is_port_in_use(port):
        port += 1
    return port


def print_banner(host, port):
    # console = Console()

    word = "Langflow"
    colors = ["#3300cc"]

    styled_word = ""

    for i, char in enumerate(word):
        color = colors[i % len(colors)]
        styled_word += f"[{color}]{char}[/]"

    # Title with emojis and gradient text
    title = (
        f"[bold]Welcome to :chains: {styled_word} [/bold]\n\n"
        f"Access [link=http://{host}:{port}]http://{host}:{port}[/link]"
    )
    info_text = (
        "Collaborate, and contribute at our "
        "[bold][link=https://github.com/logspace-ai/langflow]GitHub Repo[/link][/bold] :rocket:"
    )

    # Create a panel with the title and the info text, and a border around it
    panel = Panel(f"{title}\n{info_text}", box=box.ROUNDED, border_style="blue", expand=False)

    # Print the banner with a separator line before and after
    rprint(panel)


def run_langflow(host, port, log_level, options, app):
    """
    Run Langflow server on localhost
    """
    try:
        if platform.system() in ["Windows", "Darwin"]:
            # Run using uvicorn on MacOS and Windows
            # Windows doesn't support gunicorn
            # MacOS requires an env variable to be set to use gunicorn

            import uvicorn

            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level=log_level,
            )
        else:
            from langflow.server import LangflowApplication

            LangflowApplication(app, options).run()
    except KeyboardInterrupt:
        logger.info("Shutting down server")
        sys.exit(0)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


@app.command()
def superuser(
    username: str = typer.Option(..., prompt=True, help="Username for the superuser."),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for the superuser."),
    log_level: str = typer.Option("critical", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
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

            typer.echo("Superuser created successfully.")

        else:
            typer.echo("Superuser creation failed.")


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


def main():
    app()


if __name__ == "__main__":
    main()
