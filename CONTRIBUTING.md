# Contributing to Langflow

This guide is intended to help you start contributing to Langflow.
As an open-source project in a rapidly developing field, Langflow welcomes contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

To contribute code or documentation to this project, follow the [fork and pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) workflow.

## Install Langflow from source

Install Langflow from source by forking the repository, and then set up your development environment using Make.

### Prerequisites

* [uv(>=0.4)](https://docs.astral.sh/uv/getting-started/installation/)
* [Node.js](https://nodejs.org/en/download/package-manager)
* [Make](https://www.gnu.org/software/make/#documentation)

### Clone the Langflow repository

1. Navigate to the [Langflow GitHub repository](https://github.com/langflow-ai/langflow), and then click **Fork**.

2. Add the new remote to your local repository on your local machine:
Replace `YOUR_FORK_NAME` with a name for your fork.
Replace `YOUR_GIT_USERNAME` with your Git username.
```bash
git remote add YOUR_FORK_NAME https://github.com/YOUR_GIT_USERNAME/langflow.git
```

### Set up your Langflow development environment

1. Change your directory to the root of the local Langflow repository:
```bash
cd langflow
```

2. To set up the Langflow development environment, run the following command:
```bash
make init
```

This command sets up the development environment by:
- Checking for uv and npm.
- Installing backend and frontend dependencies.
- Installing pre-commit hooks.

There are two different workflows depending on whether you're a developer or just running Langflow from source.

Developers typically run the backend and frontend separately for development:

```bash
# Run backend in development mode (includes hot reload)
make backend

# In another terminal, run frontend in development mode (includes hot reload)
make frontend
```

The `make backend` and `make frontend` commands automatically install dependencies, so you don't need to run install commands separately.

If you're not developing, but want to run Langflow from source, run:

```bash
make run_cli
```

This command:
- Installs frontend and backend dependencies
- Builds the frontend static files
- Starts the application with default settings

After running `make init` once to set up your environment, you can use `make run_cli` for subsequent runs. The `make run_cli` command allows you to configure the application such as logging level, host, port, and environment variables.

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

4. (Optional) Install pre-commit hooks to help keep your changes clean and well-formatted. `make init` runs this automatically.

```bash
uv sync
uv run pre-commit install
```

Note: With pre-commit hooks installed, you'll need to use `uv run git commit` instead of `git commit` directly.

5. To test your changes, run `make lint`, `make format`, and `make unit_tests` before pushing to the repository.
To run all tests, including unit tests, integration tests, and coverage, run `make tests`.

### Debug

The repo includes a `.vscode/launch.json` file for debugging the backend in VSCode, which is faster than debugging with Docker Compose. To debug Langflow with the `launch.json` file in VSCode:

1. Open Langflow in VSCode.
2. Press **Ctrl+Shift+D** for Windows **or Cmd+Shift+D** for Mac to open the Run and Debug view.
3. From the **Run and Debug** dropdown, choose a debugging configuration.
4. Click the green **Play** button or press F5 to start debugging.

Use `launch.json` to quickly debug different parts of your application, like the backend, frontend, or CLI, directly from VSCode.

## Contribute documentation

The documentation is built using [Docusaurus](https://docusaurus.io/) and written in [Markdown](https://docusaurus.io/docs/markdown-features).

### Prerequisites

* [Node.js](https://nodejs.org/en/download/package-manager)

### Clone the Langflow repository

1. Navigate to the [Langflow GitHub repository](https://github.com/langflow-ai/langflow), and then click **Fork**.

2. Add the new remote to your local repository on your local machine:

```bash
git remote add fork https://github.com/<your_git_username>/langflow.git
```

3. To run the documentation locally, run the following commands:

```bash
cd docs
yarn install
yarn start
```

The documentation will be available at `localhost:3000` and all the files are located in the `/docs` folder.

## Open a pull request

Once you have written and manually tested your changes with `make lint` and `make unit_tests`, open a pull request to send your changes upstream to the main Langflow repository.

1. Open a new GitHub pull request with your patch against the `main` branch.
2. Ensure the PR title follows semantic commit conventions. For example, features are `feat: add new feature` and fixes are `fix: correct issue with X`.
3. A Langflow maintainer will review your pull request. Thanks for your contribution!

Some additional guidance on pull request titles:
* Ensure the pull request description clearly describes the problem and solution. If the PR fixes an issue, include a link to the fixed issue in the PR description with `Fixes #1234`.
* Pull request titles appear in Langflow's release notes, so they should explain what the PR does as explicitly as possible.
* Pull requests should strive to fix one thing **only**, and should contain a good description of what is being fixed.

For more information, see the [Python Developer's Guide](https://devguide.python.org/getting-started/pull-request-lifecycle/index.html#making-good-commits).

## Additional contribution guides

- [Contribute Bundles](./docs/docs/Contributing/contributing-bundles.md)
- [Contribute Components](./docs/docs/Contributing/contributing-components.md)
- [Contribute Tests](./docs/docs/Contributing/contributing-component-tests.md)
- [Contribute Templates](./docs/docs/Contributing/contributing-templates.md)