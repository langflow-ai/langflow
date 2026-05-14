---
name: langflow-ux-change
description: Use when making user-visible changes — edits under `src/frontend/` that affect rendered output (components, copy, layout, icons, styles), or edits to a component's `display_name`, `description`, or `icon` in any Python file. Surfaces the consult-a-maintainer expectation, Playwright/test obligations, formatting, and the project's design philosophy.
---

# UX Change

Fires on user-visible changes. UX decisions in langflow are agreed with a maintainer or decision-maker before shipping — not after.

## Fires on

- Anything under `src/frontend/` that changes rendered output: component code, copy, layout, styles, icons.
- Edits to a component's `display_name`, `description`, or `icon` in any Python file under `src/backend/base/langflow/components/`.

## Before making the change

Ask the contributor:

> "This is user-visible. Has the change been agreed with a maintainer or decision-maker? UX decisions go through review before shipping, not after."

If no agreement yet, help the contributor frame the question (what's changing, why, what alternatives were considered, what the user impact is) and pause until they have a green light.

## When making the change

- **Design philosophy** (Ultrahand): simple primitives with one clear purpose, visible connections, consistent predictable behavior, emergent complexity from composition — not from complex parts. Pre-built "vehicles" are fine as examples but users should be able to break them apart.
- **Tests** — run and update Playwright e2e tests: `make tests_frontend`. Jest unit tests: `make test_frontend`.
- **Formatting** — `make format_frontend` before staging.
- **Custom icons** — create the SVG in `src/frontend/src/icons/YourIcon/`, export with `forwardRef` and `isDark` prop support, register in `lazyIconImports.ts`, then set `icon = "YourIcon"` in the Python component.
- **Stack reminder** — React 19, TypeScript, Vite, Zustand for state, @xyflow/react for graph, Tailwind for styles.

## If the change renames identifiers

Editing `display_name`, `description`, or `icon` is fine — those are not identifiers. But if the change involves renaming a component class, input `name=`, or output `name=`, route through [langflow-breaking-change-gate](../langflow-breaking-change-gate/SKILL.md).

## Scope discipline

Touch only what the task requires. Don't reformat unrelated files, don't refactor adjacent components, don't add features that weren't asked for.
