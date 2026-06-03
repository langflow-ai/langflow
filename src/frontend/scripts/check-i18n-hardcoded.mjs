#!/usr/bin/env node
import { appendFileSync, readFileSync } from "node:fs";
import ts from "typescript";

// Only attributes shown to humans; structural attrs (className, id, href...) are excluded to avoid noise.
const USER_FACING_ATTRS = new Set([
  "placeholder",
  "title",
  "alt",
  "label",
  "aria-label",
  "aria-description",
  "aria-placeholder",
  "aria-roledescription",
  "description",
  "tooltip",
  "tooltiptext",
  "subtitle",
  "heading",
  "header",
  "caption",
  "summary",
  "emptymessage",
  "helpertext",
  "errortext",
  "message",
]);

// Elements whose text content is code/markup, not translatable copy.
const NO_TRANSLATE_TAGS = new Set(["code", "pre", "style", "script"]);

const IGNORE_LINE = "i18n-ignore";
const IGNORE_FILE = "i18n-ignore-file";

const stripNonText = (value) =>
  value
    .replace(/&[a-zA-Z]+;|&#\d+;/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const hasWord = (value) => /[A-Za-z]{2,}/.test(value);

const looksLikeUserText = (raw) => {
  const text = stripNonText(raw);
  return text.length > 0 && hasWord(text);
};

// Single lowercase tokens (icon names, units, css values) are almost never
// copy; require whitespace or a leading capital to treat an attribute as text.
const looksLikeUserAttr = (raw) => {
  const text = stripNonText(raw);
  if (!hasWord(text)) return false;
  return /\s/.test(text) || /^[A-Z]/.test(text);
};

const isIgnored = (lines, lineIndex) => {
  const current = lines[lineIndex] ?? "";
  const previous = lines[lineIndex - 1] ?? "";
  return current.includes(IGNORE_LINE) || previous.includes(IGNORE_LINE);
};

const collectFindings = (file) => {
  const source = readFileSync(file, "utf8");
  if (source.includes(IGNORE_FILE)) return [];

  const lines = source.split("\n");
  const sourceFile = ts.createSourceFile(
    file,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const findings = [];

  const record = (start, value, label) => {
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(start);
    if (isIgnored(lines, line)) return;
    findings.push({
      file,
      line: line + 1,
      col: character + 1,
      label,
      snippet: stripNonText(value).slice(0, 80),
    });
  };

  const walk = (node, inNoTranslate) => {
    if (ts.isJsxText(node)) {
      if (!inNoTranslate && looksLikeUserText(node.text)) {
        const offset = node.getStart(sourceFile) + node.text.search(/\S/);
        record(offset, node.text, "text");
      }
      return;
    }

    if (ts.isJsxAttribute(node) && node.initializer) {
      const name = node.name.getText(sourceFile).toLowerCase();
      const init = node.initializer;
      if (
        USER_FACING_ATTRS.has(name) &&
        ts.isStringLiteral(init) &&
        looksLikeUserAttr(init.text)
      ) {
        record(init.getStart(sourceFile), init.text, `attribute "${name}"`);
      }
    }

    let childNoTranslate = inNoTranslate;
    if (ts.isJsxElement(node)) {
      const tag = node.openingElement.tagName.getText(sourceFile).toLowerCase();
      if (NO_TRANSLATE_TAGS.has(tag)) childNoTranslate = true;
    }

    node.forEachChild((child) => walk(child, childNoTranslate));
  };

  walk(sourceFile, false);
  return findings;
};

const shouldCheck = (file) =>
  /\.tsx$/.test(file) &&
  !/\.(test|spec|stories)\.tsx$/.test(file) &&
  !/(^|\/)(__tests__|__mocks__)\//.test(file);

const main = () => {
  const files = process.argv.slice(2).filter(shouldCheck);
  const findings = [];

  for (const file of files) {
    try {
      findings.push(...collectFindings(file));
    } catch (error) {
      process.stderr.write(`Could not parse ${file}: ${error.message}\n`);
    }
  }

  for (const f of findings) {
    const message = `Hardcoded UI ${f.label} "${f.snippet}" — wrap it with t("...") and add the key to src/frontend/src/locales/en.json.`;
    process.stdout.write(
      `::error file=${f.file},line=${f.line},col=${f.col},title=Untranslated frontend string::${message}\n`,
    );
  }

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (summaryPath) {
    const header =
      findings.length === 0
        ? "## ✅ Frontend Translation Checker\n\nNo hardcoded user-facing strings found in the changed files.\n"
        : `## ⚠️ Frontend Translation Checker\n\nFound **${findings.length}** hardcoded user-facing string(s). Wrap each with \`t("...")\` and add the key to \`src/frontend/src/locales/en.json\`. Add \`i18n-ignore\` on the line (or \`i18n-ignore-file\` in the file) to suppress a false positive.\n\n| File | Line | Where | Text |\n| --- | --- | --- | --- |\n${findings
            .map(
              (f) =>
                `| \`${f.file}\` | ${f.line} | ${f.label} | ${f.snippet.replace(/\|/g, "\\|")} |`,
            )
            .join("\n")}\n`;
    try {
      appendFileSync(summaryPath, `${header}\n`);
    } catch {
      // Step summary is best-effort; annotations are the source of truth.
    }
  }

  if (findings.length > 0) {
    process.stderr.write(
      `\nFrontend Translation Checker: ${findings.length} hardcoded string(s) found.\n`,
    );
    process.exit(1);
  }

  process.stdout.write("Frontend Translation Checker: no hardcoded strings.\n");
};

await main();
