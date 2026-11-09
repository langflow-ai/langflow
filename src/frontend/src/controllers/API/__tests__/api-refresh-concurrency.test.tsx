import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, waitFor } from "@testing-library/react";
import axios, {
  type AxiosAdapter,
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { MemoryRouter } from "react-router-dom";
import { ProtectedRoute } from "@/components/authorization/authGuard";
import useAuthStore from "@/stores/authStore";
import { ApiInterceptor, api } from "../api";
import type { RefreshAccessTokenResponse } from "../services/auth-session";

jest.mock("fetch-intercept", () => ({ register: () => () => undefined }));
jest.mock("@/constants/constants", () => ({
  ...jest.requireActual("@/constants/constants"),
  IS_AUTO_LOGIN: false,
}));

function response<T>(
  config: InternalAxiosRequestConfig,
  data: T,
): AxiosResponse<T> {
  return { config, data, status: 200, statusText: "OK", headers: {} };
}

describe("API recovery with one-use refresh tokens", () => {
  const originalAdapter = api.defaults.adapter;

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    jest.restoreAllMocks();
  });

  it("shares proactive refresh with expired requests without logging out", async () => {
    useAuthStore.setState({
      autoLogin: false,
      isAuthenticated: true,
      authenticationErrorCount: 4,
    });
    const refreshed: RefreshAccessTokenResponse = {
      access_token: "new-access-token",
      refresh_token: "new-refresh-token",
      token_type: "bearer",
    };
    let complete!: (value: RefreshAccessTokenResponse) => void;
    const refreshResponse = new Promise<RefreshAccessTokenResponse>(
      (resolve) => {
        complete = resolve;
      },
    );
    const refresh = jest.fn(() => refreshResponse);
    const logout = jest.fn();
    const expiredRequests = jest.fn();
    const adapter: AxiosAdapter = async (config) => {
      if (config.url?.endsWith("/refresh")) {
        return response(config, await refresh());
      }
      if (config.url?.endsWith("/logout")) {
        logout();
        return response(config, {});
      }
      expiredRequests();
      throw new AxiosError(
        "expired access",
        AxiosError.ERR_BAD_REQUEST,
        config,
        {},
        {
          ...response(config, {}),
          status: 401,
        },
      );
    };
    api.defaults.adapter = adapter;
    const retried = jest.spyOn(axios, "request").mockResolvedValue({
      config: { headers: new AxiosHeaders() },
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
    });
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const mounted = render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ApiInterceptor />
          <ProtectedRoute>
            <div>Signed in</div>
          </ProtectedRoute>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));

    const requests = Array.from({ length: 8 }, (_, index) =>
      api.get(`/api/v1/protected-${index}`).catch((error: unknown) => error),
    );
    await waitFor(() => expect(expiredRequests).toHaveBeenCalledTimes(8));
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(logout).not.toHaveBeenCalled();
    await act(async () => {
      complete(refreshed);
      await Promise.all(requests);
    });

    expect(retried).toHaveBeenCalledTimes(8);
    expect(logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    mounted.unmount();
    client.clear();
  });
});
