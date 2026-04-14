const mockApiGet = jest.fn();
const mockApiPatch = jest.fn();
const mockApiDelete = jest.fn();

const mockQueryClient = {
  refetchQueries: jest.fn(),
};

const mockSetGlobalVariablesEntries = jest.fn();
const mockSetUnavailableFields = jest.fn();
const mockSetGlobalVariablesEntities = jest.fn();

let mockIsAuthenticated = true;

// Mock query that properly resolves data via async execution
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options?: unknown) => {
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    const result: { data: any; isLoading: boolean; error: unknown } = {
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
    patch: mockApiPatch,
    delete: mockApiDelete,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/variables"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: mockQuery,
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      // biome-ignore lint/suspicious/noExplicitAny: test mock
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSettled?.(result);
        return result;
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = { isAuthenticated: mockIsAuthenticated };
    return selector(state);
  },
}));

jest.mock("@/stores/globalVariablesStore/globalVariables", () => ({
  useGlobalVariablesStore: (
    selector: (state: Record<string, unknown>) => unknown,
  ) => {
    const state = {
      setGlobalVariablesEntries: mockSetGlobalVariablesEntries,
      setUnavailableFields: mockSetUnavailableFields,
      setGlobalVariablesEntities: mockSetGlobalVariablesEntities,
    };
    return selector(state);
  },
}));

jest.mock("@/stores/globalVariablesStore/utils/get-unavailable-fields", () => ({
  __esModule: true,
  default: jest.fn(() => ({ field1: true })),
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  refreshAllModelInputs: jest.fn(),
}));

import { useGetGlobalVariables } from "../use-get-global-variables";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

// ─── useGetGlobalVariables ────────────────────────────────────────────────────

describe("useGetGlobalVariables", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockIsAuthenticated = true;
  });

  it("updates Zustand store entries, unavailable fields, and entities", async () => {
    const variables = [
      { id: "v1", name: "OPENAI_KEY", value: "sk-123", default_fields: [] },
      { id: "v2", name: "SECRET", value: "abc", default_fields: ["field1"] },
    ];
    mockApiGet.mockResolvedValue({ data: variables });

    useGetGlobalVariables();
    await flushPromises();

    expect(mockSetGlobalVariablesEntries).toHaveBeenCalledWith([
      "OPENAI_KEY",
      "SECRET",
    ]);
    expect(mockSetUnavailableFields).toHaveBeenCalled();
    expect(mockSetGlobalVariablesEntities).toHaveBeenCalledWith(variables);
  });

  it("returns empty array when not authenticated", async () => {
    mockIsAuthenticated = false;

    const result = useGetGlobalVariables();
    await flushPromises();

    expect(result.data).toEqual([]);
    expect(mockApiGet).not.toHaveBeenCalled();
  });
});

