import { render, screen } from "@testing-library/react";

// Simple test to verify Jest setup works
describe("Basic Test Setup", () => {
  it("should render a simple div", () => {
    render(<div data-testid="test-div">Hello World</div>);
    expect(screen.getByTestId("test-div")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("should handle basic assertions", () => {
    expect(true).toBe(true);
    expect(1 + 1).toBe(2);
    expect("hello").toContain("ell");
  });
});
