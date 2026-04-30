# Regression Log

This directory contains one YAML file per release cycle documenting known regressions.
Regressions are behaviors that worked in a previous version and broke in a subsequent one.
Regressions can be found through manual QA, automated testing, a support ticket, or code review.

The purpose of this YAML is to provide a single source of truth for known breaks before and after release.

When a regression is found, add an entry to the YAML file for the current release cycle and open a pull request. To add a regression to the file, do the following:

1. Open `regressions/<release-1.10.0>.yaml`
2. Add a new entry under `entries:` following the schema below.
3. Set `status: triage` if the severity and workaround are not yet confirmed.
4. Open a pull request targeting the active RC branch (`release-1.10.0`).

Regression entry schema:

```yaml
- id: RG-NNN                        # Sequential, unique identifier
  title: "Short description"        # One line, plain language
  status: triage                    # See statuses below
  area: flow editor                 # See areas below
  first_bad_version: 1.10.0         # First version where this breaks
  last_known_good_version: 1.9.0    # Last version where this worked
  workaround: |
    Describe the workaround here.
    Leave blank or "None" if no workaround exists.
```

Status options:

| Status | Meaning |
|---|---|
| `triage` | Found, not yet fully assessed. Default when first filing. |
| `ship_with_note` | Shipping as-is. Docs must communicate the workaround. |
| `resolved` | Fixed; add `resolved_in_version` to record which version contains the fix. |
| `blocking` | Release blocker; requires explicit sign-off before shipping. |

When marking an entry `resolved`, add the version that the regression was resolved in:
```yaml
  resolved_in_version: 1.10.1
```

Area options:

| Area | Covers |
|---|---|
| `flow editor` | The visual builder UI. |
| `components` | Core components. |
| `MCP` | MCP server registration, MCP tools, MCP sidebar. |
| `API` | REST API endpoints. |
| `LFX` | The `lfx` CLI executor. |
| `auth` | Login, API keys, user management. |
| `database` | Migrations, storage, flow persistence. |
| `integrations` | Third-party components. |
| `starter projects` | Bundled example flows. |

## Review regressions before release

During QA, support engineers keep entries current throughout RC by moving items out of `triage`, add workarounds, and marked fixed items as `resolved` with `resolved_in_version`.

Docs team reviews all `ship_with_note` entries before release, and use `workaround` text to update release notes.

The release captain confirms no unresolved `blocking` entries exist.
If `blocking` entries exist, they should be signed off on.

See [RELEASE.md](../RELEASE.md) for the full release process.
