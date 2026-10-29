"""The scan that decides which documents a deploy carries.

The cases here are the ones that cost something when wrong: a file counted twice, a file
missed because it sat in a list or a nested flow, and a value that is not a storage key
being reported as one — the last would have the deploy claim success and the flow fail at
run time instead.
"""

from copy import deepcopy
from uuid import uuid4

import pytest
from langflow.utils.flow_files import (
    FileKeyCollisionError,
    collect_flow_files,
    flow_file_target_key,
    rewrite_flow_file_keys_in_place,
)
from lfx.components.files_and_knowledge.file import FileComponent

USER = str(uuid4())
FLOW = str(uuid4())


def _node(node_id: str, template: dict, nested: dict | None = None) -> dict:
    inner: dict = {"template": template}
    if nested is not None:
        inner["flow"] = {"data": nested}
    return {"id": node_id, "data": {"node": inner}}


def _file_field(**kwargs) -> dict:
    return {"type": "file", "show": True, **kwargs}


@pytest.mark.parametrize("location", ["AWS", "Google Drive"])
def test_should_ignore_local_file_after_switching_to_cloud_storage(location):
    key = f"{USER}/removed-local.pdf"
    template = {"path": _file_field(file_path=[key], list=True)}
    component = FileComponent()
    component.update_build_config(template, [{"name": location}], "storage_location")
    data = {"nodes": [_node("File-a", template)]}

    found = collect_flow_files(data)
    mapping = rewrite_flow_file_keys_in_place(data, FLOW)

    assert found.keys == []
    assert found.unresolved == []
    assert mapping == {}
    assert template["path"]["file_path"] == [key]

    component.update_build_config(template, [{"name": "Local"}], "storage_location")

    assert collect_flow_files(data).keys == [key]
    assert rewrite_flow_file_keys_in_place(data, FLOW) == {key: f"{FLOW}/removed-local.pdf"}


@pytest.mark.parametrize(
    ("field_name", "flags", "active"),
    [
        ("path", {"show": True}, True),
        ("path", {"show": False}, False),
        ("path", {}, False),
        ("path", {"show": False, "override_skip": True}, True),
        ("_type", {"show": True}, False),
        ("code", {"show": False}, True),
        ("path", {"show": True, "type": "other", "_input_type": "FileInput"}, False),
    ],
)
def test_should_collect_and_rewrite_only_active_file_inputs(field_name, flags, active):
    key = f"{USER}/report.pdf"
    field = {"type": "file", "file_path": key, **flags}
    data = {"nodes": [_node("File-a", {field_name: field})]}

    found = collect_flow_files(data)
    mapping = rewrite_flow_file_keys_in_place(data, FLOW)

    assert found.keys == ([key] if active else [])
    assert mapping == ({key: f"{FLOW}/report.pdf"} if active else {})
    assert field["file_path"] == (f"{FLOW}/report.pdf" if active else key)


def test_should_return_the_key_when_a_file_field_holds_one():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path=f"{USER}/report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == [f"{USER}/report.pdf"]
    assert found.unresolved == []


def test_should_read_value_when_file_path_is_empty():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path="", value=f"{USER}/report.pdf")})]}

    assert collect_flow_files(data).keys == [f"{USER}/report.pdf"]


def test_should_prefer_file_path_over_value_as_the_graph_does():
    data = {
        "nodes": [_node("File-aaa", {"path": _file_field(file_path=f"{USER}/real.pdf", value=f"{USER}/stale.pdf")})]
    }

    assert collect_flow_files(data).keys == [f"{USER}/real.pdf"]


def test_should_return_every_entry_when_the_field_holds_a_list():
    data = {
        "nodes": [_node("File-aaa", {"paths": _file_field(list=True, file_path=[f"{USER}/a.pdf", f"{USER}/b.pdf"])})]
    }

    assert collect_flow_files(data).keys == [f"{USER}/a.pdf", f"{USER}/b.pdf"]


def test_should_recognise_a_file_field_by_input_type():
    data = {
        "nodes": [_node("File-aaa", {"path": {"_input_type": "FileInput", "show": True, "value": f"{FLOW}/x.pdf"}})]
    }

    assert collect_flow_files(data).keys == [f"{FLOW}/x.pdf"]


def test_should_count_a_shared_document_once():
    data = {
        "nodes": [
            _node("File-aaa", {"path": _file_field(file_path=f"{USER}/shared.pdf")}),
            _node("File-bbb", {"path": _file_field(file_path=f"{USER}/shared.pdf")}),
        ]
    }

    assert collect_flow_files(data).keys == [f"{USER}/shared.pdf"]


def test_should_count_one_document_once_when_the_namespace_differs_in_case():
    data = {
        "nodes": [
            _node("File-aaa", {"path": _file_field(file_path=f"{USER}/shared.pdf")}),
            _node("File-bbb", {"path": _file_field(file_path=f"{USER.upper()}/shared.pdf")}),
        ]
    }

    assert collect_flow_files(data).keys == [f"{USER}/shared.pdf"]


def test_should_find_files_inside_a_nested_flow():
    nested = {"nodes": [_node("File-inner", {"path": _file_field(file_path=f"{FLOW}/inner.pdf")})]}
    data = {
        "nodes": [
            _node("File-outer", {"path": _file_field(file_path=f"{USER}/outer.pdf")}),
            _node("RunFlow-aaa", {}, nested=nested),
        ]
    }

    # Sorted, because the two namespaces are random UUIDs and their order varies by run.
    assert collect_flow_files(data).keys == sorted([f"{FLOW}/inner.pdf", f"{USER}/outer.pdf"])


def test_should_report_an_absolute_path_as_unresolved_rather_than_a_key():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path="/var/data/report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == []
    assert [u.value for u in found.unresolved] == ["/var/data/report.pdf"]
    assert "absolute path" in found.unresolved[0].reason


def test_should_report_a_windows_path_as_unresolved():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path="C:\\data\\report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == []
    assert "absolute path" in found.unresolved[0].reason


def test_should_report_a_bare_file_name_as_unresolved():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path="report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == []
    assert "bare file name" in found.unresolved[0].reason


def test_should_report_a_non_uuid_namespace_as_unresolved():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path="documents/report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == []
    assert "not a user or flow id" in found.unresolved[0].reason


def test_should_report_a_nested_key_as_unresolved():
    data = {"nodes": [_node("File-aaa", {"path": _file_field(file_path=f"{USER}/sub/report.pdf")})]}

    found = collect_flow_files(data)

    assert found.keys == []
    assert "storage key" in found.unresolved[0].reason


def test_should_name_the_node_and_field_on_an_unresolved_reference():
    data = {"nodes": [_node("File-aaa", {"document": _file_field(file_path="report.pdf")})]}

    unresolved = collect_flow_files(data).unresolved[0]

    assert (unresolved.node_id, unresolved.field_name) == ("File-aaa", "document")


def test_should_ignore_fields_that_are_not_file_inputs():
    data = {
        "nodes": [
            _node(
                "Chat-aaa",
                {
                    "text": {"type": "str", "value": f"{USER}/not-a-file.pdf"},
                    "path": _file_field(file_path=f"{USER}/real.pdf"),
                },
            )
        ]
    }

    assert collect_flow_files(data).keys == [f"{USER}/real.pdf"]


def test_should_return_nothing_when_a_file_field_is_empty():
    data = {
        "nodes": [
            _node("File-aaa", {"path": _file_field(file_path="", value="")}),
            _node("File-bbb", {"paths": _file_field(list=True, file_path=[])}),
            _node("File-ccc", {"path": _file_field()}),
        ]
    }

    found = collect_flow_files(data)

    assert (found.keys, found.unresolved) == ([], [])


def test_should_survive_flow_data_that_is_missing_or_malformed():
    for data in (None, {}, {"nodes": None}, {"nodes": ["not a dict"]}, {"nodes": [{"data": None}]}):
        found = collect_flow_files(data)
        assert (found.keys, found.unresolved) == ([], [])


# --- the rewrite a deploy package applies -------------------------------------------------


def test_should_move_a_key_into_the_flow_namespace_keeping_its_name():
    assert flow_file_target_key(f"{USER}/report.pdf", FLOW) == f"{FLOW}/report.pdf"


def test_should_return_what_it_rewrote_including_a_key_already_in_place():
    data = {
        "nodes": [
            _node("File-a", {"path": _file_field(file_path=f"{USER}/a.pdf")}),
            _node("File-b", {"path": _file_field(file_path=f"{FLOW}/b.pdf")}),
        ]
    }

    mapping = rewrite_flow_file_keys_in_place(data, FLOW)

    assert mapping == {f"{USER}/a.pdf": f"{FLOW}/a.pdf", f"{FLOW}/b.pdf": f"{FLOW}/b.pdf"}


def test_should_rewrite_the_slot_the_graph_reads_and_leave_the_other():
    field = _file_field(file_path=f"{USER}/real.pdf", value=f"{USER}/stale.pdf")
    data = {"nodes": [_node("File-a", {"path": field})]}

    rewrite_flow_file_keys_in_place(data, FLOW)

    assert field["file_path"] == f"{FLOW}/real.pdf"
    assert field["value"] == f"{USER}/stale.pdf"


def test_should_rewrite_value_when_file_path_is_empty():
    field = _file_field(file_path="", value=f"{USER}/report.pdf")
    data = {"nodes": [_node("File-a", {"path": field})]}

    rewrite_flow_file_keys_in_place(data, FLOW)

    assert field["value"] == f"{FLOW}/report.pdf"


def test_should_rewrite_files_in_a_nested_flow_onto_the_deployed_flow():
    inner_field = _file_field(file_path=f"{USER}/inner.pdf")
    nested = {"nodes": [_node("File-inner", {"path": inner_field})]}
    data = {"nodes": [_node("Group-a", {}, nested=nested)]}

    rewrite_flow_file_keys_in_place(data, FLOW)

    assert inner_field["file_path"] == f"{FLOW}/inner.pdf"


def test_should_treat_one_document_written_in_two_cases_as_the_same_file():
    data = {
        "nodes": [
            _node("File-a", {"path": _file_field(file_path=f"{USER}/report.pdf")}),
            _node("File-b", {"path": _file_field(file_path=f"{USER.upper()}/report.pdf")}),
        ]
    }

    mapping = rewrite_flow_file_keys_in_place(data, FLOW)

    assert mapping == {f"{USER}/report.pdf": f"{FLOW}/report.pdf"}


def test_should_refuse_when_a_user_file_and_a_flow_file_share_a_name():
    data = {
        "nodes": [
            _node("File-a", {"path": _file_field(file_path=f"{USER}/report.pdf")}),
            _node("File-b", {"path": _file_field(file_path=f"{FLOW}/report.pdf")}),
        ]
    }

    with pytest.raises(FileKeyCollisionError, match=r"report\.pdf"):
        rewrite_flow_file_keys_in_place(data, FLOW)


def test_should_agree_with_the_scan_on_which_keys_move():
    data = {
        "nodes": [
            _node("File-a", {"paths": _file_field(list=True, file_path=[f"{USER}/a.pdf", "report.pdf"])}),
            _node("File-b", {"path": _file_field(file_path="/abs/b.pdf")}),
        ]
    }
    scanned = collect_flow_files(deepcopy(data)).keys

    mapping = rewrite_flow_file_keys_in_place(data, FLOW)

    assert sorted(mapping) == scanned


def test_should_rewrite_mapped_keys_and_keep_the_default_for_other_files():
    field = _file_field(file_path=[f"{FLOW.upper()}/report.pdf", f"{USER}/other.pdf"], list=True)
    data = {"nodes": [_node("File-a", {"path": field})]}
    target = f"{FLOW}/report-version-one.pdf"

    mapping = rewrite_flow_file_keys_in_place(data, FLOW, key_mapping={f"{FLOW}/report.pdf": target})

    assert mapping == {f"{FLOW}/report.pdf": target, f"{USER}/other.pdf": f"{FLOW}/other.pdf"}
    assert field["file_path"] == [target, f"{FLOW}/other.pdf"]


def test_should_normalize_the_mapped_target_namespace():
    field = _file_field(file_path=f"{USER}/report.pdf")
    data = {"nodes": [_node("File-a", {"path": field})]}
    target = f"{FLOW}/report-version-one.pdf"

    mapping = rewrite_flow_file_keys_in_place(
        data, FLOW, key_mapping={f"{USER}/report.pdf": f"{FLOW.upper()}/report-version-one.pdf"}
    )

    assert mapping == {f"{USER}/report.pdf": target}
    assert field["file_path"] == target


@pytest.mark.parametrize("map_both", [False, True])
def test_should_refuse_a_mapped_key_collision(map_both):
    data = {
        "nodes": [
            _node("File-a", {"path": _file_field(file_path=f"{USER}/a.pdf")}),
            _node("File-b", {"path": _file_field(file_path=f"{USER}/b.pdf")}),
        ]
    }
    key_mapping = {f"{USER}/a.pdf": f"{FLOW}/b.pdf"}
    if map_both:
        key_mapping[f"{USER}/b.pdf"] = f"{FLOW}/b.pdf"

    with pytest.raises(FileKeyCollisionError, match=r"b\.pdf"):
        rewrite_flow_file_keys_in_place(data, FLOW, key_mapping=key_mapping)


@pytest.mark.parametrize(
    "target",
    [
        "",
        "report.pdf",
        "/var/data/report.pdf",
        f"{USER}/report.pdf",
        f"{FLOW}/../report.pdf",
        f"{FLOW}/sub/report.pdf",
        f"{FLOW}/.",
        f"{FLOW}/bad\x00.pdf",
        None,
    ],
)
def test_should_refuse_a_mapped_target_outside_the_flow_storage(target):
    field = _file_field(file_path=f"{USER}/report.pdf")
    data = {"nodes": [_node("File-a", {"path": field})]}

    with pytest.raises(ValueError, match="mapped file key"):
        rewrite_flow_file_keys_in_place(data, FLOW, key_mapping={f"{USER}/report.pdf": target})

    assert field["file_path"] == f"{USER}/report.pdf"
