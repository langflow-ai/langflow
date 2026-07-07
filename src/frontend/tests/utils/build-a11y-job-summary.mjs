// Builds a compact GitHub Actions summary from route-summary.json.
//
// Usage, from src/frontend after npm run a11y:html-report:
//   node tests/utils/build-a11y-job-summary.mjs

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

function resolveReportsDir() {
  const candidates = [
    path.resolve(process.cwd(), "coverage/accessibility-reports"),
    path.resolve(process.cwd(), "src/frontend/coverage/accessibility-reports"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? candidates[0];
}

const summaryPath = path.join(resolveReportsDir(), "route-summary.json");

function escapeCell(value) {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replaceAll("\n", " ");
}

// Show the actionable (non-suppressed) rules for a route; these are the ones a
// feature owner needs to fix. Suppressed chrome/framework rules are counted
// separately in the "Suppressed" column.
function renderActionableRules(rules, limit = 3) {
  const actionable = (rules ?? []).filter((rule) => !rule.suppressed);
  if (!actionable.length) return "none";
  const shown = actionable
    .slice(0, limit)
    .map((rule) => `\`${rule.ruleId}\` (${rule.count})`)
    .join(", ");
  const hidden = actionable.length - limit;
  return hidden > 0 ? `${shown}, +${hidden}` : shown;
}

function renderRouteTable(routes) {
  return [
    "| Route | Surface | Actionable | Suppressed | Top actionable rules |",
    "| --- | --- | ---: | ---: | --- |",
    ...routes.map(
      (route) =>
        `| \`${escapeCell(route.route)}\` | ${escapeCell(route.surface)} | ${route.actionableIssueCount ?? route.issueCount} | ${route.suppressedIssueCount ?? 0} | ${renderActionableRules(route.rules)} |`,
    ),
  ].join("\n");
}

function renderRuleTable(rules) {
  return [
    "| Rule | Issues | Suppressed | Top routes |",
    "| --- | ---: | :---: | --- |",
    ...rules.slice(0, 10).map((rule) => {
      const topRoutes = rule.routes
        .slice(0, 5)
        .map((route) => `\`${route.route}\` (${route.count})`)
        .join(", ");
      const hidden = rule.routes.length - 5;
      const routes = hidden > 0 ? `${topRoutes}, +${hidden}` : topRoutes;
      return `| \`${escapeCell(rule.ruleId)}\` | ${rule.count} | ${rule.suppressed ? "yes" : "—"} | ${routes} |`;
    }),
  ].join("\n");
}

if (!existsSync(summaryPath)) {
  throw new Error(
    `No route summary at ${summaryPath}. Run npm run a11y:html-report first.`,
  );
}

const summary = JSON.parse(readFileSync(summaryPath, "utf8"));

const actionableOf = (route) =>
  route.actionableIssueCount ?? route.issueCount ?? 0;

const routesByIssues = [...summary.routes].sort(
  (a, b) => actionableOf(b) - actionableOf(a) || a.route.localeCompare(b.route),
);

const worstRoutes = routesByIssues.slice(0, 10);
const remainingRoutes = routesByIssues.slice(10);

// Actionable rules first (route-summary already sorts them that way), then the
// suppressed chrome/framework rules.
const actionableRules = summary.rules.filter((rule) => !rule.suppressed);

const totalIssues = summary.issueCount;
const actionableIssues = summary.actionableIssueCount ?? totalIssues;
const suppressedIssues = summary.suppressedIssueCount ?? 0;

const lines = [
  `Generated: \`${summary.generatedAt}\``,
  "",
  "| Routes scanned | Actionable issues | Suppressed | Total issues | Rules |",
  "| ---: | ---: | ---: | ---: | ---: |",
  `| ${summary.routeCount} | ${actionableIssues} | ${suppressedIssues} | ${totalIssues} | ${summary.ruleCount} |`,
  "",
  "> Suppressed = findings owned by shared app chrome or third-party widgets",
  "> (see `tests/a11y/a11y-ignore-rules.json`). Focus on actionable issues.",
  "",
  "### Worst Routes (by actionable issues)",
  "",
  renderRouteTable(worstRoutes),
  "",
  "<details>",
  "<summary>All scanned routes</summary>",
  "",
  renderRouteTable(routesByIssues),
  "",
  "</details>",
  "",
  "### Top Actionable Rules",
  "",
  actionableRules.length > 0
    ? renderRuleTable(actionableRules)
    : "_No actionable rules — all findings are suppressed chrome/framework issues._",
];

if (remainingRoutes.length > 0) {
  lines.splice(
    9,
    0,
    `Showing top ${worstRoutes.length} routes by actionable issue count. Expand all routes for the remaining ${remainingRoutes.length}.`,
    "",
  );
}

process.stdout.write(`${lines.join("\n")}\n`);
