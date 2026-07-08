// Aggregates IBM accessibility-checker JSON reports into one grouped summary.
//
// Usage (from src/frontend, after a RUN_A11Y=true playwright run):
//   node tests/utils/aggregate-a11y-reports.mjs
//   node tests/utils/aggregate-a11y-reports.mjs --json   # machine-readable output
//
// Reads:  coverage/accessibility-reports/*.json (one per scan)
// Groups: by ruleId; counts total occurrences, unique elements (dom path),
//         and which scans hit the rule. Identical elements appearing in
//         multiple scans (header, sidebar, ...) collapse into one unique entry.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

const REPORTS_DIR = path.resolve("coverage", "accessibility-reports");
const asJson = process.argv.includes("--json");

let files;
try {
  files = readdirSync(REPORTS_DIR).filter(
    (f) => f.endsWith(".json") && f !== "summary.json",
  );
} catch {
  console.error(`No reports directory at ${REPORTS_DIR}. Run scans first:`);
  console.error("  RUN_A11Y=true npx playwright test <spec>");
  process.exit(1);
}

if (files.length === 0) {
  console.error(`No JSON reports in ${REPORTS_DIR}.`);
  console.error('Ensure .achecker.yml outputFormat includes "json".');
  process.exit(1);
}

const rules = new Map();
const scans = new Set();

for (const file of files) {
  const report = JSON.parse(readFileSync(path.join(REPORTS_DIR, file), "utf8"));
  const label = report.label ?? file.replace(/\.json$/, "");
  scans.add(label);

  for (const issue of report.results ?? []) {
    if (issue.level !== "violation" && issue.level !== "potentialviolation") {
      continue;
    }

    let entry = rules.get(issue.ruleId);
    if (!entry) {
      entry = {
        ruleId: issue.ruleId,
        level: issue.level,
        total: 0,
        elements: new Set(),
        scans: new Set(),
        messages: new Set(),
        sampleSnippet: issue.snippet,
        help: issue.help?.split("#")[0] ?? "",
      };
      rules.set(issue.ruleId, entry);
    }

    entry.total += 1;
    entry.elements.add(issue.path?.dom ?? issue.snippet);
    entry.scans.add(label);
    entry.messages.add(issue.message);
  }
}

const grouped = [...rules.values()]
  .map((e) => ({
    ruleId: e.ruleId,
    level: e.level,
    total: e.total,
    uniqueElements: e.elements.size,
    scans: [...e.scans].sort(),
    messages: [...e.messages],
    sampleSnippet: e.sampleSnippet,
    help: e.help,
  }))
  .sort((a, b) => b.uniqueElements - a.uniqueElements || b.total - a.total);

if (asJson) {
  console.log(
    JSON.stringify({ scans: [...scans].sort(), rules: grouped }, null, 2),
  );
  process.exit(0);
}

const totalIssues = grouped.reduce((sum, r) => sum + r.total, 0);
const totalUnique = grouped.reduce((sum, r) => sum + r.uniqueElements, 0);

console.log(`Scans (${scans.size}): ${[...scans].sort().join(", ")}`);
console.log(
  `Issues: ${totalIssues} total, ${totalUnique} unique elements, ${grouped.length} rules\n`,
);

const header = ["rule", "total", "unique", "scans"];
const rows = grouped.map((r) => [
  r.ruleId,
  String(r.total),
  String(r.uniqueElements),
  r.scans.length === scans.size ? "all" : r.scans.join(", "),
]);

const widths = header.map((h, i) =>
  Math.max(h.length, ...rows.map((row) => row[i].length)),
);
const formatRow = (row) =>
  row.map((cell, i) => cell.padEnd(widths[i])).join("  ");

console.log(formatRow(header));
console.log(formatRow(widths.map((w) => "-".repeat(w))));
for (const row of rows) {
  console.log(formatRow(row));
}

console.log("\nDetails:");
for (const r of grouped) {
  console.log(`\n- ${r.ruleId} [${r.level}] (${r.help})`);
  for (const message of r.messages) {
    console.log(`    ${message}`);
  }
}
