---
name: langflow-starter-project-edit
description: Use when editing files under `src/backend/base/langflow/initial_setup/starter_projects/`. Starter projects ship with every new install and shape every new user's first experience. Surfaces JSON validation, component-reference sanity checks, and the consult-a-maintainer expectation for structural changes.
---

# Starter Project Edit

Fires on edits under `src/backend/base/langflow/initial_setup/starter_projects/`.

Starter projects are not strictly breaking — existing users' flows aren't affected by changes here. But these flows ship with every new install and shape every new user's first impression of langflow. Treat them with the same care as documentation.

## Before changing anything

- **For structural changes** (adding/removing components, rewiring connections, changing the project's purpose): consult a maintainer or decision-maker first. These are product decisions.
- **For copy or layout polish**: lighter touch, but still worth surfacing in the PR description.

## When editing

- **Validate the JSON.** A broken starter project JSON breaks every new install.
- **Verify component references.** Every component the project uses must still exist with the same class name, the same input `name=`, and the same output `name=`. A rename upstream silently breaks this file. If a referenced component was renamed (which itself shouldn't happen — see [langflow-breaking-change-gate](../langflow-breaking-change-gate/SKILL.md)), update the references here too.
- **Stay in scope.** Don't "tidy up" other starter projects in the same change.

## Quick sanity check

After editing, load the project locally (`make run_cli` or `LFX_DEV=1 make backend`) and confirm it opens and runs end-to-end. A starter project that fails to load is a regression every new user sees.
