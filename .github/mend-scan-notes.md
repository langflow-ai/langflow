# Mend scan triage notes

Findings that Mend reports repeatedly but which **cannot be remediated by a version
bump**, with the evidence behind each decision. Re-check the "revisit when" column
before re-opening any of these — do not raise a floor without first confirming a
patched version actually exists.

## How to verify a finding before acting on it

Mend severities and "fixed version" hints are not authoritative. Query the real
advisory data first:

```bash
# GitHub advisory DB — highest first-patched version
gh api "/advisories?ecosystem=pip&affects=<pkg>&per_page=100" \
  --jq '[.[].vulnerabilities[]?|select(.package.name=="<pkg>")|.first_patched_version]
        |map(select(.!=null))|unique|sort'

# OSV (aggregates PyPA + CVE + GHSA; catches PYSEC ids GHSA misses)
curl -s -X POST https://api.osv.dev/v1/query \
  -d '{"package":{"name":"<pkg>","ecosystem":"PyPI"}}' | jq '.vulns[]?|{id,summary}'

# NVD, by exact version
curl -s "https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName=cpe:2.3:a:<vendor>:<pkg>:<version>:*:*:*:*:*:*:*" \
  | jq '.totalResults'

# Is there even a newer release to move to?
curl -s "https://pypi.org/pypi/<pkg>/json" | jq -r '.info.version, .urls[0].upload_time'
```

A finding is only actionable if a released version exists that is **above every
`first_patched_version`**. An advisory whose range ends in `last_affected: <latest
release>` with `first_patched_version: null` means *no fix has shipped*.

## Scan surface

`.github/workflows/mend.yml` exports dependencies with:

```
uv export --all-packages --all-extras --all-groups
```

This is the **maximal** closure — every opt-in extra and every dev/test group of
every workspace package, not what any user actually installs. A package appearing
in the scan does not imply it ships by default. Check the declaring extra and
whether it is reachable from `all` / `complete` / the root `langflow` package
before assessing exposure.

---

## Waived findings

### `transformers` — false positive

| | |
|---|---|
| **Mend** | High: 1, against 5.8.1 |
| **Reality** | Highest `first_patched_version` across **all** published advisories is **5.5.0** (GHSA-fgcw-684q-jj6r). OSV/PYSEC agrees: highest `fixed` is 5.3.0, highest `last_affected` is 5.2.0. NVD CPE query for `transformers:5.8.1` returns **0 results**. |
| **Resolved** | 5.8.1 — above every patched version |
| **Action** | None available. The floor is already `>=5.6.0,<6.0.0`. |
| **Revisit when** | A transformers advisory publishes with `first_patched_version > 5.8.1`. |

Do **not** raise the floor past 5.9.0 as a speculative fix: `docling-ibm-models>=3.13.3`
declares `transformers<5.9.0; sys_platform == "darwin"`, so a higher floor makes it
unsatisfiable on macOS and uv silently forks the resolution, backtracking the whole
docling stack (docling 2.115→2.99, docling-parse 7.8.1→6.2.0, docling-core 2.88→2.78)
on darwin only. This was already hit once; see the comment in
`src/backend/base/pyproject.toml`.

### `accelerate` — false positive

| | |
|---|---|
| **Mend** | High: 1, against 1.14.0 |
| **Reality** | **Zero** advisories in GHSA, OSV, and NVD. |
| **Resolved** | 1.14.0 — the latest release on PyPI |
| **Reachability** | Opt-in only: the `docling` extra, via `docling-slim` and `docling-ibm-models`. |
| **Action** | None. There is no vulnerability to remediate and no newer version to move to. |
| **Revisit when** | Any advisory is published for `accelerate` at all. |

### `chromadb` — unpatched upstream, not reachable

| | |
|---|---|
| **Mend** | Critical: 5, against 1.5.9 |
| **Reality** | CVE-2026-45829 / GHSA-f4j7-r4q5-qw2c, CWE-94, reported CVSS v4 9.3. Affected range is `>= 1.0.0, last_affected: 1.5.9`, `first_patched_version: null`. |
| **Fix status** | **None released.** 1.5.9 is the newest release on PyPI (uploaded 2026-05-05); the advisory published 2026-05-18. The fix is merged upstream as chroma-core/chroma#7237 but has not shipped. |
| **Action** | Nothing to bump to. |
| **Revisit when** | chromadb publishes a release newer than 1.5.9 — bump immediately. |

**Why this is not reachable from Langflow.** The vulnerability is a race between
ChromaDB's embedding-model-reference parsing and its authentication check, exposed
through the **Python FastAPI server's** `/api/v2/tenants/{tenant}/databases/{db}/collections`
endpoint. Langflow never runs that server. It uses chromadb exclusively as a client:
`PersistentClient` (embedded/local), `CloudClient` (Chroma Cloud), and `HttpClient`
(connecting to a Chroma server the user operates). The vulnerable endpoint is never
bound by any Langflow process.

**Why it cannot simply be dropped.** `langchain-chroma` is a default dependency of
`langflow-base`, and chromadb backs the Knowledge Base feature
(`lfx/base/knowledge_bases/backends/chroma.py`,
`lfx/components/files_and_knowledge/knowledge.py`,
`lfx/components/files_and_knowledge/memory_retrieval.py`). Removing it breaks a core
feature; this is not an optional integration.

### `diskcache` — no fix exists, opt-in only

| | |
|---|---|
| **Mend** | Critical: 1, against 5.6.3 |
| **Reality** | GHSA-w8v5-vhqr-4h9v / PYSEC-2026-2447. GHSA rates this **medium**, not critical. Range is `last_affected: 5.6.3`, `first_patched_version: null`. |
| **Fix status** | **None, and none expected.** 5.6.3 is the final release ever published (2023-08-31); the project is unmaintained. |
| **Action** | Nothing to bump to. |
| **Revisit when** | diskcache publishes any release after 5.6.3, or the `opendsstar` extra is removed. |

**Exploitation precondition.** The issue is unsafe pickle deserialization: an attacker
must already hold **write access to the cache directory** to achieve code execution
when the application later reads from that cache. This is a local-privilege issue, not
a remote one.

**Reachability.** Two levels inside an opt-in extra:
`opendsstar` extra → `ragworkbench` → `unitxt` → `diskcache`. The `opendsstar` extra is
**not** included in `all`, **not** in `complete`, and is not referenced by the root
`langflow` package, so it is installed only by users who explicitly ask for it.
