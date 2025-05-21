import httpx
import pkg_resources
import typer
from langflow.logging.logger import logger
from packaging import version as pkg_version

from langflow_execution.main import run_server

app = typer.Typer(no_args_is_help=True)

PYPI_PACKAGE_NAME = "langflow-execution"


def get_number_of_workers(workers=None):
    if workers == -1 or workers is None:
        workers = 1  # TODO: Just 1 for now
    logger.debug(f"Number of workers: {workers}")
    return workers


def fetch_latest_version(package_name: str) -> str | None:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["info"]["version"]
    except Exception:
        return None


def build_version_notice(current_version: str, package_name: str) -> str:
    latest_version = fetch_latest_version(package_name)
    if latest_version and pkg_version.parse(current_version) < pkg_version.parse(latest_version):
        return f"A new version of {package_name} is available: {latest_version}"
    return ""


def generate_pip_command(package_name: str) -> str:
    return f"uv pip install {package_name} -U"


@app.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to listen on."),
    log_level: str = typer.Option("info", help="Logging level."),
    reload: bool = typer.Option(False, help="Enable auto-reload."),
):
    run_server(host=host, port=port, log_level=log_level, reload=reload)


@app.command()
def version():
    """Show the version and exit, and print update notice if available."""
    try:
        current_version = pkg_resources.get_distribution(PYPI_PACKAGE_NAME).version
    except Exception:
        current_version = "unknown"
    typer.echo(f"langflow-execution {current_version}")
    if current_version != "unknown":
        notice = build_version_notice(current_version, PYPI_PACKAGE_NAME)
        if notice:
            typer.echo(notice)
            typer.echo(f"Run '{generate_pip_command(PYPI_PACKAGE_NAME)}' to update.")


if __name__ == "__main__":
    app()
