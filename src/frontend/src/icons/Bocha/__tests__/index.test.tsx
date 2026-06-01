import { render, screen } from "@testing-library/react";
import { BochaIcon } from "../index";

jest.mock("../Bocha", () => ({
  __esModule: true,
  default: ({ ...props }) => <svg data-testid="mocked-bocha-svg" {...props} />,
}));

describe("BochaIcon", () => {
  it("renders the Bocha svg icon", () => {
    render(<BochaIcon data-testid="bocha-icon" />);

    expect(screen.getByTestId("bocha-icon")).toBeInTheDocument();
    expect(screen.getByTestId("bocha-icon").tagName.toLowerCase()).toBe("svg");
  });
});
