# Bundle Mass-Extraction Plan

Follow-up to [#13043](https://github.com/langflow-ai/langflow/pull/13043)
(`feat/extension-production-install`). Builds on the
[`PORTING.md`](./PORTING.md) recipe and the
[`scripts/migrate/port_bundle.py`](../../scripts/migrate/port_bundle.py)
automation that produced [`duckduckgo/`](./duckduckgo) and
[`arxiv/`](./arxiv).

The goal is to push every vendor-specific / third-party-SDK provider out
of `src/lfx/src/lfx/components/<provider>/` into a standalone
`src/bundles/<provider>/` distribution, leaving only the framework-level
"core" component categories behind.

## Reference: what the pilot ports needed

For each port, [`PORTING.md`](./PORTING.md) §1-§7 covers:

1. **Lay out the bundle dir** — `pyproject.toml`, `extension.json`,
   `__init__.py` re-exports, byte-for-byte file move.
2. **Remove the in-tree component** — `git rm -r` + three edits to
   [`src/lfx/src/lfx/components/__init__.py`](../lfx/src/lfx/components/__init__.py).
3. **Wire the workspace** — root [`pyproject.toml`](../../pyproject.toml)
   dependency + `[tool.uv.sources]` + `[tool.uv.workspace] members`;
   optional `src/backend/base/pyproject.toml` extras cleanup; `uv lock`.
4. **Migration table** — append the 4-entry block per class to
   [`migration_table.json`](../lfx/src/lfx/extension/migration/migration_table.json).
5. **Regenerate the component index** — `LFX_DEV=1 uv run python scripts/build_component_index.py`.
6. **Integration test** — `test_pilot_<bundle>_upgrade.py` modeled on
   [`test_pilot_duckduckgo_upgrade.py`](../lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py).
7. **Verify** — `lfx extension validate`, `uv sync`, `pytest`, `ruff`.
8. **Docker** — add to
   [`docker/build_and_push_backend.Dockerfile`](../../docker/build_and_push_backend.Dockerfile)
   and
   [`docker/build_and_push_base.Dockerfile`](../../docker/build_and_push_base.Dockerfile).

`scripts/migrate/port_bundle.py` (rewritten after the datastax port)
now drives every step end-to-end. The five-phase mode is what the
mass-extraction loop should use:

```bash
uv run python scripts/migrate/port_bundle.py \
    --bundle <name> --display-name "<Display Name>" \
    --migration-release 1.10.0 --apply \
    --rewrite-consumers --update-index \
    --update-dockerfiles --remove-base-extra
```

Phase coverage:

* **A — bundle layout.** Skeleton + lazy-import `__init__.py` (preserves
  the pre-extraction `_dynamic_imports`/`__getattr__` shape) + moves all
  `*.py` files + auto-detects and moves any shared base under
  `lfx.base.<bundle>` into `lfx_<bundle>.base/`, rewriting
  intra-bundle imports.
* **B — in-tree cleanup.** Deletes the in-tree provider dir, strips the
  three references from `lfx.components.__init__.py`, and migrates the
  matching `[tool.ruff.lint.per-file-ignores]` entries from the root
  pyproject into the bundle's pyproject (so the lint exceptions travel
  with the moved files).
* **C — workspace + consumers.** Patches the root pyproject (dep,
  `uv.sources`, members) and `rg`-greps the repo for external consumers
  of `lfx.components.<bundle>` and `lfx.base.<bundle>`, rewriting them
  in place. Backend test dirs at `src/backend/tests/unit/base/<bundle>/`
  are auto-moved into the bundle's `tests/` with patch paths rewritten.
* **D — artefacts.** With `--migration-release`, appends the
  four-entry-per-class migration block directly to
  `migration_table.json`; writes a parametrised
  `test_pilot_<bundle>_upgrade.py`; with `--update-index`, surgically
  removes the bundle's category from `component_index.json` and
  recomputes its `sha256`; with `--update-dockerfiles`, patches both
  non-uv-sync Dockerfiles.
* **E — optional cleanup.** With `--remove-base-extra`, removes the
  `<bundle>` extra from `langflow-base/pyproject.toml` and any
  `langflow-base[<bundle>]` reference from `complete` (the bundle's
  own pyproject now carries those deps).

Dry-run by default; pass `--apply` to mutate the tree. The composio
dry-run is a good stress test — 63 classes, 252 migration entries, a
shared base, three consumers, and a base extra all handled by the
script.

What's left to the human:

* Pinning runtime deps in the new bundle's `pyproject.toml` (the script
  only emits `lfx>=0.5.0,<0.6.0`; the rest are bundle-specific and the
  porter must check `langchain-*` constraints against `langflow-base`).
* Reviewing the consumer-rewrite diff (the substitutions are plain
  `str.replace`; rare false positives are possible in docstrings or
  fixture strings).
* Running the verification block (`uv lock`, `uv sync`, `pytest`,
  `ruff`, `lfx extension validate`) before committing.

## What stays in core

These directories under `src/lfx/src/lfx/components/` are **framework
primitives**, not third-party integrations. They stay in-tree because
either (a) they ship no vendor SDK in their `dependencies`, or (b) they
underpin the migration / flow-controls / I/O contract that bundles
themselves depend on:

| Category | Why core |
| --- | --- |
| `_importing.py` | Lazy-import helper used by every category `__init__.py` |
| `chains` | LangChain chain primitives |
| `custom_component` | The `Component` base contract |
| `data` / `data_source` | First-class data types (`Data`, `DataFrame`, `Message`) |
| `deactivated` | Legacy graveyard — kept for migration table coverage |
| `documentloaders` | Generic loader interface |
| `embeddings` | `text_embedder`, `similarity` — framework-level |
| `files_and_knowledge` / `files_ingestion` | Built-in file / KB ingestion |
| `flow_controls` | Conditional router, flow tool, loop — flow control |
| `helpers` | Generic helpers |
| `input_output` | Chat input/output, text input/output |
| `knowledge_bases` | First-class KB primitives (langflow uses these directly) |
| `langchain_utilities` | Generic LangChain glue |
| `link_extractors` | Generic |
| `llm_operations` | Batch run, guardrails, lambda filter |
| `logic` | Generic boolean/branching primitives |
| `models` / `models_and_agents` | First-class `Agent`, `LanguageModel`, `EmbeddingModel` (per request) |
| `output_parsers` | Generic |
| `processing` | `alter_metadata`, `converter`, dataframe ops — generic |
| `prototypes` | `python_function` — experimental |
| `textsplitters` | Generic |
| `toolkits` | Generic toolkit base |
| `tools` | Built-in tools (calculator, filesystem, python_repl) — kept core per request |
| `utilities` | Calculator, current_date, id_generator (per request) |
| `vectorstores` | `local_db` only — framework-level VS contract |

## What ports to bundles

Every directory below maps to one `lfx-<bundle>` distribution. The
ordering groups by category to make parallel batches easy, but each
bundle is independently portable. Names that already have an issue or PR
on the parent project are noted.

### LLM / model providers (24)

These all bring in a vendor SDK or vendor-specific LangChain integration.

- `aiml` → `lfx-aiml`
- `amazon` → `lfx-amazon` (Bedrock + S3 uploader)
- `anthropic` → `lfx-anthropic`
- `azure` → `lfx-azure`
- `cohere` → `lfx-cohere`
- `cometapi` → `lfx-cometapi`
- `deepseek` → `lfx-deepseek`
- `groq` → `lfx-groq`
- `huggingface` → `lfx-huggingface`
- `ibm` → `lfx-ibm` (watsonx)
- `litellm` → `lfx-litellm`
- `lmstudio` → `lfx-lmstudio`
- `maritalk` → `lfx-maritalk`
- `mistral` → `lfx-mistral`
- `notdiamond` → `lfx-notdiamond`
- `novita` → `lfx-novita`
- `nvidia` → `lfx-nvidia`
- `ollama` → `lfx-ollama`
- `openai` → `lfx-openai`
- `openrouter` → `lfx-openrouter`
- `perplexity` → `lfx-perplexity`
- `sambanova` → `lfx-sambanova`
- `vertexai` → `lfx-vertexai`
- `vllm` → `lfx-vllm`
- `xai` → `lfx-xai`

### Vector stores (17)

- `cassandra` → `lfx-cassandra`
- `chroma` → `lfx-chroma`
- `clickhouse` → `lfx-clickhouse`
- `couchbase` → `lfx-couchbase`
- `elastic` → `lfx-elastic`
- `FAISS` → `lfx-faiss`
- `milvus` → `lfx-milvus`
- `mongodb` → `lfx-mongodb`
- `pgvector` → `lfx-pgvector`
- `pinecone` → `lfx-pinecone`
- `qdrant` → `lfx-qdrant`
- `redis` → `lfx-redis`
- `supabase` → `lfx-supabase`
- `upstash` → `lfx-upstash`
- `vectara` → `lfx-vectara`
- `weaviate` → `lfx-weaviate`
- `zep` → `lfx-zep`

### Search / web tools (15)

- `arxiv` ✅ already extracted ([`bundles/arxiv`](./arxiv))
- `duckduckgo` ✅ already extracted ([`bundles/duckduckgo`](./duckduckgo))
- `baidu` → `lfx-baidu`
- `bing` → `lfx-bing`
- `exa` → `lfx-exa`
- `firecrawl` → `lfx-firecrawl`
- `glean` → `lfx-glean`
- `google` → `lfx-google` (Drive, Gmail, GenAI, BQ, OAuth, Search/Serper) — biggest single bundle
- `jigsawstack` → `lfx-jigsawstack`
- `needle` → `lfx-needle`
- `scrapegraph` → `lfx-scrapegraph`
- `searchapi` → `lfx-searchapi`
- `serpapi` → `lfx-serpapi`
- `tavily` → `lfx-tavily`
- `wikipedia` → `lfx-wikipedia`
- `wolframalpha` → `lfx-wolframalpha`
- `yahoosearch` → `lfx-yahoosearch`
- `youtube` → `lfx-youtube`

### Data / SaaS integrations (16)

- `Notion` → `lfx-notion`
- `agentql` → `lfx-agentql`
- `apify` → `lfx-apify`
- `assemblyai` → `lfx-assemblyai`
- `cleanlab` → `lfx-cleanlab`
- `cloudflare` → `lfx-cloudflare`
- `composio` → `lfx-composio`
- `confluence` → `lfx-confluence`
- `datastax` → `lfx-datastax` (AstraDB + Graph RAG + HCD)
- `docling` → `lfx-docling`
- `git` → `lfx-git`
- `homeassistant` → `lfx-homeassistant`
- `langwatch` → `lfx-langwatch`
- `mem0` → `lfx-mem0`
- `twelvelabs` → `lfx-twelvelabs`
- `unstructured` → `lfx-unstructured`

### Agent / orchestration frameworks (7)

These ship a third-party framework SDK (smolagents, CrewAI, AgentICS, etc.).

- `agentics` → `lfx-agentics`
- `altk` → `lfx-altk`
- `codeagents` → `lfx-codeagents`
- `crewai` → `lfx-crewai`
- `cuga` → `lfx-cuga`
- `icosacomputing` → `lfx-icosacomputing`
- `olivya` → `lfx-olivya`
- `vlmrun` → `lfx-vlmrun`

## Summary

| Bucket | Count |
| --- | --- |
| Stay in core | 26 categories |
| Already extracted | 2 bundles (arxiv, duckduckgo) |
| To extract | ~80 bundles across 4 families |

## Open questions / sequencing

1. **Big bundles first or last?** `google`, `datastax`, `openai`, `anthropic`,
   `amazon` are the highest-fan-in. Doing them first surfaces wheel /
   migration-table / Docker edge cases early; doing them last leans on
   patterns set by the smaller ports.
2. **Class-name collisions.** `scripts/migrate/check_bare_names.py` will
   reject any `bare_class_name` migration entry that names a class
   appearing in more than one bundle folder. The author's-guide already
   names `MergeDataComponent`, `SplitTextComponent`, `SubFlowComponent` as
   the known-ambiguous set — but those live in core categories
   (`processing`, `data`, `flow_controls`), so the bundle migration
   entries can use them as `bare_class_name` candidates if and only if
   the class is unique across the bundle set. Each port needs a quick
   `check_bare_names.py --dry-run` pass before commit.
3. **`langflow-base[<provider>]` extras.** Many of these providers still
   have a `langflow-base[provider]` extra in
   [`src/backend/base/pyproject.toml`](../../src/backend/base/pyproject.toml).
   `PORTING.md` §3b removes the extra and the `complete` reference; that
   needs auditing per port.
4. **Docker.** Both non-uv-sync Dockerfiles need the bundle appended;
   long-running images may want to lift this into a generated list.
