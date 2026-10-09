import type { MigrationCheck } from "@/controllers/API/queries/migration";
import en from "@/locales/en.json";
import { acceptanceOf, CHECKS, groupChecks } from "../catalog";

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
