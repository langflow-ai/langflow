"""The scan that decides which documents a deploy carries.

The cases here are the ones that cost something when wrong: a file counted twice, a file
missed because it sat in a list or a nested flow, and a value that is not a storage key
being reported as one — the last would have the deploy claim success and the flow fail at
run time instead.
"""

from uuid import uuid4

from langflow.utils.flow_files import collect_flow_files

USER = str(uuid4())
FLOW = str(uuid4())


def _node(node_id: str, template: dict, nested: dict | None = None) -> dict:
    inner: dict = {"template": template}
    if nested is not None:
        inner["flow"] = {"data": nested}
    return {"id": node_id, "data": {"node": inner}}


def _file_field(**kwargs) -> dict:
    return {"type": "file", **kwargs}


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
    data = {"nodes": [_node("File-aaa", {"path": {"_input_type": "FileInput", "value": f"{FLOW}/x.pdf"}})]}

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

    assert collect_flow_files(data).keys == [f"{FLOW}/inner.pdf", f"{USER}/outer.pdf"]


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
