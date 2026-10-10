"""Tests for the component compatibility gate."""

import json
from pathlib import Path

import pytest

from scripts.ci.check_component_compat import find_breaking_changes, load_index, main

REAL_INDEX = Path(__file__).resolve().parents[2] / "src/lfx/src/lfx/_assets/component_index.json"


def _component(inputs: list[str], outputs: list[str]) -> dict:
    template = {"_type": "Component", "code": {"value": "..."}}
    template.update({name: {"type": "str"} for name in inputs})
    return {"template": template, "outputs": [{"name": name} for name in outputs]}


def _write_index(path: Path, components: dict[str, dict]) -> Path:
    path.write_text(json.dumps({"entries": [["category", components]]}), encoding="utf-8")
    return path


def _shape(components: dict[str, dict]) -> dict:
    return {
        name: {"inputs": set(c["template"]) - {"_type", "code"}, "outputs": {o["name"] for o in c["outputs"]}}
        for name, c in components.items()
    }


def test_load_index_reads_inputs_and_outputs(tmp_path):
    path = _write_index(tmp_path / "index.json", {"ChatInput": _component(["input_value"], ["message"])})

    assert load_index(path) == {"ChatInput": {"inputs": {"input_value"}, "outputs": {"message"}}}


def test_load_index_rejects_duplicate_class_names(tmp_path):
    path = tmp_path / "index.json"
    component = _component([], [])
    path.write_text(json.dumps({"entries": [["a", {"X": component}], ["b", {"X": component}]]}), encoding="utf-8")

    with pytest.raises(ValueError, match="more than one category"):
        load_index(path)


def test_load_index_reads_committed_index():
    shape = load_index(REAL_INDEX)

    assert shape
    assert find_breaking_changes(shape, shape, shape) == []


def test_removed_class_input_and_output_are_reported():
    before = _shape({"A": _component(["x", "y"], ["out", "extra"]), "B": _component([], [])})
    head = _shape({"A": _component(["x"], ["out"])})

    assert find_breaking_changes(before, before, head) == [
        "A: input 'y' was removed or renamed.",
        "A: output 'extra' was removed or renamed.",
        "Component 'B' was removed or renamed.",
    ]


def test_additions_are_not_breaking():
    before = _shape({"A": _component(["x"], ["out"])})
    head = _shape({"A": _component(["x", "new"], ["out", "new_out"]), "C": _component([], [])})

    assert find_breaking_changes(before, before, head) == []


def test_removal_on_base_after_branching_is_not_blamed_on_pr():
    # The PR merged base in after B was deleted on base, so head lacks B too.
    merge_base = _shape({"A": _component(["x"], []), "B": _component([], [])})
    base = _shape({"A": _component(["x"], [])})
    head = _shape({"A": _component(["x"], [])})

    assert find_breaking_changes(base, merge_base, head) == []


def test_addition_on_base_after_branching_is_not_blamed_on_pr():
    # D landed on base after the PR branched; the PR head doesn't have it yet.
    merge_base = _shape({"A": _component(["x"], [])})
    base = _shape({"A": _component(["x", "new"], []), "D": _component([], [])})
    head = _shape({"A": _component(["x"], [])})

    assert find_breaking_changes(base, merge_base, head) == []


def _write_scenario(tmp_path: Path) -> list[str]:
    before = {"A": _component(["x"], ["out"])}
    after = {"A": _component([], ["out"])}
    base = _write_index(tmp_path / "base.json", before)
    merge_base = _write_index(tmp_path / "merge_base.json", before)
    head = _write_index(tmp_path / "head.json", after)
    return ["--base", str(base), "--merge-base", str(merge_base), "--head", str(head)]


def test_main_fails_on_breaking_change(tmp_path, capsys):
    assert main(_write_scenario(tmp_path)) == 1
    assert "::error::A: input 'x' was removed or renamed." in capsys.readouterr().out


def test_main_allows_breaking_change_with_flag(tmp_path, capsys):
    assert main([*_write_scenario(tmp_path), "--allow-breaking"]) == 0
    assert "::warning::A: input 'x' was removed or renamed." in capsys.readouterr().out


def test_main_passes_without_changes(tmp_path):
    index = str(_write_index(tmp_path / "index.json", {"A": _component(["x"], ["out"])}))

    assert main(["--base", index, "--merge-base", index, "--head", index]) == 0
