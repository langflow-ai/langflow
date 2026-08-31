import assert from "node:assert/strict";
import test from "node:test";
import { getDefaultProjectIdForTest } from "./get-default-project-id-for-test.mjs";

function mockPage({ body, ok = true, status = 200, statusText = "OK" }) {
  return {
    request: {
      get: async (path) => {
        assert.equal(path, "/api/v1/projects/");
        return {
          json: async () => body,
          ok: () => ok,
          status: () => status,
          statusText: () => statusText,
        };
      },
    },
  };
}

test("selects the first owned project", async () => {
  const page = mockPage({
    body: [
      { id: "shared", is_owner: false },
      { id: "owned", is_owner: true },
      { id: "owned-later", is_owner: true },
    ],
  });

  assert.equal(await getDefaultProjectIdForTest(page), "owned");
});

test("falls back to the first valid project", async () => {
  const page = mockPage({
    body: [
      { id: "shared", is_owner: false },
      { id: "shared-later", is_owner: false },
    ],
  });

  assert.equal(await getDefaultProjectIdForTest(page), "shared");
});

test("rejects a non-success response", async () => {
  const page = mockPage({
    body: [],
    ok: false,
    status: 503,
    statusText: "Service Unavailable",
  });

  await assert.rejects(
    getDefaultProjectIdForTest(page),
    /failed with 503 Service Unavailable/,
  );
});

test("rejects a non-array payload", async () => {
  const page = mockPage({ body: { id: "not-an-array" } });

  await assert.rejects(
    getDefaultProjectIdForTest(page),
    /returned a non-array payload/,
  );
});

test("rejects an empty or invalid project list", async () => {
  const emptyPage = mockPage({ body: [] });
  const invalidPage = mockPage({
    body: [
      { id: "missing-owner" },
      { id: 123, is_owner: true },
      { id: "invalid-owner", is_owner: "true" },
    ],
  });

  await assert.rejects(
    getDefaultProjectIdForTest(emptyPage),
    /returned no valid projects/,
  );
  await assert.rejects(
    getDefaultProjectIdForTest(invalidPage),
    /returned no valid projects/,
  );
});
