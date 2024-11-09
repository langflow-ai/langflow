import asyncio
import inspect
import platform
import socket
import sys
import time
import warnings
from pathlib import Path

import click
import httpx
import typer
from dotenv import load_dotenv
from httpx import HTTPError
from multiprocess import cpu_count
from multiprocess.context import Process
from packaging import version as pkg_version
from rich import box
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import select

from langflow.logging.logger import configure, logger
from langflow.main import setup_app
from langflow.services.database.models.folder.utils import (
    create_default_folder_if_it_doesnt_exist,
)
from langflow.services.database.utils import session_getter
from langflow.services.deps import async_session_scope, get_db_service, get_settings_service
from langflow.services.settings.constants import DEFAULT_SUPERUSER
from langflow.services.utils import initialize_services
from langflow.utils.version import fetch_latest_version, get_version_info
from langflow.utils.version import is_pre_release as langflow_is_pre_release

console = Console()

app = typer.Typer(no_args_is_help=True)


def get_number_of_workers(workers=None):
    if workers == -1 or workers is None:
        workers = (cpu_count() * 2) + 1
    logger.debug(f"Number of workers: {workers}")
    return workers


def display_results(results) -> None:
    """Display the results of the migration."""
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


def set_var_for_macos_issue() -> None:
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    # we need to set this var is we are running on MacOS
    # otherwise we get an error when running gunicorn

    if platform.system() == "Darwin":
        import os

        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        # https://stackoverflow.com/questions/75747888/uwsgi-segmentation-fault-with-flask-python-app-behind-nginx-after-running-for-2 # noqa: E501
        os.environ["no_proxy"] = "*"  # to avoid error with gunicorn
        logger.debug("Set OBJC_DISABLE_INITIALIZE_FORK_SAFETY to YES to avoid error")


@app.command()
def run(
    *,
    host: str | None = typer.Option(None, help="Host to bind the server to.", show_default=False),
    workers: int | None = typer.Option(None, help="Number of worker processes.", show_default=False),
    worker_timeout: int | None = typer.Option(None, help="Worker timeout in seconds.", show_default=False),
    port: int | None = typer.Option(None, help="Port to listen on.", show_default=False),
    components_path: Path | None = typer.Option(
        Path(__file__).parent / "components",
        help="Path to the directory containing custom components.",
        show_default=False,
    ),
    # .env file param
    env_file: Path | None = typer.Option(
        None,
        help="Path to the .env file containing environment variables.",
        show_default=False,
    ),
    log_level: str | None = typer.Option(None, help="Logging level.", show_default=False),
    log_file: Path | None = typer.Option(None, help="Path to the log file.", show_default=False),
    cache: str | None = typer.Option(  # noqa: ARG001
        None,
        help="Type of cache to use. (InMemoryCache, SQLiteCache)",
        show_default=False,
    ),
    dev: bool | None = typer.Option(None, help="Run in development mode (may contain bugs)", show_default=False),  # noqa: ARG001
    frontend_path: str | None = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
        show_default=False,
    ),
    open_browser: bool | None = typer.Option(
        None,
        help="Open the browser after starting the server.",
        show_default=False,
    ),
    remove_api_keys: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Remove API keys from the projects saved in the database.",
        show_default=False,
    ),
    backend_only: bool | None = typer.Option(
        None,
        help="Run only the backend server without the frontend.",
        show_default=False,
    ),
    store: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Enables the store features.",
        show_default=False,
    ),
    auto_saving: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines if the auto save is enabled.",
        show_default=False,
    ),
    auto_saving_interval: int | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the debounce time for the auto save.",
        show_default=False,
    ),
    health_check_max_retries: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the number of retries for the health check.",
        show_default=False,
    ),
    max_file_size_upload: int | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the maximum file size for the upload in MB.",
        show_default=False,
    ),
) -> None:
    """Run Langflow."""
    if env_file:
        load_dotenv(env_file, override=True)

    configure(log_level=log_level, log_file=log_file)
    logger.debug(f"Loading config from file: '{env_file}'" if env_file else "No env_file provided.")
    set_var_for_macos_issue()
    settings_service = get_settings_service()

    frame = inspect.currentframe()
    valid_args: list = []
    values: dict = {}
    if frame is not None:
        arguments, _, _, values = inspect.getargvalues(frame)
        valid_args = [arg for arg in arguments if values[arg] is not None]

    for arg in valid_args:
        if arg == "components_path":
            settings_service.settings.update_settings(components_path=components_path)
        elif hasattr(settings_service.settings, arg):
            settings_service.set(arg, values[arg])
        logger.debug(f"Loading config from cli parameter '{arg}': '{values[arg]}'")

    host = settings_service.settings.host
    port = settings_service.settings.port
    workers = settings_service.settings.workers
    worker_timeout = settings_service.settings.worker_timeout
    log_level = settings_service.settings.log_level
    frontend_path = settings_service.settings.frontend_path
    backend_only = settings_service.settings.backend_only

    # create path object if frontend_path is provided
    static_files_dir: Path | None = Path(frontend_path) if frontend_path else None

    app = setup_app(static_files_dir=static_files_dir, backend_only=backend_only)
    # check if port is being used
    if is_port_in_use(port, host):
        port = get_free_port(port)

    options = {
        "bind": f"{host}:{port}",
        "workers": get_number_of_workers(workers),
        "timeout": worker_timeout,
    }

    # Define an env variable to know if we are just testing the server
    if "pytest" in sys.modules:
        return
    process: Process | None = None
    try:
        if platform.system() == "Windows":
            # Run using uvicorn on MacOS and Windows
            # Windows doesn't support gunicorn
            # MacOS requires an env variable to be set to use gunicorn
            run_on_windows(host, port, log_level, options, app)
        else:
            # Run using gunicorn on Linux
            process = run_on_mac_or_linux(host, port, log_level, options, app)
        if open_browser and not backend_only:
            click.launch(f"http://{host}:{port}")
        if process:
            process.join()
    except KeyboardInterrupt:
        if process is not None:
            process.terminate()
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        logger.exception(e)
        sys.exit(1)


def wait_for_server_ready(host, port) -> None:
    """Wait for the server to become ready by polling the health endpoint."""
    status_code = 0
    while status_code != httpx.codes.OK:
        try:
            status_code = httpx.get(f"http://{host}:{port}/health").status_code
        except HTTPError:
            time.sleep(1)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error while waiting for the server to become ready.")
            time.sleep(1)


def run_on_mac_or_linux(host, port, log_level, options, app):
    webapp_process = Process(target=run_langflow, args=(host, port, log_level, options, app))
    webapp_process.start()
    wait_for_server_ready(host, port)

    print_banner(host, port)
    return webapp_process


def run_on_windows(host, port, log_level, options, app) -> None:
    """Run the Langflow server on Windows."""
    print_banner(host, port)
    run_langflow(host, port, log_level, options, app)


def is_port_in_use(port, host="localhost"):
    """Check if a port is in use.

    Args:
        port (int): The port number to check.
        host (str): The host to check the port on. Defaults to 'localhost'.

    Returns:
        bool: True if the port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def get_free_port(port):
    """Given a used port, find a free port.

    Args:
        port (int): The port number to check.

    Returns:
        int: A free port number.
    """
    while is_port_in_use(port):
        port += 1
    return port


def get_letter_from_version(version: str) -> str | None:
    """Get the letter from a pre-release version."""
    if "a" in version:
        return "a"
    if "b" in version:
        return "b"
    if "rc" in version:
        return "rc"
    return None


def build_version_notice(current_version: str, package_name: str) -> str:
    latest_version = fetch_latest_version(package_name, include_prerelease=langflow_is_pre_release(current_version))
    if latest_version and pkg_version.parse(current_version) < pkg_version.parse(latest_version):
        release_type = "pre-release" if langflow_is_pre_release(latest_version) else "version"
        return f"A new {release_type} of {package_name} is available: {latest_version}"
    return ""


def generate_pip_command(package_names, is_pre_release) -> str:
    """Generate the pip install command based on the packages and whether it's a pre-release."""
    base_command = "pip install"
    if is_pre_release:
        return f"{base_command} {' '.join(package_names)} -U --pre"
    return f"{base_command} {' '.join(package_names)} -U"


def stylize_text(text: str, to_style: str, *, is_prerelease: bool) -> str:
    color = "#42a7f5" if is_prerelease else "#6e42f5"
    # return "".join(f"[{color}]{char}[/]" for char in text)
    styled_text = f"[{color}]{to_style}[/]"
    return text.replace(to_style, styled_text)


def print_banner(host: str, port: int) -> None:
    notices = []
    package_names = []  # Track package names for pip install instructions
    is_pre_release = False  # Track if any package is a pre-release
    package_name = ""

    # Use langflow.utils.version to get the version info
    version_info = get_version_info()
    langflow_version = version_info["version"]
    package_name = version_info["package"]
    is_pre_release |= langflow_is_pre_release(langflow_version)  # Update pre-release status

    notice = build_version_notice(langflow_version, package_name)
    notice = stylize_text(notice, package_name, is_prerelease=is_pre_release)
    if notice:
        notices.append(notice)
    package_names.append(package_name)

    # Generate pip command based on the collected data
    pip_command = generate_pip_command(package_names, is_pre_release)

    # Add pip install command to notices if any package needs an update
    if notices:
        notices.append(f"Run '{pip_command}' to update.")

    styled_notices = [f"[bold]{notice}[/bold]" for notice in notices if notice]
    styled_package_name = stylize_text(
        package_name, package_name, is_prerelease=any("pre-release" in notice for notice in notices)
    )

    title = f"[bold]Welcome to :chains: {styled_package_name}[/bold]\n"
    info_text = (
        "Collaborate, and contribute at our "
        "[bold][link=https://github.com/langflow-ai/langflow]GitHub Repo[/link][/bold] :star2:"
    )
    telemetry_text = (
        "We collect anonymous usage data to improve Langflow.\n"
        "You can opt-out by setting [bold]DO_NOT_TRACK=true[/bold] in your environment."
    )
    access_link = f"Access [link=http://{host}:{port}]http://{host}:{port}[/link]"

    panel_content = "\n\n".join([title, *styled_notices, info_text, telemetry_text, access_link])
    panel = Panel(panel_content, box=box.ROUNDED, border_style="blue", expand=False)
    rprint(panel)


def run_langflow(host, port, log_level, options, app) -> None:
    """Run Langflow server on localhost."""
    if platform.system() == "Windows":
        # Run using uvicorn on MacOS and Windows
        # Windows doesn't support gunicorn
        # MacOS requires an env variable to be set to use gunicorn
        import uvicorn

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level.lower(),
            loop="asyncio",
        )
    else:
        from langflow.server import LangflowApplication

        LangflowApplication(app, options).run()


@app.command()
def superuser(
    username: str = typer.Option(..., prompt=True, help="Username for the superuser."),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for the superuser."),
    log_level: str = typer.Option("error", help="Logging level.", envvar="LANGFLOW_LOG_LEVEL"),
) -> None:
    """Create a superuser."""
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
                msg = "Could not create default folder."
                raise RuntimeError(msg)
            typer.echo("Superuser created successfully.")

        else:
            typer.echo("Superuser creation failed.")


# command to copy the langflow database from the cache to the current directory
# because now the database is stored per installation
@app.command()
def copy_db() -> None:
    """Copy the database files to the current directory.

    This function copies the 'langflow.db' and 'langflow-pre.db' files from the cache directory to the current
    directory.
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
    test: bool = typer.Option(default=True, help="Run migrations in test mode."),  # noqa: FBT001
    fix: bool = typer.Option(  # noqa: FBT001
        default=False,
        help="Fix migrations. This is a destructive operation, and should only be used if you know what you are doing.",
    ),
) -> None:
    """Run or test migrations."""
    if fix and not typer.confirm(
        "This will delete all data necessary to fix migrations. Are you sure you want to continue?"
    ):
        raise typer.Abort

    initialize_services(fix_migration=fix)
    db_service = get_db_service()
    if not test:
        db_service.run_migrations()
    results = db_service.run_migrations_test()
    display_results(results)


@app.command()
def api_key(
    log_level: str = typer.Option("error", help="Logging level."),
) -> None:
    """Creates an API key for the default superuser if AUTO_LOGIN is enabled.

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

    async def aapi_key():
        async with async_session_scope() as session:
            from langflow.services.database.models.user.model import User

            superuser = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
            if not superuser:
                typer.echo(
                    "Default superuser not found. This command requires a superuser and AUTO_LOGIN to be enabled."
                )
                return None
            from langflow.services.database.models.api_key import ApiKey, ApiKeyCreate
            from langflow.services.database.models.api_key.crud import (
                create_api_key,
                delete_api_key,
            )

            api_key = (await session.exec(select(ApiKey).where(ApiKey.user_id == superuser.id))).first()
            if api_key:
                await delete_api_key(session, api_key.id)

            api_key_create = ApiKeyCreate(name="CLI")
            unmasked_api_key = await create_api_key(session, api_key_create, user_id=superuser.id)
            await session.commit()
            return unmasked_api_key

    unmasked_api_key = asyncio.run(aapi_key())
    # Create a banner to display the API key and tell the user it won't be shown again
    api_key_banner(unmasked_api_key)


def show_version(*, value: bool):
    if value:
        default = "DEV"
        raw_info = get_version_info()
        version = raw_info.get("version", default) if raw_info else default
        typer.echo(f"langflow {version}")
        raise typer.Exit


@app.callback()
def version_option(
    *,
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=show_version,
        is_eager=True,
        help="Show the version and exit.",
    ),
):
    pass


def api_key_banner(unmasked_api_key) -> None:
    is_mac = platform.system() == "Darwin"
    import pyperclip

    pyperclip.copy(unmasked_api_key.api_key)
    panel = Panel(
        f"[bold]API Key Created Successfully:[/bold]\n\n"
        f"[bold blue]{unmasked_api_key.api_key}[/bold blue]\n\n"
        "This is the only time the API key will be displayed. \n"
        "Make sure to store it in a secure location. \n\n"
        f"The API key has been copied to your clipboard. [bold]{['Ctrl', 'Cmd'][is_mac]} + V[/bold] to paste it.",
        box=box.ROUNDED,
        border_style="blue",
        expand=False,
    )
    console = Console()
    console.print(panel)


def main() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app()


if __name__ == "__main__":
    main()
