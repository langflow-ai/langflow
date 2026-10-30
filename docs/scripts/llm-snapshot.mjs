import fs from "node:fs";
import path from "node:path";

const SITE_URL = "https://docs.langflow.org";
const TAGLINE =
  "Langflow is a low-code app builder for RAG and multi-agent AI applications.";

const SKIPPED_INPUTS = new Set(["code"]);

export function versionLabel(version) {
  const match = /^(\d+)\.(\d+)\.\d+$/.exec(version);
  return match ? `${match[1]}.${match[2]}.x` : version;
}

export function pageUrl(siteUrl, docsPath, slug) {
  const base = siteUrl.replace(/\/$/, "");
  const prefix = docsPath ? `/${String(docsPath).replace(/^\/|\/$/g, "")}` : "";
  const normalized = !slug || slug === "/" ? "/" : slug.startsWith("/") ? slug : `/${slug}`;
  if (normalized === "/") {
    return `${base}${prefix}`;
  }
  return `${base}${prefix}${normalized}`;
}

export function absoluteUrl(siteUrl, href) {
  if (!href) {
    return href;
  }
  if (/^https?:\/\//.test(href)) {
    return href;
  }
  const base = siteUrl.replace(/\/$/, "");
  return href.startsWith("/") ? `${base}${href}` : `${base}/${href}`;
}

function htmlText(value) {
  return String(value || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function walkSidebar(items, level, blocks) {
  for (const item of items || []) {
    if (typeof item === "string") {
      blocks.push({ type: "doc", id: item, label: null });
      continue;
    }
    if (item.type === "html") {
      const text = htmlText(item.value);
      if (text) {
        blocks.push({ type: "heading", level: 2, text });
      }
      continue;
    }
    if (item.type === "category") {
      blocks.push({ type: "heading", level, text: item.label });
      walkSidebar(item.items, Math.min(level + 1, 4), blocks);
      continue;
    }
    if (item.type === "link") {
      blocks.push({ type: "link", label: item.label, href: item.href });
      continue;
    }
    if (item.type === "doc" || item.id) {
      blocks.push({ type: "doc", id: item.id, label: item.label || null });
      continue;
    }
    throw new Error(`Unsupported sidebar item type: ${item.type || "unknown"}`);
  }
}

export function sidebarBlocks(sidebar) {
  const items = sidebar.docs || sidebar;
  const hasGroups = items.some((item) => item && item.type === "html");
  const blocks = [];
  walkSidebar(items, hasGroups ? 3 : 2, blocks);
  return blocks;
}

function splitFrontmatter(text) {
  if (!text.startsWith("---")) {
    return { data: {}, body: text };
  }
  const end = text.indexOf("\n---", 3);
  if (end === -1) {
    return { data: {}, body: text };
  }
  const data = {};
  for (const line of text.slice(4, end).split("\n")) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (match) {
      data[match[1]] = match[2].trim().replace(/^['"]|['"]$/g, "");
    }
  }
  return { data, body: text.slice(end + 4).replace(/^\n/, "") };
}

function parseImports(text) {
  const imports = [];
  const pattern = /import\s+(?:(\w+)|\{([^}]+)\})\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of text.matchAll(pattern)) {
    if (match[1]) {
      imports.push({ local: match[1], spec: match[3] });
    }
    if (match[2]) {
      for (const piece of match[2].split(",")) {
        const local = piece.trim().split(/\s+as\s+/).pop();
        if (local) {
          imports.push({ local, spec: match[3] });
        }
      }
    }
  }
  return imports;
}

function stripImports(text) {
  const lines = text.split("\n");
  const kept = [];
  let skipping = false;
  for (const line of lines) {
    if (!skipping && /^\s*import\s/.test(line)) {
      if (/from\s+['"][^'"]+['"]\s*;?\s*$/.test(line)) {
        continue;
      }
      skipping = true;
      continue;
    }
    if (skipping) {
      if (/from\s+['"][^'"]+['"]\s*;?\s*$/.test(line)) {
        skipping = false;
      }
      continue;
    }
    kept.push(line);
  }
  return kept.join("\n");
}

function findDocFile(versionDir, id) {
  const candidates = [`${id}.mdx`, `${id}.md`, path.join(id, "index.mdx"), path.join(id, "index.md")];
  for (const candidate of candidates) {
    const fullPath = path.join(versionDir, candidate);
    if (fs.existsSync(fullPath)) {
      return fullPath;
    }
  }
  throw new Error(`Sidebar doc not found in ${versionDir}: ${id}`);
}

function renderMarkdown(filePath, versionDir, stack) {
  if (stack.has(filePath)) {
    return "";
  }
  stack.add(filePath);
  try {
    const source = fs.readFileSync(filePath, "utf8");
    const imports = parseImports(source);
    let body = stripImports(splitFrontmatter(source).body);
    for (const imported of imports) {
      if (!imported.spec.startsWith("@site/docs/")) {
        continue;
      }
      const partialPath = path.join(versionDir, imported.spec.slice("@site/docs/".length));
      if (!fs.existsSync(partialPath)) {
        continue;
      }
      const partialSource = fs.readFileSync(partialPath, "utf8");
      if (partialSource.includes("export ")) {
        continue;
      }
      const partialBody = renderMarkdown(partialPath, versionDir, stack).trim();
      const tag = new RegExp(`<${imported.local}(\\s[^/>]*)?/>`, "g");
      body = body.replace(tag, partialBody);
    }
    return body.replace(/\n{3,}/g, "\n\n").trim();
  } finally {
    stack.delete(filePath);
  }
}

export function summaryFromBody(body) {
  const lines = body.split("\n");
  const paragraph = [];
  let started = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!started) {
      if (!trimmed || trimmed.startsWith("import ") || trimmed.startsWith("#") || trimmed.startsWith(":::") || trimmed.startsWith("<") || trimmed.startsWith("export ")) {
        continue;
      }
      started = true;
    } else if (!trimmed) {
      break;
    }
    paragraph.push(trimmed);
  }
  const text = paragraph.join(" ").replace(/\s+/g, " ").trim();
  const sentence = text.match(/^.*?[.!?](?:\s|$)/);
  const summary = (sentence ? sentence[0] : text).trim();
  if (summary.length <= 240) {
    return summary;
  }
  return `${summary.slice(0, 237).trimEnd()}...`;
}

function loadDoc(versionDir, id) {
  const filePath = findDocFile(versionDir, id);
  const source = fs.readFileSync(filePath, "utf8");
  const { data } = splitFrontmatter(source);
  const body = renderMarkdown(filePath, versionDir, new Set());
  return {
    title: data.title || id,
    slug: data.slug || `/${id}`,
    body,
    summary: summaryFromBody(body),
  };
}

function headingMarks(level) {
  return "#".repeat(Math.min(Math.max(level, 2), 4));
}

export function buildLlmsTxt({ version, docsPath, siteUrl = SITE_URL, versionDir, sidebar }) {
  const label = versionLabel(version);
  const lines = [
    `# Langflow ${label}`,
    "",
    `> ${TAGLINE} This file maps the ${label} documentation.`,
    "",
    "Generated from the docs version snapshot. Do not edit by hand.",
    "",
    "## Reference",
    "",
    `- [Component catalog](${pageUrl(siteUrl, `llms/${version}`, "/components.md")}): Component types, inputs, and outputs for Langflow ${label}.`,
    `- [OpenAPI specification](${pageUrl(siteUrl, `llms/${version}`, "/openapi.json")}): HTTP API for Langflow ${label}.`,
    "",
  ];

  for (const block of sidebarBlocks(sidebar)) {
    if (block.type === "heading") {
      if (lines.at(-1) !== "") {
        lines.push("");
      }
      lines.push(`${headingMarks(block.level)} ${block.text}`, "");
      continue;
    }
    if (block.type === "link") {
      lines.push(`- [${block.label}](${absoluteUrl(siteUrl, block.href)})`);
      continue;
    }
    const doc = loadDoc(versionDir, block.id);
    const title = block.label || doc.title;
    const summary = doc.summary ? `: ${doc.summary}` : "";
    lines.push(`- [${title}](${pageUrl(siteUrl, docsPath, doc.slug)})${summary}`);
  }

  return `${lines.join("\n").replace(/\n{3,}/g, "\n\n").trim()}\n`;
}

export function buildLlmsFull({ version, docsPath, siteUrl = SITE_URL, versionDir, sidebar }) {
  const label = versionLabel(version);
  const parts = [
    `# Langflow ${label}`,
    "",
    `Prose pages for the ${label} documentation.`,
    `Component catalog: ${pageUrl(siteUrl, `llms/${version}`, "/components.md")}`,
    `OpenAPI specification: ${pageUrl(siteUrl, `llms/${version}`, "/openapi.json")}`,
    "",
  ];

  for (const block of sidebarBlocks(sidebar)) {
    if (block.type === "heading") {
      if (parts.at(-1) !== "") {
        parts.push("");
      }
      parts.push(`${headingMarks(block.level)} ${block.text}`, "");
      continue;
    }
    if (block.type === "link") {
      parts.push(`- [${block.label}](${absoluteUrl(siteUrl, block.href)})`);
      continue;
    }
    const doc = loadDoc(versionDir, block.id);
    const title = block.label || doc.title;
    parts.push("---", "", `# ${title}`, "", pageUrl(siteUrl, docsPath, doc.slug), "", doc.body, "");
  }

  return `${parts.join("\n").trim()}\n`;
}

function asText(value, maxLength = 1000) {
  if (typeof value !== "string") {
    return "";
  }
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 3).trimEnd()}...`;
}

function escapeCell(value) {
  return asText(value).replace(/\|/g, "\\|");
}

function visibleInputs(component) {
  const template = component.template || {};
  const ordered = Array.isArray(component.field_order) ? component.field_order : [];
  const seen = new Set();
  const names = [...ordered, ...Object.keys(template)].filter((name) => {
    if (seen.has(name)) {
      return false;
    }
    seen.add(name);
    return true;
  });
  const inputs = [];
  for (const name of names) {
    const field = template[name];
    if (!field || typeof field !== "object" || name.startsWith("_") || SKIPPED_INPUTS.has(name) || field.show === false || field.type === "code") {
      continue;
    }
    inputs.push({
      name: field.name || name,
      display_name: field.display_name || name,
      type: field.type || field._input_type || "",
      input_types: Array.isArray(field.input_types) ? field.input_types : [],
      required: Boolean(field.required),
      advanced: Boolean(field.advanced),
      info: asText(field.info),
    });
  }
  return inputs;
}

function visibleOutputs(component) {
  if (!Array.isArray(component.outputs)) {
    return [];
  }
  return component.outputs.map((output) => ({
    name: output.name || "",
    display_name: output.display_name || output.name || "",
    types: Array.isArray(output.types) ? output.types : [],
  }));
}

export function componentRecords(index) {
  const records = [];
  for (const entry of index.entries || []) {
    const [category, components] = entry;
    if (!components || typeof components !== "object") {
      continue;
    }
    for (const [key, component] of Object.entries(components)) {
      if (!component || typeof component !== "object") {
        continue;
      }
      records.push({
        category,
        name: key,
        class_name: component.metadata?.component_class_name || key,
        display_name: component.display_name || key,
        description: asText(component.description),
        legacy: Boolean(component.legacy),
        beta: Boolean(component.beta),
        module: component.metadata?.module || "",
        inputs: visibleInputs(component),
        outputs: visibleOutputs(component),
      });
    }
  }
  return records;
}

function typeLabel(input) {
  if (input.input_types.length === 0) {
    return input.type;
  }
  return `${input.type}: ${input.input_types.join(", ")}`;
}

export function buildComponentCatalog({ version, index }) {
  const label = versionLabel(version);
  const records = componentRecords(index);
  const json = {
    docs_version: version,
    docs_label: label,
    index_version: index.version || "",
    components: records,
  };
  const lines = [
    `# Langflow ${label} components`,
    "",
    `Docs version: ${version}`,
    `Component index version: ${index.version || "unknown"}`,
    "",
    "Names, inputs, and outputs from the component index shipped with this release.",
    "",
  ];
  let category = "";
  for (const component of records) {
    if (component.category !== category) {
      category = component.category;
      lines.push(`## ${category}`, "");
    }
    lines.push(`### ${component.display_name} (\`${component.class_name}\`)`, "");
    if (component.description) {
      lines.push(component.description, "");
    }
    if (component.name !== component.class_name) {
      lines.push(`Index name: \`${component.name}\``, "");
    }
    if (component.module) {
      lines.push(`Module: \`${component.module}\``, "");
    }
    if (component.legacy) {
      lines.push("Legacy: yes", "");
    }
    if (component.beta) {
      lines.push("Beta: yes", "");
    }
    lines.push("#### Inputs", "");
    if (component.inputs.length === 0) {
      lines.push("None.", "");
    } else {
      lines.push("| Name | Display name | Type | Required | Advanced | Description |", "| --- | --- | --- | --- | --- | --- |");
      for (const input of component.inputs) {
        lines.push(`| \`${escapeCell(input.name)}\` | ${escapeCell(input.display_name)} | ${escapeCell(typeLabel(input))} | ${input.required ? "yes" : "no"} | ${input.advanced ? "yes" : "no"} | ${escapeCell(input.info)} |`);
      }
      lines.push("");
    }
    lines.push("#### Outputs", "");
    if (component.outputs.length === 0) {
      lines.push("None.", "");
    } else {
      lines.push("| Name | Display name | Types |", "| --- | --- | --- |");
      for (const output of component.outputs) {
        lines.push(`| \`${escapeCell(output.name)}\` | ${escapeCell(output.display_name)} | ${escapeCell(output.types.join(", "))} |`);
      }
      lines.push("");
    }
  }
  return {
    markdown: `${lines.join("\n").trim()}\n`,
    json: `${JSON.stringify(json, null, 2)}\n`,
  };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

export function writeProseFiles({ version, docsPath = "", siteUrl = SITE_URL, versionDir, sidebarPath, outputDir }) {
  const sidebar = readJson(sidebarPath);
  const llmsTxt = buildLlmsTxt({ version, docsPath, siteUrl, versionDir, sidebar });
  const llmsFull = buildLlmsFull({ version, docsPath, siteUrl, versionDir, sidebar });
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, "llms.txt"), llmsTxt);
  fs.writeFileSync(path.join(outputDir, "llms-full.txt"), llmsFull);
  return { llmsTxt, llmsFull };
}

export function writeComponentCatalog({ version, indexPath, outputDir }) {
  const catalog = buildComponentCatalog({ version, index: readJson(indexPath) });
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, "components.md"), catalog.markdown);
  fs.writeFileSync(path.join(outputDir, "components.json"), catalog.json);
}

export function docsPluginConfig(config) {
  for (const preset of config.presets || []) {
    if (preset?.[1]?.docs?.lastVersion) {
      return preset[1].docs;
    }
  }
  throw new Error("Could not find the docs preset in docusaurus.config.js");
}

export function archivedDocsPath(docsConfig, version) {
  const configured = docsConfig.versions?.[version]?.path ?? "";
  if (!configured || configured === "/") {
    return version;
  }
  return configured;
}
