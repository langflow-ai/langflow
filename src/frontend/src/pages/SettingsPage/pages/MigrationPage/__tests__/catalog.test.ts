import type {
  MigrationCheck,
  MigrationState,
} from "@/controllers/API/queries/migration";
import en from "@/locales/en.json";
import {
  acceptanceOf,
  CHECKS,
  destinationsRequest,
  groupChecks,
  PROBES,
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
      "pgvector_missing",
      "secrets_missing",
    ]);
    expect(
      Object.values(PROBES).filter(
        (key) => !(`settings.migration.${key}` in en),
      ),
    ).toEqual([]);
  });
});
