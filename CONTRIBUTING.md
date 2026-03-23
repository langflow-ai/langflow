# How to contribute to Langflow

Thank you for your interest in contributing to Langflow.
This page is the practical entrypoint for first-time contributors.
Use it to choose the right contribution path, the right environment, and the minimum validation to run before you open a pull request.

## Quick start

1. Fork the [Langflow GitHub repository](https://github.com/langflow-ai/langflow).
2. Create a branch in your fork for one focused change.
3. Choose the contribution path and environment below.
4. Run the minimum validation for your change before opening a pull request to `main`.

For deeper setup, development, documentation, and component-specific instructions, use the linked guides in the next sections instead of treating this page as a full manual.

## Choose your contribution path

### Code changes

If you are changing application code, start with [DEVELOPMENT.md](./DEVELOPMENT.md).
Focus on the sections for **Set up Environment**, **Run Langflow in Development mode**, and **Troubleshooting frontend build issues**.
That guide covers the main development path, including `make init`, `make backend`, `make frontend`, `make run_cli`, and `make run_clic`.

### Documentation changes

If you are contributing documentation, start with the [contributor guide](./docs/docs/Contributing/contributing-how-to-contribute.mdx) and go to **Contribute documentation**.
Langflow docs are built with Docusaurus, and the docs contribution guide contains the preview and build workflow.

### Components, bundles, tests, templates

If you are working on a narrower contributor surface such as components, bundles, tests, or templates, use the specialized guides below instead of expanding this page with workflow-specific details.

## Choose your environment

### macOS / Linux

Use [DEVELOPMENT.md](./DEVELOPMENT.md) as the primary path.
This is the main `make`-based development workflow for Langflow contributors.

### Windows

Start with the Windows, Dev Container, or source-run paths in [DEVELOPMENT.md](./DEVELOPMENT.md).
The repository also includes helper scripts under [`scripts/windows`](./scripts/windows), but this entrypoint intentionally does not duplicate those steps.
Installer or Desktop-specific issues are outside the scope of this contributor entrypoint.

## Minimum validation before opening a PR

- For docs-only changes, run the documentation preview or documentation build flow from the docs guide before opening a PR.
- For backend changes, run at least `make unit_tests`.
- For frontend changes, run the affected frontend test or build path before opening a PR.
- For mixed changes, combine the minimum validation for each affected area instead of assuming a full local test run is always required.

Do not copy large command blocks from [DEVELOPMENT.md](./DEVELOPMENT.md) into this page.
Also avoid hard-coding documentation port numbers here, because local docs preview ports can vary by setup.

## Pull request rules

- Open your pull request against `main`.
- Your PR title must follow [semantic commit conventions](https://www.conventionalcommits.org/).
- Keep each pull request focused on one change whenever possible.
- If your PR fixes an issue, include a reference such as `Fixes #1234` in the description.
- PR titles appear in Langflow release notes, so the title should state the change clearly and directly.

## Specialized guides

Use these guides when your contribution area needs repository-specific detail that should not live in this entrypoint:

- [Contribute Bundles](./docs/docs/Contributing/contributing-bundles.mdx)
- [Contribute Components](./docs/docs/Contributing/contributing-components.mdx)
- [Contribute Tests](./docs/docs/Contributing/contributing-component-tests.mdx)
- [Contribute Templates](./docs/docs/Contributing/contributing-templates.mdx)
