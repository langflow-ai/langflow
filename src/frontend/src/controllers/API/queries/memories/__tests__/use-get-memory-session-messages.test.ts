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

import { useGetMemorySessionMessages } from "../use-get-memory-session-messages";

describe("useGetMemorySessionMessages", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useInfiniteQueryMock.mockReturnValue({});
  });

  it("disables the query when memoryId is empty", () => {
    renderHook(() =>
      useGetMemorySessionMessages({ memoryId: "", sessionId: "s1" }),
    );

    expect(useInfiniteQueryMock).toHaveBeenCalledTimes(1);

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(false);
    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("disables the query when sessionId is empty", () => {
    renderHook(() =>
      useGetMemorySessionMessages({ memoryId: "m1", sessionId: "" }),
    );

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;
    expect(opts.enabled).toBe(false);
    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("throws a clear error if enabled is forced true without memoryId", async () => {
    renderHook(() =>
      useGetMemorySessionMessages(
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

  it("throws a clear error if enabled is forced true without sessionId", async () => {
    renderHook(() =>
      useGetMemorySessionMessages(
        { memoryId: "m1", sessionId: "" },
        { enabled: true },
      ),
    );

    const opts = useInfiniteQueryMock.mock
      .calls[0]?.[0] as InfiniteQueryOptions;

    await expect(opts.queryFn({ pageParam: 1 })).rejects.toThrow(
      "sessionId is required",
    );
  });
});
