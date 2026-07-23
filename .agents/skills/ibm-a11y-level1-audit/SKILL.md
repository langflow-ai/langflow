---
name: ibm-a11y-level1-audit
description: Audit Langflow frontend UI against IBM Equal Access Level 1 criteria, produce a compliance report, fix violations, and verify with Playwright a11y specs under src/frontend/tests/a11y. Use when the user asks for an IBM Level 1 a11y audit, Level 1 compliance report, accessibility remediation against IBM Able requirements, or to find/report/fix Level 1 WCAG issues.
---

# IBM Accessibility Level 1 Audit

Audit → report → fix → verify. Scope is **IBM Equal Access Toolkit v7.3 Level 1 only**. Do not expand into Level 2/3 unless the user asks.

## Related skills

| Skill | Use for |
|-------|---------|
| [frontend-a11y-check](../frontend-a11y-check/SKILL.md) | How to write/run axe + IBM scans, baselines, component gotchas |
| [ibm-a11y-automation](../ibm-a11y-automation/SKILL.md) | Python route scanner + Markdown/HTML report generation |
| [frontend-i18n](../frontend-i18n/SKILL.md) | Any new/changed accessible names or UI strings |

## Sources of truth

1. **Level 1 criteria (engineering guide):** [references/ibm-level1-criteria.md](references/ibm-level1-criteria.md) — full checklist, deferred L2/L3 list, common failures, implementation patterns.
2. **Langflow captured IBM Level 1 filter:** `src/frontend/tests/a11y/ibm-able-level-1-requirements.md` — 21 requirements from the IBM Able UI Level 1 filter. Prefer the engineering guide when the two disagree on pace; still map findings to both IDs when useful.
3. **Verification hosts:** `src/frontend/tests/a11y/` — Playwright specs, baselines, README. Confirm this path exists before claiming coverage.

## Workflow

Copy and track:

```
Level 1 Audit Progress:
- [ ] 1. Scope the surface
- [ ] 2. Scan (IBM + axe as applicable)
- [ ] 3. Map findings to Level 1 criteria
- [ ] 4. Write the report
- [ ] 5. Fix violations
- [ ] 6. Verify with tests/a11y
- [ ] 7. Re-scan and update report status
```

### 1. Scope the surface

Identify what to audit from the user request:

- Specific route(s), page(s), or component(s)
- Pending git changes under `src/frontend`
- Default: static routes + any stateful specs that touch the changed surface

Read `src/frontend/tests/a11y/README.md` and list existing specs that already cover the surface.

### 2. Scan

Run **both** engines when the surface is interactive UI (see `frontend-a11y-check`):

```bash
# Playwright IBM scans (live DOM / stateful)
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=5

# Optional: HTML triage report
npm run a11y:html-report --silent
# → coverage/accessibility-reports/index.html

# Ad-hoc route batch (default-loaded page only)
uv run --with playwright python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --out /tmp/langflow-a11y.json \
  --markdown /tmp/langflow-a11y.md \
  --html /tmp/langflow-a11y.html \
  --timeout-ms 45000
```

For component-only changes, also run Jest axe where a `__tests__/*.a11y.test.tsx` exists.

Do not invent findings. Prefer scanner output + manual Level 1 checks scanners miss (keyboard trap both directions, focus restore, reflow at 320px, color-not-only cues).

### 3. Map findings to Level 1

For each issue, assign:

- **WCAG / IBM ID** from [references/ibm-level1-criteria.md](references/ibm-level1-criteria.md) (e.g. `2.1.1`, `4.1.2`)
- **IBM ruleId** when from Equal Access (`aria_accessiblename_exists`, `element_tabbable_role_valid`, …)
- **Severity:** `violation` | `potentialviolation` | `manual`
- **In scope?** Drop or defer anything listed under **Deferred to Level 2 & Level 3** in the criteria doc unless the user expands scope.

### 4. Write the report

Use [references/report-template.md](references/report-template.md). Deliver the report in the chat (and write a file only if the user asks for a path).

Required sections: Summary, Scope, Findings table, Fixes applied / proposed, Verification, Remaining risk / baselines.

### 5. Fix violations

When this skill is invoked for audit+fix (default), fix in-scope Level 1 violations:

- Prefer semantic HTML over ARIA.
- Follow Langflow patterns in `frontend-a11y-check` (AG Grid, Radix `asChild`, focus restore, icon-only `aria-label`).
- Route new UI strings / `aria-label`s through `frontend-i18n`.
- Do **not** silently disable scans. Use IBM baselines under `src/frontend/tests/a11y/baselines/` only for documented framework debt (see `frontend-a11y-check`).
- Keep fixes minimal; do not refactor unrelated UI.

If the user asked for **report only**, stop after step 4 and list proposed fixes without editing.

### 6. Verify with `tests/a11y`

Confirm path: `src/frontend/tests/a11y/`.

| Surface | Spec to run / update |
|---------|----------------------|
| Static routes | `static-routes.a11y.spec.ts` (+ `scripts/a11y/a11y_routes.json` if new route) |
| Auth | `auth-pages.a11y.spec.ts` |
| Core pages | `core-pages.a11y.spec.ts` |
| Data-rich (files, API keys, globals) | `files.a11y.spec.ts`, `api-keys.a11y.spec.ts`, `global-variables.a11y.spec.ts` |
| Other data-rich | `data-rich-routes.a11y.spec.ts` |
| Baselines | `baselines/*.json` |

Commands:

```bash
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<relevant>.a11y.spec.ts --project=chromium --workers=5
```

If coverage is missing for a fixed state, add a scan (and keyboard test when custom keyboard behavior was fixed) following `files.a11y.spec.ts` / `api-keys.a11y.spec.ts` patterns.

### 7. Close the loop

Re-run the same scans. Update the report: each finding → `fixed` | `baselined` | `open`. State commands run and whether IBM assert mode passed.

## Manual Level 1 spot checks

Scanners miss some Level 1 tasks — spot-check when relevant:

- **2.1.1 / 2.1.2:** Tab and Shift+Tab through the surface; Escape closes overlays; no trap.
- **2.4.3 / 2.4.7:** Focus order matches visual order; focus ring visible.
- **1.4.10:** 320px width / ~400% zoom — no essential horizontal scroll.
- **1.4.1:** Status/errors not color-only.
- **3.3.1 / 3.3.2:** Errors named in text and tied to fields; inputs labeled.

## Best practices (data grids + modals)

When auditing or fixing **settings tables** (especially `/settings/global-variables`) and similar AG Grid + modal flows, treat these as Level 1 best practices (2.1.1 / 2.4.3) — not edge-case gotchas.

### Selectable-row keyboard map

Reference implementation: `GlobalVariablesPage` + `tests/a11y/global-variables.a11y.spec.ts`.

| Key | Behavior |
|-----|----------|
| **Space** | Toggle the row selection checkbox (do **not** open edit) |
| **Enter** | Open the Update Variable modal for the focused row |

Implementation notes:

- Handle in page-level `onCellKeyDown` only (do not change shared `TableComponent` defaults for other grids unless the product asks for the same map).
- Add `suppressKeyboardEvent` on that page’s column defs for Enter/Space so AG Grid’s built-in Space selection does not fight the custom handler.
- Sync React selection state after `node.setSelected` so toolbar delete enablement updates (`TableOptions.hasSelection` is read at render time).

### Modal open/close — retain last position (focus restore)

- Opening edit from a row/cell must remember the focused cell (`rowIndex` + `colId`).
- Closing the edit modal (Escape, Cancel, or successful save) must restore focus to that same cell via `api.setFocusedCell` + DOM `.focus()`, using a few `requestAnimationFrame`s to outlast Radix dialog focus cleanup.
- Create modal opened from **Add New** should restore to that trigger (Radix default when a real `DialogTrigger` exists).
- Verify with a Playwright keyboard test: open from a cell → Escape → `document.activeElement` is still that cell (or its `col-id`), then Enter can open again without a manual mouse re-focus.

For AG Grid pagination/tab traps, Radix `asChild`, and popover Esc restore details, see [frontend-a11y-check](../frontend-a11y-check/SKILL.md) (Gotchas vs Best practices sections).

## Out of scope (unless asked)

- IBM Level 2/3 criteria listed as deferred in the criteria reference
- Section 508 software-only rows (web UI covered via 4.1.2)
- Media captions (1.2.x) when the surface has no audio/video
