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
import { ProtectedAdminRoute } from "../index";

function renderGuard({
  isAuthenticated,
  autoLogin,
  isAdmin,
  userData,
}: {
  isAuthenticated: boolean;
  autoLogin: boolean;
  isAdmin: boolean;
  userData: unknown;
}) {
  useAuthStore.setState({ isAuthenticated, autoLogin, isAdmin });
  return render(
    <AuthContext.Provider value={{ userData } as never}>
      <ProtectedAdminRoute>
        <div data-testid="admin-page" />
      </ProtectedAdminRoute>
    </AuthContext.Provider>,
  );
}

describe("ProtectedAdminRoute", () => {
  it("shows the loading page while unauthenticated", () => {
    renderGuard({
      isAuthenticated: false,
      autoLogin: false,
      isAdmin: false,
      userData: null,
    });
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("bounces a non-admin user to /flows (the app home), not the landing page", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: false,
      isAdmin: false,
      userData: { id: "u1" },
    });
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/flows");
    expect(screen.queryByTestId("admin-page")).not.toBeInTheDocument();
  });

  it("bounces auto-login deployments to /flows (no admin page there)", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: true,
      isAdmin: true,
      userData: { id: "u1" },
    });
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/flows");
  });

  it("renders the admin page for an authenticated admin", () => {
    renderGuard({
      isAuthenticated: true,
      autoLogin: false,
      isAdmin: true,
      userData: { id: "u1" },
    });
    expect(screen.getByTestId("admin-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });
});
