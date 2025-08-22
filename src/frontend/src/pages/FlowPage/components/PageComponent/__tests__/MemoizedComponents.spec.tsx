import { fireEvent, render, screen } from "@testing-library/react";
import {
  MemoizedCanvasControls,
  MemoizedLogCanvasControls,
  MemoizedSidebarTrigger,
} from "../MemoizedComponents";

jest.mock("@/components/core/canvasControlsComponent/CanvasControls", () => ({
  __esModule: true,
  default: ({ children }) => (
    <div data-testid="canvas-controls">{children}</div>
  ),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }) => <span data-testid="icon">{name}</span>,
}));
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...rest }) => (
    <div data-testid="panel" {...rest}>
      {children}
    </div>
  ),
}));
jest.mock("@/components/core/logCanvasControlsComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="log-controls" />,
}));
jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
}));
// Avoid utils importing darkStore
jest.mock("@/utils/utils", () => ({
  __esModule: true,
  cn: (...args) => args.filter(Boolean).join(" "),
}));

describe("MemoizedComponents", () => {
  it("clicking add note sets state and positions shadow box", () => {
    const setIsAddingNote = jest.fn();
    document.body.innerHTML = '<div id="shadow-box"></div>';
    render(
      <MemoizedCanvasControls
        setIsAddingNote={setIsAddingNote}
        position={{ x: 100, y: 200 }}
        shadowBoxWidth={40}
        shadowBoxHeight={20}
      />,
    );
    fireEvent.click(screen.getByTestId("add_note"));
    expect(setIsAddingNote).toHaveBeenCalledWith(true);
    const box = document.getElementById("shadow-box")! as HTMLDivElement;
    expect(box.style.display).toBe("block");
    expect(box.style.left).toBe("80px");
    expect(box.style.top).toBe("190px");
  });

  it("renders sidebar trigger and log controls", () => {
    render(<MemoizedSidebarTrigger />);
    expect(screen.getByText("Components")).toBeInTheDocument();
    render(<MemoizedLogCanvasControls />);
    expect(screen.getByTestId("log-controls")).toBeInTheDocument();
  });
});
