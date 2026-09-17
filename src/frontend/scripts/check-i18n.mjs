#!/usr/bin/env node
/**
 * i18n extraction + parity check.
 *
 * 1. Scans all `.ts` / `.tsx` files under `src/` (recursive) for static
 *    translation keys used via
 *    `t("key")`, `t('key')`, `i18n.t("key")`, and `<Trans i18nKey="key" />`.
 *    Every static key must exist in `locales/en.json` (the fallback locale).
 *    Keys built from template literals or variables cannot be resolved
 *    statically — they are skipped and counted as warnings.
 *    i18next plural keys are resolved: `t("store.results", { count })` is
 *    satisfied by `store.results_one` / `store.results_other` in en.json.
 *
 * 2. Mirrors `src/locales/__tests__/locale-parity.test.ts`: every key in
 *    en.json must exist in each shipped locale, with the same set of
 *    `{{placeholder}}` interpolation tokens.
 *
 * Exits non-zero when any check fails.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const srcRoot = path.join(frontendRoot, "src");
const localesDir = path.join(srcRoot, "locales");

const LOCALES = ["de", "es", "fr", "ja", "pt", "zh-Hans"];
const PLURAL_SUFFIXES = ["_zero", "_one", "_two", "_few", "_many", "_other"];

const readJson = (file) =>
  JSON.parse(readFileSync(path.join(localesDir, file), "utf8"));

const en = readJson("en.json");
const enKeys = new Set(Object.keys(en));

const keyExists = (key) =>
  enKeys.has(key) ||
  PLURAL_SUFFIXES.some((suffix) => enKeys.has(`${key}${suffix}`));

/** Walk src/ for .ts/.tsx files. */
const collectSourceFiles = (dir, files = []) => {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectSourceFiles(fullPath, files);
    } else if (/\.tsx?$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
};

const lineOf = (content, index) => content.slice(0, index).split("\n").length;

// Static keys: t("key") / t('key') — also covers i18n.t("key") since the
// word boundary in `\bt\(` matches after the dot.
const STATIC_CALL_RE = /\bt\(\s*(["'])([^"'\n]+)\1/g;
// Every t( call, to derive the dynamic (unresolvable) count.
const ANY_CALL_RE = /\bt\(/g;
// <Trans i18nKey="key" /> or i18nKey={"key"}
const I18N_KEY_RE = /\bi18nKey=\{?\s*(["'])([^"'\n]+)\1/g;

const usedKeys = new Map(); // key -> [{ file, line }]
let callCount = 0;
let dynamicCount = 0;

const record = (key, file, line) => {
  if (!usedKeys.has(key)) usedKeys.set(key, []);
  usedKeys.get(key).push({ file, line });
};

for (const file of collectSourceFiles(srcRoot)) {
  const content = readFileSync(file, "utf8");
  const rel = path.relative(frontendRoot, file);

  callCount += (content.match(ANY_CALL_RE) ?? []).length;

  for (const match of content.matchAll(STATIC_CALL_RE)) {
    record(match[2], rel, lineOf(content, match.index));
  }
  for (const match of content.matchAll(I18N_KEY_RE)) {
    record(match[2], rel, lineOf(content, match.index));
  }
}

const staticCallCount = [...usedKeys.values()].reduce(
  (sum, uses) => sum + uses.length,
  0,
);
dynamicCount = callCount - staticCallCount;

// --- Check 1: every static key used in code exists in en.json -------------
const missing = [];
for (const [key, uses] of [...usedKeys.entries()].sort()) {
  if (keyExists(key)) continue;
  for (const { file, line } of uses) missing.push({ key, file, line });
}

// --- Check 2: locale parity (mirrors locale-parity.test.ts) ---------------
const placeholders = (value) =>
  (String(value).match(/\{\{\s*[\w.]+\s*\}\}/g) ?? [])
    .map((token) => token.replace(/[{}\s]/g, ""))
    .sort()
    .join("|");

const parityProblems = [];
for (const locale of LOCALES) {
  const bundle = readJson(`${locale}.json`);
  for (const key of enKeys) {
    if (!(key in bundle)) {
      parityProblems.push({ locale, key, reason: "missing key" });
    } else if (placeholders(en[key]) !== placeholders(bundle[key])) {
      parityProblems.push({ locale, key, reason: "placeholder mismatch" });
    }
  }
}

// --- Report ---------------------------------------------------------------
process.stdout.write(
  `Scanned ${collectSourceFiles(srcRoot).length} source files.\n`,
);
process.stdout.write(
  `Found ${staticCallCount} static key usages (${usedKeys.size} unique keys); ` +
    `skipped ${dynamicCount} dynamic key usages (template literals / variables).\n`,
);

if (missing.length > 0) {
  console.error(
    `\n✗ ${missing.length} key(s) used in code but missing from en.json:`,
  );
  for (const { key, file, line } of missing) {
    console.error(`  ${file}:${line}  ${key}`);
  }
}

if (parityProblems.length > 0) {
  console.error(`\n✗ ${parityProblems.length} locale parity problem(s):`);
  for (const { locale, key, reason } of parityProblems) {
    console.error(`  ${locale}.json  ${key}  (${reason})`);
  }
}

if (missing.length === 0 && parityProblems.length === 0) {
  process.stdout.write(
    `✓ All used keys exist in en.json; all ${LOCALES.length} locales are in parity (keys + placeholders).\n`,
  );
  process.exit(0);
}

process.exit(1);
