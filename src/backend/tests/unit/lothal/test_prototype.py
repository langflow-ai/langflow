"""Prototype engine orchestration tests (Stories U.4-U.7).

These focus on the orchestration logic in `langflow.lothal.prototype` directly
(the brief builder, status derivation, idempotency, artifact mapping, and the
embed/preview URL helpers), with OD mocked by respx. The HTTP-endpoint behaviour
is covered separately in `api/v1/test_lothal.py`; here a lightweight project
stand-in (only attributes are read) keeps the tests off the database.
"""

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from langflow.lothal import prototype

OD_BASE = "http://open-design:7456"


def _proj(**over):
    base = {
        "id": "lothal-1",
        "name": "App",
        "prd_content": "A todo app for individuals.",
        "diagram_d2": "user -> api: submit",
        "artifacts": None,
        "od_project_id": None,
        "od_conversation_id": None,
        "prototype_status": "IDLE",
    }
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def _od_env(monkeypatch):
    monkeypatch.setenv("LOTHAL_OD_BASE_URL", OD_BASE)
    monkeypatch.delenv("LOTHAL_OD_API_TOKEN", raising=False)
    monkeypatch.delenv("OD_API_TOKEN", raising=False)
    monkeypatch.delenv("LOTHAL_OD_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "")  # skip the best-effort app-config PATCH
    monkeypatch.setenv("LOTHAL_OD_SKILL_ID", "")


# --- build_brief -------------------------------------------------------------


def test_build_brief_includes_prd_and_diagram():
    brief = prototype.build_brief("Build a todo app.", "user -> api: submit", None)
    assert "Build a todo app." in brief
    assert "user -> api: submit" in brief
    assert "prototype" in brief.lower()  # the design instruction


def test_build_brief_prefers_artifact_map_over_single_diagram():
    artifacts = {
        "adr.md": "We chose a layered architecture.",
        "diagrams/context.d2": "ctx -> svc",
        "diagrams/sequence.d2": "a -> b",
    }
    brief = prototype.build_brief("PRD", "legacy -> diagram", artifacts)
    assert "We chose a layered architecture." in brief
    assert "diagrams/context.d2" in brief
    assert "ctx -> svc" in brief
    # The legacy single diagram is not used when the artifact map has diagrams.
    assert "legacy -> diagram" not in brief


def test_build_brief_handles_missing_context():
    brief = prototype.build_brief(None, None, None)
    assert isinstance(brief, str)
    assert brief.strip()  # the intro is always present


# --- seed_and_generate -------------------------------------------------------


@pytest.mark.usefixtures("_od_env")
async def test_seed_and_generate_creates_project_and_run():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        create = respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-1"}))
        run = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-1", "conversationId": "conv-1"})
        )
        result = await prototype.seed_and_generate(_proj(id="lothal-1"))

    assert result.created is True
    assert result.od_project_id == "od-1"
    assert result.od_conversation_id == "conv-1"
    assert create.call_count == 1
    assert run.call_count == 1
    # OD requires a client-supplied id (live-verified), and the project records the
    # Lothal linkage in its metadata.
    create_body = json.loads(create.calls.last.request.content)
    assert create_body["id"] == "lothal-lothal-1"
    assert create_body["metadata"]["lothalProjectId"] == "lothal-1"


@pytest.mark.usefixtures("_od_env")
async def test_seed_and_generate_reuses_tagged_od_project_and_starts_run_if_none():
    """Reuse a tagged OD project on retry (no duplicate create); start a run since it has none."""
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "od-other", "metadata": {"lothalProjectId": "someone-else"}},
                    {"id": "od-mine", "metadata": {"source": "lothal", "lothalProjectId": "lothal-1"}},
                ],
            )
        )
        respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        create = respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "NEW"}))
        run = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-9", "conversationId": "conv-9"})
        )
        result = await prototype.seed_and_generate(_proj(id="lothal-1"))

    assert result.od_project_id == "od-mine"  # reused, not the freshly-created "NEW"
    assert create.call_count == 0
    assert run.call_count == 1  # had no runs → one started


@pytest.mark.usefixtures("_od_env")
async def test_seed_and_generate_reuses_project_and_does_not_double_run():
    """A reused OD project that already has a run is not run again."""
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects").mock(
            return_value=httpx.Response(200, json=[{"id": "od-mine", "metadata": {"lothalProjectId": "lothal-1"}}])
        )
        respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "r1", "status": "running", "conversationId": "conv-7"}])
        )
        run = respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={"runId": "x"}))
        result = await prototype.seed_and_generate(_proj(id="lothal-1"))

    assert result.od_project_id == "od-mine"
    assert result.od_conversation_id == "conv-7"  # taken from the existing run
    assert run.call_count == 0  # already had a run → not started again


async def test_seed_and_generate_is_idempotent_when_already_linked():
    # Already linked → returns the existing linkage and makes no OD call (no respx
    # routes registered, so any request would error).
    result = await prototype.seed_and_generate(_proj(od_project_id="od-existing", od_conversation_id="conv-existing"))
    assert result.created is False
    assert result.od_project_id == "od-existing"
    assert result.od_conversation_id == "conv-existing"


# --- refine ------------------------------------------------------------------


@pytest.mark.usefixtures("_od_env")
async def test_refine_starts_run_in_existing_conversation():
    with respx.mock:
        run = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-2", "conversationId": "conv-1"})
        )
        result = await prototype.refine(_proj(od_project_id="od-1", od_conversation_id="conv-1"), "make it dark")

    assert result.od_conversation_id == "conv-1"
    body = json.loads(run.calls.last.request.content)
    assert body["conversationId"] == "conv-1"
    assert body["message"] == "make it dark"


async def test_refine_without_linkage_raises():
    with pytest.raises(ValueError, match="generated"):
        await prototype.refine(_proj(od_project_id=None), "tweak")


@pytest.mark.usefixtures("_od_env")
async def test_refine_falls_back_to_stored_conversation_when_run_omits_it():
    """If OD's run reply carries no conversationId, the stored one is kept."""
    with respx.mock:
        respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={"runId": "r2"}))
        result = await prototype.refine(_proj(od_project_id="od-1", od_conversation_id="conv-stored"), "tweak")
    assert result.od_conversation_id == "conv-stored"


# --- collect_state -----------------------------------------------------------


@pytest.mark.usefixtures("_od_env")
async def test_collect_state_ready_filters_non_artifacts():
    files = [
        {
            "name": "home.html",
            "path": "home.html",
            "artifactKind": "prototype",
            "artifactManifest": {"kind": "prototype", "title": "Home"},
        },
        {"name": "notes.txt", "path": "notes.txt"},  # not an artifact
    ]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=files))
        respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "r1", "status": "succeeded", "createdAt": "2026-01-02"}])
        )
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home</html>")
        )
        state = await prototype.collect_state(_proj(od_project_id="od-1", prototype_status="GENERATING"))

    assert state.status == "READY"
    assert [a.path for a in state.artifacts] == ["home.html"]
    assert state.artifacts[0].title == "Home"
    assert state.artifacts[0].preview_url is None  # no public base configured
    # The primary HTML design is fetched and rendered inline.
    assert state.preview_html == "<html>home</html>"


@pytest.mark.usefixtures("_od_env")
async def test_collect_state_generating_while_run_in_flight():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "r1", "status": "running", "createdAt": "2026-01-02"}])
        )
        state = await prototype.collect_state(_proj(od_project_id="od-1", prototype_status="GENERATING"))
    assert state.status == "GENERATING"


@pytest.mark.usefixtures("_od_env")
async def test_collect_state_artifact_field_fallbacks():
    """Kind falls back to manifest.kind; title falls back to the path when absent."""
    files = [
        # No artifactKind, no manifest title → kind from manifest.kind, title = path.
        {"name": "deck.html", "path": "deck.html", "artifactManifest": {"kind": "deck"}},
    ]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=files))
        respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/deck.html").mock(
            return_value=httpx.Response(200, text="<html>deck</html>")
        )
        state = await prototype.collect_state(_proj(od_project_id="od-1", prototype_status="GENERATING"))
    assert len(state.artifacts) == 1
    assert state.artifacts[0].kind == "deck"
    assert state.artifacts[0].title == "deck.html"  # fell back to path


@pytest.mark.usefixtures("_od_env")
async def test_collect_state_ready_when_design_exists_and_no_active_run():
    """OD's run list can empty out after a run; a design + no in-flight run is READY (not stuck GENERATING)."""
    files = [
        {
            "name": "home.html",
            "path": "home.html",
            "artifactKind": "prototype",
            "artifactManifest": {"kind": "prototype", "title": "Home"},
        },
    ]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=files))
        respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))  # empty / lagged
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home</html>")
        )
        state = await prototype.collect_state(_proj(od_project_id="od-1", prototype_status="GENERATING"))
    assert state.status == "READY"
    assert state.preview_html == "<html>home</html>"


@pytest.mark.usefixtures("_od_env")
async def test_collect_state_not_ready_when_run_succeeded_but_no_design():
    """A succeeded run with no design artifact stays GENERATING, not READY."""
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(
            return_value=httpx.Response(200, json=[])  # no design built yet
        )
        respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "r1", "status": "succeeded", "createdAt": "2026-01-02"}])
        )
        state = await prototype.collect_state(_proj(od_project_id="od-1", prototype_status="GENERATING"))
    assert state.status == "GENERATING"  # not READY — nothing was built
    assert state.preview_html is None
    assert state.artifacts == []


async def test_collect_state_unlinked_returns_stored_without_od_call():
    state = await prototype.collect_state(_proj(od_project_id=None, prototype_status="IDLE"))
    assert state.status == "IDLE"
    assert state.artifacts == []
    assert state.embed_url is None


def test_derive_status_mapping():
    assert prototype._derive_status("GENERATING", [{"status": "succeeded"}]) == "READY"
    assert prototype._derive_status("GENERATING", [{"status": "running"}]) == "GENERATING"
    assert prototype._derive_status("GENERATING", [{"status": "queued"}]) == "GENERATING"
    # A failed/canceled run has no lifecycle state — keep the stored status.
    assert prototype._derive_status("GENERATING", [{"status": "failed"}]) == "GENERATING"
    assert prototype._derive_status("READY", [{"status": "canceled"}]) == "READY"
    # No runs → stored status untouched.
    assert prototype._derive_status("IDLE", []) == "IDLE"


def test_derive_status_picks_latest_run_by_created_at():
    runs = [
        {"status": "running", "createdAt": "2026-01-01"},
        {"status": "succeeded", "createdAt": "2026-01-03"},
        {"status": "queued", "createdAt": "2026-01-02"},
    ]
    assert prototype._derive_status("GENERATING", runs) == "READY"


# --- collect_for_approval ----------------------------------------------------


@pytest.mark.usefixtures("_od_env")
async def test_collect_for_approval_fetches_content_and_keeps_unreadable():
    files = [
        {
            "name": "home.html",
            "path": "home.html",
            "artifactKind": "prototype",
            "artifactManifest": {"kind": "prototype", "title": "Home"},
        },
        {
            "name": "logo.png",
            "path": "logo.png",
            "artifactKind": "image",
            "artifactManifest": {"kind": "image", "title": "Logo"},
        },
        {"name": "notes.txt", "path": "notes.txt"},  # not an artifact, skipped
    ]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=files))
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home</html>")
        )
        # The image content can't be read as text — it must still be retained.
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/logo.png").mock(side_effect=httpx.ConnectError("binary"))
        approved = await prototype.collect_for_approval(_proj(od_project_id="od-1"))

    by_path = {a.od_path: a for a in approved}
    assert set(by_path) == {"home.html", "logo.png"}
    assert by_path["home.html"].content == "<html>home</html>"
    assert by_path["home.html"].manifest == {"kind": "prototype", "title": "Home"}
    assert by_path["logo.png"].content is None  # unreadable, kept with its manifest


async def test_collect_for_approval_unlinked_returns_empty():
    assert await prototype.collect_for_approval(_proj(od_project_id=None)) == []


@pytest.mark.usefixtures("_od_env")
async def test_collect_for_approval_keeps_manifestless_artifact():
    """A file flagged by artifactKind but with no manifest is still copied (manifest=None)."""
    files = [{"name": "screen.html", "path": "screen.html", "artifactKind": "prototype"}]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(return_value=httpx.Response(200, json=files))
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/screen.html").mock(
            return_value=httpx.Response(200, text="<html></html>")
        )
        approved = await prototype.collect_for_approval(_proj(od_project_id="od-1"))
    assert len(approved) == 1
    assert approved[0].od_path == "screen.html"
    assert approved[0].kind == "prototype"
    assert approved[0].title == "screen.html"
    assert approved[0].manifest is None


# --- embed / preview URLs ----------------------------------------------------


def test_embed_and_preview_url_require_public_base(monkeypatch):
    monkeypatch.delenv("LOTHAL_OD_PUBLIC_BASE_URL", raising=False)
    assert prototype.embed_url("od-1") is None
    assert prototype.preview_url("od-1", "home.html") is None


def test_embed_and_preview_url_built_from_public_base(monkeypatch):
    monkeypatch.setenv("LOTHAL_OD_PUBLIC_BASE_URL", "https://od.lothal.app/")
    assert prototype.embed_url("od-1") == "https://od.lothal.app/projects/od-1"
    assert prototype.preview_url("od-1", "/home.html") == "https://od.lothal.app/artifacts/od-1/home.html"


def test_embed_url_none_without_project(monkeypatch):
    monkeypatch.setenv("LOTHAL_OD_PUBLIC_BASE_URL", "https://od.lothal.app")
    assert prototype.embed_url(None) is None
