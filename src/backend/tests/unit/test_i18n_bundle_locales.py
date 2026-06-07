"""Tests for per-bundle locale merging in i18n utilities.

Covers the Phase 2 capability that lets installed/third-party extension bundles
ship their own component translations, merged into the core i18n table with
core-wins precedence.
"""

import json

import pytest
from langflow.utils import i18n


@pytest.fixture(autouse=True)
def _reset_translations():
    """Keep the module-global translation cache from leaking across tests."""
    i18n._translations.clear()
    yield
    i18n._translations.clear()


def _write_locale(directory, lang: str, mapping: dict) -> None:
    (directory / f"{lang}.json").write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


class TestMergeBundleTranslations:
    def test_core_wins_and_bundle_adds_new_keys(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "locales"
        bundle_dir.mkdir()
        _write_locale(
            bundle_dir,
            "en",
            {
                "components.core.display_name.aaaa1111": "bundle override attempt",  # collides with core
                "components.bundlecomp.display_name.bbbb2222": "Bundle Comp",  # new key
            },
        )
        _write_locale(bundle_dir, "fr", {"components.bundlecomp.display_name.bbbb2222": "Composant Bundle"})
        monkeypatch.setattr(i18n, "_iter_bundle_locale_dirs", lambda: [bundle_dir])

        translations = {"en": {"components.core.display_name.aaaa1111": "Core Value"}}
        i18n._merge_bundle_translations(translations)

        # Core string is never overwritten by a bundle.
        assert translations["en"]["components.core.display_name.aaaa1111"] == "Core Value"
        # Bundle contributes a new key core did not define.
        assert translations["en"]["components.bundlecomp.display_name.bbbb2222"] == "Bundle Comp"
        # A locale absent from core is created from the bundle.
        assert translations["fr"]["components.bundlecomp.display_name.bbbb2222"] == "Composant Bundle"

    def test_malformed_bundle_locale_is_skipped(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "locales"
        bundle_dir.mkdir()
        (bundle_dir / "de.json").write_text("{ not valid json", encoding="utf-8")
        _write_locale(bundle_dir, "es", {"components.bundlecomp.display_name.cccc3333": "Componente"})
        monkeypatch.setattr(i18n, "_iter_bundle_locale_dirs", lambda: [bundle_dir])

        translations: dict[str, dict[str, str]] = {}
        # Must not raise on the malformed de.json; the valid es.json still merges.
        i18n._merge_bundle_translations(translations)

        assert "de" not in translations
        assert translations["es"]["components.bundlecomp.display_name.cccc3333"] == "Componente"


class TestReloadAndTranslate:
    def test_reload_picks_up_bundle_translation(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "locales"
        bundle_dir.mkdir()
        _write_locale(bundle_dir, "de", {"components.bundlecomp.display_name.bbbb2222": "Bündel-Komponente"})
        monkeypatch.setattr(i18n, "_iter_bundle_locale_dirs", lambda: [bundle_dir])

        i18n.reload_translations()

        # Bundle-contributed key resolves in its locale.
        assert i18n.translate("components.bundlecomp.display_name.bbbb2222", "de", "Bundle Comp") == "Bündel-Komponente"
        # Unknown key still falls back to the supplied English default.
        assert i18n.translate("components.unknown.display_name.0", "de", "Fallback") == "Fallback"


class TestDiscoveryIsDefensive:
    def test_iter_bundle_locale_dirs_returns_list_without_raising(self):
        # Real discovery over installed extensions must never raise; with no bundle
        # shipping a locales/ dir yet it simply returns an empty (or all-existing) list.
        result = i18n._iter_bundle_locale_dirs()
        assert isinstance(result, list)
        assert all(p.is_dir() for p in result)
