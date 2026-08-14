import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import ts from "typescript";

const testsRoot = path.resolve(import.meta.dirname, "..");
const blockingRoots = ["a11y", "core", "extended"].map((directory) =>
  path.join(testsRoot, directory),
);
const forbiddenHelpers = new Set([
  "initialGPTsetup",
  "addOpenAiInputKey",
  "selectGptModel",
  "selectAnthropicModel",
  "selectAssistantOpenAIModel",
]);
const forbiddenSecretNames = new Set([
  "ANTHROPIC_API_KEY",
  "APIFY_API_KEY",
  "APIFY_API_TOKEN",
  "AZURE_OPENAI_API_KEY",
  "COHERE_API_KEY",
  "COMPOSIO_API_KEY",
  "GOOGLE_API_KEY",
  "GROQ_API_KEY",
  "HUGGINGFACE_API_KEY",
  "MISTRAL_API_KEY",
  "NVIDIA_API_KEY",
  "OPENAI_API_KEY",
  "PERPLEXITYAI_API_KEY",
  "SEARCH_API_KEY",
  "TAVILY_API_KEY",
  "WATSONX_API_KEY",
  "YOUTUBE_API_KEY",
]);
const forbiddenSkipGuards = new Set([
  "anthropicKey",
  "apifyKey",
  "composioKey",
  "openAiKey",
  "tavilyKey",
]);
const loopbackProviderHelpers = [
  "configure-loopback-openai.ts",
  "configure-loopback-web-search.ts",
];

function* sourceFiles(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* sourceFiles(entryPath);
    else if (entry.name.endsWith(".spec.ts")) yield entryPath;
  }
}

function processEnvName(node) {
  if (
    ts.isPropertyAccessExpression(node) &&
    ts.isPropertyAccessExpression(node.expression) &&
    ts.isIdentifier(node.expression.expression) &&
    node.expression.expression.text === "process" &&
    node.expression.name.text === "env"
  ) {
    return node.name.text;
  }
  if (
    ts.isElementAccessExpression(node) &&
    ts.isPropertyAccessExpression(node.expression) &&
    ts.isIdentifier(node.expression.expression) &&
    node.expression.expression.text === "process" &&
    node.expression.name.text === "env" &&
    ts.isStringLiteral(node.argumentExpression)
  ) {
    return node.argumentExpression.text;
  }
  return null;
}

test("blocking Playwright specs use the hardened fixture and avoid live providers", () => {
  const violations = [];

  for (const filename of blockingRoots.flatMap((root) => [
    ...sourceFiles(root),
  ])) {
    const source = fs.readFileSync(filename, "utf8");
    const tree = ts.createSourceFile(
      filename,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    function visit(node) {
      const secret = processEnvName(node);
      if (secret && forbiddenSecretNames.has(secret)) {
        violations.push(
          `${path.relative(testsRoot, filename)} reads process.env.${secret}`,
        );
      }

      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression) &&
        ts.isIdentifier(node.expression.expression) &&
        node.expression.expression.text === "skipIfMissing" &&
        forbiddenSkipGuards.has(node.expression.name.text)
      ) {
        violations.push(
          `${path.relative(testsRoot, filename)} calls skipIfMissing.${node.expression.name.text}`,
        );
      }

      if (ts.isImportDeclaration(node)) {
        if (
          node.moduleSpecifier.text === "@playwright/test" &&
          node.importClause &&
          !node.importClause.isTypeOnly
        ) {
          const imported = node.importClause.namedBindings;
          const importsRuntimeTest =
            !imported ||
            (ts.isNamedImports(imported) &&
              imported.elements.some(
                (binding) =>
                  !binding.isTypeOnly &&
                  (binding.propertyName ?? binding.name).text === "test",
              ));
          if (importsRuntimeTest) {
            violations.push(
              `${path.relative(testsRoot, filename)} imports the base Playwright test fixture`,
            );
          }
        }

        const clause = node.importClause;
        const imported = clause?.namedBindings;
        if (imported && ts.isNamedImports(imported)) {
          for (const binding of imported.elements) {
            const importedName = (binding.propertyName ?? binding.name).text;
            if (forbiddenHelpers.has(importedName)) {
              violations.push(
                `${path.relative(testsRoot, filename)} imports ${importedName}`,
              );
            }
          }
        }
      }

      ts.forEachChild(node, visit);
    }

    visit(tree);
  }

  assert.deepEqual(violations, []);
});

test("loopback provider helpers wait for the shared flow editor readiness contract", () => {
  const violations = [];

  for (const helper of loopbackProviderHelpers) {
    const filename = path.join(testsRoot, "utils", helper);
    const source = fs.readFileSync(filename, "utf8");
    const tree = ts.createSourceFile(
      filename,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );
    let importsReadinessHelper = false;
    let callsReadinessHelper = false;

    function visit(node) {
      if (
        ts.isImportDeclaration(node) &&
        node.moduleSpecifier.text === "./flow/wait-for-flow-editor-ready" &&
        node.importClause?.namedBindings &&
        ts.isNamedImports(node.importClause.namedBindings) &&
        node.importClause.namedBindings.elements.some(
          (binding) =>
            (binding.propertyName ?? binding.name).text ===
            "waitForFlowEditorReady",
        )
      ) {
        importsReadinessHelper = true;
      }

      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "waitForFlowEditorReady"
      ) {
        callsReadinessHelper = true;
      }

      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression) &&
        node.expression.name.text === "getByTestId" &&
        ts.isStringLiteral(node.arguments[0]) &&
        node.arguments[0].text === "react-flow-id"
      ) {
        violations.push(`${helper} treats the React Flow DOM id as a test id`);
      }

      ts.forEachChild(node, visit);
    }

    visit(tree);
    if (!importsReadinessHelper || !callsReadinessHelper) {
      violations.push(
        `${helper} does not use waitForFlowEditorReady after reloading`,
      );
    }
  }

  assert.deepEqual(violations, []);
});

test("flow editor readiness includes search hotkey registration", () => {
  const filename = path.join(
    testsRoot,
    "utils",
    "flow",
    "wait-for-flow-editor-ready.ts",
  );
  const source = fs.readFileSync(filename, "utf8");

  assert.match(source, /getByTestId\(TID\.flowSidebar\)/);
  assert.match(
    source,
    /toHaveAttribute\(\s*"data-search-hotkey-ready",\s*"true"/,
  );
});
