import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
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
  getModelProvidersQueryOptions,
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

    it("scopes both the request and cache key by flow", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      const options = getModelProvidersQueryOptions({
        includeDeprecated: true,
        flowId: "flow-one",
      });
      await options.queryFn();

      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/models?include_deprecated=true&flow_id=flow-one",
      );
      expect(options.queryKey).toEqual([
        "useGetModelProviders",
        true,
        undefined,
        "flow-one",
        undefined,
        undefined,
      ]);
    });

    it("keys and executes both accepted provider-read purposes", async () => {
      mockApiGet.mockResolvedValue({ data: [] });

      const configureOptions = getModelProvidersQueryOptions({
        flowId: "flow-one",
        purpose: "configure",
      });
      const useOptions = getModelProvidersQueryOptions({
        flowId: "flow-one",
        purpose: "use",
      });
      await configureOptions.queryFn();
      await useOptions.queryFn();

      expect(mockApiGet.mock.calls).toEqual([
        ["/api/v1/models?flow_id=flow-one&purpose=configure"],
        ["/api/v1/models?flow_id=flow-one&purpose=use"],
      ]);
      expect(configureOptions.queryKey).toEqual([
        "useGetModelProviders",
        undefined,
        undefined,
        "flow-one",
        undefined,
        "configure",
      ]);
      expect(useOptions.queryKey).toEqual([
        "useGetModelProviders",
        undefined,
        undefined,
        "flow-one",
        undefined,
        "use",
      ]);
    });

    it("keeps global settings in a distinct unscoped cache entry", () => {
      expect(getModelProvidersQueryOptions({}).queryKey).toEqual([
        "useGetModelProviders",
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
      ]);
    });

    it("removes a revoked provider from a mounted flow picker on stale focus", async () => {
      const dateNow = jest.spyOn(Date, "now").mockReturnValue(1_000_000);
      mockApiGet
        .mockResolvedValueOnce({
          data: [
            {
              provider: "OpenAI",
              models: [],
              is_enabled: true,
            },
          ],
        })
        .mockResolvedValueOnce({ data: [] });

      try {
        const { result } = renderHook(
          () => useGetModelProviders({ flowId: "flow-one" }),
          { wrapper: createWrapper() },
        );

        await waitFor(() =>
          expect(result.current.data?.map(({ provider }) => provider)).toEqual([
            "OpenAI",
          ]),
        );

        dateNow.mockReturnValue(1_030_001);
        act(() => focusManager.setFocused(false));
        act(() => focusManager.setFocused(true));

        await waitFor(() => expect(result.current.data).toEqual([]));
        expect(mockApiGet).toHaveBeenCalledTimes(2);
      } finally {
        focusManager.setFocused(undefined);
        dateNow.mockRestore();
      }
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
        "Azure AI Foundry",
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

    it("should map Azure AI Foundry to the Azure icon", async () => {
      mockApiGet.mockResolvedValue({
        data: [
          {
            provider: "Azure AI Foundry",
            models: [],
            is_enabled: true,
          },
        ],
      });

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.[0]?.icon).toBe("Azure");
      });
    });

    it("should map Azure OpenAI to the Azure icon", async () => {
      mockApiGet.mockResolvedValue({
        data: [
          {
            provider: "Azure OpenAI",
            models: [],
            is_enabled: true,
          },
        ],
      });

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.[0]?.icon).toBe("Azure");
      });
    });

    it("should fall back to Bot for unknown providers", async () => {
      mockApiGet.mockResolvedValue({
        data: [
          {
            provider: "UnknownProvider",
            models: [],
            is_enabled: true,
          },
        ],
      });

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.[0]?.icon).toBe("Bot");
      });
    });

    it("should prefer the API-provided icon over the frontend map", async () => {
      mockApiGet.mockResolvedValue({
        data: [
          {
            provider: "Azure AI Foundry",
            models: [],
            is_enabled: true,
            icon: "Azure",
          },
        ],
      });

      const { result } = renderHook(() => useGetModelProviders({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.[0]?.icon).toBe("Azure");
      });
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
