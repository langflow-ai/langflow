"""Composition ZIP limits apply to metadata as well as flow definitions."""

import io
import zipfile
from uuid import uuid4

import orjson
import pytest
from langflow.api.utils import composition_zip as archive_io
from lfx.projects.archives import ArchivedProject, ProjectComposition


@pytest.fixture
def composition():
    project = ArchivedProject(
        id=uuid4(),
        name="Tool archive",
        project_type="tool-pack",
        project_config={"tools": []},
        flows=[{"id": str(uuid4()), "name": "Empty canvas", "data": {"nodes": [], "edges": []}}],
    )
    return ProjectComposition(root_project_id=project.id, projects=[project])


@pytest.mark.parametrize("limit", ["MAX_ENTRY_UNCOMPRESSED_BYTES", "MAX_COMPOSITION_BYTES"])
async def test_metadata_cannot_bypass_archive_size_limits(composition, monkeypatch, limit):
    contents = archive_io.composition_zip(composition).getvalue()
    monkeypatch.setattr(archive_io, limit, 100)
    with pytest.raises(ValueError, match="size limit"):
        archive_io.composition_zip(composition)
    with pytest.raises(ValueError, match="size limit"):
        await archive_io.extract_composition(contents)


async def test_legacy_archive_is_left_to_legacy_importer():
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, "w") as archive:
        archive.writestr("ordinary.json", "{}")
        archive.writestr("project.meta", '{"project_type":"flows"}')
    assert await archive_io.extract_composition(contents.getvalue()) is None


async def test_invalid_flow_json_rejects_whole_composition(composition):
    original = zipfile.ZipFile(archive_io.composition_zip(composition))
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, "w") as archive:
        for member in original.namelist():
            archive.writestr(member, b"[invalid" if member.endswith(".json") else original.read(member))
    with pytest.raises(orjson.JSONDecodeError):
        await archive_io.extract_composition(contents.getvalue())
