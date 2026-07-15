# Langflow Core

`langflow-core` is the Langflow application server and web UI packaged with
Langflow's core components only. It does not depend on provider extension
distributions such as `lfx-openai`, `lfx-ibm`, or `lfx-bundles`.

Install and run it with:

```bash
python -m pip install langflow-core
langflow run
```

The `langflow-core` command is an alias for the same launcher:

```bash
langflow-core run
```

For PostgreSQL support, install the optional extra:

```bash
python -m pip install "langflow-core[postgresql]"
```

The distribution depends on `langflow-base[complete]` for Langflow's API,
services, persistence, web UI, and service-level optional dependencies. It also
includes the `lfx` execution engine transitively through `langflow-base`. It
does not install any distribution whose name starts with `lfx-`.

Provider components remain independently installable. For example, add OpenAI
components to an existing core environment with:

```bash
python -m pip install lfx-openai
```

Use `langflow` instead when you want Langflow's curated provider bundle set by
default. Treat `langflow` and `langflow-core` as alternative distributions;
both expose the `langflow` command and should not be co-installed.

Use `langflow-base` when you need lower-level control over Langflow service
extras, or `lfx` when you need the headless execution engine without the
Langflow application server and UI.
