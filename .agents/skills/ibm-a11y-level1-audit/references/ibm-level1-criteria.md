# IBM Accessibility Level 1 — Engineering Compliance Guide

> **Standard:** IBM Equal Access Toolkit v7.3 (required as of October 1, 2024)
> **Aligns with:** WCAG 2.2 Level A & AA · US Section 508 · EN 301 549 v3.2.1
> **Source:** [IBM Accessibility Requirements](https://www.ibm.com/able/requirements/requirements/?version=v7_3)

---

## What is IBM Level 1?

IBM divides its accessibility requirements into three progressive levels of *pace of completion*. IBM assigns individual tasks within each requirement (across the Design, Develop, and Test disciplines) to a level, so teams can adopt accessibility incrementally rather than mapping each success criterion to a single level:

| Level | Purpose |
|-------|---------|
| **Level 1** | Essential tasks — highest user impact, least investment. Addresses the top concerns of people with disabilities. |
| Level 2 | Next-most-important issues that may prevent certain users from fully using the product. |
| Level 3 | Full WCAG 2.2 A/AA compliance — all three levels must be completed together. |

> **Important:** Completing only Level 1 does NOT achieve full WCAG compliance. It represents the first-priority phase in a release planning cycle. However, products completing only Level 1 can still achieve valuable accessibility and many requirements will "Support" conformance.

### Scope of this guide

This guide covers **only the requirements within IBM's Level 1 pace** — the foundational WCAG 2.0 Level A/AA criteria plus **1.4.10 Reflow** (the single WCAG 2.1/2.2 addition IBM paces at Level 1, per the [v7.3 release notes](https://www.ibm.com/able/requirements/release-notes/)). A handful of the kept requirements also carry Level 2/3 tasks for *full* conformance (for example, data tables under 1.3.1, or media alternatives); those follow-on tasks are out of scope here.

Every requirement IBM paces entirely at **Level 2 or Level 3** — all WCAG 2.1/2.2 additions and the media audio-description criteria — is listed in [Deferred to Level 2 & Level 3](#deferred-to-level-2--level-3) with its authoritative IBM pace level. Those are **not** part of a Level 1 release.

---

## Quick Reference Checklist

### Principle 1: Perceivable

| # | Requirement | Key Rule | Level 1 Tasks |
|---|-------------|----------|--------------|
| 1.1.1 | Non-text Content | All non-text content must have a text alternative | Alt text for images, icons, graphics, CAPTCHA |
| 1.3.1 | Info and Relationships | Structure conveyed visually must be programmatic | Semantic HTML: headings, lists, tables, forms |
| 1.3.2 | Meaningful Sequence | Reading order must be programmatically correct | DOM order matches visual reading order |
| 1.3.3 | Sensory Characteristics | Instructions must not rely only on shape/location | Include text labels alongside shape/position references |
| 1.4.1 | Use of Color | Color must not be the only visual cue | Add icons, patterns, or text alongside color indicators |
| 1.4.2 | Audio Control | Auto-playing audio >3s needs a stop/pause control | Provide volume or mute control independent of system |
| 1.4.3 | Contrast (Minimum) | Text must meet contrast ratios | **4.5:1** for body text · **3:1** for large text (18pt / 14pt bold) |
| 1.4.4 | Resize Text | Text must scale to 200% without loss | Do not clip, overlap, or hide text at 200% zoom |
| 1.4.5 | Images of Text | Use real text instead of images of text | Replace image-based text with HTML/CSS text |
| 1.4.10 | Reflow | Content must reflow without horizontal scroll | Layout must work at 320px wide (400% zoom on desktop) |

---

### Principle 2: Operable

| # | Requirement | Key Rule | Level 1 Tasks |
|---|-------------|----------|--------------|
| 2.1.1 | Keyboard | All functionality must be keyboard-operable | Every interactive element reachable and usable by keyboard |
| 2.1.2 | No Keyboard Trap | Focus must never get stuck | Users can always tab away; Escape closes modals/overlays |
| 2.2.1 | Timing Adjustable | Time limits must be adjustable | Allow 10× extension or turn-off for session timeouts |
| 2.2.2 | Pause, Stop, Hide | Moving/auto-updating content must be pausable | Controls to pause carousels, tickers, auto-advancing slides |
| 2.3.1 | Three Flashes | No content flashes more than 3× per second | Eliminate or threshold-test all flashing content |
| 2.4.1 | Bypass Blocks | Skip-nav or landmark regions must be available | Implement ARIA landmarks (`main`, `nav`, `banner`, `footer`) |
| 2.4.2 | Page Titled | Every page/document needs a descriptive title | Unique `<title>` tags: "Page Name – App Name" pattern |
| 2.4.3 | Focus Order | Tab order must preserve meaning | DOM order matches visual order; no arbitrary `tabindex` values |
| 2.4.4 | Link Purpose | Link text must describe the destination | Avoid "click here" / "read more" — use descriptive text or `aria-label` |
| 2.4.5 | Multiple Ways | Multiple ways to navigate a set of pages | Provide search + navigation menus |
| 2.4.6 | Headings and Labels | Headings and labels must be descriptive | Each heading uniquely describes the section it heads |
| 2.4.7 | Focus Visible | Keyboard focus indicator must be visible | Never suppress `outline` without a visible replacement |

---

### Principle 3: Understandable

| # | Requirement | Key Rule | Level 1 Tasks |
|---|-------------|----------|--------------|
| 3.1.1 | Language of Page | Page language must be programmatically identified | Set `lang` attribute on `<html>` element |
| 3.1.2 | Language of Parts | Language changes within content must be marked | Add `lang` attribute to any inline text in a different language |
| 3.2.1 | On Focus | Receiving focus must not cause a context change | No form auto-submit or page redirect on focus |
| 3.2.2 | On Input | Changing a UI setting must not auto-change context | Warn users if changing a dropdown navigates them away |
| 3.2.3 | Consistent Navigation | Repeated navigation must appear in the same order | Nav menus, headers, footers stay consistent across pages |
| 3.2.4 | Consistent Identification | Same-function components must be identified the same way | Icon and alt text for "Search" must be identical across pages |
| 3.3.1 | Error Identification | Errors must identify the field and describe the issue | Red border alone is insufficient — add text error message |
| 3.3.2 | Labels or Instructions | All inputs must have labels or instructions | Visible `<label>` or `aria-label` on every input field |
| 3.3.3 | Error Suggestion | Correction suggestions must be provided where known | "Enter a valid email address (e.g., user@example.com)" |
| 3.3.4 | Error Prevention | Legal/financial/data actions must be reversible or confirmable | Confirmation step or undo option for destructive actions |

---

### Principle 4: Robust

| # | Requirement | Key Rule | Level 1 Tasks |
|---|-------------|----------|--------------|
| 4.1.2 | Name, Role, Value | All UI components must expose name, role, and state to AT | Use semantic HTML or proper ARIA roles/states/properties |

---

### Deferred to Level 2 & Level 3

The following criteria are **not** part of Level 1 and are excluded from the checklist above. Pace levels are taken from the IBM v7.3 [release notes](https://www.ibm.com/able/requirements/release-notes/) (WCAG 2.1 criteria were added in v7.1, WCAG 2.2 in v7.3). Address these in later release phases.

| # | Requirement | IBM Pace Level |
|---|-------------|:--------------:|
| 1.3.4 | Orientation | 2 |
| 1.4.11 | Non-text Contrast | 2 |
| 1.4.13 | Content on Hover or Focus | 2 |
| 2.4.11 | Focus Not Obscured (Minimum) *(WCAG 2.2)* | 2 |
| 2.5.1 | Pointer Gestures | 2 |
| 2.5.3 | Label in Name | 2 |
| 2.5.4 | Motion Actuation | 2 |
| 2.5.7 | Dragging Movements *(WCAG 2.2)* | 2 |
| 2.5.8 | Target Size (Minimum) *(WCAG 2.2)* | 2 |
| 4.1.3 | Status Messages | 2 |
| 1.3.5 | Identify Input Purpose | 3 |
| 1.4.12 | Text Spacing | 3 |
| 2.1.4 | Character Key Shortcuts | 3 |
| 2.5.2 | Pointer Cancellation | 3 |
| 3.2.6 | Consistent Help *(WCAG 2.2)* | 3 |
| 3.3.7 | Redundant Entry *(WCAG 2.2)* | 3 |
| 3.3.8 | Accessible Authentication (Minimum) *(WCAG 2.2)* | 3 |

> **Media (1.2.x)** applies only to prerecorded/live audio and video, which this UI does not currently ship. For completeness: captions (1.2.2 Prerecorded, 1.2.4 Live) are IBM Level 1, while audio-only/video-only alternatives and audio descriptions (1.2.1, 1.2.3, 1.2.5) are Level 3.

---

### Section 508 (Software-specific)

> **Note:** These Section 508 software requirements target non-web software and are tracked separately from the WCAG pace levels above (they are not assigned a Level 1/2/3 pace). For a web UI they are largely satisfied by **4.1.2 Name, Role, Value**.

These apply to non-web software and desktop/mobile applications:

| # | Requirement | Key Rule |
|---|-------------|----------|
| 502.2.1 | User Control of Accessibility Features | Platform accessibility settings (contrast, font size) must remain user-controllable |
| 502.2.2 | No Disruption of Accessibility Features | Apps must not override OS accessibility features or keyboard shortcuts |
| 502.3.1 | Object Information | All UI objects must expose role, state, name, boundary, and description via platform APIs |
| 502.3.2 | Modification of Object Information | User-settable states/properties must be settable programmatically via AT |
| 502.3.3 | Row, Column, and Headers | Data tables must programmatically expose row/column headers |
| 502.3.4 | Values | Current values and allowed ranges must be programmatically available |
| 502.3.5 | Modification of Values | AT must be able to set values in interactive controls |

---

## Engineering Implementation Guidance

> These are practical implementation patterns. Most support Level 1 criteria; a few support criteria that IBM paces at Level 2/3 (tagged inline) and are included so the patterns stay in one place.

### HTML/Semantic Structure

```html
<!-- GOOD: Semantic structure -->
<main>
  <h1>Page Title</h1>
  <nav aria-label="Primary navigation">...</nav>
  <section aria-labelledby="section-heading">
    <h2 id="section-heading">Section Name</h2>
  </section>
</main>
<footer>...</footer>

<!-- GOOD: Proper form labels -->
<label for="email">Email address</label>
<input id="email" type="email" autocomplete="email" required aria-describedby="email-error" />
<span id="email-error" role="alert">Please enter a valid email address.</span>
```

### Color Contrast

```
Body text:        contrast ≥ 4.5:1   (1.4.3 — Level 1)
Large text:       contrast ≥ 3:1    (1.4.3 — Level 1; ≥18pt regular or ≥14pt bold)
UI components:    contrast ≥ 3:1    (1.4.11 — Level 2; borders, icons, focus rings)
Disabled states:  exempt
Logos/brand:      exempt
```

**Recommended tools:** [IBM Equal Access Checker](https://www.ibm.com/able/toolkit/tools/) (browser extension for Chrome/Firefox), axe DevTools, Colour Contrast Analyser.

### Focus Management

```css
/* NEVER do this without a visible replacement */
:focus { outline: none; }

/* DO this instead */
:focus-visible {
  outline: 2px solid #0f62fe; /* IBM Blue — meets 3:1 contrast */
  outline-offset: 2px;
}
```

```javascript
// When opening a modal, move focus to the first focusable element
dialog.addEventListener('open', () => {
  dialog.querySelector('button, [href], input, [tabindex]').focus();
});

// Trap focus inside the modal while open
// Release focus and return it to the trigger element on close
```

### Keyboard Navigation

All custom interactive components must support standard key interactions:

| Component | Keys Required |
|-----------|--------------|
| Button | `Enter`, `Space` |
| Link | `Enter` |
| Checkbox | `Space` |
| Radio group | Arrow keys within group, `Tab` to move away |
| Select/Listbox | Arrow keys, `Home`, `End`, `Enter` |
| Dialog/Modal | `Escape` to close, focus trap |
| Tabs | Arrow keys to switch tabs |
| Tree/Menu | Arrow keys, `Home`, `End`, `Escape` |

### ARIA Usage

```html
<!-- Live regions for status messages -->
<div role="status" aria-live="polite">File uploaded successfully.</div>
<div role="alert" aria-live="assertive">Error: Session expired.</div>

<!-- Custom buttons with meaningful labels -->
<button aria-label="Close dialog">×</button>
<button aria-expanded="false" aria-controls="menu-id">Menu</button>

<!-- Icon-only buttons always need accessible names -->
<button aria-label="Search">
  <svg aria-hidden="true" focusable="false">...</svg>
</button>

<!-- Loading states -->
<button aria-disabled="true" aria-busy="true">Saving...</button>
```

### Images and Media

```html
<!-- Meaningful image -->
<img src="chart.png" alt="Bar chart showing Q4 revenue increased 30% YoY" />

<!-- Decorative image -->
<img src="divider.png" alt="" role="presentation" />

<!-- Complex image with long description -->
<figure>
  <img src="architecture.png" alt="System architecture" aria-describedby="arch-desc" />
  <figcaption id="arch-desc">
    Three-tier system: frontend React app calls REST API, which connects to PostgreSQL database.
  </figcaption>
</figure>
```

### Touch / Pointer Targets *(supports 2.5.8 Target Size — IBM Level 2)*

```css
/* Ensure all interactive elements meet 24×24px minimum */
button,
a,
[role="button"],
input[type="checkbox"],
input[type="radio"] {
  min-width: 24px;
  min-height: 24px;
}

/* Preferred: 44×44px for comfortable mobile interaction */
.btn-touch {
  min-width: 44px;
  min-height: 44px;
}
```

### Text Spacing Resilience *(supports 1.4.12 Text Spacing — IBM Level 3)*

Your layouts must not break when users apply these overrides via browser/OS:

```css
/* Your CSS must gracefully handle ALL of these applied simultaneously */
line-height: 1.5 !important;
letter-spacing: 0.12em !important;
word-spacing: 0.16em !important;
/* paragraphs: 2× font-size spacing */
```

Test by injecting the [WCAG 1.4.12 bookmarklet](https://www.html5accessibility.com/tests/tsbookmarklet.html) to verify no content is clipped or overlapping.

---

## Testing Tools

| Tool | Use |
|------|-----|
| [IBM Equal Access Checker](https://www.ibm.com/able/toolkit/tools/) | Automated browser scan (Chrome/Firefox extension) |
| [axe DevTools](https://www.deque.com/axe/) | Automated accessibility auditing |
| NVDA + Firefox | Screen reader testing (Windows) |
| VoiceOver + Safari | Screen reader testing (macOS/iOS) |
| TalkBack + Chrome | Screen reader testing (Android) |
| Colour Contrast Analyser | Manual color contrast checking |
| Keyboard-only navigation | Manual tab/arrow-key walkthrough |

---

## Development Workflow

1. **Design phase:** Confirm color contrast, touch targets, focus states, and information hierarchy meet Level 1 before handoff.
2. **Development phase:** Use semantic HTML first; add ARIA only when no native element exists.
3. **Component completion:** Run IBM Equal Access Checker (or axe) — aim for zero violations.
4. **Pull request:** Include an accessibility section in your PR description noting what was verified.
5. **Before release:** Conduct a manual keyboard walkthrough and brief screen reader test on critical flows.

### IBM Automated Checker Integration (CI)

```bash
# Install the IBM accessibility-checker
npm install --save-dev accessibility-checker

# Run against a URL
npx achecker http://localhost:3000
```

```javascript
// Jest/Playwright integration example
const aChecker = require('accessibility-checker');

test('Home page has no accessibility violations', async () => {
  const results = await aChecker.getCompliance('http://localhost:3000', 'home-page');
  expect(aChecker.assertCompliance(results)).toBe(0);
});
```

---

## New in WCAG 2.2 (IBM v7.3)

Six new criteria added — all required as of October 2024. None are Level 1; they appear in [Deferred to Level 2 & Level 3](#deferred-to-level-2--level-3) above:

| Criterion | Summary | IBM Pace Level |
|-----------|---------|----------------|
| **2.4.11** Focus Not Obscured (Minimum) | Focused element must not be fully hidden by sticky UI | 2 |
| **2.5.7** Dragging Movements | Drag actions must have a single-pointer alternative | 2 |
| **2.5.8** Target Size (Minimum) | Touch targets must be at least 24×24 CSS px | 2 |
| **3.2.6** Consistent Help | Help mechanisms appear in same location across pages | 3 |
| **3.3.7** Redundant Entry | Don't re-ask for already-provided info in same session | 3 |
| **3.3.8** Accessible Authentication (Minimum) | Allow paste in login fields; support password managers | 3 |

> **Note:** 4.1.1 Parsing has been removed from WCAG 2.2 and is no longer a requirement in IBM v7.3.

---

## Common Failures to Avoid

| ❌ Failure | ✅ Fix |
|-----------|--------|
| `<div>` or `<span>` used as a button without keyboard/ARIA support | Use `<button>` or add `role="button"` + `tabindex="0"` + keyboard handlers |
| `alt=""` on meaningful images | Write a descriptive alt that conveys the image's purpose |
| `placeholder` used as the only label for an input | Add a visible `<label>` element; use placeholder as supplemental hint only |
| Color alone indicates required fields or errors | Add an asterisk (*), icon, or text label alongside color |
| Focus outline removed globally in CSS | Keep outline; style it to match design system |
| Modal opens without moving focus inside | On open, focus the first element or the modal's heading |
| Modal closes without returning focus to trigger | Track the trigger element and `focus()` it on close |
| `aria-label` that doesn't contain visible button text | Ensure aria-label starts with the visible text (e.g., `aria-label="Save document"` for a button labeled "Save") |
| `role="alert"` misused for non-urgent messages | Use `role="status"` with `aria-live="polite"` for non-urgent updates |
| Links that say "Click here" or "Learn more" without context | Describe the destination: "Learn more about pricing plans" |

---

## References

- [IBM Equal Access Toolkit](https://www.ibm.com/able/toolkit/)
- [IBM Accessibility Requirements v7.3](https://www.ibm.com/able/requirements/requirements/?version=v7_3)
- [IBM Accessibility Checker](https://www.ibm.com/able/toolkit/tools/)
- [WCAG 2.2 Understanding Docs](https://www.w3.org/WAI/WCAG22/Understanding/)
- [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
- [IBM Decision Trees for WCAG 2.2](https://www.ibm.com/able/toolkit/)
