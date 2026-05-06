import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";

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
  LocalModelStatus,
  useGetLocalModelStatus,
} from "../use-get-local-model-status";

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

describe("useGetLocalModelStatus", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should call /api/v1/local_model/status", async () => {
    const status: LocalModelStatus = {
      is_docker: false,
      is_ollama_installed: true,
      is_ollama_running: true,
      is_model_pulled: true,
      default_model: "qwen2.5:1.5b",
      ready: true,
    };
    mockApiGet.mockResolvedValue({ data: status });

    renderHook(() => useGetLocalModelStatus(undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith("/api/v1/local_model/status");
    });
  });

  it("should expose status payload to consumers", async () => {
    const status: LocalModelStatus = {
      is_docker: false,
      is_ollama_installed: false,
      is_ollama_running: false,
      is_model_pulled: false,
      default_model: "qwen2.5:1.5b",
      ready: false,
    };
    mockApiGet.mockResolvedValue({ data: status });

    const { result } = renderHook(() => useGetLocalModelStatus(undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(status);
    });
  });
});
