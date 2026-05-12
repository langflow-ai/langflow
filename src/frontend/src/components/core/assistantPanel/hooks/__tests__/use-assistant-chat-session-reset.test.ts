import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * UC9 — Frontend wires POST /api/v1/agentic/sessions/reset to:
 *   - the initial mount of `useAssistantChat` (a brand-new session_id)
 *   - the explicit New session click (`handleClearHistory`)
 * but NOT to `loadSession` (user chose to continue prior work).
 *
 * The reset call wipes the user's registered components on the backend
 * so each session starts with an empty registry overlay, mirroring the
 * "ephemeral per-session" mental model.
 */

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => {},
}));

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => jest.fn(),
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
  return { __esModule: true, default: fn };
});

jest.mock("@/stores/flowStore", () => {
  const state = { setNodes: jest.fn(), setEdges: jest.fn(), paste: jest.fn() };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

jest.mock("short-unique-id", () => {
  let counter = 0;
  return class ShortUniqueId {
    randomUUID() {
      counter += 1;
      return `mock-uid-${counter}`;
    }
  };
});

const TEST_MODEL = {
  id: "openai/gpt-4",
  name: "gpt-4",
  provider: "openai",
  displayName: "GPT-4",
};

describe("useAssistantChat — session reset wiring", () => {
  let fetchMock: jest.Mock;
  let originalFetch: typeof fetch | undefined;

  beforeEach(() => {
    jest.clearAllMocks();
    originalFetch = (global as { fetch?: typeof fetch }).fetch;
    fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok", components_cleared: 0 }),
    });
    (global as unknown as { fetch: typeof fetch }).fetch =
      fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    if (originalFetch === undefined) {
      delete (global as { fetch?: typeof fetch }).fetch;
    } else {
      (global as unknown as { fetch: typeof fetch }).fetch = originalFetch;
    }
  });

  function findResetCall(): { url: string; init: RequestInit } | undefined {
    for (const [url, init] of fetchMock.mock.calls) {
      if (typeof url === "string" && url.includes("agentic/sessions/reset")) {
        return { url, init: (init ?? {}) as RequestInit };
      }
    }
    return undefined;
  }

  it("should_call_reset_endpoint_on_initial_mount", () => {
    renderHook(() => useAssistantChat());

    const call = findResetCall();
    expect(call).toBeDefined();
    // POST with credentials so the cookie chain authenticates.
    expect(call?.init?.method).toBe("POST");
    expect(call?.init?.credentials).toBe("include");
  });

  it("should_include_the_current_session_id_in_the_query_string", () => {
    const { result } = renderHook(() => useAssistantChat());
    const expectedSessionId = result.current.sessionId;

    const call = findResetCall();
    expect(call?.url).toContain(
      `session_id=${encodeURIComponent(expectedSessionId)}`,
    );
  });

  it("should_call_reset_endpoint_when_handleClearHistory_runs", () => {
    const { result } = renderHook(() => useAssistantChat());
    // Drop the mount-time call so the next assertion measures only the
    // explicit clear-history fire.
    fetchMock.mockClear();

    act(() => {
      result.current.handleClearHistory();
    });

    const callsToReset = fetchMock.mock.calls.filter(
      ([url]) =>
        typeof url === "string" && url.includes("agentic/sessions/reset"),
    );
    expect(callsToReset).toHaveLength(1);
  });

  it("should_pass_the_NEW_session_id_when_handleClearHistory_rotates_it", () => {
    const { result } = renderHook(() => useAssistantChat());
    fetchMock.mockClear();

    act(() => {
      result.current.handleClearHistory();
    });
    const newSessionId = result.current.sessionId;

    const call = findResetCall();
    expect(call?.url).toContain(
      `session_id=${encodeURIComponent(newSessionId)}`,
    );
  });

  it("should_NOT_call_reset_endpoint_when_loadSession_runs", () => {
    const { result } = renderHook(() => useAssistantChat());
    fetchMock.mockClear();

    act(() => {
      result.current.loadSession("previously-saved-session-id", []);
    });

    const callsToReset = fetchMock.mock.calls.filter(
      ([url]) =>
        typeof url === "string" && url.includes("agentic/sessions/reset"),
    );
    // Loading a saved session must NOT wipe — user is continuing prior work.
    expect(callsToReset).toEqual([]);
  });

  it("should_swallow_fetch_failures_without_breaking_handleSend", async () => {
    // The reset is best-effort. A network failure must not block the
    // user from typing — handleSend keeps working.
    fetchMock.mockReset();
    fetchMock.mockRejectedValue(new Error("network down"));
    mockPostAssistStream.mockResolvedValue(undefined);

    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("anything", TEST_MODEL);
    });

    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
  });
});
