/**
 * AppInitPage fires the session probe and auto-login in parallel. On a fresh
 * auto-login context the probe carries no cookie, so the backend correctly
 * answers `{ authenticated: false }`. If that answer lands after login() has
 * already authenticated the page — or the probe fails, which resolves to the
 * same shape — it must not clear `isAuthenticated`: auto-login never re-runs,
 * so every `enabled: isAuthenticated` query (global variables, projects) would
 * stay disabled until a reload and `refetchQueries` would silently skip them.
 *
 * These tests render the real page against the real auth store and mock only
 * the network hooks, so the assertions exercise the effect that applies the
 * probe rather than a re-derivation of it.
 */

import { act, render } from "@testing-library/react";
import type { ReactNode } from "react";
import { AuthContext } from "@/contexts/authContext";
import type { SessionResponse } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";

type SessionQueryResult = {
  data: SessionResponse | undefined;
  isFetched: boolean;
};

const mockUseGetAuthSession = jest.fn<SessionQueryResult, []>();
const mockSetUserData = jest.fn();

jest.mock("react-router-dom", () => ({
  Outlet: () => <div data-testid="outlet" />,
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetAuthSession: () => mockUseGetAuthSession(),
  useGetAutoLogin: () => ({ isFetched: true }),
}));

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ isFetched: true }),
}));

jest.mock("@/controllers/API/queries/flows/use-get-basic-examples", () => ({
  useGetBasicExamplesQuery: () => ({ isFetched: true, refetch: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  useGetFoldersQuery: jest.fn(),
}));

jest.mock("@/controllers/API/queries/store", () => ({
  useGetTagsQuery: jest.fn(),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: jest.fn(),
}));

jest.mock("@/controllers/API/queries/version", () => ({
  useGetVersionQuery: jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-primary-loading", () => ({
  useCustomPrimaryLoading: () => ({ isFetched: true }),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ refreshStars: jest.fn(), refreshDiscordCount: jest.fn() }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ isLoading: false }),
}));

jest.mock("@/customization/components/custom-loading-page", () => ({
  CustomLoadingPage: () => <div data-testid="custom-loading" />,
}));

jest.mock("../../LoadingPage", () => ({
  LoadingPage: () => <div data-testid="loading" />,
}));

import { AppInitPage } from "../index";

const AuthWrapper = ({ children }: { children: ReactNode }) => (
  <AuthContext.Provider
    value={
      {
        accessToken: null,
        apiKey: null,
        authenticationErrorCount: 0,
        clearAuthSession: jest.fn(),
        getUser: jest.fn(),
        login: jest.fn(),
        setApiKey: jest.fn(),
        setUserData: mockSetUserData,
        storeApiKey: jest.fn(),
        userData: null,
      } as React.ContextType<typeof AuthContext>
    }
  >
    {children}
  </AuthContext.Provider>
);

const PENDING_PROBE: SessionQueryResult = { data: undefined, isFetched: false };
const UNAUTHENTICATED_PROBE: SessionQueryResult = {
  data: { authenticated: false },
  isFetched: true,
};

function renderPage() {
  return render(<AppInitPage />, { wrapper: AuthWrapper });
}

// What login() leaves behind once both of its legs have settled.
function completeAutoLogin() {
  act(() => {
    useAuthStore.setState({ autoLogin: true, isAuthenticated: true });
  });
}

function deliverProbe(
  rerender: ReturnType<typeof renderPage>["rerender"],
  probe: SessionQueryResult,
) {
  mockUseGetAuthSession.mockReturnValue(probe);
  act(() => {
    rerender(<AppInitPage />);
  });
}

describe("AppInitPage - session probe vs auto-login", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({
      autoLogin: null,
      isAuthenticated: false,
      isAdmin: false,
    });
    mockUseGetAuthSession.mockReturnValue(PENDING_PROBE);
  });

  it("keeps auto-login's auth when an unauthenticated probe lands afterwards", () => {
    const { rerender } = renderPage();

    completeAutoLogin();
    deliverProbe(rerender, UNAUTHENTICATED_PROBE);

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("reaches the same auth state whichever request lands first", () => {
    const { rerender } = renderPage();

    deliverProbe(rerender, UNAUTHENTICATED_PROBE);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);

    completeAutoLogin();

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("still clears auth on an unauthenticated probe when auto-login is off", () => {
    useAuthStore.setState({ autoLogin: false, isAuthenticated: true });
    const { rerender } = renderPage();

    deliverProbe(rerender, UNAUTHENTICATED_PROBE);

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("applies an authenticated probe", () => {
    const { rerender } = renderPage();
    const user = {
      id: "user-1",
      username: "langflow",
      is_active: true,
      is_superuser: true,
    };

    deliverProbe(rerender, {
      data: { authenticated: true, user },
      isFetched: true,
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isAdmin).toBe(true);
    expect(mockSetUserData).toHaveBeenCalledWith(user);
  });
});
