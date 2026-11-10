import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const docsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function usage() {
  console.error("Usage: npm run docs:version -- 1.14.0");
}

const version = process.argv[2];
if (!/^\d+\.\d+\.\d+$/.test(version || "")) {
  usage();
  process.exit(1);
}

const versionDir = path.join(docsDir, "versioned_docs", `version-${version}`);
if (fs.existsSync(versionDir)) {
  console.error(`Version ${version} already exists.`);
  console.error(`To regenerate model files only: node scripts/snapshot-llm-docs.mjs ${version}`);
  process.exit(1);
}

const docusaurus = path.join(docsDir, "node_modules", ".bin", "docusaurus");
if (!fs.existsSync(docusaurus)) {
  console.error("Docusaurus is not installed. Run npm install in docs/.");
  process.exit(1);
}

const versioned = spawnSync(docusaurus, ["docs:version", version], {
  cwd: docsDir,
  stdio: "inherit",
});
if (versioned.status !== 0) {
  process.exit(versioned.status ?? 1);
}

const snapshot = spawnSync(process.execPath, [path.join(docsDir, "scripts", "snapshot-llm-docs.mjs"), version], {
  cwd: docsDir,
  stdio: "inherit",
});
if (snapshot.status !== 0) {
  process.exit(snapshot.status ?? 1);
}

console.log("");
console.log(`Version ${version} is snapshotted.`);
console.log("In docusaurus.config.js, set this version as lastVersion with path \"\".");
console.log("Set the previous release path to its version number, for example \"1.13.0\".");
