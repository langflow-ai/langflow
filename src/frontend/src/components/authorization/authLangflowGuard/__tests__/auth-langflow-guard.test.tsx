import { render, screen } from "@testing-library/react";
import { createContext } from "react";

// Capture redirects instead of needing a router.
jest.mock("@/customization/components/custom-navigate", () => ({
  CustomNavigate: ({ to }: { to: string }) => (
    <div data-testid="navigate" data-to={to} />
  ),
}));

jest.mock("@/pages/LoadingPage", () => ({
  LoadingPage: () => <div data-testid="loading" />,
}));

// The guard only reads `userData` from the context; provide a bare context so
// the test doesn't pull the real AuthContext provider's API machinery.
jest.mock("@/contexts/authContext", () => ({
  AuthContext: createContext<{ userData: unknown }>({ userData: null }),
}));

import { AuthContext } from "@/contexts/authContext";
import useAuthStore from "@/stores/authStore";
import { ProtectedLangflowRoute } from "../index";

function renderGuard({
  isAuthenticated,
  autoLogin,
  isAdmin,
  userData,
}: {
  isAuthenticated: boolean;
  autoLogin: boolean | null;
  isAdmin: boolean;
  userData: unknown;
}) {
  useAuthStore.setState({ isAuthenticated, autoLogin, isAdmin } as never);
  return render(
    <AuthContext.Provider value={{ userData } as never}>
      <ProtectedLangflowRoute>
        <div data-testid="langflow-page" />
      </ProtectedLangflowRoute>
    </AuthContext.Provider>,
  );
}

describe("ProtectedLangflowRoute", () => {
  it("renders the Langflow page for an authenticated admin", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: false,
      isAdmin: true,
      userData: { id: "u1" },
    });
    expect(screen.getByTestId("langflow-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });

  it("allows auto-login / dev deployments (implicit superuser)", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: true,
      isAdmin: false,
      userData: null,
    });
    expect(screen.getByTestId("langflow-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });

  it("redirects an authenticated non-admin (Lothal user) to /lothal", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: false,
      isAdmin: false,
      userData: { id: "u1" },
    });
    expect(screen.getByTestId("navigate")).toHaveAttribute(
      "data-to",
      "/lothal",
    );
    expect(screen.queryByTestId("langflow-page")).not.toBeInTheDocument();
  });

  it("shows the loader while the user is still resolving (no premature redirect)", () => {
    // autoLogin not yet resolved and whoami still in flight: an admin must not
    // be flashed a redirect before isAdmin is known.
    renderGuard({
      isAuthenticated: true,
      autoLogin: null,
      isAdmin: false,
      userData: null,
    });
    expect(screen.getByTestId("loading")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("langflow-page")).not.toBeInTheDocument();
  });
});
