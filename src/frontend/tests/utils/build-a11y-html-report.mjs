// Builds a scan-first HTML report from IBM accessibility-checker JSON output.
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

// Labels come from buildA11yScanLabel as `<project>__<label>[__<scanIndex>]`,
// so strip only the leading project segment and the optional numeric suffix.
function shortLabelFrom(label) {
  return label.replace(/^.*?__/, "").replace(/__\d+$/, "");
}

function routeFromLabel(label) {
  const shortLabel = shortLabelFrom(label);
  return routeLabelMap.get(shortLabel)?.path ?? shortLabel;
}

function surfaceFromLabel(label) {
  const shortLabel = shortLabelFrom(label);
  return routeLabelMap.get(shortLabel)?.surface ?? "";
}

// Manifest-backed labels (`route-<id>`) are static routes; everything else is
// a stateful UI scan driven by a Playwright spec (modal, toast, dark, mobile...).
function scanKindFromLabel(label) {
  return routeLabelMap.has(shortLabelFrom(label)) ? "route" : "state";
}

function variantsFromLabel(label) {
  const shortLabel = shortLabelFrom(label);
  const variants = [];
  if (/(^|-)dark($|-)/.test(shortLabel)) variants.push("dark");
  if (/(^|-)mobile($|-)/.test(shortLabel)) variants.push("mobile");
  return variants;
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

      const suppressedViolationCount = (report.results ?? []).filter(
        (issue) => issue.ignored && issue.level === "violation",
      ).length;

      const rules = new Map();
      for (const issue of issues) {
        rules.set(issue.ruleId, (rules.get(issue.ruleId) ?? 0) + 1);
      }

      return {
        file,
        htmlFile: file.replace(/\.json$/, ".html"),
        anchor: `scan-${file.replace(/\.json$/, "").replace(/[^\w-]+/g, "-")}`,
        label,
        route: routeFromLabel(label),
        surface: surfaceFromLabel(label),
        kind: scanKindFromLabel(label),
        variants: variantsFromLabel(label),
        issues,
        violationCount: issues.filter((issue) => issue.level === "violation")
          .length,
        suppressedViolationCount,
        potentialCount: issues.filter(
          (issue) => issue.level === "potentialviolation",
        ).length,
        rules: [...rules.entries()]
          .map(([ruleId, count]) => ({ ruleId, count }))
          .sort(
            (a, b) => b.count - a.count || a.ruleId.localeCompare(b.ruleId),
          ),
      };
    })
    .sort(
      (a, b) =>
        b.issues.length - a.issues.length || a.route.localeCompare(b.route),
    );
}

function groupByRule(scans) {
  const rules = new Map();

  for (const scan of scans) {
    for (const issue of scan.issues) {
      let rule = rules.get(issue.ruleId);
      if (!rule) {
        rule = {
          ruleId: issue.ruleId,
          count: 0,
          routes: new Map(),
          anchors: new Map(),
          messages: new Set(),
          help: issue.help,
        };
        rules.set(issue.ruleId, rule);
      }
      rule.count += 1;
      rule.routes.set(scan.route, (rule.routes.get(scan.route) ?? 0) + 1);
      rule.anchors.set(scan.route, scan.anchor);
      rule.messages.add(issue.message);
    }
  }

  return [...rules.values()]
    .map((rule) => ({
      ruleId: rule.ruleId,
      count: rule.count,
      routes: [...rule.routes.entries()]
        .map(([route, count]) => ({
          route,
          count,
          anchor: rule.anchors.get(route),
        }))
        .sort((a, b) => b.count - a.count || a.route.localeCompare(b.route)),
      messages: [...rule.messages],
      help: rule.help,
    }))
    .sort((a, b) => b.count - a.count || a.ruleId.localeCompare(b.ruleId));
}

function renderVariantBadges(scan) {
  return scan.variants
    .map((variant) => `<span class="variant">${escapeHtml(variant)}</span>`)
    .join("");
}

function renderScanName(scan) {
  const kind = scan.kind === "route" ? "route" : "state";
  return `
    <span class="scan-name">
      ${escapeHtml(scan.route)}
      <span class="kind kind-${kind}">${kind}</span>
      ${renderVariantBadges(scan)}
      ${scan.surface ? `<span class="surface">${escapeHtml(scan.surface)}</span>` : ""}
    </span>
  `;
}

function renderFailingScan(scan) {
  const issuesByRule = new Map();
  for (const issue of scan.issues) {
    const group = issuesByRule.get(issue.ruleId) ?? [];
    group.push(issue);
    issuesByRule.set(issue.ruleId, group);
  }

  const ruleGroups = [...issuesByRule.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .map(
      ([ruleId, issues]) => `
        <details class="rule" open>
          <summary>
            <span class="rule-name">${escapeHtml(ruleId)}</span>
            <span class="count danger">${issues.length}</span>
          </summary>
          <div class="issue-list">
            ${issues.map(renderIssue).join("")}
          </div>
        </details>
      `,
    )
    .join("");

  return `
    <details class="scan" id="${escapeHtml(scan.anchor)}" data-filter="${escapeHtml(
      `${scan.route} ${scan.surface} ${scan.rules.map((rule) => rule.ruleId).join(" ")}`.toLowerCase(),
    )}" open>
      <summary>
        ${renderScanName(scan)}
        <span class="summary-counts">
          ${scan.violationCount ? `<span class="count danger">${scan.violationCount} violation${scan.violationCount === 1 ? "" : "s"}</span>` : ""}
          ${scan.potentialCount ? `<span class="count warn">${scan.potentialCount} potential</span>` : ""}
        </span>
      </summary>
      <div class="scan-meta">
        <a href="${escapeHtml(scan.htmlFile)}">Open IBM HTML</a>
        <a href="${escapeHtml(scan.file)}">Open raw JSON</a>
      </div>
      ${ruleGroups}
    </details>
  `;
}

function renderIssue(issue) {
  const bounds = issue.bounds
    ? `x=${issue.bounds.left}, y=${issue.bounds.top}, w=${issue.bounds.width}, h=${issue.bounds.height}`
    : "";
  const levelClass = issue.level === "violation" ? "danger" : "warn";

  return `
    <article class="issue">
      <div class="issue-head">
        <span class="badge ${levelClass}">${escapeHtml(issue.level)}</span>
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

function renderCleanScanRow(scan) {
  return `
    <tr data-filter="${escapeHtml(`${scan.route} ${scan.surface}`.toLowerCase())}">
      <td>${renderScanName(scan)}</td>
      <td class="links">
        <a href="${escapeHtml(scan.htmlFile)}">IBM HTML</a>
        <a href="${escapeHtml(scan.file)}">JSON</a>
      </td>
    </tr>
  `;
}

function renderRuleSummary(rule) {
  return `
    <tr>
      <td><a href="${escapeHtml(rule.help)}">${escapeHtml(rule.ruleId)}</a></td>
      <td>${rule.count}</td>
      <td>${rule.routes
        .map(
          (route) =>
            `<a href="#${escapeHtml(route.anchor)}">${escapeHtml(route.route)}</a> (${route.count})`,
        )
        .join(", ")}</td>
    </tr>
  `;
}

function renderHtml(scans, rules) {
  const failingScans = scans.filter((scan) => scan.issues.length > 0);
  const cleanScans = scans.filter((scan) => scan.issues.length === 0);
  const routeScans = scans.filter((scan) => scan.kind === "route");
  const totalIssues = scans.reduce((sum, scan) => sum + scan.issues.length, 0);
  const totalViolations = scans.reduce(
    (sum, scan) => sum + scan.violationCount,
    0,
  );
  const totalPotential = scans.reduce(
    (sum, scan) => sum + scan.potentialCount,
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
      --warn: #b45309;
      --ok: #15803d;
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
        --warn: #fbbf24;
        --ok: #4ade80;
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
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
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
    .stat .detail { display: block; margin-top: 4px; color: var(--muted); font-size: 13px; }
    .stat.ok strong { color: var(--ok); }
    .stat.danger strong { color: var(--danger); }
    .filter-bar { margin-top: 18px; }
    .filter-bar input[type="search"] {
      width: 100%;
      max-width: 420px;
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    tr:last-child td { border-bottom: 0; }
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
    .scan > summary { font-size: 17px; }
    .scan-name { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
    .surface {
      color: var(--muted);
      font-size: 13px;
      font-weight: 400;
    }
    .kind, .variant {
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 500;
      padding: 1px 8px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .kind-route { color: var(--accent); border-color: currentColor; }
    .rule { margin: 10px 16px; background: transparent; }
    .rule > summary { font-size: 14px; }
    .summary-counts { display: inline-flex; gap: 6px; flex-shrink: 0; }
    .count {
      min-width: 34px;
      border-radius: 999px;
      padding: 2px 10px;
      text-align: center;
      font-size: 12px;
      white-space: nowrap;
      color: var(--muted);
      border: 1px solid var(--border);
    }
    .count.danger { background: var(--danger); border-color: var(--danger); color: white; }
    .count.warn { background: var(--warn); border-color: var(--warn); color: white; }
    .scan-meta {
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
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 12px;
      font-weight: 650;
    }
    .badge.danger { color: var(--danger); }
    .badge.warn { color: var(--warn); }
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
    .links a { margin-right: 12px; }
    .empty { padding: 12px 16px; color: var(--muted); }
    .hidden { display: none; }
  </style>
</head>
<body>
  <header>
    <h1>Langflow Accessibility Report</h1>
    <p class="muted">Generated ${escapeHtml(generatedAt)} from IBM accessibility-checker JSON reports.</p>
    <div class="stats">
      <div class="stat">
        <strong>${scans.length}</strong> scans
        <span class="detail">${routeScans.length} static routes · ${scans.length - routeScans.length} UI states</span>
      </div>
      <div class="stat ${failingScans.length ? "danger" : "ok"}">
        <strong>${failingScans.length}</strong> scans with issues
        <span class="detail">${cleanScans.length} clean</span>
      </div>
      <div class="stat ${totalIssues ? "danger" : "ok"}">
        <strong>${totalIssues}</strong> issues
        <span class="detail">${totalViolations} violations · ${totalPotential} potential</span>
      </div>
      <div class="stat">
        <strong>${rules.length}</strong> rules
      </div>
    </div>
    <div class="filter-bar">
      <input id="scan-filter" type="search" placeholder="Filter scans by name, surface, or rule id…" aria-label="Filter scans">
    </div>
  </header>
  <main>
    <h2>Rules Summary</h2>
    <table>
      <thead>
        <tr><th>Rule</th><th>Issues</th><th>Scans</th></tr>
      </thead>
      <tbody>
        ${rules.map(renderRuleSummary).join("") || '<tr><td colspan="3" class="empty">No violations.</td></tr>'}
      </tbody>
    </table>
    <h2>Scans With Issues</h2>
    <section id="failing-scans">
      ${failingScans.map(renderFailingScan).join("") || '<p class="empty">No scans with violations.</p>'}
    </section>
    <h2>Clean Scans</h2>
    <details id="clean-scans">
      <summary>
        <span>Clean scans</span>
        <span class="count" id="clean-count">${cleanScans.length}</span>
      </summary>
      <table>
        <thead>
          <tr><th>Scan</th><th>Reports</th></tr>
        </thead>
        <tbody>
          ${cleanScans.map(renderCleanScanRow).join("")}
        </tbody>
      </table>
    </details>
  </main>
  <script>
    const filterInput = document.getElementById("scan-filter");
    const cleanDetails = document.getElementById("clean-scans");
    const cleanCount = document.getElementById("clean-count");
    const targets = [...document.querySelectorAll("[data-filter]")];
    const totalClean = ${cleanScans.length};

    filterInput.addEventListener("input", () => {
      const query = filterInput.value.trim().toLowerCase();
      let visibleClean = 0;
      for (const target of targets) {
        const matches = !query || target.dataset.filter.includes(query);
        target.classList.toggle("hidden", !matches);
        if (matches && target.tagName === "TR") visibleClean += 1;
      }
      cleanCount.textContent = query ? visibleClean + " / " + totalClean : totalClean;
      if (query && visibleClean > 0) cleanDetails.open = true;
    });
  </script>
</body>
</html>`;
}

const scans = readReports();
const rules = groupByRule(scans);
const summary = {
  generatedAt: new Date().toISOString(),
  scanCount: scans.length,
  routeCount: scans.length,
  staticRouteCount: scans.filter((scan) => scan.kind === "route").length,
  scansWithIssues: scans.filter((scan) => scan.issues.length > 0).length,
  issueCount: scans.reduce((sum, scan) => sum + scan.issues.length, 0),
  violationCount: scans.reduce((sum, scan) => sum + scan.violationCount, 0),
  // Raw = actionable + baseline-suppressed. Publish these three numbers together,
  // straight from this file; never hand-compute the split from baseline *files*
  // (one baseline file can suppress several results).
  baselineSuppressedCount: scans.reduce(
    (sum, scan) => sum + scan.suppressedViolationCount,
    0,
  ),
  rawViolationCount: scans.reduce(
    (sum, scan) => sum + scan.violationCount + scan.suppressedViolationCount,
    0,
  ),
  potentialViolationCount: scans.reduce(
    (sum, scan) => sum + scan.potentialCount,
    0,
  ),
  ruleCount: rules.length,
  routes: scans.map((scan) => ({
    route: scan.route,
    surface: scan.surface,
    kind: scan.kind,
    variants: scan.variants,
    label: scan.label,
    issueCount: scan.issues.length,
    violationCount: scan.violationCount,
    suppressedViolationCount: scan.suppressedViolationCount,
    potentialViolationCount: scan.potentialCount,
    rules: scan.rules,
    htmlFile: scan.htmlFile,
    jsonFile: scan.file,
  })),
  rules: rules.map((rule) => ({
    ruleId: rule.ruleId,
    count: rule.count,
    routes: rule.routes.map(({ route, count }) => ({ route, count })),
    messages: rule.messages,
    help: rule.help,
  })),
};

writeFileSync(SUMMARY_FILE, `${JSON.stringify(summary, null, 2)}\n`);
writeFileSync(OUTPUT_FILE, renderHtml(scans, rules));

process.stdout.write(`Wrote ${path.relative(process.cwd(), OUTPUT_FILE)}\n`);
process.stdout.write(`Wrote ${path.relative(process.cwd(), SUMMARY_FILE)}\n`);
