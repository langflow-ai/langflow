const mockApiGet = jest.fn();
let mockQueryFn: () => Promise<unknown> = async () => undefined;

jest.mock("@/controllers/API/api", () => ({ api: { get: mockApiGet } }));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/flows"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: (_key: unknown, fn: () => Promise<unknown>) => {
      mockQueryFn = fn;
      return {};
    },
  })),
}));

import { useGetFlowVersions } from "../use-get-flow-versions";

const entries = (count: number, start = 0) =>
  Array.from({ length: count }, (_, index) => ({ id: `v${start + index}` }));

describe("useGetFlowVersions", () => {
  beforeEach(() => mockApiGet.mockReset());

  it("should_read_every_page_when_retained_versions_exceed_one_page", async () => {
    mockApiGet
      .mockResolvedValueOnce({
        data: { entries: entries(100), max_entries: 50 },
      })
      .mockResolvedValueOnce({ data: { entries: entries(3, 100) } });

    useGetFlowVersions({ flowId: "flow-1", all: true });
    const result = (await mockQueryFn()) as {
      entries: { id: string }[];
      max_entries: number;
    };

    expect(result.entries).toHaveLength(103);
    expect(result.entries.at(-1)?.id).toBe("v102");
    expect(result.max_entries).toBe(50);
    expect(mockApiGet).toHaveBeenLastCalledWith(
      "/api/v1/flows/flow-1/versions/",
      {
        params: { limit: 100, offset: 100 },
      },
    );
  });

  it("should_read_one_page_by_default", async () => {
    mockApiGet.mockResolvedValueOnce({
      data: { entries: entries(50), max_entries: 50 },
    });

    useGetFlowVersions({ flowId: "flow-1" });
    await mockQueryFn();

    expect(mockApiGet).toHaveBeenCalledTimes(1);
    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/flows/flow-1/versions/", {
      params: { limit: 50, offset: 0 },
    });
  });
});
