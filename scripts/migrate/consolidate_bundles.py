#!/usr/bin/env python3
"""Consolidate in-tree lfx providers into the manifest-less lfx-bundles metapackage.

For each named provider, this:

  1. moves ``src/lfx/src/lfx/components/<provider>/`` -> the metapackage at
     ``src/bundles/lfx-bundles/src/lfx_bundles/<provider>/`` (rewriting any
     absolute ``lfx.components.<provider>`` self-imports to ``lfx_bundles.<provider>``);
  2. leaves a fail-soft import shim at the old in-tree location so
     ``from lfx.components.<provider> import X`` keeps working when lfx-bundles
     is co-installed (and raises an actionable ImportError when it is not);
  3. merges the provider's third-party deps into an lfx-bundles per-provider
     extra (PEP 685-normalized key) and regenerates the ``all`` aggregate;
  4. appends the 4-entry migration block per Component class so saved flows
     referencing the old ``lfx.components.<provider>.<Class>`` path migrate to
     the stable ``ext:<provider>:<Class>@official`` id.

This is the inverse of ``scripts/migrate/port_bundle.py`` (which extracts a
provider to its own standalone distribution); here the destination is the
single manifest-less metapackage.  The provider->deps map is **human-curated**
-- the ``langflow-base`` extras are not 1:1 with provider folders -- so dep
parity is reviewed, never guessed.  Add a provider by adding it to
``PROVIDER_DEPS`` and re-running.

Stdlib-only.  Dry-run by default; pass ``--apply`` to mutate the tree.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_DIR = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components"
BUNDLES_PKG = REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "src" / "lfx_bundles"
BUNDLES_PYPROJECT = REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "pyproject.toml"
MIGRATION_TABLE = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

# Release this consolidation ships in -- stamped on every migration entry.
MIGRATION_RELEASE = "1.11.0"

# Shared spec for providers whose components go through langchain_community
# wrappers (the wrapper itself; whatever SDK the wrapper lazy-imports at
# runtime is listed per provider alongside it).
_LC_COMMUNITY = "langchain-community>=0.4.1,<1.0.0"

# Curated provider -> third-party runtime deps (everything beyond lfx itself,
# which the metapackage already declares).  Each list is the provider's deps as
# verified against langflow-base's per-provider extras or its direct
# dependencies / lfx core deps.  Empty means the provider's only runtime needs
# are already in lfx core (e.g. httpx, pydantic, pandas).  ``requests`` is NOT
# an lfx core dep (only transitive in today's env), so providers importing it
# declare it explicitly.
PROVIDER_DEPS: dict[str, list[str]] = {
    # --- tranche 1: search/tools ---
    "tavily": [],  # talks to the Tavily API via httpx (an lfx core dep)
    # "exa" graduated to the standalone lfx-exa bundle (src/bundles/exa) when
    # the component moved off the deprecated metaphor-python SDK onto exa-py.
    "wikipedia": ["wikipedia==1.4.0", _LC_COMMUNITY],
    "yahoosearch": ["yfinance==0.2.50"],
    "wolframalpha": ["wolframalpha==5.1.3", _LC_COMMUNITY],
    # --- tranche 2: vector stores ---
    "chroma": ["chromadb>=1.0.0,<2.0.0", "langchain-chroma~=0.2.6", _LC_COMMUNITY],
    "clickhouse": ["clickhouse-connect==0.7.19", _LC_COMMUNITY],
    "couchbase": ["couchbase>=4.2.1", _LC_COMMUNITY],
    "milvus": ["langchain-milvus~=0.3.2"],
    "mongodb": ["pymongo>=4.10.1", "langchain-mongodb>=0.11.0"],
    "pgvector": ["pgvector>=0.4.2", _LC_COMMUNITY],
    # Marker preserved from langflow-base: no py3.14 wheel yet; on 3.14 the
    # component degrades exactly as it does in today's published images.
    "pinecone": ["langchain-pinecone~=0.2.13; python_version < '3.14'"],
    "qdrant": ["qdrant-client>=1.12.0,<2.0.0", "langchain-qdrant>=1.0.0,<2.0.0"],
    "supabase": ["supabase>=2.6.0,<3.0.0", _LC_COMMUNITY],
    "upstash": ["upstash-vector==0.6.0", _LC_COMMUNITY],
    "weaviate": ["weaviate-client>=4.10.2,<5.0.0", "langchain-weaviate>=0.0.6"],
    # --- tranche 2: model providers ---
    "groq": ["langchain-groq~=1.1.1"],
    "mistral": ["langchain-mistralai~=1.1.1"],
    "ollama": ["langchain-ollama~=0.3.10"],
    "perplexity": ["langchain-perplexity>=1.0.0,<2.0.0"],
    "sambanova": ["langchain-sambanova~=1.0.0"],
    # --- tranche 2: tools / memory / data ---
    "apify": ["apify-client>=1.8.1", _LC_COMMUNITY],
    "assemblyai": ["assemblyai>=0.33.0,<1.0.0"],
    "confluence": ["atlassian-python-api==3.41.16", _LC_COMMUNITY],
    "firecrawl": ["firecrawl-py>=1.0.16,<2.0.0"],
    "git": ["GitPython>=3.1.50", _LC_COMMUNITY],
    "glean": [],  # httpx + pydantic only (lfx core)
    "icosacomputing": ["requests>=2.32.0"],
    "mem0": ["mem0ai>=2.0.2,<3.0.0"],
    "needle": ["needle-python>=0.4.0", _LC_COMMUNITY],
    "scrapegraph": ["scrapegraph-py>=1.12.0"],
    "serpapi": ["google-search-results>=2.4.1,<3.0.0", _LC_COMMUNITY],
    "unstructured": ["langchain-unstructured~=1.0.0"],
    "youtube": ["pytube==15.0.0", "youtube-transcript-api>=1.0.0,<2.0.0", "google-api-python-client~=2.161"],
    "zep": ["zep-python==2.0.2"],
    # --- tranche 3: openai-SDK family (post partner graduation) ---
    # All ride the langchain-openai wrapper; the openai SDK is declared only
    # where a component imports it directly (otherwise wrapper-transitive).
    "aiml": ["langchain-openai>=1.1.6", "openai>=1.68.2,<3.0.0"],
    "azure": ["langchain-openai>=1.1.6"],
    "cometapi": ["langchain-openai>=1.1.6", "requests>=2.32.0"],
    "deepseek": ["langchain-openai>=1.1.6", "openai>=1.68.2,<3.0.0", "requests>=2.32.0"],
    # NOTE: the component drives LiteLLM-served endpoints through the OpenAI
    # client; it does not import the `litellm` package (langflow-base's
    # litellm extra serves other consumers and stays put).
    "litellm": ["langchain-openai>=1.1.6", "openai>=1.68.2,<3.0.0"],
    "lmstudio": ["langchain-openai>=1.1.6", "openai>=1.68.2,<3.0.0", "langchain-nvidia-ai-endpoints~=1.0.0"],
    "novita": ["langchain-openai>=1.1.6", "requests>=2.32.0"],
    "openrouter": ["langchain-openai>=1.1.6"],
    "xai": ["langchain-openai>=1.1.6", "openai>=1.68.2,<3.0.0", "requests>=2.32.0"],
    # --- tranche 4: remaining single-SDK providers (post core-tail audit) ---
    "cleanlab": ["cleanlab-tlm>=1.1.2,<2.0.0"],
    "twelvelabs": ["twelvelabs>=0.4.7,<1.0.0"],
    "jigsawstack": ["jigsawstack==0.2.7"],
    # --- tranche 5: vector/datastores + langchain-community REST wrappers ---
    "baidu": ["qianfan==0.3.5", _LC_COMMUNITY],  # QianfanChatEndpoint (community wrapper) lazy-loads qianfan
    "redis": ["redis>=7.4.0,<8.0.0", _LC_COMMUNITY],
    "elastic": ["elasticsearch~=8.19", "langchain-elasticsearch~=1.0.0", "opensearch-py==2.8.0"],
    "bing": [_LC_COMMUNITY],  # BingSearchAPIWrapper (community, httpx-based)
    "cloudflare": [_LC_COMMUNITY],  # CloudflareWorkersAI (community)
    "maritalk": [_LC_COMMUNITY],  # ChatMaritalk (community)
    "searchapi": [_LC_COMMUNITY],  # SearchApiAPIWrapper (community)
    "vectara": [_LC_COMMUNITY],  # Vectara (community)
    # --- tranche 6: REST-wrapper providers (httpx/requests, no vendor SDK) ---
    "homeassistant": ["requests>=2.32.0"],  # REST via requests; no vendor SDK
    "olivya": [],  # httpx REST only (lfx core)
    "agentql": [],  # httpx REST only (lfx core)
    # --- tranche 7: google family + agent SDKs (markers preserved from base) ---
    # google-auth-oauthlib: imported directly by the google_oauth_token component
    # (from google_auth_oauthlib.flow import InstalledAppFlow). langchain-google-community
    # only pulls it behind its [gmail,drive,calendar] extras, so declare it explicitly.
    "google": [
        "langchain-google-genai~=4.1.2",
        "langchain-google-community~=3.0.2",
        "google-api-python-client~=2.161",
        "google-auth-oauthlib>=1.2.0,<2.0.0",
    ],
    "vertexai": ["langchain-google-vertexai>=3.2.0"],
    # ALTK depends on litellm, whose current Rust extension does not build on Python 3.14.
    "altk": [
        "agent-lifecycle-toolkit>=0.10.1,<1.0; "
        "(sys_platform != 'darwin' or platform_machine != 'x86_64') and python_version < '3.14'",
    ],
    "codeagents": [
        "smolagents>=1.8.0",
        "OpenDsStar==1.0.26; python_version >= '3.11' and python_version < '3.14' and (sys_platform != 'darwin' or platform_machine != 'x86_64')",  # noqa: E501
    ],
    # --- tranche 8: agent/model SDKs (needed the lfx dynamic-import test decoupling) ---
    "composio": ["composio==0.9.2", "composio-langchain==0.9.2"],
    "huggingface": [
        "langchain-huggingface~=1.2.0; sys_platform != 'darwin' or platform_machine != 'x86_64'",
        "huggingface-hub[inference]>=1.0.0,<2.0.0",
        _LC_COMMUNITY,
    ],
    "nvidia": [
        "langchain-nvidia-ai-endpoints~=1.0.0",
        "nv-ingest-client>=26.1.0,<26.3.0 ; python_version >= '3.12'",
        "gassist>=0.0.1; sys_platform == 'win32'",
    ],
    "cuga": [
        "cuga>=0.2.20,<0.3.0; sys_platform != 'darwin' and python_version < '3.14'",
        "cuga>=0.2.20,<0.3.0; sys_platform == 'darwin' and platform_machine == 'arm64' and python_version < '3.14'",
    ],
    # --- tranche 9: langwatch evaluator (pure httpx REST; the langwatch SDK extra
    # is for the tracing service, not this component) ---
    "langwatch": [],
    # --- tranche 10: uppercase source dirs -> lowercase bundle slug (FAISS->faiss,
    # Notion->notion via bundle_slug(); import paths keep historical casing) ---
    "FAISS": [
        "faiss-cpu==1.9.0.post1; python_version < '3.14'",
        "faiss-cpu>=1.13.2; python_version >= '3.14'",
        _LC_COMMUNITY,
    ],
    "Notion": ["requests>=2.32.0", "Markdown>=3.8.0"],
}

_OPTIONAL_DEPS_HEADER = (
    "# Per-provider extras + the generated ``all`` / ``all-no-torch`` aggregates.\n"
    "# Extra keys are PEP 685-normalized (lowercase, hyphen-separated). ``all``\n"
    "# and ``all-no-torch`` are GENERATED from the per-provider keys -- never\n"
    "# hand-edit them. ``all`` pulls every provider; ``all-no-torch`` is ``all``\n"
    "# minus the torch-pulling providers (see TORCH_EXTRAS), giving a torch-free\n"
    "# superset for slim/CPU images. Managed by scripts/migrate/consolidate_bundles.py."
)

# Providers whose SDKs pull torch (directly or transitively). Excluded from the
# generated ``all-no-torch`` aggregate so it resolves torch-free. Keep in sync with
# the per-provider extras above: cuga -> cuga, codeagents -> smolagents.
TORCH_EXTRAS = frozenset({"cuga", "codeagents"})


def normalize_extra(name: str) -> str:
    """PEP 685 extra-name normalization (lowercase, runs of -_. -> single -)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _is_component_classdef(node: ast.ClassDef) -> bool:
    """True for a class that looks like a Component subclass.

    Qualifies when its own name ends with ``Component`` or any base's name does
    -- catches ``ExaSearchToolkit(Component)`` and
    ``WolframAlphaAPIComponent(LCToolComponent)`` while excluding Enum / BaseModel
    helpers.
    """
    base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
    base_names += [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
    return node.name.endswith("Component") or any(b.endswith("Component") for b in base_names)


def discover_component_classes(provider_dir: Path) -> list[tuple[str, str]]:
    """Return ``(module_stem, class_name)`` for every Component class in the provider."""
    found: list[tuple[str, str]] = []
    for py in sorted(provider_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        found.extend(
            (py.stem, node.name)
            for node in tree.body
            if isinstance(node, ast.ClassDef) and _is_component_classdef(node)
        )
    return found


def _shim_source(provider: str, slug: str) -> str:
    return (
        "# lfx-bundles-shim\n"
        f'"""Compatibility shim: lfx.components.{provider} moved to lfx-bundles.\n'
        "\n"
        "This module re-points to the installed bundle distribution. It contains\n"
        "no component implementations and no third-party dependencies, and is\n"
        "removed once the deprecation window closes (M4).\n"
        '"""\n'
        "\n"
        "import importlib\n"
        "import sys\n"
        "\n"
        "try:\n"
        f'    sys.modules[__name__] = importlib.import_module("lfx_bundles.{slug}")\n'
        "except ModuleNotFoundError as exc:\n"
        '    if exc.name is not None and (exc.name == "lfx_bundles" or exc.name.startswith("lfx_bundles.")):\n'
        "        msg = (\n"
        f"            \"The '{provider}' components moved to the 'lfx-bundles' distribution. \"\n"
        '            "Install it with: pip install lfx-bundles."\n'
        "        )\n"
        '        raise ModuleNotFoundError(msg, name="lfx_bundles") from exc\n'
        "    raise\n"
    )


def _rewrite_self_imports(text: str, provider: str, slug: str) -> str:
    """Rewrite absolute ``lfx.components.<provider>`` self-refs to ``lfx_bundles.<slug>``."""
    return re.sub(rf"\blfx\.components\.{re.escape(provider)}\b", f"lfx_bundles.{slug}", text)


def bundle_slug(provider: str) -> str:
    """Bundle directory / ext-slug name for a provider.

    Bundle names must satisfy ``BUNDLE_NAME_RE`` (lowercase), so the in-tree
    source dir name is lowercased -- e.g. ``FAISS`` -> ``faiss``, ``Notion`` ->
    ``notion``. Already-lowercase providers are unchanged. The historical
    ``lfx.components.<provider>`` import paths (migration table) keep the
    original casing; only the bundle dir + ``ext:<slug>`` id are lowercased.
    """
    return provider.lower()


def move_provider(provider: str, *, apply: bool) -> list[tuple[str, str]]:
    """Move one provider into the metapackage and leave a shim. Returns its classes."""
    slug = bundle_slug(provider)
    src = COMPONENTS_DIR / provider
    dst = BUNDLES_PKG / slug
    if not src.is_dir():
        msg = f"provider directory not found: {src}"
        raise SystemExit(msg)
    if dst.exists():
        msg = f"destination already exists (already consolidated?): {dst}"
        raise SystemExit(msg)

    # move_provider relocates only top-level ``*.py`` modules (see the glob
    # below) but rmtree's the whole source tree.  A provider with a subpackage
    # would have its subdir silently destroyed -- never copied to the bundle and
    # never migration-mapped.  Refuse rather than half-move; port_bundle.py is
    # the tool for nested layouts.
    subdirs = sorted(p.name for p in src.iterdir() if p.is_dir() and p.name != "__pycache__")
    if subdirs:
        msg = (
            f"{provider}: source has subdirectory/ies {subdirs} that move_provider does not "
            "relocate (it copies only top-level *.py modules). Use port_bundle.py, which "
            "handles nested subpackages, instead."
        )
        raise SystemExit(msg)

    classes = discover_component_classes(src)
    py_files = sorted(src.glob("*.py"))
    print(f"  {provider}: {len(py_files)} file(s), {len(classes)} component class(es) -> {dst.relative_to(REPO_ROOT)}")
    for module_stem, class_name in classes:
        print(f"      {module_stem}.{class_name} -> ext:{slug}:{class_name}@official")

    if not apply:
        return classes

    dst.mkdir(parents=True)
    for py in py_files:
        content = _rewrite_self_imports(py.read_text(encoding="utf-8"), provider, slug)
        (dst / py.name).write_text(content, encoding="utf-8")
    # Remove the moved source, then replace the in-tree dir with a one-file shim.
    shutil.rmtree(src)
    src.mkdir()
    (src / "__init__.py").write_text(_shim_source(provider, slug), encoding="utf-8")
    return classes


def _render_optional_deps(extras: dict[str, list[str]]) -> str:
    keys = sorted(k for k in extras if k not in ("all", "all-no-torch"))
    lines = ["[project.optional-dependencies]", _OPTIONAL_DEPS_HEADER]
    for key in keys:
        deps = extras[key]
        if deps:
            rendered = ", ".join(f'"{d}"' for d in deps)
            lines.append(f"{key} = [{rendered}]")
        else:
            lines.append(f"{key} = []")
    lines.append("all = [")
    lines.extend(f'    "lfx-bundles[{key}]",' for key in keys)
    lines.append("]")
    lines.append("all-no-torch = [")
    lines.extend(f'    "lfx-bundles[{key}]",' for key in keys if key not in TORCH_EXTRAS)
    lines.append("]")
    return "\n".join(lines) + "\n"


def update_bundles_pyproject(new_extras: dict[str, list[str]], *, apply: bool) -> None:
    """Merge ``new_extras`` into lfx-bundles [project.optional-dependencies], regen ``all``."""
    import tomllib

    text = BUNDLES_PYPROJECT.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    extras = {k: list(v) for k, v in parsed.get("project", {}).get("optional-dependencies", {}).items()}
    extras.pop("all", None)
    extras.pop("all-no-torch", None)
    extras.update(new_extras)

    section = _render_optional_deps(extras)
    print(f"  lfx-bundles extras now: {sorted(extras)}")
    if not apply:
        return

    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "[project.optional-dependencies]")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    # Preserve one trailing blank line before the next section.
    new_lines = [*lines[:start], section, "\n", *lines[end:]]
    BUNDLES_PYPROJECT.write_text("".join(new_lines), encoding="utf-8")


def append_migration_entries(plan: dict[str, list[tuple[str, str]]], *, apply: bool) -> None:
    """Append the 4-entry migration block per Component class (bare-name-safe).

    ``ambiguous_bare_names`` is a list of ``{name, candidates, added_in}`` -- when
    a bare class name would map to more than one target, the bare entry is
    omitted (the loader then requires an explicit import path) and the clash is
    recorded there. The tranche's class names are globally unique, so this only
    guards future runs.
    """
    table = json.loads(MIGRATION_TABLE.read_text(encoding="utf-8"))
    entries = table["entries"]
    ambiguous_list = table.get("ambiguous_bare_names", [])
    already_ambiguous = {a["name"] for a in ambiguous_list}
    existing_bare: dict[str, str] = {e["bare_class_name"]: e["target"] for e in entries if "bare_class_name" in e}

    def _entry(key: str, value: str, target: str) -> dict:
        return {key: value, "target": target, "added_in": MIGRATION_RELEASE}

    new_entries: list[dict] = []
    new_ambiguous: list[dict] = []
    for provider, classes in plan.items():
        # ext id uses the lowercase bundle slug; import paths keep the historical
        # (possibly mixed-case) ``lfx.components.<provider>`` form for migration.
        slug = bundle_slug(provider)
        for module_stem, class_name in classes:
            target = f"ext:{slug}:{class_name}@official"
            prior = existing_bare.get(class_name)
            if class_name in already_ambiguous:
                print(f"      ! {class_name!r} already ambiguous; import-path entries only")
            elif prior is not None and prior != target:
                new_ambiguous.append({"name": class_name, "candidates": [prior, target], "added_in": MIGRATION_RELEASE})
                print(f"      ! ambiguous bare name {class_name!r} ({prior} vs {target}); import-path entries only")
            else:
                new_entries.append(_entry("bare_class_name", class_name, target))
                existing_bare[class_name] = target
            new_entries.append(_entry("import_path", f"lfx.components.{provider}.{module_stem}.{class_name}", target))
            new_entries.append(_entry("import_path", f"lfx.components.{provider}.{class_name}", target))
            new_entries.append(_entry("legacy_slot", f"ext:{slug}:{class_name}@official-pre-a", target))

    # Idempotency guard: a partially-failed earlier run (provider dir moved
    # but the table already written, or vice versa) must not duplicate rows on
    # re-run.  Entries are deduped on their full content; the table itself
    # stays append-only.
    existing_keys = {json.dumps(e, sort_keys=True) for e in entries}
    new_entries = [e for e in new_entries if json.dumps(e, sort_keys=True) not in existing_keys]

    print(f"  migration: +{len(new_entries)} entries (+{len(new_ambiguous)} ambiguous)")
    if not apply:
        return

    table["entries"] = entries + new_entries
    if new_ambiguous:
        table["ambiguous_bare_names"] = ambiguous_list + new_ambiguous
    MIGRATION_TABLE.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Mutate the tree (default: dry-run).")
    parser.add_argument("providers", nargs="*", help="Subset of PROVIDER_DEPS to process (default: all).")
    args = parser.parse_args()

    selected = args.providers or sorted(PROVIDER_DEPS)
    unknown = [p for p in selected if p not in PROVIDER_DEPS]
    if unknown:
        print(f"::error:: not in PROVIDER_DEPS: {unknown}", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] consolidating {len(selected)} provider(s) into lfx-bundles: {selected}")

    plan: dict[str, list[tuple[str, str]]] = {}
    new_extras: dict[str, list[str]] = {}
    print("== move providers + shims ==")
    for provider in selected:
        plan[provider] = move_provider(provider, apply=args.apply)
        new_extras[normalize_extra(provider)] = PROVIDER_DEPS[provider]

    print("== merge per-provider extras ==")
    update_bundles_pyproject(new_extras, apply=args.apply)

    print("== append migration entries ==")
    append_migration_entries(plan, apply=args.apply)

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write changes.")
    else:
        print("\nApplied. Next: regenerate the component index (LFX_DEV=1 build_component_index.py) and verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
