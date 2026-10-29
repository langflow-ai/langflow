"""Saved nodes of the MrScraper components retired in 1.13.0 are reported and fail as retired.

Each case is a node saved with source that a 1.12 release shipped, taken from the inventory
fixtures. lfx-bundles is not installed here, so the registry is built from lfx's own classes,
which the bundle's classes subclass without changes.
"""

import json
import pathlib

import pytest
import typer
from lfx.base.mrscraper import retired
from lfx.cli.upgrade import upgrade_command
from lfx.custom.utils import create_component_template
from lfx.exceptions.component import ComponentBuildError
from lfx.graph.graph.base import Graph

FIXTURES = pathlib.Path(__file__).parents[2] / "custom" / "component" / "historical_storage_source_fixtures.json"
SHIPPED = {
    fingerprint: fixture
    for fingerprint, fixture in json.loads(FIXTURES.read_text(encoding="utf-8")).items()
    if fixture["class_name"].startswith("Mrscraper")
}
RETIRED = sorted({fixture["class_name"] for fixture in SHIPPED.values()})
SHIPPED_IDS = [
    f"{fixture['class_name']}-{fixture['tag']}-{fingerprint[:8]}" for fingerprint, fixture in SHIPPED.items()
]


def test_every_retired_component_has_shipped_sources():
    assert RETIRED == [
        "MrscraperAiScraper",
        "MrscraperBatchScrape",
        "MrscraperCrawlWebsite",
        "MrscraperGetResult",
        "MrscraperGetResults",
        "MrscraperRunAiScraper",
        "MrscraperRunManualScraper",
    ]


def _saved_flow(fixture: dict) -> dict:
    """A flow with one node of the retired component, saved with the shipped source."""
    component_class = getattr(retired, fixture["class_name"])
    node_id = f"{fixture['class_name']}-saved"
    node = component_class(_id=node_id).to_frontend_node()["data"]["node"]
    node["template"]["code"]["value"] = fixture["source"]
    node["template"]["api_token"].update(value="saved-token", load_from_db=False)
    component_type = f"ext:mrscraper:{fixture['class_name']}@official"
    return {"nodes": [{"id": node_id, "data": {"id": node_id, "type": component_type, "node": node}}], "edges": []}


def _registry() -> dict:
    return {
        "mrscraper": {
            f"ext:mrscraper:{name}@official": create_component_template(component_extractor=getattr(retired, name)())[0]
            for name in RETIRED
        }
    }


@pytest.mark.parametrize("fingerprint", SHIPPED, ids=SHIPPED_IDS)
def test_lfx_upgrade_reports_the_saved_node_as_retired(tmp_path, capsys, fingerprint):
    fixture = SHIPPED[fingerprint]
    flow_file = tmp_path / "flow.json"
    flow_file.write_text(json.dumps(_saved_flow(fixture)))
    before = flow_file.read_text()

    with pytest.raises(typer.Exit) as exc_info:
        upgrade_command(flow_file, write=True, registry=_registry())

    assert exc_info.value.exit_code == 1
    name = fixture["class_name"]
    display_name = getattr(retired, name).display_name
    assert (
        f"[RETIRED] {display_name} (ext:mrscraper:{name}@official) - id: {name}-saved"
        " - retired in 1.13.0, replace with: mrscraper.MrscraperFetchHtml"
    ) in capsys.readouterr().out
    assert flow_file.read_text() == before


@pytest.mark.parametrize("fingerprint", SHIPPED, ids=SHIPPED_IDS)
async def test_saved_node_fails_with_the_retired_message_when_built(fingerprint):
    fixture = SHIPPED[fingerprint]
    graph = Graph.from_payload(_saved_flow(fixture), flow_id="retired-mrscraper")
    vertex = graph.get_vertex(f"{fixture['class_name']}-saved")

    with pytest.raises(ComponentBuildError) as exc_info:
        await vertex.build(fallback_to_env_vars=False)

    display_name = getattr(retired, fixture["class_name"]).display_name
    assert (
        f"{display_name} was retired in Langflow 1.13.0. Replace this node with MrScraper Scraper API "
        "and update the components that read its output."
    ) in str(exc_info.value)
