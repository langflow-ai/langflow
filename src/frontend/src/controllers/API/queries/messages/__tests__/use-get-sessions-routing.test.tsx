import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { ChatSessionsDropdown } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sessions-dropdown";
import { useGetSessionsFromFlowQuery } from "../use-get-sessions-from-flow";

const mockGet = jest.fn();
let mockPlayground = false;
let mockUserId = "user-a";
let mockAuthenticated = false;
let mockSourceFlowId = "source-flow";

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow",
  }),
);

type FlowState = { playgroundPage: boolean };
type ManagerState = { currentFlowId: string };
type AuthState = {
  userData: { id: string };
  isAuthenticated: boolean;
  autoLogin: boolean;
};

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: Object.assign(
    <T,>(selector: (state: FlowState) => T) =>
      selector({ playgroundPage: mockPlayground }),
    { getState: () => ({ playgroundPage: mockPlayground }) },
  ),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: Object.assign(
    <T,>(selector: (state: ManagerState) => T) =>
      selector({ currentFlowId: mockSourceFlowId }),
    { getState: () => ({ currentFlowId: mockSourceFlowId }) },
  ),
}));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: Object.assign(
    <T,>(selector: (state: AuthState) => T) =>
      selector({
        userData: { id: mockUserId },
        isAuthenticated: mockAuthenticated,
        autoLogin: false,
      }),
    {
      getState: () => ({
        userData: { id: mockUserId },
        isAuthenticated: mockAuthenticated,
        autoLogin: false,
      }),
    },
  ),
}));

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
  mockUserId = "user-a";
  mockSourceFlowId = "source-flow";
  sessionStorage.clear();
  mockGet.mockImplementation(async (_url, { params }) => ({
    data: Array.from({ length: 250 }, (_, index) => `session-${index}`).slice(
      params.offset ?? 0,
      (params.offset ?? 0) + (params.limit ?? 250),
    ),
  }));
});

it.each([false, true])(
  "only fetches older sessions on demand (shared=%s)",
  async (shared) => {
    mockPlayground = shared;
    mockAuthenticated = shared;
    const { result } = renderHook(
      () => useGetSessionsFromFlowQuery({ id: "flow" }),
      { wrapper: wrapper() },
    );
    await waitFor(() =>
      expect(result.current.data?.sessions).toHaveLength(101),
    );
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result.current.data?.sessions[0]).toBe("flow");
    expect(result.current.hasNextPage).toBe(true);
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() =>
      expect(result.current.data?.sessions).toHaveLength(201),
    );
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() =>
      expect(result.current.data?.sessions).toHaveLength(251),
    );
    expect(result.current.hasNextPage).toBe(false);
    expect(result.current.data?.sessions.at(-1)).toBe("session-249");
    expect(
      mockGet.mock.calls.map(([, config]) => config.params.offset),
    ).toEqual([0, 100, 200]);
    for (const [url, { params }] of mockGet.mock.calls) {
      expect(
        url.endsWith(shared ? "/shared/sessions" : "/messages/sessions"),
      ).toBe(true);
      expect(params).toMatchObject({
        limit: 101,
        [shared ? "source_flow_id" : "flow_id"]: shared
          ? "source-flow"
          : "flow",
      });
    }
  },
);

it("deduplicates overlapping pages and pins the default without changing offsets", async () => {
  const firstPage = Array.from({ length: 101 }, (_, index) =>
    index === 50 ? "flow" : `session-${index}`,
  );
  mockGet
    .mockResolvedValueOnce({ data: firstPage })
    .mockResolvedValueOnce({ data: ["session-99", "session-100", "flow"] });
  const { result } = renderHook(
    () => useGetSessionsFromFlowQuery({ id: "flow" }),
    { wrapper: wrapper() },
  );
  await waitFor(() => expect(result.current.data?.sessions).toHaveLength(100));
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() => expect(result.current.hasNextPage).toBe(false));
  const sessions = result.current.data!.sessions;
  expect(sessions).toHaveLength(101);
  expect(new Set(sessions).size).toBe(sessions.length);
  expect(sessions[0]).toBe("flow");
  expect(mockGet.mock.calls[1][1].params.offset).toBe(100);
});

it("does not reuse pages across flows, shared modes, source flows or users", async () => {
  const { result, rerender } = renderHook(
    ({ id }) => useGetSessionsFromFlowQuery({ id }),
    { initialProps: { id: "flow-a" }, wrapper: wrapper() },
  );
  await waitFor(() => expect(result.current.data?.sessions).toHaveLength(101));
  await act(async () => {
    await result.current.fetchNextPage();
  });
  mockGet.mockResolvedValue({ data: ["flow-b-session"] });
  rerender({ id: "flow-b" });
  expect(result.current.data).toBeUndefined();
  await waitFor(() =>
    expect(result.current.data?.sessions).toEqual(["flow-b", "flow-b-session"]),
  );
  expect(mockGet.mock.calls.at(-1)[1].params.offset).toBe(0);

  mockPlayground = true;
  mockAuthenticated = true;
  mockGet.mockResolvedValue({ data: ["shared-session"] });
  rerender({ id: "flow-b" });
  expect(result.current.data).toBeUndefined();
  await waitFor(() =>
    expect(result.current.data?.sessions).toEqual(["flow-b", "shared-session"]),
  );

  mockSourceFlowId = "other-source";
  mockGet.mockResolvedValue({ data: ["other-source-session"] });
  rerender({ id: "flow-b" });
  expect(result.current.data).toBeUndefined();
  await waitFor(() =>
    expect(result.current.data?.sessions).toEqual([
      "flow-b",
      "other-source-session",
    ]),
  );
  expect(mockGet.mock.calls.at(-1)[1].params).toMatchObject({
    source_flow_id: "other-source",
    offset: 0,
  });

  mockUserId = "user-b";
  mockGet.mockResolvedValue({ data: ["user-b-session"] });
  rerender({ id: "flow-b" });
  expect(result.current.data).toBeUndefined();
  await waitFor(() =>
    expect(result.current.data?.sessions).toEqual(["flow-b", "user-b-session"]),
  );
  expect(mockGet.mock.calls.at(-1)[1].params.offset).toBe(0);
});

it("ignores a pending old page after switching flows", async () => {
  const { result, rerender } = renderHook(
    ({ id }) => useGetSessionsFromFlowQuery({ id }),
    { initialProps: { id: "flow-a" }, wrapper: wrapper() },
  );
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  let finish!: (value: { data: string[] }) => void;
  mockGet.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  let oldPage!: Promise<unknown>;
  act(() => {
    oldPage = result.current.fetchNextPage();
  });
  mockGet.mockResolvedValue({ data: ["new-flow-session"] });
  rerender({ id: "flow-b" });
  await waitFor(() =>
    expect(result.current.data?.sessions).toEqual([
      "flow-b",
      "new-flow-session",
    ]),
  );
  await act(async () => {
    finish({ data: ["old-flow-session"] });
    await oldPage;
  });
  expect(result.current.data?.sessions).toEqual(["flow-b", "new-flow-session"]);
});

it("pages anonymous sessions without discarding stored messages", async () => {
  mockPlayground = true;
  const stored = JSON.stringify(
    Array.from({ length: 250 }, (_, index) => ({
      session_id: `session-${index}`,
    })),
  );
  sessionStorage.setItem("flow", stored);
  const { result } = renderHook(
    () => useGetSessionsFromFlowQuery({ id: "flow" }),
    { wrapper: wrapper() },
  );
  await waitFor(() => expect(result.current.data?.sessions).toHaveLength(101));
  expect(result.current.data?.sessions[1]).toBe("session-249");
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() => expect(result.current.data?.sessions).toHaveLength(201));
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() => expect(result.current.hasNextPage).toBe(false));
  expect(result.current.data?.sessions).toHaveLength(251);
  expect(sessionStorage.getItem("flow")).toBe(stored);
  expect(mockGet).not.toHaveBeenCalled();
});

it("stops at an exact page and respects disabled queries", async () => {
  mockGet.mockResolvedValue({
    data: Array.from({ length: 100 }, (_, index) => `session-${index}`),
  });
  const { result, rerender } = renderHook(
    ({ enabled }) => useGetSessionsFromFlowQuery({ id: "flow" }, { enabled }),
    { initialProps: { enabled: false }, wrapper: wrapper() },
  );
  expect(mockGet).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.hasNextPage).toBe(false);
});

it("loads and selects an older session from the dropdown without closing it on load", async () => {
  const sessions = Array.from(
    { length: 101 },
    (_, index) => `session-${index}`,
  );
  mockGet.mockImplementation(async (_url, { params }) => ({
    data: sessions.slice(params.offset, params.offset + params.limit),
  }));
  const onSessionSelect = jest.fn();
  const onOpenChange = jest.fn();
  function Picker() {
    const query = useGetSessionsFromFlowQuery({ id: "flow" });
    return (
      <ChatSessionsDropdown
        open
        onOpenChange={onOpenChange}
        sessions={query.data?.sessions ?? []}
        hasMoreSessions={query.hasNextPage}
        isLoadingSessions={query.isFetchingNextPage}
        onLoadMoreSessions={() => {
          void query.fetchNextPage();
        }}
        onSessionSelect={onSessionSelect}
      />
    );
  }
  render(<Picker />, { wrapper: wrapper() });
  await screen.findByText("session-99");
  expect(screen.queryByText("session-100")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("load-more-sessions"));
  await screen.findByText("session-100");
  expect(onOpenChange).not.toHaveBeenCalled();
  expect(mockGet).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByText("session-100"));
  expect(onSessionSelect).toHaveBeenCalledWith("session-100");
});
