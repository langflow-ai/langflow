# lfx-talordata

Talordata SERP API component as a standalone Langflow Extension Bundle.

The bundle ships `TalordataSERPAPIComponent`, which calls Talordata SERP API and returns structured search results as a Langflow table.

## Install

```bash
pip install lfx-talordata
```

After install, restart your Langflow server. The component appears in the palette under the `talordata` bundle group.

## Develop

```bash
cd src/bundles/talordata
pip install -e .
lfx extension validate .
```

## Product

- Product: https://www.talordata.com/products/serp-api
- Documentation: https://docs.talordata.com/serp-api/query-parameters
