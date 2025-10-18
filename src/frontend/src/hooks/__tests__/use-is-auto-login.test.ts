import { renderHook } from "@testing-library/react";
import useAuthStore from "@/stores/authStore";
import { useIsAutoLogin } from "../use-is-auto-login";

// Mock the auth store
jest.mock("@/stores/authStore");

// Mock the constants
jest.mock("@/constants/constants", () => ({
  IS_AUTO_LOGIN: false,
}));

describe("useIsAutoLogin", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should return autoLogin from store when it is true", () => {
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ autoLogin: true }),
    );

    const { result } = renderHook(() => useIsAutoLogin());

    expect(result.current).toBe(true);
  });

  it("should return autoLogin from store when it is false", () => {
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ autoLogin: false }),
    );

    const { result } = renderHook(() => useIsAutoLogin());

    expect(result.current).toBe(false);
  });

  it("should return IS_AUTO_LOGIN env when autoLogin is null", () => {
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ autoLogin: null }),
    );

    const { result } = renderHook(() => useIsAutoLogin());

    // IS_AUTO_LOGIN is mocked as false
    expect(result.current).toBe(false);
  });

  it("should return IS_AUTO_LOGIN env when autoLogin is undefined", () => {
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ autoLogin: undefined }),
    );

    const { result } = renderHook(() => useIsAutoLogin());

    // IS_AUTO_LOGIN is mocked as false
    expect(result.current).toBe(false);
  });

  it("should prioritize store value over env when store value is defined", () => {
    // Even if IS_AUTO_LOGIN is false, if store has true, it should return true
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ autoLogin: true }),
    );

    const { result } = renderHook(() => useIsAutoLogin());

    expect(result.current).toBe(true);
  });
});
