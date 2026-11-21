# Additional provider contracts

This directory records integrations added after the frozen Google, Microsoft, and Slack discovery gate. That gate and its historical owner signatures stay in `design/dedicated-integrations`.

Each shipped provider has exactly one entry in `index.json`, with `provider_id` and a relative `contract` path such as `contracts/jira.v1.json`. The version-1 contract contains these fields.

- `schema_version` is `1`.
- `provider_id` matches the installed extension declaration.
- `distribution` matches the extension ID that owns that declaration.
- `manifest` is the complete, statically recorded capability manifest, including auth profiles, scopes, contexts, identity, component references, policy, risk, maturity, and transport substrate. CI compares every field and rejects extra or missing capabilities.
- `sources` contains official document records with `url`, `title`, and `verified_on` in YYYY-MM-DD format. Source verification is recorded explicitly, never inferred from a passing test.
- `transport_limitations` lists supported transport boundaries and delivery limitations.
- `evidence_paths` lists existing repository paths for implementation, contract tests, and setup documentation.
- `owner_acceptance` records `status` and `note`. New implementation proposals use `pending`. An `accepted` record also requires a named `owner` and acceptance `date` backed by that owner's actual approval.

Provider setup documents live here beside the index. A passing contract check proves that the shipped declaration matches this record. It does not prove live provider acceptance or owner sign-off.
