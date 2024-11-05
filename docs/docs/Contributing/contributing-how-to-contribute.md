---
title: How to contribute?
sidebar_position: 1
slug: /contributing-how-to-contribute
---

# How to contribute to Langflow

This guide is intended to help you get started contributing to Langflow.
As an open-source project in a rapidly developing field, we are extremely open
to contributions, whether it be in the form of a new feature, improved infra, or better documentation.

To contribute to this project, please follow the [fork and pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) workflow.

## Prerequisites

- [uv(>=0.4)](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js](https://nodejs.org/en/download/package-manager)

## Contribute code

Develop Langflow locally with [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js](https://nodejs.org/en/download/package-manager).

### Clone the Langflow Repository

1. Navigate to the [Langflow GitHub repository](https://github.com/langflow-ai/langflow) and click **Fork**.

2. Add the new remote to your local repository on your local machine:

```bash
git remote add fork https://github.com/<your_git_username>/langflow.git
```

### Prepare the development environment

1. Create development hooks.

```bash
make init
```

This command sets up the development environment by installing backend and frontend dependencies, building the frontend static files, and initializing the project. It runs `make install_backend`, `make install_frontend`, `make build_frontend`, and finally `uv run langflow run` to start the application.

2. Run `make lint`, `make format`, and `make unit_tests` before pushing to the repository.

### Debug

The repo includes a `.vscode/launch.json` file for debugging the backend in VSCode, which is a lot faster than debugging with Docker compose. To debug Langflow with the `launch.json` file in VSCode:

1. Open Langflow in VSCode.
2. Press Ctrl+Shift+D (or Cmd+Shift+D on Mac) to open the Run and Debug view.
3. Choose a configuration from the dropdown at the top (for example, "Debug Backend").
4. Click the green play button or press F5 to start debugging.
5. This allows you to quickly debug different parts of your application, like the backend, frontend, or CLI, directly from VSCode.

### Run Langflow locally (Poetry and Node.js)

Run Langflow locally by cloning the repository and installing the dependencies. We recommend using a virtual environment like venv or conda to isolate dependencies.

Before you begin, ensure you have [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js](https://nodejs.org/en/download/package-manager) installed.

1. In the repository root, install the dependencies and start the development server for the backend:

```bash
make backend
```

2. Install dependencies and start the frontend:

```bash
make frontend
```

## Contribute documentation

The documentation is built using [Docusaurus](https://docusaurus.io/). To run the documentation locally, run the following commands:

```bash
cd docs
npm install
npm run start
```

The documentation will be available at `localhost:3000` and all the files are located in the `docs/docs` folder.

## Open a pull request

Once you wrote and manually tested your change, you can start sending the patch to the main repository.

- Open a new GitHub pull request with the patch against the `main` branch.
- Ensure the PR title follows semantic commits conventions.
  - For example, `feat: add new feature`, `fix: correct issue with X`.
- Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.


## Report bugs or suggest improvements

Our [GitHub issues](https://github.com/langflow-ai/langflow/issues) page is kept up to date
with bugs, improvements, and feature requests. There is a taxonomy of labels to help
with sorting and discovery of issues of interest. [See this page](https://github.com/langflow-ai/langflow/labels) for an overview of
the system we use to tag our issues and pull requests.

If you're looking for help with your code, consider posting a question on the
[GitHub Discussions board](https://github.com/langflow-ai/langflow/discussions). Please
understand that we won't be able to provide individual support via email. We
also believe that help is much more valuable if it's **shared publicly**,
so that more people can benefit from it.

Since the Discussions board is public, please follow this guidance when posting your code questions.

1. When describing your issue, try to provide as many details as possible. What exactly goes wrong? _How_ is it failing? Is there an error? "XY doesn't work" usually isn't that helpful for tracking down problems. Always remember to include the code you ran and if possible, extract only the relevant parts and don't just dump your entire script. This will make it easier for us to reproduce the error.

2. When you include long code, logs, or tracebacks, wrap them in `<details>` and `</details>` tags. This [collapses the content](https://developer.mozilla.org/en/docs/Web/HTML/Element/details) so the contents only becomes visible on click, making the issue easier to read and follow.