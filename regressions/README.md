# Regression Log

This directory contains one YAML file per release cycle documenting known regressions.
Regressions are behaviors that worked in a previous version and broke in a subsequent one.
Regressions can be found through manual QA, automated testing, a support ticket, or code review.

The purpose of this YAML is to provide a single source of truth for known breaks before and after release.

When a regression is found, add an entry to the YAML file for the current release cycle and open a pull request. To add a regression to the file, do the following:

1. Open `regressions/<version>.yaml` for the version where the regression was discovered.
For example, open `1.9.x.yaml` if it first broke in 1.9.0.
Create the file if it doesn't exist.
2. Add a new entry under `entries:` following the schema below.
3. Set `status: triage` if the severity and workaround are not yet confirmed.
4. Open a pull request targeting the active RC branch.
The fix PR and the YAML entry may target different branches.

Regression entry schema:

```json
{
  "id": "GH-12345",
  "title": "Short plain-language description",
  "status": "triage",
  "area": "flow_editor",
  "first_bad_version": "1.10.0",
  "last_known_good_version": "1.9.0",
  "resolved_in_version": "1.10.1",
  "fix_pr": "https://github.com/langflow-ai/langflow/pull/12345",
  "workaround": "none"
}
```

`resolved_in_version` and `fix_pr` are optional.
You can omit them when first filing and add them when the fix lands.

Status options:

| Status | Meaning |
|---|---|
| `triage` | Found, not yet fully assessed. Default when first filing. |
| `ship_with_note` | Shipping as-is. Docs must communicate the workaround. |
| `resolved` | Fixed; add `resolved_in_version` to record which version contains the fix. |
| `blocking` | Release blocker; requires explicit sign-off before shipping. |

When marking an entry `resolved`, include the version that the regression was resolved in:
```yaml
  resolved_in_version: 1.10.1
```

Area options:

| Area | Covers |
|---|---|
| `flow_editor` | The visual builder UI. |
| `components` | Core components. |
| `mcp` | MCP server registration, MCP tools, MCP sidebar. |
| `api` | REST API endpoints. |
| `lfx` | The `lfx` CLI executor. |
| `auth` | Login, API keys, user management. |
| `database` | Migrations, storage, flow persistence. |
| `integrations` | Third-party components. |
| `starter_projects` | Bundled example flows. |

## Review regressions before release

During QA, support engineers keep entries current throughout RC by moving items out of `triage`, add workarounds, and marked fixed items as `resolved` with `resolved_in_version`.

Docs team reviews all `ship_with_note` entries before release, and ncludes `workaround` text to update known issues in release notes.

Release captain confirms no unresolved `blocking` entries exist.
If `blocking` entries exist, they should be signed off on in the GitHub issue by a maintainer.

See [RELEASE.md](../RELEASE.md) for the full release process.