import type {
  MigrationCheck,
  MigrationState,
} from "@/controllers/API/queries/migration";
import en from "@/locales/en.json";
import {
  acceptanceOf,
  CHECKS,
  COPY_CODES,
  copyCounts,
  copyProgress,
  DECISIONS,
  destinationsRequest,
  groupChecks,
  ITEM_CODES,
  JOB_STATES,
  PROBES,
  pgDumpCommand,
} from "../catalog";

const check = (
  name: string,
  status: MigrationCheck["status"],
  summary = "",
): MigrationCheck => ({ name, status, summary, problems: [] });

describe("groupChecks", () => {
  it("groups by what the admin has to do, keeping run order", () => {
    const groups = groupChecks(
      [
        check("version", "ok"),
        check("source: files", "fail"),
        check("source: credentials", "fail"),
        check("embedding models", "warn"),
        check("source: vector counts", "fail"),
        check("source: schema", "ok"),
      ],
      ["source: files", "source: vector counts"],
    );

    expect(groups.fix.map((c) => c.name)).toEqual(["source: credentials"]);
    expect(groups.decide.map((c) => c.name)).toEqual([
      "source: files",
      "source: vector counts",
    ]);
    expect(groups.read.map((c) => c.name)).toEqual(["embedding models"]);
    expect(groups.passed.map((c) => c.name)).toEqual([
      "version",
      "source: schema",
    ]);
    expect(groups.notRun).toBe(false);
  });

  it("shows only the schema check when it fails", () => {
    const groups = groupChecks(
      [check("version", "ok"), check("source: schema", "fail")],
      [],
    );

    expect(groups.fix.map((c) => c.name)).toEqual(["source: schema"]);
    expect(groups.passed).toEqual([]);
    expect(groups.notRun).toBe(true);
  });
});

describe("CHECKS", () => {
  // The page builds these keys from the slug, so the i18n check can't see one that is missing.
  it("has a title and a body for every check, and an accept label where it offers one", () => {
    const missing = Object.values(CHECKS)
      .flatMap(({ slug, accept }) =>
        ["title", "body", ...(accept ? ["accept"] : [])].map(
          (part) => `settings.migration.check.${slug}.${part}`,
        ),
      )
      .filter((key) => !(key in en));

    expect(missing).toEqual([]);
  });
});

describe("acceptanceOf", () => {
  const accepted = [
    {
      name: "source: files",
      summary: "2 files missing",
      accepted_by: "alice",
      accepted_at: "2026-09-30T12:00:00Z",
    },
  ];

  it("holds while the finding is unchanged", () => {
    expect(
      acceptanceOf(check("source: files", "fail", "2 files missing"), accepted)
        ?.lapsed,
    ).toBe(false);
  });

  it("lapses when the finding changed", () => {
    expect(
      acceptanceOf(check("source: files", "fail", "3 files missing"), accepted)
        ?.lapsed,
    ).toBe(true);
  });
});

describe("destinationsRequest", () => {
  const instance = (
    database: "sqlite" | "postgresql",
    knowledgeBases: boolean,
    files: boolean,
  ): MigrationState["instance"] => ({
    version: "1.13.0",
    database: { type: database },
    knowledge_bases: { local: knowledgeBases },
    files: { storage: "local", local: files },
  });
  const form = (fields: Record<string, string>) => {
    const data = new FormData();
    for (const [name, value] of Object.entries(fields)) data.set(name, value);
    return data;
  };
  const keys = { access_key_id: "id", secret_access_key: "secret" }; // pragma: allowlist secret

  it("sends every part a SQLite instance with local data needs", () => {
    expect(
      destinationsRequest(
        instance("sqlite", true, true),
        form({
          database_url: " postgresql://db.internal:5432/langflow\n",
          bucket: " acme",
          prefix: "files",
          ...keys,
          endpoint_url: "",
          ca_bundle: "",
        }),
      ),
    ).toEqual({
      database_url: "postgresql://db.internal:5432/langflow",
      vectors: { kind: "pgvector" },
      files: { bucket: "acme", prefix: "files", ...keys },
    });
  });

  it("leaves out the database on PostgreSQL, and what isn't stored on this server", () => {
    expect(
      destinationsRequest(
        instance("postgresql", false, true),
        form({
          bucket: "acme",
          prefix: "files",
          ...keys,
          endpoint_url: "http://s3.internal:8333",
          ca_bundle: "/etc/ssl/s3.pem",
        }),
      ),
    ).toEqual({
      files: {
        bucket: "acme",
        prefix: "files",
        ...keys,
        endpoint_url: "http://s3.internal:8333",
        ca_bundle: "/etc/ssl/s3.pem",
      },
    });
    expect(
      destinationsRequest(instance("postgresql", true, false), form({})),
    ).toEqual({ vectors: { kind: "pgvector" } });
  });
});

describe("PROBES", () => {
  // The page builds these keys from the server's code, so the i18n check can't see one that is missing.
  it("has a line for every reason the server refuses a destination", () => {
    expect(Object.keys(PROBES).sort()).toEqual([
      "bucket_denied",
      "bucket_missing",
      "bucket_unreachable",
      "db_not_empty",
      "db_unreachable",
      "no_create",
      "pgvector_env_missing",
      "pgvector_missing",
      "pgvector_package_missing",
      "secrets_missing",
    ]);
    expect(
      Object.values(PROBES).filter(
        (key) => !(`settings.migration.${key}` in en),
      ),
    ).toEqual([]);
  });
});

describe("JOB_STATES", () => {
  it("has words for every state of what the pause waits for", () => {
    expect(Object.keys(JOB_STATES).sort()).toEqual([
      "in_progress",
      "ingesting",
      "queued",
      "suspended",
    ]);
    expect(
      Object.values(JOB_STATES).filter(
        (slug) => !(`settings.migration.job.${slug}` in en),
      ),
    ).toEqual([]);
  });
});

describe("pgDumpCommand", () => {
  it("fills in the host, the port and the database, and names no user", () => {
    expect(pgDumpCommand("db.internal:5432/langflow")).toBe(
      "pg_dump -h db.internal -p 5432 -d langflow -F c -f langflow-backup.dump",
    );
    expect(pgDumpCommand("db.internal/langflow")).toBe(
      "pg_dump -h db.internal -d langflow -F c -f langflow-backup.dump",
    );
  });

  it("keeps IPv6 hosts whole and reads a port only outside their brackets", () => {
    expect(pgDumpCommand("[::1]/langflow")).toBe(
      "pg_dump -h ::1 -d langflow -F c -f langflow-backup.dump",
    );
    expect(pgDumpCommand("[::1]:5432/langflow")).toBe(
      "pg_dump -h ::1 -p 5432 -d langflow -F c -f langflow-backup.dump",
    );
    expect(pgDumpCommand("::1/langflow")).toBe(
      "pg_dump -h ::1 -d langflow -F c -f langflow-backup.dump",
    );
  });

  it("quotes database names that contain shell syntax", () => {
    expect(pgDumpCommand("db.internal/team's data;archive")).toBe(
      "pg_dump -h db.internal -d 'team'\\''s data;archive' -F c -f langflow-backup.dump",
    );
    expect(pgDumpCommand("db.internal/team/data")).toBe(
      "pg_dump -h db.internal -d team/data -F c -f langflow-backup.dump",
    );
  });
});

describe("COPY_CODES", () => {
  // The page builds these keys from the server's code, so the i18n check can't see one that is missing.
  it("has a line for every reason the page words when a copy does not count", () => {
    expect(Object.keys(COPY_CODES).sort()).toEqual([
      "bucket_error",
      "cancelled",
      "count_mismatch",
      "crashed",
      "destination_changed",
      "interrupted",
      "locked",
      "orphans_droppable",
      "orphans_no_rule",
      "pgvector_env_missing",
      "run_active",
      "secrets_missing",
      "target_not_empty",
      "target_unreachable",
      "value_rejected",
    ]);
    expect(
      Object.values(COPY_CODES).filter(
        (key) => !(`settings.migration.${key}` in en),
      ),
    ).toEqual([]);
  });
});

describe("ITEM_CODES", () => {
  it("has a line for every reason the page words when one knowledge base or file is not copied", () => {
    expect(Object.keys(ITEM_CODES).sort()).toEqual([
      "attachment_unmatched",
      "bad_name",
      "bucket_error",
      "file_conflict",
      "kb_backend_missing",
      "kb_changed",
      "kb_deleted",
      "kb_ingesting",
      "kb_metric_change",
      "kb_routing_changed",
      "kb_short",
      "kb_target_more",
      "kb_upgrade_pending",
      "no_source_bytes",
    ]);
    expect(
      Object.values(ITEM_CODES).filter(
        (key) => !(`settings.migration.${key}` in en),
      ),
    ).toEqual([]);
  });
});

describe("copyCounts", () => {
  it("counts what was copied, what was there already and what was not, whichever copy it was", () => {
    expect(copyCounts({ relocated: 3, skipped: 1, failed: 2 })).toEqual({
      copied: 3,
      skipped: 1,
      failed: 2,
    });
    // A test run counts what it would copy.
    expect(copyCounts({ would_relocate: 2 })).toEqual({
      copied: 2,
      skipped: 0,
      failed: 0,
    });
    // An attachment that was renamed in chat history is no file of its own.
    expect(copyCounts({ copied: 5, repointed: 4, would_copy: 1 })).toEqual({
      copied: 6,
      skipped: 0,
      failed: 0,
    });
  });
});

describe("copyProgress", () => {
  const progress = (phase?: string, done = 0, total: number | null = null) =>
    ({ event: "progress", seq: 1, phase, done, total }) as const;

  it("says what a run is doing, and counts in the reader's language once it copies", () => {
    expect(copyProgress("copy_database", progress("checking"), "en")).toEqual([
      "copy.checking",
      {},
    ]);
    expect(
      copyProgress("copy_database", progress("preparing_target"), "en"),
    ).toEqual(["copy.preparing", {}]);
    expect(
      copyProgress("copy_database", progress("copying", 1200, 57000), "en"),
    ).toEqual(["copyDb.progress", { done: "1,200", total: "57,000" }]);
    expect(
      copyProgress("copy_database", progress("copying", 1200, 57000), "de"),
    ).toEqual(["copyDb.progress", { done: "1.200", total: "57.000" }]);
    // A line with no phase is one of the copy itself.
    expect(
      copyProgress("copy_database", progress(undefined, 3, 9), "en"),
    ).toEqual(["copyDb.progress", { done: "3", total: "9" }]);
  });

  it("counts entries for knowledge bases, and files with how much of them was copied", () => {
    expect(
      copyProgress("copy_knowledge_bases", progress("copying", 12, 300), "en"),
    ).toEqual(["kb.progress", { done: "12", total: "300" }]);
    expect(
      copyProgress(
        "copy_files",
        { ...progress("copying", 1, 3), bytes: 2048 },
        "en",
      ),
    ).toEqual(["files.progress", { done: "1", total: "3", bytes: "2 KB" }]);
  });
});

describe("DECISIONS", () => {
  // The server says which decision an item offers. The page only has to have words for each.
  it("has a label for every decision the server can offer", () => {
    expect(Object.keys(DECISIONS).sort()).toEqual([
      "accept_missing_attachment",
      "accept_ranking_change",
      "drop_orphans",
      "keep_bucket_file",
      "leave_behind",
    ]);
    expect(
      Object.values(DECISIONS).filter(
        (key) => !(`settings.migration.${key}` in en),
      ),
    ).toEqual([]);
  });
});
