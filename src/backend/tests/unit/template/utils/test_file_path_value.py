from pathlib import Path

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
