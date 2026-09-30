// Mock for the `uuid` package to handle its ESM-only build in Jest.
//
// uuid v14 ships ES modules only ("type": "module"; its only `node` export,
// dist-node/index.js, is ESM), which Jest's CommonJS runtime cannot parse
// ("SyntaxError: Unexpected token 'export'"). The repo already maps other
// ESM-only packages (vanilla-jsoneditor, @jsonquerylang/jsonquery) to CommonJS
// mocks via moduleNameMapper; this does the same for uuid.
//
// The implementation is RFC 4122-correct (real random v4, deterministic SHA-1
// v5/MD5 v3) so output is byte-identical to the real package. Source code under
// test uses `v5` (with `v5.DNS`) and `v4`.
const crypto = require("crypto");

const NIL = "00000000-0000-0000-0000-000000000000";
const MAX = "ffffffff-ffff-ffff-ffff-ffffffffffff";

const DNS = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";
const URL = "6ba7b811-9dad-11d1-80b4-00c04fd430c8";

const byteToHex = [];
for (let i = 0; i < 256; i++) {
  byteToHex.push((i + 0x100).toString(16).slice(1));
}

function stringify(arr, offset = 0) {
  return (
    byteToHex[arr[offset]] +
    byteToHex[arr[offset + 1]] +
    byteToHex[arr[offset + 2]] +
    byteToHex[arr[offset + 3]] +
    "-" +
    byteToHex[arr[offset + 4]] +
    byteToHex[arr[offset + 5]] +
    "-" +
    byteToHex[arr[offset + 6]] +
    byteToHex[arr[offset + 7]] +
    "-" +
    byteToHex[arr[offset + 8]] +
    byteToHex[arr[offset + 9]] +
    "-" +
    byteToHex[arr[offset + 10]] +
    byteToHex[arr[offset + 11]] +
    byteToHex[arr[offset + 12]] +
    byteToHex[arr[offset + 13]] +
    byteToHex[arr[offset + 14]] +
    byteToHex[arr[offset + 15]]
  );
}

function parse(uuid) {
  const hex = uuid.replace(/-/g, "");
  const bytes = Buffer.alloc(16);
  for (let i = 0; i < 16; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function validate(uuid) {
  return (
    typeof uuid === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(uuid)
  );
}

function version(uuid) {
  return parseInt(uuid.slice(14, 15), 16);
}

function v4() {
  // Node's built-in RFC 4122 v4 generator.
  return crypto.randomUUID();
}

// Build a name-based generator (v3 = MD5, v5 = SHA-1) carrying namespace
// constants, matching the real `uuid` API surface (e.g. `v5.DNS`).
function makeNamedUuid(algorithm, ver) {
  function generate(name, namespace) {
    const nsBytes =
      typeof namespace === "string" ? parse(namespace) : namespace;
    const nameBytes = Buffer.from(name, "utf8");
    const hash = crypto
      .createHash(algorithm)
      .update(Buffer.concat([Buffer.from(nsBytes), nameBytes]))
      .digest();
    const bytes = Buffer.from(hash.subarray(0, 16));
    bytes[6] = (bytes[6] & 0x0f) | (ver << 4);
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    return stringify(bytes);
  }
  generate.DNS = DNS;
  generate.URL = URL;
  return generate;
}

const v3 = makeNamedUuid("md5", 3);
const v5 = makeNamedUuid("sha1", 5);

module.exports = {
  v3,
  v4,
  v5,
  NIL,
  MAX,
  parse,
  stringify,
  validate,
  version,
};
