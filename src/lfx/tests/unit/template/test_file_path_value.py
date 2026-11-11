import copy
import platform
import time
import uuid
from pathlib import Path

import pytest
from lfx.components.files_and_knowledge import file as file_module
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.services.deps import get_settings_service
from lfx.template import utils as template_utils


def _set_cache_dir(monkeypatch, cache_dir: Path) -> None:
    monkeypatch.setattr(template_utils, "user_cache_dir", lambda _app_name, _app_author: str(cache_dir))


def test_get_file_path_value_accepts_existing_cache_file(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    uploaded_file = cache_dir / "upload.txt"
    uploaded_file.write_text("allowed")
    _set_cache_dir(monkeypatch, cache_dir)

    assert template_utils.get_file_path_value(str(uploaded_file)) == str(uploaded_file.resolve())


def test_get_file_path_value_rejects_traversal_outside_cache(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")
    traversal_path = cache_dir / ".." / outside_file.name
    _set_cache_dir(monkeypatch, cache_dir)

    assert str(traversal_path).startswith(str(cache_dir))
    assert traversal_path.exists()
    assert template_utils.get_file_path_value(str(traversal_path)) == ""


def test_get_file_path_value_rejects_sibling_prefix_match(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    sibling_dir = tmp_path / "cache-malicious"
    cache_dir.mkdir()
    sibling_dir.mkdir()
    sibling_file = sibling_dir / "outside.txt"
    sibling_file.write_text("secret")
    _set_cache_dir(monkeypatch, cache_dir)

    assert str(sibling_file).startswith(str(cache_dir))
    assert template_utils.get_file_path_value(str(sibling_file)) == ""


def test_get_file_path_value_rejects_directory_inside_cache(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    inner_dir = cache_dir / "subdir"
    inner_dir.mkdir()
    _set_cache_dir(monkeypatch, cache_dir)

    # A directory inside the cache is contained but is not a real file.
    assert template_utils.get_file_path_value(str(inner_dir)) == ""


def test_get_file_path_value_rejects_empty_string(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _set_cache_dir(monkeypatch, cache_dir)

    # An empty string resolves to the CWD (a directory), which must not yield a path.
    assert template_utils.get_file_path_value("") == ""


def test_update_template_field_clears_traversal_file_path(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")
    traversal_path = cache_dir / ".." / outside_file.name
    _set_cache_dir(monkeypatch, cache_dir)

    new_template = {
        "target_file": {
            "type": "file",
            "value": "previous-value",
            "file_path": "",
        }
    }
    previous_value_dict = {
        "type": "file",
        "value": "previous-value",
        "file_path": str(traversal_path),
    }

    template_utils.update_template_field(new_template, "target_file", previous_value_dict)

    assert new_template["target_file"]["value"] == ""
    assert new_template["target_file"]["file_path"] == ""


def test_get_file_path_value_case_insensitive_bypass_windows(tmp_path: Path, monkeypatch) -> None:
    """Test that mixed-case paths cannot bypass security checks on case-insensitive filesystems.

    On Windows (case-insensitive), an attacker might try to use 'Cache' instead of 'cache'
    to bypass path validation. This test ensures the security check is robust against such attempts.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    uploaded_file = cache_dir / "upload.txt"
    uploaded_file.write_text("allowed")
    _set_cache_dir(monkeypatch, cache_dir)

    # Test with the correct case - should work
    assert template_utils.get_file_path_value(str(uploaded_file)) == str(uploaded_file.resolve())

    # On case-insensitive filesystems (Windows), test mixed-case variations
    if platform.system() == "Windows":
        # Try various case permutations of the path
        mixed_case_path = str(uploaded_file).replace("cache", "Cache")
        # Path.resolve() normalizes the case on Windows, so this should still be secure
        result = template_utils.get_file_path_value(mixed_case_path)
        # The resolved path should either match the normalized path or be rejected
        assert result == "" or result == str(uploaded_file.resolve())

        # Try uppercase
        upper_case_path = str(uploaded_file).replace("cache", "CACHE")
        result = template_utils.get_file_path_value(upper_case_path)
        assert result == "" or result == str(uploaded_file.resolve())


@pytest.fixture
def storage_root(tmp_path: Path, monkeypatch) -> Path:
    """A local storage root (config_dir) holding one upload for a user and one for another user."""
    root = (tmp_path / "storage").resolve()
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(root))
    _set_cache_dir(monkeypatch, tmp_path / "cache")
    return root


def _upload(root: Path, namespace: str, name: str) -> str:
    """Write a file the way the upload API stores it and return its storage key."""
    (root / namespace).mkdir(exist_ok=True)
    (root / namespace / name).write_text("uploaded")
    return f"{namespace}/{name}"


def test_get_file_path_value_keeps_uploaded_storage_key(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    key = _upload(storage_root, user_id, "report.pdf")

    assert template_utils.get_file_path_value(key, [user_id]) == key


def test_get_file_path_value_keeps_list_of_uploaded_storage_keys(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    keys = [_upload(storage_root, user_id, "report.pdf"), _upload(storage_root, user_id, "notes.pdf")]

    assert template_utils.get_file_path_value(keys, [user_id]) == keys


def test_get_file_path_value_clears_list_with_one_missing_file(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    keys = [_upload(storage_root, user_id, "report.pdf"), f"{user_id}/missing.pdf"]

    assert template_utils.get_file_path_value(keys, [user_id]) == ""


@pytest.mark.parametrize(
    "path_template",
    [
        pytest.param("{user}/missing.pdf", id="missing-file"),
        pytest.param("{other}/secret.pdf", id="other-user-folder"),
        pytest.param("{user}/../{other}/secret.pdf", id="dotdot-into-other-user"),
        pytest.param("../outside.txt", id="dotdot-out-of-storage"),
        pytest.param("{outside}", id="absolute-path-elsewhere"),
        pytest.param("{user}/link-out.pdf", id="symlink-out-of-storage"),
        pytest.param("{user}/link-other.pdf", id="symlink-into-other-user"),
        # A name over 255 bytes makes Path.is_file raise ENAMETOOLONG instead of returning False.
        pytest.param("{user}/" + "a" * 300, id="file-name-too-long"),
        pytest.param("{cache}/" + "a" * 300, id="cache-file-name-too-long"),
    ],
)
def test_get_file_path_value_clears_paths_outside_the_users_uploads(storage_root: Path, path_template: str) -> None:
    user_id, other_id = str(uuid.uuid4()), str(uuid.uuid4())
    _upload(storage_root, user_id, "report.pdf")
    _upload(storage_root, other_id, "secret.pdf")
    outside = storage_root.parent / "outside.txt"
    outside.write_text("secret")
    cache = storage_root.parent / "cache"
    cache.mkdir()
    (storage_root / user_id / "link-out.pdf").symlink_to(outside)
    (storage_root / user_id / "link-other.pdf").symlink_to(storage_root / other_id / "secret.pdf")
    path = path_template.format(user=user_id, other=other_id, outside=outside, cache=cache)

    assert template_utils.get_file_path_value(path, [user_id]) == ""
    assert template_utils.get_file_path_value([path], [user_id]) == ""


def test_get_file_path_value_clears_storage_key_without_a_scope(storage_root: Path) -> None:
    key = _upload(storage_root, str(uuid.uuid4()), "report.pdf")

    assert template_utils.get_file_path_value(key) == ""


def test_get_file_path_value_clears_storage_key_in_symlinked_user_folder(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    elsewhere = storage_root.parent / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "report.pdf").write_text("secret")
    (storage_root / user_id).symlink_to(elsewhere, target_is_directory=True)

    assert template_utils.get_file_path_value(f"{user_id}/report.pdf", [user_id]) == ""


def test_get_file_path_value_clears_storage_key_in_user_folder_linked_to_another_user(storage_root: Path) -> None:
    """A user folder that links to a sibling user's folder still sits under the storage root once resolved."""
    user_id, other_id = str(uuid.uuid4()), str(uuid.uuid4())
    _upload(storage_root, other_id, "secret.pdf")
    (storage_root / user_id).symlink_to(storage_root / other_id, target_is_directory=True)

    assert template_utils.get_file_path_value(f"{user_id}/secret.pdf", [user_id]) == ""
    assert template_utils.get_file_path_value([f"{user_id}/secret.pdf"], [user_id]) == ""


def test_get_file_path_value_clears_a_list_longer_than_the_limit(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    key = _upload(storage_root, user_id, "report.pdf")
    limit = template_utils.MAX_FILE_PATH_LIST_LENGTH

    assert template_utils.get_file_path_value([key] * limit, [user_id]) == [key] * limit
    assert template_utils.get_file_path_value([key] * (limit + 1), [user_id]) == ""


@pytest.mark.parametrize("entry", [["nested"], {"key": "value"}], ids=["nested-list", "dict"])
def test_get_file_path_value_clears_a_list_with_an_entry_that_is_not_a_path(storage_root: Path, entry) -> None:
    user_id = str(uuid.uuid4())
    key = _upload(storage_root, user_id, "report.pdf")

    assert template_utils.get_file_path_value([key, entry], [user_id]) == ""


@pytest.mark.parametrize("kept", [True, False], ids=["one-upload-repeated", "distinct-missing-files"])
def test_file_fields_check_each_distinct_path_once_and_stop_at_the_first_missing(
    storage_root: Path, *, kept: bool
) -> None:
    """Checking every entry of every field took over a minute at these sizes; one check per field takes milliseconds."""
    user_id = str(uuid.uuid4())
    key = _upload(storage_root, user_id, "report.pdf")
    entries = template_utils.MAX_FILE_PATH_LIST_LENGTH
    paths = [key] * entries if kept else [f"{user_id}/missing-{i}.pdf" for i in range(entries)]
    saved = {f"file_{i}": {"type": "file", "value": "report.pdf", "file_path": paths} for i in range(150)}
    updated = {name: {"type": "file", "value": "", "file_path": ""} for name in saved}

    start = time.perf_counter()
    template_utils.update_template_values(updated, saved, [user_id])

    assert time.perf_counter() - start < 10
    assert all(field["file_path"] == (paths if kept else "") for field in updated.values())


def test_copy_saved_custom_field_values_checks_a_repeated_name_once(storage_root: Path) -> None:
    """custom_fields and file_path both come from the client: repeating a name must not repeat the path checks.

    Checking the 1,000 paths again for each of the 1,500 repeats took over a minute.
    """
    user_id = str(uuid.uuid4())
    keys = [_upload(storage_root, user_id, f"report-{i}.pdf") for i in range(1_000)]
    saved = {
        "display_name": "Prompt",
        "template": {"doc": {"type": "file", "value": "report.pdf", "file_path": keys}},
        "custom_fields": {"template": ["doc"]},
    }
    updated = {
        "display_name": "Prompt",
        "template": {"doc": {"type": "file", "value": ""}},
        "custom_fields": {"template": ["doc"] * 1_500},
    }

    start = time.perf_counter()
    template_utils.copy_saved_custom_field_values(updated, saved, [user_id])

    assert time.perf_counter() - start < 10
    assert updated["template"]["doc"]["file_path"] == keys


def test_copy_saved_custom_field_values_is_linear_in_the_number_of_names() -> None:
    """A quadratic pass over 250,000 names took over a minute."""
    names = [f"var_{i}" for i in range(250_000)]
    saved = {
        "display_name": "Prompt",
        "template": {name: {"type": "str", "value": name} for name in names},
        "custom_fields": {"template": names},
    }
    updated = {
        "display_name": "Prompt",
        "template": {name: {"type": "str", "value": ""} for name in names},
        "custom_fields": {"template": names},
    }

    start = time.perf_counter()
    template_utils.copy_saved_custom_field_values(updated, saved)

    assert time.perf_counter() - start < 10
    assert {name: field["value"] for name, field in updated["template"].items()} == {name: name for name in names}


def test_copy_saved_custom_field_values_does_not_bring_back_a_field_the_update_did_not_generate() -> None:
    saved = {
        "display_name": "Prompt",
        "template": {"gone": {"type": "str", "value": "stale"}},
        "custom_fields": {"template": ["gone"]},
    }
    updated = {"display_name": "Prompt", "template": {}, "custom_fields": {"template": []}}

    template_utils.copy_saved_custom_field_values(updated, saved)

    assert updated == {"display_name": "Prompt", "template": {}, "custom_fields": {"template": []}}


async def _editor_update(saved_node: dict, user_id: str) -> dict:
    """Run the calls POST /api/v1/custom_component makes when the editor updates a node."""
    code = Path(file_module.__file__).read_text(encoding="utf-8")
    # The endpoint passes the saved class name, so the component is resolved with the caller's id
    # whatever name the generic Component class has.
    built, component = build_custom_component_template(
        Component(_code=code), user_id=user_id, class_name=file_module.FileComponent.__name__
    )
    return await component.update_frontend_node(built, copy.deepcopy(saved_node))


async def test_editor_update_keeps_uploaded_files_on_file_component(storage_root: Path) -> None:
    user_id = str(uuid.uuid4())
    keys = [_upload(storage_root, user_id, "report.pdf"), _upload(storage_root, user_id, "notes.pdf")]
    code = Path(file_module.__file__).read_text(encoding="utf-8")
    saved, _ = build_custom_component_template(Component(_code=code), user_id=user_id)
    saved["template"]["path"]["value"] = ["report.pdf", "notes.pdf"]
    saved["template"]["path"]["file_path"] = keys

    updated = await _editor_update(saved, user_id)

    assert updated["template"]["path"]["value"] == ["report.pdf", "notes.pdf"]
    assert updated["template"]["path"]["file_path"] == keys


async def test_editor_update_clears_another_users_file_on_file_component(storage_root: Path) -> None:
    other_key = _upload(storage_root, str(uuid.uuid4()), "secret.pdf")
    code = Path(file_module.__file__).read_text(encoding="utf-8")
    user_id = str(uuid.uuid4())
    saved, _ = build_custom_component_template(Component(_code=code), user_id=user_id)
    saved["template"]["path"]["value"] = ["secret.pdf"]
    saved["template"]["path"]["file_path"] = [other_key]

    updated = await _editor_update(saved, user_id)

    assert updated["template"]["path"]["value"] == ""
    assert updated["template"]["path"]["file_path"] == ""
