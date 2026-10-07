import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { useGetMessageHistory } from "../use-get-message-history";

const mockGet = jest.fn();
let mockPlayground = false;
let mockAuthenticated = false;

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
  mockGet.mockImplementation(async (_url, { params }) => ({
    data: Array.from({ length: 250 }, (_, i) =>
      message(249 - i, decodeURIComponent(params.session_id ?? "session-a")),
    ).slice(params.offset, params.offset + params.limit),
  }));
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
      mockGet.mock.calls.map(([, config]) => config.params.offset),
    ).toEqual([0, 100, 200]);
    for (const [url, { params }] of mockGet.mock.calls) {
      expect(url.endsWith(shared ? "/messages/shared" : "/messages")).toBe(
        true,
      );
      expect(params).toMatchObject({
        limit: 101,
        order: "DESC",
        session_id: "session-a",
      });
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
  expect(mockGet.mock.calls.at(-1)?.[1].params).toMatchObject({
    session_id: "session-b",
    offset: 0,
  });
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
