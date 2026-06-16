import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockLogoutMutate = jest.fn();
jest.mock("@/controllers/API/queries/auth/use-post-logout", () => ({
  useLogout: () => ({ mutate: mockLogoutMutate, isPending: false }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (s: unknown) => unknown) =>
    selector({ userData: { username: "captain" } }),
}));

import Settings from "../index";

describe("Lothal Settings", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
  });

  it("shows the appearance, account, and keys sections", () => {
    render(<Settings />);
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Account")).toBeInTheDocument();
    expect(screen.getByText("Keys & providers")).toBeInTheDocument();
  });

  it("renders the signed-in username from the auth store", () => {
    render(<Settings />);
    expect(screen.getByText("captain")).toBeInTheDocument();
  });

  it("persists the theme choice when a theme toggle is pressed", () => {
    render(<Settings />);
    // Default surface theme is dark; switch to light and assert it sticks.
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(window.localStorage.getItem("lothal:theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("persists the density choice when a density toggle is pressed", () => {
    render(<Settings />);
    fireEvent.click(screen.getByRole("button", { name: "compact" }));
    expect(window.localStorage.getItem("lothal:density")).toBe("compact");
  });

  it("logs out and returns home on settle", () => {
    render(<Settings />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(mockLogoutMutate).toHaveBeenCalledTimes(1);
    // The page passes an onSettled that navigates home — invoke it to assert.
    const opts = mockLogoutMutate.mock.calls[0][1];
    opts.onSettled();
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("links out to the credential pages", () => {
    render(<Settings />);
    const openButtons = screen.getAllByRole("button", { name: /Open/ });
    fireEvent.click(openButtons[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/settings/global-variables");
    fireEvent.click(openButtons[1]);
    expect(mockNavigate).toHaveBeenCalledWith("/settings/api-keys");
  });
});
