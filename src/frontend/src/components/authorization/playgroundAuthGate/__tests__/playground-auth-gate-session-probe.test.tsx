/**
 * The playground gate applies the same session probe as AppInitPage, so it
 * follows the same rule: an unauthenticated answer that lands after auto-login
 * has signed the page in must not clear `isAuthenticated`. Renders the real
 * gate against the real auth store; only the network hooks are mocked.
 */

import { act, render } from "@testing-library/react";
import type { SessionResponse } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";

type SessionQueryResult = {
  data: SessionResponse | undefined;
  isFetched: boolean;
};

const mockUseGetAuthSession = jest.fn<SessionQueryResult, []>();

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetAuthSession: () => mockUseGetAuthSession(),
  useGetAutoLogin: () => ({ isFetched: true }),
}));

jest.mock("@/pages/LoadingPage", () => ({
  LoadingPage: () => <div data-testid="loading" />,
}));

import { PlaygroundAuthGate } from "../index";

const UNAUTHENTICATED_PROBE: SessionQueryResult = {
  data: { authenticated: false },
  isFetched: true,
};

function renderGate() {
  return render(
    <PlaygroundAuthGate>
      <div data-testid="playground" />
    </PlaygroundAuthGate>,
  );
}

function deliverProbe(
  rerender: ReturnType<typeof renderGate>["rerender"],
  probe: SessionQueryResult,
) {
  mockUseGetAuthSession.mockReturnValue(probe);
  act(() => {
    rerender(
      <PlaygroundAuthGate>
        <div data-testid="playground" />
      </PlaygroundAuthGate>,
    );
  });
}

describe("PlaygroundAuthGate - session probe vs auto-login", () => {
  beforeEach(() => {
    useAuthStore.setState({ autoLogin: null, isAuthenticated: false });
    mockUseGetAuthSession.mockReturnValue({
      data: undefined,
      isFetched: false,
    });
  });

  it("keeps auto-login's auth when an unauthenticated probe lands afterwards", () => {
    const { rerender } = renderGate();

    act(() => {
      useAuthStore.setState({ autoLogin: true, isAuthenticated: true });
    });
    deliverProbe(rerender, UNAUTHENTICATED_PROBE);

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("still clears auth on an unauthenticated probe when auto-login is off", () => {
    useAuthStore.setState({ autoLogin: false, isAuthenticated: true });
    const { rerender } = renderGate();

    deliverProbe(rerender, UNAUTHENTICATED_PROBE);

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
