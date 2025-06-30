---
title: Contribute to Langflow
slug: /contributing-how-to-contribute
---

This guide is intended to help you start contributing to Langflow.
As an open-source project in a rapidly developing field, Langflow welcomes contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

To contribute code or documentation to this project, follow the [fork and pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) workflow.

## Install Langflow from source

Install Langflow from source by forking the repository, and then set up your development environment using Make.

### Prerequisites

* [uv](https://docs.astral.sh/uv/getting-started/installation/) version 0.4 or later
* [Node.js](https://nodejs.org/en/download/package-manager)
* [Make](https://www.gnu.org/software/make/#documentation)

### Clone the Langflow repository

1. Fork the [Langflow GitHub repository](https://github.com/langflow-ai/langflow).

2. Add the new remote to your local repository on your local machine:
```bash
git remote add FORK_NAME https://github.com/GIT_USERNAME/langflow.git
```
Replace the following:
* `FORK_NAME`: A name for your fork of the repository
* `GIT_USERNAME`: Your Git username

### Run Langflow from source

If you're not developing, but want to run Langflow from source after cloning the repo, run:

```bash
make run_cli
```

This command:
- Installs frontend and backend dependencies
- Builds the frontend static files
- Starts the application with default settings

The `make run_cli` command allows you to configure the application such as logging level, host, port, and environment variables.

For example, this command starts Langflow with custom settings for the logging level, host binding, and port number, and specifies a custom `.env` file.

```bash
make run_cli log_level=info host=localhost port=8000 env=.env.custom
```

The `make run_cli` command accepts the following parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `log_level` | `debug` | Set the logging level. Options: `debug`, `info`, `warning`, `error`, `critical` |
| `host` | `0.0.0.0` | The host address to bind the server to. Use `localhost` or `127.0.0.1` for local-only access. |
| `port` | `7860` | The port number to run the server on. |
| `env` | `.env` | Path to the environment file containing configuration variables. |
| `open_browser` | `true` | Whether to automatically open the browser when starting. Set to `false` to disable. |

### Set up your Langflow development environment

1. To set up the Langflow development environment, run the following command:

```bash
make init
```

This command sets up the development environment by:
- Checking for uv and npm.
- Installing backend and frontend dependencies.
- Installing pre-commit hooks.

2. Run the backend and frontend in separate terminals for development:

```bash
# Run backend in development mode (includes hot reload)
make backend

# In another terminal, run frontend in development mode (includes hot reload)
make frontend
```

The `make backend` and `make frontend` commands automatically install dependencies, so you don't need to run install commands separately.

3. (Optional) Install pre-commit hooks to help keep your changes clean and well-formatted. `make init` installs pre-commit hooks automatically.

```bash
uv sync
uv run pre-commit install
```

:::note
With pre-commit hooks installed, you need to use `uv run git commit` instead of `git commit` directly.
:::

4. To test your changes, run `make lint`, `make format`, and `make unit_tests` before pushing to the repository.
To run all tests, including unit tests, integration tests, and coverage, run `make tests`.

### Debug

The repo includes a `.vscode/launch.json` file for debugging the backend in VSCode, which is faster than debugging with Docker Compose. To debug Langflow with the `launch.json` file in VSCode:

For more information, see the [VSCode documentation](https://code.visualstudio.com/docs/debugtest/debugging#_start-a-debugging-session).

### Additional contribution guides

- [Contribute Bundles](./contributing-bundles.md)
- [Contribute Components](./contributing-components.md)
- [Contribute Tests](./contributing-component-tests.md)
- [Contribute Templates](./contributing-templates.md)

## Contribute documentation

The documentation is built using [Docusaurus](https://docusaurus.io/) and written in [Markdown](https://docusaurus.io/docs/markdown-features).
Contributions should follow the [Google Developer Documentation Style Guide](https://developers.google.com/style).

### Prerequisites

* [Node.js](https://nodejs.org/en/download/package-manager)
* [Yarn](https://yarnpkg.com/)

### Clone the Langflow repository

1. Fork the [Langflow GitHub repository](https://github.com/langflow-ai/langflow).

2. Add the new remote to your local repository on your local machine:
```bash
git remote add FORK_NAME https://github.com/GIT_USERNAME/langflow.git
```
Replace the following:
* `FORK_NAME`: A name for your fork of the repository
* `GIT_USERNAME`: Your Git username

3. From your Langflow fork's root, change directory to the `langflow/docs` folder with the following command:
```bash
cd docs
```

4. To install dependencies and start a local Docusaurus static site with hot reloading, run:
```bash
yarn install && yarn start
```

The documentation will be available at `localhost:3000` and all the files are located in the `/docs` folder.

5. Optional: Run `yarn build` to build the site locally and ensure there are no broken links.

## Open a pull request

To submit a pull request, do the following:

1. Open a new GitHub pull request with your patch against the `main` branch.
2. Ensure the PR title follows semantic commit conventions. For example, features are `feat: add new feature` and fixes are `fix: correct issue with X`.

Some additional guidance on pull request titles:
* Ensure the pull request description clearly describes the problem and solution. If the PR fixes an issue, include a link to the fixed issue in the PR description with `Fixes #1234`.
* Pull request titles appear in Langflow's release notes, so they should explain what the PR does as explicitly as possible.
* Pull requests should strive to fix one thing **only**, and should contain a good description of what is being fixed.

3. A Langflow maintainer will review your pull request and may request changes, so ensure you pay attention to your PRs. Thanks for your contribution!

For more information, see the [Python Developer's Guide](https://devguide.python.org/getting-started/pull-request-lifecycle/index.html#making-good-commits).