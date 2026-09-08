"""The rules that decide whether an edit becomes a row, and what that row claims."""

import pytest
from langflow.services.flow_audit.recorder import merge_changes, reconcile_with_graph


def field(name: str, before: str, after: str, **extra) -> dict:
    return {"kind": "field", "field": name, "label": name, "before": before, "after": after, **extra}


def group(target: str, changes: list[dict], badge: str = "modified") -> dict:
    return {"target": target, "label": target, "badge": badge, "changes": changes}


def graph_with(node_id: str, values: dict) -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": node_id,
                    "node": {"display_name": "Agent", "template": {k: {"value": v} for k, v in values.items()}},
                },
            }
        ],
        "edges": [],
    }


class TestMergingASession:
    def test_a_field_edited_twice_keeps_where_it_started(self):
        first = [group("node:a", [field("text", "one", "two")])]
        second = [group("node:a", [field("text", "two", "three")])]

        [merged] = merge_changes(first, second)

        assert merged["changes"] == [field("text", "one", "three")]

    def test_a_field_driven_back_to_its_start_leaves_nothing(self):
        first = [group("node:a", [field("text", "one", "two")])]
        second = [group("node:a", [field("text", "two", "one")])]

        assert merge_changes(first, second) == []

    def test_a_second_component_is_added_to_the_session(self):
        first = [group("node:a", [field("text", "one", "two")])]
        second = [group("node:b", [field("other", "x", "y")])]

        assert {g["target"] for g in merge_changes(first, second)} == {"node:a", "node:b"}

    def test_a_stronger_badge_wins_the_component(self):
        first = [group("node:a", [field("text", "one", "two")])]
        second = [group("node:a", [{"kind": "node_removed"}], badge="removed")]

        [merged] = merge_changes(first, second)

        assert merged["badge"] == "removed"

    def test_truncation_survives_the_merge(self):
        first = [group("node:a", [field("text", "a" * 60, "b" * 60, truncated=True)])]
        second = [group("node:a", [field("text", "b" * 60, "c" * 60, truncated=True)])]

        [merged] = merge_changes(first, second)

        assert merged["changes"][0]["truncated"] is True


class TestReconcilingWithWhatWasWritten:
    def test_a_change_another_writer_reverted_is_dropped(self):
        """Two writers landing at once each record against the state they read.

        The later write silently reverts the earlier one, and without this the
        entry keeps claiming a change the flow no longer has.
        """
        recorded = [group("node:a", [field("f1", "start", "changed1"), field("f2", "start", "changed2")])]

        [reconciled] = reconcile_with_graph(recorded, graph_with("a", {"f1": "start", "f2": "changed2"}))

        assert [c["field"] for c in reconciled["changes"]] == ["f2"]

    def test_a_value_that_moved_on_is_corrected_rather_than_dropped(self):
        recorded = [group("node:a", [field("f1", "start", "changed1")])]

        [reconciled] = reconcile_with_graph(recorded, graph_with("a", {"f1": "something else"}))

        assert reconciled["changes"][0]["after"] == "something else"

    def test_a_secret_is_left_alone_because_its_value_was_never_kept(self):
        recorded = [group("node:a", [{"kind": "field", "field": "api_key", "label": "API Key", "secret": True}])]

        [reconciled] = reconcile_with_graph(recorded, graph_with("a", {"api_key": "sk-new"}))

        assert reconciled["changes"][0]["secret"] is True
        assert "sk-new" not in str(reconciled)

    def test_a_component_that_is_gone_keeps_its_record(self):
        recorded = [group("node:a", [{"kind": "node_removed"}], badge="removed")]

        assert reconcile_with_graph(recorded, graph_with("b", {})) == recorded

    def test_an_edge_group_is_untouched(self):
        recorded = [group("edge:e1", [{"kind": "edge_added", "source": "A", "target": "B"}], badge="added")]

        assert reconcile_with_graph(recorded, graph_with("a", {})) == recorded


@pytest.mark.parametrize("changes", [[], [group("node:a", [])]])
def test_an_empty_summary_stays_empty(changes):
    assert merge_changes(changes, []) == [] or merge_changes(changes, []) == changes
