import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { useGetMessageHistory } from "../use-get-message-history";

const mockGet = jest.fn();
let mockPlayground = false;
let mockAuthenticated = false;
// Rows the mock server no longer has, like a real delete.
const serverDeleted = new Set<string>();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: () => ({ playgroundPage: mockPlayground }) },
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: { getState: () => ({ currentFlowId: "source-flow" }) },
}));
jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: () => mockAuthenticated,
}));
jest.mock("@/utils/utils", () => ({
  prepareSessionIdForAPI: (id: string) => encodeURIComponent(id),
}));

function message(index: number, session = "session-a"): Message {
  return {
    id: `${session}-${index}`,
    flow_id: "flow",
    session_id: session,
    timestamp: new Date(Date.UTC(2026, 0, 1, 0, index)).toISOString(),
    text: `Message ${index}`,
    sender: "User",
    sender_name: "User",
    files: [],
    edit: false,
    background_color: "",
    text_color: "",
  };
}

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  mockGet.mockReset();
  mockPlayground = false;
  mockAuthenticated = false;
  useMessagesStore.getState().clearMessages();
  sessionStorage.clear();
  serverDeleted.clear();
  mockGet.mockImplementation(async (_url, { params }) => {
    const newestFirst = Array.from({ length: 250 }, (_, i) =>
      message(249 - i, decodeURIComponent(params.session_id ?? "session-a")),
    ).filter((m) => !serverDeleted.has(m.id ?? ""));
    let start = 0;
    if (params.before_id) {
      start = newestFirst.findIndex((m) => m.id === params.before_id) + 1;
      if (start === 0) {
        throw {
          isAxiosError: true,
          response: {
            status: 400,
            data: {
              detail: "before_id does not match a message in this history.",
            },
          },
        };
      }
    }
    return { data: newestFirst.slice(start, start + params.limit) };
  });
});

it.each([false, true])(
  "loads all older pages with bounded requests (shared=%s)",
  async (shared) => {
    mockPlayground = shared;
    mockAuthenticated = shared;
    const { result } = renderHook(
      () => useGetMessageHistory({ id: "flow", sessionId: "session-a" }),
      { wrapper: wrapper() },
    );
    await waitFor(() =>
      expect(useMessagesStore.getState().messages).toHaveLength(100),
    );
    expect(result.current.hasNextPage).toBe(true);
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() =>
      expect(useMessagesStore.getState().messages).toHaveLength(200),
    );
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() =>
      expect(useMessagesStore.getState().messages).toHaveLength(250),
    );
    expect(result.current.hasNextPage).toBe(false);
    expect(
      new Set(useMessagesStore.getState().messages.map((m) => m.id)).size,
    ).toBe(250);
    expect(
      mockGet.mock.calls.map(([, config]) => config.params.before_id),
    ).toEqual([undefined, "session-a-150", "session-a-50"]);
    for (const [url, { params }] of mockGet.mock.calls) {
      expect(url.endsWith(shared ? "/messages/shared" : "/messages")).toBe(
        true,
      );
      expect(params).toMatchObject({
        limit: 101,
        order: "DESC",
        session_id: "session-a",
      });
      expect(params).not.toHaveProperty("offset");
      expect(params).toHaveProperty(
        shared ? "source_flow_id" : "flow_id",
        shared ? "source-flow" : "flow",
      );
    }
  },
);

it("preserves live messages and edits when appending older history", async () => {
  const { result } = renderHook(() => useGetMessageHistory({ id: "flow" }), {
    wrapper: wrapper(),
  });
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(100),
  );
  act(() => {
    useMessagesStore.getState().addMessage(message(250));
    useMessagesStore
      .getState()
      .updateMessage({ ...message(249), text: "Edited" });
  });
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(201),
  );
  expect(
    useMessagesStore.getState().messages.find((m) => m.id === "session-a-249")
      ?.text,
  ).toBe("Edited");
  expect(useMessagesStore.getState().messages).toContainEqual(message(250));
});

it("does not restore a deleted row when an older page is appended", async () => {
  const { result } = renderHook(() => useGetMessageHistory({ id: "flow" }), {
    wrapper: wrapper(),
  });
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(100),
  );
  await act(async () => {
    await useMessagesStore.getState().removeMessages(["session-a-249"]);
  });
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(199),
  );
  expect(
    useMessagesStore.getState().messages.some((m) => m.id === "session-a-249"),
  ).toBe(false);
});

it("resets pagination for a different session without mixing histories", async () => {
  const { result, rerender } = renderHook(
    ({ sessionId }) => useGetMessageHistory({ id: "flow", sessionId }),
    { initialProps: { sessionId: "session-a" }, wrapper: wrapper() },
  );
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(100),
  );
  await act(async () => {
    await result.current.fetchNextPage();
  });
  rerender({ sessionId: "session-b" });
  await waitFor(() =>
    expect(
      useMessagesStore
        .getState()
        .messages.every((m) => m.session_id === "session-b"),
    ).toBe(true),
  );
  expect(useMessagesStore.getState().messages).toHaveLength(100);
  const lastParams = mockGet.mock.calls.at(-1)?.[1].params;
  expect(lastParams).toMatchObject({ session_id: "session-b" });
  expect(lastParams).not.toHaveProperty("before_id");
});

it("preserves every anonymous session when the playground saves its message store", async () => {
  mockPlayground = true;
  sessionStorage.setItem(
    "flow",
    JSON.stringify([
      ...Array.from({ length: 150 }, (_, i) => message(i)),
      ...Array.from({ length: 50 }, (_, i) => message(i, "session-b")),
    ]),
  );
  const { result } = renderHook(
    () => useGetMessageHistory({ id: "flow", sessionId: "session-a" }),
    { wrapper: wrapper() },
  );
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(200),
  );
  // The playground writes its full store back after a query or a live message.
  sessionStorage.setItem(
    "flow",
    JSON.stringify(useMessagesStore.getState().messages),
  );
  expect(JSON.parse(sessionStorage.getItem("flow")!)).toHaveLength(200);
  expect(
    useMessagesStore
      .getState()
      .messages.filter((m) => m.session_id === "session-b"),
  ).toHaveLength(50);
  expect(result.current.hasNextPage).toBe(false);
  expect(mockGet).not.toHaveBeenCalled();
});

it("ignores an older-page response after switching sessions", async () => {
  const { result, rerender } = renderHook(
    ({ sessionId }) => useGetMessageHistory({ id: "flow", sessionId }),
    { initialProps: { sessionId: "session-a" }, wrapper: wrapper() },
  );
  await waitFor(() =>
    expect(useMessagesStore.getState().messages).toHaveLength(100),
  );
  let finishOldRequest!: (value: { data: Message[] }) => void;
  mockGet.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishOldRequest = resolve;
      }),
  );
  let oldRequest: Promise<unknown>;
  act(() => {
    oldRequest = result.current.fetchNextPage();
  });
  rerender({ sessionId: "session-b" });
  await waitFor(() =>
    expect(useMessagesStore.getState().messages[0]?.session_id).toBe(
      "session-b",
    ),
  );
  await act(async () => {
    finishOldRequest({ data: [message(1)] });
    await oldRequest;
  });
  expect(useMessagesStore.getState().messages).toHaveLength(100);
  expect(
    useMessagesStore
      .getState()
      .messages.every((m) => m.session_id === "session-b"),
  ).toBe(true);
});

it("stops at exactly one page and honors disabled queries", async () => {
  mockGet.mockResolvedValue({
    data: Array.from({ length: 100 }, (_, i) => message(i)),
  });
  const { result, rerender } = renderHook(
    ({ enabled }) => useGetMessageHistory({ id: "flow", enabled }),
    { initialProps: { enabled: false }, wrapper: wrapper() },
  );
  expect(mockGet).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.hasNextPage).toBe(false);
});

describe("after the cursor row is deleted", () => {
  const loadFirstPage = async () => {
    const hook = renderHook(
      () => useGetMessageHistory({ id: "flow", sessionId: "session-a" }),
      { wrapper: wrapper() },
    );
    await waitFor(() =>
      expect(useMessagesStore.getState().messages).toHaveLength(100),
    );
    return hook;
  };
  const storedIds = () =>
    new Set(
      useMessagesStore.getState().messages.flatMap((m) => (m.id ? [m.id] : [])),
    );
  const requestedCursors = () =>
    mockGet.mock.calls.map(([, config]) => config.params.before_id);

  it("anchors on the oldest row still shown when this view deleted it", async () => {
    const { result } = await loadFirstPage();
    serverDeleted.add("session-a-150");
    await act(async () => {
      await useMessagesStore.getState().removeMessages(["session-a-150"]);
    });

    await act(async () => {
      await result.current.fetchNextPage();
    });

    await waitFor(() => expect(storedIds().size).toBe(199));
    expect(requestedCursors()).toEqual([undefined, "session-a-151"]);
    expect(storedIds().has("session-a-149")).toBe(true);
    expect(storedIds().has("session-a-50")).toBe(true);
  });

  it("falls back to the next-oldest row when it was deleted elsewhere", async () => {
    const { result } = await loadFirstPage();
    serverDeleted.add("session-a-150");

    await act(async () => {
      await result.current.fetchNextPage();
    });

    await waitFor(() => expect(storedIds().size).toBe(200));
    expect(requestedCursors()).toEqual([
      undefined,
      "session-a-150",
      "session-a-151",
    ]);
    expect(result.current.isError).toBe(false);
    expect(storedIds().has("session-a-149")).toBe(true);
  });

  it("continues from the newest page when every loaded row was deleted", async () => {
    const { result } = await loadFirstPage();
    const loaded = [...storedIds()];
    for (const id of loaded) serverDeleted.add(id);
    await act(async () => {
      await useMessagesStore.getState().removeMessages(loaded);
    });

    await act(async () => {
      await result.current.fetchNextPage();
    });

    await waitFor(() => expect(storedIds().size).toBe(100));
    expect(requestedCursors()).toEqual([undefined, undefined]);
    expect(storedIds().has("session-a-149")).toBe(true);
    expect(storedIds().has("session-a-50")).toBe(true);
  });

  it("fails without retrying once no fallback anchor is left", async () => {
    const { result } = await loadFirstPage();
    for (const id of ["session-a-150", "session-a-151", "session-a-152"]) {
      serverDeleted.add(id);
    }

    let outcome: Awaited<ReturnType<typeof result.current.fetchNextPage>>;
    await act(async () => {
      outcome = await result.current.fetchNextPage();
    });

    // The server's own 400 surfaces, so the query layer does not retry it.
    expect(outcome!.isFetchNextPageError).toBe(true);
    expect(outcome!.error).toMatchObject({ response: { status: 400 } });
    expect(requestedCursors()).toEqual([
      undefined,
      "session-a-150",
      "session-a-151",
      "session-a-152",
    ]);
  });
});
