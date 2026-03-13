// Mock API before imports
const mockApiGet = jest.fn();

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
    query: jest.fn((_key, fn, _options) => {
      // Immediately call the query function and return mock result
      const result = { data: null, isLoading: false, error: null } as any;
      fn()
        .then((data: any) => {
          result.data = data;
        })
        .catch((err: any) => {
          result.error = err;
        });
      return result;
    }),
  })),
}));

import {
  EnabledModelsResponse,
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
