import { renderHook } from "@testing-library/react";

type QueryFn = (ctx: { pageParam: number }) => Promise<unknown>;

type InfiniteQueryOptions = {
  enabled?: boolean;
  queryKey: readonly unknown[];
  queryFn: QueryFn;
  initialPageParam?: number;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  getNextPageParam?: (lastPage: any) => number | undefined;
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

import { useGetMemorySessions } from "../use-get-memory-sessions";

describe("useGetMemorySessions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useInfiniteQueryMock.mockReturnValue({});
  });

  it("disables the query when memoryId is empty", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(false);
    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("enables the query when memoryId is provided", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(true);
  });

  it("sets initialPageParam to 1", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.initialPageParam).toBe(1);
  });

  it("includes memoryId and default size in the query key", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.queryKey).toContain("m1");
    expect(opts.queryKey).toContain(50);
  });

  it("uses custom size in the query key when provided", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1", size: 10 }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.queryKey).toContain(10);
  });

  it("getNextPageParam returns next page when pages remain", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    const result = opts.getNextPageParam?.({ page: 1, pages: 3 });
    expect(result).toBe(2);
  });

  it("getNextPageParam returns undefined when on the last page", () => {
    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    const result = opts.getNextPageParam?.({ page: 3, pages: 3 });
    expect(result).toBeUndefined();
  });

  it("throws when memoryId is missing but query is forced enabled", async () => {
    renderHook(() => useGetMemorySessions({ memoryId: "" }, { enabled: true }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    await expect(opts.queryFn({ pageParam: 1 })).rejects.toThrow(
      "memoryId is required",
    );
  });

  it("builds the correct URL with page and size query params", async () => {
    apiGetMock.mockResolvedValue({
      data: { items: [], total: 0, page: 1, size: 50, pages: 1 },
    });

    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    await opts.queryFn({ pageParam: 2 });

    const calledUrl: string = apiGetMock.mock.calls[0]?.[0];
    expect(calledUrl).toContain("/m1/sessions");
    expect(calledUrl).toContain("page=2");
    expect(calledUrl).toContain("size=50");
  });

  it("normalises the API response with safe defaults", async () => {
    apiGetMock.mockResolvedValue({ data: {} });

    renderHook(() => useGetMemorySessions({ memoryId: "m1" }));

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    const result: any = await opts.queryFn({ pageParam: 1 });

    expect(result.items).toEqual([]);
    expect(result.total).toBe(0);
    expect(result.pages).toBe(1);
  });
});
