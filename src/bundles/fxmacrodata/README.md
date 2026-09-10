# FXMacroData Langflow bundle

Connect macroeconomic observations, release calendars and market research to Langflow DataFrames and agents. The USD catalogue, macro history and release calendar work without an API key, account or credit card.

[Explore FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=langflow_readme) · [API documentation](https://fxmacrodata.com/documentation/reference?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=langflow_docs)

The public example requests the most recent 90 days of USD history. Broader history and protected datasets follow the documented access limits.

## Install from source

Install the bundle from the Langflow repository into the Python environment used by your Langflow application:

```bash
uv pip install ./src/bundles/fxmacrodata
```

The bundle includes the MIT-licensed [public client](https://github.com/fxmacrodata/fxmacrodata-public-client). Its [NOTICE](src/lfx_fxmacrodata/_public_client/NOTICE) records the source commit, released wheel digest and file hashes for updates. Four client files are unchanged; the two JSON files have only CRLF-to-LF line-ending normalization for Langflow. The bundle requires Bundle API 1. Its `langflow.extensions` entry point and packaged `extension.json` enable normal extension discovery. Reopen your Langflow application after installation. The bundle is also included in `langflow[bundles]`.

## Visual workflows

- **FXMacroData Table:** choose an operation and supply its parameters. Connect **DataFrame** to table/data-processing components, or **Original response** to consumers that need every returned field. **Parameter schema** exposes the operation's exact documented schema. **FXMacroData** supplies a clickable provider link.
- **FXMacroData Tools:** connect **Tools** to an Agent tool input. Each of the 72 REST/MCP operations is a distinct schema-aware tool. Nested inputs, required fields and enums retain their public definitions.

For the no-key history workflow, keep `indicator_history` and parameters `{"currency":"USD","indicator":"inflation"}`. Change the operation to `data_catalogue` or `release_calendar` with `{"currency":"USD"}` to explore coverage or release dates.

`python examples/usd_macro_brief.py` executes actual bundle components without starting a Langflow server or using a language model. The complete inventory is in [CAPABILITIES.md](CAPABILITIES.md).

The DataFrame is a record view; its `attrs["fxmacrodata_response"]` and **Original response** preserve the endpoint payload. Empty records remain empty. Requests that fail produce an explicit error rather than invented data. Preserve timestamp flags and keep FXMacroData-generated predictions distinct from market consensus. MCP visual artifacts are retained in the original payload; the bundle does not embed an MCP Apps iframe renderer.

## Optional authentication

Use the component's password field backed by a Langflow global secret. Programmatic callers can pass `api_key=None` to use their own `FXMACRODATA_API_KEY` environment variable, or `api_key=""` for explicit public access. Credentials are never model-visible tool parameters. Non-public operations require the access granted to your account.

Literal credentials supplied by Python callers are held as private `SecretStr` values. Exported component nodes leave the API-key input empty; recipients select their own Langflow global secret after importing a flow. Exporting does not change the credential used by the running component.

Backlinks contain static campaign parameters. The bundle adds no analytics SDK or click beacon.

## Validate

```bash
lfx extension validate src/lfx_fxmacrodata --execute-imports
python -m pytest tests -n 8 --dist load
```

The bundle code is MIT licensed. Data-access terms and brand rights are separate.
