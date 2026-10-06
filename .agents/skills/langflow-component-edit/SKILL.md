---
name: langflow-component-edit
description: Use when adding or editing a component under `src/backend/base/langflow/components/` — surfaces the practices an engineer would apply automatically (identifier stability, tests, alphabetical registration, formatting) and routes breaking-shaped edits to the breaking-change gate.
---

# Component Edit

Fires on any edit under `src/backend/base/langflow/components/`. Coaches the contributor through the practices an engineer would apply by reflex.

## If renaming or removing identifiers — stop and route

The following are identifiers stored in users' saved flow files. Any rename or removal is a breaking change and must go through [langflow-breaking-change-gate](../langflow-breaking-change-gate/SKILL.md) before proceeding:

- The component class name.
- Any input's `name=` field.
- Any output's `name=` field.
- Any output's `method=` field.

If the contributor wants a rename for cosmetic reasons, offer the alternative: keep the old name as a deprecation alias, add the new one alongside. Editing the `display_name`, `description`, or `icon` is fine — those are not identifiers.

## For new components

- Inherit from `Component`. Define `display_name`, `description`, `icon`, `inputs`, `outputs`.
- Register in the containing `__init__.py` in alphabetical order.
- Write a test under `src/backend/tests/unit/components/`. Choose the base class:
  - `ComponentTestBaseWithClient` — component needs API access.
  - `ComponentTestBaseWithoutClient` — pure logic.
  Required fixtures: `component_class`, `default_kwargs`, `file_names_mapping`.
- For hot reload during development: `LFX_DEV=1 make backend`.

## Before pushing

- `make format_backend` — ruff format and fixes.
- `make unit_tests` — run the suite (or scope it to the touched component for speed).
- Touched the UI side of the component (icon, display name, description)? Also see [langflow-ux-change](../langflow-ux-change/SKILL.md).

## Scope discipline

Touching only what the task requires. Resist reformatting adjacent code, adding type hints to nearby functions, or "while I'm here" refactors. Match the existing style of the file even if you would write it differently.
