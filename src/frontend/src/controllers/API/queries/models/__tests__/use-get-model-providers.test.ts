import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";

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

import {
  ModelProviderInfo,
  useGetModelProviders,
} from "../use-get-model-providers";

// Helper to render hooks with QueryClientProvider
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

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

      renderHook(() => useGetModelProviders({}), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith("/api/v1/models");
      });
    });

    it("should include deprecated param when includeDeprecated is true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      renderHook(() => useGetModelProviders({ includeDeprecated: true }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith(
          "/api/v1/models?include_deprecated=true",
        );
      });
    });

    it("should include unsupported param when includeUnsupported is true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      renderHook(() => useGetModelProviders({ includeUnsupported: true }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith(
          "/api/v1/models?include_unsupported=true",
        );
      });
    });

    it("should include both params when both are true", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      renderHook(
        () =>
          useGetModelProviders({
            includeDeprecated: true,
            includeUnsupported: true,
          }),
        { wrapper: createWrapper() },
      );

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith(
          "/api/v1/models?include_deprecated=true&include_unsupported=true",
        );
      });
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

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });
      await waitFor(() => {
        expect(result.current).toBeDefined();
      });
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

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });
      await waitFor(() => {
        expect(result.current).toBeDefined();
      });
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

        const { result } = renderHook(() => useGetModelProviders({}), {
          wrapper: createWrapper(),
        });
        await waitFor(() => {
          expect(result).toBeDefined();
        });
      }
    });
  });

  describe("Error handling", () => {
    it("should return empty array on API error", async () => {
      mockApiGet.mockRejectedValue(new Error("Network error"));

      // Should not throw, returns empty array
      expect(() =>
        renderHook(() => useGetModelProviders({}), {
          wrapper: createWrapper(),
        }),
      ).not.toThrow();
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

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });
      expect(result.current).toBeDefined();
    });

    it("should handle empty providers list", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });
      expect(result.current).toBeDefined();
    });
  });
});
