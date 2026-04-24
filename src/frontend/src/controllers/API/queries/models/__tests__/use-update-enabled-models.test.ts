// Mock API before imports
const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: mockApiPost,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((_key, fn, _options) => ({
      mutate: async (data: any) => {
        return await fn(data);
      },
      mutateAsync: async (data: any) => {
        return await fn(data);
      },
    })),
  })),
}));

import {
  ModelStatusUpdate,
  UpdateEnabledModelsResponse,
  useUpdateEnabledModels,
} from "../use-update-enabled-models";

describe("useUpdateEnabledModels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("API calls", () => {
    it("should call the correct API endpoint with updates", async () => {
      const mockResponse: UpdateEnabledModelsResponse = {
        disabled_models: [],
      };
      mockApiPost.mockResolvedValue({ data: mockResponse });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
      ];

      const mutation = useUpdateEnabledModels();
      await mutation.mutateAsync({ updates });

      expect(mockApiPost).toHaveBeenCalledWith(
        "/api/v1/models/enabled_models",
        updates,
      );
    });

    it("should handle multiple model updates", async () => {
      const mockResponse: UpdateEnabledModelsResponse = {
        disabled_models: ["gpt-3.5-turbo"],
      };
      mockApiPost.mockResolvedValue({ data: mockResponse });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
        { provider: "OpenAI", model_id: "gpt-3.5-turbo", enabled: false },
        { provider: "Anthropic", model_id: "claude-3", enabled: true },
      ];

      const mutation = useUpdateEnabledModels();
      await mutation.mutateAsync({ updates });

      expect(mockApiPost).toHaveBeenCalledWith(
        "/api/v1/models/enabled_models",
        updates,
      );
    });
  });

  describe("Response handling", () => {
    it("should return disabled_models in response", async () => {
      const mockResponse: UpdateEnabledModelsResponse = {
        disabled_models: ["gpt-3.5-turbo", "gpt-4-mini"],
      };
      mockApiPost.mockResolvedValue({ data: mockResponse });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-3.5-turbo", enabled: false },
        { provider: "OpenAI", model_id: "gpt-4-mini", enabled: false },
      ];

      const mutation = useUpdateEnabledModels();
      const result = await mutation.mutateAsync({ updates });

      expect(result).toEqual(mockResponse);
    });

    it("should handle empty disabled_models", async () => {
      const mockResponse: UpdateEnabledModelsResponse = {
        disabled_models: [],
      };
      mockApiPost.mockResolvedValue({ data: mockResponse });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
      ];

      const mutation = useUpdateEnabledModels();
      const result = await mutation.mutateAsync({ updates });

      expect(result.disabled_models).toHaveLength(0);
    });
  });

  describe("Error handling", () => {
    it("should throw on API error", async () => {
      const mockError = new Error("Network error");
      mockApiPost.mockRejectedValue(mockError);

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
      ];

      const mutation = useUpdateEnabledModels();

      await expect(mutation.mutateAsync({ updates })).rejects.toThrow(
        "Network error",
      );
    });
  });

  describe("Update structure", () => {
    it("should correctly structure enable update", async () => {
      mockApiPost.mockResolvedValue({ data: { disabled_models: [] } });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
      ];

      const mutation = useUpdateEnabledModels();
      await mutation.mutateAsync({ updates });

      const calledWith = mockApiPost.mock.calls[0][1];
      expect(calledWith[0]).toEqual({
        provider: "OpenAI",
        model_id: "gpt-4",
        enabled: true,
      });
    });

    it("should correctly structure disable update", async () => {
      mockApiPost.mockResolvedValue({
        data: { disabled_models: ["gpt-4"] },
      });

      const updates: ModelStatusUpdate[] = [
        { provider: "OpenAI", model_id: "gpt-4", enabled: false },
      ];

      const mutation = useUpdateEnabledModels();
      await mutation.mutateAsync({ updates });

      const calledWith = mockApiPost.mock.calls[0][1];
      expect(calledWith[0].enabled).toBe(false);
    });
  });
});
