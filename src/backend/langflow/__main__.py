import sys
import time
import httpx
from multiprocess import Process, cpu_count  # type: ignore
import platform
from pathlib import Path

from rich.panel import Panel
from rich import box
from rich import print as rprint
import typer
from fastapi.staticfiles import StaticFiles

from langflow.main import create_app
from langflow.settings import settings
from langflow.utils.logger import configure, logger
import webbrowser


app = typer.Typer()


def get_number_of_workers(workers=None):
    if workers == -1:
        workers = (cpu_count() * 2) + 1
    return workers


def update_settings(config: str, dev: bool = False):
    """Update the settings from a config file."""
    if config:
        settings.update_from_yaml(config, dev=dev)


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
    log_level: str = typer.Option("critical", help="Logging level."),
    log_file: Path = typer.Option("logs/langflow.log", help="Path to the log file."),
    jcloud: bool = typer.Option(False, help="Deploy on Jina AI Cloud"),
    dev: bool = typer.Option(False, help="Run in development mode (may contain bugs)"),
    path: str = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
    ),
    open_browser: bool = typer.Option(
        True, help="Open the browser after starting the server."
    ),
):
    """
    Run the Langflow server.
    """

    if jcloud:
        return serve_on_jcloud()

    configure(log_level=log_level, log_file=log_file)
    update_settings(config, dev=dev)
    app = create_app()
    # get the directory of the current file
    if not path:
        frontend_path = Path(__file__).parent
        static_files_dir = frontend_path / "frontend"
    else:
        static_files_dir = Path(path)
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )
    options = {
        "bind": f"{host}:{port}",
        "workers": get_number_of_workers(workers),
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
    }

    webapp_process = Process(
        target=run_langflow, args=(host, port, log_level, options, app)
    )
    webapp_process.start()
    status_code = 0
    while status_code != 200:
        try:
            status_code = httpx.get(f"http://{host}:{port}").status_code
        except Exception:
            time.sleep(1)

    print_banner(host, port)
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")


def print_banner(host, port):
    # console = Console()

    word = "LangFlow"
    colors = ["#690080", "#660099", "#4d00b3", "#3300cc", "#1a00e6", "#0000ff"]

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
