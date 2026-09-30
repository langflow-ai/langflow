const mockApiGet = jest.fn();
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options?: unknown) => {
    const result: { data: unknown; isLoading: boolean; error: unknown } = {
      data: null,
      isLoading: false,
      error: null,
    };

    void fn().then((data) => {
      result.data = data;
    });

    return result;
  },
);

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: mockApiGet,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key: string) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: mockQuery,
  })),
}));

import { useGetTracesQuery } from "../use-get-traces";

describe("useGetTracesQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns empty result when flowId is missing", async () => {
    useGetTracesQuery({ flowId: null });

    await Promise.resolve();

    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("calls API with sanitized params", async () => {
    mockApiGet.mockResolvedValue({ data: { traces: [], total: 0 } });

    useGetTracesQuery({
      flowId: " flow\n1 ",
      sessionId: " sess\t ",
      params: {
        query: " hi\u0001 ",
        status: "ok",
        page: 2,
      },
    });

    await Promise.resolve();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/traces", {
      params: {
        flow_id: "flow1",
        session_id: "sess",
        query: "hi",
        status: "ok",
        page: 2,
      },
    });
  });
});
