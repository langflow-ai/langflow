"""The assistant edits a Smart Router's routes as plain rows; their edges must survive."""

from lfx.mcp.server import _keep_row_ids

SAVED = [
    {"route_category": "Billing", "route_id": "category_1_result"},
    {"route_category": "Support", "route_id": "category_2_result"},
]


def _ids(rows):
    return [(row["route_category"], row.get("route_id")) for row in rows]


def test_a_renamed_route_keeps_its_id():
    renamed = [{"route_category": "Payments"}, {"route_category": "Support"}, {"route_category": "Sales"}]
    assert _ids(_keep_row_ids(SAVED, renamed)) == [
        ("Payments", "category_1_result"),
        ("Support", "category_2_result"),
        ("Sales", None),
    ]


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
