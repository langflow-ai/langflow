# Langflow Core

`langflow-core` is Langflow's service-complete, provider-bundle-free application
profile. It combines `langflow-base[complete]`, the Langflow application server
and web UI, and Langflow's built-in core components. It does not depend on
provider extension distributions such as `lfx-openai`, `lfx-ibm`, or
`lfx-bundles`.

Install and run it with:

```bash
python -m pip install langflow-core
langflow run
```

The `langflow-core` command is an alias for the same launcher:

```bash
langflow-core run
```

For voice mode, install the audio dependencies:

```bash
python -m pip install "langflow-core[audio]"
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

The full `langflow` distribution consumes `langflow-core` and adds Langflow's
curated provider bundle set. `langflow-core` is the sole owner of the
`langflow` command, so full installations use the same launcher without
installing a duplicate console script. Install `langflow-core` directly when
you want to choose provider bundles yourself.

`langflow-core` is not Langflow's smallest package profile. Use the modular
`langflow-base` package when you need a smaller dependency surface or
lower-level control over service extras, or use `lfx` when you need the
headless execution engine without the Langflow application server and UI.
