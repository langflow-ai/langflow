// Builds a route-first HTML report from IBM accessibility-checker JSON output.
//
// Usage, from src/frontend after RUN_A11Y=true Playwright scans:
//   node tests/utils/build-a11y-html-report.mjs

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

function resolveReportsDir() {
  const candidates = [
    path.resolve(process.cwd(), "coverage/accessibility-reports"),
    path.resolve(process.cwd(), "src/frontend/coverage/accessibility-reports"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? candidates[0];
}

const REPORTS_DIR = resolveReportsDir();
const OUTPUT_FILE = path.join(REPORTS_DIR, "index.html");
const SUMMARY_FILE = path.join(REPORTS_DIR, "route-summary.json");
function resolveRouteManifestPath() {
  const candidates = [
    path.resolve(process.cwd(), "../../scripts/a11y/a11y_routes.json"),
    path.resolve(process.cwd(), "scripts/a11y/a11y_routes.json"),
  ];
  const manifestPath = candidates.find((candidate) => existsSync(candidate));
  if (!manifestPath) {
    throw new Error(
      `Could not find scripts/a11y/a11y_routes.json from ${process.cwd()}`,
    );
  }
  return manifestPath;
}

const ROUTE_MANIFEST_FILE = resolveRouteManifestPath();

function readRouteManifest() {
  const manifest = JSON.parse(readFileSync(ROUTE_MANIFEST_FILE, "utf8"));
  return new Map(
    (manifest.static ?? []).map((route) => [
      `route-${route.id}`,
      {
        path: route.path,
        surface: route.surface,
      },
    ]),
  );
}

const routeLabelMap = readRouteManifest();

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function routeFromLabel(label) {
  const shortLabel = label.replace(/^.*__/, "");
  return routeLabelMap.get(shortLabel)?.path ?? shortLabel;
}

function surfaceFromLabel(label) {
  const shortLabel = label.replace(/^.*__/, "");
  return routeLabelMap.get(shortLabel)?.surface ?? "";
}

function compactSnippet(snippet) {
  return String(snippet ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

function getIssueTarget(issue) {
  const snippet = compactSnippet(issue.snippet);
  const testIdMatch = snippet.match(/data-testid="([^"]+)"/);
  const ariaLabelMatch = snippet.match(/aria-label="([^"]+)"/);
  const roleMatch = snippet.match(/role="([^"]+)"/);

  if (testIdMatch) return `[data-testid="${testIdMatch[1]}"]`;
  if (ariaLabelMatch) return `[aria-label="${ariaLabelMatch[1]}"]`;
  if (roleMatch) return `[role="${roleMatch[1]}"]`;
  return issue.path?.aria ?? issue.path?.dom ?? "unknown element";
}

function readReports() {
  let files;
  try {
    files = readdirSync(REPORTS_DIR).filter(
      (file) =>
        file.endsWith(".json") &&
        file !== "summary.json" &&
        file !== "route-summary.json",
    );
  } catch {
    throw new Error(`No reports directory at ${REPORTS_DIR}`);
  }

  return files
    .map((file) => {
      const report = JSON.parse(
        readFileSync(path.join(REPORTS_DIR, file), "utf8"),
      );
      const label = report.label ?? file.replace(/\.json$/, "");
      const issues = (report.results ?? [])
        .filter(
          (issue) =>
            !issue.ignored &&
            (issue.level === "violation" ||
              issue.level === "potentialviolation"),
        )
        .map((issue, index) => ({
          index: index + 1,
          ruleId: issue.ruleId ?? "unknown_rule",
          level: issue.level ?? "unknown",
          message: issue.message ?? "",
          target: getIssueTarget(issue),
          domPath: issue.path?.dom ?? "",
          ariaPath: issue.path?.aria ?? "",
          snippet: compactSnippet(issue.snippet),
          help: issue.help?.split("#")[0] ?? "",
          bounds: issue.bounds ?? null,
        }));

      const rules = new Map();
      for (const issue of issues) {
        rules.set(issue.ruleId, (rules.get(issue.ruleId) ?? 0) + 1);
      }

      return {
        file,
        htmlFile: file.replace(/\.json$/, ".html"),
        label,
        route: routeFromLabel(label),
        surface: surfaceFromLabel(label),
        issues,
        rules: [...rules.entries()]
          .map(([ruleId, count]) => ({ ruleId, count }))
          .sort(
            (a, b) => b.count - a.count || a.ruleId.localeCompare(b.ruleId),
          ),
      };
    })
    .sort((a, b) => a.route.localeCompare(b.route));
}

function groupByRule(routes) {
  const rules = new Map();

  for (const route of routes) {
    for (const issue of route.issues) {
      let rule = rules.get(issue.ruleId);
      if (!rule) {
        rule = {
          ruleId: issue.ruleId,
          count: 0,
          routes: new Map(),
          messages: new Set(),
          help: issue.help,
        };
        rules.set(issue.ruleId, rule);
      }
      rule.count += 1;
      rule.routes.set(route.route, (rule.routes.get(route.route) ?? 0) + 1);
      rule.messages.add(issue.message);
    }
  }

  return [...rules.values()]
    .map((rule) => ({
      ruleId: rule.ruleId,
      count: rule.count,
      routes: [...rule.routes.entries()]
        .map(([route, count]) => ({ route, count }))
        .sort((a, b) => b.count - a.count || a.route.localeCompare(b.route)),
      messages: [...rule.messages],
      help: rule.help,
    }))
    .sort((a, b) => b.count - a.count || a.ruleId.localeCompare(b.ruleId));
}

function renderRoute(route) {
  const issuesByRule = new Map();
  for (const issue of route.issues) {
    const group = issuesByRule.get(issue.ruleId) ?? [];
    group.push(issue);
    issuesByRule.set(issue.ruleId, group);
  }

  const ruleGroups = [...issuesByRule.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .map(
      ([ruleId, issues]) => `
        <details class="rule">
          <summary>
            <span class="rule-name">${escapeHtml(ruleId)}</span>
            <span class="count">${issues.length}</span>
          </summary>
          <div class="issue-list">
            ${issues.map(renderIssue).join("")}
          </div>
        </details>
      `,
    )
    .join("");

  return `
    <details class="route" open>
      <summary>
        <span class="route-name">${escapeHtml(route.route)}${route.surface ? ` <span class="surface">${escapeHtml(route.surface)}</span>` : ""}</span>
        <span class="count">${route.issues.length}</span>
      </summary>
      <div class="route-meta">
        <a href="${escapeHtml(route.htmlFile)}">Open IBM HTML</a>
        <a href="${escapeHtml(route.file)}">Open raw JSON</a>
      </div>
      ${ruleGroups || '<p class="empty">No violations.</p>'}
    </details>
  `;
}

function renderIssue(issue) {
  const bounds = issue.bounds
    ? `x=${issue.bounds.left}, y=${issue.bounds.top}, w=${issue.bounds.width}, h=${issue.bounds.height}`
    : "";

  return `
    <article class="issue">
      <div class="issue-head">
        <span class="badge">${escapeHtml(issue.level)}</span>
        ${issue.help ? `<a href="${escapeHtml(issue.help)}">IBM rule</a>` : ""}
      </div>
      <p class="message">${escapeHtml(issue.message)}</p>
      <dl>
        <dt>Target</dt>
        <dd><code>${escapeHtml(issue.target)}</code></dd>
        ${issue.domPath ? `<dt>DOM path</dt><dd><code>${escapeHtml(issue.domPath)}</code></dd>` : ""}
        ${issue.ariaPath ? `<dt>ARIA path</dt><dd><code>${escapeHtml(issue.ariaPath)}</code></dd>` : ""}
        ${bounds ? `<dt>Bounds</dt><dd><code>${escapeHtml(bounds)}</code></dd>` : ""}
        <dt>Snippet</dt>
        <dd><pre>${escapeHtml(issue.snippet)}</pre></dd>
      </dl>
    </article>
  `;
}

function renderRuleSummary(rule) {
  return `
    <tr>
      <td><a href="${escapeHtml(rule.help)}">${escapeHtml(rule.ruleId)}</a></td>
      <td>${rule.count}</td>
      <td>${rule.routes
        .map((route) => `${escapeHtml(route.route)} (${route.count})`)
        .join(", ")}</td>
    </tr>
  `;
}

function renderHtml(routes, rules) {
  const totalIssues = routes.reduce(
    (sum, route) => sum + route.issues.length,
    0,
  );
  const generatedAt = new Date().toISOString();

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Langflow Accessibility Report</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #d1d5db;
      --accent: #2563eb;
      --danger: #b91c1c;
      --code: #f3f4f6;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111827;
        --panel: #1f2937;
        --text: #f9fafb;
        --muted: #9ca3af;
        --border: #374151;
        --accent: #60a5fa;
        --danger: #f87171;
        --code: #111827;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    header, main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { padding-bottom: 8px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { margin: 28px 0 12px; font-size: 18px; }
    a { color: var(--accent); }
    .muted { color: var(--muted); }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .stat, details, table {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .stat { padding: 16px; }
    .stat strong { display: block; font-size: 24px; }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    details { margin-bottom: 12px; }
    summary {
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 16px;
      font-weight: 650;
    }
    .route > summary { font-size: 18px; }
    .surface {
      display: inline-block;
      margin-left: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 400;
    }
    .rule { margin: 10px 16px; background: transparent; }
    .rule > summary { font-size: 14px; }
    .count {
      min-width: 34px;
      border-radius: 999px;
      background: var(--danger);
      color: white;
      padding: 2px 10px;
      text-align: center;
      font-size: 12px;
    }
    .route-meta {
      display: flex;
      gap: 16px;
      padding: 0 16px 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .issue-list { padding: 0 14px 14px; }
    .issue {
      border-top: 1px solid var(--border);
      padding: 14px 2px;
    }
    .issue:first-child { border-top: 0; }
    .issue-head { display: flex; gap: 10px; align-items: center; }
    .badge {
      color: var(--danger);
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 12px;
      font-weight: 650;
    }
    .message { margin: 8px 0 10px; }
    dl {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 8px 12px;
      margin: 0;
    }
    dt { color: var(--muted); font-size: 13px; }
    dd { margin: 0; min-width: 0; }
    code, pre {
      background: var(--code);
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }
    code { padding: 2px 5px; }
    pre {
      margin: 0;
      padding: 10px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .empty { padding: 0 16px 16px; color: var(--muted); }
  </style>
</head>
<body>
  <header>
    <h1>Langflow Accessibility Report</h1>
    <p class="muted">Generated ${escapeHtml(generatedAt)} from IBM accessibility-checker JSON reports.</p>
    <div class="stats">
      <div class="stat"><strong>${routes.length}</strong> routes scanned</div>
      <div class="stat"><strong>${totalIssues}</strong> issues</div>
      <div class="stat"><strong>${rules.length}</strong> rules</div>
    </div>
  </header>
  <main>
    <h2>Rules Summary</h2>
    <table>
      <thead>
        <tr><th>Rule</th><th>Issues</th><th>Routes</th></tr>
      </thead>
      <tbody>
        ${rules.map(renderRuleSummary).join("")}
      </tbody>
    </table>
    <h2>Issues By Route</h2>
    ${routes.map(renderRoute).join("")}
  </main>
</body>
</html>`;
}

const routes = readReports();
const rules = groupByRule(routes);
const summary = {
  generatedAt: new Date().toISOString(),
  routeCount: routes.length,
  issueCount: routes.reduce((sum, route) => sum + route.issues.length, 0),
  ruleCount: rules.length,
  routes: routes.map((route) => ({
    route: route.route,
    surface: route.surface,
    label: route.label,
    issueCount: route.issues.length,
    rules: route.rules,
    htmlFile: route.htmlFile,
    jsonFile: route.file,
  })),
  rules,
};

writeFileSync(SUMMARY_FILE, `${JSON.stringify(summary, null, 2)}\n`);
writeFileSync(OUTPUT_FILE, renderHtml(routes, rules));

process.stdout.write(`Wrote ${path.relative(process.cwd(), OUTPUT_FILE)}\n`);
process.stdout.write(`Wrote ${path.relative(process.cwd(), SUMMARY_FILE)}\n`);
