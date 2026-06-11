# Releasing Langflow

Langflow follows a **release-when-ready** cadence, with each cycle typically lasting 4–6 weeks depending on QA and stabilization needs.

## Goals

* Keep `main` fast-moving for everyday work while ensuring stable release builds when features mature.
* Provide an isolated branch for QA and last-minute fixes (the release candidate, RC).
* Preserve a linear, readable history wherever possible.
* Ensure released code is extensively tested before publication.
* Minimize time to resolution of critical bugs.

## Process Overview

### 1. OSS QA

Create an OSS release candidate (RC) branch containing `langflow` and any associated PyPI packages (e.g. `lfx`).
During this period:

* QA is performed manually.
* Bug fixes are merged into the RC branch.
* New features continue development on `main`.

This step usually lasts about a week.

### 2. Desktop QA

Once OSS QA and bugfixing are complete, create a Desktop release candidate.

* The Desktop RC is based on the final OSS RC.
* Manual QA is performed.
* Bug fixes are merged into the Desktop RC.
* New features continue on `main`.

This step also usually lasts about a week.

### 3. Release

After QA and bugfixing are complete for both OSS and Desktop:

* Final releases are cut from their respective RC branches.
* Release timing is coordinated with Langflow's DevRel team.
* For at least 24 hours after release, Discord, GitHub, and other support channels should be monitored for critical bug reports.

### 4. Release Artifacts

The release workflow automatically publishes the following artifacts:

* **PyPI Packages:**
  * `langflow` - Main package with all integrations
  * `langflow-base` - Core framework without integrations
  * `lfx` - Lightweight executor CLI
  * `langflow-sdk` - SDK for programmatic access (when updated)

* **Docker Images:**
  * `langflowai/langflow` - Full Langflow image
  * `langflowai/langflow-backend` - Backend-only image (published independently)
  * `langflowai/langflow-frontend` - Frontend-only image (published independently)
  * `langflowai/langflow-ep` - Enterprise edition image (published independently)
  * `langflowai/langflow-base` - Base image without integrations

**Note:** Backend, frontend, and enterprise images are published separately from the main image and will be built even if the main version already exists on Docker Hub.

## Branch Model

| Branch                                        | Purpose                                                                                                         | Merge Policy                                                                         |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **`main`**                                    | Integration branch. All feature PRs target this by default.                                                     | **Squash & Merge** (linear history)                                                  |
| **`release-X.Y.Z`**<br>(e.g. `release-1.4.3`) | Temporary RC branch. Active only for the release cycle. Accepts QA and blocking-bug PRs labeled `type:release`. | **Squash & Merge** within the branch.<br>Rebased onto **`main`** before final merge. |

## Release Steps

### 1. Cut Release Candidate

```sh
git checkout main && git pull          # Ensure local main is up to date
git checkout -b release-X.Y.Z          # Create new release candidate branch
git push -u origin release-X.Y.Z       # Push RC branch to remote
```

### 2. Apply a Bugfix to RC

1. Create a feature branch as usual.
2. Open a GitHub PR targeting `release-X.Y.Z`.
3. Review and approve as normal.
4. Merge into the RC branch after review.

### 3. Review Regression Log

Before tagging, review `regressions/X.Y.x.yaml` to confirm no unresolved `blocking` entries exist.
If `blocking` entries exist, they should be signed off on.

See [regressions/README.md](./regressions/README.md) for the full schema and entry instructions.

### 4. Final Release

```sh
git checkout release-X.Y.Z && git pull # Ensure RC branch is up to date
git tag vX.Y.Z                         # Create final release tag
git push origin vX.Y.Z                 # Push tag to remote
```

### 5. Merge RC Back into Main

```sh
git checkout main
git merge --ff-only release-X.Y.Z      # Fast-forward main to include RC changes
```

## Merge Strategy

1. **Squash & Merge** everywhere for atomic commits and clean history.

2. While RC is open, periodically re-sync with main:

   ```sh
   git checkout release-X.Y.Z
   git fetch origin
   git rebase origin/main
   ```

   *This resolves conflicts early while keeping history linear.*

3. Final merge back must be fast-forward only. If not possible, rebase the RC onto `main` before merging.

## Versioning & Tags

* Follows [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.
* RC tags use `-rc.N`, e.g. `v1.8.0-rc.1`.
* **All tags MUST start with `v` prefix** (e.g., `v1.9.1`, not `1.9.1`).
  * The release workflow validates this format and rejects tags without the `v` prefix.
  * Duplicate tags (e.g., both `1.8.3` and `v1.8.3`) cause GitHub's release notes generation to use the wrong base comparison, resulting in incomplete changelogs.
  * The workflow automatically checks for and prevents duplicate tags.

## LFX Compatibility

Langflow and LFX share a **major.minor version line**. The compatibility contract is:

> **LFX X.Y.N is guaranteed compatible with any Flow exported from Langflow X.Y.M.**

Patch releases (`N` and `M`) are independent — a patch to LFX does not require a Langflow patch release, and vice versa.

### Version management

`make patch v=X.Y.Z` updates all four artifacts together:

| Artifact | Version set |
|---|---|
| `langflow` | `X.Y.Z` |
| `langflow-base` | `0.Y.Z` |
| `lfx` | `X.Y.Z` |
| frontend | `X.Y.Z` |

### Cutting an LFX patch release

Use `scripts/release-lfx.sh <version>`. The script warns if the LFX minor version does not match the current Langflow minor version, which would violate the compatibility contract. A warning is not a hard block — patch-only LFX releases within the same minor are expected and fine.

### Implications for users

Users can pin `lfx~=X.Y.0` in their `requirements.txt` to receive all compatible LFX patch releases for a given Langflow minor.

### Migrating from lfx 0.5.x to 1.10.0

LFX was realigned from its standalone `0.5.x` line onto Langflow's `major.minor` line, so the version jumps from `0.5.0` to `1.10.0` in a single step. This is a version-numbering change, not 95 minors of feature churn. The jump affects downstream pins, and neither pip nor uv will flag it — so it must be called out in the release announcement, not just here:

- `lfx==0.5.x` or `lfx<1.0` pins will **not** upgrade (intentional — those deployments stay put).
- `lfx>=0.5,<1` pins will **not** upgrade.
- `lfx>=0.5` with no upper bound **will** pull `1.10.0` on the next install — a major jump with no warning.

Going forward, pin `lfx~=X.Y.0` (e.g. `lfx~=1.10.0`) so you track compatible patches for a given Langflow minor without silently crossing minor lines.

## Roles

| Role                                    | Responsibility                                                    |
| --------------------------------------- | ----------------------------------------------------------------- |
| **Release Captain** (rotates per cycle) | Owns timeline, branch cut, tagging, merge-back.                   |
| **PR Author**                           | Ensures tests pass; flags PR with `type:release` if needed in RC. |
| **CI**                                  | Blocks merges on failing tests or missing labels.                 |

## FAQ

### Do we ever merge main into the RC?

No. Always rebase the RC onto `main` to preserve linear history.

### Can we automate branch deletion?

Not yet — merge-back and cleanup are manual.

### How flexible is the timeline?

Very flexible. QA and stabilization phases can be extended as needed for quality.