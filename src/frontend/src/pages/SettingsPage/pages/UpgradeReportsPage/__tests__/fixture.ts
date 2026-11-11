import type { ReportDetail } from "@/controllers/API/queries/upgrade-reports";

export const report: ReportDetail = {
  id: "ba9a4c6e-c2d1-4810-a792-48c86f591dd8",
  created_at: "2026-11-04T20:00:00Z",
  generated_at: "2026-11-04T19:00:00Z",
  target_version: "1.14.0",
  source_identity: null,
  flow_count: 3,
  warning_count: 1,
  failing_count: 0,
  document: {
    format_version: 1,
    generated_at: "2026-11-04T19:00:00Z",
    source: { dialect: "sqlite", alembic_revision: null },
    target: {
      langflow: "1.14.0",
      lfx: "1.14.0",
      component_index_sha256: "a".repeat(64),
      bundles: [],
    },
    summary: {
      flows: { ok: 2, warn: 1, fail: 0 },
      nodes: { could_not_verify: 1 },
    },
    flows: [
      {
        id: "b716ffda-cd37-4547-848d-93f9d22c39a7",
        kind: "flow",
        name: "Customer support",
        owner: { id: "owner-1", username: "Grace" },
        project: { id: "project-1", name: "Support" },
        last_edited_at: null,
        status: "warn",
        labels: ["Production"],
        nodes: [
          {
            id: "mcp-1",
            group_path: [],
            type: "MCPTools",
            display_name: "MCP Tools",
            status: "could_not_verify",
            reasons: [
              {
                code: "could_not_verify",
                message: "Tool discovery was unavailable.",
              },
            ],
            dry_run: { result: "could_not_verify" },
          },
        ],
        flow_id: null,
        version_number: null,
        used_by: { deployments: ["serving-1"] },
        error: null,
        usage: {
          editor: {
            runs: 0,
            errors: 0,
            last_run_at: null,
            history: "no_retained_records",
            coverage: {
              oldest_retained_at: null,
              newest_retained_at: null,
              observed_at: "2026-11-04T19:00:00Z",
              complete: false,
              retention_days: 30,
            },
            limitations: [],
          },
          serving: {
            runs: null,
            errors: null,
            last_run_at: null,
            history: "unavailable",
            coverage: {
              oldest_retained_at: null,
              newest_retained_at: null,
              observed_at: "2026-11-04T19:00:00Z",
              complete: false,
              retention_days: null,
            },
            limitations: ["source_unavailable"],
          },
        },
      },
    ],
    errors: [],
  },
};
export const history = { items: [report], total: 1, offset: 0, limit: 20 };
export const preview = {
  target_sha256: "b".repeat(64),
  target_version: "1.14.0",
  results: [
    {
      flow_id: report.document.flows[0].id,
      status: "ready",
      version_token: null,
      data_sha256: "c".repeat(64),
      updated_nodes: 1,
      recovery_version_id: null,
      reason_codes: ["customized_nodes_skipped"],
    },
  ],
};
