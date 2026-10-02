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
 *
 * `analyzeI18n` is exported so the gate itself is covered by
 * `scripts/check-i18n.test.mjs` (`npm run test:i18n-checker`); the CLI block at
 * the bottom only runs when this file is executed directly.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const DEFAULT_LOCALES = ["de", "es", "fr", "ja", "pt", "zh-Hans"];
const PLURAL_SUFFIXES = ["_zero", "_one", "_two", "_few", "_many", "_other"];

/** Walk a directory for .ts/.tsx files. */
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

const placeholders = (value) =>
  (String(value).match(/\{\{\s*[\w.]+\s*\}\}/g) ?? [])
    .map((token) => token.replace(/[{}\s]/g, ""))
    .sort()
    .join("|");

/**
 * Run both checks over a frontend tree.
 *
 * @param {object} options
 * @param {string} options.frontendRoot Root the reported paths are relative to.
 * @param {string} [options.srcRoot] Tree to scan (default `<frontendRoot>/src`).
 * @param {string} [options.localesDir] Bundle directory (default `<srcRoot>/locales`).
 * @param {string[]} [options.locales] Locales required to be in parity with en.
 * @returns {{fileCount: number, staticCallCount: number, uniqueKeyCount: number,
 *   dynamicCount: number, missing: Array<{key: string, file: string, line: number}>,
 *   parityProblems: Array<{locale: string, key: string, reason: string}>, ok: boolean}}
 */
export function analyzeI18n({
  frontendRoot,
  srcRoot = path.join(frontendRoot, "src"),
  localesDir = path.join(srcRoot, "locales"),
  locales = DEFAULT_LOCALES,
} = {}) {
  const readJson = (file) =>
    JSON.parse(readFileSync(path.join(localesDir, file), "utf8"));

  const en = readJson("en.json");
  const enKeys = new Set(Object.keys(en));
  const keyExists = (key) =>
    enKeys.has(key) ||
    PLURAL_SUFFIXES.some((suffix) => enKeys.has(`${key}${suffix}`));

  const usedKeys = new Map(); // key -> [{ file, line }]
  let callCount = 0;
  // Only `t(` matches may be subtracted from `callCount`: `<Trans i18nKey>` uses
  // are recorded as keys but are not `t(` calls, so counting them here would
  // undercount (and could negate) the dynamic total.
  let staticTCallCount = 0;

  const record = (key, file, line) => {
    if (!usedKeys.has(key)) usedKeys.set(key, []);
    usedKeys.get(key).push({ file, line });
  };

  const sourceFiles = collectSourceFiles(srcRoot);
  for (const file of sourceFiles) {
    const content = readFileSync(file, "utf8");
    const rel = path.relative(frontendRoot, file);

    callCount += (content.match(ANY_CALL_RE) ?? []).length;

    for (const match of content.matchAll(STATIC_CALL_RE)) {
      staticTCallCount++;
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

  // --- Check 1: every static key used in code exists in en.json -------------
  const missing = [];
  for (const [key, uses] of [...usedKeys.entries()].sort()) {
    if (keyExists(key)) continue;
    for (const { file, line } of uses) missing.push({ key, file, line });
  }

  // --- Check 2: locale parity (mirrors locale-parity.test.ts) ---------------
  const parityProblems = [];
  for (const locale of locales) {
    const bundle = readJson(`${locale}.json`);
    for (const key of enKeys) {
      if (!(key in bundle)) {
        parityProblems.push({ locale, key, reason: "missing key" });
      } else if (placeholders(en[key]) !== placeholders(bundle[key])) {
        parityProblems.push({ locale, key, reason: "placeholder mismatch" });
      }
    }
  }

  return {
    fileCount: sourceFiles.length,
    staticCallCount,
    uniqueKeyCount: usedKeys.size,
    dynamicCount: callCount - staticTCallCount,
    missing,
    parityProblems,
    ok: missing.length === 0 && parityProblems.length === 0,
  };
}

/**
 * Print an analysis and return the process exit code it implies.
 *
 * @param {ReturnType<typeof analyzeI18n>} result
 * @param {number} localeCount Number of locales checked, for the success line.
 * @param {{stdout: (text: string) => void, stderr: (text: string) => void}} out
 * @returns {number} 0 when both checks pass, 1 otherwise.
 */
export function reportI18n(
  result,
  localeCount,
  out = {
    stdout: (text) => process.stdout.write(text),
    stderr: (text) => process.stderr.write(text),
  },
) {
  out.stdout(`Scanned ${result.fileCount} source files.\n`);
  out.stdout(
    `Found ${result.staticCallCount} static key usages (${result.uniqueKeyCount} unique keys); ` +
      `skipped ${result.dynamicCount} dynamic key usages (template literals / variables).\n`,
  );

  if (result.missing.length > 0) {
    out.stderr(
      `\n✗ ${result.missing.length} key(s) used in code but missing from en.json:\n`,
    );
    for (const { key, file, line } of result.missing) {
      out.stderr(`  ${file}:${line}  ${key}\n`);
    }
  }

  if (result.parityProblems.length > 0) {
    out.stderr(
      `\n✗ ${result.parityProblems.length} locale parity problem(s):\n`,
    );
    for (const { locale, key, reason } of result.parityProblems) {
      out.stderr(`  ${locale}.json  ${key}  (${reason})\n`);
    }
  }

  if (result.ok) {
    out.stdout(
      `✓ All used keys exist in en.json; all ${localeCount} locales are in parity (keys + placeholders).\n`,
    );
    return 0;
  }
  return 1;
}

const isCli =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isCli) {
  const frontendRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
  );
  process.exit(
    reportI18n(analyzeI18n({ frontendRoot }), DEFAULT_LOCALES.length),
  );
}
