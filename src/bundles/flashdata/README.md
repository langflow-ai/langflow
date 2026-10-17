# lfx-flashdata

Google and YouTube research data for Langflow. This source bundle implements
15 capabilities as 17 components; YouTube delivery uses separate submit, status,
and result components. API calls use paid FlashData Credits. Installing this
open-source bundle does not make the API free.

This package is under development and has not been published to PyPI or approved
for the official Langflow catalog. In a Langflow 1.13 development environment:

```bash
uv pip install -e src/bundles/flashdata
lfx extension validate src/bundles/flashdata/src/lfx_flashdata
```

Restart Langflow after installation. Select a FlashData component from Bundles,
configure your API key as a Credential global variable, and connect a query,
video ID/URL, or channel handle. Advanced Parameters accepts a JSON object of
source-specific options, excluding the primary input and all credentials.
The component validates these options before making one request.

The JSON output preserves the FlashData response, including `results` and job
metadata. It can feed a Parser or a downstream data-processing component.
In Tool Mode, connect its Tool output to an Agent. Only the primary input is
agent-controlled; credentials and advanced parameters remain configured on the
component. A model provider and its billing are separate from FlashData.

Download Submit additionally requires a secret customer-storage JSON credential
and explicit Allow Paid Submission. Save the returned job ID. Inspect it with
Download Status or Download Result instead of submitting again. There is no
automatic polling or retry; an ambiguous timeout may already have been charged.
Result JSON expires after 24 hours; delivered-media retention is controlled by
your storage provider. Storage and delivery can incur additional fees.

Get a key and current rates at https://flashdata.dev. Source contracts and
limitations are documented at https://flashdata.dev/docs. The per-component
documentation links open the corresponding source page directly.
