# lfx-typesafe

TypeSafe System One components as a standalone Langflow Extension Bundle.

The bundle ships `TypeSafeSystemOneComponent`, which evaluates text or JSON
state against typed questions on `POST /v1/systemone`. Jev (`jev-latest`) is
the default model. Question types are `noul` (yes/no probability), `choice`,
and `score`.

The component calls the [System One HTTP API](https://docs.typesafe.ai/api)
with `httpx`. It does not depend on the TypeSafe SDK.

## Install

```bash
pip install lfx-typesafe
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server. The component
appears in the palette under the `typesafe` group with the namespaced ID
`ext:typesafe:TypeSafeSystemOneComponent@official`.

## Develop

```bash
cd src/bundles/typesafe
pip install -e .
lfx extension validate src/lfx_typesafe
```

## Questions

`questions` is a JSON object. Each key is the answer id returned by the API.

```json
{
  "department": {
    "type": "choice",
    "instructions": "Which team should handle this?",
    "criteria": {
      "billing": "Payments, invoicing, refunds",
      "technical": "Bugs, outages, integrations"
    }
  },
  "is_urgent": {
    "type": "noul",
    "instructions": "Does this message express urgency?"
  }
}
```
