// Mock API before imports
const mockApiGet = jest.fn();
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options: unknown) => {
    const result: {
      data: unknown;
      isLoading: boolean;
      error: unknown;
    } = { data: null, isLoading: false, error: null };
    fn()
      .then((data: unknown) => {
        result.data = data;
      })
      .catch((error: unknown) => {
        result.error = error;
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
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: mockQuery,
  })),
}));

import {
  EnabledModelsResponse,
  getEnabledModelsQueryKey,
  useGetEnabledModels,
} from "../use-get-enabled-models";

describe("useGetEnabledModels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("API calls", () => {
    it("should call the correct API endpoint", async () => {
      const mockResponse: EnabledModelsResponse = {
        enabled_models: {
          OpenAI: { "gpt-4": true, "gpt-3.5-turbo": false },
        },
      };
      mockApiGet.mockResolvedValue({ data: mockResponse });

      useGetEnabledModels();

      expect(mockApiGet).toHaveBeenCalledWith("/api/v1/models/enabled_models");
    });

    it("scopes the endpoint and cache key without accepting a workspace id", async () => {
      mockApiGet.mockResolvedValue({ data: { enabled_models: {} } });

      useGetEnabledModels({ flowId: "flow-one" });

      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/models/enabled_models?flow_id=flow-one",
      );
      expect(mockQuery).toHaveBeenCalledWith(
        ["useGetEnabledModels", "flow-one", undefined],
        expect.any(Function),
        undefined,
      );
    });

    it("separates runtime and configuration policy in both the URL and cache key", async () => {
      mockApiGet.mockResolvedValue({ data: { enabled_models: {} } });

      useGetEnabledModels({
        flowId: "flow-one",
        projectId: "project-one",
        purpose: "use",
      });
      useGetEnabledModels({
        flowId: "flow-one",
        projectId: "project-one",
        purpose: "configure",
      });

      expect(mockApiGet).toHaveBeenNthCalledWith(
        1,
        "/api/v1/models/enabled_models?flow_id=flow-one&project_id=project-one&purpose=use",
      );
      expect(mockApiGet).toHaveBeenNthCalledWith(
        2,
        "/api/v1/models/enabled_models?flow_id=flow-one&project_id=project-one&purpose=configure",
      );
      expect(mockQuery).toHaveBeenNthCalledWith(
        1,
        ["useGetEnabledModels", "flow-one", "project-one", "use"],
        expect.any(Function),
        undefined,
      );
      expect(mockQuery).toHaveBeenNthCalledWith(
        2,
        ["useGetEnabledModels", "flow-one", "project-one", "configure"],
        expect.any(Function),
        undefined,
      );
      expect(getEnabledModelsQueryKey({ purpose: "use" })).not.toEqual(
        getEnabledModelsQueryKey({ purpose: "configure" }),
      );
    });

    it("should return enabled models data", async () => {
      const mockResponse: EnabledModelsResponse = {
        enabled_models: {
          OpenAI: { "gpt-4": true },
          Anthropic: { "claude-3": true },
        },
      };
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetEnabledModels();

      // The hook should return a query result object
      expect(result).toBeDefined();
      expect(result).toHaveProperty("data");
    });
  });

  describe("Response structure", () => {
    it("should handle empty enabled_models", async () => {
      const mockResponse: EnabledModelsResponse = {
        enabled_models: {},
      };
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetEnabledModels();
      expect(result).toBeDefined();
    });

    it("should handle multiple providers with multiple models", async () => {
      const mockResponse: EnabledModelsResponse = {
        enabled_models: {
          OpenAI: {
            "gpt-4": true,
            "gpt-4-turbo": true,
            "gpt-3.5-turbo": false,
          },
          Anthropic: {
            "claude-3-opus": true,
            "claude-3-sonnet": true,
          },
          Cohere: {
            "command-r": false,
          },
        },
      };
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetEnabledModels();
      expect(result).toBeDefined();
    });
  });

  describe("Error handling", () => {
    it("should handle API errors", async () => {
      mockApiGet.mockRejectedValue(new Error("Network error"));

      // Hook should not throw, just return error state
      expect(() => useGetEnabledModels()).not.toThrow();
    });
  });
});
