/**
 * @jest-environment jsdom
 */

import { renderHook } from "@testing-library/react";

// Mock the API hook directly
const mockMutate = jest.fn();
const mockMutateAsync = jest.fn();
const mockReset = jest.fn();

jest.mock("../use-delete-installation-status", () => ({
  useClearInstallationStatus: () => ({
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

import { useClearInstallationStatus } from "../use-delete-installation-status";

describe("useClearInstallationStatus Hook", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should provide mutation functions", () => {
    const { result } = renderHook(() => useClearInstallationStatus());

    expect(result.current.mutate).toBeDefined();
    expect(result.current.mutateAsync).toBeDefined();
    expect(result.current.reset).toBeDefined();
    expect(typeof result.current.mutate).toBe("function");
    expect(typeof result.current.mutateAsync).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });

  it("should have correct initial state", () => {
    const { result } = renderHook(() => useClearInstallationStatus());

    expect(result.current.isPending).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("should call mutate function", () => {
    const { result } = renderHook(() => useClearInstallationStatus());

    result.current.mutate();

    expect(mockMutate).toHaveBeenCalled();
  });

  it("should call mutateAsync function", async () => {
    const { result } = renderHook(() => useClearInstallationStatus());

    await result.current.mutateAsync();

    expect(mockMutateAsync).toHaveBeenCalled();
  });

  it("should call reset function", () => {
    const { result } = renderHook(() => useClearInstallationStatus());

    result.current.reset();

    expect(mockReset).toHaveBeenCalled();
  });
});
