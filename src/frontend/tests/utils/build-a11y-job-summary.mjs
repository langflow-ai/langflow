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

function renderRules(rules, limit = 3) {
  if (!rules?.length) return "none";
  const shown = rules
    .slice(0, limit)
    .map((rule) => `\`${rule.ruleId}\` (${rule.count})`)
    .join(", ");
  const hidden = rules.length - limit;
  return hidden > 0 ? `${shown}, +${hidden}` : shown;
}

function renderRouteTable(routes) {
  return [
    "| Route | Surface | Issues | Top rules |",
    "| --- | --- | ---: | --- |",
    ...routes.map(
      (route) =>
        `| \`${escapeCell(route.route)}\` | ${escapeCell(route.surface)} | ${route.issueCount} | ${renderRules(route.rules)} |`,
    ),
  ].join("\n");
}

function renderRuleTable(rules) {
  return [
    "| Rule | Issues | Top routes |",
    "| --- | ---: | --- |",
    ...rules.slice(0, 10).map((rule) => {
      const topRoutes = rule.routes
        .slice(0, 5)
        .map((route) => `\`${route.route}\` (${route.count})`)
        .join(", ");
      const hidden = rule.routes.length - 5;
      const routes = hidden > 0 ? `${topRoutes}, +${hidden}` : topRoutes;
      return `| \`${escapeCell(rule.ruleId)}\` | ${rule.count} | ${routes} |`;
    }),
  ].join("\n");
}

if (!existsSync(summaryPath)) {
  throw new Error(
    `No route summary at ${summaryPath}. Run npm run a11y:html-report first.`,
  );
}

const summary = JSON.parse(readFileSync(summaryPath, "utf8"));
const routesByIssues = [...summary.routes].sort(
  (a, b) => b.issueCount - a.issueCount || a.route.localeCompare(b.route),
);

const worstRoutes = routesByIssues.slice(0, 10);
const remainingRoutes = routesByIssues.slice(10);

const lines = [
  `Generated: \`${summary.generatedAt}\``,
  "",
  "| Routes scanned | Issues | Rules |",
  "| ---: | ---: | ---: |",
  `| ${summary.routeCount} | ${summary.issueCount} | ${summary.ruleCount} |`,
  "",
  "### Worst Routes",
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
  "### Top Rules",
  "",
  renderRuleTable(summary.rules),
];

if (remainingRoutes.length > 0) {
  lines.splice(
    8,
    0,
    `Showing top ${worstRoutes.length} routes by issue count. Expand all routes for the remaining ${remainingRoutes.length}.`,
    "",
  );
}

process.stdout.write(`${lines.join("\n")}\n`);
