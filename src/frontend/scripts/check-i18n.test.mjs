/**
 * Unit coverage for the i18n extraction + parity gate.
 *
 * Each case builds a throwaway frontend tree (a `src/` with `.tsx` sources and
 * a `locales/` bundle set) so the assertions pin the checker's behavior rather
 * than the current state of the real locale files.
 */
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { analyzeI18n, reportI18n } from "./check-i18n.mjs";

const LOCALES = ["de", "fr"];

/**
 * Materialize a frontend tree and return its root.
 *
 * @param {Record<string, string>} sources Path under `src/` -> file contents.
 * @param {Record<string, Record<string, string>>} bundles Locale -> bundle.
 */
const makeTree = (sources, bundles) => {
  const root = mkdtempSync(path.join(tmpdir(), "check-i18n-"));
  const localesDir = path.join(root, "src", "locales");
  mkdirSync(localesDir, { recursive: true });
  for (const [rel, contents] of Object.entries(sources)) {
    const full = path.join(root, "src", rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, contents, "utf8");
  }
  for (const [locale, bundle] of Object.entries(bundles)) {
    writeFileSync(
      path.join(localesDir, `${locale}.json`),
      JSON.stringify(bundle, null, 2),
      "utf8",
    );
  }
  return root;
};

const analyze = (sources, bundles, locales = LOCALES) =>
  analyzeI18n({ frontendRoot: makeTree(sources, bundles), locales });

test("accepts static t(), i18n.t() and <Trans i18nKey> keys present in en.json", () => {
  const result = analyze(
    {
      "a.tsx": `const a = t("one");\nconst b = i18n.t('two');\n`,
      "nested/b.tsx": `<Trans i18nKey="three" />;\n<Trans i18nKey={"four"} />;\n`,
      "c.ts": `export const d = t("one");\n`,
      // Non-source files next to the sources must be ignored.
      "README.md": `t("not.a.key")\n`,
    },
    {
      en: { one: "One", two: "Two", three: "Three", four: "Four" },
      de: { one: "Eins", two: "Zwei", three: "Drei", four: "Vier" },
      fr: { one: "Un", two: "Deux", three: "Trois", four: "Quatre" },
    },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.missing, []);
  assert.deepEqual(result.parityProblems, []);
  assert.equal(result.fileCount, 3);
  assert.equal(result.uniqueKeyCount, 4);
  assert.equal(result.staticCallCount, 5);
});

test("reports a static key that is missing from en.json, with file and line", () => {
  const result = analyze(
    { "a.tsx": `const x = 1;\nconst y = t("absent.key");\n` },
    { en: {}, de: {}, fr: {} },
  );

  assert.equal(result.ok, false);
  assert.deepEqual(result.missing, [
    { key: "absent.key", file: path.join("src", "a.tsx"), line: 2 },
  ]);
});

test("reports a missing <Trans i18nKey>, not only t() calls", () => {
  const result = analyze(
    { "a.tsx": `<Trans i18nKey="absent.trans" />;\n` },
    { en: {}, de: {}, fr: {} },
  );

  assert.deepEqual(
    result.missing.map(({ key }) => key),
    ["absent.trans"],
  );
});

test("resolves i18next plural keys through their suffixed forms", () => {
  const bundle = {
    "store.results_one": "{{count}}",
    "store.results_other": "{{count}}",
  };
  const result = analyze(
    { "a.tsx": `t("store.results", { count });\n` },
    { en: bundle, de: bundle, fr: bundle },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.missing, []);
});

test("counts only t( calls as dynamic, so static <Trans> uses cannot negate the total", () => {
  const result = analyze(
    {
      // Two static t(), two dynamic t(), and two static <Trans i18nKey>.
      "a.tsx":
        `t("one");\nt('two');\nt(\`x.\${id}\`);\nt(keyVar);\n` +
        `<Trans i18nKey="one" />;\n<Trans i18nKey="two" />;\n`,
    },
    {
      en: { one: "One", two: "Two" },
      de: { one: "1", two: "2" },
      fr: { one: "1", two: "2" },
    },
  );

  assert.equal(result.dynamicCount, 2);
  // Static usages still include the <Trans> occurrences.
  assert.equal(result.staticCallCount, 4);
  assert.equal(result.uniqueKeyCount, 2);
});

test("reports a key present in en.json but missing from a locale", () => {
  const result = analyze(
    { "a.tsx": `t("one");\n` },
    { en: { one: "One" }, de: { one: "Eins" }, fr: {} },
  );

  assert.equal(result.ok, false);
  assert.deepEqual(result.parityProblems, [
    { locale: "fr", key: "one", reason: "missing key" },
  ]);
});

test("reports a locale whose interpolation placeholders differ from en", () => {
  const result = analyze(
    { "a.tsx": `t("greet");\n` },
    {
      en: { greet: "Hi {{name}}" },
      de: { greet: "Hallo {{ name }}" },
      fr: { greet: "Bonjour {{nom}}" },
    },
  );

  // Whitespace inside the token is normalized, so `de` is in parity.
  assert.deepEqual(result.parityProblems, [
    { locale: "fr", key: "greet", reason: "placeholder mismatch" },
  ]);
});

test("a key used nowhere in code is not reported", () => {
  const result = analyze(
    { "a.tsx": `export const nothing = true;\n` },
    {
      en: { unused: "Unused" },
      de: { unused: "Unused" },
      fr: { unused: "Unused" },
    },
  );

  assert.equal(result.ok, true);
  assert.equal(result.uniqueKeyCount, 0);
});

test("reportI18n exits 0 and prints the success line for a clean tree", () => {
  const out = { stdout: [], stderr: [] };
  const code = reportI18n(
    analyze(
      { "a.tsx": `t("one");\n` },
      { en: { one: "One" }, de: { one: "Eins" }, fr: { one: "Un" } },
    ),
    LOCALES.length,
    {
      stdout: (text) => out.stdout.push(text),
      stderr: (text) => out.stderr.push(text),
    },
  );

  assert.equal(code, 0);
  assert.equal(out.stderr.length, 0);
  assert.match(out.stdout.join(""), /all 2 locales are in parity/);
});

test("reportI18n exits 1 and names both failure kinds", () => {
  const out = { stdout: [], stderr: [] };
  const code = reportI18n(
    analyze(
      { "a.tsx": `t("absent");\n` },
      { en: { one: "One" }, de: { one: "Eins" }, fr: {} },
    ),
    LOCALES.length,
    {
      stdout: (text) => out.stdout.push(text),
      stderr: (text) => out.stderr.push(text),
    },
  );

  assert.equal(code, 1);
  const stderr = out.stderr.join("");
  assert.match(stderr, /1 key\(s\) used in code but missing from en\.json/);
  assert.match(stderr, /absent/);
  assert.match(stderr, /1 locale parity problem\(s\)/);
  assert.match(stderr, /fr\.json {2}one {2}\(missing key\)/);
});
