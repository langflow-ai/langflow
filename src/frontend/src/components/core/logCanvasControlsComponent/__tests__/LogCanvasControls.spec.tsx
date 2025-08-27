import { render, screen } from "@testing-library/react";
import LogCanvasControls from "../index";

jest.mock("@/modals/flowLogsModal", () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="logs-modal">{children}</div>,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span data-testid="icon" />,
}));
jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));

describe("LogCanvasControls", () => {
  it("renders panel and button", () => {
    render(<LogCanvasControls />);
    expect(screen.getByTestId("canvas_controls")).toBeInTheDocument();
    expect(screen.getByText("Logs")).toBeInTheDocument();
  });
});
