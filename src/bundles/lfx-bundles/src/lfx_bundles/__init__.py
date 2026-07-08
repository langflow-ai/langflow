"""lfx-bundles: the manifest-less metapackage of Langflow's long-tail providers.

This package is a bare namespace marker.  Each immediate subdirectory is one
provider bundle, discovered at runtime by lfx's ``lfx.bundles`` entry-point
folder-walk (``lfx.extension.loader._bundles_root``) and registered at the
``@official`` slot under its directory name.  There are intentionally no
re-exports here and no ``extension.json`` -- providers are added as folders,
the langchain-community way.

Provider folders are lowercase snake_case (``BUNDLE_NAME_RE``); a component's
identity is its bundle name (``ext:<provider>:<Class>@official``), stable
whether the provider ships here or in a graduated ``lfx-<provider>`` package.

Providers are added by ``scripts/migrate/consolidate_bundles.py``, never by
hand.
"""
