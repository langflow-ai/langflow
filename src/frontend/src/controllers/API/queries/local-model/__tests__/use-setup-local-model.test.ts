import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";

const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: mockApiPost,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

import { useSetupLocalModel } from "../use-setup-local-model";

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

describe("useSetupLocalModel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should POST consent body to /api/v1/local_model/setup", async () => {
    mockApiPost.mockResolvedValue({ data: { accepted: true } });

    const { result } = renderHook(() => useSetupLocalModel(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({ consent: true });
    });

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith("/api/v1/local_model/setup", {
        consent: true,
      });
    });
  });

  it("should propagate the accepted flag", async () => {
    mockApiPost.mockResolvedValue({ data: { accepted: true } });

    const { result } = renderHook(() => useSetupLocalModel(), {
      wrapper: createWrapper(),
    });

    let response;
    await act(async () => {
      response = await result.current.mutateAsync({ consent: true });
    });

    expect(response).toEqual({ accepted: true });
  });
});
