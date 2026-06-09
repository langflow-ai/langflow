# Langflow Accessibility Action Plan

> **Based on:** [a11y-gap-report.md](/Users/viktoravelino/projects/langflow/a11y-gap-report.md) (audit date `2026-06-09`, branch `release-1.10.0`)
> **Scope:** IBM Equal Access `Level 1` only
> **Cycle per item:** Fix → Automated test → Manual test
> **Primary validation tool:** IBM `accessibility-checker`

---

## How to use this plan

Each item follows this pattern:

```text
- [ ] Fix: <what to change and where>
  - [ ] Auto: <IBM checker / unit assertion to add>
  - [ ] Manual: <keyboard / screen reader / visual verification>
```

Work top-to-bottom. Early phases fix shared primitives first, then page surfaces, then contrast cleanup.

---

## Phase 0 — Tooling & Shared Foundations

### 0.1 — Set up IBM Equal Access Checker in Playwright

- [ ] **Fix:** Add `accessibility-checker` and wire `runA11yScan` into Playwright fixtures. Ensure reports write to `coverage/accessibility-reports/`.
  - [ ] **Auto:** `RUN_A11Y=true npx playwright test` produces IBM reports without crashing.
  - [ ] **Manual:** Open generated HTML report and confirm IBM rules + code snippets are present.

### 0.2 — Restore visible focus indicators globally

- [ ] **Fix:** Remove blanket `:focus-visible` suppression from:
  - `src/frontend/tailwind.config.mjs`
  - `src/frontend/src/App.css`
  - `src/frontend/src/style/classes.css`
  - `src/frontend/src/style/ag-theme-shadcn.css`
  - `src/frontend/src/style/applies.css` (`.no-focus-visible`, `.popover-input`, related rules)
  Add explicit fallback:
  ```css
  :focus-visible {
    outline: 2px solid hsl(var(--ring));
    outline-offset: 2px;
  }
  ```
  - [ ] **Auto:** Add a focus regression test that tabs through a button, input, and menu trigger and asserts a visible outline or ring is present.
  - [ ] **Manual:** Tab through Login and Main pages. Every interactive element must show clear visible focus.

### 0.3 — Add accessibility props to `ForwardedIconComponent`

- [ ] **Fix:** Extend `IconComponentProps` with shared a11y props:
  ```ts
  ariaHidden?: boolean;
  ariaLabel?: string;
  title?: string;
  ```
  Pass them through in `src/frontend/src/components/common/genericIconComponent/index.tsx`, defaulting decorative icons to hidden.
  - [ ] **Auto:** Unit test default decorative icon => `aria-hidden="true"`. Named icon => `aria-label` present when requested.
  - [ ] **Manual:** Screen reader should stop announcing decorative icons across header/forms/list cards.

### 0.4 — Remove default dialog autofocus suppression

- [ ] **Fix:** In `src/frontend/src/components/ui/dialog.tsx`, stop calling `e.preventDefault()` when no custom `onOpenAutoFocus` was provided.
  - [ ] **Auto:** Dialog test opens modal and asserts focus lands inside dialog content.
  - [ ] **Manual:** Open modal with keyboard. Screen reader announces title and focus starts inside modal.

---

## Phase 1 — Critical Shared Primitive Fixes

### 1.1 — Fix password show/hide toggle semantics

- [ ] **Fix:** In `src/frontend/src/components/core/parameterRenderComponent/components/inputComponent/index.tsx`:
  - remove `tabIndex={-1}`
  - keep native `<button type="button">`
  - add `aria-label` for current show/hide state
  - add `aria-pressed={pwdVisible}`
  - mark Eye/EyeOff icons decorative
  - [ ] **Auto:** Unit test toggle is tab-focusable and has correct `aria-label` / `aria-pressed`.
  - [ ] **Manual:** Tab to password toggle in Login. Press Space. State and label both change.

### 1.2 — Fix double-label `Input` primitive

- [ ] **Fix:** In `src/frontend/src/components/ui/input.tsx`, replace outer `<label>` wrapper with a neutral wrapper where the field is already labeled externally. Mark placeholder helper span `aria-hidden="true"`.
  - [ ] **Auto:** Unit test / jest-axe on input inside `Form.Field` shows no duplicate label issue.
  - [ ] **Manual:** Screen reader announces auth field label once, not twice.

### 1.3 — Fix `CheckBoxDiv`

- [ ] **Fix:** In `src/frontend/src/components/ui/checkbox.tsx`, add:
  - `role="checkbox"`
  - `aria-checked`
  - `aria-disabled`
  - keyboard support for Space / Enter
  - focusable `tabIndex`
  - [ ] **Auto:** Unit test keyboard toggles state and exposes checkbox semantics.
  - [ ] **Manual:** Admin checkbox can be reached and toggled by keyboard and announced correctly.

### 1.4 — Fix accordion trigger semantics

- [ ] **Fix:** In `src/frontend/src/components/ui/accordion.tsx`, stop rendering trigger as child `<div>`. Use native/focusable trigger semantics.
  - [ ] **Auto:** Unit test ensures trigger is keyboard-focusable and exposes correct role/state.
  - [ ] **Manual:** Tab to accordion trigger. Enter/Space opens and closes it.

### 1.5 — Fix full-screen modal semantics

- [ ] **Fix:** In `src/frontend/src/modals/baseModal/index.tsx` and `src/frontend/src/modals/IOModal/playground-modal.tsx`, make `type="full-screen"` expose real dialog semantics:
  - `role="dialog"`
  - `aria-modal="true"`
  - labeled title
  - focus trap
  - [ ] **Auto:** Dialog a11y test asserts `aria-dialog-name` passes.
  - [ ] **Manual:** Playground opens as proper modal; Tab stays trapped inside.

### 1.6 — Fix broken modal rendering path

- [ ] **Fix:** Replace empty-fragment implementation in `src/frontend/src/customization/components/custom-dialog-content-without-fixed.tsx` with real content, or stop routing timeout/fetch error modals through it.
  - [ ] **Auto:** Render timeout/fetch error dialog and assert text + buttons exist.
  - [ ] **Manual:** Trigger error state and confirm modal is visible and operable.

### 1.7 — Fix dialog titles

- [ ] **Fix:** Correct modal title handling in:
  - `src/frontend/src/modals/authModal/index.tsx`
  - `src/frontend/src/modals/templatesModal/index.tsx`
  - `src/frontend/src/modals/modelProviderModal/index.tsx`
  - `src/frontend/src/components/ui/dialog.tsx`
  Ensure real titles are announced once, not duplicated with fallback `"Dialog"`.
  - [ ] **Auto:** Unit tests for each modal assert a single accessible dialog name.
  - [ ] **Manual:** Screen reader announces actual modal title, not generic `"Dialog"`.

---

## Phase 2 — Core Keyboard & Naming Blockers

### 2.1 — Restore ReactFlow keyboard accessibility

- [ ] **Fix:** Remove `disableKeyboardA11y={true}` from `src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx`. Resolve key conflicts without disabling ReactFlow keyboard support globally.
  - [ ] **Auto:** Component test asserts prop is no longer passed as `true`.
  - [ ] **Manual:** Tab into canvas and use keyboard navigation/select actions on nodes.

### 2.2 — Fix flow list cards keyboard access

- [ ] **Fix:** In `src/frontend/src/pages/MainPage/components/list/index.tsx`, make cards real links/buttons or add keyboard activation with focusability.
  - [ ] **Auto:** Unit test asserts list card has focusable interactive surface.
  - [ ] **Manual:** Tab to flow card and open with Enter.

### 2.3 — Fix notification bell naming

- [ ] **Fix:** In `src/frontend/src/components/core/appHeaderComponent/index.tsx`:
  - add `aria-label` to bell button
  - expose unread state text to AT
  - ensure icon is decorative
  - [ ] **Auto:** Unit test asserts accessible name and unread SR text.
  - [ ] **Manual:** Screen reader announces bell button meaningfully, including unread state.

### 2.4 — Fix icon-only actions across high-traffic surfaces

- [ ] **Fix:** Add explicit accessible names to:
  - main page list card “more options”
  - view toggles
  - bulk actions
  - account/theme controls
  - canvas toolbar buttons
  - node toolbar buttons
  - refresh / store / image viewer icon-only buttons
  - [ ] **Auto:** Add focused unit tests for shared button wrappers and a few representative pages.
  - [ ] **Manual:** Screen reader announces each icon-only control by function, not icon name or nothing.

### 2.5 — Fix canvas handles and edges

- [ ] **Fix:** Add accessible names to node handles and edges in:
  - `src/frontend/src/CustomNodes/GenericNode/components/handleRenderComponent/index.tsx`
  - `src/frontend/src/CustomEdges/index.tsx`
  - [ ] **Auto:** Unit test asserts `aria-label` on handle and edge renderers.
  - [ ] **Manual:** Screen reader can identify connection points and relationships.

---

## Phase 3 — Structure, Headings, Labels, Titles

### 3.1 — Fix auth/account headings

- [ ] **Fix:** Replace visual `<span>` titles with `<h1>` in:
  - `src/frontend/src/pages/LoginPage/index.tsx`
  - `src/frontend/src/pages/SignUpPage/index.tsx`
  - `src/frontend/src/pages/DeleteAccountPage/index.tsx`
  - `src/frontend/src/pages/AdminPage/LoginPage/index.tsx`
  - [ ] **Auto:** Unit tests assert one visible `<h1>` per page.
  - [ ] **Manual:** Screen reader heading navigation finds correct page heading.

### 3.2 — Fix placeholder-only and weakly labeled inputs

- [ ] **Fix:** Add proper labels or programmatic names to:
  - `DeleteAccountPage` confirm password input
  - `AdminPage/LoginPage` username/password
  - admin/store/search surfaces called out in report
  - [ ] **Auto:** jest-axe / unit tests for representative forms show no missing-label violations.
  - [ ] **Manual:** Screen reader announces each input name before value/type.

### 3.3 — Fix app header / navigation semantics

- [ ] **Fix:** Change outer app header container to semantic `<header>` in `src/frontend/src/components/core/appHeaderComponent/index.tsx`. Add proper navigation semantics for sidebar surfaces.
  - [ ] **Auto:** Unit tests assert header/nav landmarks exist.
  - [ ] **Manual:** Landmarks list shows header and navigation regions correctly.

### 3.4 — Fix route titles

- [ ] **Fix:** Add page-specific `document.title` updates beyond Playground.
  - [ ] **Auto:** Route/page tests assert title changes by page.
  - [ ] **Manual:** Browser tab title updates correctly during navigation.

### 3.5 — Fix admin table structure

- [ ] **Fix:** Improve admin table semantics:
  - caption or table label
  - proper Actions header text
  - `scope="col"` on table heads
  - avoid hidden headers breaking associations
  - [ ] **Auto:** Table accessibility test verifies header associations.
  - [ ] **Manual:** Screen reader table nav reads headers for each data cell.

---

## Phase 4 — Error Handling & User Guidance

### 4.1 — Fix validation message announcement

- [ ] **Fix:** In auth flows, make validation messages screen-reader discoverable and announced when they appear.
  - `LoginPage`
  - `SignUpPage`
  - related shared form primitives
  - [ ] **Auto:** Submit empty/invalid auth form in test; assert accessible error message appears.
  - [ ] **Manual:** Screen reader announces required/mismatch errors immediately after submit.

### 4.2 — Fix alert/toast semantics

- [ ] **Fix:** Add live-region behavior to `src/frontend/src/alerts/displayArea/index.tsx` so success/error/notice messages are announced appropriately.
  - [ ] **Auto:** Unit test dispatches alert and checks `aria-live` / urgent semantics.
  - [ ] **Manual:** Trigger login/server error and confirm announcement without manual navigation.

### 4.3 — Re-verify `3.3.3` Error Suggestion

- [ ] **Fix:** After auth/message changes, re-test signup and auth error flows. Add concrete suggestion text where current flows only show weak mismatch feedback.
  - [ ] **Auto:** Form tests cover password mismatch and server-side auth failures.
  - [ ] **Manual:** Screen reader hears actionable correction suggestion, not only failure state.

### 4.4 — Re-verify `3.3.4` Error Prevention

- [ ] **Fix:** Audit destructive/data-affecting user flows after dialog fixes. Ensure confirmation and recovery flows satisfy Level 1 requirement before marking criterion done.
  - [ ] **Auto:** Add representative tests for destructive confirmation flow.
  - [ ] **Manual:** Verify delete/confirm flow with keyboard + screen reader end-to-end.

---

## Phase 5 — Contrast & Visual Compliance

### 5.1 — Fix failing text contrast tokens

- [ ] **Fix:** Update low-contrast text tokens in `src/frontend/src/style/index.css`, including:
  - `--placeholder-foreground`
  - `--muted-foreground`
  - `--status-red`
  - `--accent-blue`
  - `--accent-blue-foreground`
  - [ ] **Auto:** Add token-level contrast assertions or visual regression notes for key pairs.
  - [ ] **Manual:** Verify text contrast in light theme against IBM checker and manual inspection.

### 5.2 — Fix failing non-text contrast tokens

- [ ] **Fix:** Update:
  - `--canvas-dot`
  - weak border/input tokens
  - invalid-state ring colors
  - colored status indicators that fail graphical contrast
  - [ ] **Auto:** IBM checker run on representative pages after token updates.
  - [ ] **Manual:** Inspect focus rings, borders, canvas dots, and state indicators in light theme.

---

## Exit Criteria

- All confirmed IBM Level 1 failures in [a11y-gap-report.md](/Users/viktoravelino/projects/langflow/a11y-gap-report.md) have code fixes.
- `3.3.3` and `3.3.4` have been explicitly re-tested and resolved to final statuses.
- IBM `accessibility-checker` reports are clean enough to support Level 1 signoff on targeted flows.
