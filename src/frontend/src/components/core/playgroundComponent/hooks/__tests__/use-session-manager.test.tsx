import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";
import { useSessionManager } from "../use-session-manager";

const FLOW_ID = "flow-1";

const mockGet = jest.fn();
const mockDelete = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));
jest.mock("@/stores/flowStore", () => {
  const state = () => ({ playgroundPage: false });
  return {
    __esModule: true,
    default: Object.assign(
      (selector: (s: ReturnType<typeof state>) => unknown) => selector(state()),
      { getState: state },
    ),
  };
});
jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: () => false,
}));
jest.mock("@/modals/IOModal/hooks/useGetFlowId", () => ({
  useGetFlowId: () => FLOW_ID,
}));
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/utils/utils", () => ({
  prepareSessionIdForAPI: (id: string) => id,
  extractColumnsFromRows: () => [],
}));
jest.mock("../../chat-view/utils/message-utils", () => ({
  clearSessionMessages: jest.fn(),
}));

/**
 * Serves `sessions` from the paged sessions endpoint and answers the
 * one-message existence check with a message for every id in `taken`.
 */
function serve(sessions: string[], taken: string[] = []) {
  mockGet.mockImplementation(
    async (
      url: string,
      { params }: { params: Record<string, string | number> },
    ) => {
      if (url.endsWith("/sessions")) {
        const offset = Number(params.offset);
        return {
          data: sessions.slice(offset, offset + Number(params.limit)),
        };
      }
      return {
        data: taken.includes(String(params.session_id))
          ? [{ id: "m", session_id: params.session_id }]
          : [],
      };
    },
  );
}

const existenceChecks = () =>
  mockGet.mock.calls
    .filter(([url]) => !String(url).endsWith("/sessions"))
    .map(([, { params }]) => params.session_id);

const recentSessions = (count: number) =>
  Array.from({ length: count }, (_, i) => `recent-${i}`);

async function renderManager({ awaitSessions = true } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(
    ({ flowId }: { flowId: string }) => useSessionManager({ flowId }),
    { wrapper, initialProps: { flowId: FLOW_ID } },
  );
  if (awaitSessions) {
    await waitFor(() =>
      expect(hook.result.current.fetchedSessions.length).toBeGreaterThan(0),
    );
  }
  return hook;
}

const activeSessionId = () => useSessionManagerStore.getState().activeSessionId;

beforeEach(() => {
  mockGet.mockReset();
  mockDelete.mockReset();
  mockSetErrorData.mockReset();
  window.sessionStorage.clear();
  useSessionManagerStore.getState().reset();
});

describe("useSessionManager.sessions", () => {
  // The list used to be read from the store during render without a
  // subscription, so it stayed stale until an unrelated re-render.
  it("re-renders with the server sessions once they are synced", async () => {
    serve(["session-a", "session-b"]);

    const { result } = await renderManager();

    await waitFor(() =>
      expect(result.current.sessions).toEqual([
        FLOW_ID,
        "session-a",
        "session-b",
      ]),
    );
  });

  it("does not sync the previous flow's sessions into the next flow while its list loads", async () => {
    let serveFlowB: (response: { data: string[] }) => void = () => {};
    mockGet.mockImplementation(
      (_url: string, { params }: { params: Record<string, string> }) =>
        params.flow_id === "flow-b"
          ? new Promise((resolve) => {
              serveFlowB = resolve;
            })
          : Promise.resolve({ data: ["flow-a-session"] }),
    );
    const { result, rerender } = await renderManager();

    rerender({ flowId: "flow-b" });

    await waitFor(() =>
      expect(useSessionManagerStore.getState().flowId).toBe("flow-b"),
    );
    expect(result.current.sessions).toEqual(["flow-b"]);
    act(() => serveFlowB({ data: ["flow-b-session"] }));
    await waitFor(() =>
      expect(result.current.sessions).toEqual(["flow-b", "flow-b-session"]),
    );
  });
});

describe("useSessionManager.createSession", () => {
  it.each(["available", "taken", "error"] as const)(
    "discards an unmounted playground's %s lookup after reopening the same flow",
    async (outcome) => {
      let answerOldCheck: (response: { data: { id: string }[] }) => void =
        () => {};
      let rejectOldCheck: (error: Error) => void = () => {};
      let checks = 0;
      mockGet.mockImplementation((url: string) => {
        if (url.endsWith("/sessions")) {
          return Promise.resolve({ data: recentSessions(101) });
        }
        if (checks++ === 0) {
          return new Promise((resolve, reject) => {
            answerOldCheck = resolve;
            rejectOldCheck = reject;
          });
        }
        return Promise.resolve({ data: [] });
      });

      const first = await renderManager();
      let oldCheck = Promise.resolve();
      act(() => {
        oldCheck = first.result.current.createSession();
      });
      first.unmount();

      const reopened = await renderManager();
      await act(() => reopened.result.current.createSession());
      await act(() => reopened.result.current.createSession());
      expect(activeSessionId()).toBe("New Session 1");

      await act(async () => {
        if (outcome === "error") {
          rejectOldCheck(new Error("network down"));
        } else {
          answerOldCheck({ data: outcome === "taken" ? [{ id: "m" }] : [] });
        }
        await oldCheck;
      });

      expect(activeSessionId()).toBe("New Session 1");
      expect(existenceChecks()).toEqual([
        "New Session 0",
        "New Session 0",
        "New Session 1",
      ]);
      expect(mockSetErrorData).not.toHaveBeenCalled();
    },
  );

  it("keeps the new lookup guarded after switching away and back to a flow", async () => {
    const answers: ((response: { data: [] }) => void)[] = [];
    mockGet.mockImplementation(
      (url: string, { params }: { params: Record<string, string> }) => {
        if (url.endsWith("/sessions")) {
          return Promise.resolve({
            data:
              params.flow_id === FLOW_ID
                ? recentSessions(101)
                : ["other-flow-session"],
          });
        }
        return new Promise((resolve) => answers.push(resolve));
      },
    );
    const { result, rerender } = await renderManager();
    let oldCheck = Promise.resolve();
    act(() => {
      oldCheck = result.current.createSession();
    });

    rerender({ flowId: "flow-b" });
    await waitFor(() =>
      expect(result.current.fetchedSessions).toEqual(["other-flow-session"]),
    );
    rerender({ flowId: FLOW_ID });
    await waitFor(() =>
      expect(result.current.fetchedSessions).toEqual(recentSessions(100)),
    );

    let newCheck = Promise.resolve();
    act(() => {
      newCheck = result.current.createSession();
    });
    expect(answers).toHaveLength(2);

    await act(async () => {
      answers[0]({ data: [] });
      await oldCheck;
    });
    expect(activeSessionId()).toBe(FLOW_ID);
    await act(() => result.current.createSession());
    expect(answers).toHaveLength(2);

    await act(async () => {
      answers[1]({ data: [] });
      await newCheck;
    });
    expect(activeSessionId()).toBe("New Session 0");
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("names the session synchronously, without a request, when every session is loaded", async () => {
    serve(["New Session 0", "other"]);
    const { result } = await renderManager();

    act(() => {
      void result.current.createSession();
    });

    expect(activeSessionId()).toBe("New Session 1");
    expect(existenceChecks()).toEqual([]);
  });

  it("checks the server while the sessions are still loading", async () => {
    mockGet.mockImplementation(
      async (url: string, { params }: { params: Record<string, string> }) =>
        url.endsWith("/sessions")
          ? new Promise(() => {})
          : {
              data: params.session_id === "New Session 0" ? [{ id: "m" }] : [],
            },
    );
    const { result } = await renderManager({ awaitSessions: false });

    await act(() => result.current.createSession());

    expect(activeSessionId()).toBe("New Session 1");
    expect(existenceChecks()).toEqual(["New Session 0", "New Session 1"]);
  });

  it("skips names that unloaded older sessions already use", async () => {
    serve(recentSessions(101), [
      "New Session 0",
      "New Session 1",
      "New Session 2",
    ]);
    const { result } = await renderManager();

    await act(() => result.current.createSession());

    expect(existenceChecks()).toEqual([
      "New Session 0",
      "New Session 1",
      "New Session 2",
      "New Session 4",
    ]);
    expect(activeSessionId()).toBe("New Session 4");
    expect(result.current.sessions).toContain("New Session 4");
  });

  it("gallops past a long run of taken names instead of giving up", async () => {
    serve(
      recentSessions(101),
      Array.from({ length: 30 }, (_, i) => `New Session ${i}`),
    );
    const { result } = await renderManager();

    await act(() => result.current.createSession());

    expect(existenceChecks()).toEqual([
      "New Session 0",
      "New Session 1",
      "New Session 2",
      "New Session 4",
      "New Session 8",
      "New Session 16",
      "New Session 32",
    ]);
    expect(activeSessionId()).toBe("New Session 32");
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("creates no session and reports an error when every checked name is taken", async () => {
    serve(recentSessions(101));
    const { result } = await renderManager();
    mockGet.mockResolvedValue({ data: [{ id: "m" }] });

    await act(() => result.current.createSession());

    expect(existenceChecks()).toHaveLength(21);
    expect(existenceChecks().at(-1)).toBe(`New Session ${2 ** 19}`);
    expect(activeSessionId()).toBe(FLOW_ID);
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error creating session.",
    });
  });

  it("creates one session when clicked again while the name is checked", async () => {
    serve(recentSessions(101));
    const { result } = await renderManager();

    await act(() =>
      Promise.all([
        result.current.createSession(),
        result.current.createSession(),
      ]),
    );

    expect(existenceChecks()).toEqual(["New Session 0"]);
    expect(
      result.current.sessions.filter((id) => id.startsWith("New Session")),
    ).toEqual(["New Session 0"]);
  });

  it("keeps a name check for one flow from blocking or leaking into the next flow", async () => {
    let answerFlowACheck: (response: { data: [] }) => void = () => {};
    mockGet.mockImplementation(
      (url: string, { params }: { params: Record<string, string> }) => {
        if (url.endsWith("/sessions")) {
          return Promise.resolve({
            data:
              params.flow_id === FLOW_ID
                ? recentSessions(101)
                : ["New Session 4"],
          });
        }
        return new Promise((resolve) => {
          answerFlowACheck = resolve;
        });
      },
    );
    const { result, rerender } = await renderManager();
    let flowACheck = Promise.resolve();
    act(() => {
      flowACheck = result.current.createSession();
    });

    rerender({ flowId: "flow-b" });
    await waitFor(() =>
      expect(result.current.fetchedSessions).toEqual(["New Session 4"]),
    );
    act(() => {
      void result.current.createSession();
    });
    await act(async () => {
      answerFlowACheck({ data: [] });
      await flowACheck;
    });

    expect(activeSessionId()).toBe("New Session 5");
    expect(result.current.sessions).toEqual([
      "flow-b",
      "New Session 5",
      "New Session 4",
    ]);
  });

  it("creates no session and reports an error when the check fails", async () => {
    serve(recentSessions(101));
    const { result } = await renderManager();
    mockGet.mockRejectedValue(new Error("network down"));

    await act(() => result.current.createSession());

    expect(activeSessionId()).toBe(FLOW_ID);
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error creating session.",
    });
  });
});

describe("useSessionManager.bulkDeleteSessions", () => {
  it("deletes on the server every saved session, including one outside the loaded pages", async () => {
    serve(["loaded"]);
    mockDelete.mockResolvedValue({ data: null });
    const { result } = await renderManager();
    // The open session was kept by the store after newer sessions pushed it
    // past the loaded pages; "draft" was never sent.
    act(() => {
      const { sessions } = useSessionManagerStore.getState();
      useSessionManagerStore.setState({
        sessions: [
          { id: "draft", isLocal: true },
          ...sessions,
          { id: "kept-open", isLocal: false },
        ],
      });
    });

    await act(async () => {
      result.current.bulkDeleteSessions(["draft", "loaded", "kept-open"]);
    });

    await waitFor(() => expect(mockDelete).toHaveBeenCalledTimes(1));
    expect(mockDelete.mock.calls[0][1].data).toEqual(["loaded", "kept-open"]);
  });
});
