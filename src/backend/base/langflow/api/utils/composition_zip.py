"""Versioned multi-project ZIPs, with strict parsing and legacy root flow members."""

import asyncio
import io
import zipfile

import orjson
from lfx.projects.archives import ProjectComposition

from langflow.api.utils.core import normalize_code_for_import, normalize_flow_for_export
from langflow.api.utils.zip_utils import MAX_ENTRY_UNCOMPRESSED_BYTES, MAX_ZIP_ENTRIES, PROJECT_METADATA_FILENAME

COMPOSITION_FILENAME = "composition.meta"
MAX_COMPOSITION_BYTES = 100 * 1024 * 1024


def composition_zip(composition: ProjectComposition) -> io.BytesIO:
    """Root flows remain readable by generic flow ZIP readers; dependencies use .flow."""
    stream = io.BytesIO()
    manifest = composition.model_dump(mode="json")
    total_size = 0
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:

        def write(member, contents):
            nonlocal total_size
            total_size += len(contents)
            if len(contents) > MAX_ENTRY_UNCOMPRESSED_BYTES or total_size > MAX_COMPOSITION_BYTES:
                msg = "The composition exceeds the archive size limit."
                raise ValueError(msg)
            archive.writestr(member, contents)

        for project in manifest["projects"]:
            members = []
            for flow in project["flows"]:
                member = (
                    f"{flow['id']}.json"
                    if project["id"] == manifest["root_project_id"]
                    else f"dependencies/{project['id']}/{flow['id']}.flow"
                )
                contents = orjson.dumps(
                    normalize_flow_for_export(flow), option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2
                )
                write(member, contents)
                members.append(member)
            project["flows"] = members
        root = next(project for project in manifest["projects"] if project["id"] == manifest["root_project_id"])
        write(
            PROJECT_METADATA_FILENAME,
            orjson.dumps(
                {
                    "project_type": root["project_type"],
                    "project_config": root["project_config"],
                    "composition_version": 1,
                }
            ),
        )
        write(COMPOSITION_FILENAME, orjson.dumps(manifest, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))
    stream.seek(0)
    return stream


def _extract_composition(contents: bytes) -> ProjectComposition | None:
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        names = archive.namelist()
        if COMPOSITION_FILENAME not in names:
            if PROJECT_METADATA_FILENAME in names:
                info = archive.getinfo(PROJECT_METADATA_FILENAME)
                if info.file_size <= MAX_ENTRY_UNCOMPRESSED_BYTES:
                    try:
                        metadata = orjson.loads(archive.read(info))
                    except orjson.JSONDecodeError:
                        metadata = None
                    if isinstance(metadata, dict) and metadata.get("composition_version"):
                        msg = "The composition manifest is missing from this archive."
                        raise ValueError(msg)
            return None
        if len(names) > MAX_ZIP_ENTRIES + 2 or len(names) != len(set(names)):
            msg = "A composition archive has too many or duplicate ZIP members."
            raise ValueError(msg)
        if sum(info.file_size for info in archive.infolist()) > MAX_COMPOSITION_BYTES:
            msg = "The composition exceeds the archive size limit."
            raise ValueError(msg)

        def read(member):
            if not isinstance(member, str) or member not in names:
                msg = "A required composition member is missing from the archive."
                raise ValueError(msg)
            info = archive.getinfo(member)
            if info.file_size > MAX_ENTRY_UNCOMPRESSED_BYTES:
                msg = "A composition member exceeds the archive size limit."
                raise ValueError(msg)
            return orjson.loads(archive.read(info))

        manifest = read(COMPOSITION_FILENAME)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("projects"), list):
            msg = "Invalid composition manifest."
            raise TypeError(msg)
        used = {COMPOSITION_FILENAME, PROJECT_METADATA_FILENAME}
        for project in manifest["projects"]:
            if not isinstance(project, dict) or not isinstance(project.get("flows"), list):
                msg = "Invalid composition project."
                raise TypeError(msg)
            flows = []
            for member in project["flows"]:
                if not isinstance(member, str) or member in used:
                    msg = "A composition flow member is invalid or listed more than once."
                    raise ValueError(msg)
                flow = read(member)
                if not isinstance(flow, dict):
                    msg = "An archived flow must be a JSON object."
                    raise TypeError(msg)
                flows.append(normalize_code_for_import(flow))
                used.add(member)
            project["flows"] = flows
        if set(names) - used:
            msg = "The archive contains flow members not declared by its composition."
            raise ValueError(msg)
        return ProjectComposition.model_validate(manifest)


async def extract_composition(contents: bytes) -> ProjectComposition | None:
    try:
        return await asyncio.to_thread(_extract_composition, contents)
    except (KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        msg = "Invalid composition archive."
        raise ValueError(msg) from exc
