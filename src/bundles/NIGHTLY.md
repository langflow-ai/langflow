# Bundles & the nightly build

> **Status:** Approach A (canonical pre-releases) is **implemented in this PR**. The guard against
> premature activation is the [activation gate](#activation-gate-must-read) below — **not** merge or
> draft state: this must **NOT** be merged/activated until stable `lfx 1.10.0` is published **and**
> the nightly's base version has moved to the next minor. Sibling docs: [PORTING.md](./PORTING.md).

## Goal

Have **both** the normal release and the nightly depend on the regular published `lfx-*` bundle
packages, and **stop producing nightly bundle packages** (`lfx-arxiv-nightly`, …). The nightly
bundle track is pure overhead — bundle code is low-churn and does not need a per-night rebuild.

## The bundles

Four bundles are extracted as standalone PyPI packages (the only dirs here with a `pyproject.toml`):

| Package          | Dir                       | Version | PyPI    |
| ---------------- | ------------------------- | ------- | ------- |
| `lfx-arxiv`      | `src/bundles/arxiv`       | `0.1.0` | ✅ live |
| `lfx-docling`    | `src/bundles/docling`     | `0.1.0` | ✅ live |
| `lfx-duckduckgo` | `src/bundles/duckduckgo`  | `0.1.0` | ✅ live |
| `lfx-ibm`        | `src/bundles/ibm`         | `0.1.0` | ✅ live |

Each pins `lfx>=1.10.0,<2.0.0` and is wired into the root `pyproject.toml` as a direct dependency
(`lfx-*>=0.1.0`), a `[tool.uv.sources]` workspace entry, and a `[tool.uv.workspace]` member. **The
bundles are unchanged by this PR.**

## The normal release already meets the goal

Stable `langflow 1.10.0` → `lfx-*>=0.1.0` → `lfx>=1.10.0,<2.0.0` → stable `lfx`. One consistent,
canonical `lfx`. No change needed there.

## Background: why the nightly renamed the bundles (removed by this PR)

The old nightly published the core as a **separate distribution**, `lfx-nightly` — but the rename
only rewrote `[project].name`; the wheel still shipped the **same `lfx/` import package**. So a
`langflow-nightly` depending on a *stable* bundle would drag in **stable `lfx` alongside
`lfx-nightly`** — two distributions both owning `site-packages/lfx/` → an install-time collision.
To avoid that, the nightly gave the bundles their own `-nightly` track (`update_lfx_dep_in_bundles`
+ `rename_bundles_for_nightly` in `update_lfx_version.py`). Approach A removes the dual-distribution
design entirely, so that bundle renaming is no longer needed.

## What this PR changes (Approach A — canonical pre-releases)

Publish the nightly under the **canonical** package names as `.devN` pre-releases (`lfx==X.Y.Z.devN`,
`langflow==…`, `langflow-base==…`, `langflow-sdk==…`) instead of separate `*-nightly` distributions.
A single canonical `lfx` then exists, so the stable bundles resolve cleanly — **no bundle changes**.

- **Stop renaming the core.** `update_lfx_version.py`, `update_pyproject_combined.py`,
  `update_sdk_version.py` no longer rename to `*-nightly`; they only set the `.devN` version and
  re-pin inter-package deps to **exact canonical dev versions** (`langflow-base[complete]==<dev>`,
  `lfx==<dev>`, `langflow-sdk==<dev>` — via `update_uv_dependency.py` / `update_lf_base_dependency.py`).
  The exact dev pins also enable pre-release resolution down the tree, so the bundles' `lfx>=…`
  range latches onto the dev `lfx`.
- **Drop the bundle nightly track.** `update_lfx_dep_in_bundles()` and `rename_bundles_for_nightly()`
  are deleted; bundles keep their stable names + `lfx>=1.10.0,<2.0.0` pins.
- **Version math.** `pypi_nightly_tag.py` / `lfx_nightly_tag.py` / `sdk_nightly_tag.py` count `.devN`
  against the **canonical** PyPI histories (`langflow` / `langflow-base` / `lfx` / `langflow-sdk`),
  not the `*-nightly` projects. The base version is still read from the pyproject of the latest
  `release-*` branch the nightly builds from (see `nightly_build.yml`'s `resolve-release-branch`),
  so it tracks the release cadence automatically.
- **Publish workflow.** `release_nightly.yml` publishes canonical pre-releases; the bundle build
  step, the `dist-nightly-bundles` artifact, the `publish-nightly-bundles` job, and its gate in
  `publish-nightly-main` are removed. Verify steps now expect canonical names; the main wheel glob
  is `dist/langflow-*.whl`.

## Activation gate (MUST READ)

Do **not** merge/activate until **both**:

1. **Stable `lfx 1.10.0` is published to PyPI** (the bundles' `lfx>=1.10.0` floor must be satisfiable
   by a real release), **and**
2. **The nightly's base version is the next minor** (i.e. the latest `release-*` branch is
   `release-1.11.0`, so nightlies are `1.11.0.devN`).

Why (2) is not optional: a bundle pins `lfx>=1.10.0,<2.0.0`, and PEP 440 sorts `1.10.0.devN`
**below** `1.10.0`. So a `1.10.0.devN` nightly is **not** `>= 1.10.0` — `langflow-base`'s exact
`lfx==1.10.0.devN` pin would directly conflict with the bundle's `lfx>=1.10.0` floor and resolution
**fails**. Only a next-minor dev (`1.11.0.devN`, which *is* `>= 1.10.0`) resolves. The nightly runs
daily from **main's** workflow definition, so merging this before the gate would break the live
nightly on the next run.

> **Post-activation fix (2026-06):** condition (2) as stated was still fragile — the `release-1.11.0`
> fork's `make patch v=1.11.0` re-synced every bundle floor to `lfx>=1.11.0`
> (`scripts/ci/sync_bundle_lfx_pin.py`), which sorts **above** that same branch's `1.11.0.devN`
> nightlies and reintroduced exactly this conflict on the very first `1.11.0.dev0` nightly (the
> workspace-built bundle's metadata shadows the satisfiable PyPI `0.1.1` in the
> `uv pip install dist/*.whl` test step). The synced floor format is now
> `lfx>=X.Y.0.dev0,<(X+1).0.0` — `X.Y.0.dev0` is the lowest version PEP 440 admits in the minor
> line, so every `devN` / `rcN` / final satisfies it while older lines stay excluded, and the gate
> can no longer regress on future minor forks.

## A1 vs A2 + remaining follow-ups (decide before activating)

This PR implements the **A1** publish behavior: the separate `langflow-nightly` / `langflow-base-nightly`
/ `lfx-nightly` distributions go away; the nightly is installed via `pip install --pre langflow`.

Addressed here (consumers of the dropped `*-nightly` PyPI names, so the cutover stays self-consistent):

- **Runtime nightly detection.** `_get_version_info` (`src/backend/base/langflow/utils/version.py`,
  `test_version.py`) now derives the "Nightly" label from the `.dev` version marker — the canonical
  `langflow` distribution matches first, so the package *name* alone no longer identifies a nightly.
  Keeps the startup banner and telemetry `package` field correct.
- **CI nightly consumers.** `ci.yml`'s `check-nightly-status` inspects the latest `.devN` release of
  the canonical `langflow` project (not `langflow-nightly`); `db-migration-validation.yml` installs
  the nightly as `langflow[postgresql]==<dev>` instead of `langflow-nightly[...]`.
- **LFX install doc.** `src/lfx/README.md` nightly install is now `uv pip install --pre lfx`.

Still open (deferred by design — decisions, not blockers):

- **Docker nightly image.** `langflowai/langflow-nightly` (Docker Hub) is independent of the PyPI
  name and works as-is; decide whether to keep or rename.
- **Website install docs.** Any `pip install langflow-nightly` instructions on the docs site (not in
  this repo) should become `pip install --pre langflow`.
- **A2 alternative (preserve the install name).** Instead of dropping `langflow-nightly`, keep it as
  a thin meta-package pinning `langflow==X.Y.Z.devN`. The scripts already produce exact dev pins, so
  A2 only adds a meta-package publish step and leaves the `pip install langflow-nightly` UX intact.

## Approach B (alternative, not taken)

Move each bundle's `lfx` dependency into an extra (e.g. `lfx-<name>[standalone]`) so the same wheel
is safe inside a `lfx-nightly` env; keep the `-nightly` core and the `pip install langflow-nightly`
UX. Downside: standalone `pip install lfx-arxiv` no longer auto-installs `lfx`, and bundles must
re-publish as `0.1.1`.

## Verification (run against this branch)

- `scripts/ci/test_pypi_nightly_tag.py` passes (15/15) with canonical URLs.
- Tag scripts run live against canonical PyPI and emit `vX.Y.Z.dev0` (no `*-nightly` counted).
- Dry-run `update_sdk_version.py` / `update_lfx_version.py` / `update_pyproject_combined.py` with
  `v1.11.0.dev0` tags → all packages keep canonical names; versions set; pins become
  `langflow-base[complete]==1.11.0.dev0`, `lfx==1.11.0.dev0`, `langflow-sdk==…`; **no** `src/bundles/*`
  file is touched.
- Both workflows are valid YAML; no `publish-nightly-bundles` job remains.
