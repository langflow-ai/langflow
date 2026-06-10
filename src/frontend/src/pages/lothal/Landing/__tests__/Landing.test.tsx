import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

import useAuthStore from "@/stores/authStore";
import Landing from "../index";

function setAuth(state: { isAuthenticated: boolean; autoLogin: boolean }) {
  useAuthStore.setState(state);
}

describe("Lothal Landing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuth({ isAuthenticated: false, autoLogin: false });
  });

  it("renders the hero headline and the dockyard kicker", () => {
    render(<Landing />);
    expect(screen.getByText(/A conversation goes in\./)).toBeInTheDocument();
    expect(screen.getByText("The drydock for software")).toBeInTheDocument();
  });

  it("shows all five phases from the shared metadata", () => {
    render(<Landing />);
    for (const label of [
      "Clarify",
      "Sketch",
      "Refine",
      "Generate",
      "Deliver",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // The action phases (Clarify, Refine) are tagged as user-steered.
    expect(screen.getAllByText("you steer")).toHaveLength(2);
    expect(screen.getAllByText("lothal builds")).toHaveLength(3);
  });

  it("sends anonymous visitors to login with the lothal redirect", () => {
    render(<Landing />);
    fireEvent.click(
      screen.getAllByRole("button", { name: "Enter the dockyard" })[0],
    );
    expect(mockNavigate).toHaveBeenCalledWith("/login?redirect=/lothal");
  });

  it("sends authenticated users straight to the workshop", () => {
    setAuth({ isAuthenticated: true, autoLogin: false });
    render(<Landing />);
    fireEvent.click(
      screen.getAllByRole("button", { name: "Open your workshop" })[0],
    );
    expect(mockNavigate).toHaveBeenCalledWith("/lothal");
  });

  it("treats auto-login deployments as authenticated", () => {
    setAuth({ isAuthenticated: false, autoLogin: true });
    render(<Landing />);
    expect(
      screen.getAllByRole("button", { name: "Open your workshop" }).length,
    ).toBeGreaterThan(0);
  });

  it("scrolls to the journey section from the hero", () => {
    const scrollSpy = jest.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    render(<Landing />);
    fireEvent.click(screen.getByRole("button", { name: "See the journey" }));
    expect(scrollSpy).toHaveBeenCalled();
  });
});
