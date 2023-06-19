import sys
import time
from fastapi import FastAPI
import httpx
from multiprocess import Process, cpu_count  # type: ignore
import platform
from pathlib import Path
from typing import Optional
import socket
from rich.panel import Panel
from rich import box
from rich import print as rprint
import typer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langflow.main import create_app
from langflow.settings import settings
from langflow.utils.logger import configure, logger
import webbrowser
from dotenv import load_dotenv

app = typer.Typer()


def get_number_of_workers(workers=None):
    if workers == -1:
        workers = (cpu_count() * 2) + 1
    return workers


def update_settings(
    config: str,
    dev: bool = False,
    database_url: Optional[str] = None,
    remove_api_keys: bool = False,
):
    """Update the settings from a config file."""
    if config:
        settings.update_from_yaml(config, dev=dev)
    if database_url:
        settings.update_settings(database_url=database_url)
    if remove_api_keys:
        settings.update_settings(remove_api_keys=remove_api_keys)


def serve_on_jcloud():
    """
    Deploy Langflow server on Jina AI Cloud
    """
    import asyncio
    from importlib.metadata import version as mod_version

    import click

    try:
        from lcserve.__main__ import serve_on_jcloud  # type: ignore
    except ImportError:
        click.secho(
            "🚨 Please install langchain-serve to deploy Langflow server on Jina AI Cloud "
            "using `pip install langchain-serve`",
            fg="red",
        )
        return

    app_name = "langflow.lcserve:app"
    app_dir = str(Path(__file__).parent)
    version = mod_version("langflow")
    base_image = "jinaai+docker://deepankarm/langflow"

    click.echo("🚀 Deploying Langflow server on Jina AI Cloud")
    app_id = asyncio.run(
        serve_on_jcloud(
            fastapi_app_str=app_name,
            app_dir=app_dir,
            uses=f"{base_image}:{version}",
            name="langflow",
        )
    )
    click.secho(
        "🎉 Langflow server successfully deployed on Jina AI Cloud 🎉", fg="green"
    )
    click.secho(
        "🔗 Click on the link to open the server (please allow ~1-2 minutes for the server to startup): ",
        nl=False,
        fg="green",
    )
    click.secho(f"https://{app_id}.wolf.jina.ai/", fg="blue")
    click.secho("📖 Read more about managing the server: ", nl=False, fg="green")
    click.secho("https://github.com/jina-ai/langchain-serve", fg="blue")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    workers: int = typer.Option(1, help="Number of worker processes."),
    timeout: int = typer.Option(60, help="Worker timeout in seconds."),
    port: int = typer.Option(7860, help="Port to listen on."),
    config: str = typer.Option("config.yaml", help="Path to the configuration file."),
    # .env file param
    env_file: Path = typer.Option(
        ".env", help="Path to the .env file containing environment variables."
    ),
    log_level: str = typer.Option("critical", help="Logging level."),
    log_file: Path = typer.Option("logs/langflow.log", help="Path to the log file."),
    jcloud: bool = typer.Option(False, help="Deploy on Jina AI Cloud"),
    dev: bool = typer.Option(False, help="Run in development mode (may contain bugs)"),
    database_url: str = typer.Option(
        None,
        help="Database URL to connect to. If not provided, a local SQLite database will be used.",
    ),
    path: str = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
    ),
    open_browser: bool = typer.Option(
        True, help="Open the browser after starting the server."
    ),
    remove_api_keys: bool = typer.Option(
        False, help="Remove API keys from the projects saved in the database."
    ),
):
    """
    Run the Langflow server.
    """

    if jcloud:
        return serve_on_jcloud()

    load_dotenv(env_file)

    configure(log_level=log_level, log_file=log_file)
    update_settings(
        config, dev=dev, database_url=database_url, remove_api_keys=remove_api_keys
    )
    # get the directory of the current file
    if not path:
        frontend_path = Path(__file__).parent
        static_files_dir = frontend_path / "frontend"
    else:
        static_files_dir = Path(path)

    app = create_app()
    setup_static_files(app, static_files_dir)
    # check if port is being used
    if is_port_in_use(port, host):
        port = get_free_port(port)

    options = {
        "bind": f"{host}:{port}",
        "workers": get_number_of_workers(workers),
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
    }

    if platform.system() in ["Windows"]:
        # Run using uvicorn on MacOS and Windows
        # Windows doesn't support gunicorn
        # MacOS requires an env variable to be set to use gunicorn
        run_on_windows(host, port, log_level, options, app)
    else:
        # Run using gunicorn on Linux
        run_on_mac_or_linux(host, port, log_level, options, app, open_browser)


def run_on_mac_or_linux(host, port, log_level, options, app, open_browser=True):
    webapp_process = Process(
        target=run_langflow, args=(host, port, log_level, options, app)
    )
    webapp_process.start()
    status_code = 0
    while status_code != 200:
        try:
            status_code = httpx.get(f"http://{host}:{port}/health").status_code

        except Exception:
            time.sleep(1)

    print_banner(host, port)
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")


def run_on_windows(host, port, log_level, options, app):
    """
    Run the Langflow server on Windows.
    """
    print_banner(host, port)
    run_langflow(host, port, log_level, options, app)


def setup_static_files(app: FastAPI, static_files_dir: Path):
    """
    Setup the static files directory.

    Args:
        app (FastAPI): FastAPI app.
        path (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(request, __):
        path = static_files_dir / "index.html"

        if not path.exists():
            raise RuntimeError(f"File at path {path} does not exist.")
        return FileResponse(path)


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

    word = "LangFlow"
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
    panel = Panel(
        f"{title}\n{info_text}", box=box.ROUNDED, border_style="blue", expand=False
    )

    # Print the banner with a separator line before and after
    rprint(panel)


def run_langflow(host, port, log_level, options, app):
    """
    Run Langflow server on localhost
    """
    try:
        if platform.system() in ["Darwin", "Windows"]:
            # Run using uvicorn on MacOS and Windows
            # Windows doesn't support gunicorn
            # MacOS requires an env variable to be set to use gunicorn
            import uvicorn

            uvicorn.run(app, host=host, port=port, log_level=log_level)
        else:
            from langflow.server import LangflowApplication

            LangflowApplication(app, options).run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(e)
        sys.exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
