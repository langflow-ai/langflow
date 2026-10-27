import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import {
  archivedDocsPath,
  docsPluginConfig,
  writeComponentCatalog,
  writeProseFiles,
} from "./llm-snapshot.mjs";

const docsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(docsDir, "..");

function usage() {
  console.error("Usage: node scripts/snapshot-llm-docs.mjs 1.14.0");
}

function requireVersion(argv) {
  const version = argv[2];
  if (!/^\d+\.\d+\.\d+$/.test(version || "")) {
    usage();
    process.exit(1);
  }
  return version;
}

function loadDocsConfig() {
  const require = createRequire(path.join(docsDir, "package.json"));
  return docsPluginConfig(require(path.join(docsDir, "docusaurus.config.js")));
}

function generateOpenApi(outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const result = spawnSync(
    "uv",
    ["run", "python", "docs/openapi/generate_openapi.py", "--output", outputPath],
    { cwd: repoRoot, stdio: "inherit" },
  );
  if (result.status !== 0) {
    throw new Error("OpenAPI generation failed. The docs version snapshot was kept. Re-run node scripts/snapshot-llm-docs.mjs <version>.");
  }
}

function copyRoot(versionDir) {
  const staticDir = path.join(docsDir, "static");
  fs.copyFileSync(path.join(versionDir, "llms.txt"), path.join(staticDir, "llms.txt"));
  fs.copyFileSync(path.join(versionDir, "llms-full.txt"), path.join(staticDir, "llms-full.txt"));
}

export function snapshotVersion(version, { includeRoot = true, docsPath = "", skipOpenApi = false, skipComponents = false } = {}) {
  const versionDir = path.join(docsDir, "versioned_docs", `version-${version}`);
  const sidebarPath = path.join(docsDir, "versioned_sidebars", `version-${version}-sidebars.json`);
  if (!fs.existsSync(versionDir) || !fs.existsSync(sidebarPath)) {
    throw new Error(`No docs snapshot for ${version}. Run npm run docs:version -- ${version} first.`);
  }

  const outputDir = path.join(docsDir, "static", "llms", version);
  fs.mkdirSync(outputDir, { recursive: true });

  if (!skipOpenApi) {
    generateOpenApi(path.join(outputDir, "openapi.json"));
  }
  if (!skipComponents) {
    writeComponentCatalog({
      version,
      indexPath: path.join(repoRoot, "src", "lfx", "src", "lfx", "_assets", "component_index.json"),
      outputDir,
    });
  }

  writeProseFiles({
    version,
    docsPath,
    versionDir,
    sidebarPath,
    outputDir,
  });

  if (includeRoot) {
    copyRoot(outputDir);
  }
  return outputDir;
}

function archivePreviousDefault(version) {
  const docsConfig = loadDocsConfig();
  const previous = docsConfig.lastVersion;
  if (!previous || previous === version) {
    return;
  }
  const previousOutput = path.join(docsDir, "static", "llms", previous, "llms.txt");
  if (!fs.existsSync(previousOutput)) {
    return;
  }
  const docsPath = archivedDocsPath(docsConfig, previous);
  snapshotVersion(previous, {
    includeRoot: false,
    docsPath,
    skipOpenApi: true,
    skipComponents: true,
  });
  console.log(`Updated ${previous} page links to /${docsPath}/.`);
}

function main() {
  const version = requireVersion(process.argv);
  const outputDir = snapshotVersion(version, { includeRoot: true, docsPath: "" });
  archivePreviousDefault(version);
  console.log(`Wrote model docs for ${version} to ${outputDir}`);
  console.log("Root copies: docs/static/llms.txt and docs/static/llms-full.txt");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
