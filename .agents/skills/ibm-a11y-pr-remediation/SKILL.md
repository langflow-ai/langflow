---
name: ibm-a11y-pr-remediation
description: Scan every frontend surface touched by the current PR/branch for IBM Equal Access Level 1 accessibility issues and fix all in-scope violations by default. Discovers changed files, maps them to routes/components/states, runs both axe and IBM engines, remediates until both are green (or only documented baselines remain), and reports back. Use when the user asks to check, scan, or clean up accessibility for "this PR", "my branch", or "my changes" and wants fixes applied, not just a report. For a single scoped audit report without a default fix pass, use ibm-a11y-level1-audit; for a route batch scan only, use ibm-a11y-route-scan.
disable-model-invocation: true
---

# IBM Level 1 PR Accessibility Remediation

Scope is **IBM Equal Access Level 1 only**. **Default mode is fix, not report-only.** Scan every frontend surface touched by the PR/branch and remediate all in-scope issues until both engines are green (or only documented baselines remain).

This skill is a PR-scoped orchestrator. It does not duplicate detailed engine/pattern guidance — read the linked skills for that:

- [ibm-a11y-testing-guide](../ibm-a11y-testing-guide/SKILL.md) — which engine/test layer to use, POUR checklist, axe-vs-IBM gaps, Radix/AG-Grid gotchas, baselines.
- [ibm-a11y-route-scan](../ibm-a11y-route-scan/SKILL.md) — Python scanner options for ad-hoc route batches.
- [ibm-a11y-level1-audit](../ibm-a11y-level1-audit/SKILL.md) — Level 1 criteria references and report template, useful when the user wants a formal audit report for the PR instead of (or in addition to) fixes.
- [frontend-i18n](../frontend-i18n/SKILL.md) — accessible names / UI strings must go through i18n.

## Mandate

1. Diff the PR (or current branch vs its merge base) for `src/frontend/**` changes.
2. Map changed files → UI surfaces → routes / components / states to scan.
3. Run **both** axe (Jest where applicable) and IBM Equal Access (Playwright `page.runA11yScan` and/or `scripts/a11y/a11y_scan.py` — see `ibm-a11y-testing-guide` / `ibm-a11y-route-scan`).
4. **Fix every in-scope Level 1 violation** in the changed surfaces. Do not stop at a findings list unless the user says **report only** (in that case, hand off to `ibm-a11y-level1-audit`).
5. Re-scan until assert mode passes. Add/update a11y specs when coverage is missing.
6. Report what changed, commands run, and any baselined/deferred debt.

Do **not** invent new tag names, silently disable scans, or expand into IBM Level 2/3 unless asked.

## Progress checklist

```
IBM L1 PR A11y:
- [ ] 1. Collect changed frontend files
- [ ] 2. Map files → surfaces / routes / states
- [ ] 3. Scan (IBM + axe)
- [ ] 4. Fix all in-scope violations
- [ ] 5. Add/update tests if needed
- [ ] 6. Re-scan assert-green
- [ ] 7. Report back
```

## 1. Collect changed frontend files

Prefer the PR merge base when a PR exists; otherwise the branch merge base vs `main`/`master`.

```bash
# PR number known
gh pr diff <n> --name-only | grep -E '^src/frontend/' || true

# Current branch vs upstream default
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD origin/master)
git diff --name-only "$BASE"...HEAD -- 'src/frontend/**'

# Include uncommitted work when the user is mid-change
git diff --name-only HEAD -- 'src/frontend/**'
git diff --name-only --cached -- 'src/frontend/**'
git ls-files --others --exclude-standard 'src/frontend/**'
```

Include:
- `src/frontend/src/**/*.{tsx,ts,jsx,js,css}` (UI)
- `src/frontend/tests/a11y/**` (existing coverage)
- Locale files only when they change accessible names / labels

Skip pure non-UI churn unless it affects a11y (e.g. test helpers that change focus / ARIA). If **no** frontend files changed, say so and stop.

## 2. Map files → surfaces

For each changed file, identify:

| Change type | Scan target |
|-------------|-------------|
| Page / route | That route + meaningful states (empty/populated/modal/mobile) |
| Shared component (`TableComponent`, dialogs, menus) | **Every** consumer page that uses it — not only the file you touched |
| Primitive | Jest axe on the primitive + any Playwright surface that embeds it |
| Spec / baseline only | Re-run that spec; no product fix unless it fails |
| `a11y_routes.json` | Update static coverage; run static or route scan |

List interactive controls and states (default, empty, populated, open modal / menu, selected row, error, mobile). Prefer existing specs under `src/frontend/tests/a11y/`.

## 3. Scan (both engines must pass)

Automated a11y is not one tool — see `ibm-a11y-testing-guide` for the full engine comparison and gotchas. Summary:

- **axe-core** — Jest `axe()` (`@/utils/a11y-test`), jsdom-only.
- **IBM Equal Access** — stricter on ARIA structure and keyboard semantics. Playwright `page.runA11yScan(label)` for stateful surfaces (modals/menus/selected/editing); `scripts/a11y/a11y_scan.py` for default-loaded page only.

```bash
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=5

# Python scanner playwright deps are NOT in default uv sync.
# One-time: uv run --with playwright playwright install chromium
uv run --with playwright python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes /settings/<route> \
  --out /tmp/a11y.json --markdown /tmp/a11y.md --timeout-ms 45000
```

`RUN_A11Y=true` runs the scan; `RUN_A11Y_ASSERT=true` fails on new violations. After changing a shared component, re-scan every page that uses it.

For component-only changes:

```bash
cd src/frontend
npx jest path/to/<name>.a11y.test.tsx --runInBand
```

Do not invent findings — prefer scanner output plus manual Level 1 spot checks scanners miss (keyboard trap both ways, focus restore, 320px reflow, color-not-only).

## 4. Fix all in-scope Level 1 violations

Default: **fix**. Only list proposed fixes without editing if the user asked **report only** — then hand off to `ibm-a11y-level1-audit` for the formal report format.

Rules:
- Prefer semantic HTML over ARIA.
- Follow the Langflow patterns in `ibm-a11y-testing-guide` (AG Grid, Radix `asChild`, focus restore, icon-only `aria-label`).
- Route new UI strings / `aria-label`s through i18n (`t(...)`, all locale files) per `frontend-i18n`.
- Keep fixes minimal; do not refactor unrelated UI.
- Do **not** silently disable scans. Use IBM baselines under `src/frontend/tests/a11y/baselines/` only for documented framework debt.
- Map each issue to a Level 1 WCAG/IBM id; defer anything listed as Level 2/3 in the criteria guide (`ibm-a11y-level1-audit/references/ibm-level1-criteria.md`) unless the user expands scope.

### Manual Level 1 spot checks (when relevant)

- **2.1.1 / 2.1.2:** Tab and Shift+Tab; Escape closes overlays; no trap.
- **2.4.3 / 2.4.7:** Focus order matches visual order; focus ring visible.
- **1.4.10:** 320px / ~400% zoom — no essential horizontal scroll.
- **1.4.1:** Status/errors not color-only.
- **3.3.1 / 3.3.2:** Errors in text and tied to fields; inputs labeled.

## 5. Tests / coverage

| Surface | Spec |
|---------|------|
| Static routes | `static-routes.a11y.spec.ts` (+ `scripts/a11y/a11y_routes.json`) |
| Auth | `auth-pages.a11y.spec.ts` |
| Core pages | `core-pages.a11y.spec.ts` |
| Data-rich | `files.a11y.spec.ts`, `api-keys.a11y.spec.ts`, `global-variables.a11y.spec.ts` |
| Other data-rich | `data-rich-routes.a11y.spec.ts` |

If you fixed a state with no scan, add one (and keyboard tests for custom keyboard behavior) following `files.a11y.spec.ts` / `api-keys.a11y.spec.ts` patterns.

Tag every Playwright a11y test `@release` plus a domain tag (`@workspace` / `@api` / `@database` / `@components` / `@starter-projects`). Import `test`/`expect` from `../fixtures`.

## 6. Re-scan and report

Re-run the same scans with `RUN_A11Y_ASSERT=true`. Each finding → `fixed` | `baselined` | `open`.

When done, state:
- Changed frontend files considered
- Surfaces / states scanned
- Fixes applied (files + what)
- Commands run — whether **both** axe and IBM ran and both reported zero
- Specs / baselines added or updated
- States skipped and why
- Remaining risk or accepted limitation
