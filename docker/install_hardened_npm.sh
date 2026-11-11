#!/bin/sh

set -eu

NPM_VERSION="12.0.2"
IP_ADDRESS_VERSION="10.7.4"
BRACE_EXPANSION_VERSION="5.0.12"
TAR_VERSION="7.5.22"
# Keep node-gyp on its supported undici 6.x maintenance line.
UNDICI_VERSION="6.29.1"
POSTCSS_SELECTOR_PARSER_VERSION="7.1.6"
GLOB_VERSION="14.0.2"
MINIMATCH_VERSION="11.0.1"
PATH_SCURRY_VERSION="3.0.0"
NONRECURSIVE_GLOB_MATCH_VERSION="1.0.1"
npm_cache="$(npm config get cache)"

case "$npm_cache" in
    */.npm) ;;
    *)
        echo "Unexpected npm cache path: $npm_cache" >&2
        exit 1
        ;;
esac

npm install --global "npm@${NPM_VERSION}"
actual_npm_version="$(npm --version)"
if [ "$actual_npm_version" != "$NPM_VERSION" ]; then
    echo "npm $actual_npm_version != $NPM_VERSION" >&2
    exit 1
fi

# npm ships its own dependency tree below /usr/local/lib/node_modules/npm.
# Patch the remaining vulnerable packages in place until an npm release bundles
# versions at or above the floors tracked in LE-2197.
patch_root="$(mktemp -d)"
trap 'rm -rf "$patch_root"' EXIT
npm_root="/usr/local/lib/node_modules/npm/node_modules"

npm install --prefix "$patch_root" \
    --ignore-scripts \
    --no-package-lock \
    --no-save \
    "ip-address@${IP_ADDRESS_VERSION}" \
    "brace-expansion@${BRACE_EXPANSION_VERSION}" \
    "tar@${TAR_VERSION}" \
    "undici@${UNDICI_VERSION}" \
    "postcss-selector-parser@${POSTCSS_SELECTOR_PARSER_VERSION}" \
    "glob@${GLOB_VERSION}" \
    "minimatch@${MINIMATCH_VERSION}" \
    "path-scurry@${PATH_SCURRY_VERSION}" \
    "@isaacs/nonrecursive-glob-match@${NONRECURSIVE_GLOB_MATCH_VERSION}"

for package in ip-address brace-expansion tar undici postcss-selector-parser glob minimatch path-scurry @isaacs/nonrecursive-glob-match; do
    rm -rf "$npm_root/$package"
    cp -a "$patch_root/node_modules/$package" "$npm_root/$package"
done

node <<'NODE'
const fs = require("node:fs");
const path = "/usr/local/lib/node_modules/npm/node_modules";
const expected = {
  "ip-address": "10.7.4",
  "brace-expansion": "5.0.12",
  tar: "7.5.22",
  undici: "6.29.1",
  "postcss-selector-parser": "7.1.6",
  glob: "14.0.2",
  minimatch: "11.0.1",
  "path-scurry": "3.0.0",
  "@isaacs/nonrecursive-glob-match": "1.0.1",
  sigstore: "5.0.0",
  "@sigstore/core": "4.0.1",
  "tinyglobby/node_modules/picomatch": "4.0.5",
};

for (const [name, version] of Object.entries(expected)) {
  const actual = require(`${path}/${name}/package.json`).version;
  if (actual !== version) {
    throw new Error(`${name} ${actual} != ${version}`);
  }
}

// Both fixes change major versions. Align bundled consumers with the patched
// versions so npm ls can still detect broken or missing dependencies.
const replacements = { glob: expected.glob, minimatch: expected.minimatch };
const manifests = [
  `${path}/../package.json`,
  ...fs.readdirSync(path, { recursive: true })
    .filter(name => name.endsWith("/package.json"))
    .map(name => `${path}/${name}`),
];
for (const filename of manifests) {
  const manifest = JSON.parse(fs.readFileSync(filename, "utf8"));
  if (Object.hasOwn(replacements, manifest.name) && manifest.version !== replacements[manifest.name]) {
    throw new Error(`${filename}: vulnerable bundled ${manifest.name} ${manifest.version}`);
  }
  let changed = false;
  for (const [name, version] of Object.entries(replacements)) {
    if (manifest.dependencies && Object.hasOwn(manifest.dependencies, name)) {
      manifest.dependencies[name] = version;
      changed = true;
    }
  }
  if (changed) {
    fs.writeFileSync(filename, `${JSON.stringify(manifest, null, 2)}\n`);
  }
}
NODE

npm ls --global --all --omit=dev >/dev/null
printf '%s\n' "$actual_npm_version"
rm -rf "$npm_cache" /tmp/node-compile-cache
