import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mockMutate = jest.fn();
jest.mock("@/controllers/API/queries/auth", () => ({
  useAddUser: () => ({ mutate: mockMutate }),
}));

const mockNavigate = jest.fn();
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (s: {
      setSuccessData: jest.Mock;
      setErrorData: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

import SignUpPage from "../SignUpPage";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SignUpPage />
    </MemoryRouter>,
  );
}

function fill(field: string, value: string) {
  fireEvent.change(screen.getByLabelText(field), { target: { value } });
}

describe("Lothal SignUpPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the Lothal sign-up card", () => {
    renderAt("/signup");
    expect(screen.getByText("Create your account")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create account" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  });

  it("links to login, preserving the redirect param", () => {
    renderAt("/signup?redirect=/lothal");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      `/login?redirect=${encodeURIComponent("/lothal")}`,
    );
  });

  it("links to a plain login when there is no redirect", () => {
    renderAt("/signup");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("creates the account on submit and trims the credentials", () => {
    renderAt("/signup?redirect=/lothal");

    fill("Username", "  ada  ");
    fill("Password", "secret");
    fill("Confirm password", "secret");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(mockMutate).toHaveBeenCalledWith(
      { username: "ada", password: "secret" },
      expect.any(Object),
    );

    // Drive the success callback the way react-query would.
    const [, handlers] = mockMutate.mock.calls[0];
    handlers.onSuccess({ id: "u1" });
    expect(mockSetSuccessData).toHaveBeenCalled();
    // After signup, hop to login carrying the redirect along.
    expect(mockNavigate).toHaveBeenCalledWith(
      `/login?redirect=${encodeURIComponent("/lothal")}`,
    );
  });

  it("does not submit when fields are empty", () => {
    renderAt("/signup");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("does not submit when passwords do not match", () => {
    renderAt("/signup");
    fill("Username", "ada");
    fill("Password", "secret");
    fill("Confirm password", "different");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText("Passwords don't match.")).toBeInTheDocument();
  });

  it("does not submit when fields are whitespace-only", () => {
    renderAt("/signup");
    fill("Username", "   ");
    fill("Password", "   ");
    fill("Confirm password", "   ");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("surfaces a backend error through the alert store", () => {
    renderAt("/signup");
    fill("Username", "ada");
    fill("Password", "secret");
    fill("Confirm password", "secret");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    const [, handlers] = mockMutate.mock.calls[0];
    handlers.onError({ response: { data: { detail: "username taken" } } });
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Sign up failed",
      list: ["username taken"],
    });
  });
});
