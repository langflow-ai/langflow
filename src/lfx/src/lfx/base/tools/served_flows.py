"""Find a flow in the folder ``lfx serve`` or ``lfx run`` loaded the running graph from.

Standalone lfx has no database to look a flow up in, so a flow that calls another flow needs
the folder it came from.
"""

import json
from pathlib import Path

from lfx.schema.data import Data


def _read_flow_file(path: Path) -> Data | None:
    """Read a flow JSON file, or return ``None`` if it is unreadable.

    One unparseable file in the folder must not fail the run; it is simply not a candidate.
    """
    try:
        return Data(data=json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _flow_file_in(directory: Path, flow_name: str) -> Path | None:
    """Return the flow file named ``flow_name`` inside ``directory``, if it is there.

    A flow name is data, so it is kept from escaping the served folder: ``../../secrets``
    resolves outside and is refused rather than read.
    """
    candidate = directory / f"{flow_name}.json"
    try:
        if not candidate.resolve().is_relative_to(directory.resolve()):
            return None
    except OSError:
        return None
    return candidate if candidate.is_file() else None


def served_flow(graph, flow_name: str | None, flow_id: str | None) -> Data | None:
    """Resolve a flow from the folder ``graph`` was served or run from.

    Returns ``None`` when there is no folder on the context, which is the langflow case: the
    caller then falls through to the database lookup.
    """
    project_dir = (graph.context or {}).get("project_dir") if graph is not None else None
    if not project_dir:
        return None
    directory = Path(project_dir)

    if (
        flow_name
        and (by_stem := _flow_file_in(directory, flow_name)) is not None
        and (payload := _read_flow_file(by_stem)) is not None
    ):
        return payload

    # Exports sanitise the filename, so the stem and the flow's own name can diverge.
    # ponytail: a served folder is a handful of files, so a linear scan is enough. Index
    # it if that stops being true.
    for path in sorted(directory.glob("*.json")):
        payload = _read_flow_file(path)
        if payload is None:
            continue
        raw = payload.data
        if (flow_name and raw.get("name") == flow_name) or (flow_id and str(raw.get("id")) == str(flow_id)):
            return payload
    return None
