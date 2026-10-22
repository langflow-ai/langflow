"""The assistant edits a Smart Router's routes as plain rows; their edges must survive."""

from lfx.mcp.server import _keep_row_ids

SAVED = [
    {"route_category": "Billing", "route_id": "category_1_result"},
    {"route_category": "Support", "route_id": "category_2_result"},
]


def test_rows_without_ids_keep_the_ids_of_the_rows_they_replace():
    renamed = [{"route_category": "Payments"}, {"route_category": "Support"}, {"route_category": "Sales"}]
    assert [row.get("route_id") for row in _keep_row_ids(SAVED, renamed)] == [
        "category_1_result",
        "category_2_result",
        None,
    ]


def test_rows_that_carry_ids_are_left_alone():
    rows = [{"route_category": "Support", "route_id": "category_2_result"}, {"route_category": "New"}]
    assert _keep_row_ids(SAVED, rows) == rows


def test_values_that_are_not_tables_pass_through():
    assert _keep_row_ids("old", "new") == "new"
    assert _keep_row_ids([1, 2], [3]) == [3]
