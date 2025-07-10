---
title: Install custom dependencies
slug: /install-custom-dependencies
---

Langflow provides optional dependency groups and support for custom dependencies to extend Langflow functionality.

## Install custom dependencies in Langflow Desktop {#langflow-desktop}

To add dependencies to Langflow Desktop, add an entry for the package to the application's `requirements.txt` file:

    * On macOS, the file is located at `/Users/USER/.langflow/data/requirements.txt`.
    * On Windows, the file is located at `C:\Users\USER\AppData\Roaming\com.Langflow\data\requirements.txt`.

Add the dependency and version to `requirements.txt` on separate lines in the format `PACKAGE==VERSION`, such as `docling==2.40.0`.

Restart Langflow Desktop to install the dependencies.

If you need to change or uninstall custom dependencies. edit the `requirements.txt` file, and then restart Langflow Desktop.

## Install custom dependencies in Langflow OSS

To install your own custom dependencies in your Langflow environment, add them with your package manager.

If you're working within a cloned Langflow repository, add dependencies with `uv add` because there is already a `pyproject.toml` file for uv to reference:

```bash
uv add langflow DEPENDENCY
```

### Install optional dependency groups

Langflow OSS provides optional dependency groups that extend its functionality.

These dependencies are listed in the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L191) file under `[project.optional-dependencies]`.

Install dependency groups using pip's `[extras]` syntax. For example, to install Langflow with the `postgresql` dependency group, enter the following command:

```bash
uv pip install "langflow[postgresql]"
```

To install multiple extras, use commas to separate each dependency group:

```bash
uv pip install "langflow[deploy,local,postgresql]"
```

### Use a virtual environment to test custom dependencies

When testing locally, use a virtual environment to isolate your dependencies and prevent conflicts with other Python projects.

For example, if you want to experiment with `matplotlib` with Langflow:

```bash
# Create and activate a virtual environment
uv venv YOUR_LANGFLOW_VENV
source YOUR_LANGFLOW_VENV/bin/activate

# Install langflow and your additional dependency
uv pip install langflow matplotlib
```

If you're working within a cloned Langflow repository, add dependencies with `uv add` to reference the existing `pyproject.toml` file:

```bash
uv add langflow matplotlib
```

## Add dependencies to the Langflow codebase

When contributing to the Langflow codebase, you might need to add dependencies to Langflow.

Langflow uses a workspace with two packages:

* The `main` package (root level): For end-user features and main application code
* The `base` package (in `src/backend/base`): For core functionality and shared code

Dependencies can be added in different groups:

* Regular dependencies: Core functionality needed to run the package
* Development dependencies: Tools for testing, linting, or debugging are added in the `[dependency-groups.dev]` section
* Optional dependencies: Features that users can optionally install are added in the`[project.optional-dependencies]`

There are three ways to add a package using make commands:

* Add to main package dependencies (for end-user features):
```bash
make add main="matplotlib"
```

* Add to development tools (for testing, linting, debugging):
```bash
make add devel="matplotlib"
```

* Add to base package dependencies (for core functionality):
```bash
make add base="matplotlib"
```

You can also add these dependencies manually to the `pyproject.toml` file:

```
[project]
dependencies = [
    "matplotlib>=3.8.0"
]
```

* Or as an optional dependency:

```
[project.optional-dependencies]
plotting = [
    "matplotlib>=3.8.0",
]
```

The `make` commands add the dependency with `uv add` and update the `uv.lock` file in the appropriate location.