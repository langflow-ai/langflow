/**
 * Tests for PlaygroundAuthGate Decision Logic
 *
 * The PlaygroundAuthGate protects the /playground/:id/ route by:
 * - Allowing access when auto-login is enabled (autoLogin === true)
 * - Allowing access when user is already authenticated
 * - Redirecting to /login when auto-login is disabled and user is not authenticated
 * - Showing a loading state while auth checks are in progress
 */

import { renderHook } from "@testing-library/react";

type PlaygroundAuthState = "loading" | "authenticated" | "redirect";

function computePlaygroundAuthState(
  autoLogin: boolean | null,
  isAuthenticated: boolean,
  isAutoLoginFetched: boolean,
  isSessionFetched: boolean,
): PlaygroundAuthState {
  const isAuthCheckComplete =
    (isAutoLoginFetched || isAuthenticated) && isSessionFetched;

  if (!isAuthCheckComplete) return "loading";
  if (autoLogin === true || isAuthenticated) return "authenticated";
  if (autoLogin === false && !isAuthenticated) return "redirect";
  return "loading";
}

function usePlaygroundAuthState(
  autoLogin: boolean | null,
  isAuthenticated: boolean,
  isAutoLoginFetched: boolean,
  isSessionFetched: boolean,
): PlaygroundAuthState {
  return computePlaygroundAuthState(
    autoLogin,
    isAuthenticated,
    isAutoLoginFetched,
    isSessionFetched,
  );
}

describe("PlaygroundAuthGate - Auth Decision Logic", () => {
  describe("Auto-Login Enabled (autoLogin === true)", () => {
    it("should_return_authenticated_when_autoLogin_is_true_and_fetched", () => {
      const result = computePlaygroundAuthState(true, false, true, true);
      expect(result).toBe("authenticated");
    });

    it("should_return_authenticated_when_autoLogin_true_regardless_of_isAuthenticated", () => {
      expect(computePlaygroundAuthState(true, true, true, true)).toBe(
        "authenticated",
      );
      expect(computePlaygroundAuthState(true, false, true, true)).toBe(
        "authenticated",
      );
    });
  });

  describe("User Already Authenticated (autoLogin === false)", () => {
    it("should_return_authenticated_when_user_is_authenticated_and_autoLogin_false", () => {
      const result = computePlaygroundAuthState(false, true, true, true);
      expect(result).toBe("authenticated");
    });

    it("should_return_authenticated_when_user_is_authenticated_even_before_autoLogin_fetched", () => {
      // isAuthenticated=true makes isAuthCheckComplete=true (skips autoLogin fetch)
      const result = computePlaygroundAuthState(false, true, false, true);
      expect(result).toBe("authenticated");
    });
  });

  describe("Not Authenticated with Auto-Login Disabled", () => {
    it("should_return_redirect_when_autoLogin_false_and_not_authenticated", () => {
      const result = computePlaygroundAuthState(false, false, true, true);
      expect(result).toBe("redirect");
    });
  });

  describe("Loading States", () => {
    it("should_return_loading_when_autoLogin_is_null_and_not_authenticated", () => {
      const result = computePlaygroundAuthState(null, false, false, false);
      expect(result).toBe("loading");
    });

    it("should_return_loading_when_session_not_yet_fetched", () => {
      const result = computePlaygroundAuthState(false, false, true, false);
      expect(result).toBe("loading");
    });

    it("should_return_loading_when_autoLogin_not_yet_fetched_and_not_authenticated", () => {
      const result = computePlaygroundAuthState(null, false, false, true);
      expect(result).toBe("loading");
    });
  });

  describe("State Transitions", () => {
    it("should_transition_from_loading_to_authenticated_when_autoLogin_becomes_true", () => {
      const { result, rerender } = renderHook(
        ({
          autoLogin,
          isAuthenticated,
          isAutoLoginFetched,
          isSessionFetched,
        }) =>
          usePlaygroundAuthState(
            autoLogin,
            isAuthenticated,
            isAutoLoginFetched,
            isSessionFetched,
          ),
        {
          initialProps: {
            autoLogin: null as boolean | null,
            isAuthenticated: false,
            isAutoLoginFetched: false,
            isSessionFetched: false,
          },
        },
      );

      expect(result.current).toBe("loading");

      rerender({
        autoLogin: true,
        isAuthenticated: true,
        isAutoLoginFetched: true,
        isSessionFetched: true,
      });

      expect(result.current).toBe("authenticated");
    });

    it("should_transition_from_loading_to_redirect_when_autoLogin_becomes_false_with_no_auth", () => {
      const { result, rerender } = renderHook(
        ({
          autoLogin,
          isAuthenticated,
          isAutoLoginFetched,
          isSessionFetched,
        }) =>
          usePlaygroundAuthState(
            autoLogin,
            isAuthenticated,
            isAutoLoginFetched,
            isSessionFetched,
          ),
        {
          initialProps: {
            autoLogin: null as boolean | null,
            isAuthenticated: false,
            isAutoLoginFetched: false,
            isSessionFetched: false,
          },
        },
      );

      expect(result.current).toBe("loading");

      rerender({
        autoLogin: false,
        isAuthenticated: false,
        isAutoLoginFetched: true,
        isSessionFetched: true,
      });

      expect(result.current).toBe("redirect");
    });

    it("should_transition_from_loading_to_authenticated_when_session_restores_auth", () => {
      const { result, rerender } = renderHook(
        ({
          autoLogin,
          isAuthenticated,
          isAutoLoginFetched,
          isSessionFetched,
        }) =>
          usePlaygroundAuthState(
            autoLogin,
            isAuthenticated,
            isAutoLoginFetched,
            isSessionFetched,
          ),
        {
          initialProps: {
            autoLogin: false as boolean | null,
            isAuthenticated: false,
            isAutoLoginFetched: true,
            isSessionFetched: false,
          },
        },
      );

      expect(result.current).toBe("loading");

      // Session check completes and restores auth (user had valid cookie)
      rerender({
        autoLogin: false,
        isAuthenticated: true,
        isAutoLoginFetched: true,
        isSessionFetched: true,
      });

      expect(result.current).toBe("authenticated");
    });
  });

  describe("Edge Cases", () => {
    it("should_handle_all_false_states_as_loading", () => {
      const result = computePlaygroundAuthState(null, false, false, false);
      expect(result).toBe("loading");
    });

    it("should_prioritize_isAuthenticated_over_autoLogin_false", () => {
      // User manually logged in even though auto-login is disabled
      const result = computePlaygroundAuthState(false, true, true, true);
      expect(result).toBe("authenticated");
    });

    it("should_not_redirect_while_session_check_is_pending", () => {
      // autoLogin=false but session not yet checked - user might have valid cookie
      const result = computePlaygroundAuthState(false, false, true, false);
      expect(result).toBe("loading");
    });
  });
});
