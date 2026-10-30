import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  archivedDocsPath,
  buildComponentCatalog,
  buildLlmsFull,
  buildLlmsTxt,
  pageUrl,
  summaryFromBody,
  versionLabel,
  writeProseFiles,
} from "./llm-snapshot.mjs";

const docsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("version label keeps the release line", () => {
  assert.equal(versionLabel("1.14.0"), "1.14.x");
});

test("page urls follow the docs path", () => {
  assert.equal(pageUrl("https://docs.langflow.org", "", "/get-started-quickstart"), "https://docs.langflow.org/get-started-quickstart");
  assert.equal(pageUrl("https://docs.langflow.org", "", "/"), "https://docs.langflow.org");
  assert.equal(pageUrl("https://docs.langflow.org", "1.13.0", "/parser"), "https://docs.langflow.org/1.13.0/parser");
});

test("summary uses the first sentence", () => {
  const summary = summaryFromBody("# Title\n\nimport X from 'y';\n\nLangflow routes messages. It keeps going.\n\nNext paragraph.");
  assert.equal(summary, "Langflow routes messages.");
});

test("component catalog omits hidden fields and source code", () => {
  const catalog = buildComponentCatalog({
    version: "1.14.0",
    index: {
      version: "0.9.0",
      entries: [
        [
          "flow_controls",
          {
            ConditionalRouter: {
              display_name: "If-Else",
              description: "Routes a message.",
              legacy: false,
              field_order: ["input_text", "code", "hidden"],
              metadata: { component_class_name: "ConditionalRouterComponent", module: "lfx.components.flow_controls" },
              template: {
                input_text: { name: "input_text", display_name: "Text Input", type: "str", required: true, show: true, info: "Incoming text." },
                code: { name: "code", display_name: "Code", type: "code", show: true, info: "from lfx import secret" },
                hidden: { name: "hidden", display_name: "Hidden", type: "str", show: false, info: "nope" },
              },
              outputs: [{ name: "true_result", display_name: "True", types: ["Message"] }],
            },
          },
        ],
      ],
    },
  });

  const records = JSON.parse(catalog.json).components;
  assert.equal(records.length, 1);
  assert.equal(records[0].class_name, "ConditionalRouterComponent");
  assert.deepEqual(records[0].inputs.map((input) => input.name), ["input_text"]);
  assert.equal(records[0].outputs[0].name, "true_result");
  assert.equal(catalog.markdown.includes("from lfx import secret"), false);
  assert.equal(catalog.markdown.includes("Hidden"), false);
  assert.match(catalog.markdown, /If-Else \(`ConditionalRouterComponent`\)/);
});

test("llms files map sidebar pages and inline partials", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "langflow-llms-"));
  const versionDir = path.join(root, "versioned_docs", "version-1.14.0");
  fs.mkdirSync(versionDir, { recursive: true });
  fs.writeFileSync(
    path.join(versionDir, "_partial-note.mdx"),
    "Hidden parameters stay available in the component panel.\n",
  );
  fs.writeFileSync(
    path.join(versionDir, "guide.mdx"),
    `---
title: Install
slug: /install
---

import Note from "@site/docs/_partial-note.mdx";

Install Langflow, then start it.

<Note />

<Note />
`,
  );
  const sidebar = {
    docs: [
      { type: "html", value: "<div>Build</div>" },
      { type: "category", label: "Get started", items: [{ type: "doc", id: "guide", label: "Install Langflow" }] },
    ],
  };
  const sidebarPath = path.join(root, "sidebars.json");
  fs.writeFileSync(sidebarPath, JSON.stringify(sidebar));

  const llmsTxt = buildLlmsTxt({ version: "1.14.0", docsPath: "", versionDir, sidebar });
  assert.match(llmsTxt, /# Langflow 1\.14\.x/);
  assert.match(llmsTxt, /## Reference/);
  assert.match(llmsTxt, /https:\/\/docs\.langflow\.org\/llms\/1\.14\.0\/components\.md/);
  assert.match(llmsTxt, /https:\/\/docs\.langflow\.org\/llms\/1\.14\.0\/openapi\.json/);
  assert.match(llmsTxt, /## Build/);
  assert.match(llmsTxt, /### Get started/);
  assert.match(llmsTxt, /\[Install Langflow\]\(https:\/\/docs\.langflow\.org\/install\): Install Langflow, then start it\./);

  const llmsFull = buildLlmsFull({ version: "1.14.0", docsPath: "1.14.0", versionDir, sidebar });
  assert.match(llmsFull, /https:\/\/docs\.langflow\.org\/1\.14\.0\/install/);
  assert.equal(llmsFull.match(/Hidden parameters stay available/g)?.length, 2);
  assert.equal(llmsFull.includes("import Note"), false);

  const outputDir = path.join(root, "out");
  writeProseFiles({ version: "1.14.0", docsPath: "", versionDir, sidebarPath, outputDir });
  assert.equal(fs.existsSync(path.join(outputDir, "llms.txt")), true);
  assert.equal(fs.existsSync(path.join(outputDir, "llms-full.txt")), true);
});

test("an archived release is linked under its version path", () => {
  const docsPath = archivedDocsPath({ versions: { "1.13.0": { path: "" } } }, "1.13.0");
  assert.equal(docsPath, "1.13.0");
  assert.equal(archivedDocsPath({ versions: { "1.12.0": { path: "1.12.0" } } }, "1.12.0"), "1.12.0");
});

test("the released 1.13 sidebar resolves to published pages", () => {
  const version = "1.13.0";
  const versionDir = path.join(docsDir, "versioned_docs", `version-${version}`);
  const sidebar = JSON.parse(fs.readFileSync(path.join(docsDir, "versioned_sidebars", `version-${version}-sidebars.json`), "utf8"));
  const llmsTxt = buildLlmsTxt({ version, docsPath: "", versionDir, sidebar });
  assert.match(llmsTxt, /\[Quickstart\]\(https:\/\/docs\.langflow\.org\/get-started-quickstart\)/);
  assert.equal(llmsTxt.includes("docs/features"), false);
  assert.equal(llmsTxt.includes("versioned_docs"), false);
});
