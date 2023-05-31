import multiprocessing
import platform
from pathlib import Path

import typer
from fastapi.staticfiles import StaticFiles

from langflow.main import create_app
from langflow.settings import settings
from langflow.utils.logger import configure

app = typer.Typer()


def get_number_of_workers(workers=None):
    if workers == -1:
        workers = (multiprocessing.cpu_count() * 2) + 1
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
    log_level: str = typer.Option("info", help="Logging level."),
    log_file: Path = typer.Option("logs/langflow.log", help="Path to the log file."),
    jcloud: bool = typer.Option(False, help="Deploy on Jina AI Cloud"),
    dev: bool = typer.Option(False, help="Run in development mode (may contain bugs)"),
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
    path = Path(__file__).parent
    static_files_dir = path / "frontend"
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

    if platform.system() in ["Darwin", "Windows"]:
        # Run using uvicorn on MacOS and Windows
        # Windows doesn't support gunicorn
        # MacOS requires an env variable to be set to use gunicorn
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level=log_level)
    else:
        from langflow.server import LangflowApplication

        LangflowApplication(app, options).run()


def main():
    app()


if __name__ == "__main__":
    main()
