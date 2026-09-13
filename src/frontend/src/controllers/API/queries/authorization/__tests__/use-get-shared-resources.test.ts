const mockApiGet = jest.fn();
const mockQuery = jest.fn();
let capturedQueryFn: (() => Promise<unknown>) | undefined;

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn((selector: (state: unknown) => unknown) =>
    selector({ userData: { id: "user-1" } }),
  ),
}));

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `/api/v1/${key.toLowerCase()}`,
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: (...args: unknown[]) => mockQuery(...args),
  }),
}));

import { useGetSharedResources } from "../use-get-shared-resources";

describe("useGetSharedResources", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedQueryFn = undefined;
    mockQuery.mockImplementation(
      (_key: unknown, queryFn: () => Promise<unknown>) => {
        capturedQueryFn = queryFn;
        return { data: undefined, isLoading: false, isError: false };
      },
    );
  });

  it("requests bounded flow and project pages and keys the cache by pagination", async () => {
    const params = {
      flowPage: 2,
      flowSize: 10,
      projectPage: 3,
      projectSize: 25,
    };
    const flowPage = { items: [], page: 2, size: 10, pages: 2, total: 15 };
    const projectPage = {
      items: [],
      page: 3,
      size: 25,
      pages: 3,
      total: 55,
    };
    mockApiGet
      .mockResolvedValueOnce({ data: flowPage })
      .mockResolvedValueOnce({ data: projectPage });

    useGetSharedResources(params);
    await expect(capturedQueryFn?.()).resolves.toEqual({
      flows: flowPage,
      projects: projectPage,
    });

    expect(mockQuery.mock.calls[0][0]).toEqual([
      "authorizationSharedResources",
      "user-1",
      params,
    ]);
    expect(mockApiGet).toHaveBeenNthCalledWith(1, "/api/v1/flows/", {
      params: { get_all: false, shared_only: true, page: 2, size: 10 },
    });
    expect(mockApiGet).toHaveBeenNthCalledWith(2, "/api/v1/projects/", {
      params: { get_all: false, shared_only: true, page: 3, size: 25 },
    });
  });
});
