import { render, screen } from "@testing-library/react";

// Capture redirects instead of needing a router.
jest.mock("@/customization/components/custom-navigate", () => ({
  CustomNavigate: ({ to }: { to: string }) => (
    <div data-testid="navigate" data-to={to} />
  ),
}));

const mockConsumeRedirectUrl = jest.fn();
jest.mock("@/hooks/use-sanitize-redirect-url", () => ({
  consumeRedirectUrl: () => mockConsumeRedirectUrl(),
}));

import useAuthStore from "@/stores/authStore";
import { ProtectedLoginRoute } from "../index";

function renderGuard(state: { isAuthenticated: boolean; autoLogin: boolean }) {
  useAuthStore.setState(state);
  return render(
    <ProtectedLoginRoute>
      <div data-testid="login-page" />
    </ProtectedLoginRoute>,
  );
}

describe("ProtectedLoginRoute", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockConsumeRedirectUrl.mockReturnValue(null);
    window.history.pushState({}, "", "/login");
  });

  it("renders the login page for anonymous visitors", () => {
    renderGuard({ isAuthenticated: false, autoLogin: false });
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });

  it("sends an authenticated user to /flows by default — not /home, which would fall through to the public landing", () => {
    renderGuard({ isAuthenticated: true, autoLogin: false });
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/flows");
  });

  it("sends auto-login deployments to /flows by default", () => {
    renderGuard({ isAuthenticated: false, autoLogin: true });
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/flows");
  });

  it("honors the ?redirect= query param (the landing's /lothal funnel)", () => {
    window.history.pushState({}, "", "/login?redirect=/lothal");
    renderGuard({ isAuthenticated: true, autoLogin: false });
    expect(screen.getByTestId("navigate")).toHaveAttribute(
      "data-to",
      "/lothal",
    );
  });

  it("falls back to the stashed sessionStorage redirect when there is no query param", () => {
    mockConsumeRedirectUrl.mockReturnValue("/lothal");
    renderGuard({ isAuthenticated: true, autoLogin: false });
    expect(screen.getByTestId("navigate")).toHaveAttribute(
      "data-to",
      "/lothal",
    );
  });
});
