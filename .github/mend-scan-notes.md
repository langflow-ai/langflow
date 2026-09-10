# Mend scan triage notes

Last verified: **2026-09-10**. Upstream advisory evidence was initially checked
against PR #15019 commit `6adb1ccaac945b718d8b9f63d9f0272bc205323f`;
the DiskCache removal below is a subsequent update to the same PR.
These are engineering findings, **not security-approved waivers**. An unavailable
fix or an unused built-in code path does not close an advisory.

## Release scope

PR #15019 addresses the Transformers and PyTorch findings with published dependency
floors and a compatible Docling upgrade. It also removes OpenDsStar and DiskCache
from the managed dependency graph, while retaining component code for manual
opt-in installations. Accelerate, LangChain Community, and Chroma remain unresolved;
target their broader remediation for 1.12.3/1.13.0 subject to release planning.
A decision to defer them is not a remediation or non-impact approval.

| Dependency | Current evidence | Follow-up and compatibility impact |
| --- | --- | --- |
| `accelerate==1.14.0` | Both checkpoint path escape and FIFO blocking reproduce in **1.15.0**. | Maintain a reviewed fix for both paths, or replace the local-model consumers. A version-only upgrade is insufficient. |
| `langchain-community==0.4.2` | No built-in `SitemapLoader` reference found; exact runtime/custom-flow scope still needs security review. | Migrate the actual consumers to maintained packages, retaining saved component identities and testing old flows. |
| `chromadb==1.5.9` | No newer PyPI release; existing collection-creation hardening is not evidence for every advisory. | Assess each finding; replacing Chroma also requires knowledge-base storage migration and retrieval validation. |
| `diskcache` | Removed from the managed lock and full-workspace export with OpenDsStar and Unitxt. | OpenDsStar, CodeAct Smolagents, and File Description Generator require manual installation, which reintroduces DiskCache. |

## How to verify a finding before acting on it

1. Resolve the exact CVE/GHSA or vendor advisory. Package-name queries can miss
   advisories without package metadata: for example, the SitemapLoader advisory
   below currently has no package attached in the GitHub Advisory Database.
2. Check affected ranges, released artifacts, and the actual fix. A `last_affected`
   value or range ending at an older release is not proof that the next release
   contains a fix. A null `first_patched_version` means no fix is recorded there;
   independently verify any candidate release.
3. Trace the declared dependency and its runtime consumers. Distinguish the
   installed package, a reachable vulnerable path, and security-approved non-impact.
4. Exercise both the reported failure and legitimate behavior before declaring a
   fix. Regenerate the lock/export after dependency changes and rescan the full scope.

Useful discovery commands (empty results are not proof of safety):

```bash
gh api '/advisories?ecosystem=pip&affects=<pkg>&per_page=100'
curl --fail --silent --show-error -X POST https://api.osv.dev/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"package":{"name":"<pkg>","ecosystem":"PyPI"}}'
curl --fail --silent --show-error 'https://pypi.org/pypi/<pkg>/json'
```

## Scan surface

[The Mend workflow](workflows/mend.yml) starts from:

```bash
uv export --quiet --locked --all-packages --all-extras --all-groups \
  --no-emit-workspace --no-annotate --no-header --no-hashes \
  --format requirements.txt -o requirements-workspace-mend.txt
```

It then compiles for Python 3.12/Linux x86_64 with the PyTorch CPU index and scans
that result, the GP script requirements, and frontend dependencies. The initial
export contains every optional extra and development group; the compile applies
the target platform's markers. Removing a dependency from a default install while
retaining it in an extra does not remove it from this scan scope.

The export at the initial review commit contained all four packages in the table.
The updated export excludes OpenDsStar, ragworkbench, Unitxt, and DiskCache across
all workspace packages, extras, and groups; the other three findings remain.
[The Mend run at that commit](https://github.com/langflow-ai/langflow/actions/runs/34513056033)
completed successfully, but scan completion does not establish that its inventory
has no advisories. No per-finding Mend report or approved non-impact decision was
available for this review. Keep the scan scope intact for follow-up remediation.

## Transformers and PyTorch — addressed by PR #15019

The lock resolves `transformers==5.17.0`, `torch==2.14.0`, and
`torchvision==0.29.0`. Published dependencies require `transformers>=5.10.1` and,
for local Docling, `torch>=2.14.0`. The Docling floor is `>=2.125.0` and the
`lfx-docling` bundle is 0.1.7, avoiding the older macOS Transformers cap.

The earlier classification of Transformers 5.8.1 as a false positive is obsolete.
PR #15019 records CVE-2026-9856 template-path rejection and CVE-2025-3000 TorchScript
validation, legitimate controls, Docling conversion, and package/release checks.
Refer to the PR for the exact validation scope and environment limitations.

## Accelerate — 1.15.0 is not a verified fix

[CVE-2026-69112 / GHSA-4j2p-28q2-5m79](https://github.com/advisories/GHSA-4j2p-28q2-5m79)
covers unchecked shard names in checkpoint `weight_map` entries: paths can escape
the checkpoint directory, and named pipes can block loading indefinitely. The
advisory currently records affected versions through 1.14.0 and no patched version.

The [1.15.0 release source](https://github.com/huggingface/accelerate/blob/v1.15.0/src/accelerate/utils/modeling.py#L1936-L1944)
still joins the checkpoint folder with unvalidated index values. Proposed fixes
[#4070](https://github.com/huggingface/accelerate/pull/4070) and
[#4138](https://github.com/huggingface/accelerate/pull/4138) were closed without
merging; #4138 also explicitly excludes FIFO protection.

Local validation used the PyPI 1.14.0 and 1.15.0 wheels, PyTorch 2.14.0,
safetensors 0.8.0, and Python 3.14.3 on macOS:

- Both `load_checkpoint_in_model` and `load_checkpoint_and_dispatch` loaded a
  synthetic tensor outside the checkpoint directory through relative and absolute
  shard paths, on both releases.
- A FIFO shard blocked `load_checkpoint_in_model` beyond a three-second timeout,
  after the subprocess had imported its dependencies. The subprocess was killed.
- Sibling shards, nested shards, and Hugging Face cache-style symlink controls
  loaded successfully through both APIs on both releases.

All files were disposable local fixtures; no host data or external model was used.
This confirms the dependency bug, not reachability from every Langflow feature.
The lock pulls Accelerate through `docling-slim`'s `models-local` and `standard`
extras. The local Docling bundle requires that stack. A complete backport needs
both containment and non-regular-file handling, with explicit tests for legitimate
Hugging Face cache symlinks and supported platforms. Do not suppress the finding
or raise the version as a security fix based only on the advisory's range endpoint.

## LangChain Community — migration or scoped non-impact review needed

[CVE-2026-72848 / GHSA-vg8m-4p2q-gcjh](https://github.com/advisories/GHSA-vg8m-4p2q-gcjh)
describes `SitemapLoader` fetching nested sitemap URLs without applying its
same-domain restriction. The [upstream report](https://github.com/langchain-ai/langchain/issues/38814)
identifies the nested fetch path. PyPI still reports 0.4.2 as the latest release.

No `SitemapLoader` reference was found in the current `src` Python or JSON files. That
is a candidate basis for a **scoped** non-impact review, not proof about custom
components, imported saved flows, dynamically selected loaders, or downstream
extensions. Confirm the advisory identity against the actual Mend finding before
closing it.

`langchain-community` is a direct `langflow-base` dependency and is also required
by provider bundles and development extras. Consumers include document loaders,
vector stores, chat histories, and search utilities; a bounded search found 50
production Python files with imports, including deactivated components. The lock
also has third-party parents such as `agent-lifecycle-toolkit`, `langchain-cohere`,
`langchain-experimental`, `langchain-google-community`, and OpenDsStar.
Removing only one manifest edge will not remove the package from the full export. Migrate callers and
transitive consumers, preserve component class names used by saved flows, and
validate representative flows before removing the package.

## Chroma — per-advisory assessment and migration planning needed

PyPI still reports 1.5.9 as the latest release. The package-indexed GitHub query
returned these four advisories, each with no recorded patched version:

| Advisory | Reported surface |
| --- | --- |
| [CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | Python server collection creation before authentication |
| [CVE-2026-45830](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | Server collection operations crossing tenant boundaries |
| [CVE-2026-45831](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | `SimpleRBACAuthorizationProvider` resource-scope checks |
| [CVE-2026-45833](https://github.com/advisories/GHSA-36p7-vc44-83pf) | Server collection updates with model-loading configuration |

The CVE records identify two additional Chroma advisories that the package-indexed
query did not return:

| Advisory | Reported surface |
| --- | --- |
| [CVE-2026-45832](https://www.cve.org/CVERecord?id=CVE-2026-45832) | Python V1 collection endpoints omit tenant/database authorization context |
| [CVE-2026-8828](https://www.cve.org/CVERecord?id=CVE-2026-8828) | Rust server collection operations crossing tenant boundaries |

These six published advisories are candidates for the reported Mend total of six.
The actual Mend identifiers were unavailable, so the mapping remains unconfirmed.
Each needs its own exposure assessment; a package-query result alone is incomplete.

Built-in Langflow paths use Chroma clients, including embedded `PersistentClient`,
and do not themselves start Chroma's Python FastAPI server. This is relevant to
specific server advisories, but is not sufficient to waive all six findings or
assess a user-operated Chroma server.

`src/lfx/src/lfx/base/vectorstores/chroma_security.py` supplies
`embedding_function=None` when creating collections. It does not validate every
existing/returned collection configuration or collection update. Assess remote
configuration and client-side embedding/model-loading paths as well; do not treat
collection-creation defaults as comprehensive remediation.

Both `chromadb` and `langchain-chroma` are default `langflow-base` dependencies.
Chroma backs knowledge-base storage, ingestion, querying, retrieval, and deletion
as well as the Chroma component. Replacement requires a storage migration for
existing knowledge bases, plus behavior and saved-flow compatibility validation.

## DiskCache — removed from managed dependencies; manual opt-in remains affected

[CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)
covers unsafe pickle deserialization from attacker-writable cache storage. PyPI
still reports 5.6.3 as the latest release; no patched version is recorded. This PR
removes the dependency rather than patching DiskCache or claiming non-impact.

The previous lock contained **both** paths:

- `OpenDsStar -> diskcache`
- `OpenDsStar -> ragworkbench -> unitxt -> diskcache`

Removed the `lfx[opendsstar]` and `langflow-base[opendsstar]` extras and the
OpenDsStar requirement from `lfx-bundles[codeagents]`, including the generator's
dependency map. The latter extra is included in `lfx-bundles[all]`; previously it
pulled OpenDsStar into every full-workspace export on supported platforms. The
separate Smolagents requirement remains. `lfx-bundles` is bumped to 1.1.24 and
application/LFX bundle floors require that release.

`OpenDsStarAgentComponent`, `CodeActAgentSmolagentsComponent`, and
`FileDescriptionGeneratorComponent` retain their classes, inputs, outputs, and
import shims for saved flows. Without a manual installation, execution reports
how to install the missing dependency. File Description Generator preserves its
subprocess boundary and includes the installation guidance in the child error.
No dependency is installed automatically at runtime.

See [manual installation instructions](../src/bundles/lfx-bundles/README.md#opendsstar-manual-installation-only).
That opt-in restores the upstream cache consumers, including File Description
Generator's `DoclingDescriptionBuilder` with caching enabled. **Such environments
remain affected** and require their own security assessment. This removal covers
Langflow-managed dependencies, not user-installed OpenDsStar environments.

The dependency regression check rejects OpenDsStar or DiskCache in `uv.lock` and
in the bundle generator. The full-workspace export, Mend's Python 3.12/Linux
requirements, GP requirements, and built `lfx`, `langflow-base`, and `lfx-bundles`
wheel metadata were checked and exclude the retired dependencies. All 34 focused
metadata/component tests passed, including real subprocess error coverage.
Manual opt-in resolves with the new wheels and restores DiskCache as documented;
external-model execution was not rerun. The Mend workflow and scan scope are unchanged.
