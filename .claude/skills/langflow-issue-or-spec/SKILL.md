---
name: langflow-issue-or-spec
description: Use when drafting a GitHub issue, bug report, RFC, or design spec originating from work in this repo. Enforces a minimum shape (problem, repro, expected vs actual, scope, non-goals) so engineers have enough context to act on it, and reminds about PR-description conventions.
---

# Issue or Spec

Fires when the contributor is drafting a GitHub issue, bug report, RFC, or design document about langflow.

A well-shaped issue saves an engineer hours of back-and-forth. A poorly-shaped one becomes a stalled ticket no one wants to pick up.

## Minimum shape

Help the contributor fill in each of these. If a section is genuinely not applicable, say so explicitly rather than leaving it blank.

1. **Problem** — one paragraph. What's happening that shouldn't be, or what's missing that should be there. Concrete, not abstract.
2. **Repro** — for bugs: numbered steps from a clean state. For features: the scenario where the gap shows up.
3. **Expected vs actual** — for bugs: what should happen, what does happen.
4. **Scope** — what's in scope for this issue. One bullet per thing.
5. **Non-goals** — what is deliberately out of scope, so reviewers and implementers don't expand the work.
6. **Context** (optional but valuable) — relevant files, related issues, version, environment.

## For RFCs / design docs specifically

Add:

- **Approach** — the proposed solution in plain language before any code.
- **Alternatives considered** — at least two, with why they were rejected.
- **Open questions** — things you don't yet have an answer to.

## PR description conventions

If this is feeding into a PR description rather than an issue:

- No checklists in PR descriptions. The PR describes the change, not the review.
- Follow [semantic commit conventions](https://www.conventionalcommits.org/) for the title.
- Reference any issues fixed (e.g., `Fixes #1234`).

## Tone

Direct. Specific. No filler. If the writer is uncertain about something, say so explicitly — uncertainty stated is easier to resolve than uncertainty hidden.
