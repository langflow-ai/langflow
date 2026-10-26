"""The assistant edits a Smart Router's routes as plain rows; their edges must survive."""

import copy
from unittest.mock import AsyncMock

import pytest
from lfx.mcp.flow_builder_tools import (
    ConfigureComponent,
    drain_flow_events,
    get_working_flow,
    init_working_flow,
    reset_working_flow,
)
from lfx.mcp.server import _keep_row_ids

SAVED = [
    {"route_category": "Billing", "route_description": "Invoices and refunds", "route_id": "category_1_result"},
    {"route_category": "Support", "route_description": "Bugs and errors", "route_id": "category_2_result"},
]


def _ids(rows):
    return [(row["route_category"], row.get("route_id")) for row in rows]


def test_a_renamed_route_keeps_its_id():
    renamed = [
        {"route_category": "Payments", "route_description": "Invoices and refunds"},
        {"route_category": "Support"},
    ]
    assert _ids(_keep_row_ids(SAVED, renamed)) == [("Payments", "category_1_result"), ("Support", "category_2_result")]


def test_a_route_added_alongside_a_deletion_gets_a_new_output():
    # Sales is new, not Billing renamed: it must not take Billing's edge.
    assert _ids(_keep_row_ids(SAVED, [{"route_category": "Support"}, {"route_category": "Sales"}])) == [
        ("Support", "category_2_result"),
        ("Sales", None),
    ]


def test_names_match_ignoring_case_as_the_router_does():
    swapped = [{"route_category": " support"}, {"route_category": "BILLING"}]
    assert _ids(_keep_row_ids(SAVED, swapped)) == [(" support", "category_2_result"), ("BILLING", "category_1_result")]


def test_deleting_or_reordering_never_hands_a_route_another_ones_edge():
    assert _ids(_keep_row_ids(SAVED, [{"route_category": "Support"}])) == [("Support", "category_2_result")]
    reordered = [{"route_category": "Support"}, {"route_category": "Billing"}]
    assert _ids(_keep_row_ids(SAVED, reordered)) == [
        ("Support", "category_2_result"),
        ("Billing", "category_1_result"),
    ]


def test_rows_that_carry_ids_are_left_alone():
    rows = [{"route_category": "Support", "route_id": "category_2_result"}, {"route_category": "New"}]
    assert _keep_row_ids(SAVED, rows) == rows


def test_values_that_are_not_tables_pass_through():
    assert _keep_row_ids("old", "new") == "new"
    assert _keep_row_ids([1, 2], [3]) == [3]


def test_a_description_two_saved_routes_share_never_hands_over_an_edge():
    # Billing is deleted and Support renamed to Help: which one Help was can't be told.
    saved = [
        {"route_category": "Billing", "route_description": "Tickets", "route_id": "category_1_result"},
        {"route_category": "Support", "route_description": "Tickets", "route_id": "category_2_result"},
    ]
    assert _ids(_keep_row_ids(saved, [{"route_category": "Help", "route_description": "Tickets"}])) == [("Help", None)]


def test_a_description_two_sent_routes_share_never_hands_over_an_edge():
    sent = [
        {"route_category": "Payments", "route_description": "Invoices and refunds"},
        {"route_category": "Refunds", "route_description": "Invoices and refunds"},
    ]
    assert _ids(_keep_row_ids(SAVED, sent)) == [("Payments", None), ("Refunds", None)]


def test_names_the_router_tells_apart_keep_their_own_ids():
    saved = [
        {"route_category": "Straße", "route_id": "category_1_result"},
        {"route_category": "Strasse", "route_id": "category_2_result"},
    ]
    reordered = [{"route_category": "Strasse"}, {"route_category": "Straße"}]
    assert _ids(_keep_row_ids(saved, reordered)) == [("Strasse", "category_2_result"), ("Straße", "category_1_result")]


@pytest.fixture(params=[("routes", "Choice", "category"), ("score_levels", "Score", "level")])
def configured_router(request):
    table, kind, prefix = request.param
    reset_working_flow()
    rows = [{**row, "route_id": f"{prefix}_{i}_result"} for i, row in enumerate(SAVED, 1)]
    outputs = [{"name": row["route_id"], "display_name": row["route_category"]} for row in rows]
    outputs.append({"name": "default_result", "display_name": "Else"})
    flow = {
        "data": {
            "nodes": [
                {
                    "id": "router",
                    "data": {
                        "id": "router",
                        "type": "SmartRouter",
                        "node": {
                            "template": {
                                table: {"type": "table", "value": rows},
                                "routing_mode": {"type": "str", "value": "Decision Model"},
                                "decision_kind": {"type": "str", "value": kind},
                            },
                            "outputs": outputs,
                        },
                    },
                }
            ],
            "edges": [
                {"source": "router", "sourceHandle": row["route_id"], "target": row["route_category"]} for row in rows
            ],
        },
    }
    init_working_flow(copy.deepcopy(flow), "flow")
    yield table, prefix, flow
    reset_working_flow()


def test_in_app_configure_preserves_reordered_and_renamed_route_destinations(configured_router):
    table, prefix, original = configured_router
    tool = ConfigureComponent()
    tool.set(
        component_id="router",
        params={
            table: [
                {"route_category": "Support"},
                {"route_category": "Payments", "route_description": "Invoices and refunds"},
            ]
        },
    )
    result = tool.configure_component()
    assert "error" not in result.data
    updated = get_working_flow()["data"]
    node = updated["nodes"][0]["data"]["node"]
    assert _ids(node["template"][table]["value"]) == [
        ("Support", f"{prefix}_2_result"),
        ("Payments", f"{prefix}_1_result"),
    ]
    assert node["outputs"] == [
        {"name": f"{prefix}_2_result", "display_name": "Support"},
        {"name": f"{prefix}_1_result", "display_name": "Payments"},
        {"name": "default_result", "display_name": "Else"},
    ]
    assert updated["edges"] == original["data"]["edges"]
    assert drain_flow_events()[-1]["outputs"] == node["outputs"]


@pytest.mark.parametrize(
    "incoming",
    [
        [{"route_category": "Support"}],
        [{"route_category": "Support"}, {"route_category": "Billing"}, {"route_category": "Sales"}],
        [{"route_category": "Support"}, {"route_category": "Sales"}],
    ],
)
def test_in_app_rejects_structural_route_edits_without_mutating_flow(configured_router, incoming):
    table, _, original = configured_router
    tool = ConfigureComponent()
    tool.set(component_id="router", params={table: incoming})
    result = tool.configure_component()
    assert "updating its outputs" in result.data["error"]
    assert get_working_flow() == original
    assert not drain_flow_events()


async def test_standalone_mcp_still_refreshes_structural_route_edits(configured_router, monkeypatch):
    from lfx.mcp import server

    table, prefix, flow = configured_router
    node = flow["data"]["nodes"][0]["data"]["node"]
    node["template"][table]["real_time_refresh"] = True
    updated = copy.deepcopy(node)
    updated["template"][table]["value"] = [{"route_category": "Support", "route_id": f"{prefix}_2_result"}]
    updated["outputs"] = [updated["outputs"][1], updated["outputs"][2]]
    client = AsyncMock()
    client.post.return_value = updated
    save = AsyncMock()
    monkeypatch.setattr(server, "_get_client", lambda: client)
    monkeypatch.setattr(server, "_get_flow", AsyncMock(return_value=flow))
    monkeypatch.setattr(server, "_patch_flow", save)

    result = await server.configure_component("flow", "router", {table: [{"route_category": "Support"}]})

    assert result["configured"] == [table]
    assert client.post.call_args.kwargs["json_data"]["field_value"] == updated["template"][table]["value"]
    assert flow["data"]["nodes"][0]["data"]["node"] == updated
    save.assert_awaited_once_with("flow", flow)


@pytest.mark.usefixtures("configured_router")
def test_unrelated_configure_without_saved_outputs_still_works():
    flow = get_working_flow()
    del flow["data"]["nodes"][0]["data"]["node"]["outputs"]
    tool = ConfigureComponent()
    tool.set(component_id="router", params={"routing_mode": "Language Model"})
    result = tool.configure_component()
    assert "error" not in result.data
    assert "outputs" not in drain_flow_events()[-1]
