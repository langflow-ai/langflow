"""The assistant edits a Smart Router's routes as plain rows; their edges must survive."""

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
