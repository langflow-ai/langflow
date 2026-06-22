# Langflow Accessibility Gap Report

> **Audit Date:** 2026-06-09
> **Codebase Branch:** release-1.10.0
> **Current Focus:** IBM Equal Access `Level 1` requirements only
> **Scope:** Frontend code analysis against IBM `Level 1` filtered requirements
> **Reference:** [a11y-level-1-requirements.md](/Users/viktoravelino/projects/langflow/a11y-level-1-requirements.md)
> **Method:** Direct source code analysis + targeted re-validation of current frontend sources
> **Latest targeted update:** 2026-06-17, LE-1518 error handling and announcements

---

## Executive Summary

Langflow is **not IBM Level 1 compliant** today. Core failures cluster around keyboard access, focus handling, semantic structure, accessible naming, and contrast. Most severe blockers sit in shared primitives and high-traffic surfaces: canvas, dialogs, inputs, header/navigation, and icon wrappers.

**Estimated IBM Level 1 compliance score: ~30–35%**

### Top Critical Risks

1. **Canvas keyboard access is explicitly disabled.** `disableKeyboardA11y={true}` is still passed to ReactFlow in [PageComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx:917).
2. **Dialog focus handling is broken by default.** `DialogContent` still prevents automatic focus entry on open in [dialog.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/dialog.tsx:83).
3. **Shared icon and control semantics are unsafe by default.** `ForwardedIconComponent` still exposes no wrapper-level `aria-hidden`, `aria-label`, or `title` props in [genericIconComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/common/genericIconComponent/index.tsx:18) and [types/components/index.ts](/Users/viktoravelino/projects/langflow/src/frontend/src/types/components/index.ts:318).

---

## IBM Level 1 Baseline

IBM's `Level 1` filter currently returns these `21` requirements:

| Criterion | Title | Langflow Status | Notes |
|-----------|-------|-----------------|-------|
| `1.1.1` | Non-text Content | FAIL | Icons, handles, edges, and icon-only controls lack reliable text alternatives |
| `1.2.2` | Captions (Prerecorded) | NOT TESTED | No media-specific implementation verified in this pass |
| `1.2.4` | Captions (Live) | NOT TESTED | No live media-specific implementation verified in this pass |
| `1.3.1` | Info and Relationships | FAIL | Labels, headings, landmarks, tables, and dialog structure all have gaps |
| `1.4.3` | Contrast (Minimum) | FAIL | Multiple text tokens fail minimum contrast in current light theme |
| `1.4.10` | Reflow | PARTIAL | Static review suggests risk; viewport testing still needed |
| `1.4.11` | Non-text Contrast | FAIL | Borders, canvas dots, and state indicators fail graphical contrast |
| `2.1.1` | Keyboard | FAIL | Canvas, cards, faux controls, and some dialogs are not keyboard-safe |
| `2.1.2` | No Keyboard Trap | FAIL | Full-screen playground modal lacks dialog/focus-trap semantics |
| `2.3.1` | Three Flashes or Below Threshold | PASS | No flashing issue found in reviewed code |
| `2.4.2` | Page Titled | FAIL | Most routes keep the generic `"Langflow"` title |
| `2.4.3` | Focus Order | FAIL | Dialog autofocus suppression and trigger tab-order issues remain |
| `2.4.6` | Headings and Labels | FAIL | Prominent auth titles are not headings; multiple fields remain unlabeled |
| `2.4.7` | Focus Visible | FAIL | Global and local CSS suppress visible focus indicators |
| `3.1.1` | Language of Page | PASS | `<html lang="en">` is set |
| `3.2.4` | Consistent Identification | FAIL | Icon-only actions remain inconsistently and often invisibly identified |
| `3.3.1` | Error Identification | PARTIAL | Auth validation and toast announcements fixed; non-auth error surfaces still need broader audit |
| `3.3.2` | Labels or Instructions | FAIL | Placeholder-only inputs still exist in key flows |
| `3.3.3` | Error Suggestion | PASS (TARGETED AUTH) | Login/signup required, mismatch, and server-error flows now expose actionable suggestions |
| `3.3.4` | Error Prevention (Legal, Financial, Data) | FAIL | Flow/folder/deployment confirmations exist, but delete-account is a visible stub and cannot be verified end-to-end |
| `4.1.2` | Name, Role, Value | FAIL | Widespread issues across controls, dialogs, toggles, list cards, and canvas |

---

## Findings By Criterion

### `1.1.1` Non-text Content — FAIL

- Shared icon wrapper does not expose safe accessibility props by default in [genericIconComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/common/genericIconComponent/index.tsx:18) and [types/components/index.ts](/Users/viktoravelino/projects/langflow/src/frontend/src/types/components/index.ts:318).
- Canvas connection handles are unlabeled in `handleRenderComponent`.
- Canvas edges are unlabeled in `CustomEdges`.
- Notification badge in [appHeaderComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/core/appHeaderComponent/index.tsx:42) is visual-only.

### `1.2.2` Captions (Prerecorded) — NOT TESTED

- No prerecorded media workflow was re-verified in this pass.

### `1.2.4` Captions (Live) — NOT TESTED

- No live media workflow was re-verified in this pass.

### `1.3.1` Info and Relationships — FAIL

- `Input` wraps `<input>` in `<label>` while pages also use `Form.Label` in [input.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/input.tsx:38).
- Auth/account entry pages use visual `<span>` titles instead of headings:
  - [LoginPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/LoginPage/index.tsx:83)
  - [SignUpPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/SignUpPage/index.tsx:96)
  - [DeleteAccountPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/DeleteAccountPage/index.tsx:27)
  - [AdminPage/LoginPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/AdminPage/LoginPage/index.tsx:60)
- App header is still a plain `<div>` in [appHeaderComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/core/appHeaderComponent/index.tsx:48).
- Folder/settings navigation landmarks remain weak or absent in sidebar surfaces.
- Admin table semantics remain incomplete.

### `1.4.3` Contrast (Minimum) — FAIL

- Low-contrast text tokens remain in [style/index.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/index.css:14), [style/index.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/index.css:36), and [style/index.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/index.css:127).
- Notable failing patterns include placeholder text, muted text, red status text, and blue token combinations in light theme.

### `1.4.10` Reflow — PARTIAL

- Static review shows risk around constrained layouts and overflow patterns.
- Needs dedicated viewport/manual verification before final pass/fail call.

### `1.4.11` Non-text Contrast — FAIL

- Border/input/canvas contrast tokens remain weak in [style/index.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/index.css:17), [style/index.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/index.css:37), and [style/applies.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/applies.css:1243).
- Invalid-state ring and colored status indicators remain under target contrast.

### `2.1.1` Keyboard — FAIL

- ReactFlow keyboard support explicitly disabled in [PageComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx:917).
- Flow list cards are click-only containers in [MainPage/components/list/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/MainPage/components/list/index.tsx:110).
- `CheckBoxDiv` is visual-only in [checkbox.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/checkbox.tsx:29).
- Accordion trigger still renders through a `<div>` in [accordion.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/accordion.tsx:28).
- Folder rename and several canvas/sidebar actions still rely on mouse-only patterns.

### `2.1.2` No Keyboard Trap — FAIL

- Playground modal uses `type="full-screen"` in [playground-modal.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/IOModal/playground-modal.tsx:344).
- `type="full-screen"` renders a plain `<div>` in [baseModal/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/baseModal/index.tsx:287), without dialog semantics or focus trap.

### `2.3.1` Three Flashes or Below Threshold — PASS

- No flashing pattern was identified in this code review.
- This remains a static-review pass, not a visual media certification.

### `2.4.2` Page Titled — FAIL

- Application default title remains `"Langflow"` in [src/frontend/index.html](/Users/viktoravelino/projects/langflow/src/frontend/index.html:19).
- Playground updates title in [Playground/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/Playground/index.tsx:58), but most other routes do not.

### `2.4.3` Focus Order — FAIL

- Dialog open autofocus is prevented by default in [dialog.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/dialog.tsx:83).
- Delete confirmation trigger still uses `tabIndex={-1}` in [deleteConfirmationModal/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/deleteConfirmationModal/index.tsx:31).
- Focus return after close is not consistently managed across modal flows.

### `2.4.6` Headings and Labels — FAIL

- Prominent auth/account titles are not headings.
- Placeholder-only inputs remain in [DeleteAccountPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/DeleteAccountPage/index.tsx:30) and [AdminPage/LoginPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/AdminPage/LoginPage/index.tsx:63).
- Search, toggle, and icon-only action labels remain inconsistent in admin/store/main flows.

### `2.4.7` Focus Visible — FAIL

- Global focus suppression remains in [tailwind.config.mjs](/Users/viktoravelino/projects/langflow/src/frontend/tailwind.config.mjs:483).
- Additional outline/ring suppression exists in:
  - [App.css](/Users/viktoravelino/projects/langflow/src/frontend/src/App.css:161)
  - [style/classes.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/classes.css:75)
  - [style/ag-theme-shadcn.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/ag-theme-shadcn.css:115)
  - [style/applies.css](/Users/viktoravelino/projects/langflow/src/frontend/src/style/applies.css:1298)

### `3.1.1` Language of Page — PASS

- `<html lang="en">` is present in [src/frontend/index.html](/Users/viktoravelino/projects/langflow/src/frontend/index.html:2).

### `3.2.4` Consistent Identification — FAIL

- Notification, toolbar, dropdown, canvas, and list-card actions rely heavily on unlabeled or inconsistently labeled icon-only patterns.
- Same action types are not consistently exposed with the same accessible naming strategy.

### `3.3.1` Error Identification — PARTIAL

- Login and signup required-field errors are now rendered as `role="alert"` messages and associated with their controls via `aria-describedby` in [LoginPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/LoginPage/index.tsx:78) and [SignUpPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/SignUpPage/index.tsx:86).
- Toasts now map severity to live-region semantics in [alerts/displayArea/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/alerts/displayArea/index.tsx:18): errors use `role="alert"` / `aria-live="assertive"`; success and notice use `role="status"` / `aria-live="polite"`.
- Automated evidence:
  - [LoginPage.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/LoginPage/__tests__/LoginPage.a11y.test.tsx:63)
  - [SignUpPage.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/SignUpPage/__tests__/SignUpPage.a11y.test.tsx:65)
  - [displayArea.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/alerts/displayArea/__tests__/displayArea.a11y.test.tsx:34)
- Remaining risk: non-auth validation/error surfaces were not exhaustively re-audited in this LE-1518 pass.

### `3.3.2` Labels or Instructions — FAIL

- Placeholder-only inputs remain in delete-account and admin-login flows.
- Required markers and instructions are still not clearly exposed in all auth forms.
- Several admin/settings/search surfaces still depend on placeholder-only or weakly associated labels.

### `3.3.3` Error Suggestion — PASS (TARGETED AUTH)

- Signup password mismatch now announces actionable correction text: "Passwords do not match. Re-enter both passwords so they match."
- Server-side login errors append "Check your username and password, then try again."
- Server-side signup errors append "Use a different username or contact an administrator if you already have an account."
- Automated evidence:
  - [LoginPage.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/LoginPage/__tests__/LoginPage.a11y.test.tsx:87)
  - [SignUpPage.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/SignUpPage/__tests__/SignUpPage.a11y.test.tsx:86)

### `3.3.4` Error Prevention (Legal, Financial, Data) — FAIL

- Folder/flow deletion uses [DeleteConfirmationModal](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/deleteConfirmationModal/index.tsx:33), which presents a named destructive confirmation dialog, explicit permanent-delete copy, a cancel action, and a destructive delete action.
- Shared dialog title detection now recognizes nested `DialogHeader > DialogTitle` structures in [dialog.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/dialog.tsx:32), so delete dialogs announce their specific title instead of the fallback "Dialog".
- Automated evidence: [DeleteConfirmationModal.a11y.test.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/deleteConfirmationModal/__tests__/DeleteConfirmationModal.a11y.test.tsx:5) verifies the named dialog, permanent-delete warning, cancel path, and no accidental confirmation on cancel.
- Deployment deletion has stronger type-to-confirm protection in [type-to-confirm-delete-dialog.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/MainPage/pages/deploymentsPage/components/type-to-confirm-delete-dialog.tsx:25).
- Account deletion remains unimplemented: [DeleteAccountPage/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/pages/DeleteAccountPage/index.tsx:12) contains only placeholder comments and no real deletion/recovery path. This prevents a pass for the criterion across the targeted destructive/data-affecting flows.
- Keyboard walkthrough, shared delete dialog: open the delete trigger, focus enters the named "Delete" dialog container, `Tab` reaches `Cancel`, `Delete`, and `Close`, `Cancel` exits without calling confirm, and activating `Delete` runs the destructive callback. Screen-reader structural announcement is supported by `role="dialog"` plus the visible `DialogTitle`; live assistive-technology execution was not performed in this source/test pass.

### `4.1.2` Name, Role, Value — FAIL

- Password toggle lacks accessible name and is removed from tab order in [inputComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/core/parameterRenderComponent/components/inputComponent/index.tsx:303).
- Notification bell button is unlabeled in [appHeaderComponent/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/core/appHeaderComponent/index.tsx:84).
- Full-screen playground modal lacks dialog role/state in [baseModal/index.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/modals/baseModal/index.tsx:287).
- `CheckBoxDiv` lacks checkbox role/state in [checkbox.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/checkbox.tsx:29).
- Accordion trigger lacks proper button semantics in [accordion.tsx](/Users/viktoravelino/projects/langflow/src/frontend/src/components/ui/accordion.tsx:28).
- Many icon-only buttons across cards, dropdowns, toolbars, and dialogs still have no accessible name.

---

## Priority Fixes

1. Remove `disableKeyboardA11y={true}` from canvas and restore keyboard-safe node/list interactions.
2. Remove default dialog autofocus suppression and fix modal trigger/focus return behavior.
3. Add shared icon-wrapper accessibility props and enforce accessible naming for icon-only controls.
4. Replace placeholder-only / fake-heading auth patterns with real labels, headings, and landmarks.
5. Remove global/local focus suppression CSS and restore visible focus indicators.
6. Fix high-impact semantic primitives: `Input`, `CheckBoxDiv`, `AccordionTrigger`, full-screen modal container.
7. Repair route titles so non-playground pages set meaningful `document.title`.
8. Adjust failing text and non-text contrast tokens before page-level QA.
