/**
 * AuthProvider's user data must reach `useAuthStore` on every path, not only on
 * login. After a reload the session is restored by AppInitPage calling the
 * context's `setUserData`, and pages that read the store (the Connections
 * page's owner column, flowStore, use-get-flow-id) saw `null` until the next
 * login. Renders the real provider against the real auth store; only the
 * network hooks and the store's side stores are mocked.
 */

import { act, renderHook } from "@testing-library/react";
import { type ReactNode, useContext } from "react";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";

jest.mock("@/utils/cookie-manager", () => ({
  cookieManager: {
    get: jest.fn(),
    set: jest.fn(),
    clearAuthCookies: jest.fn(),
  },
  getCookiesInstance: jest.fn(),
}));

jest.mock("@/stores/storeStore", () => ({
  useStoreStore: <T,>(
    selector: (state: {
      checkHasStore: () => void;
      fetchApiData: () => void;
    }) => T,
  ): T => selector({ checkHasStore: jest.fn(), fetchApiData: jest.fn() }),
}));

const mockMutateLoggedUser = jest.fn();

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetUserData: () => ({ mutate: mockMutateLoggedUser }),
}));

jest.mock(
  "@/controllers/API/queries/variables/use-get-mutation-global-variables",
  () => ({
    useGetGlobalVariablesMutation: () => ({ mutate: jest.fn() }),
  }),
);

import { AuthContext, AuthProvider } from "../authContext";

const USER: Users = {
  id: "user-1",
  username: "eric",
  is_active: true,
  is_superuser: false,
  profile_image: "",
  create_at: new Date("2026-09-01T00:00:00Z"),
  updated_at: new Date("2026-09-01T00:00:00Z"),
};

const wrapper = ({ children }: { children: ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

function renderAuthContext() {
  return renderHook(() => useContext(AuthContext), { wrapper });
}

/** Signed in through login, where `useGetUserData` also writes the store. */
function signIn(result: ReturnType<typeof renderAuthContext>["result"]) {
  act(() => result.current.setUserData(USER));
  useAuthStore.setState({ userData: USER });
}

describe("AuthProvider keeps useAuthStore.userData in sync", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({ userData: null });
  });

  it("mirrors a session-restored user into the store", () => {
    const { result } = renderAuthContext();

    // What AppInitPage does with the session probe after a reload.
    act(() => result.current.setUserData(USER));

    expect(result.current.userData).toEqual(USER);
    expect(useAuthStore.getState().userData).toEqual(USER);
  });

  it("clears the store copy together with the context copy", () => {
    const { result } = renderAuthContext();
    signIn(result);

    act(() => result.current.setUserData(null));

    expect(result.current.userData).toBeNull();
    expect(useAuthStore.getState().userData).toBeNull();
  });

  it("clears the store copy when the auth session is cleared", () => {
    const { result } = renderAuthContext();
    signIn(result);

    act(() => result.current.clearAuthSession());

    expect(result.current.userData).toBeNull();
    expect(useAuthStore.getState().userData).toBeNull();
  });

  it("clears the store copy when fetching the user fails", () => {
    const { result } = renderAuthContext();
    signIn(result);

    act(() => result.current.getUser());
    act(() => mockMutateLoggedUser.mock.calls[0][1].onError());

    expect(useAuthStore.getState().userData).toBeNull();
  });

  it("hands out a stable setter so effects that depend on it do not re-run", () => {
    const { result, rerender } = renderAuthContext();
    const first = result.current.setUserData;

    act(() => result.current.setUserData(USER));
    rerender();

    expect(result.current.setUserData).toBe(first);
  });
});
