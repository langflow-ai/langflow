import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import {
  checkPlaywrightReportFile,
  inspectPlaywrightReport,
} from "./check-playwright-report.mjs";

const reportWith = (playwrightTest) => ({
  suites: [
    {
      title: "suite",
      specs: [
        {
          title: "spec",
          file: "tests/example.spec.ts",
          line: 12,
          column: 4,
          tests: [playwrightTest],
        },
      ],
    },
  ],
  errors: [],
});

test("accepts a clean report", () => {
  assert.deepEqual(
    inspectPlaywrightReport(
      reportWith({ status: "expected", results: [{ status: "passed" }] }),
    ),
    { testCount: 1, flaky: [] },
  );
});

test("reports a flaky test without failing", () => {
  assert.deepEqual(
    inspectPlaywrightReport(
      reportWith({
        status: "flaky",
        results: [{ status: "failed" }, { status: "passed" }],
      }),
    ),
    { testCount: 1, flaky: ["tests/example.spec.ts:12:4 — suite > spec"] },
  );
});

test("reports a retried-to-pass test as flaky without failing", () => {
  assert.deepEqual(
    inspectPlaywrightReport(
      reportWith({
        status: "expected",
        results: [{ status: "timedOut" }, { status: "passed" }],
      }),
    ),
    { testCount: 1, flaky: ["tests/example.spec.ts:12:4 — suite > spec"] },
  );
});

test("still fails when a flaky test accompanies a real failure", () => {
  const report = reportWith({
    status: "unexpected",
    results: [{ status: "failed" }],
  });
  report.suites[0].specs.push({
    title: "flaky spec",
    file: "tests/flaky.spec.ts",
    line: 3,
    column: 1,
    tests: [
      {
        status: "flaky",
        results: [{ status: "failed" }, { status: "passed" }],
      },
    ],
  });
  assert.throws(
    () => inspectPlaywrightReport(report),
    /unexpected: tests\/example\.spec\.ts:12:4[\s\S]*flaky: tests\/flaky\.spec\.ts:3:1/,
  );
});

test("rejects an unexpected result", () => {
  assert.throws(
    () =>
      inspectPlaywrightReport(
        reportWith({ status: "unexpected", results: [{ status: "failed" }] }),
      ),
    /unexpected: tests\/example\.spec\.ts:12:4 — suite > spec/,
  );
});

test("prints the recursive suite title and spec location", () => {
  const report = {
    suites: [
      {
        title: "outer",
        suites: [
          {
            title: "inner",
            specs: [
              {
                title: "does work",
                file: "tests/nested.spec.ts",
                line: 27,
                tests: [
                  {
                    title: "reporter test title",
                    status: "flaky",
                    results: [{ status: "failed" }, { status: "passed" }],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
    errors: [],
  };

  assert.deepEqual(inspectPlaywrightReport(report).flaky, [
    "tests/nested.spec.ts:27 — outer > inner > does work",
  ]);
});

test("rejects a missing report", async () => {
  await assert.rejects(
    checkPlaywrightReportFile("/definitely/missing/playwright-report.json"),
    /Missing Playwright report/,
  );
});

test("rejects a report with no tests", () => {
  assert.throws(
    () => inspectPlaywrightReport({ suites: [], errors: [] }),
    /contains no tests/,
  );
});

test("rejects a partial test record", () => {
  assert.throws(
    () => inspectPlaywrightReport(reportWith({})),
    /Malformed Playwright test record/,
  );
});

test("accepts a legitimately skipped record without attempts", () => {
  assert.deepEqual(
    inspectPlaywrightReport(reportWith({ status: "skipped", results: [] })),
    { testCount: 1, flaky: [] },
  );
});

test("rejects malformed report JSON", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "playwright-report-"));
  const reportPath = path.join(directory, "report.json");
  await writeFile(reportPath, "not-json", "utf8");

  await assert.rejects(
    checkPlaywrightReportFile(reportPath),
    /Malformed Playwright report JSON/,
  );
});
