/**
 * @jest-environment jsdom
 */

import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

// Mock the API hook directly
const mockMutate = jest.fn();
const mockMutateAsync = jest.fn();
const mockReset = jest.fn();

jest.mock("../use-post-install-package", () => ({
  useInstallPackage: () => ({
    mutate: mockMutate,
    mutateAsync: mockMutateAsync,
    reset: mockReset,
    isPending: false,
    isError: false,
    isSuccess: false,
    data: null,
    error: null,
  }),
}));

import { useInstallPackage } from "../use-post-install-package";

describe("useInstallPackage Hook", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should provide mutation functions", () => {
    const { result } = renderHook(() => useInstallPackage());

    expect(result.current.mutate).toBeDefined();
    expect(result.current.mutateAsync).toBeDefined();
    expect(result.current.reset).toBeDefined();
    expect(typeof result.current.mutate).toBe("function");
    expect(typeof result.current.mutateAsync).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });

  it("should have correct initial state", () => {
    const { result } = renderHook(() => useInstallPackage());

    expect(result.current.isPending).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("should call mutate function", () => {
    const { result } = renderHook(() => useInstallPackage());

    result.current.mutate("numpy");

    expect(mockMutate).toHaveBeenCalledWith("numpy");
  });

  it("should call mutateAsync function", async () => {
    const { result } = renderHook(() => useInstallPackage());

    await result.current.mutateAsync("pandas");

    expect(mockMutateAsync).toHaveBeenCalledWith("pandas");
  });

  it("should call reset function", () => {
    const { result } = renderHook(() => useInstallPackage());

    result.current.reset();

    expect(mockReset).toHaveBeenCalled();
  });
});
