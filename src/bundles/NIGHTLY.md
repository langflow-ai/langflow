# Bundles & the nightly build

> **Status:** decision record + runbook. The cutover described in
> [Cutover runbook](#cutover-runbook-gated) is **deferred** and **gated on stable `lfx 1.10.0`
> being published to PyPI**. Until then the nightly keeps its current behavior (it renames the
> bundles — see [Why the nightly renames the bundles](#why-the-nightly-renames-the-bundles)).
> Sibling docs: [PORTING.md](./PORTING.md).

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
(`lfx-*>=0.1.0`), a `[tool.uv.sources]` workspace entry, and a `[tool.uv.workspace]` member. (The
other dirs under `src/bundles/` are placeholders for future extraction and ship nothing.)

## The normal release already meets the goal

Stable `langflow 1.10.0` → `lfx-*>=0.1.0` → `lfx>=1.10.0,<2.0.0` → stable `lfx`. One consistent,
canonical `lfx`. **No change needed.** (These published bundles only become *installable* once the
release ships stable `lfx 1.10.0`; PyPI's stable `lfx` is otherwise behind the bundles' floor.)

## Why the nightly renames the bundles

The nightly stack publishes the core as a **separate distribution**, `lfx-nightly` — but the
rename only rewrites `[project].name`; the wheel still ships the **same `lfx/` import package**
(`[tool.hatch.build.targets.wheel] packages = ["src/lfx"]` is untouched).

So if `langflow-nightly` depended on a **stable** bundle, that bundle's transitive
`lfx>=1.10.0,<2.0.0` would pull in **stable `lfx` alongside `lfx-nightly`**. Two distributions, both
owning `site-packages/lfx/` → an install-time file collision / clobber.

This is the real blocker, and it is **not** removed by publishing stable `lfx 1.10.0`: shipping it
fixes the *resolve* step, but the dual-`lfx` *install* conflict remains as long as the nightly core
is a separately-named distribution. That is why
[`scripts/ci/update_lfx_version.py`](../../scripts/ci/update_lfx_version.py) gives the bundles their
own nightly track via `update_lfx_dep_in_bundles()` (repins each bundle to `lfx-nightly==<dev>`) and
`rename_bundles_for_nightly()` (renames `lfx-<name>` → `lfx-<name>-nightly` and repoints the root
deps + workspace sources).

## Cutover runbook (gated)

> **Gate:** do **not** activate any of the following until stable `lfx 1.10.0` is published to PyPI.
> The nightly runs daily (`cron "0 0 * * *"`) from **main's** workflow definition, so anything
> merged that flips this behavior goes live on the next run.

### Approach A — canonical pre-releases (recommended)

Publish the nightly under the **real** package names as `.devN` pre-releases (`lfx==1.10.x.devN`,
`langflow==…`, `langflow-base==…`, `langflow-sdk==…`); users install with `pip install --pre langflow`.
Then a single canonical `lfx` distribution exists, so the stable bundles resolve cleanly with **no
changes to the bundles at all**.

1. **Stop renaming the core** in `scripts/ci/update_lfx_version.py`: drop
   `update_pyproject_name(..., "lfx-nightly")` and `update_lfx_workspace_dep(..., "lfx-nightly")`;
   version-bump `lfx` under its canonical name. Mirror for base/main/sdk in
   `update_pyproject_combined.py` / `update_pyproject_name.py` / `update_uv_dependency.py`.
2. **Remove the bundle nightly handling**: delete the `update_lfx_dep_in_bundles()` and
   `rename_bundles_for_nightly()` calls in `update_lfx_for_nightly()`.
3. **Version math** — nightlies must sort *above* the latest stable. Post-1.10.0 they become
   `1.10.1.devN` (or the next minor). Update `pypi_nightly_tag.py` / `lfx_nightly_tag.py` /
   `sdk_nightly_tag.py` to read the next-version base and count `dev` against the **canonical** PyPI
   histories (`lfx`, `langflow`, `langflow-base`) instead of the `*-nightly` ones.
4. **Publish workflow** `.github/workflows/release_nightly.yml`: publish canonical pre-releases and
   remove the bundle build step, the `dist-nightly-bundles` artifact, the `publish-nightly-bundles`
   job, and its entry in `publish-nightly-main`'s `needs` / `if`.
5. **Install UX / docs / docker**: `pip install langflow-nightly` → `pip install --pre langflow`;
   update docs + docker nightly tags; deprecate/freeze `langflow-nightly`, `langflow-base-nightly`,
   `lfx-nightly`, and the `lfx-*-nightly` bundles (optionally keep a thin alias during a transition).

### Approach B — `lfx` as a bundle extra (contained alternative)

Move each bundle's `lfx` dependency into an extra (e.g. `lfx-<name>[standalone]`) so the **same
wheel** is safe inside a `lfx-nightly` environment (it no longer drags in a second `lfx`). Keep the
`-nightly` core and the `pip install langflow-nightly` UX; remove only the bundle rename and the
`publish-nightly-bundles` job.

- **Downside:** standalone `pip install lfx-arxiv` no longer auto-installs `lfx` (a runtime
  `ImportError` footgun unless users install the extra or already have `lfx`).
- Bundles re-publish as `0.1.1`. Finalize A-vs-B before cutover.

## Why prepping now is safe (but activating is gated)

The cutover can be authored and **CI-validated now**: PR CI resolves `lfx` from the uv **workspace**
(editable local `lfx 1.10.0`), not PyPI — proven by the fact that the bundles already pin
`lfx>=1.10.0,<2.0.0`, no PR-triggered workflow installs a bundle from PyPI, and the branch is green.
Only **merging/activating** the cutover must wait for stable `lfx 1.10.0`, because that is when
published nightly artifacts and end-user installs resolve `lfx>=1.10.0` from PyPI and the dual-`lfx`
conflict would re-appear on the live nightly.

## Verification (at cutover time)

- `uv lock` resolves `lfx` to the workspace editable (`grep -A2 'name = "lfx"' uv.lock` →
  `editable = "src/lfx"`).
- Dry-run the updater:
  `uv run --no-sync ./scripts/ci/update_lfx_version.py v1.10.1.dev0 v0.1.0.dev0`, then
  `git diff src/bundles src/lfx/pyproject.toml` shows **no** bundle renamed to `-nightly` and **no**
  `lfx` → `lfx-nightly` rename of the core.
- No `lfx-*-nightly` wheels are produced (the `publish-nightly-bundles` job is gone).
