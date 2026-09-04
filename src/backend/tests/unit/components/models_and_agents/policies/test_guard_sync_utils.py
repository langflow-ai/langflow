from copy import deepcopy

from lfx.components.models_and_agents.policies.guard_sync_utils import (
    GENERATED_GUARD_INFO_PREFIX,
    sync_generated_guard_code_inputs,
)


def _generated_field(name: str, value: str) -> dict:
    return {
        "type": "code",
        "dynamic": True,
        "info": f"{GENERATED_GUARD_INFO_PREFIX}{name}",
        "value": value,
    }


def test_sync_preserves_generated_fields_when_step2_directory_is_missing(tmp_path):
    build_config = {
        "result.json": _generated_field("result.json", "persisted result"),
        "test_project/guard.py": _generated_field("test_project/guard.py", "persisted guard"),
        "project": {"type": "str", "value": "test_project"},
    }
    original_config = deepcopy(build_config)

    result = sync_generated_guard_code_inputs(
        build_config=build_config,
        work_dir=tmp_path / "missing_project",
        step2_subdir="Step_2",
        project_name="test_project",
    )

    assert result is build_config
    assert result == original_config


def test_sync_preserves_generated_fields_when_step2_path_is_not_a_directory(tmp_path):
    work_dir = tmp_path / "test_project"
    work_dir.mkdir()
    (work_dir / "Step_2").write_text("not a directory", encoding="utf-8")
    build_config = {
        "result.json": _generated_field("result.json", "persisted result"),
        "test_project/guard.py": _generated_field("test_project/guard.py", "persisted guard"),
    }
    original_config = deepcopy(build_config)

    result = sync_generated_guard_code_inputs(
        build_config=build_config,
        work_dir=work_dir,
        step2_subdir="Step_2",
        project_name="test_project",
    )

    assert result == original_config


def test_sync_reconciles_generated_fields_when_step2_directory_exists(tmp_path):
    work_dir = tmp_path / "test_project"
    step2_dir = work_dir / "Step_2"
    project_dir = step2_dir / "test_project"
    project_dir.mkdir(parents=True)
    (step2_dir / "result.json").write_text("fresh result", encoding="utf-8")
    (project_dir / "guard.py").write_text("fresh guard", encoding="utf-8")
    (step2_dir / "ignored.py").write_text("ignored", encoding="utf-8")

    build_config = {
        "result.json": _generated_field("result.json", "stale result"),
        "test_project/stale.py": _generated_field("test_project/stale.py", "stale guard"),
        "project": {"type": "str", "value": "test_project"},
    }

    result = sync_generated_guard_code_inputs(
        build_config=build_config,
        work_dir=work_dir,
        step2_subdir="Step_2",
        project_name="test_project",
    )

    assert result["result.json"]["value"] == "fresh result"
    assert result["test_project/guard.py"]["value"] == "fresh guard"
    assert "test_project/stale.py" not in result
    assert "ignored.py" not in result
    assert result["project"] == {"type": "str", "value": "test_project"}
