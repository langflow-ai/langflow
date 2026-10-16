# langflow-extra-providers

Add **OpenAI-compatible model providers** (DeepSeek, GLM/Z.ai, and any other
OpenAI-API-compatible endpoint) to Langflow's **Model providers** dialog —
**without editing Langflow's source code**.

This is a standalone pip package that you install *alongside* Langflow. It
registers the extra providers at runtime by mutating Langflow's in-memory model
catalog. Because it lives in its own package (not in Langflow's source tree), it
**survives `pip install -U langflow`** — you install it once and never have to
re-patch after an update.

## Why this exists

Langflow's provider catalog (`MODEL_PROVIDER_METADATA`) and model lists are
hardcoded in `lfx`. Adding a provider normally means editing those files, which
gets overwritten on every Langflow update. This package injects the providers at
runtime instead, so there is nothing to re-apply after upgrading.

DeepSeek and GLM both expose an OpenAI-compatible API, so they reuse Langflow's
existing `ChatOpenAI` integration — just pointed at a different `base_url`.

## Install

Install into the **same environment** as your Langflow server:

```bash
pip install langflow-extra-providers          # from a wheel/PyPI
# or, from this directory:
pip install .
```

Then activate auto-loading (writes a tiny `.pth` file into the environment's
`site-packages` so the providers register every time Langflow starts):

```bash
python -m langflow_extra_providers install
```

Restart the Langflow server. **DeepSeek** and **GLM (Z.ai)** now appear in
*Settings → Model providers*. Click **+**, paste your API key, and use them like
any built-in provider.

> The `install` step is a one-time action and survives Langflow upgrades. Run
> `python -m langflow_extra_providers uninstall` to deactivate.

### Commands

```bash
python -m langflow_extra_providers install     # activate auto-load (.pth)
python -m langflow_extra_providers uninstall   # deactivate auto-load
python -m langflow_extra_providers status      # show state + configured providers
python -m langflow_extra_providers apply       # register once in the current process
```

## Configure / add more providers (no code changes)

The built-ins are DeepSeek and GLM (Z.ai). To change endpoints, add models, or
register additional OpenAI-compatible providers, set the
`LANGFLOW_EXTRA_PROVIDERS` environment variable to inline JSON **or a path to a
`.json` file**. It is merged on top of the defaults.

```bash
export LANGFLOW_EXTRA_PROVIDERS='{
  "GLM (Z.ai)": { "base_url": "https://open.bigmodel.cn/api/paas/v4" },
  "Moonshot": {
    "base_url": "https://api.moonshot.cn/v1",
    "api_key_var": "MOONSHOT_API_KEY",
    "api_docs_url": "https://platform.moonshot.cn/docs",
    "models": [
      { "name": "moonshot-v1-8k",  "tool_calling": true },
      { "name": "moonshot-v1-32k", "tool_calling": true }
    ]
  }
}'
```

Per-provider spec fields:

| field             | required | description                                                        |
|-------------------|----------|--------------------------------------------------------------------|
| `base_url`        | yes      | OpenAI-compatible endpoint, e.g. `https://api.deepseek.com`         |
| `api_key_var`     | yes      | Global-variable / env key for the API key, e.g. `DEEPSEEK_API_KEY` |
| `models`          | no       | List of `{ "name": ..., "tool_calling": bool, "reasoning": bool }` |
| `api_docs_url`    | no       | Link shown in the provider settings panel                          |
| `icon`            | no       | Frontend icon name (defaults to `OpenAI`; unknown → generic icon)  |
| `description`     | no       | Help text shown for the API-key field                              |
| `default_headers` | no       | Extra HTTP headers sent on every request                           |

Set `LANGFLOW_EXTRA_PROVIDERS_DISABLE_DEFAULTS=1` to drop the built-in DeepSeek /
GLM entries and use only your own.

The API key can also be provided via the matching environment variable
(e.g. `export DEEPSEEK_API_KEY=...`) instead of the Settings UI.

## How it works (no monkey-business in your flows)

* Adds entries to `MODEL_PROVIDER_METADATA` (so the provider + its API-key field
  show up in Settings) and to the static model catalog (so the provider and its
  models appear in the dialog and dropdowns).
* Pre-seeds `lfx`'s model-class cache with a small factory that returns a
  `langchain_openai.ChatOpenAI` bound to the provider's `base_url`. Langflow's
  `get_llm()` resolves the class through that cache, so **no change to
  instantiation code is needed**.
* Registration is armed by a lightweight `sys.meta_path` hook that fires the
  moment Langflow loads its model catalog — it does **not** import the heavy
  `lfx` package on unrelated `python` invocations.
* Everything is wrapped in defensive `try/except`: if a future Langflow refactor
  changes these internals, the worst case is the extra providers silently not
  registering — your Langflow install keeps working.

## Compatibility note

This package relies on `lfx` internals (the model catalog structures). It targets
the Langflow version it ships with. If a future Langflow release reorganizes the
model-provider internals, update this package. Pin it next to your Langflow
version if you need strict reproducibility.

## Uninstall

```bash
python -m langflow_extra_providers uninstall   # remove the .pth
pip uninstall langflow-extra-providers
```
