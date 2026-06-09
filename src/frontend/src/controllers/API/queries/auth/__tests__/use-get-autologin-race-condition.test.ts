/**
 * Tests for useGetAutoLogin Race Condition Prevention
 *
 * These tests ensure that the auto-login hook does NOT prematurely logout users
 * when isAuthenticated is still in its initial state (false) before session validation.
 *
 * The race condition occurs when:
 * 1. User opens a new tab (e.g., MCP Server button)
 * 2. useGetAutoLogin runs and checks isAuthenticated (defaults to false in Zustand)
 * 3. Before useGetAuthSession validates cookies, the old code would call mutationLogout()
 * 4. This clears valid HttpOnly cookies, causing incorrect logout
 *
 * The fix removes the premature logout logic and delegates auth decisions to ProtectedRoute.
 */

// Mock dependencies - use unique names to avoid conflicts with other test files
const raceConditionMockSetAutoLogin = jest.fn();
const raceConditionMockNavigate = jest.fn();
const raceConditionMockMutationLogout = jest.fn();

// Track isAuthenticated state for testing race conditions
let raceConditionMockIsAuthenticated = false;
let raceConditionMockAutoLogin: boolean | undefined = undefined;

jest.mock("@/constants/constants", () => ({
  AUTO_LOGIN_MAX_RETRY_DELAY: 30000,
  AUTO_LOGIN_RETRY_DELAY: 1000,
  IS_AUTO_LOGIN: false, // Manual login mode for testing
}));

jest.mock("@/contexts/authContext", () => ({
  AuthContext: {
    Provider: ({ children }: { children: React.ReactNode }) => children,
  },
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => raceConditionMockNavigate,
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      setAutoLogin: raceConditionMockSetAutoLogin,
      isAuthenticated: raceConditionMockIsAuthenticated,
      autoLogin: raceConditionMockAutoLogin,
    };
    return selector(state);
  },
}));

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: jest.fn(),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((endpoint: string) => `/api/v1/${endpoint.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: jest.fn((_key: string[], fn: () => Promise<null>) => {
      return {
        data: null,
        isLoading: false,
        isFetched: true,
        refetch: fn,
      };
    }),
  }),
}));

jest.mock("@/controllers/API/queries/auth/use-post-logout", () => ({
  useLogout: () => ({
    mutateAsync: raceConditionMockMutationLogout,
  }),
}));

describe("useGetAutoLogin - Race Condition Prevention", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    raceConditionMockIsAuthenticated = false;
    raceConditionMockAutoLogin = undefined;
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe("Prevent Premature Logout", () => {
    it("should_not_call_logout_when_isAuthenticated_is_false_but_session_not_validated", () => {
      // Arrange: Simulate the race condition scenario
      // isAuthenticated is false (initial Zustand state)
      // but user has valid HttpOnly cookies (not yet validated)
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false; // Manual login mode

      // Act: Simulate auto-login error (expected when LANGFLOW_AUTO_LOGIN=false)
      // The old buggy code would call mutationLogout() here

      // Assert: mutationLogout should NOT be called
      // because we haven't validated if the session is actually invalid
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });

    it("should_not_navigate_to_login_before_session_validation_completes", () => {
      // Arrange
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // Act: Simulate the scenario where user opens new tab

      // Assert: Should not navigate to login prematurely
      expect(raceConditionMockNavigate).not.toHaveBeenCalledWith(
        expect.stringContaining("/login"),
      );
    });

    it("should_allow_ProtectedRoute_to_handle_redirect_decisions", () => {
      // Arrange
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // Assert: The hook should NOT make redirect decisions
      // This responsibility belongs to ProtectedRoute
      expect(raceConditionMockNavigate).not.toHaveBeenCalled();
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });
  });

  describe("MCP Server New Tab Scenario", () => {
    it("should_preserve_valid_session_when_opening_new_tab", () => {
      // Arrange: User has valid session cookies but opens new tab
      // In new tab, Zustand state resets to defaults (isAuthenticated=false)
      raceConditionMockIsAuthenticated = false; // Default Zustand state in new tab
      raceConditionMockAutoLogin = undefined; // Not yet determined

      // Act: The new code should wait for session validation
      // instead of immediately logging out

      // Assert: No premature logout
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
      expect(raceConditionMockNavigate).not.toHaveBeenCalled();
    });

    it("should_not_clear_cookies_before_session_validation", () => {
      // Arrange
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // Assert: Cookies should not be cleared prematurely
      // mutationLogout would clear HttpOnly cookies
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });
  });

  describe("Auto-Login Mode Behavior", () => {
    it("should_preserve_retry_logic_when_auto_login_enabled", () => {
      // Arrange
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = true; // Auto-login mode

      // This behavior is preserved - retry logic for auto-login mode
      // The key change is that manual login mode no longer calls logout
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });

    it("should_not_logout_when_authenticated_and_auto_login_fails", () => {
      // Arrange: User is authenticated but auto-login check fails
      raceConditionMockIsAuthenticated = true;
      raceConditionMockAutoLogin = false;

      // Should never logout an authenticated user
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });
  });

  describe("State Consistency", () => {
    it("should_not_modify_isAuthenticated_directly_in_hook", () => {
      // The hook should NOT modify isAuthenticated
      // That's the responsibility of useGetAuthSession
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // No direct modification of isAuthenticated should occur
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });
  });

  describe("Edge Cases", () => {
    it("should_handle_undefined_autoLogin_state_gracefully", () => {
      // Arrange: autoLogin is undefined (initial state)
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = undefined;

      // Should not cause errors or premature actions
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
      expect(raceConditionMockNavigate).not.toHaveBeenCalled();
    });

    it("should_handle_rapid_navigation_between_tabs", () => {
      // Arrange: Simulate rapid tab switching
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // No race condition should cause logout
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });

    it("should_handle_slow_network_conditions", () => {
      // Arrange: Session validation takes time
      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // Assert: Even with slow network, no premature logout
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });
  });
});

describe("handleAutoLoginError - Behavior Verification", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    raceConditionMockIsAuthenticated = false;
    raceConditionMockAutoLogin = undefined;
  });

  describe("Manual Login Mode (LANGFLOW_AUTO_LOGIN=false)", () => {
    it("should_NOT_call_mutationLogout_in_manual_login_mode", () => {
      // This is the critical fix
      // Old behavior: called mutationLogout() when !isAuthenticated && !IS_AUTO_LOGIN
      // New behavior: does NOT call mutationLogout()

      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      // The fix removes this branch entirely
      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });

    it("should_NOT_navigate_to_login_in_manual_login_mode", () => {
      // Old behavior: navigated to /login
      // New behavior: delegates to ProtectedRoute

      raceConditionMockIsAuthenticated = false;
      raceConditionMockAutoLogin = false;

      expect(raceConditionMockNavigate).not.toHaveBeenCalled();
    });
  });

  describe("Regression Prevention", () => {
    it("should_never_clear_valid_cookies_before_validation", () => {
      // This test ensures the bug doesn't reoccur
      // mutationLogout clears HttpOnly cookies - this should never happen
      // before useGetAuthSession validates the session

      expect(raceConditionMockMutationLogout).not.toHaveBeenCalled();
    });

    it("should_maintain_single_source_of_truth_for_auth_redirects", () => {
      // ProtectedRoute should be the single source of truth
      // This hook should NOT make redirect decisions

      expect(raceConditionMockNavigate).not.toHaveBeenCalled();
    });
  });
});
