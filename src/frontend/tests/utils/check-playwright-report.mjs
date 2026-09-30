import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const FAILURE_RESULT_STATUSES = new Set(["failed", "timedOut", "interrupted"]);
const TEST_STATUSES = new Set(["expected", "unexpected", "flaky", "skipped"]);
const RESULT_STATUSES = new Set([
  "passed",
  "failed",
  "timedOut",
  "skipped",
  "interrupted",
]);

function formatLocation(spec) {
  const file = spec.file ?? spec.location?.file;
  const line = spec.line ?? spec.location?.line;
  const column = spec.column ?? spec.location?.column;
  if (!file) return "unknown-file";
  if (!line) return file;
  return `${file}:${line}${column ? `:${column}` : ""}`;
}

function collectTests(suites, tests, ancestorTitles = []) {
  for (const suite of suites) {
    const suiteTitles = suite.title
      ? [...ancestorTitles, suite.title]
      : ancestorTitles;
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        tests.push({
          ...test,
          fullTitle: [...suiteTitles, spec.title].filter(Boolean).join(" > "),
          location: formatLocation(spec),
        });
      }
    }
    collectTests(suite.suites ?? [], tests, suiteTitles);
  }
}

export function inspectPlaywrightReport(report) {
  if (!report || typeof report !== "object" || !Array.isArray(report.suites)) {
    throw new Error("Malformed Playwright report: expected a suites array.");
  }

  const tests = [];
  collectTests(report.suites, tests);
  if (tests.length === 0) {
    throw new Error("Playwright report contains no tests.");
  }

  const flaky = [];
  const unexpected = [];
  for (const test of tests) {
    if (!TEST_STATUSES.has(test.status)) {
      throw new Error(
        `Malformed Playwright test record at ${test.location}: unrecognized aggregate status.`,
      );
    }
    if (!Array.isArray(test.results)) {
      throw new Error(
        `Malformed Playwright test record at ${test.location}: expected a results array.`,
      );
    }
    const results = test.results;
    if (test.status !== "skipped" && results.length === 0) {
      throw new Error(
        `Malformed Playwright test record at ${test.location}: expected at least one result.`,
      );
    }
    if (
      results.some(
        (result) =>
          !result ||
          typeof result !== "object" ||
          !RESULT_STATUSES.has(result.status),
      )
    ) {
      throw new Error(
        `Malformed Playwright test record at ${test.location}: unrecognized result status.`,
      );
    }
    const hasFailedAttempt = results.some((result) =>
      FAILURE_RESULT_STATUSES.has(result.status),
    );
    const finalResult = results.at(-1);
    const retriedToPass =
      results.length > 1 &&
      hasFailedAttempt &&
      finalResult?.status === "passed";

    if (test.status === "flaky" || retriedToPass) {
      flaky.push(`${test.location} — ${test.fullTitle}`);
      continue;
    }
    if (
      test.status === "unexpected" ||
      FAILURE_RESULT_STATUSES.has(finalResult?.status)
    ) {
      unexpected.push(`${test.location} — ${test.fullTitle}`);
    }
  }

  if (Array.isArray(report.errors) && report.errors.length > 0) {
    unexpected.push(`${report.errors.length} top-level reporter error(s)`);
  }

  // Only a test that ended red fails the gate. A test that retried to green is
  // returned for the caller to report, not thrown: the suite carries a
  // background flake rate of a few specs per run out of ~445, and a different
  // set surfaces each time, so failing on it blocks every PR on whichever
  // specs happened to be unlucky. Flakes stay visible in the log so the list
  // can be worked down.
  if (unexpected.length > 0) {
    const details = unexpected.map((title) => `  - unexpected: ${title}`);
    if (flaky.length > 0) {
      details.push(...flaky.map((title) => `  - flaky: ${title}`));
    }
    throw new Error(`Playwright report is not clean:\n${details.join("\n")}`);
  }

  return { testCount: tests.length, flaky };
}

export async function checkPlaywrightReportFile(reportPath) {
  let contents;
  try {
    contents = await readFile(reportPath, "utf8");
  } catch (error) {
    throw new Error(`Missing Playwright report at ${reportPath}.`, {
      cause: error,
    });
  }

  let report;
  try {
    report = JSON.parse(contents);
  } catch (error) {
    throw new Error(`Malformed Playwright report JSON at ${reportPath}.`, {
      cause: error,
    });
  }
  return inspectPlaywrightReport(report);
}

const isCli =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isCli) {
  const reportPath = process.argv[2];
  if (!reportPath) {
    console.error("Usage: node check-playwright-report.mjs <report.json>");
    process.exitCode = 2;
  } else {
    try {
      const { testCount, flaky } = await checkPlaywrightReportFile(reportPath);
      if (flaky.length > 0) {
        console.warn(
          `Playwright report has ${flaky.length} flaky test(s) (not failing the gate):\n${flaky
            .map((title) => `  - flaky: ${title}`)
            .join("\n")}`,
        );
      }
      // biome-ignore lint/suspicious/noConsole: this CLI reports its gate result to CI logs
      console.log(
        `Playwright report has no failures (${testCount} tests, ${flaky.length} flaky).`,
      );
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    }
  }
}
