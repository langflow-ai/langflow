"""Microsoft list results remain inspectable in either output evaluation order."""

from __future__ import annotations

import pytest
from lfx_microsoft import OutlookCalendarListComponent, OutlookSearchComponent, SharePointListComponent
from microsoft_testkit import TransportRecorder, build_component, credential, graph_fixture, json_response


@pytest.mark.parametrize("next_link_first", [False, True])
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    ("component_class", "inputs", "fixture_name", "output_name", "scope"),
    [
        (OutlookSearchComponent, {}, "messages_page1", "messages", "Mail.Read"),
        (
            OutlookCalendarListComponent,
            {"start_time": "2026-09-01T00:00:00", "end_time": "2026-09-02T00:00:00"},
            "calendar_view",
            "events",
            "Calendars.Read",
        ),
        (SharePointListComponent, {}, "drive_children", "items", "Files.Read"),
    ],
)
async def test_list_artifacts_include_records_and_next_link(
    resolver_factory,
    component_class,
    inputs,
    fixture_name,
    output_name,
    scope,
    empty,
    next_link_first,
) -> None:
    resolver_factory(credential(scopes={scope}))
    body = graph_fixture(fixture_name)
    if empty:
        body["value"] = []
        body.pop("@odata.nextLink", None)
    expected_rows = body["value"]
    expected_next_link = body.get("@odata.nextLink", "")
    recorder = TransportRecorder(lambda _request: json_response(body))
    component = build_component(
        component_class,
        recorder,
        connection="microsoft/work",
        top=max(len(expected_rows), 1),
        **inputs,
    )
    component._vertex.outgoing_edges = []
    if next_link_first:
        component.outputs = list(reversed(component.outputs))

    results, artifacts = await component._build_results()

    assert [row.data for row in results[output_name]] == expected_rows
    assert artifacts[output_name]["repr"] == str(results[output_name])
    assert artifacts[output_name]["type"] == "array"
    assert [row["data"] for row in artifacts[output_name]["raw"]] == expected_rows
    assert results["next_link"].text == expected_next_link
    assert artifacts["next_link"]["repr"] == expected_next_link
    assert artifacts["next_link"]["type"] == "text"
    assert artifacts["next_link"]["raw"] == expected_next_link
    assert len(recorder.requests) == 1
