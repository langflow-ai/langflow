import {
  buildWorkflowRunRequest,
  createWorkflowAgent,
  WORKFLOWS_ENDPOINT,
  WORKFLOWS_PUBLIC_ENDPOINT,
} from "../run-agent";

describe("buildWorkflowRunRequest", () => {
  it("returns a native WorkflowRunRequest with input_value mapped from message", () => {
    const body = buildWorkflowRunRequest({
      flowId: "flow-1",
      message: "hello",
    });

    expect(body).toEqual({
      flow_id: "flow-1",
      input_value: "hello",
      mode: "stream",
      stream_protocol: "agui",
    });
  });

  it("defaults input_value to empty string when no message is provided", () => {
    const body = buildWorkflowRunRequest({ flowId: "flow-1" });

    expect(body.input_value).toBe("");
  });

  it("maps threadId to session_id only when explicitly provided", () => {
    const withThread = buildWorkflowRunRequest({
      flowId: "flow-1",
      threadId: "t-9",
    });
    const without = buildWorkflowRunRequest({ flowId: "flow-1" });

    expect(withThread.session_id).toBe("t-9");
    expect(without).not.toHaveProperty("session_id");
  });

  it("drops an empty-string threadId (falsy guard pins current behavior)", () => {
    // Semantic gap: the builder uses `if (opts.threadId)`, so an explicit
    // `""` is indistinguishable from an unset value and session_id is
    // omitted. This test pins that behavior; if we ever switch to
    // `!== undefined` semantics, this assertion flips and the change is
    // a deliberate one.
    const body = buildWorkflowRunRequest({ flowId: "flow-1", threadId: "" });

    expect(body).not.toHaveProperty("session_id");
  });

  it('forwards an explicit mode="stream" and pins stream_protocol', () => {
    const body = buildWorkflowRunRequest({
      flowId: "flow-1",
      mode: "stream",
    });

    expect(body.mode).toBe("stream");
    expect(body.stream_protocol).toBe("agui");
  });

  it("maps tweaks, partial-run ids, flowData and files into native keys", () => {
    const body = buildWorkflowRunRequest({
      flowId: "flow-1",
      tweaks: { "ChatInput-abc": { input_value: "x" } },
      startComponentId: "c1",
      stopComponentId: "c2",
      flowData: { nodes: [{ id: "n1" }], edges: [] },
      files: ["a.txt"],
    });

    expect(body).toMatchObject({
      tweaks: { "ChatInput-abc": { input_value: "x" } },
      start_component_id: "c1",
      stop_component_id: "c2",
      data: { nodes: [{ id: "n1" }], edges: [] },
      files: ["a.txt"],
    });
  });

  it('rejects mode="sync" because the SSE decoder can\'t read a JSON response', () => {
    expect(() =>
      buildWorkflowRunRequest({ flowId: "flow-1", mode: "sync" }),
    ).toThrow(/only supports mode="stream"/);
  });

  it('rejects mode="background" because the response is a job JSON, not SSE', () => {
    expect(() =>
      buildWorkflowRunRequest({ flowId: "flow-1", mode: "background" }),
    ).toThrow(/only supports mode="stream"/);
  });

  it("omits optional native fields when the caller did not set them", () => {
    const body = buildWorkflowRunRequest({ flowId: "flow-1" });

    expect(body).not.toHaveProperty("tweaks");
    expect(body).not.toHaveProperty("start_component_id");
    expect(body).not.toHaveProperty("stop_component_id");
    expect(body).not.toHaveProperty("data");
    expect(body).not.toHaveProperty("files");
  });

  it("never emits AG-UI RunAgentInput keys on the request body", () => {
    const body = buildWorkflowRunRequest({
      flowId: "flow-1",
      message: "hi",
      threadId: "t-1",
      tweaks: { x: { y: 1 } },
      startComponentId: "s",
      stopComponentId: "e",
      flowData: { nodes: [], edges: [] },
      files: ["f"],
    });

    for (const forbidden of [
      "threadId",
      "runId",
      "forwardedProps",
      "state",
      "messages",
      "tools",
      "context",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });
});

describe("createWorkflowAgent", () => {
  it("defaults to the v2 workflows endpoint", () => {
    const agent = createWorkflowAgent({
      body: buildWorkflowRunRequest({ flowId: "flow-1" }),
    });

    expect(agent.url).toBe(WORKFLOWS_ENDPOINT);
  });

  it("uses a caller-provided url", () => {
    const agent = createWorkflowAgent({
      url: "/api/v2/workflows-test",
      body: buildWorkflowRunRequest({ flowId: "flow-1" }),
    });

    expect(agent.url).toBe("/api/v2/workflows-test");
  });

  it("passes custom headers through to the underlying HttpAgent", () => {
    const agent = createWorkflowAgent({
      headers: { "X-Foo": "bar" },
      body: buildWorkflowRunRequest({ flowId: "flow-1" }),
    });

    expect(agent.headers).toMatchObject({ "X-Foo": "bar" });
  });
});

describe("createWorkflowAgent wire body", () => {
  // jsdom does not ship `fetch`, `TextEncoder`, or `TextDecoder`; pull
  // them from Node's `util` so we can spy on fetch and the AG-UI SSE
  // decoder has the codecs it expects.
  beforeAll(() => {
    const g = global as {
      fetch?: unknown;
      TextEncoder?: unknown;
      TextDecoder?: unknown;
    };
    const util = require("util") as {
      TextEncoder: typeof TextEncoder;
      TextDecoder: typeof TextDecoder;
    };
    if (typeof g.TextEncoder !== "function") g.TextEncoder = util.TextEncoder;
    if (typeof g.TextDecoder !== "function") g.TextDecoder = util.TextDecoder;
    if (typeof g.fetch !== "function") {
      g.fetch = () => Promise.reject(new Error("fetch not stubbed"));
    }
  });

  // AG-UI's `runHttpRequest` consumes `.ok`, `.status`, `.headers.get()`,
  // and `.body.getReader()`; this fake response is the minimum surface
  // that satisfies that contract so the SSE decoder runs for real.
  function sseResponse(events: object[]): unknown {
    const encoder = new (
      globalThis as { TextEncoder: typeof TextEncoder }
    ).TextEncoder();
    const payload = encoder.encode(
      events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
    );
    let delivered = false;
    return {
      ok: true,
      status: 200,
      headers: {
        get(key: string) {
          return key.toLowerCase() === "content-type"
            ? "text/event-stream"
            : null;
        },
      },
      body: {
        getReader() {
          return {
            async read() {
              if (delivered) return { done: true, value: undefined };
              delivered = true;
              return { done: false, value: payload };
            },
            async cancel() {
              /* no-op */
            },
          };
        },
      },
      text: async () => "",
    };
  }

  it("posts the native WorkflowRunRequest body (not RunAgentInput) to the endpoint", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
      captured.push({
        url:
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : (input as Request).url,
        init: init ?? {},
      });
      return sseResponse([
        { type: "RUN_STARTED", threadId: "t", runId: "r", timestamp: 0 },
        { type: "RUN_FINISHED", threadId: "t", runId: "r", timestamp: 0 },
      ]);
    };
    const fetchSpy = jest
      .spyOn(global as { fetch: typeof fetch }, "fetch")
      .mockImplementation(fetchImpl as unknown as typeof fetch);

    try {
      const body = buildWorkflowRunRequest({
        flowId: "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
        message: "hello",
        threadId: "session-abc",
      });
      const agent = createWorkflowAgent({ body });

      await new Promise<void>((resolve, reject) => {
        const sub = agent
          .run({
            threadId: "session-abc",
            runId: "",
            state: {},
            messages: [],
            tools: [],
            context: [],
            forwardedProps: {},
          })
          .subscribe({
            error: (err) => {
              sub.unsubscribe();
              reject(err);
            },
            complete: () => {
              sub.unsubscribe();
              resolve();
            },
          });
      });

      expect(captured).toHaveLength(1);
      expect(captured[0].url).toBe(WORKFLOWS_ENDPOINT);
      expect(captured[0].init.method).toBe("POST");
      const wireBody = JSON.parse(captured[0].init.body as string);
      expect(wireBody).toEqual({
        flow_id: "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
        input_value: "hello",
        mode: "stream",
        stream_protocol: "agui",
        session_id: "session-abc",
      });
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it("decodes typed AG-UI events from the SSE response", async () => {
    const fetchSpy = jest
      .spyOn(global as { fetch: typeof fetch }, "fetch")
      .mockImplementation((async () =>
        sseResponse([
          { type: "RUN_STARTED", threadId: "t", runId: "r", timestamp: 0 },
          {
            type: "CUSTOM",
            name: "langflow.event",
            value: { event_type: "token", data: { chunk: "hi" } },
            timestamp: 0,
            rawEvent: {},
          },
          {
            type: "RUN_FINISHED",
            threadId: "t",
            runId: "r",
            timestamp: 0,
          },
        ])) as unknown as typeof fetch);

    try {
      const agent = createWorkflowAgent({
        body: buildWorkflowRunRequest({
          flowId: "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
          message: "hi",
        }),
      });

      const seenTypes: string[] = [];
      await new Promise<void>((resolve, reject) => {
        const sub = agent
          .run({
            threadId: "client-thread",
            runId: "client-run",
            state: {},
            messages: [],
            tools: [],
            context: [],
            forwardedProps: {},
          })
          .subscribe({
            next: (e: { type: string }) => {
              seenTypes.push(e.type);
            },
            error: (err) => {
              sub.unsubscribe();
              reject(err);
            },
            complete: () => {
              sub.unsubscribe();
              resolve();
            },
          });
      });

      expect(seenTypes).toEqual(
        expect.arrayContaining(["RUN_STARTED", "CUSTOM", "RUN_FINISHED"]),
      );
    } finally {
      fetchSpy.mockRestore();
    }
  });
});

describe("buildWorkflowRunRequest — public endpoint shape", () => {
  // The public-flow endpoint's Pydantic schema has ``extra="forbid"``
  // and explicitly omits ``data`` and ``tweaks``. Sending either would
  // 422 the request. Pin the dropping behaviour here so a regression in
  // the bridge surfaces in the unit suite, not as a CI playwright fail.

  it("drops tweaks when usePublicEndpoint is true", () => {
    const body = buildWorkflowRunRequest({
      flowId: "11111111-1111-1111-1111-111111111111",
      message: "hi",
      tweaks: { "node-id": { input_value: "x" } },
      usePublicEndpoint: true,
    });

    expect(body.tweaks).toBeUndefined();
  });

  it("drops flowData when usePublicEndpoint is true", () => {
    const body = buildWorkflowRunRequest({
      flowId: "11111111-1111-1111-1111-111111111111",
      message: "hi",
      flowData: { nodes: [], edges: [] },
      usePublicEndpoint: true,
    });

    expect(body.data).toBeUndefined();
  });

  it("still includes tweaks/data when usePublicEndpoint is false (canvas path)", () => {
    const body = buildWorkflowRunRequest({
      flowId: "11111111-1111-1111-1111-111111111111",
      message: "hi",
      tweaks: { "node-id": { input_value: "x" } },
      flowData: { nodes: [], edges: [] },
      usePublicEndpoint: false,
    });

    expect(body.tweaks).toEqual({ "node-id": { input_value: "x" } });
    expect(body.data).toEqual({ nodes: [], edges: [] });
  });
});

describe("WORKFLOWS_PUBLIC_ENDPOINT", () => {
  it("is the canonical /api/v2/workflows/public path", () => {
    expect(WORKFLOWS_PUBLIC_ENDPOINT).toBe("/api/v2/workflows/public");
  });
});
