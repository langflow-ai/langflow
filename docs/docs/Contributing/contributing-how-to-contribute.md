---
title: Contribute to Langflow
slug: /contributing-how-to-contribute
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This guide is intended to help you start contributing to Langflow.
As an open-source project in a rapidly developing field, Langflow welcomes contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

To contribute code or documentation to this project, follow the [fork and pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) workflow.

## Install Langflow from source

Install Langflow from source by forking the repository, and then set up your development environment using Make.

### Prerequisites

* [uv](https://docs.astral.sh/uv/getting-started/installation/) version 0.4 or later
* [Node.js](https://nodejs.org/en/download/package-manager)
* [Make](https://www.gnu.org/software/make/#documentation)

:::tip Windows
For Windows installations, you don't need need Make, and you can find [Windows scripts](https://github.com/langflow-ai/langflow/tree/main/scripts/windows) in the Langflow repository.
:::

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

If you're not developing, but want to run Langflow from source after cloning the repo, run the following commands.

<Tabs groupId="os">
  <TabItem value="macOS/Linux" label="macOS/Linux" default>

    1. To run Langflow from source, run the following command:
    ```bash
    make run_cli
    ```

    This command does the following:
    - Installs frontend and backend dependencies
    - Builds the frontend static files
    - Starts the application with default settings

    The Langflow frontend is available at `http://localhost:7860/`.

  </TabItem>
  <TabItem value="Windows" label="Windows">

    To run Langflow from source on Windows, you can use the Langflow project's included scripts, or run the commands in the terminal.

    1. To run Langflow with the included scripts, navigate to the `scripts/windows` directory.
    Two scripts are available to install and start Langflow.

    2. Run Langflow with one of the scripts.

    <Tabs groupId="windows-shell">
      <TabItem value="Windows CMD" label="Windows CMD" default>

        To install and start Langflow with a Windows Batch file, double-click `build_and_run.bat`.

      </TabItem>
      <TabItem value="Powershell" label="Powershell">

        To install and start Langflow with the Powershell script, run:

            ```ps
            .\build_and_run.ps1
            ```

      </TabItem>
    </Tabs>

    **Alternatively**, to run Langflow from source with the Windows Command Line or Powershell, do the following.

    <Tabs groupId="windows-shell">
      <TabItem value="Windows CMD" label="Windows CMD" default>

        1. Run the following commands to build the Langflow frontend.
        ```
        cd src/frontend && npm install && npm run build && npm run start
        ```

        2. Copy the contents of the built `src/frontend/build` directory to `src/backend/base/langflow/frontend`.

        3. To start Langflow, run the following command.
        ```
        uv run langflow run
        ```

        The frontend is served at http://localhost:7860.

      </TabItem>
      <TabItem value="Powershell" label="Powershell">

        1. Run the following commands to build the Langflow frontend.
        ```
        cd src/frontend
        npm install
        npm run build
        npm run start
        ```

        2. Copy the contents of the built `src/frontend/build` directory to `src/backend/base/langflow/frontend`.

        3. To start Langflow, run the following command.
        ```
        uv run langflow run
        ```

        The frontend is served at http://localhost:7860.

      </TabItem>
    </Tabs>

  </TabItem>
</Tabs>

### Set up your Langflow development environment

<Tabs groupId="os">
  <TabItem value="macOS/Linux" label="macOS/Linux" default>

1. To set up the Langflow development environment, run the following command:
    ```bash
    make init
    ```

    This command sets up the development environment by doing the following:
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

    The frontend is served at `http://localhost:7860`.

    The `make backend` and `make frontend` commands automatically install dependencies, so you don't need to run install commands separately.

3. Optional: Install pre-commit hooks to help keep your changes clean and well-formatted. `make init` installs pre-commit hooks automatically.

    ```bash
    uv sync
    uv run pre-commit install
    ```

    :::note
    With pre-commit hooks installed, you need to use `uv run git commit` instead of `git commit` directly.
    :::

4. To test your changes, run `make lint`, `make format`, and `make unit_tests` before pushing to the repository.
To run all tests, including unit tests, integration tests, and coverage, run `make tests`.

  </TabItem>
  <TabItem value="Windows" label="Windows">

Since Windows does not include `make`, building and running Langflow from source uses `npm` and `uv`.

To set up the Langflow development environment, run the frontend and backend in separate terminals.

1. To run the frontend, run the following commands.

    ```bash
    cd src/frontend
    npm install
    npm run start
    ```

2. To run the backend, run the following command.

    ```bash
    uv run langflow run --backend-only
    ```

The frontend is served at `http://localhost:7860`.

  </TabItem>
</Tabs>

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
yarn install
yarn start
```

The documentation is available at `localhost:3000`.
The Markdown content files are located in the `langflow/docs/docs` folder.

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