"""CI gate: keep ``_LangflowComponentsAliasFinder`` head renames in sync with the migration table.

The compat bridge in ``langflow.__init__`` carries two static tables:

* ``_HEAD_RENAMES`` — first-segment renames applied before bundle lookup
  (e.g. ``FAISS`` -> ``faiss`` for the case-sensitive schema rename, or
  ``knowledge_bases`` -> ``files_and_knowledge`` for the in-tree rename).
* ``_GOOGLE_MODULE_TO_BUNDLE`` — file-stem routing for the 4-way ``google``
  split (one bundle per audience).

Both tables are maintained by hand.  The migration table at
``lfx/extension/migration/migration_table.json`` is the ground truth for
how legacy ``lfx.components.<head>.<class>`` paths map to extracted
bundles.  This suite cross-references the two so a new bundle rename
that lands in the migration table without a corresponding bridge update
fails CI rather than silently breaking ``from langflow.components.X``
imports in saved flows.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from langflow import _LangflowComponentsAliasFinder

# Heads that don't correspond to extracted bundles -- the bridge maps them
# to renamed in-tree directories, so they MUST live in ``_HEAD_RENAMES``
# but won't appear in the migration table (which only records bundle
# extractions).
_IN_TREE_RENAMES: set[tuple[str, str]] = {
    ("knowledge_bases", "files_and_knowledge"),
}

# The ``google`` head is special: it's split into 4 audience bundles via
# ``_GOOGLE_MODULE_TO_BUNDLE`` rather than being a 1:1 rename.  The
# migration-table-derived rename test below excludes it.
_SPLIT_HEADS: set[str] = {"google"}


def _migration_table_path() -> Path:
    """Locate ``migration_table.json`` relative to this file."""
    repo_root = Path(__file__).resolve()
    for parent in repo_root.parents:
        candidate = parent / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
        if candidate.exists():
            return candidate
    msg = "Could not locate migration_table.json"
    raise FileNotFoundError(msg)


@pytest.fixture(scope="module")
def migration_entries() -> list[dict]:
    with _migration_table_path().open() as f:
        return json.load(f)["entries"]


@pytest.fixture(scope="module")
def head_to_bundles(migration_entries: list[dict]) -> dict[str, set[str]]:
    """Map every ``lfx.components.<head>`` first segment to the bundle(s) it lands in."""
    mapping: dict[str, set[str]] = defaultdict(set)
    for entry in migration_entries:
        import_path = entry.get("import_path", "")
        target = entry.get("target", "")
        if not import_path.startswith("lfx.components.") or not target.startswith("ext:"):
            continue
        parts = import_path.split(".")
        if len(parts) < 3:
            continue
        head = parts[2]
        try:
            bundle = target.split(":", 2)[1]
        except IndexError:
            continue
        if bundle:
            mapping[head].add(bundle)
    return dict(mapping)


class TestHeadRenamesCoverage:
    """``_HEAD_RENAMES`` must cover every head whose bundle name differs."""

    def test_every_rename_in_migration_table_is_in_bridge(self, head_to_bundles):
        """Every 1:1 head->bundle rename in the migration table must be in ``_HEAD_RENAMES``.

        Excludes the 4-way google split, which is routed via a separate
        ``_GOOGLE_MODULE_TO_BUNDLE`` table.  Without the rename in
        ``_HEAD_RENAMES`` the bridge fails to find the bundle.
        """
        missing: list[tuple[str, str]] = []
        for head, bundles in head_to_bundles.items():
            if head in _SPLIT_HEADS:
                continue
            # Only 1:1 head->bundle renames are expected here.  Multi-bundle
            # heads that aren't the google split are an error in the
            # migration table itself.
            assert len(bundles) == 1, (
                f"Head {head!r} maps to multiple bundles {sorted(bundles)!r} but is not in "
                f"_SPLIT_HEADS; either add it to the 4-way split machinery or fix the "
                f"migration table."
            )
            (bundle,) = bundles
            if head == bundle:
                continue  # No rename needed.
            if _LangflowComponentsAliasFinder._HEAD_RENAMES.get(head) != bundle:
                missing.append((head, bundle))
        assert not missing, (
            f"_HEAD_RENAMES is missing entries that the migration table requires: "
            f"{missing!r}.  Add these to ``_LangflowComponentsAliasFinder._HEAD_RENAMES`` "
            f"in src/backend/base/langflow/__init__.py."
        )

    def test_in_tree_renames_present(self):
        """In-tree renames must still be in ``_HEAD_RENAMES``.

        They don't appear in the migration table (which only records
        bundle extractions), but locking them in keeps a future cleanup
        from accidentally dropping ``knowledge_bases``.
        """
        for head, bundle in _IN_TREE_RENAMES:
            assert _LangflowComponentsAliasFinder._HEAD_RENAMES.get(head) == bundle, (
                f"In-tree rename {head!r} -> {bundle!r} missing from _HEAD_RENAMES"
            )

    def test_no_orphan_head_renames(self, head_to_bundles):
        """Every ``_HEAD_RENAMES`` entry must match a migration entry or be in-tree.

        A stale entry here means the bundle was renamed back or removed
        without updating the bridge.
        """
        in_tree_heads = {h for h, _ in _IN_TREE_RENAMES}
        orphans: list[tuple[str, str]] = []
        for head, target in _LangflowComponentsAliasFinder._HEAD_RENAMES.items():
            if head in in_tree_heads:
                continue
            bundles = head_to_bundles.get(head)
            if not bundles or target not in bundles:
                orphans.append((head, target))
        assert not orphans, (
            f"_HEAD_RENAMES contains entries with no corresponding migration table "
            f"entry: {orphans!r}.  Either restore the bundle or remove the stale "
            f"_HEAD_RENAMES entry."
        )


class TestGoogleSplitCoverage:
    """``_GOOGLE_MODULE_TO_BUNDLE`` must route every google file stem to a real bundle."""

    def test_every_google_file_stem_covered(self, migration_entries):
        """Every ``lfx.components.google.<stem>`` must be in ``_GOOGLE_MODULE_TO_BUNDLE``.

        Otherwise the bridge falls through to a nonexistent path when
        a saved flow imports the legacy module.
        """
        expected: dict[str, str] = {}
        for entry in migration_entries:
            import_path = entry.get("import_path", "")
            target = entry.get("target", "")
            if not import_path.startswith("lfx.components.google."):
                continue
            if not target.startswith("ext:"):
                continue
            parts = import_path.split(".")
            if len(parts) < 4:
                continue
            stem = parts[3]
            # Filter to file-stem entries (snake_case) -- class-name entries
            # (PascalCase) are bare-name lookups, not file routing.
            if stem != stem.lower():
                continue
            try:
                bundle = target.split(":", 2)[1]
            except IndexError:
                continue
            expected[stem] = bundle

        actual = _LangflowComponentsAliasFinder._GOOGLE_MODULE_TO_BUNDLE
        missing = {stem: bundle for stem, bundle in expected.items() if actual.get(stem) != bundle}
        assert not missing, (
            f"_GOOGLE_MODULE_TO_BUNDLE is missing or has incorrect mappings for: "
            f"{missing!r}.  Update the table in src/backend/base/langflow/__init__.py."
        )

    def test_no_orphan_google_stems(self, migration_entries):
        """Every ``_GOOGLE_MODULE_TO_BUNDLE`` entry must match a migration entry.

        Stale entries mean a file was renamed or removed without
        updating the bridge.
        """
        valid_stems: set[str] = set()
        for entry in migration_entries:
            import_path = entry.get("import_path", "")
            if not import_path.startswith("lfx.components.google."):
                continue
            parts = import_path.split(".")
            if len(parts) < 4:
                continue
            stem = parts[3]
            if stem == stem.lower():
                valid_stems.add(stem)

        orphans = sorted(set(_LangflowComponentsAliasFinder._GOOGLE_MODULE_TO_BUNDLE) - valid_stems)
        assert not orphans, (
            f"_GOOGLE_MODULE_TO_BUNDLE has stale entries not in the migration table: "
            f"{orphans!r}.  Remove these or restore the migration entry."
        )
