import { fireEvent, render, screen } from "@testing-library/react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { ProtectedRoute } from "@/components/authorization/authGuard";
import { ProtectedLoginRoute } from "@/components/authorization/authLoginGuard";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";

let mockAuthenticated = false;
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector) =>
    selector({ isAuthenticated: mockAuthenticated, autoLogin: false }),
}));
jest.mock("@/controllers/API/queries/auth", () => ({
  useRefreshAccessToken: () => ({ mutate: jest.fn() }),
}));
jest.mock("@/constants/constants", () => ({
  IS_AUTO_LOGIN: false,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS: 3600,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV: Number.NaN,
}));

function Login() {
  useSanitizeRedirectUrl();
  return (
    <button
      onClick={() => {
        mockAuthenticated = true;
      }}
    >
      Log in
    </button>
  );
}

function Location() {
  const { pathname, search } = useLocation();
  return (
    <output data-testid="location">
      {pathname}
      {search}
    </output>
  );
}

describe("navigation under a URL prefix", () => {
  beforeEach(() => {
    mockAuthenticated = false;
    sessionStorage.clear();
  });

  it.each(["", "/langflow", "/tools/langflow"])(
    "returns to a protected deep link after login with prefix %s",
    async (prefix) => {
      window.history.replaceState(null, "", `${prefix}/flow/example`);
      const app = () => (
        <BrowserRouter basename={prefix || "/"}>
          <Location />
          <Routes>
            <Route
              path="/flow/:id"
              element={
                <ProtectedRoute>
                  <div>Flow editor</div>
                </ProtectedRoute>
              }
            />
            <Route
              path="/login"
              element={
                <ProtectedLoginRoute>
                  <Login />
                </ProtectedLoginRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      );
      const { rerender } = render(app());
      await screen.findByRole("button", { name: "Log in" });
      expect(screen.getByTestId("location")).toHaveTextContent(/^\/login$/);
      expect(sessionStorage.getItem("langflow_login_redirect")).toBe(
        "/flow/example",
      );
      fireEvent.click(screen.getByRole("button", { name: "Log in" }));
      rerender(app());
      await screen.findByText("Flow editor");
      expect(screen.getByTestId("location")).toHaveTextContent(
        /^\/flow\/example$/,
      );
    },
  );
});
