import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { resolveBlobReports } from "./resolve-blob-reports.mjs";

function fixture(t, paths) {
  const root = mkdtempSync(join(tmpdir(), "langflow-blob-manifest-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const path of paths) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), "report fixture");
  }
  return root;
}

test("accepts the flattened single-artifact download without inventing its attempt", (t) => {
  const root = fixture(t, ["report.zip"]);
  assert.deepEqual(resolveBlobReports(root, 1), [
    { shard: 1, attempt: null, path: join(root, "report.zip") },
  ]);
});

test("keeps successful shards from earlier attempts and selects the newest rerun", (t) => {
  const root = fixture(t, [
    "blob-report-authz-Linux-1-of-2-attempt-2/old.zip",
    "blob-report-authz-Linux-1-of-2-attempt-11/new.zip",
    "blob-report-authz-Linux-2-of-2-attempt-1/second.zip",
  ]);
  assert.deepEqual(
    resolveBlobReports(root, 2).map(({ shard, attempt }) => ({
      shard,
      attempt,
    })),
    [
      { shard: 1, attempt: 11 },
      { shard: 2, attempt: 1 },
    ],
  );
});

for (const [label, paths, expected, error] of [
  ["multiple flat reports", ["first.zip", "second.zip"], 1, /flat download/],
  ["missing flat shard", ["report.zip"], 2, /flat download/],
  [
    "mixed layouts",
    ["report.zip", "blob-report-authz-Linux-1-of-1-attempt-1/report.zip"],
    1,
    /flat download/,
  ],
  [
    "missing named shard",
    ["blob-report-core-Linux-1-of-2-attempt-1/report.zip"],
    2,
    /Missing blob reports/,
  ],
  [
    "wrong total",
    ["blob-report-core-Linux-1-of-2-attempt-1/report.zip"],
    1,
    /Invalid report artifact/,
  ],
  [
    "out-of-range shard",
    ["blob-report-core-Linux-3-of-2-attempt-1/report.zip"],
    2,
    /Invalid report artifact/,
  ],
  [
    "multiple zips in one artifact",
    [
      "blob-report-authz-Linux-1-of-1-attempt-1/a.zip",
      "blob-report-authz-Linux-1-of-1-attempt-1/b.zip",
    ],
    1,
    /Expected one blob zip/,
  ],
  [
    "duplicate shard attempt",
    [
      "blob-report-core-Linux-1-of-1-attempt-1/a.zip",
      "blob-report-authz-Linux-1-of-1-attempt-1/b.zip",
    ],
    1,
    /Ambiguous reports/,
  ],
  ["empty directory", [], 1, /Missing blob reports/],
  [
    "unrecognized artifact",
    ["unknown/report.zip"],
    1,
    /Unrecognized report artifact/,
  ],
  ["invalid expected count", ["report.zip"], 0, /positive integer/],
]) {
  test(`rejects ${label}`, (t) => {
    assert.throws(() => resolveBlobReports(fixture(t, paths), expected), error);
  });
}
