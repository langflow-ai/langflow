---
title: Install custom dependencies
slug: /install-custom-dependencies
---

To install custom dependencies in your Langflow environment, add them with your package manager.

## Create a virtual environment for local testing

When testing locally, use a virtual environment to isolate your dependencies and prevent conflicts with other Python projects.

For example, if you want to experiment with `matplotlib` with Langflow:

```bash
# Create and activate a virtual environment
uv venv YOUR_LANGFLOW_VENV
source YOUR_LANGFLOW_VENV/bin/activate

# Install langflow and your additional dependency
uv add langflow matplotlib
```

## Add dependencies to the Langflow project

When contributing to Langflow itself, add dependencies to the project's configuration. Langflow uses a workspace with two packages:

* The `main` package (root level): For end-user features and main application code
* The `base` package (in `src/backend/base`): For core functionality and shared code

Dependencies can be added in different groups:

* Regular dependencies: Core functionality needed to run the package
* Development dependencies: Tools for testing, linting, or debugging are added in the `[dependency-groups.dev]` section
* Optional dependencies: Features that users can optionally install are added in the`[project.optional-dependencies]`

There are three ways to add a package using make commands:

1. Add to main package dependencies (for end-user features):
```bash
make add main="matplotlib"
```

2. Add to development tools (for testing, linting, debugging):
```bash
make add devel="matplotlib"
```

3. Add to base package dependencies (for core functionality):
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

Or as an optional dependency:

```
[project.optional-dependencies]
plotting = [
    "matplotlib>=3.8.0",
]
```

The `make` commands add the dependency with `uv add` and update the `uv.lock` file in the appropriate location.
