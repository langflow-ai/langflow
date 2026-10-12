"""Tests for the component compatibility gate."""

import json
from pathlib import Path

import pytest

from scripts.ci.check_component_compat import (
    ALIASES_FILE,
    find_problems,
    load_checker,
    load_index,
    load_literal_dict,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_INDEX = REPO_ROOT / "src/lfx/src/lfx/_assets/component_index.json"
CHECKER = REPO_ROOT / "src/lfx/src/lfx/upgrade/checker.py"
TYPE_MIGRATIONS_FILE = REPO_ROOT / "src/lfx/src/lfx/graph/edge/base.py"
LOST_HANDLE = "no longer accept connections; updating a saved node drops edges into them."


@pytest.fixture(scope="module")
def checker():
    return load_checker(CHECKER)


@pytest.fixture(scope="module")
def migrations():
    return load_literal_dict(TYPE_MIGRATIONS_FILE, "TYPE_MIGRATIONS")


def _field(input_types=None, *, required=False, value=""):
    field = {"type": "str", "required": required, "value": value}
    if input_types is not None:
        field["input_types"] = input_types
    return field


def _output(name, types=("Message",), method=None):
    return {"name": name, "types": list(types), "method": method or name, "allows_loop": False}


def _component(fields=None, outputs=None, module="lfx.components.demo.demo.DemoComponent"):
    template = {"_type": "Component", "code": {"value": "..."}}
    template.update(fields or {})
    return {"template": template, "outputs": outputs or [], "metadata": {"module": module}}


def _problems(base, head, *, checker, migrations, aliases=None, repo_root=Path("/nonexistent")):
    return find_problems(base, head, checker=checker, migrations=migrations, aliases=aliases or {}, repo_root=repo_root)


def test_committed_index_is_compatible_with_itself(checker, migrations):
    index = load_index(REAL_INDEX)

    assert index
    assert _problems(index, index, checker=checker, migrations=migrations) == []


def test_removed_output_is_breaking(checker, migrations):
    base = {"A": _component(outputs=[_output("out"), _output("extra")])}
    head = {"A": _component(outputs=[_output("out")])}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'A' changed incompatibly: output 'extra' removed.")
    ]


def test_component_switching_to_dynamic_outputs_is_a_notice(checker, migrations):
    # Components like Run Flow declare no static outputs and build them per flow.
    base = {"A": _component(outputs=[_output("out")])}
    head = {"A": _component(outputs=[])}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        (
            "notice",
            "Component 'A' no longer declares static outputs; saved edges from them resolve only "
            "if the outputs it builds at runtime keep the same names.",
        )
    ]


def test_replacing_every_output_is_breaking(checker, migrations):
    base = {"A": _component(outputs=[_output("out")])}
    head = {"A": _component(outputs=[_output("renamed")])}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'A' changed incompatibly: output 'out' removed.")
    ]


def test_added_output_is_not_breaking(checker, migrations):
    base = {"A": _component(outputs=[_output("out")])}
    head = {"A": _component(outputs=[_output("out"), _output("new")])}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_narrowed_output_types_are_breaking(checker, migrations):
    base = {"A": _component(outputs=[_output("out", types=["Message", "JSON"])])}
    head = {"A": _component(outputs=[_output("out", types=["Message"])])}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'A' changed incompatibly: output 'out' no longer emits JSON.")
    ]


def test_type_migrations_are_not_breaking(checker, migrations):
    base = {"A": _component({"x": _field(["Data"])}, [_output("out", types=["DataFrame"])])}
    head = {"A": _component({"x": _field(["JSON"])}, [_output("out", types=["Table"])])}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_new_required_input_without_default_is_breaking(checker, migrations):
    base = {"A": _component({"x": _field()})}
    head = {"A": _component({"x": _field(), "model": _field(required=True)})}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'A' changed incompatibly: new required input 'model' has no default.")
    ]


def test_new_optional_input_is_not_breaking(checker, migrations):
    base = {"A": _component({"x": _field()})}
    head = {"A": _component({"x": _field(), "y": _field(required=True, value="default")})}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_narrowed_input_types_are_breaking(checker, migrations):
    base = {"A": _component({"x": _field(["Message", "JSON"])})}
    head = {"A": _component({"x": _field(["Message"])})}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'A' changed incompatibly: input 'x' no longer accepts JSON.")
    ]


def test_removed_connectable_input_is_breaking(checker, migrations):
    base = {"A": _component({"llm": _field(["LanguageModel"]), "verbose": _field()})}
    head = {"A": _component({"verbose": _field()})}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        (
            "error",
            f"Component 'A' input(s) 'llm' {LOST_HANDLE}",
        )
    ]


def test_input_that_loses_its_handle_is_breaking(checker, migrations):
    base = {"A": _component({"url": _field(["Message"])})}
    head = {"A": _component({"url": _field()})}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        (
            "error",
            f"Component 'A' input(s) 'url' {LOST_HANDLE}",
        )
    ]


def test_model_field_keeps_its_handle_without_input_types(checker, migrations):
    base = {"A": _component({"model": {"type": "model", "input_types": ["LanguageModel"], "refresh_button": True}})}
    head = {"A": _component({"model": {"type": "model", "refresh_button": True}})}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_removed_model_field_is_breaking_despite_refresh_button(checker, migrations):
    # The editor always draws a handle for model fields, even with a refresh button.
    base = {"A": _component({"model": {"type": "model", "refresh_button": True}})}
    head = {"A": _component()}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        (
            "error",
            f"Component 'A' input(s) 'model' {LOST_HANDLE}",
        )
    ]


def test_removed_non_widget_field_is_breaking(checker, migrations):
    # A type the editor has no widget for is rendered as a handle even without input_types.
    base = {"A": _component({"handle": {"type": "other"}})}
    head = {"A": _component()}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        (
            "error",
            f"Component 'A' input(s) 'handle' {LOST_HANDLE}",
        )
    ]


def test_removed_field_with_refresh_button_had_no_handle(checker, migrations):
    base = {"A": _component({"x": {**_field(["Message"]), "refresh_button": True}})}
    head = {"A": _component()}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_removed_plain_input_is_not_breaking(checker, migrations):
    base = {"A": _component({"llm": _field(["LanguageModel"]), "verbose": _field()})}
    head = {"A": _component({"llm": _field(["LanguageModel"])})}

    assert _problems(base, head, checker=checker, migrations=migrations) == []


def test_removed_component_is_breaking(checker, migrations):
    base = {"A": _component(), "B": _component(module="lfx.components.gone.gone.GoneComponent")}
    head = {"A": _component()}

    assert _problems(base, head, checker=checker, migrations=migrations) == [
        ("error", "Component 'B' was removed or renamed; saved flows that use it will no longer load.")
    ]


def test_component_dropped_by_regeneration_is_diagnosed(checker, migrations, tmp_path):
    source = tmp_path / "src/lfx/src/lfx/components/demo/demo.py"
    source.parent.mkdir(parents=True)
    source.write_text("class DemoComponent(Component):\n    pass\n", encoding="utf-8")
    base = {"Demo": _component()}

    [(level, message)] = _problems(base, {}, checker=checker, migrations=migrations, repo_root=tmp_path)

    assert level == "error"
    assert "src/lfx/src/lfx/components/demo/demo.py still defines DemoComponent" in message
    assert "LEGACY_TYPE_ALIASES" in message
    assert "fix-index" in message


def test_component_moved_to_bundle_is_a_notice(checker, migrations, tmp_path):
    source = tmp_path / "src/bundles/acme/src/lfx_acme/components/acme.py"
    source.parent.mkdir(parents=True)
    source.write_text('class AcmeComponent(Component):\n    name = "Acme"\n', encoding="utf-8")
    base = {"Acme": _component(module="lfx.components.acme.acme.AcmeComponent")}

    assert _problems(base, {}, checker=checker, migrations=migrations, repo_root=tmp_path) == [
        (
            "notice",
            "Component 'Acme' moved to src/bundles/acme/src/lfx_acme/components/acme.py; "
            "saved flows need that bundle installed.",
        )
    ]


def test_rename_through_compatible_alias_is_not_breaking(checker, migrations):
    base = {"Old": _component(outputs=[_output("out")], module="lfx.components.x.old.Old")}
    head = {"New": _component(outputs=[_output("out")])}

    assert _problems(base, head, checker=checker, migrations=migrations, aliases={"Old": "New"}) == []


def test_rename_through_incompatible_alias_is_breaking(checker, migrations):
    base = {"Old": _component(outputs=[_output("out")], module="lfx.components.x.old.Old")}
    head = {"New": _component(outputs=[_output("other")])}

    assert _problems(base, head, checker=checker, migrations=migrations, aliases={"Old": "New"}) == [
        ("error", "Component 'Old' changed incompatibly: output 'out' removed.")
    ]


def test_alias_into_a_bundle_is_a_notice(checker, migrations):
    base = {"Old": _component(module="lfx.components.x.old.Old")}
    aliases = {"Old": "ext:acme:AcmeComponent@official"}

    assert _problems(base, {}, checker=checker, migrations=migrations, aliases=aliases) == [
        (
            "notice",
            "Component 'Old' is aliased to 'ext:acme:AcmeComponent@official'; saved flows need that bundle installed.",
        )
    ]


def test_category_move_is_not_breaking(tmp_path, checker, migrations):
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    base.write_text(json.dumps({"entries": [["one", {"A": _component()}]]}), encoding="utf-8")
    head.write_text(json.dumps({"entries": [["two", {"A": _component()}]]}), encoding="utf-8")

    assert _problems(load_index(base), load_index(head), checker=checker, migrations=migrations) == []


def _write_scenario(tmp_path: Path, head_outputs: list[str]) -> list[str]:
    before = {"entries": [["c", {"A": _component(outputs=[_output("out")])}]]}
    after = {"entries": [["c", {"A": _component(outputs=[_output(name) for name in head_outputs])}]]}
    (tmp_path / "base.json").write_text(json.dumps(before), encoding="utf-8")
    (tmp_path / "head.json").write_text(json.dumps(after), encoding="utf-8")
    aliases = tmp_path / ALIASES_FILE
    aliases.parent.mkdir(parents=True, exist_ok=True)
    aliases.write_text("LEGACY_TYPE_ALIASES: dict[str, str] = {}\n", encoding="utf-8")
    return [
        "--merge-base",
        str(tmp_path / "base.json"),
        "--head",
        str(tmp_path / "head.json"),
        "--checker",
        str(CHECKER),
        "--type-migrations",
        str(TYPE_MIGRATIONS_FILE),
        "--repo-root",
        str(tmp_path),
    ]


def test_main_warns_but_passes_by_default(tmp_path, capsys, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main(_write_scenario(tmp_path, ["renamed"])) == 0
    assert "::warning::Component 'A' changed incompatibly: output 'out' removed." in capsys.readouterr().out
    assert "output 'out' removed" in summary.read_text(encoding="utf-8")


def test_main_fails_in_fail_mode(tmp_path, capsys):
    assert main([*_write_scenario(tmp_path, ["renamed"]), "--fail"]) == 1
    assert "::error::Component 'A' changed incompatibly" in capsys.readouterr().out


def test_main_passes_without_changes(tmp_path, capsys, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main([*_write_scenario(tmp_path, ["out"]), "--fail"]) == 0
    assert "0 finding(s), 0 breaking." in capsys.readouterr().out
    assert "No breaking component changes found." in summary.read_text(encoding="utf-8")


def test_annotation_messages_are_escaped(tmp_path, capsys):
    before = {"entries": [["c", {"A%\nB": _component(module="lfx.components.x.y.Z")}]]}
    (tmp_path / "base.json").write_text(json.dumps(before), encoding="utf-8")
    args = _write_scenario(tmp_path, ["out"])
    (tmp_path / "base.json").write_text(json.dumps(before), encoding="utf-8")

    main(args)

    assert "Component 'A%25\\nB' was removed" in capsys.readouterr().out
