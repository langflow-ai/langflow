import { act, renderHook } from "@testing-library/react";

// Mock react-cookie
const mockCookies = {
  get: jest.fn(),
  set: jest.fn(),
  remove: jest.fn(),
};

jest.mock("react-cookie", () => ({
  Cookies: jest.fn().mockImplementation(() => mockCookies),
}));

// Mock constants
jest.mock("@/constants/constants", () => ({
  LANGFLOW_ACCESS_TOKEN: "langflow_access_token",
  LANGFLOW_API_TOKEN: "langflow_api_token",
}));

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

import useAuthStore from "../authStore";

describe("useAuthStore", () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();

    // Set default cookie values
    mockCookies.get.mockImplementation((key) => {
      switch (key) {
        case "langflow_access_token":
          return null;
        case "langflow_api_token":
          return null;
        default:
          return null;
      }
    });

    // Reset the store state
    useAuthStore.setState({
      isAdmin: false,
      isAuthenticated: false,
      accessToken: null,
      userData: null,
      autoLogin: null,
      apiKey: null,
      authenticationErrorCount: 0,
    });
  });

  describe("initial state", () => {
    it("should initialize with correct default state when no cookies are present", () => {
      const { result } = renderHook(() => useAuthStore());

      expect(result.current.isAdmin).toBe(false);
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.accessToken).toBeNull();
      expect(result.current.userData).toBeNull();
      expect(result.current.autoLogin).toBeNull();
      expect(result.current.apiKey).toBeNull();
      expect(result.current.authenticationErrorCount).toBe(0);
    });

    it("should simulate authenticated state from cookies", () => {
      const { result } = renderHook(() => useAuthStore());

      // Manually set authenticated state to simulate cookie behavior
      act(() => {
        result.current.setIsAuthenticated(true);
        result.current.setAccessToken("test-access-token");
        result.current.setApiKey("test-api-key");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.accessToken).toBe("test-access-token");
      expect(result.current.apiKey).toBe("test-api-key");
    });

    it("should handle null/undefined cookie values", () => {
      const { result } = renderHook(() => useAuthStore());

      // Verify that when cookies are null/undefined, we get proper null values
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.accessToken).toBeNull();
      expect(result.current.apiKey).toBeNull();
    });
  });

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

  describe("edge cases and error scenarios", () => {
    it("should handle null values gracefully", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setAccessToken(null);
        result.current.setUserData(null);
        result.current.setApiKey(null);
      });

      expect(result.current.accessToken).toBeNull();
      expect(result.current.userData).toBeNull();
      expect(result.current.apiKey).toBeNull();
    });

    it("should handle boolean edge cases for autoLogin", () => {
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

    it("should handle authenticationErrorCount edge cases", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setAuthenticationErrorCount(-1);
      });
      expect(result.current.authenticationErrorCount).toBe(-1);

      act(() => {
        result.current.setAuthenticationErrorCount(0);
      });
      expect(result.current.authenticationErrorCount).toBe(0);

      act(() => {
        result.current.setAuthenticationErrorCount(999);
      });
      expect(result.current.authenticationErrorCount).toBe(999);
    });

    it("should handle multiple logout calls", async () => {
      const { result } = renderHook(() => useAuthStore());

      // Set up authenticated state
      act(() => {
        result.current.setIsAuthenticated(true);
        result.current.setIsAdmin(true);
        result.current.setAccessToken("token");
      });

      // First logout
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);

      // Second logout should not throw
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);
    });

    it("should handle complex user data object", () => {
      const { result } = renderHook(() => useAuthStore());
      const complexUserData = {
        id: "user-123",
        username: "testuser",
        is_superuser: true,
        is_active: false,
        profile_image: "https://example.com/avatar.jpg",
        create_at: new Date("2023-01-01"),
        updated_at: new Date("2023-12-31"),
      };

      act(() => {
        result.current.setUserData(complexUserData);
      });

      expect(result.current.userData).toEqual(complexUserData);
      expect(result.current.userData?.is_superuser).toBe(true);
      expect(result.current.userData?.is_active).toBe(false);
    });

    it("should maintain state consistency during rapid updates", () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        // Rapidly update multiple values
        result.current.setIsAuthenticated(true);
        result.current.setIsAdmin(true);
        result.current.setAccessToken("token1");
        result.current.setAccessToken("token2");
        result.current.setAuthenticationErrorCount(5);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isAdmin).toBe(true);
      expect(result.current.accessToken).toBe("token2"); // Should use last value
      expect(result.current.authenticationErrorCount).toBe(5);
    });

    it("should preserve state after partial logout operations", async () => {
      const { result } = renderHook(() => useAuthStore());

      // Set up initial state
      act(() => {
        result.current.setAuthenticationErrorCount(3);
      });

      const initialErrorCount = result.current.authenticationErrorCount;

      // Perform logout
      await act(async () => {
        await result.current.logout();
      });

      // Verify that authenticationErrorCount is not modified by logout
      expect(result.current.authenticationErrorCount).toBe(initialErrorCount);
    });
  });

  describe("store integration scenarios", () => {
    it("should handle authentication flow simulation", async () => {
      const { result } = renderHook(() => useAuthStore());

      // Start as unauthenticated
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);

      // Simulate login
      act(() => {
        result.current.setIsAuthenticated(true);
        result.current.setAccessToken("login-token");
        result.current.setUserData({
          id: "123",
          username: "loginuser",
          is_superuser: true,
          is_active: true,
          profile_image: "",
          create_at: new Date(),
          updated_at: new Date(),
        });
        result.current.setIsAdmin(true);
        result.current.setApiKey("api-key-123");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isAdmin).toBe(true);
      expect(result.current.accessToken).toBe("login-token");
      expect(result.current.apiKey).toBe("api-key-123");
      expect(result.current.userData).toBeTruthy();

      // Simulate logout
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);
      expect(result.current.accessToken).toBeNull();
      expect(result.current.apiKey).toBeNull();
      expect(result.current.userData).toBeNull();
    });

    it("should handle session timeout simulation", () => {
      const { result } = renderHook(() => useAuthStore());

      // Simulate authenticated user with error count building up
      act(() => {
        result.current.setIsAuthenticated(true);
        result.current.setAccessToken("session-token");
        result.current.setAuthenticationErrorCount(0);
      });

      // Simulate authentication errors incrementing
      act(() => {
        result.current.setAuthenticationErrorCount(1);
      });
      expect(result.current.authenticationErrorCount).toBe(1);

      act(() => {
        result.current.setAuthenticationErrorCount(2);
      });
      expect(result.current.authenticationErrorCount).toBe(2);

      act(() => {
        result.current.setAuthenticationErrorCount(3);
      });
      expect(result.current.authenticationErrorCount).toBe(3);

      // User should still be authenticated until explicit logout
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.accessToken).toBe("session-token");
    });
  });
});
