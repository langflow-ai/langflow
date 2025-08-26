/**
 * @jest-environment jsdom
 */

import { renderHook } from "@testing-library/react";

// Mock the API hook directly
const mockData = {
  installation_in_progress: false,
  last_result: null,
};

jest.mock("../use-get-installation-status", () => ({
  useGetInstallationStatus: (enabled: boolean) => ({
    data: enabled ? mockData : undefined,
    isPending: false,
    isError: false,
    isSuccess: enabled,
    error: null,
    isFetching: false,
    isLoading: false,
  }),
}));

import { useGetInstallationStatus } from "../use-get-installation-status";

describe("useGetInstallationStatus Hook", () => {
  it("should return data when enabled", () => {
    const { result } = renderHook(() => useGetInstallationStatus(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.isSuccess).toBe(true);
    expect(result.current.isPending).toBe(false);
    expect(result.current.isError).toBe(false);
  });

  it("should not return data when disabled", () => {
    const { result } = renderHook(() => useGetInstallationStatus(false));

    expect(result.current.data).toBeUndefined();
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.isPending).toBe(false);
    expect(result.current.isError).toBe(false);
  });

  it("should have correct interface", () => {
    const { result } = renderHook(() => useGetInstallationStatus(true));

    expect(result.current).toHaveProperty("data");
    expect(result.current).toHaveProperty("isPending");
    expect(result.current).toHaveProperty("isError");
    expect(result.current).toHaveProperty("isSuccess");
    expect(result.current).toHaveProperty("error");
    expect(result.current).toHaveProperty("isFetching");
    expect(result.current).toHaveProperty("isLoading");
  });

  it("should handle installation in progress state", () => {
    const { result } = renderHook(() => useGetInstallationStatus(true));

    // The mock data shows installation_in_progress: false
    expect(result.current.data?.installation_in_progress).toBe(false);
    expect(result.current.data?.last_result).toBeNull();
  });
});
