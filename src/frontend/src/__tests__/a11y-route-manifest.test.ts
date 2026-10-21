/**
 * Drift guard between the router and the accessibility scan manifest.
 *
 * `scripts/a11y/a11y_routes.json` is the single source of truth for what the
 * a11y scanners visit (`src/frontend/tests/a11y/static-routes.a11y.spec.ts`,
 * `scripts/a11y/a11y_scan.py`, and `.github/workflows/a11y-scan.yml`). Nothing
 * tied that list back to `src/frontend/src/routes.tsx`, so a newly registered
 * route was silently skipped by every scanner: `/settings/connections` shipped
 * live and unscanned because it appeared in none of the manifest sections.
 *
 * This suite parses the JSX route tree out of `routes.tsx` and asserts that
 * every reachable path is recorded in exactly one of `static`, `dynamic`,
 * `gated`, or `excluded` — and, in the other direction, that the manifest has
 * no entries for routes that no longer exist.
 *
 * The manifest's `assumptions` block records the feature-flag environment the
 * path list is valid under, so the flags are resolved from it rather than
 * guessed: the assumptions are verified against the real flag values, and any
 * flag that gates a route must be declared there.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import ts from "typescript";

const MANIFEST_PATH = join("scripts", "a11y", "a11y_routes.json");
const ROUTES_PATH = join("src", "frontend", "src", "routes.tsx");
const FRONTEND_SRC = join("src", "frontend", "src");
const FEATURE_FLAGS_PATH = join(
  FRONTEND_SRC,
  "customization",
  "feature-flags.ts",
);
const CONFIG_CONSTANTS_PATH = join(
  FRONTEND_SRC,
  "customization",
  "config-constants.ts",
);

const MANIFEST_SECTIONS = ["static", "dynamic", "gated", "excluded"] as const;
type ManifestSection = (typeof MANIFEST_SECTIONS)[number];

type ManifestEntry = { path?: string; template?: string };
type RouteManifest = Record<ManifestSection, ManifestEntry[]> & {
  assumptions: string[];
};

/** Jest runs from `src/frontend`; the manifest lives at the repository root. */
function findRepoRoot(): string {
  let directory = process.cwd();
  for (let depth = 0; depth < 8; depth++) {
    if (existsSync(join(directory, MANIFEST_PATH))) {
      return directory;
    }
    const parent = dirname(directory);
    if (parent === directory) break;
    directory = parent;
  }
  throw new Error(`Could not find ${MANIFEST_PATH} from ${process.cwd()}`);
}

const repoRoot = findRepoRoot();
const readRepoFile = (relativePath: string) =>
  readFileSync(join(repoRoot, relativePath), "utf8");

const manifest = JSON.parse(readRepoFile(MANIFEST_PATH)) as RouteManifest;

/**
 * Normalize a route path so both sides of the comparison agree on spelling:
 * `routes.tsx` writes `flows/` and `*`, the manifest writes `/flows` and `*`.
 */
function normalizeRoutePath(path: string): string {
  const withLeadingSlash = path.startsWith("/") ? path : `/${path}`;
  const collapsed = withLeadingSlash.replace(/\/{2,}/g, "/");
  return collapsed.length > 1 ? collapsed.replace(/\/+$/, "") : "/";
}

function joinRoutePath(parentPath: string, segment: string): string {
  return normalizeRoutePath(
    segment.startsWith("/") ? segment : `${parentPath}/${segment}`,
  );
}

/**
 * `general/:scrollId?` matches both `/settings/general/x` and
 * `/settings/general`, so both spellings are reachable and both need a home in
 * the manifest.
 */
function expandOptionalSegments(path: string): string[] {
  const variants = [path];
  let current = path;
  while (current.endsWith("?") && current.includes("/")) {
    current = normalizeRoutePath(current.slice(0, current.lastIndexOf("/")));
    variants.push(current);
  }
  return variants;
}

function parseSource(relativePath: string, kind: ts.ScriptKind) {
  return ts.createSourceFile(
    relativePath,
    readRepoFile(relativePath),
    ts.ScriptTarget.Latest,
    true,
    kind,
  );
}

/** `export const X = true | false | "literal"` — anything else maps to null. */
function parseExportedLiterals(
  relativePath: string,
): Map<string, boolean | string | null> {
  const sourceFile = parseSource(relativePath, ts.ScriptKind.TS);
  const literals = new Map<string, boolean | string | null>();
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    const isExported = statement.modifiers?.some(
      (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
    );
    if (!isExported) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name)) continue;
      const initializer = declaration.initializer;
      let value: boolean | string | null = null;
      if (initializer?.kind === ts.SyntaxKind.TrueKeyword) {
        value = true;
      } else if (initializer?.kind === ts.SyntaxKind.FalseKeyword) {
        value = false;
      } else if (initializer && ts.isStringLiteral(initializer)) {
        value = initializer.text;
      }
      literals.set(declaration.name.text, value);
    }
  }
  return literals;
}

const featureFlags = parseExportedLiterals(FEATURE_FLAGS_PATH);
const configConstants = parseExportedLiterals(CONFIG_CONSTANTS_PATH);

/** `"ENABLE_FILE_MANAGEMENT is true, so /assets routes are active."` */
const assumedFlags = new Map<string, boolean>(
  manifest.assumptions
    .map((assumption) =>
      /^([A-Z][A-Z0-9_]*) is (true|false)\b/.exec(assumption),
    )
    .filter((match): match is RegExpExecArray => match !== null)
    .map((match) => [match[1], match[2] === "true"]),
);
const assumesEmptyBasename = manifest.assumptions.some((assumption) =>
  /^BASENAME is empty\b/.test(assumption),
);

type RouteScan = {
  /** Every path a user can land on, normalized and optional-expanded. */
  reachablePaths: Set<string>;
  /** Flags that decide whether a route subtree is registered at all. */
  referencedFlags: Set<string>;
  /** Customization seams rendered into the tree, e.g. `CustomRoutesStore()`. */
  extensionPoints: Set<string>;
  /** Declarations this parser refused to guess at. */
  unresolved: string[];
};

function scanRoutes(): RouteScan {
  const sourceFile = parseSource(ROUTES_PATH, ts.ScriptKind.TSX);
  const scan: RouteScan = {
    reachablePaths: new Set<string>(),
    referencedFlags: new Set<string>(),
    extensionPoints: new Set<string>(),
    unresolved: [],
  };

  const describe = (node: ts.Node) => {
    const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart());
    const text = node.getText(sourceFile).replace(/\s+/g, " ");
    return `${ROUTES_PATH}:${line + 1}: ${text.slice(0, 120)}`;
  };

  const resolveFlag = (node: ts.Node): boolean | undefined => {
    if (!ts.isIdentifier(node)) return undefined;
    const name = node.text;
    if (!featureFlags.has(name)) return undefined;
    scan.referencedFlags.add(name);
    const value = featureFlags.get(name);
    return typeof value === "boolean" ? value : undefined;
  };

  const resolvePathAttribute = (
    initializer: ts.JsxAttributeValue | undefined,
  ): string | undefined => {
    if (!initializer) return undefined;
    if (ts.isStringLiteral(initializer)) return initializer.text;
    if (!ts.isJsxExpression(initializer) || !initializer.expression) {
      return undefined;
    }
    const expression = initializer.expression;
    if (ts.isStringLiteral(expression)) return expression.text;
    if (ts.isConditionalExpression(expression)) {
      const flagValue = resolveFlag(expression.condition);
      if (flagValue === undefined) return undefined;
      const branch = flagValue ? expression.whenTrue : expression.whenFalse;
      return ts.isStringLiteral(branch) ? branch.text : undefined;
    }
    return undefined;
  };

  const record = (path: string) => {
    for (const variant of expandOptionalSegments(path)) {
      scan.reachablePaths.add(variant);
    }
  };

  const visitRoute = (
    node: ts.JsxElement | ts.JsxSelfClosingElement,
    parentPath: string,
  ) => {
    const opening = ts.isJsxElement(node) ? node.openingElement : node;
    const attributes = opening.attributes.properties.filter(ts.isJsxAttribute);
    const pathAttribute = attributes.find(
      (attribute) => attribute.name.getText(sourceFile) === "path",
    );
    const isIndexRoute = attributes.some(
      (attribute) => attribute.name.getText(sourceFile) === "index",
    );

    let routePath = parentPath;
    if (pathAttribute) {
      const segment = resolvePathAttribute(pathAttribute.initializer);
      if (segment === undefined) {
        scan.unresolved.push(
          `unresolvable path attribute — ${describe(pathAttribute)}`,
        );
        return;
      }
      routePath = joinRoutePath(parentPath, segment);
      record(routePath);
    }
    if (isIndexRoute) {
      record(routePath);
    }

    if (ts.isJsxElement(node)) {
      for (const child of node.children) {
        visit(child, routePath);
      }
    }
  };

  const visit = (node: ts.Node, parentPath: string) => {
    if (ts.isJsxText(node)) {
      if (!node.containsOnlyTriviaWhiteSpaces) {
        scan.unresolved.push(`unexpected JSX text — ${describe(node)}`);
      }
      return;
    }
    if (ts.isArrayLiteralExpression(node)) {
      for (const element of node.elements) visit(element, parentPath);
      return;
    }
    if (ts.isParenthesizedExpression(node)) {
      visit(node.expression, parentPath);
      return;
    }
    if (ts.isJsxFragment(node)) {
      for (const child of node.children) visit(child, parentPath);
      return;
    }
    if (ts.isJsxExpression(node)) {
      if (!node.expression) return;
      visit(node.expression, parentPath);
      return;
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
    ) {
      const flagValue = resolveFlag(node.left);
      if (flagValue === undefined) {
        scan.unresolved.push(`unresolvable route guard — ${describe(node)}`);
        return;
      }
      if (flagValue) visit(node.right, parentPath);
      return;
    }
    if (ts.isConditionalExpression(node)) {
      const flagValue = resolveFlag(node.condition);
      if (flagValue === undefined) {
        scan.unresolved.push(`unresolvable route branch — ${describe(node)}`);
        return;
      }
      visit(flagValue ? node.whenTrue : node.whenFalse, parentPath);
      return;
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      scan.extensionPoints.add(node.expression.text);
      return;
    }
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node;
      if (opening.tagName.getText(sourceFile) === "Route") {
        visitRoute(node, parentPath);
        return;
      }
    }
    scan.unresolved.push(`unexpected route declaration — ${describe(node)}`);
  };

  const findRouteTree = (node: ts.Node): ts.Node | undefined => {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "createRoutesFromElements"
    ) {
      return node.arguments[0];
    }
    return ts.forEachChild(node, findRouteTree);
  };

  const routeTree = findRouteTree(sourceFile);
  if (!routeTree) {
    throw new Error(`No createRoutesFromElements(...) call in ${ROUTES_PATH}`);
  }
  visit(routeTree, "/");
  return scan;
}

const routeScan = scanRoutes();

/** Resolve `CustomRoutesStore` back to the module `routes.tsx` imports it from. */
function resolveExtensionPointSource(identifier: string): string {
  const sourceFile = parseSource(ROUTES_PATH, ts.ScriptKind.TSX);
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement)) continue;
    const bindings = statement.importClause?.namedBindings;
    const imported =
      bindings &&
      ts.isNamedImports(bindings) &&
      bindings.elements.some((element) => element.name.text === identifier);
    const isDefault = statement.importClause?.name?.text === identifier;
    if (!imported && !isDefault) continue;
    const specifier = (statement.moduleSpecifier as ts.StringLiteral).text;
    const base = join(FRONTEND_SRC, specifier.replace(/^\.\//, ""));
    for (const candidate of [`${base}.tsx`, `${base}.ts`]) {
      if (existsSync(join(repoRoot, candidate))) return candidate;
    }
    throw new Error(`Could not resolve module for ${identifier}: ${specifier}`);
  }
  throw new Error(`No import of ${identifier} in ${ROUTES_PATH}`);
}

function manifestEntries(): Array<{ section: ManifestSection; path: string }> {
  return MANIFEST_SECTIONS.flatMap((section) =>
    (manifest[section] ?? []).map((entry) => {
      const declared = entry.path ?? entry.template;
      if (!declared) {
        throw new Error(
          `${MANIFEST_PATH} ${section} entry has neither "path" nor "template": ${JSON.stringify(entry)}`,
        );
      }
      return { section, path: normalizeRoutePath(declared) };
    }),
  );
}

describe("a11y route manifest", () => {
  it("records assumptions that match the real feature-flag values", () => {
    const mismatched = [...assumedFlags.entries()]
      .filter(([flag, assumed]) => featureFlags.get(flag) !== assumed)
      .map(
        ([flag, assumed]) =>
          `${flag}: manifest assumes ${assumed}, ${FEATURE_FLAGS_PATH} has ${String(
            featureFlags.get(flag),
          )}`,
      );

    expect(mismatched).toEqual([]);
  });

  it("records an assumption for every flag that gates a route", () => {
    const undeclared = [...routeScan.referencedFlags]
      .filter((flag) => !assumedFlags.has(flag))
      .sort();

    expect(undeclared).toEqual([]);
  });

  it("keeps route paths rooted at / as the manifest assumes", () => {
    expect(assumesEmptyBasename).toBe(true);
    expect(configConstants.get("BASENAME")).toBe("");
  });

  it("resolves every route declaration in routes.tsx", () => {
    expect(routeScan.unresolved).toEqual([]);
  });

  it("reaches only customization seams that register no OSS routes", () => {
    const registering = [...routeScan.extensionPoints]
      .map((identifier) => ({
        identifier,
        source: resolveExtensionPointSource(identifier),
      }))
      .filter(({ source }) => readRepoFile(source).includes("<Route"))
      .map(
        ({ identifier, source }) =>
          `${identifier} (${source}) registers routes; add them to ${MANIFEST_PATH}`,
      );

    expect(routeScan.extensionPoints.size).toBeGreaterThan(0);
    expect(registering).toEqual([]);
  });

  it("accounts for every reachable route in one of its sections", () => {
    const accounted = new Set(manifestEntries().map((entry) => entry.path));
    const missing = [...routeScan.reachablePaths]
      .filter((path) => !accounted.has(path))
      .sort();

    expect(missing).toEqual([]);
  });

  it("lists each route in exactly one section", () => {
    const sectionsByPath = new Map<string, ManifestSection[]>();
    for (const { section, path } of manifestEntries()) {
      sectionsByPath.set(path, [...(sectionsByPath.get(path) ?? []), section]);
    }
    const duplicated = [...sectionsByPath.entries()]
      .filter(([, sections]) => sections.length > 1)
      .map(([path, sections]) => `${path}: ${sections.join(", ")}`)
      .sort();

    expect(duplicated).toEqual([]);
  });

  it("keeps no manifest entries for routes that no longer exist", () => {
    const stale = manifestEntries()
      .filter((entry) => !routeScan.reachablePaths.has(entry.path))
      .map((entry) => `${entry.section}: ${entry.path}`)
      .sort();

    expect(stale).toEqual([]);
  });
});
