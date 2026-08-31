"""Every entry point that runs a flow must label its span with the surface it came from.

``protocol`` answers the operator's first question when an error rate moves: which door did
this come through. A webhook failing and the canvas failing are different incidents with
different owners, and the attribute is the only thing that separates them.

Two halves, because they fail differently.

The completeness gate below is static: it reads the values the source can emit and compares
them against the declared list. That is what catches a new entry point being added with no
cell, which is how a sweep like this rots between releases.

The per-cell tests are dynamic: they drive the real route and read the exported span. That is
what catches a binding that exists in the source but does not actually reach the span, which
static reading cannot see.

Naming trap worth knowing before editing this file: ``protocol`` is overloaded in the v2 code.
``stream_protocol``, and the ``protocol=`` argument in ``background_execution/service.py``, are
the SSE wire format (``agui`` / ``langflow``) and have nothing to do with this attribute. The
gate below matches on call shape rather than on the word, so it does not conflate them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from lfx.observability import APPLICATION_TRACER_NAME

BACKEND_SRC = Path(__file__).resolve().parents[4] / "base" / "langflow"
LFX_SRC = Path(__file__).resolve().parents[5] / "lfx" / "src" / "lfx"

# One row per surface that can run a flow. Keep this sorted and keep it complete: the gate
# below fails when the source emits a value that is not here, which is the point.
DECLARED_PROTOCOLS = {
    "a2a",
    "agentic",
    "lfx.run",
    "lfx.serve",
    "mcp",
    "openai_responses",
    "v1",
    "v1.advanced",
    "v1.build",
    "v1.build.public",
    "v2",
    "v2.background",
    "v2.public",
    "voice",
    "webhook",
}


# Where each cell's live evidence lives. This IS the sweep's table: a protocol with no entry
# has never been driven end to end, and saying so out loud is the point -- a sweep that
# silently omits a surface reads as more coverage than it has.
#
# "sweep" means a test in this file. Anything else names the file that already drives it;
# duplicating those here would add a second thing to keep in step for no extra evidence.
CELL_EVIDENCE = {
    "v1": "sweep",
    "v1.advanced": "sweep",
    "v2": "sweep",
    "v2.background": "sweep",
    "webhook": "sweep",
    "openai_responses": "sweep",
    "v1.build": "tests/unit/api/test_build_flow_span.py",
    "a2a": "tests/unit/api/v1/test_a2a_span.py",
    "voice": "tests/unit/services/telemetry/test_flow_execution_span.py",
    "lfx.serve": "src/lfx/tests/unit/cli/test_serve_app_flow_span.py",
    "lfx.run": "src/lfx/tests/unit/cli/test_run_command_flow_span.py",
    # Not yet driven end to end. Each needs a driver this sweep does not have yet; recorded
    # rather than omitted so the gap is visible in the table instead of in nobody's head.
    "v1.build.public": "BLOCKED: needs a public-flow fixture with the tmp build route",
    "v2.public": "BLOCKED: needs a published public workflow fixture",
    "mcp": "BLOCKED: needs an MCP client session against the in-process server",
    "agentic": "BLOCKED: needs the assistant service driven end to end",
}


# The N/A cells: combinations that must fail loudly rather than run something. Kept beside
# CELL_EVIDENCE because a table that only records what works reads as complete when it is not.
NA_EVIDENCE = {
    "lfx.serve x v1/webhook/mcp routes": "src/lfx/tests/unit/cli/test_serve_app_flow_span.py",
    "lfx.run x any HTTP surface": "src/lfx/tests/unit/cli/test_run_command_flow_span.py",
}


def test_every_declared_protocol_has_recorded_evidence():
    """The table itself. A cell with no row here is an unfilled cell, blocked or not."""
    missing = DECLARED_PROTOCOLS - set(CELL_EVIDENCE)

    assert not missing, f"declared with no evidence row: {sorted(missing)}"


def test_no_evidence_row_is_orphaned():
    """And the reverse, so a deleted surface cannot leave a row claiming coverage."""
    orphaned = set(CELL_EVIDENCE) - DECLARED_PROTOCOLS

    assert not orphaned, f"evidence rows for protocols that no longer exist: {sorted(orphaned)}"


def test_every_cited_evidence_file_exists():
    """A cited file that has been moved or deleted is a cell claiming coverage it lost.

    The paths were prose until this existed, and one of them was still a placeholder with an
    ellipsis in it, which is exactly the rot this catches.
    """
    repo_root = BACKEND_SRC.parents[3]
    missing = []
    for protocol, evidence in sorted({**CELL_EVIDENCE, **NA_EVIDENCE}.items()):
        if evidence == "sweep" or evidence.startswith("BLOCKED"):
            continue
        candidate = repo_root / evidence if evidence.startswith("src/") else BACKEND_SRC.parents[1] / evidence
        if not candidate.is_file():
            missing.append(f"{protocol} -> {evidence} (looked in {candidate})")

    assert not missing, "evidence files that do not exist:\n  " + "\n  ".join(missing)


def _literal_protocols(root: Path) -> set[str]:
    """Every protocol value the source under ``root`` can bind, read from the AST.

    Two call shapes carry one, and missing the second is exactly the mistake this function
    exists to prevent:

    * ``execution_protocol("v1")`` -- bound directly at the entry point.
    * ``_stream_event_frames(..., protocol="v2.background")`` -- passed one level out, then
      bound inside. The parameter is required and un-defaulted there precisely so an unwired
      caller cannot silently inherit a wrong label.

    Matched on call shape, not on the identifier ``protocol``, so the SSE wire-format argument
    of the same name is not swept up.
    """
    found: set[str] = set()
    for path in root.rglob("*.py"):
        # Not `"test" in path.parts`: that matches a directory named exactly "test" and misses
        # both "tests" directories and test_*.py modules, of which the scanned roots contain 32.
        # A test that binds a made-up protocol would otherwise register as an emitted value.
        if any(part in {"test", "tests"} or part.startswith("test_") for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name == "execution_protocol":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.add(arg.value)
            elif name == "_stream_event_frames":
                for kw in node.keywords:
                    if kw.arg == "protocol" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        found.add(kw.value.value)
    return found


def test_the_scanner_finds_something():
    """Asserted before the comparisons: an empty scan would make both gates vacuous."""
    assert _literal_protocols(BACKEND_SRC), f"no protocol values found under {BACKEND_SRC}"


def test_no_entry_point_emits_an_undeclared_protocol():
    """A new surface without a cell fails here rather than shipping unlabelled."""
    emitted = _literal_protocols(BACKEND_SRC) | _literal_protocols(LFX_SRC)
    undeclared = emitted - DECLARED_PROTOCOLS

    assert not undeclared, (
        f"these protocol values are emitted but have no cell in this sweep: {sorted(undeclared)}. "
        f"Add a row to DECLARED_PROTOCOLS and a per-cell test, or stop emitting them."
    )


def test_every_declared_protocol_is_actually_emitted():
    """The other direction: a cell for a surface that no longer exists is dead weight.

    Without this, deleting an entry point leaves a row asserting nothing, and the table reads
    as more coverage than it has.
    """
    emitted = _literal_protocols(BACKEND_SRC) | _literal_protocols(LFX_SRC)
    stale = DECLARED_PROTOCOLS - emitted

    assert not stale, f"declared but never emitted anywhere in the source: {sorted(stale)}"


# ---------------------------------------------------------------------------
# Per-cell evidence, driven through the real routes.
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(scope="module")
def span_exporter():
    """Attach an exporter to whatever tracer provider this worker has, and hand it back.

    In-process rather than in a subprocess because these tests need the app, the database and
    the auth fixtures.

    Attaching rather than installing is deliberate. The provider is process-global and
    ``set_tracer_provider`` is first-write-wins, so a module that installs its own works alone
    and breaks the moment xdist puts another provider-installing module in the same worker.
    Adding a processor to the provider already there has no ordering dependency.

    The cells still cannot pass vacuously: each asserts its own span arrived before asserting
    anything about it.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        # A real SDK provider is already installed. set_tracer_provider is first-write-wins,
        # so installing another would be ignored and every assertion below would read an
        # exporter nothing feeds. Attach to the one that exists instead: no ordering
        # dependency, and the cells still fail loudly if their span never arrives.
        current.add_span_processor(processor)
        try:
            yield exporter
        finally:
            # Shut the processor down rather than detach it: a provider has no removal API,
            # so clearing the exporter empties the list and leaves the processor registered,
            # still appending every later span in this worker to it for the rest of the run.
            processor.shutdown()
            exporter.clear()
        return

    provider = TracerProvider()
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        provider.shutdown()
        exporter.clear()


def flow_span_protocols(exporter) -> list[str | None]:
    """The ``protocol`` attribute of every exported flow span, in order."""
    return [
        (span.attributes or {}).get("protocol")
        for span in exporter.get_finished_spans()
        if span.name == "flow.execute"
        and span.instrumentation_scope
        and span.instrumentation_scope.name == APPLICATION_TRACER_NAME
    ]


async def test_v1_run_endpoint_reports_v1(client, simple_api_test, created_api_key, span_exporter):
    """Cell 1: POST /api/v1/run/{flow} -> protocol=v1.

    Authenticated with an API key rather than the session cookie, because that is what the
    route accepts and therefore what a real caller of this surface uses.
    """
    span_exporter.clear()
    flow_id = simple_api_test["id"]

    response = await client.post(
        f"/api/v1/run/{flow_id}",
        json={"input_value": "hello", "input_type": "chat", "output_type": "chat"},
        headers={"x-api-key": created_api_key.api_key},
    )

    assert response.status_code == 200, response.text
    assert "v1" in flow_span_protocols(span_exporter), flow_span_protocols(span_exporter)


async def test_v2_sync_run_reports_v2(client, simple_api_test, created_api_key, span_exporter):
    """Cell 5: POST /api/v2/workflows?mode=sync -> protocol=v2.

    The sync mode is the one that goes through ``Graph.arun``. The streaming and background
    modes of the same endpoint bind ``v2.background``, which is a separate cell -- asserting
    the exact value here is what keeps the three from being confused for one another.
    """
    span_exporter.clear()

    response = await client.post(
        "/api/v2/workflows?mode=sync",
        json={"flow_id": str(simple_api_test["id"]), "input_value": "hello"},
        headers={"x-api-key": created_api_key.api_key},
    )

    assert response.status_code == 200, response.text
    protocols = flow_span_protocols(span_exporter)
    assert "v2" in protocols, protocols
    # The exact value matters: a sync run reporting v2.background would mean an operator
    # cannot tell inline work from queued work, which is the whole point of the attribute.
    assert "v2.background" not in protocols, protocols


async def test_v1_advanced_run_reports_v1_advanced(client, simple_api_test, created_api_key, span_exporter):
    """Cell 4: POST /api/v1/run/advanced/{flow} -> protocol=v1.advanced."""
    span_exporter.clear()

    response = await client.post(
        f"/api/v1/run/advanced/{simple_api_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"inputs": [{"components": [], "input_value": "hello"}], "outputs": [], "tweaks": {}, "stream": False},
    )

    assert response.status_code == 200, response.text
    protocols = flow_span_protocols(span_exporter)
    assert "v1.advanced" in protocols, protocols
    # Distinct from the plain v1 endpoint: they share a driver, so a regression that dropped
    # the more specific binding would silently relabel this surface as v1.
    assert protocols == ["v1.advanced"], protocols


async def test_webhook_run_reports_webhook(client, added_webhook_test, created_api_key, span_exporter):
    """Cell 8: POST /api/v1/webhook/{flow} -> protocol=webhook.

    The webhook returns 202 and runs the flow in the background, so the span appears after the
    response. Polled rather than asserted immediately, because asserting straight away would
    race the run and fail intermittently rather than meaningfully.
    """
    import asyncio

    span_exporter.clear()

    response = await client.post(
        f"api/v1/webhook/{added_webhook_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"test_key": "test_value"},
    )
    assert response.status_code == 202, response.text

    for _ in range(100):
        if "webhook" in flow_span_protocols(span_exporter):
            break
        await asyncio.sleep(0.1)

    assert "webhook" in flow_span_protocols(span_exporter), flow_span_protocols(span_exporter)


async def test_openai_responses_run_reports_openai_responses(client, simple_api_test, created_api_key, span_exporter):
    """Cell 11: POST /api/v1/responses -> protocol=openai_responses.

    The OpenAI-compatible surface takes the flow id in ``model``, which is the shape an
    OpenAI SDK client sends.
    """
    span_exporter.clear()

    response = await client.post(
        "/api/v1/responses",
        headers={"x-api-key": created_api_key.api_key},
        json={"model": str(simple_api_test["id"]), "input": "hello", "stream": False},
    )

    assert response.status_code == 200, response.text
    assert "openai_responses" in flow_span_protocols(span_exporter), flow_span_protocols(span_exporter)


async def test_v2_background_run_reports_v2_background(client, simple_api_test, created_api_key, span_exporter):
    """Cell 6: POST /api/v2/workflows with mode=background -> protocol=v2.background.

    The cell that made this sweep worth writing. A background run is handed to a worker after
    the response returns, so the label has to survive that hop; if it did not, queued work
    would be indistinguishable from inline work in the APM, which is the single question an
    operator asks when a v2 run is slow.
    """
    import asyncio

    span_exporter.clear()

    response = await client.post(
        "/api/v2/workflows",
        headers={"x-api-key": created_api_key.api_key},
        json={"flow_id": str(simple_api_test["id"]), "input_value": "hello", "mode": "background"},
    )
    assert response.status_code == 200, response.text

    for _ in range(150):
        if "v2.background" in flow_span_protocols(span_exporter):
            break
        await asyncio.sleep(0.1)

    protocols = flow_span_protocols(span_exporter)
    assert "v2.background" in protocols, protocols
    # Not "v2": that would mean the background hop lost the specific label and fell back to
    # the generic one, which reads as a pass while erasing the distinction.
    assert "v2" not in protocols, protocols
