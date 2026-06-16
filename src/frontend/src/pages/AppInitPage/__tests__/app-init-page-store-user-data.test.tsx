/**
 * Regression test for the cookie-based session restore bug.
 *
 * There are two `userData` holders: the AuthContext (React Context) and the
 * Zustand authStore. A fresh login populates both, but a session restore (the
 * user reopens the app with a valid HttpOnly refresh cookie) used to populate
 * only the context. Pages that read the store directly — e.g. Lothal Settings —
 * therefore showed a blank user ("Signed in" / "?") after reopening, even
 * though the session was valid.
 *
 * AppInitPage's session-restore effect must write the Zustand store too.
 */

import { render } from "@testing-library/react";
import { AuthContext } from "@/contexts/authContext";
import type { SessionResponse } from "@/controllers/API/queries/auth/use-get-auth-session";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
import type { AuthContextType } from "@/types/contexts/auth";
import { AppInitPage } from "../index";

type StoreSelector<T> = (state: Record<string, unknown>) => T;

// The session response we want the effect to react to.
let sessionData: SessionResponse | undefined;

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetAuthSession: () => ({ data: sessionData, isFetched: true }),
  useGetAutoLogin: () => ({ isFetched: true }),
}));
jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ isFetched: true }),
}));
jest.mock("@/controllers/API/queries/flows/use-get-basic-examples", () => ({
  useGetBasicExamplesQuery: () => ({ isFetched: true, refetch: jest.fn() }),
}));
jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  useGetFoldersQuery: () => ({}),
}));
jest.mock("@/controllers/API/queries/store", () => ({
  useGetTagsQuery: () => ({}),
}));
jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({}),
}));
jest.mock("@/controllers/API/queries/version", () => ({
  useGetVersionQuery: () => ({}),
}));
jest.mock("@/customization/components/custom-loading-page", () => ({
  CustomLoadingPage: () => null,
}));
jest.mock("@/customization/hooks/use-custom-primary-loading", () => ({
  useCustomPrimaryLoading: () => ({ isFetched: true }),
}));
jest.mock("../../LoadingPage", () => ({ LoadingPage: () => null }));
jest.mock("react-router-dom", () => ({ Outlet: () => null }));
jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: StoreSelector<unknown>) =>
    selector({ refreshStars: jest.fn(), refreshDiscordCount: jest.fn() }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: StoreSelector<unknown>) => selector({ isLoading: false }),
}));

function renderAppInit() {
  const ctx = {
    setUserData: jest.fn(),
    storeApiKey: jest.fn(),
  } as unknown as AuthContextType;
  return render(
    <AuthContext.Provider value={ctx}>
      <AppInitPage />
    </AuthContext.Provider>,
  );
}

describe("AppInitPage — Zustand store user data on session restore", () => {
  beforeEach(() => {
    sessionData = undefined;
    useAuthStore.setState({
      userData: null,
      isAuthenticated: false,
      isAdmin: false,
    });
  });

  it("populates the auth store userData when an authenticated session is restored", () => {
    sessionData = {
      authenticated: true,
      user: {
        id: "1",
        username: "admin",
        is_active: true,
        is_superuser: true,
      },
    };

    renderAppInit();

    const state = useAuthStore.getState();
    expect(state.userData?.username).toBe("admin");
    expect(state.isAuthenticated).toBe(true);
    expect(state.isAdmin).toBe(true);
  });

  it("clears the auth store userData when the session is explicitly unauthenticated", () => {
    useAuthStore.setState({
      userData: { username: "admin" } as Users,
      isAdmin: true,
    });
    sessionData = { authenticated: false };

    renderAppInit();

    const state = useAuthStore.getState();
    expect(state.userData).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isAdmin).toBe(false);
  });
});
