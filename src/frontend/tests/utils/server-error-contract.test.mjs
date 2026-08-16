import assert from "node:assert/strict";
import test from "node:test";
import {
  createPendingRequestTracker,
  createServerErrorContract,
  expectServerError,
  getServerErrorContractFailures,
  observeServerError,
  readResponseBodyWithTimeout,
  sanitizeResponseExcerpt,
  shouldSettleApiRequestOnResponse,
  shouldTrackApiRequest,
} from "./server-error-contract.mjs";

test("redacts structured secrets including whitespace-containing values", () => {
  const excerpt = sanitizeResponseExcerpt(
    JSON.stringify({
      password: "super secret value", // pragma: allowlist secret
      nested: { api_key: "sk-abc def", safe: "visible" }, // pragma: allowlist secret
    }),
  );

  assert.equal(excerpt.includes("super secret value"), false);
  assert.equal(excerpt.includes("sk-abc def"), false);
  assert.equal(excerpt.includes("visible"), true);
  assert.equal((excerpt.match(/\[REDACTED\]/g) ?? []).length, 2);
});

test("redacts quoted secrets and bearer tokens in non-JSON diagnostics", () => {
  const excerpt = sanitizeResponseExcerpt(
    'failure password="super secret value" api_key=sk-abc Authorization: Basic dXNlcjpwYXNz bearer abc.def==', // pragma: allowlist secret
  );

  assert.equal(excerpt.includes("super secret value"), false);
  assert.equal(excerpt.includes("sk-abc"), false);
  assert.equal(excerpt.includes("dXNlcjpwYXNz"), false);
  assert.equal(excerpt.includes("abc.def=="), false);
});

test("redacts unquoted multiword values through the next field boundary", () => {
  const excerpt = sanitizeResponseExcerpt(
    "password=super secret value status=failed",
  );

  assert.equal(excerpt.includes("super secret value"), false);
  assert.equal(excerpt.includes("status=failed"), true);
});

test("redacts auth schemes inside otherwise non-sensitive JSON values", () => {
  const excerpt = sanitizeResponseExcerpt(
    JSON.stringify(["Bearer abc.def==", { message: "Basic dXNlcjpwYXNz" }]),
  );

  assert.equal(excerpt.includes("abc.def=="), false);
  assert.equal(excerpt.includes("dXNlcjpwYXNz"), false);
});

test("redacts assignments inside a valid JSON string", () => {
  const excerpt = sanitizeResponseExcerpt('"password=super secret"');

  assert.equal(excerpt.includes("super secret"), false);
  assert.equal(JSON.parse(excerpt), "password=[REDACTED]");
});

test("redacts assignments inside a non-sensitive structured field", () => {
  const excerpt = sanitizeResponseExcerpt(
    JSON.stringify({ message: "api_key=sk-live-secret" }),
  );

  assert.equal(excerpt.includes("sk-live-secret"), false);
  assert.deepEqual(JSON.parse(excerpt), { message: "api_key=[REDACTED]" });
});

test("redacts provider credentials described in prose", () => {
  const structuredExcerpt = sanitizeResponseExcerpt(
    JSON.stringify({
      detail: "Incorrect API key provided: sk-proj-live-secret",
      nested: { message: "The token was service-token-value" },
    }),
  );
  const plaintextExcerpt = sanitizeResponseExcerpt(
    "Authentication token: auth-token-value request failed",
  );

  assert.equal(structuredExcerpt.includes("sk-proj-live-secret"), false);
  assert.equal(structuredExcerpt.includes("service-token-value"), false);
  assert.equal(plaintextExcerpt.includes("auth-token-value"), false);
  assert.equal((structuredExcerpt.match(/\[REDACTED\]/g) ?? []).length, 2);
});

test("redacts URI userinfo and additional credential fields", () => {
  const excerpt = sanitizeResponseExcerpt(
    JSON.stringify({
      detail: "OperationalError postgresql://admin:P@ssw0rd@db.internal/prod",
      message: "session=abc123 credential=correct horse battery staple",
      DATABASE_URL: "postgresql://another:secret@db.internal/prod", // pragma: allowlist secret
      private_key: "private material", // pragma: allowlist secret
    }),
  );

  for (const secret of [
    "admin",
    "P@ssw0rd",
    "abc123",
    "correct horse",
    "another",
    "private material",
  ]) {
    assert.equal(excerpt.includes(secret), false);
  }
  assert.equal(excerpt.includes("db.internal/prod"), true);
});

test("fully redacts a plaintext database URL assignment", () => {
  const excerpt = sanitizeResponseExcerpt(
    "DATABASE_URL=postgresql://admin:P@ssw0rd@db.internal/prod next=x",
  );

  assert.equal(excerpt, "DATABASE_URL=[REDACTED] next=x");
});

test("bounds sanitized diagnostics", () => {
  assert.equal(sanitizeResponseExcerpt("x".repeat(20), 8), "xxxxxxxx");
});

test(
  "bounds an unresolved response body with a sanitized diagnostic",
  { timeout: 250 },
  async () => {
    const result = await readResponseBodyWithTimeout(
      { text: () => new Promise(() => {}) },
      {
        timeoutMs: 5,
        label: "POST /api/v2/files?password=super-secret",
      },
    );

    assert.deepEqual(result, {
      status: "timeout",
      diagnostic:
        "Timed out after 5ms reading response body for POST /api/v2/files?password=[REDACTED]",
    });
  },
);

test("drains a request that finishes after teardown begins", async () => {
  const tracker = createPendingRequestTracker();
  const request = { id: "late-response" };
  tracker.start(request);

  const drain = tracker.drain(100);
  queueMicrotask(() => tracker.finish(request));

  assert.deepEqual(await drain, []);
});

test("includes an immediate follow-up request in the same drain", async () => {
  const tracker = createPendingRequestTracker();
  const firstRequest = { id: "first" };
  const followUpRequest = { id: "follow-up" };
  tracker.start(firstRequest);

  const drain = tracker.drain(100);
  queueMicrotask(() => {
    tracker.finish(firstRequest);
    tracker.start(followUpRequest);
    queueMicrotask(() => tracker.finish(followUpRequest));
  });

  assert.deepEqual(await drain, []);
});

test("drains tracked requests without admitting background work after teardown", async () => {
  const tracker = createPendingRequestTracker();
  const inFlightRequest = { id: "in-flight" };
  const backgroundRequest = { id: "background-poll" };
  tracker.start(inFlightRequest);
  tracker.stop();

  const drain = tracker.drain(100);
  tracker.start(backgroundRequest);
  queueMicrotask(() => tracker.finish(inFlightRequest));

  assert.deepEqual(await drain, []);
  assert.deepEqual(tracker.snapshot(), []);
});

test("freezes lifecycles while retaining a delayed follow-up 5xx status", async () => {
  const lifecycles = createPendingRequestTracker();
  const statuses = createPendingRequestTracker();
  const contract = createServerErrorContract();
  const inFlightRequest = { id: "in-flight" };
  const backgroundPoll = { id: "background-poll" };
  const followUpRequest = { id: "follow-up-5xx" };
  const postStatusBoundaryPoll = { id: "post-status-boundary-poll" };
  const startRequest = (request) => {
    statuses.start(request);
    lifecycles.start(request);
  };

  startRequest(inFlightRequest);
  lifecycles.stop();
  const lifecycleDrain = lifecycles.drain(200);
  const followUpAdmitted = new Promise((resolve) => {
    queueMicrotask(() => {
      statuses.finish(inFlightRequest);
      lifecycles.finish(inFlightRequest);

      // Polling after the test boundary remains status-observable but cannot
      // extend the frozen finite-lifecycle drain.
      startRequest(backgroundPoll);
      statuses.finish(backgroundPoll);

      setTimeout(() => {
        startRequest(followUpRequest);
        resolve();
      }, 5);
    });
  });

  await followUpAdmitted;
  assert.deepEqual(lifecycles.snapshot(), []);
  assert.deepEqual(statuses.snapshot(), [followUpRequest]);
  assert.deepEqual(await lifecycleDrain, []);

  statuses.stop();
  const statusDrain = statuses.drain(200);
  startRequest(postStatusBoundaryPoll);
  queueMicrotask(() => {
    observeServerError(contract, {
      method: "GET",
      path: "/api/v1/flows/follow-up",
      status: 503,
      responseBody: "temporarily unavailable",
    });
    statuses.finish(followUpRequest);
  });

  assert.deepEqual(await statusDrain, []);
  assert.deepEqual(statuses.snapshot(), []);
  assert.deepEqual(getServerErrorContractFailures(contract), {
    unexpected: [
      {
        method: "GET",
        path: "/api/v1/flows/follow-up",
        status: 503,
        responseBody: "temporarily unavailable",
      },
    ],
    droppedUnexpected: 0,
    missing: [],
  });
});

test("tracks a follow-up request when the drain starts empty", async () => {
  const tracker = createPendingRequestTracker();
  const followUpRequest = { id: "initially-idle-follow-up" };

  const drain = tracker.drain(5);
  queueMicrotask(() => tracker.start(followUpRequest));

  assert.deepEqual(await drain, [followUpRequest]);
});

test("waits through a short quiet period for a delayed follow-up", async () => {
  const tracker = createPendingRequestTracker();
  const firstRequest = { id: "first" };
  const followUpRequest = { id: "delayed-follow-up" };
  tracker.start(firstRequest);

  const drain = tracker.drain(100);
  tracker.finish(firstRequest);
  setTimeout(() => tracker.start(followUpRequest), 5);

  assert.deepEqual(await drain, [followUpRequest]);
});

test("returns unresolved requests after the bounded drain", async () => {
  const tracker = createPendingRequestTracker();
  const request = { id: "unresolved" };
  tracker.start(request);

  assert.deepEqual(await tracker.drain(1), [request]);
});

test("snapshots requests that have not produced a response status", () => {
  const tracker = createPendingRequestTracker();
  const request = { id: "awaiting-response-headers" };
  tracker.start(request);

  assert.deepEqual(tracker.snapshot(), [request]);
  tracker.finish(request);
  assert.deepEqual(tracker.snapshot(), []);
});

test("tracks API operations but not teardown-prone profile image assets", () => {
  assert.equal(
    shouldTrackApiRequest("http://localhost:7860/api/v1/flows/"),
    true,
  );
  assert.equal(
    shouldTrackApiRequest(
      "http://localhost:7860/api/v1/files/profile_pictures/People/avatar-01.svg",
    ),
    false,
  );
  assert.equal(
    shouldTrackApiRequest("http://localhost:3000/assets/app.js"),
    false,
  );
});

test("settles only genuine long-lived API streams when headers arrive", () => {
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/build/job/events?event_delivery=streaming",
      "application/x-ndjson; charset=utf-8",
    ),
    true,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/build/flow/flow?event_delivery=direct",
      "application/x-ndjson",
    ),
    true,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/build/job/events?event_delivery=polling",
      "application/x-ndjson",
    ),
    false,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/flows/",
      "application/json",
    ),
    false,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v2/files/file-id",
      "application/octet-stream",
    ),
    false,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/logs/stream",
      "text/event-stream; charset=utf-8",
    ),
    true,
  );
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:3000/assets/app.js",
      "text/event-stream",
    ),
    false,
  );
});

test("keeps a delayed JSON body tracked and observes its follow-up 5xx", async () => {
  const lifecycles = createPendingRequestTracker();
  const contract = createServerErrorContract();
  const jsonRequest = { id: "ordinary-json" };
  const followUpRequest = { id: "follow-up-5xx" };

  lifecycles.start(jsonRequest);
  assert.equal(
    shouldSettleApiRequestOnResponse(
      "http://localhost:7860/api/v1/flows/",
      "application/json",
    ),
    false,
  );
  assert.deepEqual(lifecycles.snapshot(), [jsonRequest]);

  const drain = lifecycles.drain(200);
  setTimeout(() => {
    // requestfinished fires only after the delayed JSON body is consumed. The
    // application can then issue another request in the same teardown drain.
    lifecycles.finish(jsonRequest);
    lifecycles.start(followUpRequest);
    observeServerError(contract, {
      method: "POST",
      path: "/api/v1/flows/follow-up",
      status: 503,
      responseBody: "temporarily unavailable",
    });
    lifecycles.finish(followUpRequest);
  }, 5);

  assert.deepEqual(await drain, []);
  assert.deepEqual(getServerErrorContractFailures(contract), {
    unexpected: [
      {
        method: "POST",
        path: "/api/v1/flows/follow-up",
        status: 503,
        responseBody: "temporarily unavailable",
      },
    ],
    droppedUnexpected: 0,
    missing: [],
  });
});

const expected = {
  method: "POST",
  path: "/api/v1/variables/",
  status: 503,
  count: 1,
};
const observed = {
  method: "POST",
  path: "/api/v1/variables/",
  status: 503,
  responseBody: "unavailable",
};

test("records an unmatched 5xx as unexpected", () => {
  const contract = createServerErrorContract();
  observeServerError(contract, observed);

  assert.deepEqual(getServerErrorContractFailures(contract), {
    unexpected: [observed],
    droppedUnexpected: 0,
    missing: [],
  });
});

test("accepts the exact expected count", () => {
  const contract = createServerErrorContract();
  expectServerError(contract, expected);
  observeServerError(contract, observed);

  assert.deepEqual(getServerErrorContractFailures(contract), {
    unexpected: [],
    droppedUnexpected: 0,
    missing: [],
  });
});

test("reports an unused expectation", () => {
  const contract = createServerErrorContract();
  expectServerError(contract, expected);

  assert.deepEqual(getServerErrorContractFailures(contract).missing, [
    { ...expected, observed: 0 },
  ]);
});
