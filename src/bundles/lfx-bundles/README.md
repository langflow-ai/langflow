# lfx-bundles

The long tail of Langflow's provider components as a **single manifest-less
metapackage**, modeled on `langchain-community`. This is the destination for
every vendor/third-party provider that does not warrant its own standalone
distribution; the curated partner providers (OpenAI, Anthropic, AWS,
DataStax, Cohere) ship as separate `lfx-<provider>` packages instead.

## How it works

`lfx-bundles` declares the `lfx.bundles` entry point:

```toml
[project.entry-points."lfx.bundles"]
lfx_bundles = "lfx_bundles"
```

At startup, lfx resolves this package and **folder-walks its immediate
subdirectories**. Each subdirectory is one bundle, registered at the
`@official` slot under its directory name — no `extension.json`, no per-provider
manifest. Adding a provider is just adding a folder.

```
src/lfx_bundles/
├── __init__.py        # bare namespace marker
├── <provider>/        # one bundle, e.g. tavily/, pinecone/, ...
│   ├── *.py           # Component subclasses
│   └── starter_projects/
│       └── *.json     # Optional templates owned by this provider
└── ...
```

A component's identity is its **bundle name** (`ext:<provider>:<Class>@official`),
which is stable whether the provider ships here or graduates to a standalone
`lfx-<provider>` package. Because a manifest-shipping package always shadows the
manifest-less metapackage, a provider can graduate with **no lockstep release**.

## Installing

```bash
pip install langflow                   # server + default partner bundles
pip install lfx                        # engine only, no bundles
pip install "lfx[bundles]"             # engine + this metapackage (deployment footnote)
pip install "lfx-bundles[<provider>]"  # one provider's code + that provider's SDK deps
```

`lfx-bundles` itself depends only on `lfx`. Each provider's third-party SDKs are
**optional extras** (PEP 685-normalized keys, e.g. `lfx-bundles[qdrant]`); the
generated `all` extra pulls every provider's deps for users who explicitly
install `lfx[bundles]` or `lfx-bundles[all]`.

Deprecated extras for graduated providers may remain as compatibility aliases.
For example, `lfx-bundles[google]`, `lfx-bundles[azure]`, and
`lfx-bundles[ollama]` now install their standalone bundles, but are excluded
from the generated aggregate extras because Langflow installs them directly.

### OpenDsStar: manual installation only

Starting with `lfx-bundles` 1.1.24, OpenDsStar is no longer a managed dependency,
including in `codeagents` and `all`. The `lfx[opendsstar]` and
`langflow-base[opendsstar]` extras have also been removed. The component code and
saved-flow identifiers remain available for OpenDsStar Agent, CodeAct Smolagents,
and File Description Generator, but running them requires a separate installation.

To keep using these components, install into the same Python environment as
Langflow. The last managed dependency combination was:

```bash
uv pip install 'OpenDsStar==1.0.26' 'langchain-litellm==0.5.1'
```

That combination was limited to Python 3.11–3.13 and excluded Intel macOS. The
`langchain-litellm` pin preserves compatibility with Langflow's cryptography floor.
An exact `uv sync` can remove manually installed packages; repeat the manual
installation after syncing, or manage it in your own environment requirements.

Manual installation reintroduces DiskCache and its unpatched
[CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v). This opt-in is
outside Langflow's managed dependency set and requires your own security assessment.

## Adding a provider

Providers are moved here by `scripts/migrate/consolidate_bundles.py`, which also
maintains the per-provider extras and the generated `all` aggregate. **Do not**
hand-edit the extras block in `pyproject.toml`. Provider folder names must be
lowercase snake_case (`a-z`, `0-9`, `_`, 2–64 chars).

Starter projects that require a provider belong in that provider's
`starter_projects/` directory. Langflow discovers them only after the
manifest-less provider loads, then applies the normal component-availability
filter before seeding them.
