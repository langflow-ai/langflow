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

const mockConvertTrace = jest.fn<unknown, [unknown]>();

jest.mock("../helpers", () => ({
  convertTrace: (data: unknown) => mockConvertTrace(data),
}));

import { useGetTraceQuery } from "../use-get-trace";

describe("useGetTraceQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null when traceId is missing", async () => {
    useGetTraceQuery({ traceId: "" });

    await Promise.resolve();

    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("calls API and converts response", async () => {
    const apiTrace = { id: "trace-1", spans: [] };
    mockApiGet.mockResolvedValue({ data: apiTrace });
    mockConvertTrace.mockReturnValue({ id: "trace-1" });

    useGetTraceQuery({ traceId: "trace-1" });

    await Promise.resolve();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/traces/trace-1");
    expect(mockConvertTrace).toHaveBeenCalledWith(apiTrace);
  });
});
