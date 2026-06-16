import { render } from "@testing-library/react";
import type { AxiosError } from "axios";

// --- Mocks -----------------------------------------------------------------
// The interceptor calls these mutation hooks to renew the token / log out.
// We assert on whether they fire, so they must be jest mocks we can inspect.
const mockRenew = jest.fn();
const mockLogout = jest.fn();
jest.mock("@/controllers/API/queries/auth", () => ({
  useRefreshAccessToken: () => ({ mutate: mockRenew }),
  useLogout: () => ({ mutate: mockLogout }),
}));

const mockSetAuthErrorCount = jest.fn();
const authState = {
  autoLogin: false, // forces the "should retry refresh" branch on auth errors
  accessToken: "tok",
  authenticationErrorCount: 0,
  setAuthenticationErrorCount: mockSetAuthErrorCount,
};
// The store's hook form `useAuthStore(selector)` is used for subscriptions, but
// the interceptor reads the live error count via `useAuthStore.getState()` so the
// ">3" logout cap can't be defeated by a stale render closure — mock both.
jest.mock("@/stores/authStore", () => {
  const useAuthStoreMock = (selector: (s: typeof authState) => unknown) =>
    selector(authState);
  (
    useAuthStoreMock as unknown as { getState: () => typeof authState }
  ).getState = () => authState;
  return { __esModule: true, default: useAuthStoreMock };
});

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (
    selector: (s: { setHealthCheckTimeout: jest.Mock }) => unknown,
  ) => selector({ setHealthCheckTimeout: jest.fn() }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      verticesBuild: { verticesIds: [] },
      updateBuildStatus: jest.fn(),
      setIsBuilding: jest.fn(),
    }),
  },
}));

jest.mock("@/customization/hooks/use-custom-api-headers", () => ({
  useCustomApiHeaders: () => ({}),
}));

jest.mock("fetch-intercept", () => ({
  register: () => () => {},
}));

import { ApiInterceptor, api } from "../api";

/**
 * Render <ApiInterceptor /> so its effect registers the response interceptor
 * on the shared `api` instance, and return the captured rejection handler.
 */
function mountAndCaptureErrorHandler() {
  const useSpy = jest.spyOn(api.interceptors.response, "use");
  render(<ApiInterceptor />);
  // The first response.use call is the auth interceptor; arg[1] is onRejected.
  const onRejected = useSpy.mock.calls[0][1] as (
    error: AxiosError,
  ) => Promise<unknown>;
  useSpy.mockRestore();
  return onRejected;
}

function authError(status: number, method: string, url: string): AxiosError {
  return {
    response: { status },
    config: { method, url },
  } as unknown as AxiosError;
}

describe("ApiInterceptor auth-error handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    authState.authenticationErrorCount = 0;
    // Default to a non-auth page so the refresh path is exercised.
    window.history.pushState({}, "", "/");
  });

  it("re-rejects a 403 on POST /users/ without renewing the token or logging out", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(403, "post", "/api/v1/users/");

    // The signup-disabled 403 must propagate to the caller's onError...
    await expect(onRejected(error)).rejects.toBe(error);

    // ...and must NOT trigger the refresh→logout path that would swallow it.
    expect(mockRenew).not.toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("re-rejects a 403 on the bare POST /users endpoint (no trailing slash)", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(403, "POST", "/api/v1/users");

    await expect(onRejected(error)).rejects.toBe(error);
    expect(mockRenew).not.toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("still runs the refresh path for a 403 on GET /users/ (POST-only scoping)", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(403, "get", "/api/v1/users/");

    // A GET is not the signup create call, so the auth error is treated as a
    // (possibly) expired session and the token-renew path runs.
    await onRejected(error);
    expect(mockRenew).toHaveBeenCalledTimes(1);
  });

  it("still runs the refresh path for a 401 on GET /users/", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(401, "get", "/api/v1/users/");

    await onRejected(error);
    expect(mockRenew).toHaveBeenCalledTimes(1);
  });

  it("does not over-exempt: a 403 on a POST to a non-users endpoint still refreshes", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(403, "post", "/api/v1/login");

    await onRejected(error);
    expect(mockRenew).toHaveBeenCalledTimes(1);
  });

  it("does not exempt URLs that merely contain 'users' in a non-terminal segment", async () => {
    const onRejected = mountAndCaptureErrorHandler();
    // pathname is /api/v1/users/me — does not end in /users, so not exempt.
    const error = authError(403, "post", "/api/v1/users/me");

    await onRejected(error);
    expect(mockRenew).toHaveBeenCalledTimes(1);
  });

  // --- B.16: terminate the refresh loop ------------------------------------

  it("logs out instead of refreshing once the live error count exceeds the cap", async () => {
    // The interceptor reads the count via getState(), so a stale render closure
    // can't keep the count pinned at 0. Once it is past the cap, the next auth
    // error must log out (ending the loop) rather than renew again.
    authState.authenticationErrorCount = 4;
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(401, "get", "/api/v1/flows");

    // Past the cap, the handler re-rejects instead of renewing.
    await expect(onRejected(error)).rejects.toBe(error);

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockRenew).not.toHaveBeenCalled();
    // Counter is reset so a fresh session starts clean.
    expect(mockSetAuthErrorCount).toHaveBeenCalledWith(0);
  });

  it("neither refreshes nor logs out on /signup (no unbounded refresh loop)", async () => {
    // A logged-out visitor on /signup is expected; an auth error there must be
    // re-rejected without touching the refresh→logout path. "/signup" does not
    // contain "login", so it was previously unguarded.
    window.history.pushState({}, "", "/signup");
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(401, "get", "/api/v1/flows");

    await expect(onRejected(error)).rejects.toBe(error);
    expect(mockRenew).not.toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("still guards the /login page against the refresh loop", async () => {
    window.history.pushState({}, "", "/login");
    const onRejected = mountAndCaptureErrorHandler();
    const error = authError(401, "get", "/api/v1/flows");

    await expect(onRejected(error)).rejects.toBe(error);
    expect(mockRenew).not.toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });
});
