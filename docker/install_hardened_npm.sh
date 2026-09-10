#!/bin/sh

set -eu

NPM_VERSION="12.0.2"
IP_ADDRESS_VERSION="10.3.1"
BRACE_EXPANSION_VERSION="5.0.9"
TAR_VERSION="7.5.22"
UNDICI_VERSION="6.28.0"
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
    "undici@${UNDICI_VERSION}"

for package in ip-address brace-expansion tar undici; do
    rm -rf "$npm_root/$package"
    cp -a "$patch_root/node_modules/$package" "$npm_root/$package"
done

node <<'NODE'
const path = "/usr/local/lib/node_modules/npm/node_modules";
const expected = {
  "ip-address": "10.3.1",
  "brace-expansion": "5.0.9",
  tar: "7.5.22",
  undici: "6.28.0",
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
NODE

npm ls --global --all --omit=dev >/dev/null
printf '%s\n' "$actual_npm_version"
rm -rf "$npm_cache" /tmp/node-compile-cache
