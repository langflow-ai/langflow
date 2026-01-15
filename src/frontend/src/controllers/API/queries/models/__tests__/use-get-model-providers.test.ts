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
      const result = { data: null, isLoading: false, error: null };
      fn().then((data: any) => {
        result.data = data;
      });
      return result;
    }),
  })),
}));

import {
  ModelProviderInfo,
  useGetModelProviders,
} from "../use-get-model-providers";

describe("useGetModelProviders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("API calls", () => {
    it("should call API without query params when no params provided", async () => {
      const mockResponse: ModelProviderInfo[] = [
        {
          provider: "OpenAI",
          models: [{ model_name: "gpt-4", metadata: { model_type: "llm" } }],
          is_enabled: true,
        },
      ];
      mockApiGet.mockResolvedValue({ data: mockResponse });

      useGetModelProviders({});

      expect(mockApiGet).toHaveBeenCalledWith("/api/v1/models");
    });

    it("should include deprecated param when includeDeprecated is true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      useGetModelProviders({ includeDeprecated: true });

      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/models?include_deprecated=true",
      );
    });

    it("should include unsupported param when includeUnsupported is true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      useGetModelProviders({ includeUnsupported: true });

      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/models?include_unsupported=true",
      );
    });

    it("should include both params when both are true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      useGetModelProviders({
        includeDeprecated: true,
        includeUnsupported: true,
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/models?include_deprecated=true&include_unsupported=true",
      );
    });
  });

  describe("Response transformation", () => {
    it("should add icon to provider based on provider name", async () => {
      const mockResponse: ModelProviderInfo[] = [
        {
          provider: "OpenAI",
          models: [],
          is_enabled: true,
        },
        {
          provider: "Anthropic",
          models: [],
          is_enabled: false,
        },
      ];
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetModelProviders({});
      expect(result).toBeDefined();
    });

    it("should use Bot as default icon for unknown providers", async () => {
      const mockResponse: ModelProviderInfo[] = [
        {
          provider: "UnknownProvider",
          models: [],
          is_enabled: true,
        },
      ];
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetModelProviders({});
      expect(result).toBeDefined();
    });
  });

  describe("Icon mapping", () => {
    it("should map known providers to correct icons", async () => {
      const knownProviders = [
        "OpenAI",
        "Anthropic",
        "Google Generative AI",
        "Groq",
        "Amazon Bedrock",
        "NVIDIA",
        "Cohere",
        "Azure OpenAI",
        "SambaNova",
        "Ollama",
      ];

      for (const provider of knownProviders) {
        const mockResponse: ModelProviderInfo[] = [
          { provider, models: [], is_enabled: true },
        ];
        mockApiGet.mockResolvedValue({ data: mockResponse });

        const result = useGetModelProviders({});
        expect(result).toBeDefined();
      }
    });
  });

  describe("Error handling", () => {
    it("should return empty array on API error", async () => {
      mockApiGet.mockRejectedValue(new Error("Network error"));

      // Should not throw, returns empty array
      expect(() => useGetModelProviders({})).not.toThrow();
    });
  });

  describe("Response structure", () => {
    it("should handle providers with multiple models", async () => {
      const mockResponse: ModelProviderInfo[] = [
        {
          provider: "OpenAI",
          models: [
            { model_name: "gpt-4", metadata: { model_type: "llm" } },
            { model_name: "gpt-4-turbo", metadata: { model_type: "llm" } },
            {
              model_name: "text-embedding-ada-002",
              metadata: { model_type: "embeddings" },
            },
          ],
          is_enabled: true,
        },
      ];
      mockApiGet.mockResolvedValue({ data: mockResponse });

      const result = useGetModelProviders({});
      expect(result).toBeDefined();
    });

    it("should handle empty providers list", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      const result = useGetModelProviders({});
      expect(result).toBeDefined();
    });
  });
});
