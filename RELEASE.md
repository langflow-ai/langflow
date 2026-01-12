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
* Release timing is coordinated with Langflow’s DevRel team.
* For at least 24 hours after release, Discord, GitHub, and other support channels should be monitored for critical bug reports.

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

### 3. Final Release

```sh
git checkout release-X.Y.Z && git pull # Ensure RC branch is up to date
git tag vX.Y.Z                         # Create final release tag
git push origin vX.Y.Z                 # Push tag to remote
```

### 4. Merge RC Back into Main

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