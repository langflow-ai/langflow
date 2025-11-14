import { act, renderHook, waitFor } from "@testing-library/react";
import { ReactNode, useContext } from "react";

// Mock all dependencies
const mockCookiesInstance = {
  get: jest.fn(),
  set: jest.fn(),
  remove: jest.fn(),
};

jest.mock("@/utils/cookie-manager", () => ({
  getCookiesInstance: jest.fn(() => mockCookiesInstance),
  cookieManager: {
    get: jest.fn((name) => mockCookiesInstance.get(name)),
    set: jest.fn((name, value, options) => {
      // Simulate the actual cookieManager behavior of always passing options
      const defaultOptions = {
        path: "/",
        secure: false, // HTTP in test environment
        sameSite: "lax",
        ...options,
      };
      return mockCookiesInstance.set(name, value, defaultOptions);
    }),
    getCookies: jest.fn(() => mockCookiesInstance),
    clearAuthCookies: jest.fn(),
  },
}));

jest.mock("@/utils/utils", () => ({
  getAuthCookie: jest.fn((_cookies, name) => mockCookiesInstance.get(name)),
  setAuthCookie: jest.fn((_cookies, name, value) =>
    mockCookiesInstance.set(name, value),
  ),
}));

jest.mock("@/utils/local-storage-util", () => ({
  setLocalStorage: jest.fn(),
}));

const mockSetIsAuthenticated = jest.fn();
const mockSetIsAdmin = jest.fn();

const mockAuthStore = (selector: any) => {
  const state = {
    setIsAuthenticated: mockSetIsAuthenticated,
    setIsAdmin: mockSetIsAdmin,
  };
  return selector ? selector(state) : state;
};

(mockAuthStore as any).getState = () => ({
  setIsAuthenticated: mockSetIsAuthenticated,
  setIsAdmin: mockSetIsAdmin,
});

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: mockAuthStore,
}));

const mockCheckHasStore = jest.fn();
const mockFetchApiData = jest.fn();

jest.mock("@/stores/storeStore", () => ({
  useStoreStore: (selector: any) => {
    const state = {
      checkHasStore: mockCheckHasStore,
      fetchApiData: mockFetchApiData,
    };
    return selector(state);
  },
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: {
    getState: () => ({ refreshStars: jest.fn() }),
    setState: jest.fn(),
    subscribe: jest.fn(),
    destroy: jest.fn(),
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({})),
}));

jest.mock("@/utils/styleUtils", () => ({}));

// Mock query hooks
const mockMutateLoggedUser = jest.fn();
const mockMutateGetGlobalVariables = jest.fn();

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetUserData: () => ({
    mutate: mockMutateLoggedUser,
  }),
}));

jest.mock(
  "@/controllers/API/queries/variables/use-get-mutation-global-variables",
  () => ({
    useGetGlobalVariablesMutation: () => ({
      mutate: mockMutateGetGlobalVariables,
    }),
  }),
);

// Import AuthProvider after all mocks
import { AuthContext, AuthProvider } from "../authContext";

describe("AuthContext - Login Fix for Race Condition", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockCookiesInstance.get.mockReturnValue(null);
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  const useTestContext = () => useContext(AuthContext);

  describe("Login Race Condition Fix", () => {
    it("should NOT set isAuthenticated until both requests complete successfully", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";
      const refreshToken = "test_refresh_token";
      const mockUserData = {
        id: "user123",
        username: "testuser",
        is_superuser: false,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      // Track when setIsAuthenticated is called
      let authSetCallCount = 0;
      mockSetIsAuthenticated.mockImplementation(() => {
        authSetCallCount++;
      });

      // Start login
      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      // At this point, mutations should have been called
      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(1);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(1);

      // But isAuthenticated should NOT be set yet
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Simulate getUser completing first
      act(() => {
        const getUserCallback = mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // Still should NOT be set (waiting for globalVariables)
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Simulate getGlobalVariables completing
      act(() => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // NOW isAuthenticated should be set
      expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
      expect(mockSetIsAuthenticated).toHaveBeenCalledTimes(1);
    });

    it("should set isAuthenticated when globalVariables completes before getUser", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";
      const mockUserData = {
        id: "user123",
        username: "testuser",
        is_superuser: true,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      // Start login
      act(() => {
        result.current.login(accessToken, "login");
      });

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      // Simulate getGlobalVariables completing FIRST
      act(() => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // Should NOT be set yet (waiting for getUser)
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Simulate getUser completing SECOND
      act(() => {
        const getUserCallback = mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // NOW should be set
      expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
    });

    it("should still set isAuthenticated even if getUser fails", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      // Start login
      act(() => {
        result.current.login(accessToken, "login");
      });

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      // Simulate getUser FAILING
      act(() => {
        const getUserErrorCallback =
          mockMutateLoggedUser.mock.calls[0][1].onError;
        getUserErrorCallback(new Error("User fetch failed"));
      });

      // Simulate getGlobalVariables completing
      act(() => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // Should still set isAuthenticated (fail-safe behavior)
      expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
    });

    it("should handle cookies being set synchronously before API calls", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";
      const refreshToken = "test_refresh_token";

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Verify cookies were set BEFORE mutations started
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(3); // access, auto_login, refresh

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(1);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(1);
    });
  });

  describe("Prevent Premature Redirect", () => {
    it("should complete user data loading before allowing redirect", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "token";
      const mockUserData = {
        id: "user123",
        username: "testuser",
        is_superuser: true,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      // Login
      act(() => {
        result.current.login(accessToken, "login");
      });

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      // Complete getUser - should call checkHasStore and fetchApiData
      act(() => {
        const getUserCallback = mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      expect(mockCheckHasStore).toHaveBeenCalled();
      expect(mockFetchApiData).toHaveBeenCalled();

      // Complete globalVariables
      act(() => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
    });
  });

  describe("Cookie Synchronization", () => {
    it("should set all auth cookies during login", () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "access_token_123";
      const refreshToken = "refresh_token_456";

      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Verify all cookies were set (with options parameter)
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "access_token_lf",
        accessToken,
        expect.any(Object),
      );
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "auto_login_lf",
        "login",
        expect.any(Object),
      );
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "refresh_token_lf",
        refreshToken,
        expect.any(Object),
      );
    });

    it("should not set refresh token cookie if not provided", () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      act(() => {
        result.current.login("access_token_123", "login");
      });

      // Should only set access_token and auto_login cookies
      const setCallArgs = mockCookiesInstance.set.mock.calls.map(
        (call) => call[0],
      );

      expect(setCallArgs).toContain("access_token_lf");
      expect(setCallArgs).toContain("auto_login_lf");
      expect(setCallArgs).not.toContain("refresh_token_lf");
    });
  });

  describe("Integration: Complete Login Flow", () => {
    it("should complete full login flow without race conditions", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "full_flow_token";
      const refreshToken = "full_flow_refresh";
      const mockUserData = {
        id: "user123",
        username: "fulltest",
        is_superuser: false,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      // Mock cookie getter to return the access token
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return accessToken;
        return null;
      });

      // Step 1: Start login
      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Verify cookies set
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(3);

      // Verify isAuthenticated NOT set yet
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Advance timers to trigger the verifyAndProceed function
      act(() => {
        jest.advanceTimersByTime(50);
      });

      // Verify mutations triggered
      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(1);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(1);

      // Step 2: Complete getUser
      act(() => {
        const getUserCallback = mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // Verify user data processed
      expect(mockCheckHasStore).toHaveBeenCalled();
      expect(mockFetchApiData).toHaveBeenCalled();

      // Verify isAuthenticated STILL not set
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Step 3: Complete getGlobalVariables
      act(() => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // Step 4: NOW isAuthenticated should be set
      expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
      expect(mockSetIsAuthenticated).toHaveBeenCalledTimes(1);
    });
  });

  describe("Edge Cases", () => {
    it("should handle rapid multiple login calls", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      // Mock cookie getter to return tokens
      mockCookiesInstance.get.mockImplementation((name) => {
        if (name === "access_token_lf") return "token3"; // Last token set
        return null;
      });

      // Rapidly call login multiple times
      act(() => {
        result.current.login("token1", "login");
        result.current.login("token2", "login");
        result.current.login("token3", "login");
      });

      // Advance timers to trigger the verifyAndProceed function for all logins
      act(() => {
        jest.advanceTimersByTime(150); // 50ms x 3 logins
      });

      // Should trigger mutations for each login
      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(3);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(3);
    });

    it("should handle login with auto-login option", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      act(() => {
        result.current.login("auto_token", "auto");
      });

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "auto_login_lf",
        "auto",
        expect.any(Object),
      );
    });
  });
});
