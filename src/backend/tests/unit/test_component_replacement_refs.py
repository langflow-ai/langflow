"""Legacy components' ``replacement`` refs must resolve in the ``/api/v1/all`` payload.

The canvas Legacy banner looks up each ``<category>.<name>`` ref in the payload
(``src/frontend/src/CustomNodes/utils/resolve-palette-key.ts``) and falls back
to "No direct replacement." when nothing matches. That fallback is what users
saw after categories were renamed (``data`` -> ``files_and_knowledge``,
``logic`` -> ``flow_controls``, ...). The refs looked fine in source but no
longer matched anything in the payload.
"""

from pathlib import Path

from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.deps import get_settings_service

# Categories served only by opt-in bundles. A ref into one of these may dangle
# when the bundle is not installed, because "No direct replacement." is correct
# then. Every other ref must resolve.
OPT_IN_BUNDLE_CATEGORIES = frozenset(
    {
        "composio",
        "searchapi",
        "serpapi",
        "serply",
        "wikipedia",
        "yahoosearch",
    }
)

OFFICIAL_SLOT_SUFFIX = "@official"

BUNDLES_DIR = Path(__file__).resolve().parents[4] / "src" / "bundles"


def _prefer_official(keys: list[str]) -> str | None:
    return next((key for key in keys if key.endswith(OFFICIAL_SLOT_SUFFIX)), keys[0] if keys else None)


def resolve_replacement_ref(all_types: dict, ref: str) -> str | None:
    """Return the palette key a ``<category>.<name>`` ref resolves to, mirroring the frontend.

    Within ``all_types[category]`` try, in order: the bare key (built-in
    components), ``ext:<category>:<name>@<slot>`` (extension-bundle components
    keyed by class name), then an entry whose ``name`` field matches.
    """
    category, _, name = ref.partition(".")
    components = all_types.get(category)
    if not components or not name:
        return None
    if name in components:
        return name

    keys = list(components)
    by_class_name = _prefer_official([key for key in keys if key.startswith(f"ext:{category}:{name}@")])
    if by_class_name:
        return by_class_name

    return _prefer_official([key for key in keys if (components[key] or {}).get("name") == name])


def _collect_replacement_refs(all_types: dict) -> list[tuple[str, str, str]]:
    return [
        (category, key, ref)
        for category, components in all_types.items()
        for key, template in components.items()
        for ref in (template or {}).get("replacement") or []
    ]


def _is_uninstalled_opt_in(all_types: dict, ref: str) -> bool:
    category = ref.partition(".")[0]
    return category in OPT_IN_BUNDLE_CATEGORIES and category not in all_types


def test_resolver_matches_bare_ext_and_name_keys():
    all_types = {
        "processing": {"Operations": {"name": "Operations"}},
        "google": {
            "ext:google:GmailSendComponent@extra": {},
            "ext:google:GmailSendComponent@official": {},
        },
        "datastax": {"ext:datastax:AstraDBVectorStoreComponent@official": {"name": "AstraDB"}},
    }

    assert resolve_replacement_ref(all_types, "processing.Operations") == "Operations"
    assert resolve_replacement_ref(all_types, "google.GmailSendComponent") == "ext:google:GmailSendComponent@official"
    assert resolve_replacement_ref(all_types, "datastax.AstraDB") == "ext:datastax:AstraDBVectorStoreComponent@official"
    assert resolve_replacement_ref(all_types, "helpers.Memory") is None
    assert resolve_replacement_ref(all_types, "processing.Missing") is None


def test_opt_in_categories_are_served_by_bundles():
    # Keeps the skip list honest: a renamed core category (``helpers``,
    # ``logic``, ...) must never be excused. ``lfx.components`` still carries
    # import shims under those names, so check the bundle sources instead.
    not_bundles = sorted(
        category
        for category in OPT_IN_BUNDLE_CATEGORIES
        if not (BUNDLES_DIR / "lfx-bundles" / "src" / "lfx_bundles" / category).is_dir()
        and not (BUNDLES_DIR / category).is_dir()
    )
    assert not not_bundles, f"{not_bundles} are not served by a bundle under src/bundles, so their refs must resolve"


async def test_every_core_replacement_ref_resolves():
    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
    refs = _collect_replacement_refs(all_types)
    assert refs, "No legacy component in the payload declares a replacement; the check would pass vacuously"

    unresolved = [
        f"{category}/{key} -> {ref}"
        for category, key, ref in refs
        if resolve_replacement_ref(all_types, ref) is None and not _is_uninstalled_opt_in(all_types, ref)
    ]

    assert not unresolved, (
        "These replacement refs resolve to no palette entry, so the Legacy banner shows "
        "'No direct replacement.'. Point each at the component's current category and palette key "
        "(or its `name`), or add the category to OPT_IN_BUNDLE_CATEGORIES if it belongs to an "
        "opt-in bundle:\n" + "\n".join(sorted(unresolved))
    )
