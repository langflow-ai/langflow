import { writeFileSync } from "node:fs";
import type { ICheckerReport, ICheckerResult } from "accessibility-checker";
import path from "path";

// Keep in sync with .achecker.yml `outputFolder`.
const A11Y_REPORTS_DIR = "coverage/accessibility-reports";

// Persist the ignore rules a scan actually applied as a sidecar next to its IBM
// report ({scanLabel}.json). The report builder reads this to grey out the
// suppressed rules for exactly that scan — no label-prefix guessing. Always
// written (even []) so "this scan suppressed nothing" is explicit and
// distinguishable from a missing/legacy report.
export function writeA11yIgnoreSidecar(
  scanLabel: string,
  ignoreRules?: string[],
): void {
  const file = path.join(A11Y_REPORTS_DIR, `${scanLabel}.ignore.json`);
  writeFileSync(
    file,
    `${JSON.stringify({ label: scanLabel, ignoreRules: ignoreRules ?? [] }, null, 2)}\n`,
  );
}

function compactWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function truncate(value: string, max = 140): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

export function sanitizeA11yLabelPart(value: string): string {
  const sanitized = value.replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "");
  return sanitized || "scan";
}

export function buildA11yScanLabel(
  projectName: string,
  label: string,
  scanIndex: number,
): string {
  const scanLabelParts = [
    sanitizeA11yLabelPart(projectName),
    sanitizeA11yLabelPart(label),
  ];

  if (scanIndex > 0) {
    scanLabelParts.push(`${scanIndex}`);
  }

  return scanLabelParts.join("__");
}

export function isCheckerReport(
  report: ICheckerResult["report"],
): report is ICheckerReport {
  return "summary" in report && "results" in report && "label" in report;
}

export function buildA11ySummaryAttachment(
  scanIndex: number,
  scanLabel: string,
  report: ICheckerReport,
) {
  return {
    name: `a11y-summary-${scanIndex}`,
    contentType: "application/json",
    body: Buffer.from(
      JSON.stringify(
        {
          label: scanLabel,
          url: report.summary.URL,
          policies: report.summary.policies,
          ruleArchive: report.summary.ruleArchive,
          counts: report.summary.counts,
        },
        null,
        2,
      ),
    ),
  };
}

export function formatA11yFailure(
  scanLabel: string,
  report: ICheckerReport,
  ignoreRules?: string[],
): string {
  const counts = report.summary.counts;
  const reportPath = path.posix.join(
    "coverage",
    "accessibility-reports",
    `${scanLabel}.html`,
  );

  const failingIssues = report.results.filter(
    (issue) =>
      !issue.ignored &&
      (issue.level === "violation" || issue.level === "potentialviolation") &&
      !ignoreRules?.includes(issue.ruleId),
  );

  const groupedIssues = new Map<
    string,
    {
      count: number;
      message: string;
      level: string;
      ruleId: string;
      snippet: string;
      xpath: string;
    }
  >();

  for (const issue of failingIssues) {
    const key = `${issue.level}::${issue.ruleId}::${issue.message}`;
    const existing = groupedIssues.get(key);

    if (existing) {
      existing.count += 1;
      continue;
    }

    groupedIssues.set(key, {
      count: 1,
      message: issue.message,
      level: issue.level ?? "unknown",
      ruleId: issue.ruleId,
      snippet: truncate(compactWhitespace(issue.snippet)),
      xpath: Object.values(issue.path ?? {})[0] ?? "n/a",
    });
  }

  const topIssues = Array.from(groupedIssues.values())
    .sort((left, right) => right.count - left.count)
    .slice(0, 8);

  const lines = [
    `IBM accessibility regression detected: ${scanLabel}`,
    `Report: ${reportPath}`,
    `New issues: ${failingIssues.length}`,
    `Report counts: violation=${counts.violation}, potential=${counts.potentialviolation}, recommendation=${counts.recommendation}, manual=${counts.manual}`,
    `Top issues (${topIssues.length}/${groupedIssues.size} groups shown):`,
    ...topIssues.map(
      (issue) =>
        `- [${issue.level}] ${issue.ruleId} x${issue.count}: ${issue.message}\n  xpath: ${issue.xpath}\n  snippet: ${issue.snippet}`,
    ),
  ];

  if (groupedIssues.size > topIssues.length) {
    lines.push("More issues in HTML report.");
  }

  return lines.join("\n");
}

export function countNewA11yViolations(
  report: ICheckerReport,
  ignoreRules?: string[],
): number {
  return report.results.filter(
    (issue) =>
      issue.level === "violation" &&
      !issue.ignored &&
      !ignoreRules?.includes(issue.ruleId),
  ).length;
}
