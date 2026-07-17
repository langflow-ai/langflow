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
**optional extras** (PEP 685-normalized keys, e.g. `lfx-bundles[google]`); the
generated `all` extra pulls every provider's deps for users who explicitly
install `lfx[bundles]` or `lfx-bundles[all]`.

## Adding a provider

Providers are moved here by `scripts/migrate/consolidate_bundles.py`, which also
maintains the per-provider extras and the generated `all` aggregate. **Do not**
hand-edit the extras block in `pyproject.toml`. Provider folder names must be
lowercase snake_case (`a-z`, `0-9`, `_`, 2–64 chars).

Starter projects that require a provider belong in that provider's
`starter_projects/` directory. Langflow discovers them only after the
manifest-less provider loads, then applies the normal component-availability
filter before seeding them.
