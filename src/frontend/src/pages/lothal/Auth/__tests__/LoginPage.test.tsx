import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mockMutate = jest.fn();
jest.mock("@/controllers/API/queries/auth", () => ({
  useLoginUser: () => ({ mutate: mockMutate }),
}));

const mockLogin = jest.fn();
const mockClearAuthSession = jest.fn();
jest.mock("@/contexts/authContext", () => {
  const React = require("react");
  return {
    AuthContext: React.createContext({
      login: mockLogin,
      clearAuthSession: mockClearAuthSession,
    }),
  };
});

const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));

const mockQueryClear = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => ({ clear: mockQueryClear }),
}));

import LoginPage from "../LoginPage";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe("Lothal LoginPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the dockyard sign-in card", () => {
    renderAt("/login");
    expect(screen.getByText("Welcome back")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("links to signup, preserving the redirect param", () => {
    renderAt("/login?redirect=/lothal");
    const link = screen.getByRole("link", { name: "Create an account" });
    expect(link).toHaveAttribute(
      "href",
      `/signup?redirect=${encodeURIComponent("/lothal")}`,
    );
  });

  it("links to a plain signup when there is no redirect", () => {
    renderAt("/login");
    expect(
      screen.getByRole("link", { name: "Create an account" }),
    ).toHaveAttribute("href", "/signup");
  });

  it("logs in on submit and carries the access token into the session", () => {
    renderAt("/login?redirect=/lothal");

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "  ada  " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    // Credentials are trimmed before they hit the mutation.
    expect(mockMutate).toHaveBeenCalledWith(
      { username: "ada", password: "secret" },
      expect.any(Object),
    );

    // Drive the success callback the way react-query would.
    const [, handlers] = mockMutate.mock.calls[0];
    handlers.onSuccess({ access_token: "tok", refresh_token: "ref" });
    expect(mockClearAuthSession).toHaveBeenCalled();
    expect(mockLogin).toHaveBeenCalledWith("tok", "login", "ref");
  });

  it("does not submit when fields are empty", () => {
    renderAt("/login");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("surfaces a backend error through the alert store", () => {
    renderAt("/login");
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "ada" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const [, handlers] = mockMutate.mock.calls[0];
    handlers.onError({ response: { data: { detail: "bad creds" } } });
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Sign in failed",
      list: ["bad creds"],
    });
  });
});
