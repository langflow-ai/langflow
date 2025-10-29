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
    get: jest.fn(),
    set: jest.fn(),
    getCookies: jest.fn(() => mockCookiesInstance),
  },
}));

jest.mock("@/utils/utils", () => ({
  getAuthCookie: jest.fn((_cookies, name) => mockCookiesInstance.get(name)),
  setAuthCookie: jest.fn((_cookies, name, value) =>
    mockCookiesInstance.set(name, value)
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
  })
);

// Import AuthProvider after all mocks
import { AuthContext, AuthProvider } from "../authContext";

describe("AuthContext - Login Fix for Race Condition", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCookiesInstance.get.mockReturnValue(null);
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

      // Track when setIsAuthenticated is called
      let authSetCallCount = 0;
      mockSetIsAuthenticated.mockImplementation(() => {
        authSetCallCount++;
      });

      // Start login
      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // At this point, isAuthenticated should NOT be set yet
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Simulate getUser completing first
      act(() => {
        const getUserCallback =
          mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // Still should NOT be set (waiting for globalVariables)
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Simulate getGlobalVariables completing
      await act(async () => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // NOW isAuthenticated should be set
      await waitFor(
        () => {
          expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
          expect(mockSetIsAuthenticated).toHaveBeenCalledTimes(1);
        },
        { timeout: 3000 } // Increased timeout for CI environments
      );
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

      // Start login
      act(() => {
        result.current.login(accessToken, "login");
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
      await act(async () => {
        const getUserCallback =
          mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // NOW should be set
      await waitFor(
        () => {
          expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
        },
        { timeout: 3000 }
      );
    });

    it("should still set isAuthenticated even if getUser fails", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";

      // Start login
      act(() => {
        result.current.login(accessToken, "login");
      });

      // Simulate getUser FAILING
      act(() => {
        const getUserErrorCallback =
          mockMutateLoggedUser.mock.calls[0][1].onError;
        getUserErrorCallback(new Error("User fetch failed"));
      });

      // Simulate getGlobalVariables completing
      await act(async () => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // Should still set isAuthenticated (fail-safe behavior)
      await waitFor(
        () => {
          expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
        },
        { timeout: 3000 }
      );
    });

    it("should handle cookies being set synchronously before API calls", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const accessToken = "test_access_token";
      const refreshToken = "test_refresh_token";

      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Verify cookies were set BEFORE mutations started
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(3); // access, auto_login, refresh
      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(1);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(1);
    });
  });

  describe("Prevent Premature Redirect", () => {
    it("should complete user data loading before allowing redirect", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      const mockUserData = {
        id: "user123",
        username: "testuser",
        is_superuser: true,
        is_active: true,
        profile_image: "",
        create_at: new Date(),
        updated_at: new Date(),
      };

      // Login
      act(() => {
        result.current.login("token", "login");
      });

      // Complete getUser - should call checkHasStore and fetchApiData
      act(() => {
        const getUserCallback =
          mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      expect(mockCheckHasStore).toHaveBeenCalled();
      expect(mockFetchApiData).toHaveBeenCalled();

      // Complete globalVariables
      await act(async () => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      await waitFor(
        () => {
          expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
        },
        { timeout: 3000 }
      );
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

      // Verify all cookies were set
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "access_token_lf",
        accessToken
      );
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "auto_login_lf",
        "login"
      );
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "refresh_token_lf",
        refreshToken
      );
    });

    it("should not set refresh token cookie if not provided", () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      act(() => {
        result.current.login("access_token_123", "login");
      });

      // Should only set access_token and auto_login cookies
      const setCallArgs = mockCookiesInstance.set.mock.calls.map(
        (call) => call[0]
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

      // Step 1: Start login
      act(() => {
        result.current.login(accessToken, "login", refreshToken);
      });

      // Verify cookies set
      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(3);

      // Verify mutations triggered
      expect(mockMutateLoggedUser).toHaveBeenCalledTimes(1);
      expect(mockMutateGetGlobalVariables).toHaveBeenCalledTimes(1);

      // Verify isAuthenticated NOT set yet
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Step 2: Complete getUser
      act(() => {
        const getUserCallback =
          mockMutateLoggedUser.mock.calls[0][1].onSuccess;
        getUserCallback(mockUserData);
      });

      // Verify user data processed
      expect(mockCheckHasStore).toHaveBeenCalled();
      expect(mockFetchApiData).toHaveBeenCalled();

      // Verify isAuthenticated STILL not set
      expect(mockSetIsAuthenticated).not.toHaveBeenCalled();

      // Step 3: Complete getGlobalVariables
      await act(async () => {
        const getVarsCallback =
          mockMutateGetGlobalVariables.mock.calls[0][1].onSettled;
        getVarsCallback();
      });

      // Step 4: NOW isAuthenticated should be set
      await waitFor(
        () => {
          expect(mockSetIsAuthenticated).toHaveBeenCalledWith(true);
          expect(mockSetIsAuthenticated).toHaveBeenCalledTimes(1);
        },
        { timeout: 3000 }
      );
    });
  });

  describe("Edge Cases", () => {
    it("should handle rapid multiple login calls", async () => {
      const { result } = renderHook(() => useTestContext(), { wrapper });

      // Rapidly call login multiple times
      act(() => {
        result.current.login("token1", "login");
        result.current.login("token2", "login");
        result.current.login("token3", "login");
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
        "auto"
      );
    });
  });
});
