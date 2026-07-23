# IBM Level 1 Accessibility Report Template

Use this structure when delivering the audit report.

```markdown
# IBM Level 1 Accessibility Report

**Date:** YYYY-MM-DD
**Standard:** IBM Equal Access Toolkit v7.3 — Level 1
**Surface:** [routes / components / PR scope]
**Engines:** IBM Equal Access (`page.runA11yScan` / `a11y_scan.py`) · axe (Jest) · manual

## Summary

- Findings: N total (V violations, P potential, M manual)
- Fixed: N · Baselined: N · Open: N
- Verification: PASS | FAIL | PARTIAL — `tests/a11y/...`

## Scope

- In scope: [pages/states]
- Out of scope: [Level 2/3 deferred, unscanned states + why]
- Specs consulted: `src/frontend/tests/a11y/...`

## Findings

| ID | Criterion | Rule / evidence | Location | Severity | Status | Notes |
|----|-----------|-----------------|----------|----------|--------|-------|
| F1 | 4.1.2 | `aria_accessiblename_exists` | `File:Line` or scan label | violation | open \| fixed \| baselined | |

## Fixes

For each fixed finding:

- **F#:** what changed and why (1–2 sentences)
- Files touched

## Verification

Commands run:

```bash
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<spec> --project=chromium --workers=5
```

- Specs updated: [list or none]
- Baselines added/changed: [list or none]
- HTML report: `coverage/accessibility-reports/index.html` (if generated)

## Remaining risk

- Open Level 1 issues
- Accepted baselines (path + reason)
- Manual checks not yet performed
```
