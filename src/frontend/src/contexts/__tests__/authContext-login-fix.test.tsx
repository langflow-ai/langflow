import { act, renderHook } from "@testing-library/react";
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

type MockAuthState = {
  setIsAuthenticated: typeof mockSetIsAuthenticated;
  setIsAdmin: typeof mockSetIsAdmin;
};

const getMockAuthState = (): MockAuthState => ({
  setIsAuthenticated: mockSetIsAuthenticated,
  setIsAdmin: mockSetIsAdmin,
});

const mockAuthStore = Object.assign(
  <T,>(selector: (state: MockAuthState) => T): T => {
    const state = {
      setIsAuthenticated: mockSetIsAuthenticated,
      setIsAdmin: mockSetIsAdmin,
    };
    return selector(state);
  },
  { getState: getMockAuthState },
);

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: mockAuthStore,
}));

const mockCheckHasStore = jest.fn();
const mockFetchApiData = jest.fn();

type MockStoreState = {
  checkHasStore: typeof mockCheckHasStore;
  fetchApiData: typeof mockFetchApiData;
};

jest.mock("@/stores/storeStore", () => ({
  useStoreStore: <T,>(selector: (state: MockStoreState) => T): T => {
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

      // Only the non-sensitive UI preference is written by JavaScript. The
      // server owns both token cookies so they retain HttpOnly.
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(1);
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "auto_login_lf",
        "login",
        expect.any(Object),
      );

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
    it("should leave token cookies server-owned during login", () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "access_token_123";
      const refreshToken = "refresh_token_456";

      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "auto_login_lf",
        "login",
        expect.any(Object),
      );
      const setCallArgs = mockCookiesInstance.set.mock.calls.map(
        (call) => call[0],
      );
      expect(setCallArgs).not.toContain("access_token_lf");
      expect(setCallArgs).not.toContain("refresh_token_lf");
    });

    it("should leave token cookies server-owned when refresh token is omitted", () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      act(() => {
        result.current.login("access_token_123", "login");
      });

      const setCallArgs = mockCookiesInstance.set.mock.calls.map(
        (call) => call[0],
      );

      expect(setCallArgs).not.toContain("access_token_lf");
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

      // Only the auto-login UI preference is written by JavaScript.
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(1);

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
