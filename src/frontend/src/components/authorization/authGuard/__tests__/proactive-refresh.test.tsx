/**
 * Regression tests for the ProtectedRoute proactive token refresh.
 *
 * GHSA-fjgc-vj2f-77hm shortened the auto-login access token from 365 days to
 * ACCESS_TOKEN_EXPIRE_SECONDS (default 1h) and added a refresh_token_lf cookie.
 * The proactive refresh interval used to be armed only for manual sessions
 * (`!autoLogin`), so under default AUTO_LOGIN a tab left open past the token
 * lifetime would 401 with no client-side recovery. The interval must now be
 * armed for auto-login sessions too so they refresh transparently via /refresh.
 */

import { act, render } from "@testing-library/react";

// Mirrors the mocked LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS below (seconds → ms).
const ACCESS_TOKEN_EXPIRE_SECONDS = 3240;
const INTERVAL_MS = ACCESS_TOKEN_EXPIRE_SECONDS * 1000;

const mockMutateRefresh = jest.fn();
let mockAuthState: {
  isAuthenticated: boolean;
  autoLogin: boolean | undefined;
} = {
  isAuthenticated: true,
  autoLogin: true,
};

jest.mock("@/constants/constants", () => ({
  IS_AUTO_LOGIN: true,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS: 3240,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV: Number.NaN,
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useRefreshAccessToken: () => ({ mutate: mockMutateRefresh }),
}));

jest.mock("@/customization/components/custom-navigate", () => ({
  CustomNavigate: () => null,
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockAuthState) => unknown) =>
    selector(mockAuthState),
}));

import { ProtectedRoute } from "../index";

describe("ProtectedRoute - proactive token refresh", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockMutateRefresh.mockClear();
    sessionStorage.clear();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("arms the proactive refresh under auto-login (GHSA-fjgc-vj2f-77hm)", () => {
    mockAuthState = { isAuthenticated: true, autoLogin: true };

    render(
      <ProtectedRoute>
        <div>child</div>
      </ProtectedRoute>,
    );

    // Auto-login just minted a fresh token, so there is no redundant immediate
    // refresh on mount.
    expect(mockMutateRefresh).not.toHaveBeenCalled();

    // The interval keeps the now short-lived token alive via /refresh.
    act(() => {
      jest.advanceTimersByTime(INTERVAL_MS);
    });
    expect(mockMutateRefresh).toHaveBeenCalledTimes(1);

    act(() => {
      jest.advanceTimersByTime(INTERVAL_MS);
    });
    expect(mockMutateRefresh).toHaveBeenCalledTimes(2);
  });

  it("refreshes immediately on mount for manual sessions (unchanged)", () => {
    mockAuthState = { isAuthenticated: true, autoLogin: false };

    render(
      <ProtectedRoute>
        <div>child</div>
      </ProtectedRoute>,
    );

    // Manual sessions validate the cookie session once on mount...
    expect(mockMutateRefresh).toHaveBeenCalledTimes(1);

    // ...then keep refreshing on the interval.
    act(() => {
      jest.advanceTimersByTime(INTERVAL_MS);
    });
    expect(mockMutateRefresh).toHaveBeenCalledTimes(2);
  });

  it("does not arm a refresh until autoLogin is determined", () => {
    mockAuthState = { isAuthenticated: false, autoLogin: undefined };

    render(
      <ProtectedRoute>
        <div>child</div>
      </ProtectedRoute>,
    );

    act(() => {
      jest.advanceTimersByTime(INTERVAL_MS * 2);
    });
    expect(mockMutateRefresh).not.toHaveBeenCalled();
  });
});
