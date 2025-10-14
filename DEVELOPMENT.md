# Setting up a Development Environment

This document details how to set up a local development environment that will allow you to contribute changes to the project!

## Base Requirements

- The project is hosted on GitHub, so you need an account there (and if you are reading this, you likely do!)
- An IDE such as Microsoft VS Code IDE https://code.visualstudio.com/

## Set up Git Repository Fork

You will push changes to a fork of the Langflow repository, and from there create a Pull Request into the project repository.

Fork the [Langflow GitHub repository](https://github.com/langflow-ai/langflow/fork), and follow the instructions to create a new fork.

On your new fork, click the "<> Code" button to get a URL to [clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) using your preferred method, and clone the repository; for example using `https`:

```bash
git clone https://github.com/<your username>/langflow.git
```

Finally, add the Project repository as `upstream`:

```bash
cd langflow
git remote add upstream https://github.com/langflow-ai/langflow.git
git remote set-url --push upstream no_push
```

> [!TIP] > **Windows/WSL Users**: You may find that files "change", specifically the file mode e.g. "changed file mode 100755 → 100644". You can workaround this problem with `git config core.filemode false`.

## Set up Environment

There are two options available to you: use your local environment with `make` commands (recommended for macOS and Linux), or use a Development Container ("[Dev Container](https://containers.dev/)") which is recommended for Windows users.

### Option 1 (Recommended): Use Your Local Environment

Install Pre-Requisites:

- **Operating System**: macOS or Linux; Windows users should use WSL or consider Option 2 (Dev Container).
- **`git`**: The project uses the ubiquitous `git` tool for change control.
- **`make`**: The project uses `make` to coordinate packaging.
- **`uv`**: This project uses `uv` (`>=0.4`), a Python package and project manager from Astral. Install instructions at https://docs.astral.sh/uv/getting-started/installation/.
- **`npm`**: The frontend files are built with Node.js (`v22.12 LTS`) and `npm` (`v10.9`). Install instructions at https://nodejs.org/en/download/package-manager.
  - Windows (WSL) users: ensure `npm` is installed within WSL environment; `which npm` should resolve to a Linux location, not a Windows location.

### Option 2: Use a Dev Container (Recommended for Windows)

Open this repository as a Dev Container per your IDEs instructions.

A preconfigured `.devcontainer` is included in this repository and is auto-detected by supported IDEs.

#### Microsoft VS Code

To start the preconfigured `.devcontainer` with the VS Code Dev Containers extension, from the Command Palette, run the Dev Containers: Reopen in Container command.

- See [Developing inside a Container](https://code.visualstudio.com/docs/devcontainers/containers)
- You may also find it helpful to [share `git` credentials](https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials) with the container

### Initial Environment Validation

To setup and validate the initial environment, run:

```bash
make init
```

This sets up the development environment by installing backend and frontend dependencies and installing pre-commit hooks. It runs `make install_backend`, `make install_frontend`, and `uvx pre-commit install`.

> [!TIP]
> If you want to quickly run Langflow from source without setting up the full development environment, you can use `make run_cli` instead. This command installs dependencies, builds the frontend, and starts the application in one step.

After running `make init`, you have two options for running Langflow:

- Use `make run_cli` to build and run the application immediately.
- Continue to the next section to run Langflow in Development mode.

### Troubleshooting frontend build issues

If you encounter frontend build problems or are upgrading from an older version of Langflow, run `make run_clic` once.

```bash
make run_clic
```

This command cleans the build cache and rebuilds everything from scratch, which resolves most frontend-related issues when switching between versions.

## Complete development environment setup

There are some other steps to consider before you are ready to begin development.

### Optional pre-commit hooks

Pre-commit hooks will help keep your changes clean and well-formatted.

> [!NOTE]
> With these installed, the `git commit` command needs to run within the Python environment; your syntax needs to change to `uv run git commit`.

Install pre-commit hooks by running the following commands:

```bash
uv sync
uv run pre-commit install
```

## Run Langflow in Development mode

With the above validation, you can now run the backend (FastAPI) and frontend (Node) services in a way that will "hot-reload" your changes. In this mode, the FastAPI server requires a Node.js server to serve the frontend pages rather than serving them directly.

> [!NOTE]
> You will likely have multiple terminal sessions active in the normal development workflow. These will be annotated as _Backend Terminal_, _Frontend Terminal_, _Documentation Terminal_, and _Build Terminal_.

### Debug Mode

A debug configuration is provided for VS Code users: this can be launched from the Debug tab (the backend debug mode can be launched directly via the F5 key). You may prefer to start services in this mode. You may still want to read the following subsections to understand expected console output and service readiness.

### Start the Backend Service

The backend service runs as a FastAPI service on Python, and is responsible for servicing API requests. In the _Backend Terminal_, start the backend service:

```bash
make backend
```

> [!TIP]
> **Component Development Mode**: By default, Langflow uses a prebuilt component index for fast startup (~10ms). If you're actively developing or modifying components, enable dynamic component loading with `LFX_DEV`:
>
> ```bash
> # Load all components dynamically
> LFX_DEV=1 make backend
>
> # Load only specific component modules (faster dev workflow)
> LFX_DEV=mistral,openai,anthropic make backend
> ```
>
> The list mode is particularly useful when working on specific integrations, as it significantly speeds up startup time by only loading the components you need.
>
> Without `LFX_DEV`, component changes require rebuilding the index:
>
> ```bash
> uv run python scripts/build_component_index.py
> ```

You will get output similar to:

```
INFO:     Will watch for changes in these directories: ['/home/phil/git/langflow']
INFO:     Loading environment from '.env'
INFO:     Uvicorn running on http://0.0.0.0:7860 (Press CTRL+C to quit)
INFO:     Started reloader process [22330] using WatchFiles
Starting Langflow ...
```

At which point you can check http://localhost:7860/health in a browser; when the backend service is ready it will return a document like:

```json
{ "status": "ok" }
```

### Start the Frontend Service

The frontend (User Interface) is, in shipped code (i.e. via `langflow run`), statically-compiled files that the backend FastAPI service provides to clients via port `7860`. In development mode, these are served by a Node.js service on port `3000`. In the _Frontend Terminal_, start the frontend service:

```bash
make frontend
```

You will get output similar to:

```
  VITE v5.4.11  ready in 552 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

At this point, you can navigate to http://localhost:3000/ in a browser and access the Langflow User Interface.

### Build and display documentation

> [!IMPORTANT]
> If you're using a dev container, run the documentation build from outside the container in your host terminal, not from within the dev container workspace. The documentation build may not work properly when run inside the dev container.

If you are contributing changes to documentation (always welcome!), these are built using [Docusaurus](https://docusaurus.io/) and served separately, also using Node.js.

In the terminal, from the project root directory, run the following:

```bash
cd docs
yarn install
yarn start
```

If the frontend service is running on port `3000` you might be prompted `Would you like to run the app on another port instead?`, in which case answer "yes". You will get output similar to:

```
[SUCCESS] Docusaurus website is running at: http://localhost:3001/
```

Navigate to http://localhost:3001/ in a browser and view the documentation. Documentation updates will be visible as they are saved, though sometimes the browser page will also need to be refreshed.

## Adding or Modifying a Component

Components reside in folders under `src/backend/base/langflow`, and their unit tests under `src/backend/base/tests/unit/components`.

> [!IMPORTANT]
> **Component Development Mode**: When actively developing components, make sure to run the backend with `LFX_DEV=1` to enable live reloading:
>
> ```bash
> LFX_DEV=1 make backend
> ```
>
> This ensures your component changes are immediately reflected without needing to rebuild the component index.

### Adding a Component

Add the component to the appropriate subdirectory, and add the component to the `__init__.py` file (alphabetical ordering on the `import` and the `__all__` list). Assuming the backend and frontend services are running **with `LFX_DEV=1`**, the backend service will restart as these files are changed. The new component will be visible after the backend is restarted, _*and*_ after you hit "refresh" in the browser.

> [!TIP]
> It is faster to copy-paste the component code from your editor into the UI _without_ saving in the source code in the editor, and once you are satisfied it is working you can save (restarting the backend) and refresh the browser to confirm it is present.

You should try to add a unit test for your component, though templates and best practices for this is a work in progress. At the very least, please create a Markdown file in the unit test subdirectory associated with your component (create the directory if not present), with the same filename as the component but with a `.md` extension. Within this should be the steps you have taken to manually test the component.

### Modifying a Component

Modifying a component is much the same as adding a component: it is generally easier to make changes in the UI and then save the file in the repository. Please be sure to review and modify unit tests; if there is not a unit test for the component, the addition of one that at least covers your changes would be much appreciated!

> [!NOTE]
> If you have an old version of the component on the canvas when changes are saved and the backend service restarts, that component should show "Updates Available" when the canvas is reloaded (i.e. a browser refresh). [Issue 5179](https://github.com/langflow-ai/langflow/issues/5179) indicates this behavior is not consistent, at least in a development setting.

### Component Index

When you're done modifying components and ready to commit, the component index will be automatically updated by CI when you create a pull request. The GitHub Actions workflow will detect changes to components and rebuild the index, committing it to your PR branch if needed.

If you want to manually rebuild the index locally for testing:

```bash
uv run python scripts/build_component_index.py
```

## Building and Testing Changes

When you are ready to commit, and before you commit, you should consider the following:

- `make lint`
- `make format_backend` and `make format_frontend` will run code formatters on their respective codebases
- `make unit_tests` runs the (backend) unit tests (see "Quirks" below for more about testing).

Once these changes are ready, it is helpful to rebase your changes on top of `upstream`'s `main` branch, to ensure you have the latest code version! Of course if you have had to merge changes into your component you may want to re-lint/format/unit_test.

As a final validation, stop the backend and frontend services and run `make init`; this will do a clean build and the UI should be available in port `7860` (as it has invoked `langflow run`). Open a **new** browser tab to this service and do a final check of your changes by adding your new/modified component onto the canvas from the Components list.

## Committing, Pushing, and Pull Requests

Once you are happy your changes are complete, commit them and push the changes to your own fork (this will be `origin` if you followed the above instructions). You can then raise a Pull Request into the Project repository on the GitHub interface or within your IDE.

> [!TIP]
> Remember that if you have pre-commit hooks enabled, you need to run the `git` command as `uv run git` to activate the necessary Python environment!

## Some Quirks!

You may observe some quirky things:

### Testing

- Backend test `src/backend/tests/unit/test_database.py` can fail when running with `make tests` but passes when running manually
  - You can validate this by running the test cases sequentially: `uv run pytest src/backend/tests/unit/test_database.py`
- There are some other test targets: `integration_tests`, `coverage`, `tests_frontend` but these require additional setup not covered in this document.

### Files That Change

There are some files that change without you having made changes:

- Files in `src/backend/base/langflow/initial_setup/starter_projects` modify after `langflow run`; these are formatting changes. Feel free to commit (or ignore) them.
- `uv.lock` and `src/frontend/package-lock.json` files can be modified by `make` targets; changes should not be committed by individual contributors.
  - You can exclude these from consideration in git: `git update-index --assume-unchanged uv.lock src/frontend/package-lock.json`
  - You can re-include these from consideration in git: `git update-index --no-assume-unchanged uv.lock src/frontend/package-lock.json`
