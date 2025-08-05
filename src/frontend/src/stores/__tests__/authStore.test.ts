import { act, renderHook } from "@testing-library/react";

// Mock the darkStore to avoid import.meta issues
jest.mock("../darkStore", () => ({
  useDarkStore: {
    getState: () => ({ refreshStars: jest.fn() }),
    setState: jest.fn(),
    subscribe: jest.fn(),
    destroy: jest.fn(),
  },
}));

// Mock all complex dependencies to avoid import issues
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({})),
}));

jest.mock("@/utils/styleUtils", () => ({}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender",
  () => () => null,
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent/components/tableDropdownCellEditor",
  () => () => null,
);

// Jest can't find this module to mock it, let's skip this mock

// Jest can't find this module either

import useAuthStore from "../authStore";

// We can't easily mock the cookie hook at initialization time, so we'll test actual behavior
describe("useAuthStore", () => {
  describe("state management", () => {
    it("should update isAdmin state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setIsAdmin(true);
      });

      expect(result.current.isAdmin).toBe(true);

      act(() => {
        result.current.setIsAdmin(false);
      });

      expect(result.current.isAdmin).toBe(false);
    });

    it("should update isAuthenticated state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setIsAuthenticated(true);
      });

      expect(result.current.isAuthenticated).toBe(true);

      act(() => {
        result.current.setIsAuthenticated(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
    });

    it("should update accessToken state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setAccessToken("new-access-token");
      });

      expect(result.current.accessToken).toBe("new-access-token");

      act(() => {
        result.current.setAccessToken(null);
      });

      expect(result.current.accessToken).toBeNull();
    });

    it("should update userData state", () => {
      const { result } = renderHook(() => useAuthStore());
      const mockUserData = {
        id: "123",
        username: "testuser",
        is_superuser: false,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      act(() => {
        result.current.setUserData(mockUserData);
      });

      expect(result.current.userData).toEqual(mockUserData);

      act(() => {
        result.current.setUserData(null);
      });

      expect(result.current.userData).toBeNull();
    });

    it("should update autoLogin state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setAutoLogin(true);
      });

      expect(result.current.autoLogin).toBe(true);

      act(() => {
        result.current.setAutoLogin(false);
      });

      expect(result.current.autoLogin).toBe(false);
    });

    it("should update apiKey state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setApiKey("new-api-key");
      });

      expect(result.current.apiKey).toBe("new-api-key");

      act(() => {
        result.current.setApiKey(null);
      });

      expect(result.current.apiKey).toBeNull();
    });

    it("should update authenticationErrorCount state", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setAuthenticationErrorCount(5);
      });

      expect(result.current.authenticationErrorCount).toBe(5);

      act(() => {
        result.current.setAuthenticationErrorCount(0);
      });

      expect(result.current.authenticationErrorCount).toBe(0);
    });
  });

  describe("logout function", () => {
    it("should reset auth-related state on logout", async () => {
      const { result } = renderHook(() => useAuthStore());

      // Set up some state first
      act(() => {
        result.current.setIsAuthenticated(true);
        result.current.setIsAdmin(true);
        result.current.setAccessToken("access-token");
        result.current.setApiKey("api-key");
        result.current.setUserData({
          id: "123",
          username: "test",
          is_superuser: true,
          is_active: true,
          profile_image: "",
          create_at: new Date(),
          updated_at: new Date(),
        });
        result.current.setAutoLogin(true);
      });

      // Verify state is set
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isAdmin).toBe(true);
      expect(result.current.accessToken).toBe("access-token");
      expect(result.current.apiKey).toBe("api-key");
      expect(result.current.userData).toBeTruthy();
      expect(result.current.autoLogin).toBe(true);

      // Perform logout
      await act(async () => {
        await result.current.logout();
      });

      // Verify state is reset
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);
      expect(result.current.accessToken).toBeNull();
      expect(result.current.apiKey).toBeNull();
      expect(result.current.userData).toBeNull();
      expect(result.current.autoLogin).toBe(false);
    });
  });
});
