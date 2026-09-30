import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * WS-3 / RC-3 — session-scoped component lifetime.
 *
 * Requirement CHANGED (decision 2026-05-15): user-generated components must
 * survive a panel re-mount / page reload. They are wiped ONLY on an explicit
 * "New session" (`handleClearHistory`), never on mount — otherwise a
 * component generated in one turn vanishes before the next request can use
 * it (report #3 "só funciona no 1º pedido", screenshot 2).
 *
 * So the reset endpoint (`POST /api/v1/agentic/sessions/reset`, which wipes
 * the user's registered components) is wired to:
 *   - the explicit New session click (`handleClearHistory`)  — YES
 *   - the initial mount of `useAssistantChat`                — NO  (changed)
 *   - `loadSession` (user chose to continue prior work)      — NO
 *
 * Why the old mount-wipe tests were replaced (not deleted to "go green"):
 * the behavior they pinned is exactly the bug. See git history / PR.
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

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn().mockResolvedValue(undefined),
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

  it("should_NOT_call_reset_endpoint_on_initial_mount", () => {
    // Components must survive a panel open. Wiping on mount is the bug.
    renderHook(() => useAssistantChat());

    expect(findResetCall()).toBeUndefined();
  });

  it("should_NOT_call_reset_endpoint_on_remount_so_components_survive_reload", () => {
    const first = renderHook(() => useAssistantChat());
    first.unmount();
    fetchMock.mockClear();

    // Re-mounting (panel reopen / page reload) must not wipe the user's
    // registered components.
    renderHook(() => useAssistantChat());

    const callsToReset = fetchMock.mock.calls.filter(
      ([url]) =>
        typeof url === "string" && url.includes("agentic/sessions/reset"),
    );
    expect(callsToReset).toEqual([]);
  });

  it("should_include_the_session_id_in_the_query_string_on_clear_history", () => {
    const { result } = renderHook(() => useAssistantChat());
    fetchMock.mockClear();

    act(() => {
      result.current.handleClearHistory();
    });

    const call = findResetCall();
    expect(call?.url).toContain(
      `session_id=${encodeURIComponent(result.current.sessionId)}`,
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
