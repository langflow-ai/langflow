"""Pipelined HTTP requests must produce independent server spans in every launch mode."""

import asyncio
import socket

import pytest
import typer
import uvicorn
from fastapi import FastAPI, Response
from lfx.cli import commands
from typer.testing import CliRunner


@pytest.fixture(params=["single", "windows", "gunicorn"])
def serve_config(request, monkeypatch, tmp_path):
    """Capture the real launch configuration without starting a process supervisor."""
    if request.param == "gunicorn":
        pytest.importorskip("gunicorn", reason="the gunicorn worker is Unix-only")
        from lfx.cli.serve_gunicorn import LFXUvicornWorker
        from uvicorn.workers import UvicornWorker

        config = uvicorn.Config("lfx.cli.serve_preloaded_app:app", **LFXUvicornWorker.CONFIG_KWARGS)
        for key, value in UvicornWorker.CONFIG_KWARGS.items():
            assert getattr(config, key) == value
        return config

    configs = []

    def capture_config(app, **kwargs):
        configs.append(uvicorn.Config(app, **kwargs))

    monkeypatch.setattr(commands.uvicorn, "run", capture_config)
    if request.param == "windows":
        with monkeypatch.context() as windows:
            windows.setattr(commands.sys, "platform", "win32")
            commands._launch_workers(
                host="127.0.0.1",
                port=8000,
                workers=2,
                log_level="warning",
                flow_dir=tmp_path,
                no_env_fallback=False,
                script_paths=None,
                temp_file_to_cleanup=None,
                verbose_print=lambda *_args: None,
                max_requests=None,
            )
    else:
        monkeypatch.setenv("LANGFLOW_API_KEY", "context-isolation-test")  # pragma: allowlist secret
        monkeypatch.setattr(commands, "is_port_in_use", lambda *_args: False)
        app = typer.Typer()
        app.command()(commands.serve_command)
        result = CliRunner().invoke(app, [])
        assert result.exit_code == 0, result.output

    assert len(configs) == 1
    return configs[0]


async def test_pipelined_requests_have_independent_server_spans(serve_config):
    """Send requests together so httptools starts later tasks inside the finishing task."""
    pytest.importorskip("opentelemetry.instrumentation.fastapi")
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.trace import SpanKind

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = FastAPI()

    @app.get("/health")
    async def health():
        await asyncio.sleep(0)
        return Response("ok")

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    # Exercise each launch mode's request handling options on the same instrumented app.
    serve_config.app = (lambda: app) if serve_config.factory else app
    serve_config.http = "httptools"
    serve_config.lifespan = "off"
    serve_config.access_log = False
    server = uvicorn.Server(serve_config)
    request_count = 12

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.settimeout(0)
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                        pytest.fail("server exited before startup")
                    await asyncio.sleep(0.01)
                reader, writer = await asyncio.open_connection(*listener.getsockname())
                try:
                    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n" * request_count)
                    await writer.drain()
                    for _ in range(request_count):
                        headers = await reader.readuntil(b"\r\n\r\n")
                        assert headers.startswith(b"HTTP/1.1 200 OK\r\n")
                        assert await reader.readexactly(2) == b"ok"
                finally:
                    writer.close()
                    await writer.wait_closed()
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=10)
            provider.shutdown()

    spans = [span for span in exporter.get_finished_spans() if span.name == "GET /health"]
    assert len(spans) == request_count
    assert sum(span.kind == SpanKind.SERVER for span in spans) == request_count
    assert all(span.parent is None for span in spans)
    assert len({span.context.trace_id for span in spans}) == request_count
