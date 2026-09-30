import { renderHook } from "@testing-library/react";

type QueryFn = (ctx: { pageParam: number }) => Promise<unknown>;

type InfiniteQueryOptions = {
  enabled?: boolean;
  queryKey: readonly unknown[];
  queryFn: QueryFn;
};

const useInfiniteQueryMock = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  useInfiniteQuery: (options: InfiniteQueryOptions) =>
    useInfiniteQueryMock(options),
}));

const apiGetMock = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => apiGetMock(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/memories",
}));

import { useGetMemoryMessages } from "../use-get-memory-messages";

describe("useGetMemoryMessages", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useInfiniteQueryMock.mockReturnValue({});
    apiGetMock.mockResolvedValue({
      data: { items: [], total: 0, page: 1, size: 50, pages: 0 },
    });
  });

  it("disables the query when memoryId is empty", () => {
    renderHook(() => useGetMemoryMessages({ memoryId: "", sessionId: "s1" }));

    expect(useInfiniteQueryMock).toHaveBeenCalledTimes(1);

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(false);
    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("enables the query when memoryId is present and sessionId is omitted", () => {
    renderHook(() => useGetMemoryMessages({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(true);
  });

  it("throws a clear error if enabled is forced true without memoryId", async () => {
    renderHook(() =>
      useGetMemoryMessages(
        { memoryId: "", sessionId: "s1" },
        { enabled: true },
      ),
    );

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;

    await expect(opts.queryFn({ pageParam: 1 })).rejects.toThrow(
      "memoryId is required",
    );
  });

  it("sends session_id when sessionId is provided", async () => {
    renderHook(() => useGetMemoryMessages({ memoryId: "m1", sessionId: "s1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;

    await opts.queryFn({ pageParam: 2 });

    expect(apiGetMock).toHaveBeenCalledTimes(1);
    const url = String(apiGetMock.mock.calls[0]?.[0] ?? "");
    expect(url).toContain("/api/v1/memories/m1/messages");
    expect(url).toContain("session_id=s1");
    expect(url).toContain("page=2");
  });

  it("omits session_id when sessionId is null or undefined", async () => {
    renderHook(() => useGetMemoryMessages({ memoryId: "m1", sessionId: null }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;

    await opts.queryFn({ pageParam: 1 });

    expect(apiGetMock).toHaveBeenCalledTimes(1);
    const url = String(apiGetMock.mock.calls[0]?.[0] ?? "");
    expect(url).toContain("/api/v1/memories/m1/messages");
    expect(url).not.toContain("session_id");
  });

  it("uses distinct query keys for filtered vs all-sessions calls", () => {
    renderHook(() => useGetMemoryMessages({ memoryId: "m1", sessionId: "s1" }));
    renderHook(() => useGetMemoryMessages({ memoryId: "m1" }));

    const keyFiltered = (
      useInfiniteQueryMock.mock.calls[0]?.[0] as InfiniteQueryOptions
    ).queryKey;
    const keyAll = (
      useInfiniteQueryMock.mock.calls[1]?.[0] as InfiniteQueryOptions
    ).queryKey;

    expect(keyFiltered).not.toEqual(keyAll);
  });
});
