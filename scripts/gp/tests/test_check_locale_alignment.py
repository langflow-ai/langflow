"""Tests for check_locale_alignment.py."""

import json

import check_locale_alignment as align_mod


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class TestCheckAlignment:
    def test_fully_aligned_returns_zero(self, tmp_path):
        en = {"components.a.display_name.1234abcd": "A", "components.b.display_name.5678efgh": "B"}
        _write(tmp_path / "en.json", en)
        _write(tmp_path / "de.json", en)
        assert align_mod.check_alignment(tmp_path, max_orphans=200) == 0

    def test_orphans_over_budget_fails(self, tmp_path):
        en = {"k1": "v"}
        de = {"k1": "v", **{f"orphan{i}": "x" for i in range(10)}}
        _write(tmp_path / "en.json", en)
        _write(tmp_path / "de.json", de)
        # 10 orphans > budget of 5 -> 1 language over budget
        assert align_mod.check_alignment(tmp_path, max_orphans=5) == 1

    def test_orphans_within_budget_passes(self, tmp_path):
        en = {"k1": "v"}
        de = {"k1": "v", "orphan1": "x", "orphan2": "y"}
        _write(tmp_path / "en.json", en)
        _write(tmp_path / "de.json", de)
        # 2 orphans <= budget of 5
        assert align_mod.check_alignment(tmp_path, max_orphans=5) == 0

    def test_missing_keys_never_fail(self, tmp_path):
        # en has many keys de lacks (untranslated -> English fallback); zero orphans.
        en = {f"k{i}": "v" for i in range(100)}
        de = {"k0": "v"}
        _write(tmp_path / "en.json", en)
        _write(tmp_path / "de.json", de)
        assert align_mod.check_alignment(tmp_path, max_orphans=0) == 0

    def test_missing_en_returns_failure(self, tmp_path):
        # No en.json source of truth present.
        assert align_mod.check_alignment(tmp_path, max_orphans=200) == 1

    def test_en_only_dir_is_aligned(self, tmp_path):
        _write(tmp_path / "en.json", {"k": "v"})
        assert align_mod.check_alignment(tmp_path, max_orphans=200) == 0

    def test_counts_each_language_over_budget(self, tmp_path):
        en = {"k1": "v"}
        over = {"k1": "v", **{f"orphan{i}": "x" for i in range(10)}}
        _write(tmp_path / "en.json", en)
        _write(tmp_path / "de.json", over)
        _write(tmp_path / "fr.json", over)
        _write(tmp_path / "es.json", {"k1": "v"})  # aligned
        assert align_mod.check_alignment(tmp_path, max_orphans=5) == 2
